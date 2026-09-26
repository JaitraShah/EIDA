# Same-runtime baseline re-run (plain extractor, no CoT)

Control for the CoT ablation: the stored baseline (Table 2) came from an older Ollama/GPU. Written to outputs/extractions_rerun/; Table 2 is untouched.

| pair | re-run (lex) | re-run (sem) |
|---|--:|--:|
| QSUM_001 | 0.455 (5/11) | 0.727 (8/11) |
| QSUM_002 | 0.250 (2/8) | 0.875 (7/8) |
| QSUM_003 | 0.111 (1/9) | 0.111 (1/9) |
| QSUM_004 | 0.214 (3/14) | 0.714 (10/14) |
| QSUM_005 | 0.333 (2/6) | 0.333 (2/6) |
| **pooled** | **0.271** | **0.583** |

Stored baseline (Table 2, old runtime), pooled: lex 0.333, sem 0.583. Runtime-only shift: lex -0.062, sem +0.000.
