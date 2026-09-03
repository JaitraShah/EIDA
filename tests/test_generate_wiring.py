"""PairGenerator wiring test -- checks the call sequence and the assembled pair
without touching a model. The real-model check is `python scripts/generate_synthetic.py
--only SYN_011 --force`."""
import json

import pytest

from edia.benchmark import generate as gen
from edia.benchmark.dataset import InDocument, PairSource
from edia.benchmark.topics import TOPICS
from edia.extraction.llm_client import LLMResponse

SPEC = {
    "decision": "The team will migrate the billing service to Aurora Postgres in Q3.",
    "topic": "database migration",
    "status": "decided",
    "alternatives": [
        {"option": "stay on self-managed Postgres", "rejected": True, "reason": "on-call burden"},
        {"option": "Aurora Postgres", "rejected": False, "reason": None},
    ],
    "rationale": ["Aurora removes the failover runbook the SRE team maintains by hand."],
    "conditions": ["The 40k euro reserved-instance commitment is not yet approved by finance."],
    "dissent": ["The SRE lead argued the migration window collides with the audit freeze."],
    "owner": "platform engineering lead",
    "approver": "CTO",
}

ROLES = ["Platform Lead", "SRE", "Finance Partner", "CTO"]
TRANSCRIPT = "\n".join(
    f"{ROLES[i % len(ROLES)]}: line {i} about the migration." for i in range(1, 17)
)
DOCUMENT = "Billing service moves to Aurora Postgres in Q3. Owner: platform engineering lead."


@pytest.fixture
def fake_model(monkeypatch):
    calls = {"json": 0, "plain": []}

    class FakeClient:
        model = "fake"
        options = {"temperature": 0.8, "seed": 1}
        host = "http://fake"
        timeout = 1

        def chat_json(self, system, user):
            calls["json"] += 1
            return LLMResponse(text=json.dumps(SPEC), model="fake", latency_s=0.0)

    monkeypatch.setattr(gen.PairGenerator, "_client", lambda self, seed, temperature=None: FakeClient())

    def fake_plain(client, system, user):
        calls["plain"].append(user)
        return TRANSCRIPT if "transcript" in user.lower() else DOCUMENT

    monkeypatch.setattr(gen.PairGenerator, "_plain_call", staticmethod(fake_plain))
    return calls


def test_generate_produces_a_complete_pair(fake_model):
    pair = gen.PairGenerator(model="fake").generate("SYN_011", TOPICS[0], 1, seed=1001)

    assert pair.pair_id == "SYN_011"
    assert pair.source is PairSource.SYNTHETIC
    assert pair.transcript == TRANSCRIPT
    assert pair.document == DOCUMENT
    assert len(pair.decisions) == 1
    assert pair.decisions[0].owner == "platform engineering lead"
    # 1 decision + 2 alternatives + 1 rationale + 1 condition + 1 dissent + owner + approver
    assert len(pair.elements) == 8
    assert fake_model["json"] == 1
    assert len(fake_model["plain"]) == 2


def test_generation_metadata_is_recorded_for_reproducibility(fake_model):
    pair = gen.PairGenerator(model="fake", temperature=0.8).generate(
        "SYN_011", TOPICS[0], 1, seed=1001
    )
    assert pair.generation.sampled is True
    assert pair.generation.seed == 1001
    assert pair.generation.temperature == 0.8
    assert pair.generation.prompt_version == gen.PROMPT_VERSION


def test_document_prompt_lists_omitted_elements_as_forbidden(fake_model):
    gen.PairGenerator(model="fake").generate("SYN_011", TOPICS[0], 1, seed=1001)
    doc_prompt = fake_model["plain"][1]
    assert "must NOT appear" in doc_prompt


