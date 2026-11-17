"""Rules about mouse input: was a selection made with the mouse, and where is it."""

MOUSE_GRACE_SECONDS = 0.5  # apps may claim the selection shortly after the button goes up


def is_mouse_selection(buttons_down: bool, now: float, last_release_at: float | None,
                       grace: float = MOUSE_GRACE_SECONDS) -> bool:
    """True if a selection change at time `now` came from the mouse.

    Mouse = a button is held right now (dragging, double-click), or was released
    less than `grace` seconds ago. Anything else (Shift+arrows, Ctrl+A) is keyboard.
    """
    if buttons_down:
        return True
    return last_release_at is not None and now - last_release_at <= grace


def selection_anchor(press: tuple[int, int] | None,
                     release: tuple[int, int]) -> tuple[int, int, int]:
    """(left_x, top_y, bottom_y) of a selection from its press and release points.

    Works for drags in any direction; without a known press point, the
    release point alone is used.
    """
    if press is None:
        press = release
    (x1, y1), (x2, y2) = press, release
    return min(x1, x2), min(y1, y2), max(y1, y2)


def is_ignored_app(window_class: str | None, ignored: list[str]) -> bool:
    """True if the active window's class matches an ignored app name.

    Case-insensitive substring match, so "firefox" covers both the snap
    ("firefox_firefox") and the .deb ("Firefox") builds.
    """
    if not window_class:
        return False
    name = window_class.lower()
    return any(app.lower() in name for app in ignored if app)
