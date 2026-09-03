"""
Calibrate the auto gap-labeller against the 5 hand-validated gold pairs
(QSUM_001..005). These are the ONLY QMSum meetings with human present/gap labels,
so they are the trust anchor for the ~227 auto-labelled ones.

For each gold pair, run each detector on (pair.document, element.text) for every
hand-labelled element and compare the predicted gap to element.gold_gap. Reports
gap-class precision/recall/F1/confusion and a threshold sweep, per detector.

Gate for proceeding to the full corpus build: NLI gap-class F1 >= ~0.9 and zero
(or near-zero) false negatives, consistent with the 21/22 Task 2 pilot
(outputs/nli_transfer_test_results.md). If it comes in lower, retune
--threshold or fall back to the LLM detector before mass-labelling.

    python scripts/calibrate_qmsum_labels.py                       # nli + lexical
    python scripts/calibrate_qmsum_labels.py --models roberta-large-mnli facebook/bart-large-mnli
    python scripts/calibrate_qmsum_labels.py --with-llm            # also the Ollama ablation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import load_all
from edia.gapdetect.lexical import LexicalGapDetector
from edia.gapdetect.metrics import GapMetrics, sweep_threshold

GOLD_IDS = ["QSUM_001", "QSUM_002", "QSUM_003", "QSUM_004", "QSUM_005"]
PAIRS_DIR = Path("data/benchmark/pairs")
OUT = Path("outputs/qmsum_label_calibration.json")


def _gold_pairs():
    pairs = {p.pair_id: p for p in load_all(PAIRS_DIR)}
    missing = [g for g in GOLD_IDS if g not in pairs]
    if missing:
        raise SystemExit(f"missing gold pairs {missing} -- run `python -m edia.benchmark.fold_qmsum`")
    return [pairs[g] for g in GOLD_IDS]


def _eval_detector(detector, pairs, threshold: float) -> dict:
    per_pair = []
    scores: list[float] = []
    gaps: list[bool] = []
    overall = GapMetrics()
    for p in pairs:
        m = GapMetrics()
        for el in p.elements:
            s = detector.present_score(p.document, el.text)
            predicted_gap = s < threshold
            m.add(predicted_gap, el.gold_gap)
            overall.add(predicted_gap, el.gold_gap)
            scores.append(s)
            gaps.append(el.gold_gap)
        per_pair.append({"pair_id": p.pair_id, **m.to_dict()})
    return {
        "threshold": threshold,
        "overall": overall.to_dict(),
        "per_pair": per_pair,
        "threshold_sweep": sweep_threshold(scores, gaps),
        "false_negatives": [
            {"pair_id": p.pair_id, "type": el.element_type.value, "text": el.text,
             "present_score": round(detector.present_score(p.document, el.text), 3)}
            for p in pairs for el in p.elements
            if el.gold_gap and detector.present_score(p.document, el.text) >= threshold
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=["roberta-large-mnli"],
                    help="HF NLI model id(s) to calibrate")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--with-llm", action="store_true", help="also run the Ollama detector")
    ap.add_argument("--no-nli", action="store_true", help="lexical (+llm) only")
    args = ap.parse_args(argv)

    pairs = _gold_pairs()
    n_elems = sum(len(p.elements) for p in pairs)
    n_gaps = sum(p.gap_count for p in pairs)
    print(f"gold: {len(pairs)} pairs, {n_elems} hand-labelled elements, {n_gaps} gaps\n")

    results: dict[str, dict] = {}

    results["lexical"] = _eval_detector(LexicalGapDetector(), pairs, args.threshold)

    if not args.no_nli:
        from edia.gapdetect.nli import NliGapDetector
        for model_name in args.models:
            print(f"loading {model_name} ...")
            det = NliGapDetector(model_name=model_name, entail_threshold=args.threshold)
            results[f"nli:{model_name}"] = _eval_detector(det, pairs, args.threshold)

    if args.with_llm:
        from edia.gapdetect.entailment_llm import LlmEntailmentGapDetector
        results["llm_entailment"] = _eval_detector(
            LlmEntailmentGapDetector(), pairs, args.threshold
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'detector':32s} {'P':>6} {'R':>6} {'F1':>6} {'acc':>6}  FN")
    for name, r in results.items():
        o = r["overall"]
        print(f"{name:32s} {o['precision']:6.3f} {o['recall']:6.3f} {o['f1']:6.3f} "
              f"{o['accuracy']:6.3f}  {o['confusion']['fn']}")
    print(f"\nfull detail -> {OUT}")

    best_nli = next((r for n, r in results.items() if n.startswith("nli:")), None)
    if best_nli:
        f1 = best_nli["overall"]["f1"]
        fn = best_nli["overall"]["confusion"]["fn"]
        ok = f1 >= 0.9 and fn <= 1
        print(f"\nGATE: NLI F1={f1:.3f}, FN={fn}  -> {'PASS' if ok else 'REVIEW before full build'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
