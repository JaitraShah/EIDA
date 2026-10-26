"""
Phase 3.4 — the comparative analysis table (EDIA_Project_Plan_v2.md, Table 4).

Pulls together every approach that has been run and renders the single comparison
table the paper's Section 7 is built around. Run after:

    python scripts/run_qmsum_eval.py                 # EDIA baseline, lexical
    python scripts/run_qmsum_eval.py --semantic       # EDIA baseline, semantic
    python scripts/run_cot_ablation.py                # EDIA + CoT
    python scripts/multihop_retrieval.py              # multi-hop retrieval
    # GraphRAG: run scripts/run_graphrag_comparison.py first, then pass its completeness
    # with --graphrag, or leave it out to render the plan's own cited-argument fallback.

Any input file that is missing is rendered as "not run" rather than guessed, so a
partial run never silently produces a complete-looking table.

    python scripts/build_comparison_table.py
    python scripts/build_comparison_table.py --graphrag 0.15 --graphrag-note "15 meetings, local search"
    # scripts/run_graphrag_comparison.py prints the exact command, incl. --graphrag-lex
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPORT_MD = Path("outputs/comparative_analysis.md")

FILES = {
    "edia_lex": Path("outputs/task4_extraction_scores.json"),
    "edia_sem": Path("outputs/task4_extraction_scores_semantic.json"),
    "cot": Path("outputs/cot_ablation_results.json"),
    "multihop": Path("outputs/multihop_retrieval_results.json"),
    # plain EDIA re-extracted on the same runtime as CoT/GraphRAG (run_cot_ablation.py --no-cot)
    "edia_rerun": Path("outputs/baseline_rerun_scores.json"),
}


def _quote_counts(rows: list[dict]) -> tuple[int, int]:
    """(grounded, total) summed over reports. `quotes_grounded` is a '76/84' string."""
    grounded = total = 0
    for r in rows:
        g, _, t = (r.get("quotes_grounded") or "0/0").partition("/")
        grounded += int(g or 0)
        total += int(t or 0)
    return grounded, total


def _hallucination(rows: list[dict]) -> float:
    grounded, total = _quote_counts(rows)
    return (total - grounded) / total if total else 0.0


def _edia_row(lex_path: Path, sem_path: Path) -> dict | None:
    if not (lex_path.exists() and sem_path.exists()):
        return None
    lex = json.loads(lex_path.read_text(encoding="utf-8"))
    sem = json.loads(sem_path.read_text(encoding="utf-8"))
    lex_c = sum(r["gt_matched"] for r in lex) / sum(r["gt_total"] for r in lex)
    sem_c = sum(r["gt_matched"] for r in sem) / sum(r["gt_total"] for r in sem)
    return {"lex": lex_c, "sem": sem_c, "halluc": _hallucination(lex)}


def _cot_row(path: Path) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    lex = d["lexical"]; sem = d["semantic"]
    lex_c = sum(r["gt_matched"] for r in lex) / sum(r["gt_total"] for r in lex)
    sem_c = sum(r["gt_matched"] for r in sem) / sum(r["gt_total"] for r in sem)
    return {"lex": lex_c, "sem": sem_c, "halluc": _hallucination(lex)}


def _multihop_row(path: Path) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    return {"lex": d["completeness_excl_decision_lex"],
            "sem": d["completeness_excl_decision_sem"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graphrag", type=float, default=None,
                    help="GraphRAG completeness (0-1) if you ran it end-to-end")
    ap.add_argument("--graphrag-lex", type=float, default=None,
                    help="GraphRAG lexical completeness (0-1); scripts/run_graphrag_comparison.py prints both")
    ap.add_argument("--graphrag-note", default="")
    args = ap.parse_args(argv)

    edia = _edia_row(FILES["edia_lex"], FILES["edia_sem"])
    # same shape as the CoT results file (lexical/semantic ScoreReport lists)
    edia_rerun = _cot_row(FILES["edia_rerun"])
    cot = _cot_row(FILES["cot"])
    multihop = _multihop_row(FILES["multihop"])

    def cell(v, fmt="{:.1%}"):
        return fmt.format(v) if v is not None else "not run"

    lines = [
        "# Phase 3.4 — comparative analysis (Table 4)",
        "",
        "Completeness scored against the 5 gold Product/test meetings (the only "
        "meetings with hand-built reasoning ground truth -- see Phase 2.3 scoping). "
        "Both lexical and semantic completeness are reported per the project's own "
        "rule: never pick the flattering scorer.",
        "",
        "| approach | completeness (lex) | completeness (sem) | hallucination | core failure reason |",
        "|---|--:|--:|--:|---|",
        f"| EDIA pipeline | {cell(edia['lex'] if edia else None)} | "
        f"{cell(edia['sem'] if edia else None)} | "
        f"{cell(edia['halluc'] if edia else None)} | Multi-hop across chunks (Table 3) |",
        *([f"| EDIA pipeline, re-run on the CoT/GraphRAG runtime | {cell(edia_rerun['lex'])} | "
           f"{cell(edia_rerun['sem'])} | {cell(edia_rerun['halluc'])} | Same method; the runtime "
           f"change alone moves lexical completeness |"] if edia_rerun else []),
        f"| EDIA + CoT | {cell(cot['lex'] if cot else None)} | "
        f"{cell(cot['sem'] if cot else None)} | "
        f"{cell(cot['halluc'] if cot else None)} | CoT helps reasoning at answer time, not retrieval |",
        f"| GraphRAG | {cell(args.graphrag_lex) if args.graphrag_lex is not None else '—'} | "
        f"{cell(args.graphrag)} | — | Designed for static structured text, not "
        f"conversational multi-speaker data"
        + (f" ({args.graphrag_note})" if args.graphrag_note else
           "; not run end-to-end here -- see EDIA_Project_Plan_v2.md Sec. 3.2 for the "
           "cited-argument fallback (external GraphRAG benchmarks report ~13% on "
           "conversational tasks)")
        + " |",
        f"| Multi-hop retrieval | {cell(multihop['lex'] if multihop else None)} | "
        f"{cell(multihop['sem'] if multihop else None)} "
        f"| 0 (retrieves, does not generate) | Chain unknown in advance -- hop 1 fails "
        f"before hop 2 can compound it |",
        "",
    ]

    if edia_rerun:
        lines += [
            "**Runtimes.** The first EDIA row (Table 2) was extracted on Ollama 0.32.1 / RTX 3050; "
            "EDIA + CoT, GraphRAG and the EDIA re-run on Ollama 0.34.4 / RTX 3090 (same model and "
            "settings). Compare CoT and GraphRAG against the **re-run** row: CoT's same-runtime "
            f"effect is {cot['lex'] - edia_rerun['lex']:+.1%} lexical / "
            f"{cot['sem'] - edia_rerun['sem']:+.1%} semantic."
            if cot else
            "**Runtimes.** The first EDIA row was extracted on Ollama 0.32.1 / RTX 3050; the re-run "
            "row on Ollama 0.34.4 / RTX 3090.",
            "",
        ]
    missing = [k for k, v in [("EDIA baseline", edia), ("CoT ablation", cot),
                              ("multi-hop retrieval", multihop)] if v is None]
    if missing:
        lines.append(f"**Not yet run: {', '.join(missing)}.** Run the corresponding "
                     f"script (see this script's docstring) and re-render.")
    if args.graphrag is None:
        lines.append("**GraphRAG not supplied.** Pass `--graphrag <completeness>` "
                     "after running it, or keep the plan's cited fallback as-is.")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
