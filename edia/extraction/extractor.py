"""
Chunk -> DecisionRecord extraction.

Pipeline: ingest -> chunk -> one LLM call per chunk -> parse -> validate against the
frozen schema -> flat ExtractionResult.

Two constraints from the Task 4 spec are enforced structurally, not by convention:

  * temperature=0 -- OllamaClient refuses to construct otherwise.
  * no cross-chunk merging -- records keep their originating chunk_id and
    ExtractionResult.merged_across_chunks stays False. If the same decision is
    discussed in two overlapping chunks you get two records. That is correct for
    now; dedup is a later, separately-evaluated step.

Failures are recorded, not raised: one bad chunk out of forty should not lose the
other thirty-nine. Failed chunk ids land in ExtractionResult.chunks_failed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Iterable

from pydantic import ValidationError

from .chunker import Chunk, chunk_text
from .llm_client import DEFAULT_MODEL, OllamaClient, OllamaCallFailed, OllamaUnavailable
from .prompts import (
    COT_SYSTEM_PROMPT,
    REPAIR_PROMPT,
    SYSTEM_PROMPT,
    build_cot_prompt,
    build_user_prompt,
)
from .schema import (
    DecisionRecord,
    DecisionStatus,
    ExtractionResult,
    SCHEMA_VERSION,
)

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)
_VALID_STATUSES = {s.value for s in DecisionStatus}

# The prompt asks for an empty list when a chunk settles nothing. Small models
# answer the question instead: they emit a record whose decision text *is* the
# statement that no decision was made ("No clear decision was made about the design
# aesthetic"). Observed on QSUM_003 c003/c004 -- and those were the two chunks that
# actually contained the meeting's real decisions, so this is not a harmless quirk:
# it inflates record counts, pollutes the unmatched-element rate, and disguises a
# miss as an extraction.
#
# The filter is narrow on purpose. These records frequently carry *genuine*
# reasoning alongside the useless decision line -- one QSUM_001 record pairs
# "No decision was made about the casing" with 14 real alternatives, rationale
# and conditions. Dropping the whole record to remove one bad line destroys
# correct extractions and measurably lowers completeness, so a record is only
# discarded when the non-decision line is *all* it contains. Otherwise it is
# kept: the bogus line then costs one unmatched element, which is reported
# separately and never counted as hallucination.
#
# Deliberately anchored at the start of the sentence so genuine decisions that
# happen to contain a negation survive -- "The team decided not to integrate an
# LCD display" is a real decision and must be kept.
_NON_DECISION_RE = re.compile(
    r"^\s*(?:no|none|nothing|neither|"
    r"there\s+(?:was|were|is|are)\s+no|"
    r"the\s+(?:team|group)\s+did\s+not\s+(?:make|reach|come))\b"
    r"[^.]{0,80}?\b(?:decision|decided|agree\w*|consensus|conclusion|resolution)\b",
    re.IGNORECASE,
)


def is_non_decision(text: str) -> bool:
    """True when the 'decision' is really a statement that nothing was decided."""
    return bool(_NON_DECISION_RE.match(text or ""))


_REASONING_FIELDS = ("alternatives", "rationale", "conditions", "dissent")


def is_empty_non_decision(record) -> bool:
    """True when a record says nothing was decided AND carries no other reasoning.

    Accepts either a raw dict from the model or a DecisionRecord, so the extractor
    and the cache-replay path in scripts/run_qmsum_eval.py apply one rule.
    """
    get = record.get if isinstance(record, dict) else lambda k, d=None: getattr(record, k, d)
    if not is_non_decision(get("decision") or ""):
        return False
    return not any(get(f) or [] for f in _REASONING_FIELDS)


# --------------------------------------------------------------------------- #
# parsing / coercion
# --------------------------------------------------------------------------- #

def extract_json_object(text: str) -> dict:
    """Pull the JSON object out of a model response.

    Ollama's format="json" makes this almost always a no-op, but small models still
    occasionally emit a leading token or a trailing newline-delimited second object,
    so the fallback stays.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = _JSON_OBJ_RE.search(text)
    if not m:
        raise ValueError(f"No JSON object found in response: {text[:200]!r}")
    return json.loads(m.group(0))


