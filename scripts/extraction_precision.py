"""Precision and F1 for every extraction approach on the five gold meetings.

Completeness (recall) alone rewards over-generation, so this adds precision on the
same units, matchers and thresholds as the completeness scores (lexical token-F1 at
0.45, semantic all-MiniLM-L6-v2 at 0.55).

- Unit: one extracted reasoning element (`DecisionRecord.reasoning_elements()`).
  Owner/approver are excluded on both sides, as they are from completeness.
- Precision: share of extracted elements whose best similarity to any hand-labelled
  element clears the threshold. It is a LOWER BOUND: the hand labels are not
  exhaustive, so a correct element the annotator did not write down counts as wrong.
- Redundancy-penalised precision: distinct hand-labelled elements matched / extracted
  elements, i.e. a second copy of an already-found element earns nothing.
- Recall = completeness, recomputed here and checked against score_extraction, so
  every approach is scored on exactly the data its own script scored.
- Multi-hop retrieval is handed the true decisions, so decisions are excluded from
  both its predictions and its ground truth, and gold is matched against what it
  retrieved only (same as its completeness column).

    python scripts/extraction_precision.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import multihop_retrieval as mh  # noqa: E402
from run_graphrag_comparison import ANSWER_DIR, convert  # noqa: E402
from run_qmsum_eval import _drop_non_decisions  # noqa: E402

from edia.benchmark.qmsum_ground_truth import GROUND_TRUTH  # noqa: E402
from edia.benchmark.score import (  # noqa: E402
    SOFT_ELEMENT_TYPES, SemanticMatcher, score_extraction, token_f1,
)
from edia.extraction.schema import ExtractionResult  # noqa: E402

OUT = ROOT / "outputs"
LEX_THRESHOLD, SEM_THRESHOLD = 0.45, 0.55
SOFT = {t.value for t in SOFT_ELEMENT_TYPES}


def _cached(dirname: str, pid: str, drop_non_decisions: bool = False) -> ExtractionResult:
    r = ExtractionResult.model_validate(
        json.loads((OUT / dirname / f"{pid}.json").read_text(encoding="utf-8")))
    if drop_non_decisions:  # what run_qmsum_eval.py does to the original baseline cache
        r.records = _drop_non_decisions(r.records, pid)
    return r


def _graphrag(pid: str, strict: bool) -> ExtractionResult:
    payload = json.loads((ANSWER_DIR / f"{pid}.json").read_text(encoding="utf-8"))
    return convert(pid, payload, None, strict=strict)


def _multihop(pid: str) -> ExtractionResult:
    truth = next(t for t in GROUND_TRUTH if t.pair_id == pid)
    ret = mh.Retriever(mh.load_turns(pid))
    recs = [mh.multihop_extract(ret, d.decision, 3) for d in truth.decisions]
    return ExtractionResult(source_id=pid, model_name="tfidf-multihop", records=recs,
                            merged_across_chunks=False)


# (name, loader, excluded types, completeness the paper reports as lex/sem %)
APPROACHES = [
    ("EDIA pipeline", lambda p: _cached("extractions", p, True), set(), (33.3, 58.3)),
    ("EDIA pipeline, same runtime", lambda p: _cached("extractions_rerun", p), set(), (27.1, 58.3)),
    ("EDIA + chain-of-thought", lambda p: _cached("extractions_cot", p), set(), (33.3, 62.5)),
    ("GraphRAG (support filter on)", lambda p: _graphrag(p, True), set(), (4.2, 14.6)),
    ("GraphRAG (support filter off)", lambda p: _graphrag(p, False), set(), (4.2, 18.8)),
    ("Multi-hop retrieval (excl. decisions)", _multihop, {"decision"}, (0.0, 12.8)),
]


def _f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def score(result, truth, excluded, sim, threshold, semantic):
    gt = [(t, x) for t, x in truth.all_elements() if t not in SOFT and t not in excluded]
    pred = [(t.value, x) for rec in result.records for t, x in rec.reasoning_elements()
            if t.value not in SOFT and t.value not in excluded]

    if excluded:
        # multi-hop: gold matched against the retrieved items only (its decisions are an
        # input), exactly as multihop_retrieval.py scores its fair column
        gt_hit = sum(bool(pred) and max(sim(x, g) for _, x in pred) >= threshold for _, g in gt)
    else:
        # recall exactly as score_extraction computes it
        rep = score_extraction(result, truth, threshold=threshold, semantic=semantic)
        kept = [m for m in rep.matches if m.gt_type not in SOFT]
        assert len(kept) == len(gt)
        gt_hit = sum(m.matched for m in kept)

    correct = 0
    for _, x in pred:
        if gt and max(sim(x, g) for _, g in gt) >= threshold:
            correct += 1
    return {"pred": len(pred), "correct": correct, "gt": len(gt), "gt_hit": gt_hit}


def main() -> int:
    semantic = SemanticMatcher()
    results = []
    for name, load, excluded, (exp_lex, exp_sem) in APPROACHES:
        row = {"approach": name}
        for label, sim, thr, sem, expected in (
            ("lex", token_f1, LEX_THRESHOLD, None, exp_lex),
            ("sem", semantic.similarity, SEM_THRESHOLD, semantic, exp_sem),
        ):
            tot = {"pred": 0, "correct": 0, "gt": 0, "gt_hit": 0}
            for truth in GROUND_TRUTH:
                s = score(load(truth.pair_id), truth, excluded, sim, thr, sem)
                tot = {k: tot[k] + s[k] for k in tot}
            r = tot["gt_hit"] / tot["gt"]
            if round(100 * r, 1) != expected:
                raise SystemExit(f"{name} {label}: recall {r:.1%} != published {expected}% -- "
                                 "not scoring the same data; stopping")
            p = tot["correct"] / tot["pred"] if tot["pred"] else 0.0
            p_red = tot["gt_hit"] / tot["pred"] if tot["pred"] else 0.0
            row[label] = {**tot, "precision": p, "precision_redundancy_penalised": p_red,
                          "recall": r, "f1": _f1(p, r)}
        results.append(row)

    lines = [
        "# Extraction precision and F1 (5 gold meetings)",
        "",
        "Same units, matchers and thresholds as completeness (lexical token-F1 @ 0.45, "
        "semantic MiniLM @ 0.55). Recall = completeness, recomputed and checked against the "
        "published figure for every row. **Precision is a lower bound**: the hand labels "
        "are not exhaustive, so a correct element the annotator did not list counts as wrong.",
        "",
        "| approach | extracted elements | P (lex) | R (lex) | F1 (lex) | P (sem) | R (sem) | F1 (sem) |",
        "|---|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for row in results:
        lx, sm = row["lex"], row["sem"]
        lines.append(f"| {row['approach']} | {lx['pred']} | {lx['precision']:.1%} | "
                     f"{lx['recall']:.1%} | {lx['f1']:.1%} | {sm['precision']:.1%} | "
                     f"{sm['recall']:.1%} | {sm['f1']:.1%} |")
    lines += [
        "",
        "## Redundancy-penalised precision",
        "",
        "Distinct hand-labelled elements matched / extracted elements: a repeated copy of an "
        "element already found earns nothing. The gap from plain precision is how much of the "
        "output is duplicates of correct items.",
        "",
        "| approach | lex | sem |",
        "|---|--:|--:|",
    ]
    for row in results:
        lines.append(f"| {row['approach']} | {row['lex']['precision_redundancy_penalised']:.1%} | "
                     f"{row['sem']['precision_redundancy_penalised']:.1%} |")

    (OUT / "extraction_precision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "extraction_precision.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {OUT / 'extraction_precision.md'} and .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
