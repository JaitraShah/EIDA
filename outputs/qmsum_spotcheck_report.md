# QMSUM_AUTO silver labels — spot-check (model review, not a human)

> The comparison pass in this report is an LLM-assisted review (`llm-review`). It is
> not human validation; see `outputs/qmsum_spotcheck_mini_report.json` for the human check.

Stratified sample: **17 pairs, 382 elements** (Academic 7 / Committee 4 / Product 6),
`scripts/sample_for_spotcheck.py` → `data/benchmark/spotcheck/`.

## Result (`scripts/spotcheck_report.py`)

Auto (NLI @ 0.55) vs an independent element-by-element review, on the **gap class**:

| | value |
|---|---|
| gap-class precision | **0.931** |
| gap-class recall | **1.00** |
| gap-class F1 | **0.964** |
| present-class recall | 0.671 |
| **balanced accuracy** | **0.836** |
| confusion | tp 312 · fp 23 · **fn 0** · tn 47 |

Read the balanced accuracy, not the gap F1: this sample is 82% gaps, so gap-class
F1 alone would flatter any labeller (see the base-rate section of
`outputs/task5_benchmark_results.md`). 0.836 against a 0.5 floor is a real result;
the gap between it and 1.0 is the ~33% of genuinely-present elements the labeller
called gaps.

- **Zero false negatives**: the auto labeller never marked a real gap as present.
  The labels are conservative in the safe direction.
- **23 false positives (~7% of predicted gaps)**: elements the summary *did* keep,
  reworded, that NLI scored as NEUTRAL. Every disagreement is this one direction.
  Examples: `"technologically innovative"` vs the summary's `"innovative
  technology"`; `"easy to use"` vs `"user-friendliness"`; `"sports infrastructure
  in schools"` present near-verbatim but scored a gap. This is exactly Task 2's
  documented paraphrase-sensitivity failure, now quantified at corpus scale.
- Worst pairs: `QMS_PRD_TR_089` (4/28 — the three marketing points are in the
  summary verbatim-ish), `QMS_PRD_TR_050` (3/24). Best: the meta-summary Committee
  pairs (`QMS_CMT_TR_006` 0/63) where the document genuinely keeps nothing.

## Caveat on the review pass

The comparison pass here was an **LLM-assisted read of document-vs-elements**, not a
human blind annotation. It is a sanity cross-check, not the definitive number.
A human blind pass was done afterwards on a smaller sample
(`outputs/qmsum_spotcheck_mini_report.json`: 52 elements, gap precision 0.478, balanced
accuracy 0.60). It found a much higher false-gap rate than this model pass, so the `fp ~7%`
here should not be relied on.

## Implication for the benchmark

The `qmsum_auto` tier is usable **with this ~7% false-gap rate stated**. It biases
*against* any gap detector's precision (some "gaps" it correctly calls present will
score as errors) and *inflates* apparent recall — so, as the reports already say,
real gap-detector accuracy comes from `source=qmsum` (gold) + `source=synthetic`
(constructed) + this number, not from the `qmsum_auto` rows themselves.
