"""
Task 5 step 2: the human annotation pass.

This is a verification interface, not a labelling-from-scratch one. Generation
already decided which elements the document was supposed to keep (see generate.py),
so the annotator's job is to answer, per element: *does the document I am reading
actually contain this?* That is a much more reliable judgement than "list everything
missing from this document", and it is why the agreement numbers in agreement.py
mean something.

Anchoring control: the first annotator on a pair sees the generated label as a
default. Any subsequent annotator is BLIND by default -- they never see the first
annotator's or the generator's label. Double-annotating with the label visible would
inflate agreement and make the >0.6 Jaccard target meaningless.

Nothing here is automated on the annotator's behalf. The tool refuses to record a
label the annotator did not enter.

Usage:
    python -m edia.benchmark.annotate --annotator manan
    python -m edia.benchmark.annotate --annotator priya --double     # blind 2nd pass
    python -m edia.benchmark.annotate --annotator manan --pair SYN_011
    python -m edia.benchmark.annotate --status
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from .dataset import AnnotationMeta, BenchmarkPair, InDocument, load_all

PAIRS_DIR = Path("data/benchmark/pairs")

KEYMAP = {
    "o": InDocument.OMITTED,
    "v": InDocument.VERBATIM,
    "p": InDocument.PARAPHRASED,
    "y": InDocument.PRESENT_UNSPECIFIED,
}

HELP = """\
  o = omitted        the document does not contain this at all
  v = verbatim       present in near-identical wording
  p = paraphrased    present, but reworded
  y = present        present, wording relationship unclear
  ? = flag           cannot decide -- records a flag for adjudication
  s = skip pair      leave this pair unannotated
  x = reject pair    the pair is unrealistic / unusable
  q = quit           save what is done and exit
"""


def _print_pair(pair: BenchmarkPair, show_transcript: bool) -> None:
    print("\n" + "=" * 78)
    print(f"{pair.pair_id}   [{pair.source.value} / {pair.topic}]   {pair.title}")
    print("=" * 78)
    if show_transcript:
        print("\n--- DISCUSSION " + "-" * 62)
        print(pair.transcript)
    print("\n--- DOCUMENT " + "-" * 64)
    print(pair.document)
    print("-" * 78)


def annotate_pair(
    pair: BenchmarkPair, annotator: str, blind: bool, show_transcript: bool
) -> tuple[AnnotationMeta | None, str]:
    """Returns (annotation or None, action) where action is one of ok/skip/reject/quit."""
    _print_pair(pair, show_transcript)
    print(HELP)

    labels: dict[str, InDocument] = {}
    flagged: list[str] = []
    started = time.time()

    for i, el in enumerate(pair.elements, start=1):
        default = None if blind else el.in_document
        prompt_default = f" [{default.value}]" if default else ""
        print(f"\n({i}/{len(pair.elements)}) [{el.element_type.value}] {el.text}")
        while True:
            raw = input(f"  in the document?{prompt_default} > ").strip().lower()
            if raw == "" and default is not None:
                labels[el.element_id] = default
                break
            if raw in KEYMAP:
                labels[el.element_id] = KEYMAP[raw]
                break
            if raw == "?":
                flagged.append(el.element_id)
                labels[el.element_id] = el.in_document if not blind else InDocument.OMITTED
                print("    flagged for adjudication")
                break
            if raw in ("s", "x", "q"):
                action = {"s": "skip", "x": "reject", "q": "quit"}[raw]
                if action == "reject":
                    notes = input("  why is this pair unusable? > ").strip()
                    return (
                        AnnotationMeta(
                            annotator=annotator, labels=labels, flagged=flagged,
                            unrealistic=True, notes=notes,
                            minutes_spent=round((time.time() - started) / 60, 1),
                        ),
                        "reject",
                    )
                return None, action
            print("    unrecognised -- enter o / v / p / y / ? / s / x / q")

    notes = input("\n  notes on this pair (optional) > ").strip()
    return (
        AnnotationMeta(
            annotator=annotator, labels=labels, flagged=flagged, unrealistic=False,
            notes=notes, minutes_spent=round((time.time() - started) / 60, 1),
        ),
        "ok",
    )


def status(pairs: list[BenchmarkPair]) -> None:
    print(f"{'pair':<12} {'source':<10} {'elems':>5} {'gaps':>5}  annotators")
    for p in pairs:
        who = ", ".join(a.annotator for a in p.annotations) or "-"
        flag = "  LEAK-FLAGGED" if p.notes.startswith("AUTOMATIC LEAK FLAG") else ""
        print(f"{p.pair_id:<12} {p.source.value:<10} {len(p.elements):>5} "
              f"{p.gap_count:>5}  {who}{flag}")
    single = sum(len(p.annotations) == 1 for p in pairs)
    double = sum(len(p.annotations) >= 2 for p in pairs)
    print(f"\n{len(pairs)} pairs | {single} single-annotated | {double} double-annotated "
          f"| {sum(not p.annotations for p in pairs)} unannotated")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator", help="your name -- recorded with the labels")
    ap.add_argument("--pair", help="annotate one specific pair id")
    ap.add_argument("--double", action="store_true",
                    help="work through pairs that already have exactly one annotation")
    ap.add_argument("--show-transcript", action="store_true",
                    help="also print the discussion (slower, but needed for disputed elements)")
    ap.add_argument("--no-blind", action="store_true",
                    help="show existing labels on a second pass (inflates agreement -- avoid)")
    ap.add_argument("--blind", action="store_true",
                    help="force blind even on the first pass -- required for spot-checking "
                         "auto-labelled pairs, where seeing the silver label would bias the human")
    ap.add_argument("--status", action="store_true", help="print progress and exit")
    ap.add_argument("--dir", default=str(PAIRS_DIR))
    ap.add_argument("--source", help="only pairs of this source "
                    "(synthetic | qmsum | qmsum_auto)")
    args = ap.parse_args(argv)

    pairs = load_all(args.dir)
    if args.source:
        pairs = [p for p in pairs if p.source.value == args.source]
    if not pairs:
        where = f"{args.dir}" + (f" (source={args.source})" if args.source else "")
        print(f"no pairs in {where} -- generate or fold some first")
        return 1

    if args.status:
        status(pairs)
        return 0

    if not args.annotator:
        print("--annotator is required (or use --status)")
        return 1

    if args.pair:
        queue = [p for p in pairs if p.pair_id == args.pair]
    elif args.double:
        queue = [p for p in pairs if len(p.annotations) == 1]
    else:
        queue = [p for p in pairs if not p.annotations]

    queue = [p for p in queue if all(a.annotator != args.annotator for a in p.annotations)]
    if not queue:
        print("nothing to annotate for you in that selection.")
        return 0

    blind = args.blind or (args.double and not args.no_blind)
    print(f"{len(queue)} pair(s) queued for {args.annotator}"
          f"{' (BLIND)' if blind else ''}")

    for pair in queue:
        annotation, action = annotate_pair(pair, args.annotator, blind, args.show_transcript)
        if action == "quit":
            print("stopping -- annotated pairs are saved.")
            break
        if action == "skip":
            print(f"{pair.pair_id}: skipped")
            continue
        assert annotation is not None
        pair.annotations.append(annotation)
        pair.save(args.dir)
        changed = sum(
            1 for e in pair.elements
            if annotation.labels.get(e.element_id) != e.in_document
        )
        print(f"{pair.pair_id}: saved ({changed} label(s) differ from the generated label"
              f"{', PAIR REJECTED' if annotation.unrealistic else ''})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
