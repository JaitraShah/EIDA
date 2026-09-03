"""
Re-run only the element_type classifier over the built QMSUM_AUTO pairs.

Decomposition is deterministic and unchanged, so the sentence sequence per pair is
identical -- this rewrites `element_type` in place and leaves `in_document` labels,
element ids and detector scores untouched. Use after tuning the cue rules in
`edia.benchmark.decompose`; it is pure regex, no model, seconds not hours.

Also reports **cue coverage**: the fraction of elements whose type came from an
actual cue match rather than the RATIONALE fallback. That number is the honest
health check on the by-element-type breakdown for this tier.

    python scripts/retype_qmsum_elements.py --dry-run
    python scripts/retype_qmsum_elements.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import BenchmarkPair
from edia.benchmark.decompose import SentenceDecomposer, classify_with_cue
from edia.benchmark.qmsum_corpus import PAIRS_DIR, RAW_ROOT, iter_meetings

OUT = Path("outputs/qmsum_element_type_coverage.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(RAW_ROOT))
    ap.add_argument("--dir", default=str(PAIRS_DIR))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    pairs_dir = Path(args.dir)
    dec = SentenceDecomposer()
    old_c, new_c = Counter(), Counter()
    cue_hits = total = changed = touched = skipped = 0

    for m in iter_meetings(args.root):
        path = pairs_dir / f"{m.meeting_id}.json"
        if not path.exists():
            continue
        pair = BenchmarkPair.load(path)
        raws = dec.decompose(m.specific_query_list)
        if len(raws) != len(pair.elements):
            print(f"{m.meeting_id}: SKIP -- {len(raws)} decomposed vs "
                  f"{len(pair.elements)} stored (decomposition drifted)")
            skipped += 1
            continue

        pair_changed = False
        # rebuild the is_first_in_answer flag the same way SentenceDecomposer does
        seen_q: set[int] = set()
        for raw, el in zip(raws, pair.elements):
            first = raw.query_index not in seen_q
            seen_q.add(raw.query_index)
            etype, cue = classify_with_cue(raw.text, is_first_in_answer=first)
            old_c[el.element_type.value] += 1
            new_c[etype.value] += 1
            cue_hits += cue
            total += 1
            if el.element_type is not etype:
                el.element_type = etype
                changed += 1
                pair_changed = True
        if pair_changed and not args.dry_run:
            pair.save(pairs_dir)
        touched += 1

    coverage = cue_hits / total if total else 0.0
    result = {
        "pairs": touched, "skipped_pairs": skipped, "elements": total,
        "cue_matched": cue_hits, "cue_coverage": round(coverage, 3),
        "types_changed": changed,
        "old_distribution": dict(old_c.most_common()),
        "new_distribution": dict(new_c.most_common()),
        "note": (
            f"Only {coverage:.0%} of QMSum specific-query sentences carry a "
            "reasoning cue. QMSum answers are narrative meeting summaries, so most "
            "sentences genuinely are not an alternative/dissent/condition; they fall "
            "to RATIONALE, which on this tier means 'unclassified narrative', not "
            "'a stated reason'. Read the by-element-type breakdown for qmsum_auto as "
            "indicative only -- the synthetic tier is where types are trustworthy."
        ),
    }
    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{touched} pairs, {total} elements, {changed} type(s) changed"
          f"{' (DRY RUN)' if args.dry_run else ''}")
    print(f"cue coverage: {cue_hits}/{total} = {coverage:.1%}\n")
    print(f"{'type':12s} {'old':>6} {'new':>6}")
    for t in ("decision", "alternative", "rationale", "condition",
              "dissent", "owner", "approver"):
        print(f"{t:12s} {old_c.get(t, 0):6d} {new_c.get(t, 0):6d}")
    if not args.dry_run:
        print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
