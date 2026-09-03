"""
Cut the five Task 1 meetings out of the QMSum Product test split into standalone files.

Meeting -> file-index mapping. Task 1 refers to meetings by number ("Meeting 5",
"Meeting 7", ...); those are 0-based line indices into
data/Product/jsonl/test.jsonl. Verified by content, not assumed:

    idx  5  -> QSUM_001  three casing shapes (uncurved / single / double curved)
    idx  7  -> QSUM_002  "What about Kryptonite?"
    idx  9  -> QSUM_003  "basic buttons with a self-intuitive screen menu",
                         "Silver lightweight plastic was temporarily decided"
    idx 10  -> QSUM_004  Google / fancy / intelligent controller
    idx 12  -> QSUM_005  "the chip can be simple, regular or advanced"

Writes, per meeting:
  data/qmsum/<PAIR>_transcript.json  -- QMSum-shaped, ingests through ingestion/json_parser
  data/qmsum/<PAIR>_document.txt     -- the general summary, i.e. the "document" proxy
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.qmsum_corpus import general_summary

SRC = Path("data/qmsum/product_test.jsonl")
OUT = Path("data/qmsum")

# pair_id -> (file index, expected marker string that must appear in the transcript)
PAIR_INDEX: dict[str, tuple[int, str]] = {
    "QSUM_001": (5, "curved"),
    "QSUM_002": (7, "kryptonite"),
    "QSUM_003": (9, "menu"),
    "QSUM_004": (10, "intelligent controller"),
    "QSUM_005": (12, "advanced chip"),
}


def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC} -- download data/Product/jsonl/test.jsonl from the QMSum repo first")
        return 1

    rows = [json.loads(line) for line in SRC.open(encoding="utf-8")]
    OUT.mkdir(parents=True, exist_ok=True)

    for pair_id, (idx, marker) in PAIR_INDEX.items():
        row = rows[idx]
        turns = row["meeting_transcripts"]
        full = " ".join(t.get("content", "") for t in turns).lower()
        if marker not in full:
            print(f"FAIL {pair_id}: marker {marker!r} not found at index {idx} -- mapping is wrong")
            return 2

        (OUT / f"{pair_id}_transcript.json").write_text(
            json.dumps({"meeting_transcripts": turns}, indent=1, ensure_ascii=False),
            encoding="utf-8",
        )
        summary = general_summary(row)
        (OUT / f"{pair_id}_document.txt").write_text(summary, encoding="utf-8")

        words = len(full.split())
        print(f"{pair_id}  idx={idx:2d}  turns={len(turns):4d}  words={words:5d}  "
              f"doc_words={len(summary.split()):4d}  marker ok")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
