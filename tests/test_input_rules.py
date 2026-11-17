from input_rules import is_mouse_selection, selection_anchor


def test_selection_while_button_held_is_mouse():
    assert is_mouse_selection(True, now=10.0, last_release_at=None)


def test_selection_right_after_release_is_mouse():
    # some apps claim the selection just after the button goes up
    assert is_mouse_selection(False, now=10.2, last_release_at=10.0)


def test_selection_without_any_click_is_keyboard():
    assert not is_mouse_selection(False, now=10.0, last_release_at=None)


def test_selection_long_after_last_click_is_keyboard():
    assert not is_mouse_selection(False, now=12.0, last_release_at=10.0)


def test_anchor_single_line_drag_left_to_right():
    assert selection_anchor((300, 500), (700, 500)) == (300, 500, 500)


def test_anchor_upward_drag():
    # pressed lower-right, released upper-left
    assert selection_anchor((700, 600), (300, 500)) == (300, 500, 600)


def test_anchor_without_press_uses_release():
    assert selection_anchor(None, (400, 450)) == (400, 450, 450)


from input_rules import is_ignored_app  # noqa: E402


def test_firefox_is_ignored_snap_and_deb():
    assert is_ignored_app("firefox_firefox", ["firefox"])   # Ubuntu snap Firefox
    assert is_ignored_app("Firefox", ["firefox"])           # .deb Firefox, any case


def test_other_apps_are_not_ignored():
    assert not is_ignored_app("Evince", ["firefox"])
    assert not is_ignored_app("com.microsoft.VSCode", ["firefox"])


def test_unknown_window_is_not_ignored():
    assert not is_ignored_app(None, ["firefox"])
