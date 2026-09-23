# Phase 3.4 — comparative analysis (Table 4)

Completeness scored against the 5 gold Product/test meetings (the only meetings with hand-built reasoning ground truth -- see Phase 2.3 scoping). Both lexical and semantic completeness are reported per the project's own rule: never pick the flattering scorer.

| approach | completeness (lex) | completeness (sem) | hallucination | core failure reason |
|---|--:|--:|--:|---|
| EDIA pipeline | 33.3% | 58.3% | 16.4% | Multi-hop across chunks (Table 3) |
| EDIA + CoT | not run | not run | not run | CoT helps reasoning at answer time, not retrieval |
| GraphRAG | — | not run | — | Designed for static structured text, not conversational multi-speaker data; not run end-to-end here -- see EDIA_Project_Plan_v2.md Sec. 3.2 for the cited-argument fallback (external GraphRAG benchmarks report ~13% on conversational tasks) |
| Multi-hop retrieval | — | 12.2% | 0 (retrieves, does not generate) | Chain unknown in advance -- hop 1 fails before hop 2 can compound it |

**Not yet run: CoT ablation.** Run the corresponding script (see this script's docstring) and re-render.
**GraphRAG not supplied.** Pass `--graphrag <completeness>` after running it, or keep the plan's cited fallback as-is.
