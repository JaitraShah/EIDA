"""
Task 5 step 1: generate the 50 synthetic (discussion, document) pairs.

Design decision that matters more than anything else here: **ground truth is
constructed, not annotated afterwards.** The pipeline decides which reasoning
elements exist and which ones the document is allowed to keep BEFORE either text is
written, then writes both texts to that plan:

    1. sample a decision spec (the reasoning elements)          [LLM, sampled]
    2. assign each element a label: omitted / verbatim / paraphrased   [seeded RNG]
    3. write the discussion containing ALL elements             [LLM, sampled]
    4. write the document containing ONLY the present ones      [LLM, sampled]
    5. leak-check the document against the omitted elements     [deterministic]

That ordering is what makes the human annotation pass (step 2) a *verification* job
rather than a from-scratch labelling job, and it is why the labels are trustworthy
enough to compute agreement on.

Step 5 exists because step 4 is the weak link: a 7B model asked to omit something
will sometimes mention it anyway. Leaked pairs are flagged, not silently kept -- a
benchmark whose "gap" labels are wrong would make every downstream number wrong in
the flattering direction.

Sampling is used deliberately here (unlike extraction, which is temperature=0) --
50 pairs at temperature 0 would be 50 near-identical meetings. Temperature and seed
are recorded per pair in GenerationMeta so any pair can be regenerated exactly.

Checkpointing: every finished pair is written to data/benchmark/pairs/ immediately
and a manifest row is appended. Re-running skips whatever already exists, so this
survives being stopped and resumed across sessions.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from ..extraction.extractor import _as_list, _clean_str, extract_json_object
from ..extraction.llm_client import DEFAULT_MODEL, OllamaClient
from ..extraction.schema import DecisionRecord, DecisionStatus, ElementType
from .dataset import (
    BenchmarkPair,
    ElementLabel,
    GenerationMeta,
    InDocument,
    PairSource,
)
from .score import content_tokens, token_f1
from .textutil import split_sentences
from .topics import Topic, pair_plan

PROMPT_VERSION = "synth-v1"
PAIRS_DIR = Path("data/benchmark/pairs")
MANIFEST = Path("data/benchmark/manifest.json")

GENERATION_TEMPERATURE = 0.8

# How often each element type survives into the document. Shaped to match what Task 1
# actually observed: the outcome is almost always kept, the reasoning around it is
# usually dropped, and dissent is dropped hardest. Owner/approver are the deliberate
# exception -- synthetic enterprise documents do record them, which is the contrast
# with QMSum's structural N/A (Task 1 caveat 1).
LABEL_WEIGHTS: dict[ElementType, dict[InDocument, float]] = {
    ElementType.DECISION:    {InDocument.OMITTED: 0.10, InDocument.VERBATIM: 0.35, InDocument.PARAPHRASED: 0.55},
    ElementType.ALTERNATIVE: {InDocument.OMITTED: 0.70, InDocument.VERBATIM: 0.10, InDocument.PARAPHRASED: 0.20},
    ElementType.RATIONALE:   {InDocument.OMITTED: 0.75, InDocument.VERBATIM: 0.05, InDocument.PARAPHRASED: 0.20},
    ElementType.CONDITION:   {InDocument.OMITTED: 0.70, InDocument.VERBATIM: 0.10, InDocument.PARAPHRASED: 0.20},
    ElementType.DISSENT:     {InDocument.OMITTED: 0.85, InDocument.VERBATIM: 0.05, InDocument.PARAPHRASED: 0.10},
    ElementType.OWNER:       {InDocument.OMITTED: 0.40, InDocument.VERBATIM: 0.45, InDocument.PARAPHRASED: 0.15},
    ElementType.APPROVER:    {InDocument.OMITTED: 0.50, InDocument.VERBATIM: 0.35, InDocument.PARAPHRASED: 0.15},
}

LEAK_THRESHOLD = 0.6


# --------------------------------------------------------------------------- #
# prompts
# --------------------------------------------------------------------------- #

SPEC_SYSTEM = """\
You invent realistic corporate meeting decisions for a research dataset. You return \
JSON only. You write like a real meeting, not like a case study: specific numbers, \
named systems, real tradeoffs, and at least one objection that does not get fully \
resolved.\
"""

SPEC_USER = """\
Invent ONE decision for this meeting.

Topic: {label}
People in the room: {setting}
The decision turns on: {axis}
Variation seed: {variant} -- make this materially different from other decisions on \
the same topic (different specific options, different sticking point, different outcome).

