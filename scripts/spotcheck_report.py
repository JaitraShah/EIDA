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

# set in main(): outputs/qmsum_<folder name>_report.json
OUT = Path("outputs/qmsum_spotcheck_report.json")

# Annotator names that are NOT human. The spotcheck pairs carry a `llm-review`
# pass whose own note says "Not a substitute for a human pass" -- if it is allowed
# to occupy the first slot, "auto vs human" silently becomes auto-vs-model and the
# whole point of Phase 1.5 (a non-circular check on the silver labels) is lost.
MACHINE_ANNOTATORS = {"llm-review", "auto", "model"}


def _human_passes(pair, machine: set[str]) -> list:
    return [a for a in pair.annotations if a.annotator.lower() not in machine]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="data/benchmark/spotcheck")
    ap.add_argument("--machine-annotator", action="append", default=[],
                    help="extra annotator name to treat as non-human (repeatable)")
    ap.add_argument("--allow-machine", action="store_true",
                    help="score machine annotations as if human -- for inspecting the "
                         "llm-review pass only; NEVER for a reported number")
    args = ap.parse_args(argv)

    machine = set() if args.allow_machine else (
        MACHINE_ANNOTATORS | {m.lower() for m in args.machine_annotator}
    )

    global OUT
    OUT = Path(f"outputs/qmsum_{Path(args.dir).name}_report.json")

    all_pairs = [p for p in load_all(args.dir) if p.annotations]
    pairs = [p for p in all_pairs if _human_passes(p, machine)]
    if not pairs:
        skipped = sorted({a.annotator for p in all_pairs for a in p.annotations})
        raise SystemExit(
            f"no HUMAN-annotated pairs in {args.dir}.\n"
            f"Found only machine annotations from: {', '.join(skipped) or '(none)'}.\n\n"
            f"The spotcheck pairs already carry a llm-review pass, so a human is the\n"
            f"SECOND annotator on each pair. Run:\n"
            f"  python -m edia.benchmark.annotate --dir {args.dir} "
            f"--annotator <you> --double\n"
        )
    if len(pairs) < len(all_pairs):
        print(f"note: {len(all_pairs) - len(pairs)} pair(s) have no human pass yet; "
              f"scoring the {len(pairs)} that do.")

    auto_vs_human = GapMetrics()
    disagreements = []
    hh_auto: list[bool] = []          # pooled gap flags for human-vs-human
    hh_a: list[bool] = []
    hh_b: list[bool] = []
    n_double = 0

    human_names: set[str] = set()
    for p in pairs:
        humans = _human_passes(p, machine)
        human = humans[0].labels
        human_names.add(humans[0].annotator)
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
        if len(humans) >= 2:
            n_double += 1
            a, b = humans[0].labels, humans[1].labels
            for el in p.elements:
                if el.element_id in a and el.element_id in b:
                    hh_a.append(a[el.element_id] is InDocument.OMITTED)
                    hh_b.append(b[el.element_id] is InDocument.OMITTED)

    result = {
        "pairs": len(pairs),
        "human_annotators": sorted(human_names),
        "machine_annotators_excluded": sorted(machine),
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
    print(f"human annotator(s): {', '.join(result['human_annotators'])}"
          f"   |  excluded as machine: {', '.join(result['machine_annotators_excluded']) or 'none'}")
    print(f"pairs scored: {len(pairs)}  |  double-annotated: {n_double}\n")
    print(f"auto vs human (gap class), n={o['n']}:")
    print(f"  gap class     : P {o['precision']}  R {o['recall']}  F1 {o['f1']}")
    print(f"  present class : P {o['present_precision']}  R {o['present_recall']}  "
          f"F1 {o['present_f1']}")
    print(f"  balanced accuracy {o['balanced_accuracy']}  (all-gap detector = 0.5)")
    print(f"  confusion {o['confusion']}")
    if "human_vs_human" in result:
        h = result["human_vs_human"]
        print(f"human vs human: Jaccard {h['pooled_jaccard']}  kappa {h['pooled_cohens_kappa']} "
              f"(n={h['elements']})")
    print(f"\n{len(disagreements)} element-level disagreements -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
