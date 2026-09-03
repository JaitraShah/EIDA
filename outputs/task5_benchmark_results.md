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

## The base-rate problem — read this before quoting any headline F1

Corpus-wide run (`outputs/gap_eval_results.md`, lexical detector, 236 pairs /
5 027 elements, threshold 0.45):

| | value |
|---|--:|
| overall gap-class F1 | **0.964** |
| gap base rate | **0.927** |
| F1 an *all-gap* detector would score | **0.962** |

**The headline is worth almost nothing.** A detector that blindly answered "gap"
to every element scores 0.962; lexical token-overlap scores 0.964. This is the
same trap `agreement.py` already guards for on the annotation side, and the gap
report now prints an explicit base-rate warning whenever a bucket exceeds 0.85.

What the breakdowns actually show:

| `by_in_document` | n | accuracy |
|---|--:|--:|
| omitted | 4 661 | 0.970 |
| present_unspecified | 348 | **0.448** |
| verbatim | 8 | 0.500 |
| paraphrased | 10 | 0.800 |

Lexical is good at gaps and **worse than a coin flip at recognising present
elements**. The overall number hides that completely because 93% of elements are
gaps.

| `by_source` | n | base rate | F1 |
|---|--:|--:|--:|
| qmsum_auto | 4 930 | 0.932 | 0.966 |
| qmsum (gold) | 50 | 0.760 | 0.892 |
| synthetic | 47 | **0.638** | **0.793** |

F1 falls monotonically as the base rate falls. **The synthetic tier is the only
part of the benchmark balanced enough to separate detectors** — which is the
argument for finishing the ~2040-pair generation, and the reason the QMSum tiers
alone would have produced a flattering, meaningless result.

Three consequences for how this benchmark gets reported:

1. Never quote a QMSum-tier F1 without the base rate beside it.
2. Score on the **present** class as well as the gap class, or report balanced
   accuracy — the gap class alone is nearly free.
3. Detector comparison (NLI vs lexical vs LLM) is only meaningful on the
   synthetic tier and the `by_in_document` present rows.

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

`qmsum_auto` element types are a cue-word heuristic, and the heuristic's coverage
was measured rather than assumed (`scripts/retype_qmsum_elements.py` →
`outputs/qmsum_element_type_coverage.json`):

| | |
|---|--:|
| elements | 4 930 |
| matched an actual cue | 1 030 (**20.9%**) |

Distribution after a cue-rule pass (old → new): rationale 3 323→3 174,
decision 1 445→1 446, alternative 87→149, condition 20→76, dissent 49→79,
owner 4, approver 2.

The improvement is real but small, and that is the finding, not a bug: **QMSum
specific-query answers are narrative meeting summaries** — findings, descriptions,
procedural notes — not structured decision reasoning, so most sentences genuinely
are not an alternative, a dissent or a condition. Two consequences to carry:

- `rationale` on this tier means *"reasoning-ish narrative, unclassified"*, not
  *"a stated reason"*.
- most of the `decision` count comes from the positional first-sentence-of-answer
  rule, not from a cue.

So read the by-element-type breakdown for `qmsum_auto` as **indicative only**. The
synthetic tier is where element types are trustworthy — there they come from a
typed spec, not a guess. `decompose.LlmDecomposer` (a mistral pass) is the fix if
the breakdown ever needs to be load-bearing on the QMSum side.
