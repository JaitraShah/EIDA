"""
Build the auto-labelled QMSum benchmark: decompose every meeting's specific-query
answers into elements, label each present/omitted with a gap detector, and write
one `PairSource.QMSUM_AUTO` BenchmarkPair per meeting into data/benchmark/pairs/.

Resumable: a meeting whose pair file already exists is skipped unless --force.
Per-meeting rows are appended to data/benchmark/manifest_qmsum.jsonl and per-
element detector scores to outputs/qmsum_corpus_labels.jsonl (for calibration and
spot-check auditing).

    python scripts/build_qmsum_corpus.py --detector nli            # roberta-large-mnli
    python scripts/build_qmsum_corpus.py --detector nli --shard 0/4   # one of 4 workers
    python scripts/build_qmsum_corpus.py --only QMS_PRD_TE_003 --force
    python scripts/build_qmsum_corpus.py --detector lexical        # offline sanity baseline
    python scripts/build_qmsum_corpus.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.dataset import InDocument, load_all
from edia.benchmark.decompose import get_decomposer
from edia.benchmark.qmsum_corpus import (
    MIN_DOCUMENT_WORDS,
    PAIRS_DIR,
    RAW_ROOT,
    build_pair,
    iter_meetings,
)

MANIFEST = Path("data/benchmark/manifest_qmsum.jsonl")
LABELS_OUT = Path("outputs/qmsum_corpus_labels.jsonl")


def _make_detector(name: str, model: str | None, threshold: float):
    if name == "lexical":
        from edia.gapdetect.lexical import LexicalGapDetector

        return LexicalGapDetector(threshold=threshold), "lexical:token_f1"
    if name == "nli":
        from edia.gapdetect.nli import NliGapDetector

        d = NliGapDetector(model_name=model or "roberta-large-mnli",
                           entail_threshold=threshold)
        return d, f"nli:{d.model_name}"
    if name == "llm":
        from edia.gapdetect.entailment_llm import LlmEntailmentGapDetector

        d = LlmEntailmentGapDetector(model=model)
        return d, f"llm:{d.model}"
    if name == "ensemble":
        from edia.gapdetect.ensemble import EnsembleGapDetector

        d = EnsembleGapDetector(nli_model=model or "roberta-large-mnli",
                                nli_threshold=threshold, llm_model=model)
        return d, f"ensemble[{'+'.join(d.member_names)}]"
    raise ValueError(f"unknown detector {name!r}")


def _shard_ok(shard: str | None, i: int) -> bool:
    if not shard:
        return True
    k, n = (int(x) for x in shard.split("/"))
    return i % n == k


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(RAW_ROOT))
    ap.add_argument("--detector", default="nli",
                    choices=["nli", "llm", "lexical", "ensemble"])
    ap.add_argument("--decomposer", default="sentence", choices=["sentence", "llm"])
    ap.add_argument("--model", default=None, help="override detector model name")
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="entailment prob (nli) or token-f1 (lexical) above which "
                         "an element counts as present")
    ap.add_argument("--only", help="one meeting id, e.g. QMS_ACA_TR_004")
    ap.add_argument("--limit", type=int, help="process at most N new meetings")
    ap.add_argument("--shard", help="k/N -- process meetings where index %% N == k")
    ap.add_argument("--force", action="store_true", help="rewrite existing pairs")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    PAIRS_DIR.mkdir(parents=True, exist_ok=True)
    meetings = list(iter_meetings(args.root))

    if args.status:
        on_disk = {p.stem for p in PAIRS_DIR.glob("QMS_*.json")}
        done = [m for m in meetings if m.meeting_id in on_disk]
        print(f"corpus meetings : {len(meetings)}")
        print(f"pairs written   : {len(done)}")
        print(f"remaining       : {len(meetings) - len(done)}")
        if MANIFEST.exists():
            rows = [json.loads(l) for l in MANIFEST.open(encoding='utf-8') if l.strip()]
            statuses: dict[str, int] = {}
            for r in rows:
                statuses[r.get("status", "?")] = statuses.get(r.get("status", "?"), 0) + 1
            print(f"manifest rows   : {len(rows)}  {statuses}")
        return 0

    detector, provenance = _make_detector(args.detector, args.model, args.threshold)
    decomposer = get_decomposer(args.decomposer,
                                **({"model": args.model} if args.decomposer == "llm" else {}))
    provenance = f"{provenance} / decompose:{decomposer.name} / thr={args.threshold}"

    processed = 0
    for i, m in enumerate(meetings):
        if args.only and m.meeting_id != args.only:
            continue
        if not args.only and not _shard_ok(args.shard, i):
            continue
        pair_path = PAIRS_DIR / f"{m.meeting_id}.json"
        if pair_path.exists() and not args.force:
            continue
        if args.limit is not None and processed >= args.limit:
            break

        start = time.time()
        try:
            if m.document_word_count < MIN_DOCUMENT_WORDS:
                append_jsonl(MANIFEST, {"meeting_id": m.meeting_id, "status": "skipped_short_document",
                                        "document_words": m.document_word_count})
                print(f"{m.meeting_id}: SKIP short document ({m.document_word_count} words)")
                continue

            raw_elements = decomposer.decompose(m.specific_query_list)
            if not raw_elements:
                append_jsonl(MANIFEST, {"meeting_id": m.meeting_id, "status": "skipped_no_elements"})
                print(f"{m.meeting_id}: SKIP no substantive elements")
                continue

            labelled = []
            for raw in raw_elements:
                label, score = detector.label_element(m.document, raw.text)
                labelled.append((raw, label, score))
                append_jsonl(LABELS_OUT, {
                    "meeting_id": m.meeting_id, "domain": m.domain, "split": m.split,
                    "query_index": raw.query_index, "element_type": raw.element_type.value,
                    "text": raw.text, "label": label.value, "entail_score": round(score, 4),
                    "detector": args.detector, "threshold": args.threshold,
                })

            pair = build_pair(m, labelled, label_provenance=provenance)
            pair.save(PAIRS_DIR)
            gaps = sum(1 for _, lab, _ in labelled if lab is InDocument.OMITTED)
            append_jsonl(MANIFEST, {
                "meeting_id": m.meeting_id, "status": "ok", "domain": m.domain,
                "split": m.split, "elements": len(labelled), "gaps": gaps,
                "provenance": provenance, "seconds": round(time.time() - start, 1),
            })
            print(f"{m.meeting_id}: {len(labelled)} elements, {gaps} gaps "
                  f"({time.time() - start:.0f}s)")
        except Exception as e:  # noqa: BLE001 -- best effort, record and continue
            append_jsonl(MANIFEST, {"meeting_id": m.meeting_id, "status": "failed",
                                    "error": f"{type(e).__name__}: {e}"})
            print(f"{m.meeting_id}: FAILED -- {type(e).__name__}: {e}")
        processed += 1

    stats = load_all(PAIRS_DIR)
    print(f"\ndone. {sum(1 for p in stats if p.source.value == 'qmsum_auto')} "
          f"QMSUM_AUTO pairs on disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
