"""Benchmark-side tests: dataset schema, label assignment, leak detection,
QMSum fold-in, and agreement maths. All offline."""
import random

import pytest

from edia.benchmark.agreement import cohens_kappa, compare, jaccard, report
from edia.benchmark.dataset import (
    AnnotationMeta,
    BenchmarkPair,
    ElementLabel,
    InDocument,
    PairSource,
    dataset_stats,
)
from edia.benchmark.fold_qmsum import build_pair, label_for
from edia.benchmark.generate import assign_labels, find_leaks, spec_to_record
from edia.benchmark.qmsum_ground_truth import BY_ID
import re

from edia.benchmark.topics import (
    ARCHETYPES,
    DOMAINS,
    PAIRS_PER_TOPIC,
    TOPICS,
    pair_plan,
)
from edia.extraction.schema import ElementType


def make_pair(pair_id="SYN_011", labels=None, annotations=None) -> BenchmarkPair:
    labels = labels or [InDocument.OMITTED, InDocument.VERBATIM, InDocument.PARAPHRASED]
    return BenchmarkPair(
        pair_id=pair_id, source=PairSource.SYNTHETIC, topic="cloud_migration",
        transcript="PM: hello\nSRE: hi", document="We decided.",
        elements=[
            ElementLabel(
                element_id=f"{pair_id}_e{i:02d}", element_type=ElementType.RATIONALE,
                text=f"element {i}", in_document=lab, decision_id=f"{pair_id}_d1",
            )
            for i, lab in enumerate(labels, start=1)
        ],
        annotations=annotations or [],
    )


# --- plan --------------------------------------------------------------------

def test_plan_shape():
    plan = pair_plan()
    assert len(TOPICS) == len(DOMAINS) * len(ARCHETYPES)
    assert len(plan) == len(TOPICS) * PAIRS_PER_TOPIC
    assert 1500 <= len(plan) <= 2500, "target ~2000 synthetic pairs"

    ids = [p[0] for p in plan]
    seeds = [p[3] for p in plan]
    assert len(set(ids)) == len(plan), "unique pair ids"
    assert len(set(seeds)) == len(plan), "unique seeds -- the old int(id.split) scheme collided"
    assert all(re.fullmatch(r"SYN_\d{4}_\d{3}", pid) for pid in ids)


def test_topics_are_not_ami_product_design():
    """QMSum already covers that domain; duplicating it would break the comparison."""
    keys = {t.key for t in TOPICS}
    assert "ami_product_design" not in keys
    assert all("__" in k for k in keys), "keys are <domain>__<archetype>"


# --- dataset schema ----------------------------------------------------------

def test_gold_gap_only_for_omitted():
    pair = make_pair()
    assert [e.gold_gap for e in pair.elements] == [True, False, False]
    assert pair.gap_count == 1
    assert pair.present_count == 2


def test_roundtrip_save_load(tmp_path):
    pair = make_pair()
    path = pair.save(tmp_path)
    loaded = BenchmarkPair.load(path)
    assert loaded.pair_id == pair.pair_id
    assert loaded.elements[0].in_document is InDocument.OMITTED


def test_dataset_stats():
    stats = dataset_stats([make_pair("SYN_011"), make_pair("SYN_012")])
    assert stats["pairs"] == 2
    assert stats["elements"] == 6
    assert stats["gaps"] == 2
    assert stats["by_source"]["synthetic"] == 2


# --- label assignment --------------------------------------------------------

def test_assign_labels_is_deterministic_for_a_seed():
    elements = [(ElementType.DECISION, "d"), (ElementType.RATIONALE, "r"),
                (ElementType.ALTERNATIVE, "a"), (ElementType.DISSENT, "x")]
    a = assign_labels(elements, random.Random(7))
    b = assign_labels(elements, random.Random(7))
    assert a == b


def test_assign_labels_always_leaves_at_least_one_gap_and_one_present():
    elements = [(ElementType.DECISION, "d"), (ElementType.RATIONALE, "r"),
                (ElementType.CONDITION, "c"), (ElementType.DISSENT, "x")]
    for seed in range(50):
        labels = assign_labels(elements, random.Random(seed))
        assert any(l is InDocument.OMITTED for l in labels), seed
        assert any(l is not InDocument.OMITTED for l in labels), seed


def test_paraphrased_positives_actually_occur():
    """Task 2's failure mode needs present-but-reworded examples in the benchmark."""
    elements = [(ElementType.DECISION, "d"), (ElementType.RATIONALE, "r"),
                (ElementType.ALTERNATIVE, "a")]
    seen = set()
    for seed in range(80):
        seen.update(assign_labels(elements, random.Random(seed)))
    assert InDocument.PARAPHRASED in seen
    assert InDocument.OMITTED in seen


# --- leak detection ----------------------------------------------------------

def _omitted(text):
    return ElementLabel(
        element_id="e1", element_type=ElementType.CONDITION, text=text,
        in_document=InDocument.OMITTED, decision_id="d1",
    )


def test_leak_detected_when_document_mentions_omitted_element():
    doc = ("Migration approved. The team noted the vendor contract has an early "
           "termination penalty of forty thousand euros.")
    leaks = find_leaks(doc, [_omitted("The vendor contract has an early termination penalty of forty thousand euros.")])
    assert leaks and leaks[0]["score"] >= 0.6


def test_no_leak_when_document_is_clean():
    doc = "Migration to the new platform was approved. Rollout starts in March."
    leaks = find_leaks(doc, [_omitted("The vendor contract has an early termination penalty of forty thousand euros.")])
    assert leaks == []


