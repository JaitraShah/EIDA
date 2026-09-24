"""
Phase 2.3 diagnostic — how much of each domain's "unsupported quote" rate is
near-verbatim tidying rather than fabrication.

The official hallucination rate (outputs/corpus_extraction_results.md) uses the
lenient grounding check in edia.benchmark.score: case, punctuation, whitespace,
`{...}` transcription markers and filler words are forgiven, changed words are not.
Academic (ICSI) transcripts are far more fragmented than the other domains -- false
starts ("the i it may"), repeats, word fragments -- and a model quoting them drops
those, which the lenient check still counts as unsupported.

This script does NOT change that metric. It splits each domain's unsupported quotes
into:
  near-verbatim -- every (lenient-normalised) quote word appears in order in the
                   quote's own chunk, within a window of 1.5x the quote length + 3
                   words (i.e. words were dropped, none added or changed)
  other         -- everything else (paraphrase, fabrication, wrong chunk)
and reports the rate that would remain if near-verbatim tidying were forgiven.
Report it beside the official rate, never instead of it.

    python scripts/quote_fidelity_diagnostic.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.qmsum_corpus import RAW_ROOT, iter_meetings
from edia.benchmark.score import check_evidence_grounding, normalize_lenient
from edia.extraction.chunker import chunk_text
from edia.extraction.schema import ExtractionResult

EXTRACT_DIR = Path("outputs/extractions")
REPORT_MD = Path("outputs/corpus_quote_fidelity.md")
REPORT_JSON = Path("outputs/corpus_quote_fidelity.json")
DOMAINS = {"ACA": "Academic", "CMT": "Committee", "PRD": "Product"}
SLACK = 1.5


def near_verbatim(quote: list[str], hay: list[str]) -> bool:
    """All quote words appear in order in `hay`, within SLACK*len(quote)+3 words."""
    if not quote:
        return False
    for start, word in enumerate(hay):
        if word != quote[0]:
            continue
        i, j = 1, start
        limit = min(len(hay), start + int(SLACK * len(quote)) + 3)
        while i < len(quote) and j + 1 < limit:
            j += 1
            if hay[j] == quote[i]:
                i += 1
        if i == len(quote):
            return True
    return False


def main() -> int:
    stats = defaultdict(lambda: {"quotes": 0, "unsupported": 0, "near_verbatim": 0})
    for m in iter_meetings(RAW_ROOT):
        cache = EXTRACT_DIR / f"{m.meeting_id}.json"
        if not cache.exists():
            continue
        res = ExtractionResult.model_validate(json.loads(cache.read_text(encoding="utf-8")))
        chunks = {c.chunk_id: c.text for c in chunk_text(
            m.transcript, source_id=m.meeting_id, max_tokens=1200, overlap_turns=2)}
        chunk_of = {r.decision_id: r.chunk_id for r in res.records}
        s = stats[DOMAINS[m.meeting_id.split("_")[1]]]
        for q in check_evidence_grounding(res.records, chunks):
            s["quotes"] += 1
            if q.grounded:
                continue
            s["unsupported"] += 1
            hay = normalize_lenient(chunks.get(chunk_of[q.decision_id], "")).split()
            if near_verbatim(normalize_lenient(q.quote).split(), hay):
                s["near_verbatim"] += 1

    lines = [
        "# Corpus quote fidelity — tidying vs fabrication (Phase 2.3 diagnostic)",
        "",
        "Official rate = lenient grounding (markers + fillers forgiven). "
        "Near-verbatim = quote words all present, in order, in the quote's own chunk "
        f"(window {SLACK}x quote length + 3): words dropped, none added or changed.",
        "",
        "| domain | quotes | unsupported (official) | of which near-verbatim | unsupported if tidying forgiven |",
        "|---|--:|--:|--:|--:|",
    ]
    tot = {"quotes": 0, "unsupported": 0, "near_verbatim": 0}
    for dom in ("Academic", "Committee", "Product"):
        s = stats[dom]
        for k in tot:
            tot[k] += s[k]
    for dom, s in [*[(d, stats[d]) for d in ("Academic", "Committee", "Product")], ("**all**", tot)]:
        q, u, nv = s["quotes"], s["unsupported"], s["near_verbatim"]
        lines.append(f"| {dom} | {q} | {u/q:.1%} | {nv}/{u} ({nv/u:.0%}) | {(u-nv)/q:.1%} |")
    lines += ["", "Report the official column as the hallucination rate; this table explains "
              "the domain gap, it does not replace it."]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({**stats, "all": tot}, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
