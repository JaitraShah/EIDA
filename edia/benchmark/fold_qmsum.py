"""
Task 5 step 4: fold the five already-validated QMSum pairs into the benchmark as
QSUM_001-005, in the same BenchmarkPair schema as the synthetic pairs.

Nothing is re-judged here. The `in_document` label for each element comes from the
Task 1 tables via qmsum_ground_truth.present_in_document -- an element Task 1
recorded as surviving into the general summary is PRESENT, everything else is
OMITTED. Matching is lexical against the recorded present-list, with the results
printed so the mapping is inspectable rather than implicit.

Two honest asymmetries versus the synthetic pairs, worth stating wherever these
numbers appear together:

  1. QMSum "documents" are the QMSum general summaries, which are annotator-written
     summaries of a meeting -- not filed decision records. Task 1 already flagged
     this substitution; folding the pairs in does not launder it.
  2. Present QMSum elements are labelled PRESENT_UNSPECIFIED, not verbatim vs
     paraphrased, because Task 1 did not record that distinction. The one case we
     know is a paraphrase (the wood/plastic element that produced the single Task 2
     NLI false positive) is labelled PARAPHRASED explicitly.
"""

from __future__ import annotations

from pathlib import Path

from ..extraction.schema import ElementType
from .dataset import BenchmarkPair, ElementLabel, InDocument, PairSource
from .qmsum_ground_truth import GROUND_TRUTH, GroundTruthPair
from .score import content_tokens, token_f1

DATA = Path("data/qmsum")
PAIRS_DIR = Path("data/benchmark/pairs")   # one directory for the whole benchmark

PRESENT_MATCH_THRESHOLD = 0.6

# A decision element needs most of itself covered before it counts as present.
# Without this, QSUM_001's decision ("a single-curved casing was chosen") matches the
# document's bare mention of the phrase "single-curved casing" and comes out labelled
# present -- which is precisely the opposite of what Task 1 found: the summary names
# all three shapes and never says which one won.
DECISION_RECALL_THRESHOLD = 0.7

# Elements known from Task 2 to be present-but-reworded rather than present-verbatim.
# Keyed by (pair_id, lowercase substring of the element text).
KNOWN_PARAPHRASES = {
    ("QSUM_004", "wood was chosen over plastic"),
}


def label_for(pair: GroundTruthPair, text: str, etype: ElementType) -> InDocument:
    best = max((token_f1(text, p) for p in pair.present_in_document), default=0.0)
    if best < PRESENT_MATCH_THRESHOLD:
        return InDocument.OMITTED

    if etype is ElementType.DECISION:
        own = content_tokens(text)
        covered = max(
            (len(own & content_tokens(p)) / len(own) for p in pair.present_in_document),
            default=0.0,
        ) if own else 0.0
        if covered < DECISION_RECALL_THRESHOLD:
            return InDocument.OMITTED

    lowered = text.lower()
    for pid, needle in KNOWN_PARAPHRASES:
        if pid == pair.pair_id and needle in lowered:
            return InDocument.PARAPHRASED
    return InDocument.PRESENT_UNSPECIFIED


def build_pair(truth: GroundTruthPair) -> BenchmarkPair:
    transcript_path = DATA / f"{truth.pair_id}_transcript.json"
    document_path = DATA / f"{truth.pair_id}_document.txt"
    if not transcript_path.exists() or not document_path.exists():
        raise SystemExit(
            f"{truth.pair_id}: missing prepared files -- run scripts/prepare_qmsum.py first"
        )

    # The transcript is stored QMSum-shaped; render it to the same flat
    # "Speaker: text" form the synthetic pairs use so both are comparable.
    from ..ingestion.ingest import ingest_file

    transcript = ingest_file(str(transcript_path), doc_type="transcript").raw_text
    document = document_path.read_text(encoding="utf-8")

    elements: list[ElementLabel] = []
    i = 0
    for decision in truth.decisions:
        for etype, text in decision.reasoning_elements():
            i += 1
            elements.append(
                ElementLabel(
                    element_id=f"{truth.pair_id}_e{i:02d}",
                    element_type=etype,
                    text=text,
                    in_document=label_for(truth, text, etype),
                    decision_id=decision.decision_id,
                )
            )

    return BenchmarkPair(
        pair_id=truth.pair_id,
        source=PairSource.QMSUM,
        topic="ami_product_design",
        title=truth.title,
        transcript=transcript,
        document=document,
        decisions=list(truth.decisions),
        elements=elements,
        generation=None,
        label_provenance="hand",
        notes=(
            truth.notes
            + "\n\nLabels come from Task 1 (outputs/gap_validation_results.md), not from a "
            "fresh annotation pass. Present elements are PRESENT_UNSPECIFIED because Task 1 "
            "did not record verbatim-vs-paraphrase; the document is a QMSum general summary "
            "standing in for a filed decision record."
        ),
    )


def main() -> int:
    PAIRS_DIR.mkdir(parents=True, exist_ok=True)
    for truth in GROUND_TRUTH:
        pair = build_pair(truth)
        path = pair.save(PAIRS_DIR)
        omitted = [e for e in pair.elements if e.in_document is InDocument.OMITTED]
        print(
            f"{pair.pair_id}: {len(pair.elements)} elements, "
            f"{len(omitted)} gaps, {pair.present_count} present -> {path}"
        )
        for e in pair.elements:
            if e.in_document is not InDocument.OMITTED:
                print(f"    present [{e.element_type.value}] {e.text[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
