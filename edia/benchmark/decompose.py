"""
Turn a QMSum specific-query answer (a short human-written paragraph about one
sub-topic of a meeting) into atomic reasoning elements for the benchmark.

Two implementations behind one interface:

  * `SentenceDecomposer` -- deterministic, offline, the default. Splits on sentence
    boundaries and classifies each sentence into one of the frozen `ElementType`
    slots by cue words. Cheap and perfectly reproducible, which matters because the
    output is *ground-truth material*: 232 meetings x ~6 queries x ~4 sentences is
    ~5-9k elements, and an LLM pass over that is neither cheap nor regenerable.

  * `LlmDecomposer` -- an Ollama pass that returns a JSON list of atomic claims
    with a type each. Better segmentation of compound clauses ("rejected because of
    cost AND localisation burden" -> two units), at the cost of ~1.5k non-
    deterministic model calls. Kept as a runnable ablation, not the default.

Known limitation of the sentence path, stated so it travels with the data:
sentence granularity under-segments compound clauses and occasionally over-
segments a run-on. Both are visible to the human spot-check and fixable later by
switching decomposer with **no schema change** -- an element is an element.

The `element_type` here only feeds the by-element-type breakdown in the gap-eval
report; it never affects a gap label. Treat that breakdown as indicative.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..extraction.schema import ElementType
from .textutil import split_sentences

# --------------------------------------------------------------------------- #
# cue-word type classification
# --------------------------------------------------------------------------- #

# Order matters: the first bucket whose pattern hits wins. DISSENT and ALTERNATIVE
# are checked before RATIONALE/CONDITION because "rejected because X" is more
# usefully an ALTERNATIVE than a RATIONALE.
_TYPE_CUES: list[tuple[ElementType, re.Pattern]] = [
    (ElementType.APPROVER, re.compile(
        r"\b(signed off|sign-off|approved by|gave (?:the |their )?approval|"
        r"authorised by|authorized by)\b", re.I)),
    (ElementType.OWNER, re.compile(
        r"\b(will own|takes ownership|responsible for (?:delivering|carrying)|"
        r"assigned to|will lead|action(?:ed)? (?:on|to)|owner is)\b", re.I)),
    (ElementType.DISSENT, re.compile(
        r"\b(disagreed|objected|pushed back|was against|opposed|"
        r"raised concerns?|was sceptical|was skeptical|was not convinced|"
        r"argued against|preferred (?:a|an|the|to)\b|would rather)\b", re.I)),
    (ElementType.ALTERNATIVE, re.compile(
        r"\b(instead of|rather than|as an alternative|other option|another option|"
        r"was rejected|were rejected|was turned down|was ruled out|were ruled out|"
        r"was considered and|was dismissed|option[s]? (?:on the table|considered)|"
        r"considered (?:using|adopting|a|an|the)\b)\b", re.I)),
    (ElementType.CONDITION, re.compile(
        r"\b(provided that|as long as|on condition|depends on|dependent on|"
        r"unresolved|open (?:risk|question|issue)|still to be|remains? to be|"
        r"caveat|subject to|temporar(?:y|ily)|for now|pending|"
        r"was not (?:established|known|decided)|would increase the cost|"
        r"cost (?:was|is) (?:unknown|unclear))\b", re.I)),
    (ElementType.RATIONALE, re.compile(
        r"\b(because|since|so that|in order to|the reason|this (?:is|was) why|"
        r"on the grounds that|justified by|driven by|motivated by|"
        r"the rationale|which is why)\b", re.I)),
    (ElementType.DECISION, re.compile(
        r"\b(decided|agreed to|chose to|chose (?:a|an|the)\b|was chosen|were chosen|"
        r"was adopted|were adopted|settled on|will (?:go|proceed) with|"
        r"resolved to|concluded that|the decision (?:was|is)|opted (?:for|to))\b", re.I)),
]


def classify_element_type(text: str, *, is_first_in_answer: bool = False) -> ElementType:
    """Best-effort mapping of one sentence to a frozen ElementType slot.

    `is_first_in_answer` biases toward DECISION: the opening sentence of a QMSum
    specific-query answer is almost always the outcome statement.
    """
    for etype, rx in _TYPE_CUES:
        if rx.search(text):
            return etype
    if is_first_in_answer:
        return ElementType.DECISION
    return ElementType.RATIONALE  # the schema's own fallback (see generate.assign_labels)


# --------------------------------------------------------------------------- #
# decomposers
# --------------------------------------------------------------------------- #

@dataclass
class RawElement:
    """One atomic reasoning unit pulled from a specific-query answer, before an
    in_document label is attached."""

    text: str
    element_type: ElementType
    query_index: int          # which specific_query_list entry it came from
    query: str                # the sub-topic question, kept for auditing


MIN_ELEMENT_CHARS = 25
MIN_ELEMENT_CONTENT_WORDS = 4
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _is_substantive(sentence: str) -> bool:
    """Drop fragments too short to carry a reasoning claim (headers, 'Yes.',
    'The group discussed this.')."""
    if len(sentence) < MIN_ELEMENT_CHARS:
        return False
    if len(_WORD_RE.findall(sentence)) < MIN_ELEMENT_CONTENT_WORDS:
        return False
    return True


class SentenceDecomposer:
    """Deterministic: one element per substantive sentence of each answer."""

    name = "sentence"

    def decompose(self, specific_query_list: list[dict]) -> list[RawElement]:
        out: list[RawElement] = []
        for qi, entry in enumerate(specific_query_list or []):
            answer = (entry or {}).get("answer") or ""
            query = (entry or {}).get("query") or ""
            sentences = split_sentences(answer)
            for si, sent in enumerate(sentences):
                if not _is_substantive(sent):
                    continue
                out.append(
                    RawElement(
                        text=sent,
                        element_type=classify_element_type(
                            sent, is_first_in_answer=(si == 0)
                        ),
                        query_index=qi,
                        query=query,
                    )
                )
        return out


_LLM_SYSTEM = (
    "You split a short meeting-notes paragraph into atomic factual claims. You "
    "return JSON only. Each claim is one self-contained sentence stating exactly "
    "one thing: one decision, one option, one reason, one caveat, or one objection. "
    "You never add information that is not in the paragraph."
)

_LLM_USER = """\
Paragraph (about the sub-topic: {query}):
---
{answer}
---

