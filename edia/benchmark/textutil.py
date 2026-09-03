"""
Small shared text helpers for the benchmark side.

`split_sentences` is the one place the "split prose into sentence-ish units" regex
lives. `edia.benchmark.generate` (leak checking) and `edia.benchmark.decompose`
(QMSum element extraction) both use it, so a change to sentence handling is a
one-line change here rather than three subtly-different copies.

`edia.extraction.chunker` keeps its own turn-local `_SENTENCE_RE`: it splits a
single oversized speaker turn and must not also break on newlines (there are none
inside a rendered turn) or strip, because its output feeds a token-budget
calculation the chunker tests pin to within 5%. That regex is deliberately not
merged here.
"""

from __future__ import annotations

import re

# Sentence boundary: after . ! or ? followed by whitespace. QMSum specific-query
# answers are also frequently newline-separated bullet-ish clauses, so a run of
# newlines is a boundary too.
_SENTENCE_OR_LINE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str, *, split_newlines: bool = True) -> list[str]:
    """Split prose into stripped, non-empty sentence-ish units.

    split_newlines=True (default) also treats a run of newlines as a boundary,
    which matches how `generate.find_leaks` historically split documents and how
    QMSum answers are laid out. Pass False for whitespace-joined text where a
    stray newline should not start a new unit.
    """
    if not text:
        return []
    rx = _SENTENCE_OR_LINE_RE if split_newlines else _SENTENCE_END_RE
    return [s.strip() for s in rx.split(text) if s and s.strip()]
