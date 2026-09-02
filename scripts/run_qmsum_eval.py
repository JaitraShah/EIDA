"""
Task 4 step 6: run the extractor over the five Task 1 QMSum transcripts and score
completeness and hallucination against outputs/gap_validation_results.md.

Checkpointed per pair: a completed extraction is written to
outputs/extractions/<PAIR>.json and reused on the next run unless --force is passed.
A 600-turn transcript at ~10 chunks x ~40s per chunk on CPU is minutes per meeting,
so losing a finished run to a crash in the scorer would be genuinely annoying.

Usage:
    python scripts/prepare_qmsum.py
    python scripts/run_qmsum_eval.py                 # lexical matcher, mistral
    python scripts/run_qmsum_eval.py --semantic      # paraphrase-tolerant matcher
    python scripts/run_qmsum_eval.py --only QSUM_002 --force
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.qmsum_ground_truth import BY_ID, GROUND_TRUTH
from edia.benchmark.score import (
    DEFAULT_MATCH_THRESHOLD,
    SemanticMatcher,
    render_markdown,
    score_extraction,
)
from edia.extraction.chunker import chunk_text
from edia.extraction.extractor import DecisionExtractor, is_empty_non_decision
from edia.extraction.llm_client import DEFAULT_MODEL, OllamaClient, OllamaUnavailable
from edia.extraction.schema import DecisionRecord, ExtractionResult
from edia.ingestion.ingest import ingest_file

DATA = Path("data/qmsum")
EXTRACT_DIR = Path("outputs/extractions")
REPORT_MD = Path("outputs/task4_extraction_results.md")
REPORT_JSON = Path("outputs/task4_extraction_scores.json")


def _drop_non_decisions(records: list[DecisionRecord], label: str) -> list[DecisionRecord]:
    """Apply the extractor's non-decision filter to records that were cached before
    that filter existed, so a cached run and a fresh run report the same numbers."""
    kept = [r for r in records if not is_empty_non_decision(r)]
    dropped = len(records) - len(kept)
    if dropped:
        print(f"  {label}: dropped {dropped} 'no decision was made' record(s) from cache")
    return kept


def load_or_extract(
    pair_id: str, extractor: DecisionExtractor, args
) -> tuple[ExtractionResult, dict[str, str], float]:
    transcript = DATA / f"{pair_id}_transcript.json"
    if not transcript.exists():
        raise SystemExit(f"{transcript} missing -- run scripts/prepare_qmsum.py first")

    doc = ingest_file(str(transcript), doc_type="transcript")
    chunks = chunk_text(
        doc.raw_text,
        source_id=pair_id,
        max_tokens=args.max_tokens,
        overlap_turns=args.overlap_turns,
    )
    chunk_texts = {c.chunk_id: c.text for c in chunks}

    cache = EXTRACT_DIR / f"{pair_id}.json"
    if cache.exists() and not args.force:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        print(f"{pair_id}: reusing cached extraction ({cache})")
        cached_result = ExtractionResult.model_validate(payload)
        cached_result.records = _drop_non_decisions(cached_result.records, pair_id)
        return cached_result, chunk_texts, 0.0

    print(f"{pair_id}: {len(chunks)} chunks, {doc.metadata.get('word_count')} words -> {args.model}")
    start = time.time()

    # Per-chunk checkpointing. At ~200s/chunk on a 4GB GPU a 14-chunk meeting is
    # ~45 minutes, so losing a whole pair to one interruption is worth avoiding.
    chunk_cache = EXTRACT_DIR / "chunks"
    chunk_cache.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult(
        source_id=pair_id, model_name=args.model, merged_across_chunks=False
    )
    for chunk in chunks:
        cpath = chunk_cache / f"{chunk.chunk_id}.json"
        if cpath.exists() and not args.force:
            cached = json.loads(cpath.read_text(encoding="utf-8"))
            result.records.extend(
                _drop_non_decisions(
                    [DecisionRecord.model_validate(r) for r in cached["records"]],
                    chunk.chunk_id,
                )
            )
            result.chunks_processed += 1
            print(f"  {chunk.chunk_id}: cached ({len(cached['records'])} record(s))")
            continue
        try:
            records = extractor.extract_from_chunk(chunk)
        except Exception as e:
            print(f"  {chunk.chunk_id}: FAILED -- {type(e).__name__}: {e}")
            result.chunks_failed.append(chunk.chunk_id)
            continue
        result.records.extend(records)
        result.chunks_processed += 1
        cpath.write_text(
            json.dumps(
                {"records": [r.model_dump(mode="json") for r in records]},
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"  {chunk.chunk_id}: {len(records)} record(s) "
              f"[turns {chunk.turn_start}-{chunk.turn_end}]")

    elapsed = time.time() - start

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"{pair_id}: {len(result.records)} record(s) in {elapsed:.0f}s -> {cache}")
    return result, chunk_texts, elapsed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--overlap-turns", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=DEFAULT_MATCH_THRESHOLD)
    ap.add_argument("--semantic", action="store_true",
                    help="use sentence-transformer matching (paraphrase-tolerant)")
    ap.add_argument("--only", help="run a single pair id, e.g. QSUM_002")
    ap.add_argument("--force", action="store_true", help="ignore cached extractions")
    args = ap.parse_args(argv)

    pairs = [BY_ID[args.only]] if args.only else GROUND_TRUTH

    try:
        # The timeout has to clear the worst legitimate generation, or it starves
        # chunks rather than protecting them. num_predict caps output at 2048
        # tokens; measured throughput on this box is ~2.6 tok/s with 60% of the
        # model on CPU, so a full-length answer needs ~790s. A 420s ceiling killed
        # QSUM_005_c009 six times before that arithmetic got done. 1200s leaves
        # headroom while still bounding a socket that hangs when the machine sleeps
        # -- generation itself cannot run away, because num_predict bounds it.
        client = OllamaClient(model=args.model, timeout=1200)
        client.ensure_available()
    except OllamaUnavailable as e:
        # Cached extractions can still be re-scored without a live model.
        if args.force or not all((EXTRACT_DIR / f"{p.pair_id}.json").exists() for p in pairs):
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        print(f"NOTE: {e}\n      scoring cached extractions only.", file=sys.stderr)
        client = None

    extractor = DecisionExtractor(client=client, verbose=True) if client else None
    matcher = SemanticMatcher() if args.semantic else None

    reports = []
    total_time = 0.0
    for truth in pairs:
        result, chunk_texts, elapsed = load_or_extract(truth.pair_id, extractor, args)
        total_time += elapsed
        reports.append(
            score_extraction(
                result, truth, chunk_texts=chunk_texts,
                threshold=args.threshold, semantic=matcher,
            )
        )

    md = render_markdown(reports)
    header = (
        f"# Task 4 — Extraction results on the five Task 1 QMSum pairs\n\n"
        f"- model: `{args.model}` (temperature=0, seed=0, top_k=1)\n"
        f"- chunking: max_tokens={args.max_tokens}, overlap_turns={args.overlap_turns}\n"
        f"- matcher: `{reports[0].matcher}` at threshold {args.threshold}\n"
        f"- cross-chunk merging: **off** (Task 4 constraint)\n"
        f"- ground truth: `outputs/gap_validation_results.md` via "
        f"`edia/benchmark/qmsum_ground_truth.py`\n"
        f"- extraction wall time this run: {total_time:.0f}s\n\n"
        f"**Reading the numbers:** *unsupported evidence* is the hallucination rate — "
        f"model quotes that do not occur in the source chunk, an objective check. "
        f"*Unmatched extracted* is NOT a hallucination rate: the Task 1 tables were built to "
        f"answer \"did the document drop this?\", not to enumerate everything the discussion "
        f"contained, so an unmatched element may be a correct extraction Task 1 never "
        f"tabulated. Those items are listed in the JSON for human adjudication.\n\n"
    )
    # The two matchers answer different questions and both get reported, so the
    # semantic pass must not overwrite the lexical one.
    suffix = "_semantic" if args.semantic else ""
    report_md = REPORT_MD.with_name(REPORT_MD.stem + suffix + REPORT_MD.suffix)
    report_json = REPORT_JSON.with_name(REPORT_JSON.stem + suffix + REPORT_JSON.suffix)

    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text(header + md + "\n", encoding="utf-8")
    report_json.write_text(
        json.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + md.split("\n### ")[0])
    print(f"\nwrote {REPORT_MD} and {REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
