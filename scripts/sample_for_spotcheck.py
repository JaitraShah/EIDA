"""
Draw a stratified sample of auto-labelled pairs for the human spot-check that
validates the QMSUM_AUTO silver labels.

Pairs are copied (not moved) into data/benchmark/spotcheck/ so the annotator runs:

    python -m edia.benchmark.annotate --dir data/benchmark/spotcheck --annotator <you> --blind
    python -m edia.benchmark.annotate --dir data/benchmark/spotcheck --annotator <other> --double
    python scripts/spotcheck_report.py

Stratifies across domain and (auto) gap-rate band so the sample is not dominated by
one domain or by all-gap meetings.

    python scripts/sample_for_spotcheck.py --pairs 50 --target-elements 350
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import load_all

PAIRS_DIR = Path("data/benchmark/pairs")
SPOTCHECK_DIR = Path("data/benchmark/spotcheck")


def _band(gap_rate: float) -> str:
    if gap_rate < 0.4:
        return "low_gap"
    if gap_rate < 0.7:
        return "mid_gap"
    return "high_gap"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(PAIRS_DIR))
    ap.add_argument("--out", default=str(SPOTCHECK_DIR))
    ap.add_argument("--pairs", type=int, default=50, help="max pairs to sample")
    ap.add_argument("--target-elements", type=int, default=350,
                    help="stop once the sample reaches ~this many elements")
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--source", default="qmsum_auto")
    args = ap.parse_args(argv)

    pairs = [p for p in load_all(args.dir) if p.source.value == args.source]
    if not pairs:
        raise SystemExit(f"no {args.source} pairs in {args.dir} -- build the corpus first")

    strata: dict[tuple[str, str], list] = defaultdict(list)
    for p in pairs:
        domain = (p.topic or "").split("_", 1)[-1]
        rate = p.gap_count / len(p.elements) if p.elements else 0.0
        strata[(domain, _band(rate))].append(p)

    rng = random.Random(args.seed)
    for v in strata.values():
        rng.shuffle(v)

    # round-robin across strata until pair/element budget is hit
    picked: list = []
    elems = 0
    keys = sorted(strata)
    idx = {k: 0 for k in keys}
    while len(picked) < args.pairs and elems < args.target_elements:
        progressed = False
        for k in keys:
            if idx[k] < len(strata[k]):
                p = strata[k][idx[k]]
                idx[k] += 1
                picked.append(p)
                elems += len(p.elements)
                progressed = True
                if len(picked) >= args.pairs or elems >= args.target_elements:
                    break
        if not progressed:
            break

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for p in picked:
        shutil.copy2(Path(args.dir) / f"{p.pair_id}.json", out / f"{p.pair_id}.json")

    by_domain: dict[str, int] = defaultdict(int)
    for p in picked:
        by_domain[(p.topic or "").split("_", 1)[-1]] += 1
    print(f"sampled {len(picked)} pairs / {elems} elements -> {out}")
    print(f"by domain: {dict(by_domain)}")
    print(f"\nnext:\n  python -m edia.benchmark.annotate --dir {out} --annotator <you> --blind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
