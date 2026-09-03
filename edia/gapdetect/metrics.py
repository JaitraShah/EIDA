"""Gap-class classification metrics (positive class = OMITTED = "the document
dropped this"). Shared by calibration and the full gap eval.

Framing follows Task 2: a false positive is "said gap, was actually present"; a
false negative is "missed a real gap". Zero false negatives across the true gaps
is the headline the project cares about (never hide a dropped rationale)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GapMetrics:
    tp: int = 0   # predicted gap, is gap
    fp: int = 0   # predicted gap, was present
    fn: int = 0   # predicted present, was gap   <- the expensive error
    tn: int = 0   # predicted present, is present

    @property
    def n(self) -> int:
        return self.tp + self.fp + self.fn + self.tn

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.n if self.n else 0.0

    @property
    def gap_base_rate(self) -> float:
        return (self.tp + self.fn) / self.n if self.n else 0.0

    # -- the present class ---------------------------------------------------
    # Gap-class metrics alone are nearly free on this data: with a ~93% gap base
    # rate an all-gap detector scores F1 0.962. The present class is the hard half
    # -- "did the detector notice the document DID keep this?" -- and it is where
    # lexical falls apart (accuracy 0.448 on present_unspecified). Always report
    # both, or `balanced_accuracy`.

    @property
    def present_precision(self) -> float:
        d = self.tn + self.fn
        return self.tn / d if d else 0.0

    @property
    def present_recall(self) -> float:
        """Specificity: of the elements the document really kept, how many were
        correctly called present."""
        d = self.tn + self.fp
        return self.tn / d if d else 0.0

    @property
    def present_f1(self) -> float:
        p, r = self.present_precision, self.present_recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def balanced_accuracy(self) -> float:
        """Mean of gap recall and present recall -- immune to the base rate. An
        all-gap detector scores 0.5 here however skewed the data is."""
        return (self.recall + self.present_recall) / 2

    def add(self, predicted_gap: bool, actual_gap: bool) -> None:
        if predicted_gap and actual_gap:
            self.tp += 1
        elif predicted_gap and not actual_gap:
            self.fp += 1
        elif not predicted_gap and actual_gap:
            self.fn += 1
        else:
            self.tn += 1

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "gap_base_rate": round(self.gap_base_rate, 3),
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
            "accuracy": round(self.accuracy, 3),
            "present_precision": round(self.present_precision, 3),
            "present_recall": round(self.present_recall, 3),
            "present_f1": round(self.present_f1, 3),
            "balanced_accuracy": round(self.balanced_accuracy, 3),
            "confusion": {"tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn},
        }


def sweep_threshold(
    present_scores: list[float], actual_gaps: list[bool], grid=None
) -> list[dict]:
    """P/R/F1 on the gap class at each candidate present-threshold.

    An element is a predicted gap when present_score < threshold.
    """
    if grid is None:
        grid = [round(x / 100, 2) for x in range(20, 85, 5)]
    rows = []
    for t in grid:
        m = GapMetrics()
        for s, g in zip(present_scores, actual_gaps):
            m.add(predicted_gap=(s < t), actual_gap=g)
        rows.append({"threshold": t, **m.to_dict()})
    return rows
