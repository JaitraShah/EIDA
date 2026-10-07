"""
Phase 3.3 — multi-hop retrieval baseline (EDIA_Project_Plan_v2.md).

Implements the plan's exact chain: given a decision, retrieve its rationale, then
use the rationale to retrieve alternatives, then retrieve objections. Retrieval is
TF-IDF cosine over transcript turns (scikit-learn, already a dependency via
sentence-transformers) -- no external API, fully reproducible.

    def multihop_extract(meeting_text, decision):
        rationale    = retrieve(meeting_text, f"Why was '{decision}' chosen?")
        alternatives = retrieve(meeting_text, f"Given that '{rationale}', what alternatives...")
        objections   = retrieve(meeting_text, f"What objections were raised about '{decision}'?")

The plan's hypothesis: the chain breaks because the first hop already fails -- in a
meeting you often cannot find the rationale without already understanding the full
context, so the chain is only knowable in hindsight.

IMPORTANT scoring caveat, stated once here rather than buried in a footnote: the
method receives the true decision text as input (`multihop_extract(text, decision)`
-- the plan's own signature takes it as a parameter, it does not discover it). So
decision-type recall is 100% by construction and NOT comparable to the EDIA
pipeline, which must find decisions from scratch. This script reports completeness
both ways -- **use "excluding decision" for the Phase 3.4 comparison table**, since
that is the fair apples-to-apples number. Conditions/owner/approver are outside the
plan's 3-hop chain and are always misses here; that is a real, reportable
limitation of the baseline as specified, not a bug in this script.

    python scripts/multihop_retrieval.py
    python scripts/multihop_retrieval.py --top-k 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from edia.benchmark.qmsum_ground_truth import GROUND_TRUTH
from edia.benchmark.score import SOFT_ELEMENT_TYPES, SemanticMatcher, score_extraction, token_f1
from edia.extraction.schema import Alternative, DecisionRecord, ExtractionResult

DATA = Path("data/qmsum")
REPORT_MD = Path("outputs/multihop_retrieval_results.md")
REPORT_JSON = Path("outputs/multihop_retrieval_results.json")
BASELINE_SEM = Path("outputs/task4_extraction_scores_semantic.json")


def _edia_baseline() -> str:
    if not BASELINE_SEM.exists():
        return "not yet run -- `python scripts/run_qmsum_eval.py --semantic`"
    rows = json.loads(BASELINE_SEM.read_text(encoding="utf-8"))
    m = sum(r["gt_matched"] for r in rows)
    t = sum(r["gt_total"] for r in rows)
    return f"{m/t:.1%}" if t else "n/a"


def load_turns(pair_id: str) -> list[str]:
    raw = json.loads((DATA / f"{pair_id}_transcript.json").read_text(encoding="utf-8"))
    turns = raw.get("meeting_transcripts", raw) if isinstance(raw, dict) else raw
    return [f"{(t.get('speaker') or '').strip()}: {(t.get('content') or t.get('text') or '').strip()}"
            for t in turns]


class Retriever:
    def __init__(self, turns: list[str]):
        self.turns = turns
        self.vec = TfidfVectorizer(stop_words="english")
        self.matrix = self.vec.fit_transform(turns)

    def retrieve(self, query: str, k: int) -> str:
        q = self.vec.transform([query])
        sims = cosine_similarity(q, self.matrix)[0]
        top = sims.argsort()[-k:][::-1]
        return " ".join(self.turns[i] for i in top if sims[i] > 0)


def multihop_extract(retriever: Retriever, decision: str, k: int) -> DecisionRecord:
    rationale = retriever.retrieve(f"Why was '{decision}' chosen? What was the reasoning?", k)
    alternatives = retriever.retrieve(
        f"Given that {rationale[:200]}, what other options or alternatives were considered "
        f"instead of {decision}?", k,
    )
    objections = retriever.retrieve(
        f"What objections, concerns, or disagreements were raised about '{decision}'?", k,
    )
    return DecisionRecord(
        decision_id=f"multihop_{abs(hash(decision)) % 100000}",
        source_id="multihop",
        chunk_id="multihop_0",
        decision=decision,
        rationale=[rationale] if rationale else [],
        alternatives=[Alternative(option=alternatives)] if alternatives else [],
        dissent=[objections] if objections else [],
    )


SOFT = {t.value for t in SOFT_ELEMENT_TYPES}


def _completeness(report, exclude_types: set[str] = frozenset()) -> tuple[int, int]:
    """(matched, total) over report.matches, optionally excluding a gt_type.

    Owner/approver are always excluded, exactly as EDIA's completeness excludes them
    (score.py SOFT_ELEMENT_TYPES); otherwise this baseline is scored on a different
    denominator from the rows it is compared against."""
    kept = [m for m in report.matches if m.gt_type not in exclude_types | SOFT]
    return sum(m.matched for m in kept), len(kept)


def _retrieval_only(records, truth, sim, threshold) -> tuple[int, int]:
    """(matched, total) for the non-decision ground truth, matched ONLY against what was
    retrieved. The true decisions are an input here; letting their text match a gold
    rationale (which it often resembles) would credit retrieval for its own input."""
    retrieved = [x for rec in records for t, x in rec.reasoning_elements()
                 if t.value != "decision" and t.value not in SOFT]
    gt = [g for t, g in truth.all_elements() if t != "decision" and t not in SOFT]
    hit = sum(bool(retrieved) and max(sim(x, g) for x in retrieved) >= threshold for g in gt)
    return hit, len(gt)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top-k", type=int, default=3, help="turns retrieved per hop")
    ap.add_argument("--threshold", type=float, default=0.45, help="lexical match threshold")
    ap.add_argument("--sem-threshold", type=float, default=0.55,
                    help="semantic match threshold (same as the EDIA semantic baseline)")
    args = ap.parse_args(argv)

    semantic = SemanticMatcher()
    rows = []
    for truth in GROUND_TRUTH:
        turns = load_turns(truth.pair_id)
        retriever = Retriever(turns)

        gt_decisions = [d.decision for d in truth.decisions]
        records = [multihop_extract(retriever, d, args.top_k) for d in gt_decisions]
        result = ExtractionResult(source_id=truth.pair_id, model_name="tfidf-multihop",
                                  records=records, merged_across_chunks=False)

        lex = score_extraction(result, truth, threshold=args.threshold)
        rows.append((truth.pair_id,
                     *_completeness(lex),
                     *_retrieval_only(records, truth, token_f1, args.threshold),
                     *_retrieval_only(records, truth, semantic.similarity, args.sem_threshold)))

    lines = [
        "# Phase 3.3 — multi-hop retrieval baseline",
        "",
        f"- retriever: TF-IDF cosine, top-{args.top_k} turns per hop",
        "- decisions are given as input (the plan's own `multihop_extract(text, decision)` "
        "signature) -- decision recall is 100% by construction and excluded from the fair "
        "comparison column",
        "- conditions are outside the plan's 3-hop chain (rationale -> alternatives -> "
        "objections) and are always misses here",
        "- owner/approver are excluded from every column, as in EDIA's completeness",
        "- excl.-decision columns match the gold elements against the RETRIEVED turns only: "
        "the handed-in decision text often resembles a gold rationale, and crediting that "
        "would count the method's own input as something it found",
        "",
        "Both matchers are reported, with the same thresholds as the EDIA baseline "
        f"(lexical {args.threshold}, semantic {args.sem_threshold}).",
        "",
        "| pair | lexical, incl. seeded decision | lexical, excl. decision | semantic, excl. decision |",
        "|---|--:|--:|--:|",
    ]
    tot = [0] * 6
    for pid, *vals in rows:
        tot = [a + b for a, b in zip(tot, vals)]
        cells = [f"{m / n:.3f} ({m}/{n})" if n else "n/a" for m, n in zip(vals[::2], vals[1::2])]
        lines.append(f"| {pid} | " + " | ".join(cells) + " |")
    c_all, c_lex, c_sem = (m / n if n else 0.0 for m, n in zip(tot[::2], tot[1::2]))
    lines.append(f"| **total** | **{c_all:.3f}** ({tot[0]}/{tot[1]}) | **{c_lex:.3f}** "
                 f"({tot[2]}/{tot[3]}) | **{c_sem:.3f}** ({tot[4]}/{tot[5]}) |")
    lines += [
        "",
        "## Reading",
        "",
        f"**Use the excl.-decision columns for Table 4: {c_lex:.1%} lexical / {c_sem:.1%} "
        "semantic.** This baseline is handed its decisions, so the seeded column would "
        "flatter it on the one thing it was not asked to do.",
        "",
        f"Against EDIA's semantic-scored {_edia_baseline()}, multi-hop retrieval's "
        f"{c_sem:.1%} semantic is the failure mode the plan predicted: rationale is "
        "retrieved by similarity to the decision text alone, before anything about *why* "
        "is known, so hop 1 frequently returns adjacent-topic turns rather than the actual "
        "reasoning -- and hops 2-3 compound that error since they query using hop 1's "
        "(possibly wrong) output.",
    ]

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({
        "top_k": args.top_k, "threshold": args.threshold, "sem_threshold": args.sem_threshold,
        "rows": [{"pair_id": p, "matched_incl": a, "total_incl": b,
                  "matched_excl_lex": c, "total_excl_lex": d,
                  "matched_excl_sem": e, "total_excl_sem": f}
                 for p, a, b, c, d, e, f in rows],
        "completeness_incl_decision": c_all,
        "completeness_excl_decision_lex": c_lex,
        "completeness_excl_decision_sem": c_sem,
    }, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {REPORT_MD} and {REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
