# Task 2 — NLI Transfer Test Results

**Model:** `roberta-large-mnli` (pretrained, no fine-tuning)
**Test set:** 22 reasoning elements across the 5 validated pairs from Task 1 (`gap_validation_results.md`)
**Setup:** premise = general-summary text (our "document" proxy), hypothesis = one reasoning
element at a time. ENTAILMENT → present (no gap). NEUTRAL or CONTRADICTION → gap detected.
Full per-item output: `nli_results.json` (attached alongside this report).

## Results table

| Meeting | Manual label | Model label | Confidence | Match? |
|---|---|---|---|---|
| M5 | Gap | NEUTRAL | 0.992 | ✅ |
| M5 | Gap | NEUTRAL | 0.778 | ✅ |
| M5 | Gap | NEUTRAL | 0.869 | ✅ |
| M5 | Gap | NEUTRAL | 0.826 | ✅ |
| M5 | Present | ENTAILMENT | 0.992 | ✅ |
| M7 | Present | ENTAILMENT | 0.990 | ✅ |
| M7 | Gap | NEUTRAL | 0.976 | ✅ |
| M7 | Gap | NEUTRAL | 0.897 | ✅ |
| M7 | Present | ENTAILMENT | 0.988 | ✅ |
| M7 | Gap | NEUTRAL | 0.892 | ✅ |
| M9 | Present | ENTAILMENT | 0.980 | ✅ |
| M9 | Present | ENTAILMENT | 0.932 | ✅ |
| M9 | Gap | NEUTRAL | 0.870 | ✅ |
| M9 | Present | ENTAILMENT | 0.989 | ✅ |
| M10 | Present | ENTAILMENT | 0.987 | ✅ |
| M10 | Gap | NEUTRAL | 0.980 | ✅ |
| M10 | **Present** | **NEUTRAL** | 0.984 | ❌ |
| M10 | Gap | NEUTRAL | 0.997 | ✅ |
| M12 | Present | ENTAILMENT | 0.984 | ✅ |
| M12 | Gap | NEUTRAL | 0.973 | ✅ |
| M12 | Gap | NEUTRAL | 0.543 | ✅ |
| M12 | Gap | NEUTRAL | 0.961 | ✅ |

## Overall accuracy: **21/22 = 95.5%**

- **False positives** (model said gap, was actually present): 1
- **False negatives** (model missed a real gap): 0

## The one failure, in detail

Element: *"Wood was chosen as material instead of plastic."*
Document text: *"the industrial designer suggested using wood... which was agreed by the group."*

The content is present, but the phrasing differs ("chose" vs. "suggested... agreed by the group") —
this looks like a **paraphrase-sensitivity** failure rather than a true content gap. RoBERTa-MNLI is
comparatively literal about surface wording when the premise doesn't use the same verb structure as
the hypothesis. Worth flagging because it's the failure mode most likely to recur at scale: a
document that documents a decision using different words than the discussion used will look like a
false gap.

## Where the model struggled

Only one clear failure in 22 checks, and it's a paraphrase-mismatch case, not a reasoning failure —
the model correctly separated substance (rationale, rejected alternatives, conditions) from mere
topic-mentions in every other case, including a genuinely subtle one: the LCD/chip-cost element in
M12 was correctly flagged as a gap but at a much lower confidence (0.543) than every other
correct call, suggesting the model is less sure on multi-hop reasoning (LCD → advanced chip →
cost) than on single-fact entailment. Zero false negatives across 13 true gaps is the important
number for our use case — the model never missed a real gap; it only occasionally over-flagged.

## Fallback threshold decision (per Task 2 spec)

- Below 60% → LLM-based entailment primary, NLI as ablation
- 60–75% → NLI primary, tune confidence threshold
- **Above 75% → NLI as primary gap detection method** ← **this path applies (95.5%)**

**Decision: proceed with `roberta-large-mnli` (or a comparably-sized NLI model) as the primary gap
detection mechanism**, not just an ablation baseline. This is a stronger result than the team's
48-hour validation plan assumed as a baseline case. Two caveats to carry into the benchmark
(Task 5) design:

1. **Test on `facebook/bart-large-mnli` too** before finalizing (per original task spec) — not yet
   done in this run due to time budget; one model tested is a proof of transfer, not model selection.
2. **The paraphrase-mismatch failure mode should be built into the benchmark's negative examples**
   deliberately — include "present but reworded" cases, not just verbatim-vs-omitted cases, so the
   evaluated method doesn't look artificially strong against phrasing it was accidentally tuned to.

## Caveat on sample size

n=22 across 5 meetings, one domain (Product/AMI-style). This is exactly the scale Task 2 asked for
as a diagnostic transfer test — it tells us the mechanism transfers, not the exact production
accuracy rate. That number comes from the 50+ pair benchmark (Task 5).