def _as_list(value) -> list:
    """Small models return a bare string where a list is specified. Accept it."""
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v not in (None, "", [])]
    return [value]


def _clean_str(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"null", "none", "n/a", "na", "unknown", "not specified"}:
        return None
    return s


def coerce_record(
    raw: dict, *, decision_id: str, source_id: str, chunk_id: str
) -> DecisionRecord:
    """Turn one model-emitted decision dict into a validated DecisionRecord.

    Coercion here is strictly structural -- fixing list-vs-string, dropping nulls,
    normalising the status string. It never invents or reworks content, because
    doing so would launder a hallucination into something the scorer can't see.
    """
    status_raw = (_clean_str(raw.get("status")) or "decided").lower()
    status = status_raw if status_raw in _VALID_STATUSES else DecisionStatus.UNCLEAR.value

    alternatives = []
    for alt in _as_list(raw.get("alternatives")):
        if isinstance(alt, str):
            alternatives.append({"option": alt, "rejected": None, "reason": None})
            continue
        if not isinstance(alt, dict):
            continue
        option = _clean_str(alt.get("option") or alt.get("name"))
        if not option:
            continue
        rejected = alt.get("rejected")
        alternatives.append(
            {
                "option": option,
                "rejected": rejected if isinstance(rejected, bool) else None,
                "reason": _clean_str(alt.get("reason")),
            }
        )

    evidence = []
    for ev in _as_list(raw.get("evidence")):
        if isinstance(ev, str):
            evidence.append({"quote": ev, "speaker": None, "supports": "decision"})
            continue
        if not isinstance(ev, dict):
            continue
        quote = _clean_str(ev.get("quote") or ev.get("text"))
        if not quote:
            continue
        supports = (_clean_str(ev.get("supports")) or "decision").lower()
        if supports not in {
            "decision", "alternative", "rationale", "condition",
            "dissent", "owner", "approver", "status",
        }:
            supports = "decision"
        evidence.append(
            {"quote": quote, "speaker": _clean_str(ev.get("speaker")), "supports": supports}
        )

    conf = raw.get("extraction_confidence")
    try:
        conf = float(conf) if conf is not None else None
        if conf is not None:
            conf = min(max(conf, 0.0), 1.0)
    except (TypeError, ValueError):
        conf = None

    return DecisionRecord(
        decision_id=decision_id,
        source_id=source_id,
        chunk_id=chunk_id,
        schema_version=SCHEMA_VERSION,
        decision=_clean_str(raw.get("decision")) or "",
        topic=_clean_str(raw.get("topic")),
        status=status,
        alternatives=alternatives,
        rationale=[s for s in (_clean_str(r) for r in _as_list(raw.get("rationale"))) if s],
        conditions=[s for s in (_clean_str(c) for c in _as_list(raw.get("conditions"))) if s],
        dissent=[s for s in (_clean_str(d) for d in _as_list(raw.get("dissent"))) if s],
        owner=_clean_str(raw.get("owner")),
        approver=_clean_str(raw.get("approver")),
        evidence=evidence,
        extraction_confidence=conf,
    )


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #

