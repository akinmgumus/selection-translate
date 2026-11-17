from placement import place_popup, popup_width


def test_width_bounds():
    assert popup_width("hi") == 250
    assert popup_width("x" * 2000) == 600


def test_below_pointer_when_room():
    assert place_popup(500, 300, 300, 400, 100, 1920, 1080) == (500, 320, 100)  # aligned to selection left edge


def test_above_line_when_no_room_below():
    x, y, h = place_popup(500, 1000, 1000, 400, 150, 1920, 1080)
    assert h == 150
    assert y + h <= 1000 - 24  # popup bottom stays above the selected line
    assert y >= 0


def test_clamped_to_right_and_left_edges():
    assert place_popup(1900, 300, 300, 400, 100, 1920, 1080)[0] == 1520
    assert place_popup(-20, 300, 300, 400, 100, 1920, 1080)[0] == 0


def test_multiline_selection_near_bottom_goes_above_first_line():
    # selection spans y=900..1000; popup must not cover any of it
    x, y, h = place_popup(500, 900, 1000, 400, 150, 1920, 1080)
    assert y + h <= 900 - 24


def test_upward_drag_goes_below_last_line():
    # pressed at y=600, released at y=500 (pointer ends on the TOP line)
    x, y, h = place_popup(500, 500, 600, 400, 100, 1920, 1080)
    assert y >= 600 + 20


def test_too_tall_for_both_sides_shrinks_and_never_covers_selection():
    top, bottom = 500, 520
    x, y, h = place_popup(500, top, bottom, 400, 900, 1920, 1080)
    assert h < 900
    assert y >= bottom + 20 or y + h <= top - 24
    assert y >= 0 and y + h <= 1080
