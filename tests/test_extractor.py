"""Extractor tests that run offline against a fake LLM client.

These cover the parts that actually break in practice: malformed model output,
string-where-a-list-was-specified, invented fields, and the no-merge constraint.
The real-model run against QMSum is a separate script (scripts/run_qmsum_eval.py),
not a unit test -- it needs a 4GB model and takes minutes.
"""
import json

import pytest

from edia.extraction.chunker import Chunk, chunk_text
from edia.extraction.extractor import (
    DecisionExtractor,
    coerce_record,
    extract_json_object,
)
from edia.extraction.llm_client import DETERMINISTIC_OPTIONS, LLMResponse, OllamaClient
from edia.extraction.schema import DecisionStatus


class FakeClient:
    """Stands in for OllamaClient. Returns queued responses in order."""

    def __init__(self, responses, model="fake"):
        self.responses = list(responses)
        self.model = model
        self.calls = []

    def chat_json(self, system, user):
        self.calls.append((system, user))
        payload = self.responses.pop(0) if self.responses else '{"decisions": []}'
        if isinstance(payload, Exception):
            raise payload
        return LLMResponse(text=payload, model=self.model, latency_s=0.0)


def make_chunk(text="PM: We will use kryptonite.", cid="M7_c000"):
    return Chunk(
        chunk_id=cid, source_id="M7", index=0, text=text,
        turn_start=0, turn_end=0, speakers=["PM"], est_tokens=10,
    )


# --- determinism guard -----------------------------------------------------

def test_temperature_zero_enforced():
    assert DETERMINISTIC_OPTIONS["temperature"] == 0.0
    with pytest.raises(ValueError, match="temperature must be 0"):
        OllamaClient(options={"temperature": 0.7})


def test_client_options_are_copied_not_shared():
    c = OllamaClient(options={"num_ctx": 4096})
    assert c.options["num_ctx"] == 4096
    assert DETERMINISTIC_OPTIONS["num_ctx"] == 8192


# --- JSON extraction -------------------------------------------------------

def test_extract_json_clean():
    assert extract_json_object('{"decisions": []}') == {"decisions": []}


def test_extract_json_with_prose_wrapper():
    text = 'Here is the JSON:\n{"decisions": [{"decision": "x"}]}\nHope that helps!'
    assert extract_json_object(text)["decisions"][0]["decision"] == "x"


def test_extract_json_no_object_raises():
    with pytest.raises(ValueError):
        extract_json_object("I could not find any decisions.")


# --- coercion --------------------------------------------------------------

BASE = dict(decision_id="d1", source_id="M7", chunk_id="M7_c000")


def test_coerce_string_where_list_expected():
    rec = coerce_record(
        {"decision": "Kryptonite chosen", "rationale": "chip dominates cost"}, **BASE
    )
    assert rec.rationale == ["chip dominates cost"]


def test_coerce_string_alternatives():
    rec = coerce_record({"decision": "d", "alternatives": ["battery", "solar"]}, **BASE)
    assert [a.option for a in rec.alternatives] == ["battery", "solar"]
    assert all(a.rejected is None for a in rec.alternatives)


def test_coerce_drops_null_placeholder_strings():
    rec = coerce_record(
        {"decision": "d", "owner": "null", "approver": "N/A",
         "conditions": ["none", "real condition"]},
        **BASE,
    )
    assert rec.owner is None and rec.approver is None
    assert rec.conditions == ["real condition"] or "none" not in [c.lower() for c in rec.conditions]


def test_coerce_ignores_invented_top_level_fields():
    """A model that adds fields must not be able to widen the frozen schema."""
    rec = coerce_record(
        {"decision": "d", "business_impact": "high", "sentiment": "positive"}, **BASE
    )
    assert not hasattr(rec, "business_impact")


def test_coerce_bad_status_becomes_unclear():
    rec = coerce_record({"decision": "d", "status": "kind of agreed"}, **BASE)
    assert rec.status is DecisionStatus.UNCLEAR


def test_coerce_provisional_status_preserved():
    rec = coerce_record({"decision": "d", "status": "provisional"}, **BASE)
    assert rec.status is DecisionStatus.PROVISIONAL


def test_coerce_confidence_clamped():
    assert coerce_record({"decision": "d", "extraction_confidence": 9}, **BASE).extraction_confidence == 1.0
    assert coerce_record({"decision": "d", "extraction_confidence": "high"}, **BASE).extraction_confidence is None


