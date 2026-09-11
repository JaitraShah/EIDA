"""
Phase 2.4 -- structured failure analysis of extraction misses on the 5 gold pairs.

Turns "completeness is 58%" into a diagnosis by asking, for every reasoning element
the extractor failed to recover, *why* it was missed.

Scope (fixed deliberately -- see EDIA_Project_Plan_v2.md): only QSUM_001-005 have
hand-built reasoning ground truth, and all five are Product/test. Academic and
Committee meetings are NOT labelled for completeness and must not be.

Misses are taken from the **semantic** scorer, not the lexical one. 14 of the 32
lexical misses are correct extractions the token-F1 matcher under-credited
("battery" scored 0.00); counting those as reasoning failures would manufacture a
"paraphrase miss" category that is really a scorer artifact.

Two steps:

    python scripts/failure_analysis.py --build     # evidence -> outputs/failure_analysis_evidence.json
    python scripts/failure_analysis.py --report    # annotations -> outputs/failure_taxonomy.md

`--build` gathers, per missed element, the signals a human needs to categorise it:
where the supporting content actually sits in the transcript, how far apart those
turns are, which chunk(s) they fall in, and what the extractor said that was
closest. Categories are then recorded by hand in

    data/failure_annotations.jsonl     {"key": ..., "category": ..., "note": ...}

`--report` tallies them. The categorisation is a human reading the evidence; this
script only assembles it and counts the result.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.qmsum_ground_truth import BY_ID
from edia.benchmark.score import SOFT_ELEMENT_TYPES
from edia.extraction.chunker import chunk_text

# score.py keeps owner/approver out of headline completeness (they are N/A in
# AMI-style data, Task 1 caveat 1) but still lists them in `missed_elements`.
# Categorising them as extraction failures would blame the extractor for a dataset
# limitation, so they are dropped here too and reported as a separate count.
SOFT_TYPES = {t.value for t in SOFT_ELEMENT_TYPES}

DATA = Path("data/qmsum")
EXTRACT_DIR = Path("outputs/extractions")
SEM_SCORES = Path("outputs/task4_extraction_scores_semantic.json")
LEX_SCORES = Path("outputs/task4_extraction_scores.json")
EVIDENCE = Path("outputs/failure_analysis_evidence.json")
ANNOTATIONS = Path("data/failure_annotations.jsonl")
REPORT_MD = Path("outputs/failure_taxonomy.md")

CATEGORIES = {
    "multihop_scattered": "Multi-hop: scattered -- reasoning spread across 3+ turns far apart",
    "multihop_implicit": "Multi-hop: implicit -- connection never stated directly; inferred",
    "chunk_boundary": "Chunking boundary -- reasoning split across a chunk cut",
    "paraphrase_miss": "Paraphrase miss -- found but worded differently; scorer missed it",
    "hallucination": "Model hallucination -- extractor invented a quote not in source",
    "out_of_scope": "Out of scope -- present in transcript, model chose not to extract",
}

# Chunking must mirror the extraction run or boundary attribution is meaningless.
MAX_TOKENS = 1200
OVERLAP_TURNS = 2
TOP_TURNS = 5


def load_turns(pair_id: str) -> list[dict]:
    """Flat list of {idx, speaker, text} for the meeting transcript."""
    raw = json.loads((DATA / f"{pair_id}_transcript.json").read_text(encoding="utf-8"))
    turns = raw.get("meeting_transcripts", raw) if isinstance(raw, dict) else raw
    out = []
    for i, t in enumerate(turns):
        out.append({
            "idx": i,
            "speaker": (t.get("speaker") or "").strip(),
            "text": (t.get("content") or t.get("text") or "").strip(),
        })
    return out


def _embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def locate_evidence(model, element_text: str, turns: list[dict], top_k=TOP_TURNS):
    """The turns most likely to carry this element's supporting content."""
    import numpy as np

    texts = [t["text"] for t in turns]
    emb = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True,
                       show_progress_bar=False, batch_size=64)
    q = model.encode([element_text], convert_to_numpy=True, normalize_embeddings=True,
                     show_progress_bar=False)[0]
    sims = emb @ q
    order = np.argsort(-sims)[:top_k]
    return [
        {"turn": int(i), "sim": round(float(sims[i]), 3),
         "speaker": turns[i]["speaker"], "text": turns[i]["text"][:300]}
        for i in sorted(order, key=lambda i: -sims[i])
    ]


def chunk_index(turns_count: int, transcript: str, pair_id: str):
    """Map each chunk to the turn range it covers, for boundary attribution."""
    chunks = chunk_text(transcript, source_id=pair_id,
                        max_tokens=MAX_TOKENS, overlap_turns=OVERLAP_TURNS)
    return [{"chunk_id": c.chunk_id, "n_turns": getattr(c, "n_turns", None),
             "preview": c.text[:120]} for c in chunks]


