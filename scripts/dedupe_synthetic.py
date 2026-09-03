"""
Flag near-duplicate synthetic pairs.

2000 mistral-written meetings on ~120 topics will contain some that are the same
decision in different words. This embeds each pair's decision + element texts with
a sentence-transformer and flags any pair whose cosine similarity to an
already-accepted pair exceeds --threshold. Flagged pairs are recorded in
data/benchmark/manifest.jsonl (status=near_duplicate) and listed in
outputs/synthetic_near_duplicates.json -- they are NOT deleted; regenerate them
with `generate_synthetic.py --only <id> --force` or drop them from an eval with a
filter.

    python scripts/dedupe_synthetic.py --threshold 0.9
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import load_all
from edia.benchmark.generate import MANIFEST

OUT = Path("outputs/synthetic_near_duplicates.json")


def _pair_text(p) -> str:
    parts = [d.decision for d in p.decisions] + [e.text for e in p.elements]
    return " ".join(t for t in parts if t)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="data/benchmark/pairs")
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    args = ap.parse_args(argv)

    from sentence_transformers import SentenceTransformer, util

    pairs = [p for p in load_all(args.dir) if p.source.value == "synthetic"]
    if not pairs:
        raise SystemExit(f"no synthetic pairs in {args.dir}")
    pairs.sort(key=lambda p: p.pair_id)

    model = SentenceTransformer(args.model)
    emb = model.encode([_pair_text(p) for p in pairs], convert_to_tensor=True,
                       show_progress_bar=True, normalize_embeddings=True)
    sim = util.cos_sim(emb, emb)

    flagged: list[dict] = []
    kept: list[int] = []
    for i in range(len(pairs)):
        dup_of = None
        for j in kept:
            if float(sim[i][j]) >= args.threshold:
                dup_of = j
                break
        if dup_of is None:
            kept.append(i)
        else:
            flagged.append({
                "pair_id": pairs[i].pair_id,
                "duplicate_of": pairs[dup_of].pair_id,
                "cosine": round(float(sim[i][dup_of]), 4),
                "topic": pairs[i].topic,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"threshold": args.threshold, "model": args.model,
         "synthetic_pairs": len(pairs), "near_duplicates": len(flagged),
         "flagged": flagged}, indent=2, ensure_ascii=False), encoding="utf-8")

    if flagged:
        with MANIFEST.open("a", encoding="utf-8") as fh:
            for f in flagged:
                fh.write(json.dumps({"pair_id": f["pair_id"], "status": "near_duplicate",
                                     "duplicate_of": f["duplicate_of"],
                                     "cosine": f["cosine"]}, ensure_ascii=False) + "\n")

    print(f"{len(pairs)} synthetic pairs -> {len(flagged)} near-duplicates "
          f"(cosine >= {args.threshold}) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
