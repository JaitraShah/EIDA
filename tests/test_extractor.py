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
        self.text_calls = []

    def chat_json(self, system, user):
        self.calls.append((system, user))
        payload = self.responses.pop(0) if self.responses else '{"decisions": []}'
        if isinstance(payload, Exception):
            raise payload
        return LLMResponse(text=payload, model=self.model, latency_s=0.0)

    def chat_text(self, system, user):
        self.text_calls.append((system, user))
        return LLMResponse(text="- Decision: kryptonite was chosen.",
                           model=self.model, latency_s=0.0)


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


# --- non-decision filtering -------------------------------------------------

@pytest.mark.parametrize("text", [
    "No decision was made about the design of the remote control",
    "No clear decision was made about the design aesthetic of the remote control.",
    "There was no agreement on the material.",
    "The team did not reach a decision on pricing.",
    "no consensus was reached regarding the chip tier",
])
def test_non_decision_statements_detected(text):
    from edia.extraction.extractor import is_non_decision
    assert is_non_decision(text)


@pytest.mark.parametrize("text", [
    "The team decided not to integrate an LCD display.",
    "No LCD display will be included in the final design.",
    "Kryptonite was chosen as the energy source.",
    "None of the casing shapes were rejected outright; all three remain.",
])
def test_real_decisions_survive_the_filter(text):
    """A negation inside a genuine decision must not trip the filter."""
    from edia.extraction.extractor import is_non_decision
    assert not is_non_decision(text)


def test_empty_no_decision_record_is_dropped():
    """Observed on QSUM_003: the model answers 'no decision was made' instead of
    returning an empty list. With nothing else attached, that record is noise."""
    payload = json.dumps({"decisions": [
        {"decision": "No decision was made about the design of the remote control"},
        {"decision": "Lightweight plastic was temporarily chosen."},
    ]})
    ex = DecisionExtractor(client=FakeClient([payload]), verbose=False)
    recs = ex.extract_from_chunk(make_chunk())
    assert len(recs) == 1
    assert recs[0].decision.startswith("Lightweight plastic")


def test_no_decision_record_with_real_reasoning_is_kept():
    """The filter must stay narrow. These records often carry genuine reasoning --
    one QSUM_001 record pairs a useless decision line with 14 real elements -- and
    dropping the whole record throws away correct extractions."""
    payload = json.dumps({"decisions": [{
        "decision": "No clear decision was made about the design aesthetic.",
        "alternatives": ["fashionable and stylish", "plastic", "metal"],
        "rationale": ["The team debated look and feel at length."],
    }]})
    ex = DecisionExtractor(client=FakeClient([payload]), verbose=False)
    recs = ex.extract_from_chunk(make_chunk())
    assert len(recs) == 1, "a record carrying real reasoning must survive"
    assert [a.option for a in recs[0].alternatives] == [
        "fashionable and stylish", "plastic", "metal"
    ]


def test_is_empty_non_decision_accepts_dicts_and_records():
    """The extractor filters dicts; the cache-replay path filters DecisionRecords.
    One rule has to cover both or a cached run and a fresh run disagree."""
    from edia.extraction.extractor import is_empty_non_decision
    bare = {"decision": "No decision was made."}
    assert is_empty_non_decision(bare)
    assert is_empty_non_decision(coerce_record(bare, **BASE))
    rich = {"decision": "No decision was made.", "rationale": ["a real reason"]}
    assert not is_empty_non_decision(rich)
    assert not is_empty_non_decision(coerce_record(rich, **BASE))


# --- Phase 3.1 CoT ablation ------------------------------------------------

def test_cot_off_by_default_makes_one_call():
    fake = FakeClient([GOOD])
    ex = DecisionExtractor(client=fake, verbose=False)
    ex.extract_from_chunk(make_chunk())
    assert fake.text_calls == [], "baseline must not make a reasoning call"


def test_cot_makes_a_separate_unconstrained_reasoning_call():
    """The reasoning pass MUST go through chat_text, not chat_json.

    chat_json sends Ollama format="json", which grammar-constrains decoding to a
    JSON object -- under it the model cannot emit reasoning tokens at all, so a
    'think step by step' instruction on the extraction prompt is a silent no-op and
    the whole ablation would measure prompt wording rather than chain-of-thought.
    """
    fake = FakeClient([GOOD])
    ex = DecisionExtractor(client=fake, verbose=False, cot=True)
    ex.extract_from_chunk(make_chunk())

    assert len(fake.text_calls) == 1, "CoT must make exactly one reasoning call"
    assert len(fake.calls) == 1, "…and still exactly one extraction call"

    # the notes must actually reach the extraction prompt, or the pass is wasted
    _, extraction_user = fake.calls[0]
    assert "kryptonite was chosen" in extraction_user


def test_json_mode_is_off_for_text_calls_and_on_for_json_calls():
    """Guards the payload flag itself, so re-adding format='json' to the text path
    fails here rather than silently voiding the ablation."""
    import inspect

    from edia.extraction.llm_client import OllamaClient

    src = inspect.getsource(OllamaClient._chat)
    assert 'payload["format"] = "json"' in src
    assert "if json_mode:" in src
