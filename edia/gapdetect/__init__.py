"""
Gap detection: given a filed decision document and one reasoning element from the
discussion, decide whether the document contains that element (present) or dropped
it (a gap).

This is the Task 2 mechanism, finally in code. Task 2's transfer test put
`roberta-large-mnli` at 95.5% on a 22-element pilot and concluded "use NLI as the
primary gap detector, not just an ablation" (outputs/nli_transfer_test_results.md).

All detectors share one interface:

    detector.label_element(document, element_text) -> (InDocument, float)
    detector.is_gap(document, element_text) -> bool

`label_element` returns `InDocument.OMITTED` for a gap and
`InDocument.PRESENT_UNSPECIFIED` otherwise (NLI/lexical cannot tell verbatim from
paraphrased -- only that the content is there). The float is the detector's
present-confidence in [0, 1], kept for threshold calibration and auditing.
"""

from .base import GapDetector

__all__ = ["GapDetector"]
