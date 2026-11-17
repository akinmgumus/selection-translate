"""Clean up text copied out of PDFs and decide whether it is worth translating."""
import re

MAX_CHARS = 5000

# "optimi-\n  zation" -> "optimization": a hyphen at the end of a line, between letters.
_HYPHEN_BREAK = re.compile(r"(\w)-[ \t]*\r?\n\s*(\w)")
_WHITESPACE = re.compile(r"\s+")


def clean_pdf_text(raw: str) -> str:
    """Re-join PDF line breaks and hyphenated words; collapse whitespace."""
    text = _HYPHEN_BREAK.sub(r"\1\2", raw)
    return _WHITESPACE.sub(" ", text).strip()


def should_translate(text: str, last: str | None) -> bool:
    """True if the (cleaned) text is new, non-empty, has letters and is not too long."""
    cleaned = clean_pdf_text(text)
    if not cleaned or cleaned == last:
        return False
    if len(cleaned) > MAX_CHARS:
        return False
    return any(ch.isalpha() for ch in cleaned)