Return JSON:
{{
  "decision": "one sentence: what was decided",
  "topic": "two or three word subject label",
  "status": "decided | provisional | deferred",
  "alternatives": [
    {{"option": "named option", "rejected": true, "reason": "why it lost"}}
  ],
  "rationale": ["a concrete reason the chosen option won"],
  "conditions": ["a caveat, unresolved cost, dependency or open risk"],
  "dissent": ["an objection someone in the room voiced"],
  "owner": "role who will carry it out",
  "approver": "role who signed off, or null"
}}

Requirements:
- 2 to 4 alternatives, at least one rejected with a stated reason.
- 2 to 3 rationale items. 1 to 2 conditions. 1 to 2 dissent items.
- Use specific detail (numbers, system names, dates), not generic phrasing.
- Each item is a single self-contained sentence that makes sense on its own.

Return the JSON object only."""

TRANSCRIPT_SYSTEM = """\
You write realistic meeting transcripts for a research dataset. Real meetings are \
messy: people interrupt, repeat themselves, go on small tangents, and reach \
decisions gradually rather than announcing them. You write the transcript only.\
"""

TRANSCRIPT_USER = """\
Write a meeting transcript, 25 to 40 speaker turns, in which this decision is reached.

People in the room: {setting}
Format every line as `Role: what they said` with no blank lines and no stage directions.

The transcript MUST contain all of the following, spoken naturally by the people who \
would raise them -- not read out as a list:

DECISION REACHED: {decision}
STATUS: {status}
OPTIONS THAT WERE ON THE TABLE:
{alternatives}
REASONS THE CHOSEN OPTION WON:
{rationale}
CAVEATS / OPEN RISKS RAISED:
{conditions}
OBJECTIONS VOICED:
{dissent}
WHO WILL OWN IT: {owner}
WHO SIGNED OFF: {approver}

Rules:
- Open with something other than the decision. Let it emerge.
- The objections must be said by someone who means them, and must be answered \
partially, not perfectly.
- Include one short off-topic exchange (2-3 turns) so the transcript is not \
uniformly dense.
- Do not use headings, bullets, or summaries. Transcript lines only."""

DOCUMENT_SYSTEM = """\
You write the short written record that gets filed after a meeting -- the kind of \
summary that goes into a wiki page or a decision log. These records are always \
shorter than the discussion and routinely leave things out. You write the record only.\
"""

DOCUMENT_USER = """\
Write the filed decision record for this meeting. 90 to 160 words, plain prose or a \
few short lines. No headings beyond a single title line.

INCLUDE exactly these points, and nothing else of substance:
{include}

REWORD these ones -- same meaning, different wording from how the discussion put it:
{paraphrase}

CRITICAL -- the following were discussed but must NOT appear in the record in any \
form. Do not mention them, do not hint at them, do not gesture at them with phrases \
like "after weighing the options" or "some concerns were raised":
{exclude}

