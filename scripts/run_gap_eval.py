"""
Gap-detection evaluation over the whole benchmark (synthetic + QMSUM_AUTO + the 5
gold pairs).

For every reasoning element, each detector predicts gap vs present; that is scored
against `element.gold_gap`. Reports gap-class precision / recall / F1 / confusion,
overall and broken down by:

  * source            synthetic | qmsum | qmsum_auto
  * domain            product / academic / committee / <synthetic domain>
  * element_type      decision / alternative / rationale / condition / dissent / ...
  * in_document       omitted / verbatim / paraphrased / present_unspecified
                      -- the key diagnostic: does the detector miss PARAPHRASED
                      positives (the Task 2 failure mode)?

IMPORTANT: QMSUM_AUTO labels are silver (NLI-produced). NLI-vs-qmsum_auto is a
self-consistency number, not accuracy -- the report labels it as such. Trust the
`source=qmsum` (5 gold) and `source=synthetic` (constructed) rows, and the human
spot-check, for real accuracy.

Per-element scores are cached to outputs/gap_eval_scores.jsonl so re-runs (and the
slow LLM detector) resume.

    python scripts/run_gap_eval.py                          # nli + lexical
    python scripts/run_gap_eval.py --with-llm --llm-sample 300
    python scripts/run_gap_eval.py --threshold 0.55 --nli-model facebook/bart-large-mnli
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import PairSource, load_all
from edia.gapdetect.lexical import LexicalGapDetector
from edia.gapdetect.metrics import GapMetrics, sweep_threshold

PAIRS_DIR = Path("data/benchmark/pairs")
SCORES_CACHE = Path("outputs/gap_eval_scores.jsonl")
REPORT_MD = Path("outputs/gap_eval_results.md")
REPORT_JSON = Path("outputs/gap_eval_results.json")


def pair_domain(pair) -> str:
    t = (pair.topic or "").lower()
    if t.startswith("qmsum_"):
        return t.split("_", 1)[1]
    if t == "ami_product_design":
        return "product"
    if "__" in t:                      # synthetic domain__archetype (post Phase 4)
        return t.split("__", 1)[0]
    return t or "unknown"


def _load_cache() -> dict:
    cache: dict = {}
    if SCORES_CACHE.exists():
        for line in SCORES_CACHE.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            cache[(r["detector"], r["element_id"])] = r["present_score"]
    return cache


def _append_cache(rows: list[dict]) -> None:
    SCORES_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with SCORES_CACHE.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _make_detector(kind: str, nli_model: str, threshold: float):
    if kind == "lexical":
        return LexicalGapDetector(threshold=threshold)
    if kind == "nli":
        from edia.gapdetect.nli import NliGapDetector
        return NliGapDetector(model_name=nli_model, entail_threshold=threshold)
    if kind == "llm":
        from edia.gapdetect.entailment_llm import LlmEntailmentGapDetector
        return LlmEntailmentGapDetector(threshold=threshold)
    if kind == "ensemble":
        from edia.gapdetect.ensemble import EnsembleGapDetector
        return EnsembleGapDetector(nli_model=nli_model, nli_threshold=threshold)
    raise ValueError(kind)


def _score_all(detector, dkey: str, elements, cache: dict, verbose_every=500):
    """Yield (element_meta, present_score); fill+persist cache as it goes."""
    fresh: list[dict] = []
    for i, (pair, el) in enumerate(elements):
        key = (dkey, el.element_id)
        if key in cache:
            score = cache[key]
        else:
            score = detector.present_score(pair.document, el.text)
            row = {"detector": dkey, "element_id": el.element_id,
                   "present_score": round(float(score), 5)}
            fresh.append(row)
            cache[key] = score
            if len(fresh) >= 200:
                _append_cache(fresh); fresh = []
        if verbose_every and i and i % verbose_every == 0:
            print(f"  {dkey}: {i}/{len(elements)} elements")
        yield pair, el, score
    if fresh:
        _append_cache(fresh)


def _breakdowns(rows):
    """rows: list of (source, domain, etype, sublabel, predicted_gap, actual_gap)."""
    dims = {"by_source": 0, "by_domain": 1, "by_element_type": 2, "by_in_document": 3}
    out: dict = {}
    for name, idx in dims.items():
        buckets: dict[str, GapMetrics] = defaultdict(GapMetrics)
        for r in rows:
            buckets[r[idx]].add(r[4], r[5])
        out[name] = {k: m.to_dict() for k, m in sorted(buckets.items())}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(PAIRS_DIR))
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--nli-model", default="roberta-large-mnli")
    ap.add_argument("--detectors", nargs="+", default=["nli", "lexical"],
                    choices=["nli", "lexical", "llm", "ensemble"])
    ap.add_argument("--with-llm", action="store_true", help="shorthand: add 'llm'")
    ap.add_argument("--llm-sample", type=int, default=0,
                    help="run the llm detector on a stratified sample of N elements only")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args(argv)

    detectors = list(dict.fromkeys(args.detectors + (["llm"] if args.with_llm else [])))
    pairs = load_all(args.dir)
    if not pairs:
        raise SystemExit(f"no pairs in {args.dir}")

    all_elements = [(p, el) for p in pairs for el in p.elements]
    print(f"{len(pairs)} pairs, {len(all_elements)} elements; detectors={detectors}")

    cache = _load_cache()
    report: dict = {"threshold": args.threshold, "nli_model": args.nli_model,
                    "pairs": len(pairs), "elements": len(all_elements), "detectors": {}}

    for kind in detectors:
        dkey = f"nli:{args.nli_model}" if kind == "nli" else kind
        det = _make_detector(kind, args.nli_model, args.threshold)

        elements = all_elements
        if kind in ("llm", "ensemble") and args.llm_sample:
            rng = random.Random(args.seed)
            by_cell: dict = defaultdict(list)
            for p, el in all_elements:
                by_cell[(p.source.value, el.element_type.value, el.gold_gap)].append((p, el))
            picked: list = []
            per = max(1, args.llm_sample // max(1, len(by_cell)))
            for cell in by_cell.values():
                rng.shuffle(cell)
                picked.extend(cell[:per])
            elements = picked[:args.llm_sample]
            print(f"  {kind}: stratified sample of {len(elements)} elements")

        rows = []
        overall = GapMetrics()
        scores: list[float] = []
        gaps: list[bool] = []
        fp_list, fn_list = [], []
        for pair, el, score in _score_all(det, dkey, elements, cache):
            predicted_gap = score < args.threshold
            actual_gap = el.gold_gap
            overall.add(predicted_gap, actual_gap)
            scores.append(float(score)); gaps.append(actual_gap)
            rows.append((pair.source.value, pair_domain(pair), el.element_type.value,
                         el.in_document.value, predicted_gap, actual_gap))
            if predicted_gap and not actual_gap:
                fp_list.append({"pair_id": pair.pair_id, "type": el.element_type.value,
                                "in_document": el.in_document.value, "text": el.text,
                                "present_score": round(float(score), 3)})
            elif not predicted_gap and actual_gap:
                fn_list.append({"pair_id": pair.pair_id, "type": el.element_type.value,
                                "text": el.text, "present_score": round(float(score), 3)})

        report["detectors"][dkey] = {
            "n_elements_scored": len(rows),
            "overall": overall.to_dict(),
            "threshold_sweep": sweep_threshold(scores, gaps),
            "breakdowns": _breakdowns(rows),
            "false_positives": fp_list[:200],
            "false_negatives": fn_list[:200],
        }
        o = overall.to_dict()
        print(f"  {dkey}: P={o['precision']} R={o['recall']} F1={o['f1']} "
              f"acc={o['accuracy']} (FN={o['confusion']['fn']})")

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT_MD.write_text(_render_md(report), encoding="utf-8")
    print(f"\nwrote {REPORT_MD} and {REPORT_JSON}")
    return 0


def _render_md(report: dict) -> str:
    L = [f"# Gap detection — benchmark results\n",
         f"- threshold (present if entail/score ≥): **{report['threshold']}**",
         f"- {report['pairs']} pairs, {report['elements']} elements\n",
         "> **QMSUM_AUTO is silver.** Its labels are NLI-produced, so the "
         "`source=qmsum_auto` rows for the NLI detector measure self-consistency, "
         "not accuracy. Read `source=qmsum` (5 hand-gold) and `source=synthetic` "
         "(constructed labels) for real accuracy, plus the human spot-check.\n"]
    if any(k.startswith("nli:") for k in report["detectors"]):
        L.insert(2, f"- NLI model: `{report['nli_model']}`")
    for dkey, d in report["detectors"].items():
        o = d["overall"]
        L.append(f"## {dkey}\n")
        L.append(f"**Gap class:** P={o['precision']} · R={o['recall']} · "
                 f"F1={o['f1']} · n={o['n']} · base rate={o['gap_base_rate']}")
        L.append(f"**Present class (the hard half):** P={o['present_precision']} · "
                 f"R={o['present_recall']} · F1={o['present_f1']}")
        L.append(f"**Balanced accuracy: {o['balanced_accuracy']}** "
                 f"(all-gap detector scores 0.5) · raw acc={o['accuracy']}")
        L.append(f"Confusion: tp={o['confusion']['tp']} fp={o['confusion']['fp']} "
                 f"fn={o['confusion']['fn']} tn={o['confusion']['tn']}\n")
        # Same trap agreement.py guards for: with a ~93% gap base rate a high F1 is
        # mostly chance. Say so in the report rather than letting the headline stand.
        if o["gap_base_rate"] >= 0.85:
            allgap_f1 = 2 * o["gap_base_rate"] / (1 + o["gap_base_rate"])
            L.append(
                f"> **Base-rate warning.** {o['gap_base_rate']:.0%} of these elements "
                "are gaps, so a detector that called *everything* a gap would already "
                f"score F1 {allgap_f1:.3f}. Read the `by_in_document` table below "
                "(accuracy on the *present* rows) and the balanced "
                "`source=synthetic` rows, not this headline.\n"
            )
        for bname, buckets in d["breakdowns"].items():
            L.append(f"### {dkey} — {bname}\n")
            L.append("| bucket | n | base rate | gap P | gap R | gap F1 "
                     "| present R | **bal acc** |")
            L.append("|---|--:|--:|--:|--:|--:|--:|--:|")
            for k, m in buckets.items():
                L.append(f"| {k} | {m['n']} | {m['gap_base_rate']} | {m['precision']} "
                         f"| {m['recall']} | {m['f1']} | {m['present_recall']} "
                         f"| **{m['balanced_accuracy']}** |")
            L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
