"""Deterministic text metrics (counting is done in code, never by the model)."""

import re


def count_words(text):
    return len(text.split())


def count_sentences(text):
    stripped = text.strip()
    if not stripped:
        return 0
    parts = re.split(r"[.!?]+", stripped)
    return len([part for part in parts if part.strip()])


def count_paragraphs(text):
    stripped = text.strip()
    if not stripped:
        return 0
    parts = re.split(r"\n\s*\n", stripped)
    return len([part for part in parts if part.strip()])


def clean_countdown(text):
    """Remove CAPEL countdown markers (<k>) before counting."""
    return re.sub(r"<\d+>", " ", text).strip()


def evaluate(text, lo, hi, target):
    """Evaluate a response against the desired word window.

    `lo`/`hi`/`target` are the *desired* values (not necessarily what the prompt
    literally requested, which may be over-asked). Pass None for experiments
    without a length dimension.
    """
    word_count = count_words(text)
    result = {
        "word_count": word_count,
        "sentence_count": count_sentences(text),
        "paragraph_count": count_paragraphs(text),
        "in_window": None,
        "under": None,
        "over": None,
        "abs_error": None,
    }
    if lo is not None and hi is not None:
        result["in_window"] = lo <= word_count <= hi
        result["under"] = word_count < lo
        result["over"] = word_count > hi
        if target is not None:
            result["abs_error"] = abs(word_count - target)
    return result
