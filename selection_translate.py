#!/usr/bin/env python3
"""Selection Translate: select text anywhere (e.g. a PDF in Evince) and a popup
shows its translation into `my_language` (default Turkish); text already in
that language goes to `second_language` (default English). See README.

Run:  python3 selection_translate.py [--debug]   start (stays in the background)
      python3 selection_translate.py --on          turn on (starts it if not running)
      python3 selection_translate.py --off         turn off (pause; no popups)
      python3 selection_translate.py --settings    choose languages
"""
import ctypes
import ctypes.util
import fcntl
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11, GLib, Gtk, Pango  # noqa: E402,F401

from engines import TranslateError, load_config, translate_auto  # noqa: E402
from input_rules import is_ignored_app, is_mouse_selection, selection_anchor  # noqa: E402
from placement import place_popup, popup_width  # noqa: E402
from textclean import clean_pdf_text, should_translate  # noqa: E402

LOCK_PATH = Path.home() / ".cache" / "selection-translate.lock"
TICK_MS = 25           # how often we look at the mouse (fast enough to catch quick clicks/taps)
STABLE_SECONDS = 0.3   # selection must stay unchanged this long after mouse release
MAX_HEIGHT_RATIO = 0.6
MARGIN = 6             # outer margin of the popup content, px
XK_ESCAPE = 0xFF1B
BUTTONS = (Gdk.ModifierType.BUTTON1_MASK | Gdk.ModifierType.BUTTON2_MASK
           | Gdk.ModifierType.BUTTON3_MASK)

CSS = b"""
.st-popup { background-color: @theme_base_color; border: 1px solid @borders; }
.st-header { font-size: 85%; font-weight: bold; color: @insensitive_fg_color; }
.st-body { font-size: 110%; padding: 2px 4px 6px 4px; }
.st-error { color: @error_color; }
.st-warning { color: @warning_color; }
.st-popup button { padding: 0 6px; min-height: 0; min-width: 0; }
"""

DEBUG = False


def log(msg: str) -> None:
    if DEBUG:
        print(f"[selection-translate] {msg}", file=sys.stderr, flush=True)


