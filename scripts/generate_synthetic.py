"""
Synthetic-pair generation runner, resumable. The edia_db benchmark is LOCKED at 139
synthetic pairs: do not regenerate.

Every finished pair is written to data/benchmark/pairs/ and recorded in
data/benchmark/manifest.json before the next one starts, so this can be stopped
(ctrl-C, closed laptop, ended session) and restarted with the same command -- it
picks up where it left off. Nothing is regenerated unless --force is passed.

    python scripts/generate_synthetic.py                 # generate everything missing
    python scripts/generate_synthetic.py --limit 5       # a batch at a time
    python scripts/generate_synthetic.py --only SYN_034 --force
    python scripts/generate_synthetic.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import dataset_stats, load_all
from edia.benchmark.generate import MANIFEST, PAIRS_DIR, generate_all, load_manifest
from edia.benchmark.topics import pair_plan
from edia.extraction.llm_client import DEFAULT_MODEL, OllamaClient, OllamaUnavailable


def print_status() -> None:
    plan = pair_plan()
    manifest = load_manifest()
    on_disk = {p.stem for p in PAIRS_DIR.glob("SYN_*.json")} if PAIRS_DIR.exists() else set()
    failed = [pid for pid, row in manifest.get("pairs", {}).items()
              if row.get("status") == "failed"]
    flagged = [pid for pid, row in manifest.get("pairs", {}).items()
               if row.get("status") == "flagged_leak"]

    print(f"planned    : {len(plan)}")
    print(f"generated  : {len(on_disk)}")
    print(f"remaining  : {len(plan) - len(on_disk)}")
    print(f"leak-flagged (need human re-label or regeneration): {len(flagged)}")
    if flagged:
        print("   " + ", ".join(sorted(flagged)))
    if failed:
        print(f"failed     : {len(failed)} -> {', '.join(sorted(failed))}")

    pairs = load_all(PAIRS_DIR)
    if pairs:
        print("\ndataset so far:")
        print(json.dumps(dataset_stats(pairs), indent=2))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, help="generate at most N pairs this run")
    ap.add_argument("--only", help="one pair id, e.g. SYN_0007_012")
    ap.add_argument("--shard", help="k/N -- generate only plan positions where i %% N == k "
                                    "(run N of these in parallel across GPUs)")
    ap.add_argument("--no-jitter", action="store_true",
                    help="fix temperature at 0.8 instead of per-pair jitter")
    ap.add_argument("--force", action="store_true", help="regenerate even if it exists")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    if args.status:
        print_status()
        return 0

    try:
        OllamaClient(model=args.model).ensure_available()
    except OllamaUnavailable as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    generate_all(
        model=args.model, limit=args.limit, only=args.only, force=args.force,
        shard=args.shard, jitter=not args.no_jitter,
    )
    print(f"\nmanifest: {MANIFEST}")
    print_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
