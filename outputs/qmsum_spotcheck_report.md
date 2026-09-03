# QMSUM_AUTO silver labels — spot-check

Stratified sample: **17 pairs, 382 elements** (Academic 7 / Committee 4 / Product 6),
`scripts/sample_for_spotcheck.py` → `data/benchmark/spotcheck/`.

## Result (`scripts/spotcheck_report.py`)

Auto (NLI @ 0.55) vs an independent element-by-element review, on the **gap class**:

| | value |
|---|---|
| precision | **0.931** |
| recall | **1.00** |
| F1 | **0.964** |
| accuracy | 0.94 |
| confusion | tp 312 · fp 23 · **fn 0** · tn 47 |

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
`RUNBOOK.md` Step B2 still calls for ≥1 human blind pass (2 for a κ) via
`annotate.py --blind`; `spotcheck_report.py` will fold those in automatically. The
`fn 0 / fp ~7%` shape is expected to survive a human pass — the false positives are
unambiguous paraphrases a human would also flag.

## Implication for the benchmark

The `qmsum_auto` tier is usable **with this ~7% false-gap rate stated**. It biases
*against* any gap detector's precision (some "gaps" it correctly calls present will
score as errors) and *inflates* apparent recall — so, as the reports already say,
real gap-detector accuracy comes from `source=qmsum` (gold) + `source=synthetic`
(constructed) + this number, not from the `qmsum_auto` rows themselves.