def build() -> int:
    sem = {r["pair_id"]: r for r in json.loads(SEM_SCORES.read_text(encoding="utf-8"))}
    lex = {r["pair_id"]: r for r in json.loads(LEX_SCORES.read_text(encoding="utf-8"))}

    model = _embedder()
    records = []
    soft_skipped: list[str] = []

    for pair_id in sorted(sem):
        truth = BY_ID[pair_id]
        turns = load_turns(pair_id)
        transcript = "\n".join(f"{t['speaker']}: {t['text']}" for t in turns)
        chunks = chunk_index(len(turns), transcript, pair_id)

        lex_missed = {m["text"] for m in lex[pair_id]["missed_elements"]}
        extracted_path = EXTRACT_DIR / f"{pair_id}.json"
        extracted = json.loads(extracted_path.read_text(encoding="utf-8")) \
            if extracted_path.exists() else {}

        for m in sem[pair_id]["missed_elements"]:
            if m["type"] in SOFT_TYPES:
                soft_skipped.append(f"{pair_id}::{m['type']}::{m['text'][:40]}")
                continue
            ev = locate_evidence(model, m["text"], turns)
            spread = (max(e["turn"] for e in ev) - min(e["turn"] for e in ev)) if ev else 0
            records.append({
                "key": f"{pair_id}::{m['type']}::{m['text'][:60]}",
                "pair_id": pair_id,
                "meeting": truth.qmsum_meeting,
                "element_type": m["type"],
                "element_text": m["text"],
                "semantic_best_score": m.get("best_score"),
                "closest_extracted": m.get("closest_extracted"),
                "also_missed_by_lexical": m["text"] in lex_missed,
                "n_turns_in_meeting": len(turns),
                "n_chunks": len(chunks),
                "evidence_turn_spread": spread,
                "evidence_turns": ev,
            })

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"{len(records)} residual (semantic) misses -> {EVIDENCE}")
    for pid in sorted(sem):
        n = sum(1 for r in records if r["pair_id"] == pid)
        print(f"  {pid}: {n}")
    if soft_skipped:
        print(f"\nexcluded {len(soft_skipped)} owner/approver misses "
              f"(N/A in AMI data, not extraction failures):")
        for s in soft_skipped:
            print("  ", s)
    print(f"\nAnnotate in {ANNOTATIONS}, then: python scripts/failure_analysis.py --report")
    print("categories:", ", ".join(CATEGORIES))
    return 0


def report() -> int:
    if not ANNOTATIONS.exists():
        raise SystemExit(f"no annotations at {ANNOTATIONS} -- run --build and annotate first")
    records = {r["key"]: r for r in json.loads(EVIDENCE.read_text(encoding="utf-8"))}
    anns = [json.loads(l) for l in ANNOTATIONS.read_text(encoding="utf-8").splitlines() if l.strip()]

    unknown = [a["category"] for a in anns if a["category"] not in CATEGORIES]
    if unknown:
        raise SystemExit(f"unknown categories: {sorted(set(unknown))}")

    missing = set(records) - {a["key"] for a in anns}
    tally = Counter(a["category"] for a in anns)
    by_pair: dict[str, Counter] = {}
    for a in anns:
        pid = records[a["key"]]["pair_id"] if a["key"] in records else "?"
        by_pair.setdefault(pid, Counter())[a["category"]] += 1

    total = sum(tally.values())
    lines = [
        "# Phase 2.4 — extraction failure taxonomy",
        "",
        "Scope: the 5 gold Product/test meetings (QSUM_001–005) — the only meetings with",
        "hand-built reasoning ground truth. Misses are the **semantic**-scorer residual,",
        "so lexical scoring artifacts are excluded by construction.",
        "",
        f"Annotated: **{total}** of {len(records)} residual misses."
        + (f" ({len(missing)} unannotated)" if missing else ""),
        "",
        "| Failure category | n | share |",
        "|---|--:|--:|",
    ]
    for cat, desc in CATEGORIES.items():
        n = tally.get(cat, 0)
        lines.append(f"| {desc} | {n} | {n/total:.0%} |" if total else f"| {desc} | 0 | — |")
    lines += ["", "## By meeting", "",
              "| pair | " + " | ".join(CATEGORIES) + " |",
              "|---" * (len(CATEGORIES) + 1) + "|"]
    for pid in sorted(by_pair):
        lines.append(f"| {pid} | " + " | ".join(str(by_pair[pid].get(c, 0)) for c in CATEGORIES) + " |")

    multihop = tally.get("multihop_scattered", 0) + tally.get("multihop_implicit", 0)
    lines += ["", "## Reading", "",
              f"Multi-hop categories account for **{multihop}/{total} "
              f"({multihop/total:.0%})** of residual misses." if total else ""]

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if missing:
        print(f"\n{len(missing)} unannotated:")
        for k in sorted(missing):
            print("  ", k)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    if args.build:
        return build()
    if args.report:
        return report()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
