"""Shared detector interface + the present/gap decision rule."""

from __future__ import annotations

from typing import Protocol

from ..benchmark.dataset import InDocument


def label_from_present_score(score: float, threshold: float) -> InDocument:
    """One place for the rule every detector applies: at or above threshold the
    element's content is in the document (PRESENT_UNSPECIFIED -- wording
    relationship not judged); below it, the document dropped it (OMITTED)."""
    return InDocument.PRESENT_UNSPECIFIED if score >= threshold else InDocument.OMITTED


class GapDetector(Protocol):
    """Structural type. `label_element` and `is_gap` are what callers use."""

    name: str

    def present_score(self, document: str, element_text: str) -> float:
        """Confidence in [0, 1] that `document` contains `element_text`'s content."""
        ...

    def label_element(self, document: str, element_text: str) -> tuple[InDocument, float]:
        ...

    def is_gap(self, document: str, element_text: str) -> bool:
        ...


class BaseGapDetector:
    """Mixin: implement `present_score` + set `threshold`, get the rest free."""

    name = "base"
    threshold: float = 0.5

    def present_score(self, document: str, element_text: str) -> float:  # pragma: no cover
        raise NotImplementedError

    def label_element(self, document: str, element_text: str) -> tuple[InDocument, float]:
        s = self.present_score(document, element_text)
        return label_from_present_score(s, self.threshold), s

    def is_gap(self, document: str, element_text: str) -> bool:
        return self.label_element(document, element_text)[0] is InDocument.OMITTED
