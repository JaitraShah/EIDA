"""
The benchmark pair format shared by the synthetic pairs (Task 5) and the five
already-validated QMSum pairs (Task 1, folded in as QSUM_001-005).

One format for both is the point: the QMSum pairs are the reality check on the
synthetic ones. If a method scores well on synthetic pairs and badly on QSUM pairs,
the generator has made the task too easy, and that comparison is only possible if
both live in the same schema.

`in_document` deliberately has three "present" states, not two. Task 2 found that
the single NLI failure across 22 checks was a paraphrase-mismatch -- a reasoning
element that WAS in the document but phrased differently ("suggested... agreed by
the group" vs "chose"). A benchmark whose positives are all verbatim copies would
hide exactly that failure mode, so the generator plants paraphrased positives on
purpose and labels them as such.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..extraction.schema import SCHEMA_VERSION, DecisionRecord, ElementType

DATASET_VERSION = "1.0.0"


class InDocument(str, Enum):
    OMITTED = "omitted"                       # absent -> gold_gap = True
    VERBATIM = "verbatim"                     # present in near-identical wording
    PARAPHRASED = "paraphrased"               # present but reworded (the hard positive)
    PRESENT_UNSPECIFIED = "present_unspecified"  # present; wording relationship not labelled


class PairSource(str, Enum):
    SYNTHETIC = "synthetic"
    QMSUM = "qmsum"


class ElementLabel(BaseModel):
    """One reasoning element and whether the document kept it."""

    model_config = ConfigDict(extra="forbid")

    element_id: str
    element_type: ElementType
    text: str
    in_document: InDocument
    decision_id: str

    @property
    def gold_gap(self) -> bool:
        """True = the document dropped this. The label a gap detector is scored on."""
        return self.in_document is InDocument.OMITTED


class GenerationMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    temperature: float
    seed: int
    prompt_version: str
    sampled: bool = True


class AnnotationMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotator: str
    labels: dict[str, InDocument] = Field(default_factory=dict)   # element_id -> label
    flagged: list[str] = Field(default_factory=list)              # element_ids the annotator disputes
    unrealistic: bool = False                                     # whole pair rejected as implausible
    notes: str = ""
    minutes_spent: Optional[float] = None


class BenchmarkPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair_id: str
    source: PairSource
    topic: str
    title: str = ""
    transcript: str
    document: str
    decisions: list[DecisionRecord] = Field(default_factory=list)
    elements: list[ElementLabel] = Field(default_factory=list)
    generation: Optional[GenerationMeta] = None
    annotations: list[AnnotationMeta] = Field(default_factory=list)
    notes: str = ""
    schema_version: str = SCHEMA_VERSION
    dataset_version: str = DATASET_VERSION

    @property
    def gap_count(self) -> int:
        return sum(e.gold_gap for e in self.elements)

    @property
    def present_count(self) -> int:
        return len(self.elements) - self.gap_count

    def save(self, directory: str | Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.pair_id}.json"
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> "BenchmarkPair":
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def load_all(directory: str | Path) -> list[BenchmarkPair]:
    directory = Path(directory)
    if not directory.exists():
        return []
    return [BenchmarkPair.load(p) for p in sorted(directory.glob("*.json"))]


def dataset_stats(pairs: list[BenchmarkPair]) -> dict:
    by_source: dict[str, int] = {}
    by_label: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for p in pairs:
        by_source[p.source.value] = by_source.get(p.source.value, 0) + 1
        for e in p.elements:
            by_label[e.in_document.value] = by_label.get(e.in_document.value, 0) + 1
            by_type[e.element_type.value] = by_type.get(e.element_type.value, 0) + 1
    total_elements = sum(len(p.elements) for p in pairs)
    gaps = sum(p.gap_count for p in pairs)
    return {
        "pairs": len(pairs),
        "by_source": by_source,
        "elements": total_elements,
        "gaps": gaps,
        "gap_rate": round(gaps / total_elements, 3) if total_elements else 0.0,
        "by_in_document": by_label,
        "by_element_type": by_type,
        "annotated_pairs": sum(bool(p.annotations) for p in pairs),
        "double_annotated_pairs": sum(len(p.annotations) >= 2 for p in pairs),
    }
