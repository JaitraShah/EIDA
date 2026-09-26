# Phase 3.1 — chain-of-thought ablation

- model: `mistral` (temperature=0), prompt: baseline + `prompts.COT_INSTRUCTION` prepended before the excerpt
- scope: the 5 gold Product/test meetings (same as Phase 2.3 -- only they have completeness ground truth)

| pair | baseline (lex) | CoT (lex) | Δ | baseline (sem) | CoT (sem) | Δ |
|---|--:|--:|--:|--:|--:|--:|
| QSUM_001 | 0.455 | 0.364 | -0.091 | 0.636 | 0.636 | +0.000 |
| QSUM_002 | 0.500 | 0.500 | +0.000 | 0.875 | 0.750 | -0.125 |
| QSUM_003 | 0.111 | 0.111 | +0.000 | 0.222 | 0.111 | -0.111 |
| QSUM_004 | 0.286 | 0.286 | -0.000 | 0.643 | 0.857 | +0.214 |
| QSUM_005 | 0.333 | 0.500 | +0.167 | 0.500 | 0.667 | +0.167 |
| **total** | **0.333** | **0.333** | **+0.000** | **0.583** | **0.625** | **+0.042** |

Totals are pooled (sum matched / sum ground truth) in every column. Baseline column reads from `outputs/task4_extraction_scores{,_semantic}.json` -- run `python scripts/run_qmsum_eval.py` and `--semantic` first if those are missing or stale.

## Same-runtime comparison (primary)

The stored baseline above was extracted on an older Ollama/GPU, so its delta mixes the CoT effect with the runtime change. Against the plain extractor re-run on the SAME runtime (`--no-cot`): lexical 0.271 -> 0.333 (**+0.062**), semantic 0.583 -> 0.625 (**+0.042**). Quote this delta.

## Reading

Semantic-scored completeness moved by **+4.2%** under CoT. A small delta (positive or negative) supports the plan's hypothesis: CoT changes how the model reasons about content already in front of it, not whether it can locate content scattered elsewhere in the meeting -- so it should not move completeness much either way. A large positive delta would need a second look before quoting it, since it would contradict the diagnosis in Table 3.
