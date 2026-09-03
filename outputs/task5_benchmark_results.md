# Task 5 — benchmark results

*Status: QMSum tier built and validated. Synthetic tier generating (~5 min/pair on
the current box → runs beyond one session). Full-corpus gap eval and corpus
extraction pending the GPU box. ⟨pending⟩ marks numbers that need those runs.*

## Dataset (current)

| tier | source | pairs | elements | gap rate | label provenance |
|---|---|--:|--:|--:|---|
| gold | `qmsum` | 5 | 50 | 0.76 | hand (Task 1) |
| corpus | `qmsum_auto` | 227 | 4 930 | 0.93 | nli:roberta-large-mnli @ 0.55 |
| synthetic | `synthetic` | in progress (target ~2040) | — | — | constructed |

QMSum corpus: all 232 meetings, 3 domains (Academic 59 / Committee 36 / Product 137),
all splits, 5 gold held out. 1 543 specific-query answers → 4 930 sentence elements.

## Auto-label validation

**Threshold** (`outputs/qmsum_threshold_tuning.json`): entail-score distribution is
sharply bimodal (median 0.004, 74% below 0.02). Corpus gap rate moves only
0.86→0.93 across thresholds 0.1–0.55; lowering it to hit a "plausible" band costs
gold F1. **0.55 kept** — best agreement with human labels; the 0.93 rate reflects a
genuine ~5:1 sentence-level compression, not a tunable artifact.

**Spot-check** (`outputs/qmsum_spotcheck_report.md`) — 17 pairs / 382 elements,
auto vs an independent review, gap class:

| precision | recall | F1 | fn | fp |
|--:|--:|--:|--:|--:|
| 0.931 | 1.00 | 0.964 | 0 | 23 (~7%) |

The silver labels never under-call a gap; ~7% of predicted gaps are
paraphrase-present false positives (Task 2's known failure, quantified). A human
blind pass (RUNBOOK B2) is still needed to finalise this.

## Gap detection — 5 gold pairs (the non-circular numbers)

`outputs/gap_eval_results_gold.md`, threshold 0.55:

| detector | P | R | F1 | acc | FN |
|---|--:|--:|--:|--:|--:|
| `nli:roberta-large-mnli` | 0.83 | 0.90 | 0.86 | 0.78 | 4 |
| `lexical:token_f1` | 0.79 | 1.00 | 0.88 | 0.80 | 0 |

On the terse gold-fragment hypotheses lexical edges NLI on overall F1; NLI's
advantage is on paraphrased-present elements, which this 50-element gold set has
only one of. That comparison needs the synthetic tier (hundreds of `paraphrased`
labels) to be meaningful — see `by_in_document` in the full report once it exists.

## Pending (GPU box — `RUNBOOK.md`)

- **Full-corpus gap eval** (`run_gap_eval.py` over all 232 + synthetic): ~5 000
  elements × NLI; on this box it contends with generation. Run solo or on the GPU
  box. Report will carry the `by_source` / `by_domain` / `by_element_type` /
  `by_in_document` breakdowns; the `qmsum_auto` NLI row is self-consistency, not
  accuracy (the renderer says so).
- **LLM-entailment ablation** (`--detectors llm --llm-sample 400`).
- **Corpus extraction** (`run_corpus_extraction.py`) → `corpus_extraction_results.md`.
- **Synthetic**: finish the ~2040-pair run, then `dedupe_synthetic.py`.
- **Human blind spot-check pass** → refined auto-label F1 + κ.

## Known caveat carried into every number

`qmsum_auto` element types are a cue-word heuristic and came out badly skewed
(rationale 3 334, decision 1 454, alternative 108, dissent 52, condition 24) — QMSum
summary prose lacks the cue phrases. The per-element-type breakdown for that tier
is indicative only; `decompose.LlmDecomposer` (a mistral pass) is the fix if the
breakdown needs to be load-bearing.
