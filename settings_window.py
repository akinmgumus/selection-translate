"""Settings window (Ctrl+Super+Right): engine, DeepL key, my/second language."""
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from engines import CONFIG_PATH, base_language, load_config  # noqa: E402
from languages import fetch_languages, normalize_code, save_languages  # noqa: E402

HELP = ("Text in any language is translated into <b>My language</b>.\n"
        "Text already in My language is translated into <b>Second language</b>.")

ENGINES = (("deepl", "DeepL (API key)"), ("google", "Google Translate (free, no key)"))


class SettingsWindow(Gtk.Window):
    def __init__(self, config_path: Path = CONFIG_PATH,
                 languages: list[tuple[str, str]] | None = None):
        super().__init__(title="Selection Translate — Settings")
        self.config_path = Path(config_path)
        config = load_config(self.config_path)
        self.names = {}
        langs = languages if languages is not None else fetch_languages(config)
        self.names = dict(langs)

        self.set_border_width(14)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        help_label = Gtk.Label(xalign=0)
        help_label.set_markup(HELP)
        grid.attach(help_label, 0, 0, 2, 1)

        self.engine = Gtk.ComboBoxText()
        for engine_id, label in ENGINES:
            self.engine.append(engine_id, label)
        self.engine.set_active_id("deepl" if config.get("engine") == "deepl" else "google")
        self.key = Gtk.Entry(visibility=False, width_chars=38,
                             placeholder_text="your DeepL API key (Free keys end in :fx)")
        self.key.set_text(config.get("deepl_key") or "")
        self.key_label = Gtk.Label(label="DeepL API key:", xalign=1)
        for widget in (self.key, self.key_label):
            widget.set_no_show_all(True)  # shown only while DeepL is selected
        self.engine.connect("changed", lambda *_: self._update_key_row())
        self._update_key_row()

        self.mine = self._combo(langs, config["my_language"])
        self.second = self._combo(langs, config["second_language"])
        rows = (("Engine:", self.engine), (self.key_label, self.key),
                ("My language:", self.mine), ("Second language:", self.second))
        for row, (label, widget) in enumerate(rows, start=1):
            if isinstance(label, str):
                label = Gtk.Label(label=label, xalign=1)
            grid.attach(label, 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)

        self.error = Gtk.Label(xalign=0)
        self.error.get_style_context().add_class("error")
        grid.attach(self.error, 0, 5, 2, 1)

        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.destroy())
        save = Gtk.Button(label="Save")
        save.get_style_context().add_class("suggested-action")
        save.connect("clicked", self._on_save_clicked)
        buttons.pack_start(cancel, False, False, 0)
        buttons.pack_start(save, False, False, 0)
        grid.attach(buttons, 0, 6, 2, 1)

        self.add(grid)
        self.connect("key-press-event", self._on_key)

    def _combo(self, langs: list[tuple[str, str]], current: str) -> Gtk.ComboBoxText:
        combo = Gtk.ComboBoxText()
        combo.set_wrap_width(4)  # grid of names: ~100 languages fit on one screen
        for code, name in langs:
            combo.append(code, name)
        # "en" in the config -> "en-us" in the list; "de-de" -> "de" if merged
        if not combo.set_active_id(normalize_code(current)):
            combo.set_active_id(base_language(current))
        return combo

    def _update_key_row(self) -> None:
        deepl = self.engine.get_active_id() == "deepl"
        self.key.set_visible(deepl)
        self.key_label.set_visible(deepl)

    def save(self) -> bool:
        """Write engine, key and languages; False (with a message) if not possible."""
        mine, second = self.mine.get_active_id(), self.second.get_active_id()
        if not mine or not second:
            self.error.set_text("Please choose both languages.")
            return False
        engine = self.engine.get_active_id()
        extra = {"engine": engine}
        if engine == "deepl":
            key = self.key.get_text().strip()
            if not key:
                self.error.set_text("Enter your DeepL API key, or choose Google Translate.")
                return False
            extra["deepl_key"] = key  # for Google the stored key is kept, not erased
        try:
            save_languages(mine, second, self.config_path, extra=extra)
        except (ValueError, OSError) as exc:
            self.error.set_text(str(exc))
            return False
        return True

    def _on_save_clicked(self, *_):
        if self.save():
            mine = self.names.get(self.mine.get_active_id(), self.mine.get_active_id())
            second = self.names.get(self.second.get_active_id(), self.second.get_active_id())
            engine = dict(ENGINES)[self.engine.get_active_id()].split(" (")[0]
            notify(f"{engine}: everything → {mine}, {mine} → {second}")
            self.destroy()

    def _on_key(self, _widget, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._on_save_clicked()
            return True
        return False


def notify(message: str) -> None:
    try:
        subprocess.Popen(["notify-send", "-t", "2500", "-h", "int:transient:1",
                          "Selection Translate", message])
    except OSError:
        pass


def run() -> int:
    window = SettingsWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    window.present()
    Gtk.main()
    return 0