class Popup(Gtk.Window):
    """Borderless, never-focused window showing one translation."""

    def __init__(self, on_closed):
        # POPUP = override-redirect: no title bar, no keyboard focus, always on top.
        super().__init__(type=Gtk.WindowType.POPUP)
        self._on_closed = on_closed
        self._anchor = (0, 0, 0)  # selection left x, top y, bottom y
        self._width = 250
        self._text = ""
        self.get_style_context().add_class("st-popup")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin=MARGIN)
        header = self.header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.lang = Gtk.Label(xalign=0, wrap=True)  # wraps if a fallback warning is shown
        self.lang.get_style_context().add_class("st-header")
        self.copy_btn = Gtk.Button(label="Copy", relief=Gtk.ReliefStyle.NONE)
        self.copy_btn.connect("clicked", self._copy)
        close_btn = Gtk.Button(label="×", relief=Gtk.ReliefStyle.NONE)
        close_btn.connect("clicked", lambda *_: self.close_popup())
        header.pack_start(self.lang, True, True, 0)
        header.pack_end(close_btn, False, False, 0)
        header.pack_end(self.copy_btn, False, False, 0)

        self.body = Gtk.Label(xalign=0, yalign=0, selectable=True, wrap=True)
        self.body.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.body.get_style_context().add_class("st-body")
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.add(self.body)

        outer.pack_start(header, False, False, 0)
        outer.pack_start(self.scroller, True, True, 0)
        self.add(outer)

    # --- public API used by the app ---------------------------------------
    def show_loading(self, source_text: str, left_x: int, sel_top: int, sel_bottom: int) -> None:
        self._anchor = (left_x, sel_top, sel_bottom)
        self._width = popup_width(source_text)
        self.lang.set_text("…")
        self._set_body("Translating…", error=False)

    def show_result(self, text: str, source: str, target: str, note: str = "") -> None:
        # note: fallback warning, e.g. "Google · DeepL limit reached" (shown in orange)
        header = f"{source.upper()} → {target.upper()}"
        self.lang.set_text(f"{header}  ·  {note}" if note else header)
        ctx = self.lang.get_style_context()
        (ctx.add_class if note else ctx.remove_class)("st-warning")
        self._width = max(self._width, popup_width(text))
        self._set_body(text, error=False)

    def show_error(self, message: str) -> None:
        self.lang.get_style_context().remove_class("st-warning")
        self.lang.set_text("Error")
        self._set_body(message, error=True)

    def contains_point(self, x: int, y: int) -> bool:
        if not self.get_visible():
            return False
        wx, wy = self.get_position()
        w, h = self.get_size()
        return wx <= x < wx + w and wy <= y < wy + h

    def close_popup(self) -> None:
        if self.get_visible():
            self.hide()
            self._on_closed()

    # --- internals ----------------------------------------------------------
    def _set_body(self, text: str, error: bool) -> None:
        self._text = text
        self.body.set_text(text)
        ctx = self.body.get_style_context()
        (ctx.add_class if error else ctx.remove_class)("st-error")
        self.copy_btn.set_label("Copy")
        self.copy_btn.set_sensitive(not error)
        self._layout()

    def measure(self, inner_width: int) -> tuple[int, int]:
        """(chrome height, body text height) for the current text at this width.

        Asked explicitly with the width: a ScrolledWindow would ask its wrapping
        label for a height without a width and get a single-line answer.
        """
        self.get_child().show_all()  # hidden widgets report height 0; window stays unmapped
        self.body.set_size_request(inner_width, -1)
        body_h =self.body.get_preferred_height_for_width(inner_width)[1]
        header_h = self.header.get_preferred_height()[1]
        chrome = header_h + 2 + 2 * MARGIN + 2  # header + box spacing + margins + border
        return chrome, body_h

    def _layout(self) -> None:
        px, top, bottom = self._anchor
        area = Gdk.Display.get_default().get_monitor_at_point(px, bottom).get_workarea()
        inner = self._width - 2 * MARGIN - 2
        chrome, body_h = self.measure(inner)
        wanted = chrome + min(body_h, int(area.height * MAX_HEIGHT_RATIO))
        x, y, h = place_popup(px, top, bottom, self._width, wanted, area.width, area.height,
                              screen_x=area.x, screen_y=area.y)
        shown_body = max(h - chrome, 1)
        scroll = Gtk.PolicyType.NEVER if body_h <= shown_body else Gtk.PolicyType.AUTOMATIC
        self.scroller.set_policy(Gtk.PolicyType.NEVER, scroll)
        self.scroller.set_size_request(inner, shown_body)
        # size and place first, then show: avoids a frame at the old size/spot
        self.resize(self._width, h)
        self.move(x, y)
        self.show_all()

    def _copy(self, *_):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(self._text, -1)
        self.copy_btn.set_label("Copied")


class XClassHint(ctypes.Structure):
    _fields_ = [("res_name", ctypes.c_void_p), ("res_class", ctypes.c_void_p)]