def test_leak_in_document_auto_corrects_omitted_to_paraphrased(monkeypatch):
    """The document here repeats the condition verbatim while it was planned as
    'omitted'. find_leaks locates it in one sentence, so the label is corrected to
    'paraphrased' (present, reworded) rather than the pair being flagged."""
    condition = SPEC["conditions"][0]

    class FakeClient:
        model = "fake"
        options = {}
        host = "http://fake"
        timeout = 1

        def chat_json(self, system, user):
            return LLMResponse(text=json.dumps(SPEC), model="fake", latency_s=0.0)

    monkeypatch.setattr(gen.PairGenerator, "_client", lambda self, seed, temperature=None: FakeClient())
    monkeypatch.setattr(
        gen.PairGenerator, "_plain_call",
        staticmethod(lambda c, s, u: TRANSCRIPT if "transcript" in u.lower() else condition),
    )
    # force every element to be omitted except the decision
    monkeypatch.setattr(
        gen, "assign_labels",
        lambda elements, rng: [
            InDocument.VERBATIM if i == 0 else InDocument.OMITTED
            for i in range(len(elements))
        ],
    )

    pair = gen.PairGenerator(model="fake").generate("SYN_011", TOPICS[0], 1, seed=1001)
    assert pair.notes.startswith("LEAK AUTO-CORRECTED")
    assert "AUTOMATIC LEAK FLAG" not in pair.notes
    cond_el = next(e for e in pair.elements if e.text == condition)
    assert cond_el.in_document is InDocument.PARAPHRASED, "leaked omitted -> paraphrased"


def test_thin_spec_is_rejected(monkeypatch):
    class FakeClient:
        model = "fake"
        options = {}
        host = "http://fake"
        timeout = 1

        def chat_json(self, system, user):
            return LLMResponse(text=json.dumps({"decision": "We decided."}), model="fake", latency_s=0.0)

    monkeypatch.setattr(gen.PairGenerator, "_client", lambda self, seed, temperature=None: FakeClient())
    with pytest.raises(ValueError, match="too thin"):
        gen.PairGenerator(model="fake").generate("SYN_011", TOPICS[0], 1, seed=1001)


def test_generate_all_hands_out_unique_seeds(monkeypatch):
    """The old `int(pair_id.split('_')[1])` seed derivation collided past 9 variants.
    Every planned pair must now get its own seed from pair_plan()."""
    from edia.benchmark.topics import pair_plan

    plan = pair_plan()
    assert len({p[3] for p in plan}) == len(plan)
    # generate() must accept the new id shape
    assert plan[0][0].startswith("SYN_0000_0")
    assert plan[-1][3] != plan[0][3]


def test_temperature_jitter_is_per_pair_and_recorded(fake_model):
    g = gen.PairGenerator(model="fake", temp_jitter=(0.7, 0.95))
    p1 = g.generate("SYN_0000_001", TOPICS[0], 1, seed=1001)
    p2 = g.generate("SYN_0000_002", TOPICS[0], 2, seed=1002)
    assert 0.7 <= p1.generation.temperature <= 0.95
    assert p1.generation.temperature != p2.generation.temperature  # different seeds


def test_non_transcript_output_is_retried_then_rejected(monkeypatch):
    """A model that answers with a summary paragraph instead of a transcript must
    not produce a pair -- those are worthless to an annotator."""
    class FakeClient:
        model = "fake"
        options = {}
        host = "http://fake"
        timeout = 1

        def chat_json(self, system, user):
            return LLMResponse(text=json.dumps(SPEC), model="fake", latency_s=0.0)

    attempts = []
    monkeypatch.setattr(gen.PairGenerator, "_client", lambda self, seed, temperature=None: FakeClient())
    monkeypatch.setattr(
        gen.PairGenerator, "_plain_call",
        staticmethod(lambda c, s, u: (attempts.append(u), "The team agreed to migrate.")[1]),
    )
    with pytest.raises(ValueError, match="multi-speaker transcript"):
        gen.PairGenerator(model="fake").generate("SYN_011", TOPICS[0], 1, seed=1001)
    assert len(attempts) == 2, "should retry once with a stricter instruction"