class DecisionExtractor:
    def __init__(
        self,
        client: OllamaClient | None = None,
        model: str = DEFAULT_MODEL,
        verbose: bool = True,
        cot: bool = False,
    ):
        self.client = client or OllamaClient(model=model)
        self.verbose = verbose
        self.cot = cot  # Phase 3.1 ablation -- see prompts.COT_INSTRUCTION

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, file=sys.stderr, flush=True)

    def extract_from_chunk(self, chunk: Chunk) -> list[DecisionRecord]:
        """One model call for one chunk (two in CoT mode). Raises on unrecoverable failure."""
        notes = None
        if self.cot:
            notes = self.client.chat_text(
                COT_SYSTEM_PROMPT, build_cot_prompt(chunk.text, chunk.speakers)
            ).text
            self._log(f"  {chunk.chunk_id}: cot notes {len(notes)} chars")
        user = build_user_prompt(chunk.text, chunk.speakers, cot_notes=notes)
        resp = self.client.chat_json(SYSTEM_PROMPT, user)

        try:
            data = extract_json_object(resp.text)
        except (ValueError, json.JSONDecodeError) as e:
            self._log(f"  {chunk.chunk_id}: unparseable JSON, attempting repair ({e})")
            repair = REPAIR_PROMPT.format(error=str(e), previous=resp.text[:2000])
            resp = self.client.chat_json(SYSTEM_PROMPT, repair)
            data = extract_json_object(resp.text)

        raw_decisions = data.get("decisions")
        if raw_decisions is None and "decision" in data:
            raw_decisions = [data]  # model returned a bare decision object
        raw_decisions = _as_list(raw_decisions)

        records: list[DecisionRecord] = []
        for n, raw in enumerate(raw_decisions, start=1):
            if not isinstance(raw, dict):
                continue
            decision_text = _clean_str(raw.get("decision"))
            if not decision_text:
                continue  # no decision text -> nothing to record
            if is_empty_non_decision({**raw, "decision": decision_text}):
                self._log(f"  {chunk.chunk_id}: dropped an empty 'no decision' record")
                continue
            decision_id = f"{chunk.chunk_id}_d{n}"
            try:
                records.append(
                    coerce_record(
                        raw,
                        decision_id=decision_id,
                        source_id=chunk.source_id,
                        chunk_id=chunk.chunk_id,
                    )
                )
            except ValidationError as e:
                self._log(f"  {decision_id}: dropped, failed schema validation: {e.error_count()} error(s)")
        return records

    def extract_chunks(self, chunks: Iterable[Chunk], source_id: str) -> ExtractionResult:
        result = ExtractionResult(
            source_id=source_id,
            schema_version=SCHEMA_VERSION,
            model_name=self.client.model,
            merged_across_chunks=False,  # Task 4: explicitly not merging yet
        )
        for chunk in chunks:
            try:
                records = self.extract_from_chunk(chunk)
            except (OllamaCallFailed, ValueError, json.JSONDecodeError) as e:
                self._log(f"  {chunk.chunk_id}: FAILED -- {type(e).__name__}: {e}")
                result.chunks_failed.append(chunk.chunk_id)
                continue
            result.records.extend(records)
            result.chunks_processed += 1
            self._log(
                f"  {chunk.chunk_id}: {len(records)} decision(s) "
                f"[turns {chunk.turn_start}-{chunk.turn_end}]"
            )
        return result

    def extract_text(
        self,
        raw_text: str,
        source_id: str,
        max_tokens: int = 1200,
        overlap_turns: int = 2,
    ) -> ExtractionResult:
        chunks = chunk_text(
            raw_text, source_id=source_id, max_tokens=max_tokens, overlap_turns=overlap_turns
        )
        self._log(f"{source_id}: {len(chunks)} chunk(s), model={self.client.model}")
        return self.extract_chunks(chunks, source_id)

    def extract_file(
        self,
        file_path: str,
        doc_type: str = "transcript",
        max_tokens: int = 1200,
        overlap_turns: int = 2,
    ) -> ExtractionResult:
        from ..ingestion.ingest import ingest_file

        doc = ingest_file(file_path, doc_type=doc_type)
        source_id = doc.file_name.rsplit(".", 1)[0]
        return self.extract_text(
            doc.raw_text, source_id, max_tokens=max_tokens, overlap_turns=overlap_turns
        )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract DecisionRecords from a transcript.")
    ap.add_argument("file", help="transcript or document file (pdf/docx/txt/json/csv)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--doc-type", default="transcript", choices=["transcript", "document"])
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--overlap-turns", type=int, default=2)
    ap.add_argument("--out", help="write ExtractionResult JSON here")
    args = ap.parse_args(argv)

    try:
        client = OllamaClient(model=args.model)
        client.ensure_available()
    except OllamaUnavailable as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    extractor = DecisionExtractor(client=client)
    result = extractor.extract_file(
        args.file,
        doc_type=args.doc_type,
        max_tokens=args.max_tokens,
        overlap_turns=args.overlap_turns,
    )

    payload = result.model_dump(mode="json")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(
            f"{len(result.records)} record(s) from {result.chunks_processed} chunk(s) "
            f"-> {args.out}"
        )
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    if result.chunks_failed:
        print(f"WARNING: {len(result.chunks_failed)} chunk(s) failed: "
              f"{', '.join(result.chunks_failed)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