Return JSON: {{"claims": [{{"text": "...", "type": "decision|alternative|rationale|condition|dissent|owner|approver"}}]}}
Split compound sentences ("rejected due to cost and time" -> two claims). Drop
filler that states nothing ("The group discussed this at length"). Return the JSON only."""


class LlmDecomposer:
    """Ollama-backed: better clause splitting, non-deterministic, ablation only.

    Falls back to `SentenceDecomposer` for any answer the model mangles, so a bad
    call degrades rather than dropping a whole meeting's sub-topic.
    """

    name = "llm"

    def __init__(self, client=None, model: str | None = None):
        from ..extraction.llm_client import DEFAULT_MODEL, OllamaClient

        self.client = client or OllamaClient(model=model or DEFAULT_MODEL)
        self._fallback = SentenceDecomposer()

    def decompose(self, specific_query_list: list[dict]) -> list[RawElement]:
        from ..extraction.extractor import _as_list, _clean_str, extract_json_object

        out: list[RawElement] = []
        for qi, entry in enumerate(specific_query_list or []):
            answer = (entry or {}).get("answer") or ""
            query = (entry or {}).get("query") or ""
            if not answer.strip():
                continue
            try:
                resp = self.client.chat_json(
                    _LLM_SYSTEM, _LLM_USER.format(query=query, answer=answer)
                )
                claims = _as_list(extract_json_object(resp.text).get("claims"))
                parsed: list[RawElement] = []
                for c in claims:
                    if isinstance(c, str):
                        text, tval = c, None
                    elif isinstance(c, dict):
                        text, tval = _clean_str(c.get("text")), _clean_str(c.get("type"))
                    else:
                        continue
                    if not text or not _is_substantive(text):
                        continue
                    try:
                        etype = ElementType(tval) if tval else classify_element_type(text)
                    except ValueError:
                        etype = classify_element_type(text)
                    parsed.append(RawElement(text, etype, qi, query))
                if parsed:
                    out.extend(parsed)
                    continue
            except Exception:  # noqa: BLE001 -- degrade to the deterministic path
                pass
            for e in self._fallback.decompose([entry]):
                e.query_index = qi
                out.append(e)
        return out


def get_decomposer(name: str, **kw):
    if name == "sentence":
        return SentenceDecomposer()
    if name == "llm":
        return LlmDecomposer(**kw)
    raise ValueError(f"unknown decomposer {name!r} (want 'sentence' or 'llm')")
