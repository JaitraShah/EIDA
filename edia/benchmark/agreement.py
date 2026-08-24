"""
Task 5 step 3: inter-annotator agreement on the double-annotated pairs.

The brief sets a Jaccard > 0.6 target on the gap sets, so Jaccard is what is
reported first. Cohen's kappa is reported alongside it, because Jaccard on gap sets
has a known blind spot for this dataset: our documents drop most reasoning, so gaps
are the majority class, and two annotators who both mark nearly everything as a gap
score a high Jaccard without actually agreeing on anything hard. Kappa corrects for
that chance agreement. If Jaccard clears 0.6 but kappa is near zero, the target has
been met on paper and not in substance -- say so rather than reporting the Jaccard
alone.

Also reported: agreement on the finer 4-way label (omitted / verbatim / paraphrased /
present), since the verbatim-vs-paraphrased distinction is the one Task 2 showed
matters, and it is also the one humans are most likely to split on.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from .dataset import BenchmarkPair, InDocument, load_all

PAIRS_DIR = Path("data/benchmark/pairs")
JACCARD_TARGET = 0.6


@dataclass
class PairAgreement:
    pair_id: str
    annotator_a: str
    annotator_b: str
    elements: int
    jaccard: float
    kappa: float
    binary_agreement: float
    fourway_agreement: float
    disagreements: list[dict] = field(default_factory=list)


def jaccard(a: set[str], b: set[str]) -> float:
    """Empty-vs-empty is perfect agreement, not a divide-by-zero."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def cohens_kappa(labels_a: list[bool], labels_b: list[bool]) -> float:
    n = len(labels_a)
    if n == 0:
        return 0.0
    observed = sum(x == y for x, y in zip(labels_a, labels_b)) / n
    pa_true, pb_true = sum(labels_a) / n, sum(labels_b) / n
    expected = pa_true * pb_true + (1 - pa_true) * (1 - pb_true)
    if expected >= 1.0:
        # both annotators used a single class throughout -- kappa is undefined,
        # report 1.0 only if they also agreed, else 0.0
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1 - expected)


def compare(pair: BenchmarkPair, i: int = 0, j: int = 1) -> PairAgreement | None:
    if len(pair.annotations) < 2:
        return None
    a, b = pair.annotations[i], pair.annotations[j]

    shared = [
        e for e in pair.elements
        if e.element_id in a.labels and e.element_id in b.labels
    ]
    if not shared:
        return None

    gaps_a = {e.element_id for e in shared if a.labels[e.element_id] is InDocument.OMITTED}
    gaps_b = {e.element_id for e in shared if b.labels[e.element_id] is InDocument.OMITTED}

    bin_a = [e.element_id in gaps_a for e in shared]
    bin_b = [e.element_id in gaps_b for e in shared]

    disagreements = [
        {
            "element_id": e.element_id,
            "type": e.element_type.value,
            "text": e.text,
            a.annotator: a.labels[e.element_id].value,
            b.annotator: b.labels[e.element_id].value,
            "generated": e.in_document.value,
        }
        for e in shared
        if a.labels[e.element_id] is not b.labels[e.element_id]
    ]

    return PairAgreement(
        pair_id=pair.pair_id,
        annotator_a=a.annotator,
        annotator_b=b.annotator,
        elements=len(shared),
        jaccard=jaccard(gaps_a, gaps_b),
        kappa=cohens_kappa(bin_a, bin_b),
        binary_agreement=sum(x == y for x, y in zip(bin_a, bin_b)) / len(shared),
        fourway_agreement=sum(
            a.labels[e.element_id] is b.labels[e.element_id] for e in shared
        ) / len(shared),
        disagreements=disagreements,
    )


def report(pairs: list[BenchmarkPair]) -> dict:
    results = [r for r in (compare(p) for p in pairs) if r]
    if not results:
        return {"double_annotated_pairs": 0, "note": "no pair has two annotations yet"}

    # Pooled = one calculation over every element from every double-annotated pair,
    # which is the number to quote. The per-pair mean is reported too because a single
    # bad pair is easier to spot there.
    pooled_a: set[str] = set()
    pooled_b: set[str] = set()
    bin_a: list[bool] = []
    bin_b: list[bool] = []
    for pair in pairs:
        if len(pair.annotations) < 2:
            continue
        a, b = pair.annotations[0], pair.annotations[1]
        for e in pair.elements:
            if e.element_id not in a.labels or e.element_id not in b.labels:
                continue
            ga = a.labels[e.element_id] is InDocument.OMITTED
            gb = b.labels[e.element_id] is InDocument.OMITTED
            if ga:
                pooled_a.add(e.element_id)
            if gb:
                pooled_b.add(e.element_id)
            bin_a.append(ga)
            bin_b.append(gb)

    pooled_jaccard = jaccard(pooled_a, pooled_b)
    pooled_kappa = cohens_kappa(bin_a, bin_b)
    gap_rate = (sum(bin_a) + sum(bin_b)) / (2 * len(bin_a)) if bin_a else 0.0

    return {
        "double_annotated_pairs": len(results),
        "elements_compared": len(bin_a),
        "gap_base_rate": round(gap_rate, 3),
        "pooled_jaccard": round(pooled_jaccard, 3),
        "pooled_cohens_kappa": round(pooled_kappa, 3),
        "mean_pair_jaccard": round(sum(r.jaccard for r in results) / len(results), 3),
        "mean_binary_agreement": round(
            sum(r.binary_agreement for r in results) / len(results), 3
        ),
        "mean_fourway_agreement": round(
            sum(r.fourway_agreement for r in results) / len(results), 3
        ),
        "target": f"jaccard > {JACCARD_TARGET}",
        "target_met": pooled_jaccard > JACCARD_TARGET,
        "kappa_caveat": (
            "Jaccard clears the target but kappa is weak (<0.4): with a "
            f"{gap_rate:.0%} gap base rate, most of that Jaccard is chance agreement. "
            "Do not report the Jaccard on its own."
            if pooled_jaccard > JACCARD_TARGET and pooled_kappa < 0.4
            else "kappa is consistent with the Jaccard; no base-rate inflation detected."
        ),
        "per_pair": [
            {
                "pair_id": r.pair_id,
                "annotators": [r.annotator_a, r.annotator_b],
                "elements": r.elements,
                "jaccard": round(r.jaccard, 3),
                "kappa": round(r.kappa, 3),
                "binary_agreement": round(r.binary_agreement, 3),
                "fourway_agreement": round(r.fourway_agreement, 3),
                "disagreements": r.disagreements,
            }
            for r in results
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(PAIRS_DIR))
    ap.add_argument("--out", default="outputs/task5_agreement.json")
    args = ap.parse_args(argv)

    pairs = load_all(args.dir)
    result = report(pairs)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if result.get("double_annotated_pairs"):
        print(f"double-annotated pairs : {result['double_annotated_pairs']}")
        print(f"elements compared      : {result['elements_compared']}")
        print(f"gap base rate          : {result['gap_base_rate']:.0%}")
        print(f"pooled Jaccard         : {result['pooled_jaccard']}  "
              f"(target > {JACCARD_TARGET}) -> "
              f"{'MET' if result['target_met'] else 'NOT MET'}")
        print(f"pooled Cohen's kappa   : {result['pooled_cohens_kappa']}")
        print(f"4-way label agreement  : {result['mean_fourway_agreement']}")
        print(f"\n{result['kappa_caveat']}")
    else:
        print(result.get("note", "nothing to compare"))
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
