"""
Attach a pre-computed annotation pass to the spot-check pairs.

Used to record an annotator who worked from a flat file rather than the
interactive `annotate.py` TUI -- e.g. an LLM-assisted review, or a reviewer who
marked up a printout. `--disagreements FILE` is a JSON list of element_ids the
annotator judged **present** (PRESENT_UNSPECIFIED) where the stored label is
OMITTED; every other element takes the stored label. `--annotator` names the pass.

This does NOT replace the human blind pass -- it records one opinion in the same
structure so `spotcheck_report.py` can score it.

    python scripts/record_annotation.py --annotator llm-review \
        --disagreements outputs/llm_spotcheck_disagreements.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import AnnotationMeta, InDocument, load_all


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="data/benchmark/spotcheck")
    ap.add_argument("--annotator", required=True)
    ap.add_argument("--disagreements", required=True,
                    help="JSON list of element_ids judged present (vs a stored OMITTED)")
    ap.add_argument("--notes", default="")
    args = ap.parse_args(argv)

    present_ids = set(json.loads(Path(args.disagreements).read_text(encoding="utf-8")))
    pairs = load_all(args.dir)
    if not pairs:
        raise SystemExit(f"no pairs in {args.dir}")

    touched = flipped = 0
    for p in pairs:
        if any(a.annotator == args.annotator for a in p.annotations):
            continue
        labels: dict[str, InDocument] = {}
        for el in p.elements:
            if el.element_id in present_ids and el.in_document is InDocument.OMITTED:
                labels[el.element_id] = InDocument.PRESENT_UNSPECIFIED
                flipped += 1
            else:
                labels[el.element_id] = el.in_document
        p.annotations.append(AnnotationMeta(
            annotator=args.annotator, labels=labels,
            notes=args.notes or "recorded via scripts/record_annotation.py",
        ))
        p.save(args.dir)
        touched += 1

    print(f"annotated {touched} pairs as {args.annotator!r}; "
          f"{flipped} element(s) flipped OMITTED -> present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
