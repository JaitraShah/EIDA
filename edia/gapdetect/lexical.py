"""
Lexical gap detector -- the offline, model-free baseline.

Present-score = max token-F1 between the element and any single sentence of the
document (same primitive `fold_qmsum.label_for` uses to fold the 5 gold pairs, and
the same shape as `generate.find_leaks`). It is deliberately weak: it cannot see a
paraphrase, which is exactly the failure mode Task 2 flagged. Its job in the eval
is to show how much the NLI detector buys over pure lexical overlap.
"""

from __future__ import annotations

from ..benchmark.score import token_f1
from ..benchmark.textutil import split_sentences
from .base import BaseGapDetector

DEFAULT_THRESHOLD = 0.45


class LexicalGapDetector(BaseGapDetector):
    name = "lexical"

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold

    def present_score(self, document: str, element_text: str) -> float:
        sents = split_sentences(document) or [document]
        return max((token_f1(element_text, s) for s in sents), default=0.0)