Write the record only."""


# --------------------------------------------------------------------------- #
# label assignment
# --------------------------------------------------------------------------- #

def assign_labels(
    elements: list[tuple[ElementType, str]], rng: random.Random
) -> list[InDocument]:
    """Draw an in_document label per element from the Task-1-shaped weights.

    Guarantees at least one omitted and at least one present element: a pair with no
    gap teaches a detector nothing, and a pair that is all gap is not a document.
    """
    labels: list[InDocument] = []
    for etype, _ in elements:
        weights = LABEL_WEIGHTS.get(etype, LABEL_WEIGHTS[ElementType.RATIONALE])
        choices, probs = zip(*weights.items())
        labels.append(rng.choices(choices, weights=probs, k=1)[0])

    if all(l is InDocument.OMITTED for l in labels):
        # force the decision itself (or the first element) to survive
        idx = next((i for i, (t, _) in enumerate(elements) if t is ElementType.DECISION), 0)
        labels[idx] = InDocument.PARAPHRASED
    if all(l is not InDocument.OMITTED for l in labels):
        candidates = [
            i for i, (t, _) in enumerate(elements)
            if t in (ElementType.DISSENT, ElementType.RATIONALE, ElementType.CONDITION)
        ] or [len(labels) - 1]
        labels[rng.choice(candidates)] = InDocument.OMITTED

    return labels


# --------------------------------------------------------------------------- #
# leak checking
# --------------------------------------------------------------------------- #

def find_leaks(document: str, omitted: list[ElementLabel]) -> list[dict]:
    """Report omitted elements whose content nonetheless shows up in the document.

    Sentence-level rather than whole-document: an element's content words scattered
    across a 150-word document is coincidence, the same words concentrated in one
    sentence is a leak.
    """
    sentences = split_sentences(document)
    leaks: list[dict] = []
    for el in omitted:
        if len(content_tokens(el.text)) < 3:
            continue  # too short to judge; the human pass will catch it
        best, best_sent = 0.0, ""
        for sent in sentences:
            s = token_f1(el.text, sent)
            if s > best:
                best, best_sent = s, sent
        if best >= LEAK_THRESHOLD:
            leaks.append(
                {"element_id": el.element_id, "text": el.text,
                 "score": round(best, 2), "document_sentence": best_sent.strip()}
            )
    return leaks


MIN_TURNS = 12
MIN_SPEAKERS = 3


def _looks_like_discussion(text: str) -> bool:
    """A generated transcript must actually be a multi-speaker exchange."""
    from ..extraction.chunker import parse_turns

    turns = [t for t in parse_turns(text) if t.speaker]
    speakers = {t.speaker for t in turns}
    return len(turns) >= MIN_TURNS and len(speakers) >= MIN_SPEAKERS


# --------------------------------------------------------------------------- #
# generation
# --------------------------------------------------------------------------- #

def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- (none)"


def spec_to_record(spec: dict, pair_id: str) -> DecisionRecord:
    status = (_clean_str(spec.get("status")) or "decided").lower()
    if status not in {s.value for s in DecisionStatus}:
        status = "decided"

    alternatives = []
    for alt in _as_list(spec.get("alternatives")):
        if isinstance(alt, str):
            alternatives.append({"option": alt, "rejected": None, "reason": None})
        elif isinstance(alt, dict) and _clean_str(alt.get("option")):
            alternatives.append({
                "option": _clean_str(alt.get("option")),
                "rejected": alt.get("rejected") if isinstance(alt.get("rejected"), bool) else None,
                "reason": _clean_str(alt.get("reason")),
            })

    return DecisionRecord(
        decision_id=f"{pair_id}_d1",
        source_id=pair_id,
        chunk_id="SYNTHETIC_SPEC",
        decision=_clean_str(spec.get("decision")) or "",
        topic=_clean_str(spec.get("topic")),
        status=status,
        alternatives=alternatives,
        rationale=[s for s in (_clean_str(x) for x in _as_list(spec.get("rationale"))) if s],
        conditions=[s for s in (_clean_str(x) for x in _as_list(spec.get("conditions"))) if s],
        dissent=[s for s in (_clean_str(x) for x in _as_list(spec.get("dissent"))) if s],
        owner=_clean_str(spec.get("owner")),
        approver=_clean_str(spec.get("approver")),
    )


class PairGenerator:
    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = GENERATION_TEMPERATURE):
        self.model = model
        self.temperature = temperature

    def _client(self, seed: int) -> OllamaClient:
        return OllamaClient(
            model=self.model,
            allow_sampling=True,
            options={"temperature": self.temperature, "top_p": 0.95, "top_k": 40, "seed": seed},
        )

    def generate(self, pair_id: str, topic: Topic, variant: int, seed: int) -> BenchmarkPair:
        client = self._client(seed)
        rng = random.Random(seed)

        # 1. decision spec
        spec_raw = client.chat_json(
            SPEC_SYSTEM,
            SPEC_USER.format(
                label=topic.label, setting=topic.setting,
                axis=topic.example_axis, variant=variant,
            ),
        )
        spec = extract_json_object(spec_raw.text)
        record = spec_to_record(spec, pair_id)
        if not record.decision:
            raise ValueError("spec produced no decision text")

        elements = record.reasoning_elements()
        if len(elements) < 4:
            raise ValueError(f"spec too thin: only {len(elements)} reasoning elements")

        # 2. labels, decided before either text exists
        labels = assign_labels(elements, rng)
        element_labels = [
            ElementLabel(
                element_id=f"{pair_id}_e{i:02d}",
                element_type=etype,
                text=text,
                in_document=label,
                decision_id=record.decision_id,
            )
            for i, ((etype, text), label) in enumerate(zip(elements, labels), start=1)
        ]

        # 3. transcript containing everything
        transcript_prompt = TRANSCRIPT_USER.format(
                setting=topic.setting,
                decision=record.decision,
                status=record.status.value,
                alternatives=_bullets(
                    [f"{a.option}" + (f" (rejected: {a.reason})" if a.reason else "")
                     for a in record.alternatives]
                ),
                rationale=_bullets(record.rationale),
                conditions=_bullets(record.conditions),
                dissent=_bullets(record.dissent),
                owner=record.owner or "not assigned",
                approver=record.approver or "nobody explicitly",
        )
        transcript = self._plain_call(client, TRANSCRIPT_SYSTEM, transcript_prompt)

        # 3b. reject a transcript that is not actually a multi-speaker discussion.
        # A 7B model asked for 25-40 turns sometimes returns a summary paragraph or a
        # two-person exchange; those pairs are worthless and cheaper to catch here
        # than to hand to an annotator.
        if not _looks_like_discussion(transcript):
            transcript = self._plain_call(
                client,
                TRANSCRIPT_SYSTEM,
                transcript_prompt
                + "\n\nYour previous attempt was not a transcript. Output ONLY lines of "
                  "the form `Role: what they said`, at least 25 of them, with at least "
                  "three different roles speaking. No prose, no headings, no summary.",
            )
            if not _looks_like_discussion(transcript):
                raise ValueError("model would not produce a multi-speaker transcript")

        # 4. document containing only the survivors
        include = [e.text for e in element_labels if e.in_document is InDocument.VERBATIM]
        paraphrase = [e.text for e in element_labels if e.in_document is InDocument.PARAPHRASED]
        exclude = [e.text for e in element_labels if e.in_document is InDocument.OMITTED]
        document = self._plain_call(
            client,
            DOCUMENT_SYSTEM,
            DOCUMENT_USER.format(
                include=_bullets(include) if include else "- (nothing to state verbatim)",
                paraphrase=_bullets(paraphrase),
                exclude=_bullets(exclude),
            ),
        )

        # 5. leak check
        leaks = find_leaks(document, [e for e in element_labels if e.in_document is InDocument.OMITTED])

        notes = ""
        if leaks:
            notes = (
                "AUTOMATIC LEAK FLAG -- the document appears to mention "
                f"{len(leaks)} element(s) labelled omitted. Human pass must re-label or "
                "regenerate this pair before it is used.\n"
                + json.dumps(leaks, indent=2, ensure_ascii=False)
            )

        return BenchmarkPair(
            pair_id=pair_id,
            source=PairSource.SYNTHETIC,
            topic=topic.key,
            title=record.topic or topic.label,
            transcript=transcript.strip(),
            document=document.strip(),
            decisions=[record],
            elements=element_labels,
            generation=GenerationMeta(
                model=self.model, temperature=self.temperature, seed=seed,
                prompt_version=PROMPT_VERSION, sampled=True,
            ),
            label_provenance="constructed",
            notes=notes,
        )

    @staticmethod
    def _plain_call(client: OllamaClient, system: str, user: str) -> str:
        """Prose call -- Ollama's JSON mode is wrong here because we want text.
        Unwraps the occasional model that answers with {"text": ...} anyway."""
        import requests

        r = requests.post(
            f"{client.host}/api/chat",
            json={
                "model": client.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": client.options,
            },
            timeout=client.timeout,
        )
        r.raise_for_status()
        text = r.json().get("message", {}).get("content", "").strip()
        if text.startswith("{"):
            try:
                obj = json.loads(text)
                for key in ("transcript", "document", "text", "content"):
                    if isinstance(obj.get(key), str):
                        return obj[key]
            except json.JSONDecodeError:
                pass
        return text


# --------------------------------------------------------------------------- #
# checkpointed batch run
# --------------------------------------------------------------------------- #

def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"prompt_version": PROMPT_VERSION, "pairs": {}}


def save_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def generate_all(
    model: str = DEFAULT_MODEL,
    limit: int | None = None,
    only: str | None = None,
    force: bool = False,
    base_seed: int = 1000,
    verbose: bool = True,
) -> dict:
    """Generate the plan, skipping pairs already on disk. Safe to stop and resume."""
    generator = PairGenerator(model=model)
    manifest = load_manifest()
    plan = pair_plan()
    if only:
        plan = [p for p in plan if p[0] == only]

    done = 0
    for pair_id, topic, variant in plan:
        if limit is not None and done >= limit:
            break
        path = PAIRS_DIR / f"{pair_id}.json"
        if path.exists() and not force:
            if verbose:
                print(f"{pair_id}: exists, skipping")
            continue

        seed = base_seed + int(pair_id.split("_")[1])
        start = time.time()
        try:
            pair = generator.generate(pair_id, topic, variant, seed)
        except Exception as e:  # generation is best-effort; record and move on
            print(f"{pair_id}: FAILED -- {type(e).__name__}: {e}")
            manifest["pairs"][pair_id] = {"status": "failed", "error": f"{type(e).__name__}: {e}"}
            save_manifest(manifest)
            continue

        pair.save(PAIRS_DIR)
        status = "flagged_leak" if pair.notes else "ok"
        manifest["pairs"][pair_id] = {
            "status": status,
            "topic": topic.key,
            "elements": len(pair.elements),
            "gaps": pair.gap_count,
            "seed": seed,
            "seconds": round(time.time() - start, 1),
        }
        save_manifest(manifest)
        done += 1
        if verbose:
            print(
                f"{pair_id}: {status}  {len(pair.elements)} elements "
                f"({pair.gap_count} gaps)  {time.time() - start:.0f}s"
            )

    return manifest
