# Extraction precision and F1 (5 gold meetings)

Same units, matchers and thresholds as completeness (lexical token-F1 @ 0.45, semantic MiniLM @ 0.55). Recall = completeness, recomputed and checked against the published figure for every row. **Precision is a lower bound**: the hand labels are not exhaustive, so a correct element the annotator did not list counts as wrong.

| approach | extracted elements | P (lex) | R (lex) | F1 (lex) | P (sem) | R (sem) | F1 (sem) |
|---|--:|--:|--:|--:|--:|--:|--:|
| EDIA pipeline | 398 | 4.8% | 33.3% | 8.4% | 13.8% | 58.3% | 22.3% |
| EDIA pipeline, same runtime | 346 | 4.9% | 27.1% | 8.3% | 13.6% | 58.3% | 22.0% |
| EDIA + chain-of-thought | 438 | 3.2% | 33.3% | 5.8% | 10.7% | 62.5% | 18.3% |
| GraphRAG (support filter on) | 52 | 3.8% | 4.2% | 4.0% | 13.5% | 14.6% | 14.0% |
| GraphRAG (support filter off) | 75 | 2.7% | 4.2% | 3.3% | 12.0% | 18.8% | 14.6% |
| Multi-hop retrieval (excl. decisions) | 27 | 0.0% | 0.0% | 0.0% | 40.7% | 12.8% | 19.5% |

## Redundancy-penalised precision

Distinct hand-labelled elements matched / extracted elements: a repeated copy of an element already found earns nothing. The gap from plain precision is how much of the output is duplicates of correct items.

| approach | lex | sem |
|---|--:|--:|
| EDIA pipeline | 4.0% | 7.0% |
| EDIA pipeline, same runtime | 3.8% | 8.1% |
| EDIA + chain-of-thought | 3.7% | 6.8% |
| GraphRAG (support filter on) | 3.8% | 13.5% |
| GraphRAG (support filter off) | 2.7% | 12.0% |
| Multi-hop retrieval (excl. decisions) | 0.0% | 18.5% |