def test_scattered_words_are_not_a_leak():
    """Content words spread across the document are coincidence, not a leak."""
    doc = ("The contract was signed. Early feedback was positive. Termination of the "
           "pilot is not planned. The penalty box is a hockey reference nobody enjoyed.")
    leaks = find_leaks(doc, [_omitted("The vendor contract has an early termination penalty of forty thousand euros.")])
    assert leaks == []


# --- spec -> record ----------------------------------------------------------

def test_spec_to_record_tolerates_loose_model_output():
    rec = spec_to_record(
        {
            "decision": "Adopt Postgres",
            "status": "kind of decided",
            "alternatives": ["MySQL", {"option": "DynamoDB", "rejected": True, "reason": "cost"}],
            "rationale": "team knows it",
            "conditions": None,
            "owner": "platform lead",
            "approver": "null",
        },
        "SYN_011",
    )
    assert rec.status.value == "decided"        # unrecognised status falls back
    assert [a.option for a in rec.alternatives] == ["MySQL", "DynamoDB"]
    assert rec.rationale == ["team knows it"]
    assert rec.conditions == []
    assert rec.approver is None


# --- QMSum fold-in -----------------------------------------------------------

def test_fold_preserves_task1_labels():
    pair = build_pair(BY_ID["QSUM_002"])
    assert pair.source is PairSource.QMSUM
    present = [e.text for e in pair.elements if not e.gold_gap]
    assert present == ["Kryptonite was chosen as the preferred energy source."]
    assert pair.gap_count == 7


def test_qsum_001_decision_is_a_gap():
    """Task 1: the summary names all three casing shapes but never says which won."""
    pair = build_pair(BY_ID["QSUM_001"])
    decisions = [e for e in pair.elements if e.element_type is ElementType.DECISION]
    assert all(e.gold_gap for e in decisions)
    alts_present = [e for e in pair.elements
                    if e.element_type is ElementType.ALTERNATIVE and not e.gold_gap]
    assert len(alts_present) == 3


def test_task2_false_positive_is_labelled_paraphrased():
    pair = build_pair(BY_ID["QSUM_004"])
    wood = next(e for e in pair.elements if "Wood was chosen" in e.text)
    assert wood.in_document is InDocument.PARAPHRASED


def test_qsum_003_provisional_condition_survives():
    pair = build_pair(BY_ID["QSUM_003"])
    cond = next(e for e in pair.elements if e.element_type is ElementType.CONDITION)
    assert not cond.gold_gap, "Task 1 found the document kept 'temporarily'"


def test_label_for_requires_most_of_a_decision():
    truth = BY_ID["QSUM_001"]
    assert label_for(truth, "single-curved casing", ElementType.ALTERNATIVE) is not InDocument.OMITTED
    assert label_for(
        truth, "A single-curved casing was chosen for the remote control.",
        ElementType.DECISION,
    ) is InDocument.OMITTED


# --- agreement ---------------------------------------------------------------

def test_jaccard_basics():
    assert jaccard(set(), set()) == 1.0
    assert jaccard({"a"}, {"a"}) == 1.0
    assert jaccard({"a"}, {"b"}) == 0.0
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_kappa_perfect_and_chance():
    assert cohens_kappa([True, False, True], [True, False, True]) == pytest.approx(1.0)
    assert cohens_kappa([True, True, True], [True, True, True]) == pytest.approx(1.0)
    assert cohens_kappa([True, False], [False, True]) < 0


def annotated(pair_id, a_labels, b_labels):
    pair = make_pair(pair_id, labels=[InDocument.OMITTED] * len(a_labels))
    ids = [e.element_id for e in pair.elements]
    pair.annotations = [
        AnnotationMeta(annotator="a", labels=dict(zip(ids, a_labels))),
        AnnotationMeta(annotator="b", labels=dict(zip(ids, b_labels))),
    ]
    return pair


def test_compare_flags_disagreements():
    O, V = InDocument.OMITTED, InDocument.VERBATIM
    pair = annotated("SYN_011", [O, O, V], [O, V, V])
    result = compare(pair)
    assert result.elements == 3
    assert result.jaccard == pytest.approx(0.5)
    assert len(result.disagreements) == 1


def test_report_warns_when_high_jaccard_is_base_rate_inflation():
    O, V = InDocument.OMITTED, InDocument.VERBATIM
    # both annotators mark almost everything a gap: Jaccard high, kappa ~0
    pair = annotated("SYN_011", [O] * 9 + [V], [O] * 9 + [O])
    result = report([pair])
    assert result["pooled_jaccard"] > 0.6
    assert result["target_met"] is True
    assert "chance agreement" in result["kappa_caveat"]


def test_report_handles_no_double_annotation():
    assert report([make_pair()])["double_annotated_pairs"] == 0


# --- generation supervisor ----------------------------------------------------

def test_supervisor_defaults_to_the_whole_plan(tmp_path, monkeypatch):
    """The supervisor's job is 'until the plan is on disk' -- its default target
    must track pair_plan(), not a hardcoded number."""
    import importlib.util
    from pathlib import Path as _P

    spec = importlib.util.spec_from_file_location(
        "gensup", _P(__file__).resolve().parents[1] / "scripts" / "generation_supervisor.py"
    )
    sup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sup)

    monkeypatch.setattr(sup, "PAIRS_DIR", tmp_path)
    assert sup.generated_count() == 0
    (tmp_path / "SYN_0001_001.json").write_text("{}", encoding="utf-8")
    (tmp_path / "QMS_PRD_TR_000.json").write_text("{}", encoding="utf-8")
    assert sup.generated_count() == 1, "counts SYN_* only, not the QMSum pairs"

    from edia.benchmark.topics import pair_plan
    assert len(pair_plan()) == 2040
