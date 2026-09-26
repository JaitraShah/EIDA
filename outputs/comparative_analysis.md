# Phase 3.4 — comparative analysis (Table 4)

Completeness scored against the 5 gold Product/test meetings (the only meetings with hand-built reasoning ground truth -- see Phase 2.3 scoping). Both lexical and semantic completeness are reported per the project's own rule: never pick the flattering scorer.

| approach | completeness (lex) | completeness (sem) | hallucination | core failure reason |
|---|--:|--:|--:|---|
| EDIA pipeline | 33.3% | 58.3% | 16.4% | Multi-hop across chunks (Table 3) |
| EDIA pipeline, re-run on the CoT/GraphRAG runtime | 27.1% | 58.3% | 14.1% | Same method; the runtime change alone moves lexical completeness |
| EDIA + CoT | 33.3% | 62.5% | 13.9% | CoT helps reasoning at answer time, not retrieval |
| GraphRAG | 4.2% | 14.6% | — | Designed for static structured text, not conversational multi-speaker data (5 gold meetings, local search; 4.2% / 18.8% without the converter support filter) |
| Multi-hop retrieval | — | 12.2% | 0 (retrieves, does not generate) | Chain unknown in advance -- hop 1 fails before hop 2 can compound it |

**Runtimes.** The first EDIA row (Table 2) was extracted on Ollama 0.32.1 / RTX 3050; EDIA + CoT, GraphRAG and the EDIA re-run on Ollama 0.34.4 / RTX 3090 (same model and settings). Compare CoT and GraphRAG against the **re-run** row: CoT's same-runtime effect is +6.2% lexical / +4.2% semantic.