class X11Probe:
    """Small read-only questions to the X server, via libX11 (no focus needed).

    - esc_down(): is Esc held right now? Like the mouse polling, this only
      *looks* at the key state, so Evince still receives the key press.
    - active_window_class(): app class of the focused window, e.g. "Evince",
      "firefox_firefox".
    """

    def __init__(self):
        self._x = None
        try:
            x = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "libX11.so.6")
            x.XOpenDisplay.restype = ctypes.c_void_p
            x.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x.XKeysymToKeycode.restype = ctypes.c_ubyte
            x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            x.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_char * 32]
            x.XGetClassHint.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(XClassHint)]
            x.XFree.argtypes = [ctypes.c_void_p]
            self._dpy = x.XOpenDisplay(None)
            if self._dpy:
                self._esc = x.XKeysymToKeycode(self._dpy, XK_ESCAPE)
                self._keys = (ctypes.c_char * 32)()  # 256 bits, one per keycode
                self._x = x
        except OSError as exc:
            log(f"no X11 access, Esc and app filter disabled: {exc}")

    def esc_down(self) -> bool:
        if self._x is None:
            return False
        self._x.XQueryKeymap(self._dpy, self._keys)
        return bool(self._keys.raw[self._esc // 8] >> (self._esc % 8) & 1)

    def active_window_class(self) -> str | None:
        if self._x is None:
            return None
        window = Gdk.Screen.get_default().get_active_window()
        if window is None or not hasattr(window, "get_xid"):
            return None
        hint = XClassHint()
        if not self._x.XGetClassHint(self._dpy, window.get_xid(), ctypes.byref(hint)):
            return None
        try:
            return ctypes.string_at(hint.res_class).decode("utf-8", "replace") if hint.res_class else None
        finally:
            for ptr in (hint.res_name, hint.res_class):
                if ptr:
                    self._x.XFree(ptr)


class App:
    """Watches the PRIMARY selection and drives the popup."""

    def __init__(self):
        self.primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self.primary.connect("owner-change", self._on_selection_changed)
        self.popup = Popup(on_closed=self._on_popup_closed)
        self.pending = False
        self.changed_at = 0.0
        self.last_text: str | None = None
        self.request_id = 0
        self.enabled = True
        self.press_pos: tuple[int, int] | None = None    # where the last mouse press began
        self.release_pos: tuple[int, int] | None = None  # where it ended
        self.last_release_at: float | None = None
        self.button_was_down = False
        self.esc_was_down = False
        self.x11 = X11Probe()
        display = Gdk.Display.get_default()
        self.pointer = display.get_default_seat().get_pointer()
        self.root = Gdk.get_default_root_window()
        GLib.timeout_add(TICK_MS, self._tick)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.pending = False
        if not enabled:
            self.popup.close_popup()
        log("enabled" if enabled else "disabled")

    def _on_selection_changed(self, clipboard, _event):
        if not self.enabled or clipboard.get_owner() is not None:
            return  # paused, or selection made inside our own popup
        try:
            _, _, _, mask = self.root.get_device_position(self.pointer)
        except Exception as exc:
            log(f"pointer query failed: {exc!r}")
            return
        now = time.monotonic()
        # Apps like Evince claim a dragged selection the instant the button goes
        # up, before our 25 ms poll records the release. If the last poll still
        # saw a button held, the release just happened: count it as the mouse.
        held = bool(mask & BUTTONS) or self.button_was_down
        if not is_mouse_selection(held, now, self.last_release_at):
            log(f"ignored keyboard selection (button now={bool(mask & BUTTONS)}, "
                f"poll saw held={self.button_was_down}, last release={self.last_release_at})")
            return
        window_class = self.x11.active_window_class()
        if is_ignored_app(window_class, load_config()["ignore_apps"]):
            log(f"ignored selection in {window_class}")
            return
        self.pending = True
        self.changed_at = now

    def _tick(self) -> bool:
        try:
            self._poll_pointer()
            self._poll_keys()
        except Exception as exc:  # never let one bad poll kill the timer
            log(f"tick error: {exc!r}")
        return True  # keep the timer running

    def _poll_keys(self) -> None:
        if not self.popup.get_visible():
            self.esc_was_down = False
            return
        esc = self.x11.esc_down()
        if esc and not self.esc_was_down:
            self.popup.close_popup()
        self.esc_was_down = esc

    def _poll_pointer(self) -> None:
        _, x, y, mask = self.root.get_device_position(self.pointer)
        buttons_down = bool(mask & BUTTONS)
        if buttons_down and not self.button_was_down:           # button just went down
            self.press_pos = (x, y)
            if self.popup.get_visible() and not self.popup.contains_point(x, y):
                self.popup.close_popup()
        elif not buttons_down and self.button_was_down:         # button just went up
            self.release_pos = (x, y)
            self.last_release_at = time.monotonic()
        self.button_was_down = buttons_down
        if not buttons_down and self.pending and time.monotonic() - self.changed_at >= STABLE_SECONDS:
            self.pending = False
            # Anchor to where the selection was made, not where the mouse is now.
            anchor = selection_anchor(self.press_pos, self.release_pos or (x, y))
            self.primary.request_text(self._on_text, anchor)

    def _on_text(self, _clipboard, text, pos):
        if text is None or not should_translate(text, self.last_text):
            return
        cleaned = clean_pdf_text(text)
        self.last_text = cleaned
        self.request_id += 1
        rid = self.request_id
        log(f"#{rid} selected: {cleaned[:80]!r}")
        left_x, top_y, bottom_y = pos
        self.popup.show_loading(cleaned, left_x, top_y, bottom_y)
        threading.Thread(target=self._translate_worker, args=(rid, cleaned), daemon=True).start()

    def _translate_worker(self, rid: int, text: str) -> None:
        # Runs off the GTK thread; results go back through GLib.idle_add.
        try:
            result = translate_auto(text, load_config())
            GLib.idle_add(self._on_result, rid, result, None)
        except TranslateError as exc:
            GLib.idle_add(self._on_result, rid, None, str(exc))
        except Exception as exc:  # never let a worker crash silently
            GLib.idle_add(self._on_result, rid, None, f"Unexpected error: {exc}")

    def _on_result(self, rid, result, error) -> bool:
        if rid != self.request_id or not self.enabled:
            log(f"#{rid} dropped (newer selection exists)")
            return False
        if error:
            log(f"#{rid} error: {error}")
            self.popup.show_error(error)
        else:
            log(f"#{rid} {result.source} → {result.target}: {result.text[:80]!r}")
            note = f"Google · {result.notice}" if result.notice else ""
            self.popup.show_result(result.text, result.source, result.target, note=note)
        return False  # run once

    def _on_popup_closed(self):
        # Let the same sentence be translated again after the popup was dismissed,
        # and make any translation still in flight stale so it can't reopen it.
        self.last_text = None
        self.request_id += 1


def acquire_lock():
    """Take the single-instance lock and record our PID in it; None if taken."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_PATH, "a+")  # "a+": never wipe the running instance's PID
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def running_pid() -> int | None:
    """PID of the running instance, or None if none is running."""
    if not LOCK_PATH.exists():
        return None
    with open(LOCK_PATH, "a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.seek(0)
            text = handle.read().strip()
            return int(text) if text.isdigit() else None
        fcntl.flock(handle, fcntl.LOCK_UN)
        return None


def notify(message: str) -> None:
    try:
        subprocess.Popen(["notify-send", "-t", "1500", "-h", "int:transient:1",
                          "Selection Translate", message])
    except OSError:
        pass


def main(argv: list[str]) -> int:
    global DEBUG
    DEBUG = "--debug" in argv
    if "--settings" in argv:
        import settings_window
        return settings_window.run()
    pid = running_pid()
    if "--off" in argv:
        if pid:
            os.kill(pid, signal.SIGUSR2)
        else:
            notify("Translate: OFF")
        return 0
    if pid:
        if "--on" in argv:
            os.kill(pid, signal.SIGUSR1)
        else:
            print("selection-translate is already running", file=sys.stderr)
        return 0
    lock = acquire_lock()
    if lock is None:
        print("selection-translate is already running", file=sys.stderr)
        return 0
    css = Gtk.CssProvider()
    css.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    app = App()

    def switch(enabled: bool) -> bool:
        app.set_enabled(enabled)
        notify("Translate: ON" if enabled else "Translate: OFF")
        return True  # keep the signal handler installed

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, switch, True)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, switch, False)
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, Gtk.main_quit)
    if "--on" in argv:
        notify("Translate: ON")
    log("running; select some text")
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
