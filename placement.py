"""Popup width and on-screen position (pure arithmetic, no GTK)."""

MIN_WIDTH = 250
MAX_WIDTH = 600


def popup_width(text: str) -> int:
    """Short text -> narrow popup, long text -> up to MAX_WIDTH px."""
    return max(MIN_WIDTH, min(MAX_WIDTH, 8 * len(text) // 3))


MIN_HEIGHT = 40


def place_popup(px: int, sel_top: int, sel_bottom: int, w: int, h: int,
                screen_w: int, screen_h: int, gap: int = 20, line_h: int = 24,
                screen_x: int = 0, screen_y: int = 0) -> tuple[int, int, int]:
    """Where to put a w x h popup so it never covers the selection.

    sel_top / sel_bottom: pointer y where the selection started and ended
    (either order of dragging), i.e. the first and last selected lines.
    Returns (x, y, height). Prefers below the last line; else above the first
    line; if neither side fits, uses the roomier side and shrinks the height
    (the popup then scrolls). screen_x/screen_y: the monitor's origin.
    """
    top, bottom = min(sel_top, sel_bottom), max(sel_top, sel_bottom)
    x = max(min(px, screen_x + screen_w - w), screen_x)  # px = selection left edge

    below_y = bottom + gap                      # popup top edge if placed below
    above_limit = top - line_h                  # popup bottom edge if placed above
    space_below = screen_y + screen_h - below_y
    space_above = above_limit - screen_y

    if h <= space_below:
        return x, below_y, h
    if h <= space_above:
        return x, above_limit - h, h
    if space_below >= space_above:
        return x, below_y, max(space_below, MIN_HEIGHT)
    fit = max(space_above, MIN_HEIGHT)
    return x, above_limit - fit, fit
