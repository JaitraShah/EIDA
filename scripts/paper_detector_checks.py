"""
Two detector checks behind the paper's Table 1, computed from the score cache only
(no model calls):

1. All four detectors on the SAME stratified sample the LLM/ensemble ablation used
   (run_gap_eval.py's sampling: seed 13, per-cell cap 400 // n_cells -> 296 elements),
   restricted to gold + synthetic (200 elements). The 96 qmsum_auto elements are
   dropped because their labels were produced by the NLI detector (circular).
2. Accuracy by in_document label on gold + synthetic only. The by_in_document table in
   outputs/gap_eval_results.md pools all tiers, so its `omitted` row is 82% circular
   (4,593 of 5,610 elements are NLI-labelled corpus items).

    python scripts/paper_detector_checks.py      # -> outputs/paper_detector_checks.md
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import load_all
from edia.gapdetect.metrics import GapMetrics

PAIRS_DIR = Path("data/benchmark/pairs")
CACHE = Path("outputs/gap_eval_scores.jsonl")
REPORT = Path("outputs/paper_detector_checks.md")
THRESHOLD = 0.55
DETECTORS = ["nli:roberta-large-mnli", "lexical", "llm", "ensemble"]


def main() -> int:
    pairs = load_all(PAIRS_DIR)
    cache = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        cache[(r["detector"], r["element_id"])] = r["present_score"]

    # --- 1. same sample (mirrors scripts/run_gap_eval.py exactly) ---
    all_elements = [(p, el) for p in pairs for el in p.elements]
    rng = random.Random(13)
    by_cell: dict = defaultdict(list)
    for p, el in all_elements:
        by_cell[(p.source.value, el.element_type.value, el.gold_gap)].append((p, el))
    per = max(1, 400 // max(1, len(by_cell)))
    picked: list = []
    for cell in by_cell.values():
        rng.shuffle(cell)
        picked.extend(cell[:per])
    sample = [x for x in picked[:400] if x[0].source.value != "qmsum_auto"]

    lines = ["# Detector checks for the paper (Table 1)", "",
             f"## Same stratified sample, gold + synthetic (n={len(sample)}, threshold {THRESHOLD})", "",
             "| detector | bal acc | present F1 |", "|---|--:|--:|"]
    for det in DETECTORS:
        m = GapMetrics()
        for p, el in sample:
            m.add(cache[(det, el.element_id)] < THRESHOLD, el.gold_gap)
        lines.append(f"| {det} | {m.balanced_accuracy:.3f} | {m.present_f1:.3f} |")

    # --- 2. accuracy by label, non-circular tiers ---
    stats: dict = defaultdict(lambda: [0, 0])
    for p in pairs:
        if p.source.value == "qmsum_auto":
            continue
        for el in p.elements:
            for det in ("nli:roberta-large-mnli", "lexical"):
                ok = (cache[(det, el.element_id)] < THRESHOLD) == el.gold_gap
                stats[(det, el.in_document.value)][0] += ok
                stats[(det, el.in_document.value)][1] += 1
    lines += ["", "## Accuracy by label, gold + synthetic only", "",
              "| label | n | NLI acc | lexical acc |", "|---|--:|--:|--:|"]
    for lab in ("omitted", "paraphrased", "verbatim", "present_unspecified"):
        n = stats[("lexical", lab)][1]
        if n:
            a, b = stats[("nli:roberta-large-mnli", lab)], stats[("lexical", lab)]
            lines.append(f"| {lab} | {n} | {a[0]/a[1]:.3f} | {b[0]/b[1]:.3f} |")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
