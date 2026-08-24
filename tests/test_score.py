"""Scoring tests -- offline, no model needed."""
import pytest

from edia.benchmark.qmsum_ground_truth import BY_ID, GROUND_TRUTH
from edia.benchmark.score import (
    check_evidence_grounding,
    normalize,
    render_markdown,
    score_extraction,
    token_f1,
)
from edia.extraction.schema import DecisionRecord, ExtractionResult

CHUNK_TEXT = (
    "Project Manager: What about Kryptonite?\n"
    "Industrial Designer: I would prefer a battery, and I am skeptical of the dynamo.\n"
    "Project Manager: The chip is the most expensive part regardless.\n"
    "User Interface: The website did not give an actual cost.\n"
)


def rec(**kw) -> DecisionRecord:
    base = dict(decision_id="d1", source_id="QSUM_002", chunk_id="c0", decision="d")
    base.update(kw)
    return DecisionRecord(**base)


def result_with(*records) -> ExtractionResult:
    return ExtractionResult(
        source_id="QSUM_002", records=list(records),
        chunks_processed=1, model_name="test",
    )


# --- ground-truth fixture integrity -----------------------------------------

def test_five_pairs_present():
    assert [p.pair_id for p in GROUND_TRUTH] == [
        "QSUM_001", "QSUM_002", "QSUM_003", "QSUM_004", "QSUM_005"
    ]


def test_ground_truth_uses_frozen_schema():
    for p in GROUND_TRUTH:
        for d in p.decisions:
            assert isinstance(d, DecisionRecord)
            assert d.schema_version == "1.0.0"


def test_task1_specifics_encoded():
    """Spot-check the details Task 1 called out, so a careless edit here is caught."""
    q3 = BY_ID["QSUM_003"]
    assert any(d.status.value == "provisional" for d in q3.decisions), "'temporarily decided'"
    q2 = BY_ID["QSUM_002"]
    assert any("did not give an actual cost" in c for d in q2.decisions for c in d.conditions)
    assert any("battery" in x.lower() for d in q2.decisions for x in d.dissent)
    q4 = BY_ID["QSUM_004"]
    # four distinct objections behind the intelligent-controller rejection
    assert len(q4.decisions[0].rationale) == 4


def test_present_in_document_recorded():
    assert BY_ID["QSUM_005"].present_in_document == ["speech recognition"]
    assert len(BY_ID["QSUM_004"].present_in_document) == 5


# --- matching primitives -----------------------------------------------------

def test_normalize_ignores_case_and_punctuation():
    assert normalize("The  chip, regardless!") == "the chip regardless"


def test_token_f1_identical_is_one():
    assert token_f1("the chip is expensive", "the chip is expensive") == pytest.approx(1.0)


def test_token_f1_unrelated_is_zero():
    assert token_f1("kryptonite chosen", "meeting adjourned") == 0.0


def test_token_f1_partial():
    s = token_f1(
        "The chip dominates cost so power source cost is secondary",
        "The chip is the most expensive part regardless, so the energy source cost is a secondary concern",
    )
    assert 0.3 < s < 1.0


# --- evidence grounding ------------------------------------------------------

def test_verbatim_quote_is_grounded():
    r = rec(evidence=[{"quote": "What about Kryptonite?", "supports": "decision"}])
    checks = check_evidence_grounding([r], {"c0": CHUNK_TEXT})
    assert checks[0].grounded


def test_whitespace_and_case_differences_forgiven():
    r = rec(evidence=[{"quote": "the   website did not give an ACTUAL cost", "supports": "condition"}])
    assert check_evidence_grounding([r], {"c0": CHUNK_TEXT})[0].grounded


def test_fabricated_quote_is_ungrounded():
    r = rec(evidence=[{"quote": "The board approved a budget of 40 euros.", "supports": "rationale"}])
    assert not check_evidence_grounding([r], {"c0": CHUNK_TEXT})[0].grounded


def test_paraphrased_quote_counts_as_ungrounded():
    """Paraphrasing inside a quote is a fabrication for our purposes -- the prompt
    demands verbatim, and a paraphrase cannot be audited back to the transcript."""
    r = rec(evidence=[{"quote": "the site gave no real price", "supports": "condition"}])
    assert not check_evidence_grounding([r], {"c0": CHUNK_TEXT})[0].grounded


# --- end-to-end scoring ------------------------------------------------------

def test_perfect_extraction_scores_full_completeness():
    truth = BY_ID["QSUM_002"]
    records = []
    for i, d in enumerate(truth.decisions):
        records.append(
            rec(decision_id=f"x{i}", decision=d.decision, topic=d.topic, status=d.status,
                alternatives=[a.model_dump() for a in d.alternatives],
                rationale=list(d.rationale), conditions=list(d.conditions),
                dissent=list(d.dissent))
        )
    report = score_extraction(result_with(*records), truth, chunk_texts={"c0": CHUNK_TEXT})
    assert report.completeness == 1.0
    assert report.gt_matched == report.gt_total


def test_empty_extraction_scores_zero_completeness_without_hallucinating():
    truth = BY_ID["QSUM_002"]
    report = score_extraction(result_with(), truth, chunk_texts={"c0": CHUNK_TEXT})
    assert report.completeness == 0.0
    assert report.unsupported_evidence_rate == 0.0, "no quotes means no fabrication"
    assert report.unmatched_extracted == []


def test_hallucination_rate_counts_ungrounded_quotes_only():
    truth = BY_ID["QSUM_002"]
    r = rec(
        decision="Kryptonite was chosen as the preferred energy source.",
        evidence=[
            {"quote": "What about Kryptonite?", "supports": "decision"},
            {"quote": "The CFO signed off on the budget.", "supports": "approver"},
        ],
    )
    report = score_extraction(result_with(r), truth, chunk_texts={"c0": CHUNK_TEXT})
    assert report.quotes_total == 2
    assert report.quotes_grounded == 1
    assert report.unsupported_evidence_rate == pytest.approx(0.5)
    assert report.ungrounded_quotes[0].supports == "approver"


def test_owner_approver_excluded_from_headline_completeness():
    """Task 1 caveat 1: owner/approver is a dataset limitation, not an extractor miss."""
    truth = BY_ID["QSUM_005"]  # has approver="Project Manager"
    report = score_extraction(result_with(), truth)
    assert report.gt_soft_total >= 1
    soft_texts = [m.gt_text for m in report.matches if m.gt_type in ("owner", "approver")]
    assert "Project Manager" in soft_texts
    # the approver element must not be inside the headline denominator
    assert report.gt_total == len(truth.all_elements()) - report.gt_soft_total


def test_unmatched_extracted_is_reported_separately():
    truth = BY_ID["QSUM_002"]
    r = rec(decision="The team agreed to order pizza for the next meeting.")
    report = score_extraction(result_with(r), truth)
    assert report.unmatched_extracted
    assert report.unmatched_element_rate == 1.0
    assert report.unsupported_evidence_rate == 0.0, "unmatched != hallucinated"


def test_markdown_renders_totals():
    truth = BY_ID["QSUM_002"]
    report = score_extraction(result_with(rec()), truth, chunk_texts={"c0": CHUNK_TEXT})
    md = render_markdown([report])
    assert "TOTAL" in md and "QSUM_002" in md
