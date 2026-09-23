"""
Phase 3.1 — chain-of-thought ablation (EDIA_Project_Plan_v2.md).

Does asking the model to reason step-by-step before extracting improve
completeness? The plan's hypothesis: CoT helps reasoning at answer time but does
not help find facts scattered across a chunk, so any gain should be small. This
script measures the actual delta rather than assuming it.

Mirrors run_qmsum_eval.py's checkpointing exactly, but points the extractor and
the cache at a separate directory (outputs/extractions_cot/) so a CoT run can
never silently overwrite -- or be silently satisfied by -- the baseline cache.

Scope: the 5 gold Product/test meetings (QSUM_001-005), because completeness needs
hand-built ground truth and that exists only for them (same scoping decision as
Phase 2.3). Scored with BOTH matchers, matching the baseline so the two are
comparable line-for-line.

    python scripts/run_cot_ablation.py
    python scripts/run_cot_ablation.py --only QSUM_002 --force
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.qmsum_ground_truth import BY_ID, GROUND_TRUTH
from edia.benchmark.score import SemanticMatcher, render_markdown, score_extraction
from edia.extraction.chunker import chunk_text
from edia.extraction.extractor import DecisionExtractor
from edia.extraction.llm_client import DEFAULT_MODEL, OllamaClient, OllamaUnavailable
from edia.extraction.schema import DecisionRecord, ExtractionResult
from edia.ingestion.ingest import ingest_file

DATA = Path("data/qmsum")
EXTRACT_DIR = Path("outputs/extractions_cot")
BASELINE_LEX = Path("outputs/task4_extraction_scores.json")
BASELINE_SEM = Path("outputs/task4_extraction_scores_semantic.json")
REPORT_MD = Path("outputs/cot_ablation_results.md")
REPORT_JSON = Path("outputs/cot_ablation_results.json")


def load_or_extract(pair_id: str, extractor: DecisionExtractor, args) -> ExtractionResult:
    transcript = DATA / f"{pair_id}_transcript.json"
    if not transcript.exists():
        raise SystemExit(f"{transcript} missing -- run scripts/prepare_qmsum.py first")

    doc = ingest_file(str(transcript), doc_type="transcript")
    chunks = chunk_text(doc.raw_text, source_id=pair_id,
                        max_tokens=args.max_tokens, overlap_turns=args.overlap_turns)

    cache = EXTRACT_DIR / f"{pair_id}.json"
    if cache.exists() and not args.force:
        print(f"{pair_id}: reusing cached CoT extraction ({cache})")
        return ExtractionResult.model_validate(json.loads(cache.read_text(encoding="utf-8")))

    print(f"{pair_id}: {len(chunks)} chunks -> {args.model} (cot=True)")
    start = time.time()
    chunk_cache = EXTRACT_DIR / "chunks"
    chunk_cache.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult(source_id=pair_id, model_name=args.model, merged_across_chunks=False)

    for chunk in chunks:
        cpath = chunk_cache / f"{chunk.chunk_id}.json"
        if cpath.exists() and not args.force:
            cached = json.loads(cpath.read_text(encoding="utf-8"))
            result.records.extend(DecisionRecord.model_validate(r) for r in cached["records"])
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
            json.dumps({"records": [r.model_dump(mode="json") for r in records]},
                      indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  {chunk.chunk_id}: {len(records)} record(s)")

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
                     encoding="utf-8")
    print(f"{pair_id}: {len(result.records)} record(s) in {time.time()-start:.0f}s -> {cache}")
    return result


def _baseline_completeness() -> dict[str, tuple[float, float]]:
    """pair_id -> (lexical completeness, semantic completeness), if already run."""
    out: dict[str, tuple[float, float]] = {}
    if BASELINE_LEX.exists() and BASELINE_SEM.exists():
        lex = {r["pair_id"]: r["completeness"] for r in json.loads(BASELINE_LEX.read_text())}
        sem = {r["pair_id"]: r["completeness"] for r in json.loads(BASELINE_SEM.read_text())}
        for pid in lex:
            out[pid] = (lex[pid], sem.get(pid, 0.0))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--overlap-turns", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.45)
    ap.add_argument("--only", help="run a single pair id, e.g. QSUM_002")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    pairs = [BY_ID[args.only]] if args.only else GROUND_TRUTH

    try:
        client = OllamaClient(model=args.model, timeout=1200)
        client.ensure_available()
    except OllamaUnavailable as e:
        if args.force or not all((EXTRACT_DIR / f"{p.pair_id}.json").exists() for p in pairs):
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        print(f"NOTE: {e}\n      scoring cached extractions only.", file=sys.stderr)
        client = None

    extractor = DecisionExtractor(client=client, verbose=True, cot=True) if client else None
    lex_reports, sem_reports = [], []
    sem_matcher = SemanticMatcher()

    for truth in pairs:
        result = load_or_extract(truth.pair_id, extractor, args)
        lex_reports.append(score_extraction(result, truth, threshold=args.threshold))
        sem_reports.append(score_extraction(result, truth, threshold=0.55, semantic=sem_matcher))

    baseline = _baseline_completeness()
    lines = [
        "# Phase 3.1 — chain-of-thought ablation",
        "",
        f"- model: `{args.model}` (temperature=0), prompt: baseline + "
        f"`prompts.COT_INSTRUCTION` prepended before the excerpt",
        f"- scope: the 5 gold Product/test meetings (same as Phase 2.3 -- only they "
        f"have completeness ground truth)",
        "",
        "| pair | baseline (lex) | CoT (lex) | Δ | baseline (sem) | CoT (sem) | Δ |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]
    for lr, sr in zip(lex_reports, sem_reports):
        base_lex, base_sem = baseline.get(lr.pair_id, (float("nan"), float("nan")))
        d_lex = lr.completeness - base_lex if base_lex == base_lex else float("nan")
        d_sem = sr.completeness - base_sem if base_sem == base_sem else float("nan")
        lines.append(
            f"| {lr.pair_id} | {base_lex:.3f} | {lr.completeness:.3f} | {d_lex:+.3f} | "
            f"{base_sem:.3f} | {sr.completeness:.3f} | {d_sem:+.3f} |"
        )

    tot_lex_gt = sum(r.gt_total for r in lex_reports)
    tot_lex_m = sum(r.gt_matched for r in lex_reports)
    tot_sem_gt = sum(r.gt_total for r in sem_reports)
    tot_sem_m = sum(r.gt_matched for r in sem_reports)
    if baseline:
        base_lex_tot = sum(baseline[p][0] for p in baseline) / len(baseline)
        base_sem_tot = sum(baseline[p][1] for p in baseline) / len(baseline)
    else:
        base_lex_tot = base_sem_tot = float("nan")

    lines += [
        f"| **total** | **{base_lex_tot:.3f}** | **{tot_lex_m/tot_lex_gt:.3f}** | "
        f"**{tot_lex_m/tot_lex_gt - base_lex_tot:+.3f}** | **{base_sem_tot:.3f}** | "
        f"**{tot_sem_m/tot_sem_gt:.3f}** | **{tot_sem_m/tot_sem_gt - base_sem_tot:+.3f}** |",
        "",
        "Baseline column reads from `outputs/task4_extraction_scores{,_semantic}.json` "
        "-- run `python scripts/run_qmsum_eval.py` and `--semantic` first if those are "
        "missing or stale.",
        "",
        "## Reading",
        "",
        f"Semantic-scored completeness moved by **{tot_sem_m/tot_sem_gt - base_sem_tot:+.1%}** "
        "under CoT. A small delta (positive or negative) supports the plan's hypothesis: "
        "CoT changes how the model reasons about content already in front of it, not "
        "whether it can locate content scattered elsewhere in the meeting -- so it should "
        "not move completeness much either way. A large positive delta would need a second "
        "look before quoting it, since it would contradict the diagnosis in Table 3.",
    ]

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps({
            "model": args.model,
            "lexical": [r.to_dict() for r in lex_reports],
            "semantic": [r.to_dict() for r in sem_reports],
            "baseline_completeness": {k: list(v) for k, v in baseline.items()},
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("\n".join(lines))
    print(f"\nwrote {REPORT_MD} and {REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
