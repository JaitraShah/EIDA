"""
Score the human spot-check of the QMSUM_AUTO silver labels.

Treats each element's auto label (`element.in_document`) as annotator "auto" and
the human `AnnotationMeta.labels` as annotator "human", then reports, on the gap
class (OMITTED vs not):

  * auto-vs-human: precision / recall / F1 / confusion  -- how good the silver
    labels actually are, on the sampled slice
  * human-vs-human (when a pair has 2 human passes): pooled Jaccard + Cohen's
    kappa via edia.benchmark.agreement -- the reliability ceiling

If a pair carries >= 2 human annotations the first two are used for human-vs-human;
auto-vs-human always uses the first human pass.

    python scripts/spotcheck_report.py --dir data/benchmark/spotcheck
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.agreement import cohens_kappa, jaccard
from edia.benchmark.dataset import InDocument, load_all
from edia.gapdetect.metrics import GapMetrics

OUT = Path("outputs/qmsum_spotcheck_report.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="data/benchmark/spotcheck")
    args = ap.parse_args(argv)

    pairs = [p for p in load_all(args.dir) if p.annotations]
    if not pairs:
        raise SystemExit(f"no annotated pairs in {args.dir} -- run edia.benchmark.annotate first")

    auto_vs_human = GapMetrics()
    disagreements = []
    hh_auto: list[bool] = []          # pooled gap flags for human-vs-human
    hh_a: list[bool] = []
    hh_b: list[bool] = []
    n_double = 0

    for p in pairs:
        human = p.annotations[0].labels
        for el in p.elements:
            if el.element_id not in human:
                continue
            auto_gap = el.in_document is InDocument.OMITTED
            human_gap = human[el.element_id] is InDocument.OMITTED
            auto_vs_human.add(predicted_gap=auto_gap, actual_gap=human_gap)
            if auto_gap != human_gap:
                disagreements.append({
                    "pair_id": p.pair_id, "element_id": el.element_id,
                    "type": el.element_type.value, "text": el.text,
                    "auto": el.in_document.value,
                    "human": human[el.element_id].value,
                })
        if len(p.annotations) >= 2:
            n_double += 1
            a, b = p.annotations[0].labels, p.annotations[1].labels
            for el in p.elements:
                if el.element_id in a and el.element_id in b:
                    hh_a.append(a[el.element_id] is InDocument.OMITTED)
                    hh_b.append(b[el.element_id] is InDocument.OMITTED)

    result = {
        "pairs": len(pairs),
        "double_annotated_pairs": n_double,
        "auto_vs_human_gap_class": auto_vs_human.to_dict(),
        "disagreements": disagreements,
    }
    if hh_a:
        ga = {i for i, v in enumerate(hh_a) if v}
        gb = {i for i, v in enumerate(hh_b) if v}
        result["human_vs_human"] = {
            "elements": len(hh_a),
            "pooled_jaccard": round(jaccard(ga, gb), 3),
            "pooled_cohens_kappa": round(cohens_kappa(hh_a, hh_b), 3),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    o = result["auto_vs_human_gap_class"]
    print(f"auto vs human (gap class), n={o['n']}:")
    print(f"  precision {o['precision']}  recall {o['recall']}  F1 {o['f1']}  acc {o['accuracy']}")
    print(f"  confusion {o['confusion']}")
    if "human_vs_human" in result:
        h = result["human_vs_human"]
        print(f"human vs human: Jaccard {h['pooled_jaccard']}  kappa {h['pooled_cohens_kappa']} "
              f"(n={h['elements']})")
    print(f"\n{len(disagreements)} element-level disagreements -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
