# Phase 3.2 — GraphRAG comparison (end-to-end)

- GraphRAG 3.2.0, default config/prompts, standard index, `local` search
- chat model `mistral` (temperature 0, seed 0, max_tokens 2048) and embeddings `nomic-embed-text`, both via Ollama
- query (plan Sec. 3.2, verbatim): "What decisions were made and what reasoning was given?"
- answer restructured into EDIA's schema by one fixed deterministic mistral call (restate-only prompt, evidence left empty); items whose content words are <80% present in the GraphRAG answer, and placeholders like 'Not specified', are dropped before scoring (the converter was seen inventing an alternative); scored with `score_extraction`
- thresholds: lexical 0.45, semantic 0.55 (identical to the EDIA baseline)

| pair | records | dropped (unsupported) | completeness (lex) | completeness (sem) | index time |
|---|--:|--:|--:|--:|--:|
| QSUM_001 | 3 | 2 | 0.000 (0/11) | 0.364 (4/11) | 368.7 s |
| QSUM_002 | 3 | 4 | 0.000 (0/8) | 0.000 (0/8) | 261.8 s |
| QSUM_003 | 6 | 13 | 0.111 (1/9) | 0.111 (1/9) | 224.0 s |
| QSUM_004 | 4 | 2 | 0.000 (0/14) | 0.000 (0/14) | 322.3 s |
| QSUM_005 | 4 | 16 | 0.167 (1/6) | 0.333 (2/6) | 420.5 s |
| **total** | | 37 | **0.042** | **0.146** | |

## Sensitivity: support filter off

With only placeholders removed (no support filter): lexical **0.042**, semantic **0.188** (vs 0.042 / 0.146 above). The filter can reject a fair one-word paraphrase as well as invented content, so the true figure lies in this range; report both. Either way GraphRAG is far below EDIA (33.3% / 58.3%).

Hallucination is not reported: the answer is a summary with no quotes to ground. The restructuring call is a possible source of error in either direction and should be stated alongside the number.

Render Table 4 with:

    python scripts/build_comparison_table.py --graphrag 0.146 --graphrag-lex 0.042 --graphrag-note "5 gold meetings, local search; 4.2% / 18.8% without the converter support filter"