def test_coerce_evidence_supports_normalised():
    rec = coerce_record(
        {"decision": "d", "evidence": [{"quote": "q", "supports": "vibes"}]}, **BASE
    )
    assert rec.evidence[0].supports.value == "decision"


def test_coerce_bare_string_evidence():
    rec = coerce_record({"decision": "d", "evidence": ["we will use kryptonite"]}, **BASE)
    assert rec.evidence[0].quote == "we will use kryptonite"


# --- extraction flow -------------------------------------------------------

GOOD = json.dumps({
    "decisions": [{
        "decision": "Kryptonite chosen as the energy source.",
        "topic": "energy source",
        "status": "decided",
        "alternatives": [{"option": "battery", "rejected": True, "reason": "not chosen"}],
        "rationale": ["chip dominates the cost"],
        "conditions": ["no actual cost found"],
        "dissent": ["ID preferred battery"],
        "owner": None, "approver": None,
        "evidence": [{"quote": "We will use kryptonite.", "speaker": "PM", "supports": "decision"}],
        "extraction_confidence": 0.9,
    }]
})


def test_extract_from_chunk_happy_path():
    ex = DecisionExtractor(client=FakeClient([GOOD]), verbose=False)
    recs = ex.extract_from_chunk(make_chunk())
    assert len(recs) == 1
    r = recs[0]
    assert r.decision_id == "M7_c000_d1"
    assert r.chunk_id == "M7_c000"
    assert r.dissent == ["ID preferred battery"]


def test_empty_decisions_is_valid():
    ex = DecisionExtractor(client=FakeClient(['{"decisions": []}']), verbose=False)
    assert ex.extract_from_chunk(make_chunk()) == []


def test_bare_decision_object_accepted():
    ex = DecisionExtractor(client=FakeClient(['{"decision": "Kryptonite chosen."}']), verbose=False)
    recs = ex.extract_from_chunk(make_chunk())
    assert len(recs) == 1


def test_decision_without_text_is_dropped():
    payload = '{"decisions": [{"decision": "", "rationale": ["invented"]}]}'
    ex = DecisionExtractor(client=FakeClient([payload]), verbose=False)
    assert ex.extract_from_chunk(make_chunk()) == []


def test_repair_round_on_unparseable_output():
    fake = FakeClient(["sorry, I cannot do that", GOOD])
    ex = DecisionExtractor(client=fake, verbose=False)
    recs = ex.extract_from_chunk(make_chunk())
    assert len(recs) == 1
    assert len(fake.calls) == 2, "should have made a repair call"


def test_failed_chunk_is_recorded_not_raised():
    fake = FakeClient(["nonsense", "still nonsense", GOOD])
    ex = DecisionExtractor(client=fake, verbose=False)
    chunks = [make_chunk(cid="M7_c000"), make_chunk(cid="M7_c001")]
    result = ex.extract_chunks(chunks, "M7")
    assert result.chunks_failed == ["M7_c000"]
    assert result.chunks_processed == 1
    assert len(result.records) == 1


def test_no_cross_chunk_merging():
    """Same decision in two chunks must stay as two records with distinct chunk_ids."""
    fake = FakeClient([GOOD, GOOD])
    ex = DecisionExtractor(client=fake, verbose=False)
    chunks = [make_chunk(cid="M7_c000"), make_chunk(cid="M7_c001")]
    result = ex.extract_chunks(chunks, "M7")
    assert len(result.records) == 2
    assert {r.chunk_id for r in result.records} == {"M7_c000", "M7_c001"}
    assert result.merged_across_chunks is False


def test_extract_text_end_to_end_offline():
    transcript = (
        "Project Manager: What power source?\n"
        "Industrial Designer: Battery is cheap.\n"
        "Project Manager: Let's go kryptonite.\n"
    )
    fake = FakeClient([GOOD])
    ex = DecisionExtractor(client=fake, verbose=False)
    result = ex.extract_text(transcript, "M7", max_tokens=500)
    assert result.source_id == "M7"
    assert result.model_name == "fake"
    assert len(result.records) == 1


def test_result_serialises_to_json():
    ex = DecisionExtractor(client=FakeClient([GOOD]), verbose=False)
    result = ex.extract_chunks([make_chunk()], "M7")
    blob = json.dumps(result.model_dump(mode="json"))
    assert "kryptonite" in blob.lower()
