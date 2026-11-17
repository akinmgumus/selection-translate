"""GTK-level tests. They need an X display; skipped otherwise."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="needs an X display")

import selection_translate as st  # noqa: E402
from engines import Translation  # noqa: E402

LONG = ("Reinforcement learning agents learn a policy by interacting with an environment "
        "and receiving rewards; the objective is to maximise the expected discounted return "
        "over trajectories sampled from the policy. ") * 3


def test_body_height_grows_with_text():
    p = st.Popup(on_closed=lambda: None)
    p.body.set_text("hi")
    _, short_h = p.measure(238)
    p.body.set_text(LONG)
    _, long_h = p.measure(238)
    assert long_h > 4 * short_h


def test_closed_popup_is_not_reopened_by_late_result():
    app = st.App()
    app.request_id = 5                     # a translation (#5) is in flight
    app._on_popup_closed()                 # user clicks elsewhere meanwhile
    app._on_result(5, Translation("Merhaba", "en", "tr"), None)
    assert not app.popup.get_visible()
    app.popup.destroy()


def test_pointer_polled_fast_enough_for_quick_clicks():
    assert st.TICK_MS <= 30


def test_tick_survives_errors():
    app = st.App()

    def boom(*_):
        raise RuntimeError("X hiccup")

    app.root = type("R", (), {"get_device_position": boom})()
    assert app._tick() is True             # timer keeps running
    app.popup.destroy()


class FakeRoot:
    def __init__(self, mask=0):
        self.mask = mask

    def get_device_position(self, _pointer):
        return None, 100, 100, self.mask


def test_keyboard_selection_is_ignored():
    app = st.App()
    app.root = FakeRoot(mask=0)            # no mouse button down, no recent click
    app._on_selection_changed(app.primary, None)
    assert not app.pending
    app.popup.destroy()


def test_mouse_selection_is_accepted():
    app = st.App()
    app.x11 = FakeX11("Evince")
    app.root = FakeRoot(mask=st.Gdk.ModifierType.BUTTON1_MASK)
    app._on_selection_changed(app.primary, None)
    assert app.pending
    app.popup.destroy()


class FakeX11:
    def __init__(self, active_class="Evince"):
        self.down = False
        self.active_class = active_class

    def esc_down(self):
        return self.down

    def active_window_class(self):
        return self.active_class


def test_esc_closes_popup():
    app = st.App()
    app.root = FakeRoot(mask=0)
    app.x11 = FakeX11()
    app.popup.show_loading("hello", -10000, -10000, -10000)
    assert app.popup.get_visible()
    app.x11.down = True
    app._tick()
    assert not app.popup.get_visible()
    app.popup.destroy()


def test_disabled_ignores_selections_and_hides_popup():
    app = st.App()
    app.root = FakeRoot(mask=st.Gdk.ModifierType.BUTTON1_MASK)
    app.x11 = FakeX11("Evince")
    app.popup.show_loading("hello", -10000, -10000, -10000)
    app.set_enabled(False)
    assert not app.popup.get_visible()
    app._on_selection_changed(app.primary, None)
    assert not app.pending
    app.set_enabled(True)
    app._on_selection_changed(app.primary, None)
    assert app.pending
    app.popup.destroy()


def test_running_pid_reports_none_when_not_running(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "LOCK_PATH", tmp_path / "x.lock")
    assert st.running_pid() is None


def test_running_pid_reports_holder(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "LOCK_PATH", tmp_path / "x.lock")
    handle = st.acquire_lock()
    assert handle is not None
    assert st.running_pid() == os.getpid()
    handle.close()


def test_selection_in_firefox_is_ignored():
    app = st.App()
    app.root = FakeRoot(mask=st.Gdk.ModifierType.BUTTON1_MASK)
    app.x11 = FakeX11("firefox_firefox")
    app._on_selection_changed(app.primary, None)
    assert not app.pending
    app.popup.destroy()
