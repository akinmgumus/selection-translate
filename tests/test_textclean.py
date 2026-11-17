from textclean import clean_pdf_text, should_translate


def test_joins_hyphenated_line_break():
    assert clean_pdf_text("optimi-\nzation step") == "optimization step"


def test_joins_broken_lines_and_spaces():
    assert clean_pdf_text("the loss\nfunction  is\n\nconvex ") == "the loss function is convex"


def test_keeps_real_hyphen_inside_line():
    assert clean_pdf_text("state-of-the-art model") == "state-of-the-art model"


def test_should_translate_rules():
    assert should_translate("Gradient descent", None)
    assert not should_translate("   ", None)
    assert not should_translate("Gradient descent", "Gradient descent")
    assert not should_translate("3.14 (12)", None)
    assert not should_translate("a" * 5001, None)
