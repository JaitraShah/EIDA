"""
Ingest the full QMSum release (all 3 domains, all splits) into `BenchmarkPair`s
with automatically-derived gap-detection labels.

QMSum ships, per meeting: the raw multi-speaker transcript (`meeting_transcripts`),
a one-paragraph `general_query_list` answer, and ~6 `specific_query_list` answers
(a few sentences each about one sub-topic, with transcript span pointers). This
module treats:

  * concatenated `general_query_list` answers  -> the "filed document" proxy
    (identical to what `scripts/prepare_qmsum.py` does for the 5 gold pairs)
  * sentences of each `specific_query_list` answer  -> reasoning elements
    (`edia.benchmark.decompose`)
  * "is this element entailed by the document?"  -> the in_document label,
    answered by an NLI detector in `edia.gapdetect` (filled in by
    `scripts/build_qmsum_corpus.py`, not here)

The result is `PairSource.QMSUM_AUTO`. These labels are **silver, not gold**: they
are produced by a model. Scoring that same model against them measures
self-consistency, not accuracy -- real accuracy comes only from the 5 hand-gold
pairs and the human spot-check. Every report built on this data must say so.

`decisions` is left empty on these pairs, so they do not feed extraction-
completeness scoring (which needs hand-built `DecisionRecord`s). They feed gap
detection and hallucination scoring, both of which need only `elements` / records.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..ingestion.parsers.json_parser import turns_to_text
from .dataset import BenchmarkPair, ElementLabel, InDocument, PairSource
from .decompose import RawElement

RAW_ROOT = Path("data/qmsum/raw")
PAIRS_DIR = Path("data/benchmark/pairs")

DOMAIN_CODE = {"Academic": "ACA", "Committee": "CMT", "Product": "PRD"}
SPLIT_CODE = {"train": "TR", "val": "VA", "test": "TE"}
DOMAINS = tuple(DOMAIN_CODE)
SPLITS = tuple(SPLIT_CODE)

# The 5 hand-validated Task 1 pairs are Product/test rows at these 0-based indices
# (scripts/prepare_qmsum.py::PAIR_INDEX). They are emitted as QSUM_001..005 by
# fold_qmsum, with real hand labels, so the corpus pass skips them by default to
# avoid a silver duplicate of a gold pair.
GOLD_PRODUCT_TEST = {5: "QSUM_001", 7: "QSUM_002", 9: "QSUM_003",
                     10: "QSUM_004", 12: "QSUM_005"}

# A general summary shorter than this makes almost every element look like a gap
# (there is nothing for NLI to entail against). Such meetings are excluded and
# counted, not silently mislabelled.
MIN_DOCUMENT_WORDS = 40


def meeting_id(domain: str, split: str, idx: int) -> str:
    return f"QMS_{DOMAIN_CODE[domain]}_{SPLIT_CODE[split]}_{idx:03d}"


def general_summary(row: dict) -> str:
    """The 'filed document' proxy: every general_query_list answer, joined.

    Factored out so this and scripts/prepare_qmsum.py produce byte-identical text.
    """
    return "\n\n".join(
        q["answer"] for q in row.get("general_query_list", []) if q.get("answer")
    )


@dataclass
class QmsumMeeting:
    meeting_id: str
    domain: str
    split: str
    source_index: int
    turns: list[dict]
    general_query_list: list[dict]
    specific_query_list: list[dict]
    topic_list: list[dict] = field(default_factory=list)
    gold_pair_id: str | None = None      # set when this row IS one of the 5 gold

    @property
    def transcript(self) -> str:
        return turns_to_text(self.turns)[0]

    @property
    def document(self) -> str:
        return general_summary({"general_query_list": self.general_query_list})

    @property
    def document_word_count(self) -> int:
        return len(self.document.split())


def _split_path(root: Path, domain: str, split: str) -> Path:
    return root / domain / f"{split}.jsonl"


def iter_meetings(
    root: str | Path = RAW_ROOT,
    domains: tuple[str, ...] = DOMAINS,
    splits: tuple[str, ...] = SPLITS,
    *,
    include_gold: bool = False,
) -> Iterator[QmsumMeeting]:
    """Yield every QMSum meeting in deterministic (domain, split, line) order.

    Iterates the per-domain jsonl (not data/ALL) so each of the 232 meetings is
    seen once with an unambiguous domain. The 5 gold Product/test rows are skipped
    unless include_gold=True.
    """
    root = Path(root)
    paths = [(_split_path(root, d, s), d, s) for d in domains for s in splits]
    if not any(p.exists() for p, _, _ in paths):
        raise FileNotFoundError(
            f"no QMSum jsonl under {root}/ -- stage the release as "
            f"{root}/<Academic|Committee|Product>/<train|val|test>.jsonl "
            f"(see the plan's Phase 1 / README)"
        )
    for path, domain, split in paths:
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                for idx, line in enumerate(fh):
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    gold = (
                        GOLD_PRODUCT_TEST.get(idx)
                        if (domain == "Product" and split == "test")
                        else None
                    )
                    if gold and not include_gold:
                        continue
                    yield QmsumMeeting(
                        meeting_id=meeting_id(domain, split, idx),
                        domain=domain,
                        split=split,
                        source_index=idx,
                        turns=row.get("meeting_transcripts", []),
                        general_query_list=row.get("general_query_list", []),
                        specific_query_list=row.get("specific_query_list", []),
                        topic_list=row.get("topic_list", []),
                        gold_pair_id=gold,
                    )


def build_pair(
    meeting: QmsumMeeting,
    labelled: list[tuple[RawElement, InDocument, float]],
    *,
    label_provenance: str,
    detector_notes: str = "",
) -> BenchmarkPair:
    """Assemble a QMSUM_AUTO BenchmarkPair from decomposed + labelled elements.

    `labelled` is (element, in_document, detector_score) triples. The score is
    stashed in `notes` as JSON so the calibration and spot-check passes can audit
    the operating point without a second detector run.
    """
    elements: list[ElementLabel] = []
    scores: list[dict] = []
    for i, (raw, label, score) in enumerate(labelled, start=1):
        eid = f"{meeting.meeting_id}_e{i:02d}"
        elements.append(
            ElementLabel(
                element_id=eid,
                element_type=raw.element_type,
                text=raw.text,
                in_document=label,
                decision_id=f"{meeting.meeting_id}_q{raw.query_index:02d}",
            )
        )
        scores.append({"element_id": eid, "entail_score": round(score, 4),
                       "query_index": raw.query_index})

    notes = (
        f"QMSUM_AUTO -- domain={meeting.domain}, split={meeting.split}, "
        f"source_index={meeting.source_index}. Document = concatenated QMSum "
        f"general_query_list answer(s); elements = sentences of specific_query_list "
        f"answers. in_document labels are SILVER: produced by {label_provenance}. "
        f"Not for extraction-completeness scoring (decisions=[]).\n"
        + (detector_notes + "\n" if detector_notes else "")
        + json.dumps({"detector_scores": scores}, ensure_ascii=False)
    )

    return BenchmarkPair(
        pair_id=meeting.meeting_id,
        source=PairSource.QMSUM_AUTO,
        topic=f"qmsum_{meeting.domain.lower()}",
        title=f"QMSum {meeting.domain} meeting {meeting.source_index} ({meeting.split})",
        transcript=meeting.transcript,
        document=meeting.document,
        decisions=[],
        elements=elements,
        generation=None,
        label_provenance=label_provenance,
        notes=notes,
    )


def corpus_stats(root: str | Path = RAW_ROOT) -> dict:
    by_domain: dict[str, int] = {}
    by_split: dict[str, int] = {}
    short_docs: list[str] = []
    total = 0
    total_specific = 0
    for m in iter_meetings(root):
        total += 1
        by_domain[m.domain] = by_domain.get(m.domain, 0) + 1
        by_split[m.split] = by_split.get(m.split, 0) + 1
        total_specific += len(m.specific_query_list)
        if m.document_word_count < MIN_DOCUMENT_WORDS:
            short_docs.append(m.meeting_id)
    return {
        "meetings": total,
        "by_domain": by_domain,
        "by_split": by_split,
        "specific_query_answers": total_specific,
        "avg_specific_per_meeting": round(total_specific / total, 1) if total else 0,
        "short_document_meetings_excluded": len(short_docs),
        "short_document_ids": short_docs,
        "gold_meetings_held_out": list(GOLD_PRODUCT_TEST.values()),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(RAW_ROOT))
    ap.add_argument("--stats", action="store_true", help="print corpus stats and exit")
    args = ap.parse_args(argv)

    if args.stats:
        print(json.dumps(corpus_stats(args.root), indent=2))
        return 0

    n = sum(1 for _ in iter_meetings(args.root))
    print(f"{n} QMSum meetings iterable under {args.root} "
          f"(run scripts/build_qmsum_corpus.py to label and write pairs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
