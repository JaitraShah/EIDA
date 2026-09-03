"""
Corpus-wide extraction: run the Task 4 extractor over every QMSum meeting (all
domains / splits) and score the OBJECTIVE half only -- evidence grounding
(hallucination rate) and strict-verbatim rate. Completeness/recall is not scored
here because only the 5 gold meetings have hand-built reasoning ground truth
(use scripts/run_qmsum_eval.py for those).

Per-chunk and per-meeting checkpointing to outputs/extractions/ (shared with
run_qmsum_eval.py), so an interrupted run resumes. Sharded for multi-GPU.

    python scripts/run_corpus_extraction.py --limit 3          # smoke test
    python scripts/run_corpus_extraction.py --shard 0/4        # one of four workers
    python scripts/run_corpus_extraction.py --domains Academic Committee
    python scripts/run_corpus_extraction.py --rescore-only     # no model, just re-aggregate

Output: outputs/corpus_extraction_results.md + .json, aggregated by domain x split.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.qmsum_corpus import RAW_ROOT, iter_meetings
from edia.benchmark.score import score_extraction
from edia.extraction.chunker import chunk_text
from edia.extraction.extractor import DecisionExtractor
from edia.extraction.llm_client import DEFAULT_MODEL, OllamaClient, OllamaUnavailable
from edia.extraction.schema import DecisionRecord, ExtractionResult

EXTRACT_DIR = Path("outputs/extractions")
REPORT_MD = Path("outputs/corpus_extraction_results.md")
REPORT_JSON = Path("outputs/corpus_extraction_results.json")


def _extract_meeting(meeting, extractor, args) -> tuple[ExtractionResult, dict]:
    chunks = chunk_text(meeting.transcript, source_id=meeting.meeting_id,
                        max_tokens=args.max_tokens, overlap_turns=args.overlap_turns)
    chunk_texts = {c.chunk_id: c.text for c in chunks}

    cache = EXTRACT_DIR / f"{meeting.meeting_id}.json"
    if cache.exists() and not args.force:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        return ExtractionResult.model_validate(payload), chunk_texts

    if extractor is None:
        raise RuntimeError(f"{meeting.meeting_id}: no cached extraction and no live model")

    chunk_cache = EXTRACT_DIR / "chunks"
    chunk_cache.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult(source_id=meeting.meeting_id, model_name=args.model,
                              merged_across_chunks=False)
    for chunk in chunks:
        cpath = chunk_cache / f"{chunk.chunk_id}.json"
        if cpath.exists() and not args.force:
            cached = json.loads(cpath.read_text(encoding="utf-8"))
            result.records.extend(DecisionRecord.model_validate(r) for r in cached["records"])
            result.chunks_processed += 1
            continue
        try:
            records = extractor.extract_from_chunk(chunk)
        except Exception as e:  # noqa: BLE001
            print(f"  {chunk.chunk_id}: FAILED -- {type(e).__name__}: {e}")
            result.chunks_failed.append(chunk.chunk_id)
            continue
        result.records.extend(records)
        result.chunks_processed += 1
        cpath.write_text(json.dumps(
            {"records": [r.model_dump(mode="json") for r in records]},
            indent=2, ensure_ascii=False), encoding="utf-8")

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result.model_dump(mode="json"), indent=2,
                                ensure_ascii=False), encoding="utf-8")
    return result, chunk_texts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(RAW_ROOT))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--domains", nargs="+", default=["Academic", "Committee", "Product"])
    ap.add_argument("--splits", nargs="+", default=["train", "val", "test"])
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--overlap-turns", type=int, default=2)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--shard", help="k/N")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--rescore-only", action="store_true",
                    help="skip the model; only re-aggregate cached extractions")
    args = ap.parse_args(argv)

    meetings = list(iter_meetings(args.root, tuple(args.domains), tuple(args.splits)))
    print(f"{len(meetings)} meetings in scope")

    extractor = None
    if not args.rescore_only:
        try:
            client = OllamaClient(model=args.model, timeout=1200)
            client.ensure_available()
            extractor = DecisionExtractor(client=client, verbose=False)
        except OllamaUnavailable as e:
            print(f"NOTE: {e}\n      scoring cached extractions only.", file=sys.stderr)

    reports = []
    done = 0
    t0 = time.time()
    for i, m in enumerate(meetings):
        if args.shard:
            k, n = (int(x) for x in args.shard.split("/"))
            if i % n != k:
                continue
        if args.limit is not None and done >= args.limit:
            break
        cache = EXTRACT_DIR / f"{m.meeting_id}.json"
        if extractor is None and not cache.exists():
            continue
        try:
            result, chunk_texts = _extract_meeting(m, extractor, args)
        except Exception as e:  # noqa: BLE001
            print(f"{m.meeting_id}: SKIP -- {type(e).__name__}: {e}")
            continue
        rep = score_extraction(result, truth=None, chunk_texts=chunk_texts,
                               pair_id=m.meeting_id)
        rep.__dict__["_domain"] = m.domain
        rep.__dict__["_split"] = m.split
        reports.append(rep)
        done += 1
        print(f"{m.meeting_id}: {len(result.records)} records, "
              f"{rep.quotes_grounded}/{rep.quotes_total} quotes grounded "
              f"({rep.unsupported_evidence_rate:.0%} unsupported)")

    if not reports:
        print("nothing scored (no cached extractions and no live model).")
        return 1

    # aggregate by domain x split
    agg: dict = defaultdict(lambda: {"meetings": 0, "records": 0, "q_total": 0,
                                     "q_grounded": 0, "q_strict": 0, "chunks_failed": 0})
    for r in reports:
        key = f"{r.__dict__['_domain']}/{r.__dict__['_split']}"
        a = agg[key]
        a["meetings"] += 1
        a["records"] += r.records
        a["q_total"] += r.quotes_total
        a["q_grounded"] += r.quotes_grounded
        a["q_strict"] += r.quotes_strict_grounded
        a["chunks_failed"] += len(r.chunks_failed)

    def rates(a):
        qt = a["q_total"] or 1
        return {**a,
                "evidence_grounding": round(a["q_grounded"] / qt, 3),
                "unsupported_evidence_rate": round(1 - a["q_grounded"] / qt, 3),
                "strict_verbatim_rate": round(a["q_strict"] / qt, 3)}

    out = {"model": args.model, "meetings_scored": len(reports),
           "wall_seconds": round(time.time() - t0, 1),
           "by_domain_split": {k: rates(v) for k, v in sorted(agg.items())},
           "per_meeting": [
               {"meeting_id": r.pair_id, "domain": r.__dict__["_domain"],
                "split": r.__dict__["_split"], "records": r.records,
                "quotes": f"{r.quotes_grounded}/{r.quotes_total}",
                "unsupported_evidence_rate": round(r.unsupported_evidence_rate, 3),
                "strict_verbatim_rate": round(r.strict_verbatim_rate, 3),
                "chunks_failed": len(r.chunks_failed)}
               for r in reports]}

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    L = [f"# Corpus extraction — hallucination scoring over QMSum\n",
         f"- model: `{args.model}` (temperature=0, seed=0)",
         f"- meetings scored: {len(reports)} / {len(meetings)} in scope",
         f"- completeness/recall NOT scored here (no hand ground truth beyond the 5 gold)\n",
         "| domain/split | meetings | records | quotes grounded | unsupported | strict verbatim | chunks failed |",
         "|---|--:|--:|--:|--:|--:|--:|"]
    for k, v in sorted(agg.items()):
        r = rates(v)
        L.append(f"| {k} | {r['meetings']} | {r['records']} | "
                 f"{r['q_grounded']}/{r['q_total']} ({r['evidence_grounding']:.0%}) | "
                 f"{r['unsupported_evidence_rate']:.0%} | {r['strict_verbatim_rate']:.0%} | "
                 f"{r['chunks_failed']} |")
    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nwrote {REPORT_MD} and {REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
