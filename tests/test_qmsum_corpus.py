"""QMSum corpus ingestion + decomposition -- all offline, no model."""
import json

import pytest

from edia.benchmark.dataset import InDocument, PairSource
from edia.benchmark.decompose import (
    SentenceDecomposer,
    classify_element_type,
    get_decomposer,
)
from edia.benchmark.qmsum_corpus import (
    GOLD_PRODUCT_TEST,
    build_pair,
    corpus_stats,
    general_summary,
    iter_meetings,
    meeting_id,
)
from edia.extraction.schema import ElementType
from edia.ingestion.parsers.json_parser import parse_json_transcript, turns_to_text

TURNS = [
    {"speaker": "Project Manager", "content": "Let's start."},
    {"speaker": "Marketing", "content": "I disagree with the budget."},
    {"content": "no speaker here"},
]


def _fake_row(n_general=1, n_specific=2, doc_words=60):
    long_answer = " ".join(["word"] * doc_words)
    return {
        "topic_list": [{"topic": "t", "relevant_text_span": [["0", "9"]]}],
        "general_query_list": [{"query": "summarise", "answer": long_answer}
                               for _ in range(n_general)],
        "specific_query_list": [
            {"query": f"q{i}", "answer": (
                "The team decided to adopt Postgres. "
                "MySQL was rejected because of replication lag. "
                "Cost of the managed tier is still unresolved. "
                "The DBA disagreed and preferred CockroachDB."
            ), "relevant_text_span": [["1", "5"]]}
            for i in range(n_specific)
        ],
        "meeting_transcripts": TURNS,
    }


def _fake_tree(tmp_path):
    root = tmp_path / "raw"
    for domain, splits in {"Academic": ["train"], "Committee": ["val"],
                           "Product": ["test"]}.items():
        for split in splits:
            d = root / domain
            d.mkdir(parents=True, exist_ok=True)
            rows = [_fake_row() for _ in range(14)]  # Product/test needs idx 5,7,9,10,12
            (d / f"{split}.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows), encoding="utf-8"
            )
    return root


# --- shared transcript render ---------------------------------------------------

def test_turns_to_text_matches_file_parser(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"meeting_transcripts": TURNS}), encoding="utf-8")
    from_file, meta_file = parse_json_transcript(str(p))
    from_mem, meta_mem = turns_to_text(TURNS)
    assert from_file == from_mem
    assert meta_file == meta_mem == {"turn_count": 3}
    assert "Project Manager: Let's start." in from_mem
    assert "no speaker here" in from_mem  # speakerless turn kept as bare text


def test_turns_to_text_empty():
    assert turns_to_text([]) == ("", {"turn_count": 0})
    assert turns_to_text(None) == ("", {"turn_count": 0})


# --- general summary ----------------------------------------------------------

def test_general_summary_joins_all_answers():
    row = {"general_query_list": [{"answer": "A."}, {"answer": "B."}, {"answer": ""}]}
    assert general_summary(row) == "A.\n\nB."


# --- meeting iteration ------------------------------------------------------------

def test_iter_meetings_ids_and_gold_holdout(tmp_path):
    root = _fake_tree(tmp_path)
    meetings = list(iter_meetings(root))
    ids = [m.meeting_id for m in meetings]

    assert ids == [m.meeting_id for m in iter_meetings(root)], "deterministic order"
    assert len(ids) == len(set(ids)), "unique ids"
    assert meeting_id("Academic", "train", 0) == "QMS_ACA_TR_000"
    assert "QMS_PRD_TE_005" not in ids, "gold Product/test row 5 held out by default"
    assert all(m.gold_pair_id is None for m in meetings)

    # 14 Product/test rows - 5 gold = 9 emitted
    prod = [m for m in meetings if m.domain == "Product"]
    assert len(prod) == 14 - len(GOLD_PRODUCT_TEST)

    withgold = list(iter_meetings(root, include_gold=True))
    gold = [m for m in withgold if m.gold_pair_id]
    assert {m.gold_pair_id for m in gold} == set(GOLD_PRODUCT_TEST.values())


def test_iter_meetings_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(iter_meetings(tmp_path / "nope"))


def test_corpus_stats_shape(tmp_path):
    stats = corpus_stats(_fake_tree(tmp_path))
    # Academic/train 14 + Committee/val 14 + Product/test (14 - 5 gold) 9
    assert stats["meetings"] == 14 + 14 + 9
    assert stats["by_domain"] == {"Academic": 14, "Committee": 14, "Product": 9}
    assert stats["short_document_meetings_excluded"] == 0


# --- element type classification ------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("The team decided to adopt Postgres.", ElementType.DECISION),
    ("MySQL was rejected because of replication lag.", ElementType.ALTERNATIVE),
    ("This was chosen because it is cheaper and the team knows it.", ElementType.RATIONALE),
    ("The managed-tier cost is still unresolved.", ElementType.CONDITION),
    ("The DBA disagreed and preferred CockroachDB.", ElementType.DISSENT),
    ("The migration was signed off by the CTO.", ElementType.APPROVER),
])
def test_classify_element_type(text, expected):
    assert classify_element_type(text) == expected


def test_classify_first_sentence_biases_to_decision():
    plain = "The remote will be blue and round with a small screen."
    assert classify_element_type(plain) == ElementType.RATIONALE
    assert classify_element_type(plain, is_first_in_answer=True) == ElementType.DECISION


# --- sentence decomposer -------------------------------------------------------

def test_sentence_decomposer_splits_and_filters():
    sql = [{"query": "db choice", "answer": (
        "The team decided to adopt Postgres for the primary store. "
        "Yes. "  # too short -> dropped
        "MySQL was rejected because replication lag exceeded the SLA."
    )}]
    els = SentenceDecomposer().decompose(sql)
    assert [e.text for e in els] == [
        "The team decided to adopt Postgres for the primary store.",
        "MySQL was rejected because replication lag exceeded the SLA.",
    ]
    assert els[0].element_type == ElementType.DECISION
    assert els[0].query_index == 0
    assert els[1].element_type == ElementType.ALTERNATIVE


def test_get_decomposer_unknown():
    with pytest.raises(ValueError):
        get_decomposer("magic")


# --- build_pair --------------------------------------------------------------

def test_build_pair_is_qmsum_auto_silver(tmp_path):
    root = _fake_tree(tmp_path)
    m = next(iter_meetings(root))
    els = SentenceDecomposer().decompose(m.specific_query_list)
    labelled = [
        (e, InDocument.OMITTED if i % 2 else InDocument.PRESENT_UNSPECIFIED, 0.1 * i)
        for i, e in enumerate(els)
    ]
    pair = build_pair(m, labelled, label_provenance="nli:roberta-large-mnli / thr=0.5")

    assert pair.source is PairSource.QMSUM_AUTO
    assert pair.decisions == []
    assert pair.has_reasoning_ground_truth is False
    assert pair.dataset_version == "1.1.0"
    assert pair.label_provenance.startswith("nli:")
    assert len(pair.elements) == len(labelled)
    assert pair.elements[0].decision_id == f"{m.meeting_id}_q00"
    # detector scores are embedded for audit
    assert "detector_scores" in pair.notes

    reloaded = pair.__class__.model_validate_json(pair.model_dump_json())
    assert reloaded.source is PairSource.QMSUM_AUTO
