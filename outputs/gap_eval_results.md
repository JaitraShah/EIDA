# Gap detection — benchmark results

- threshold (present if entail/score ≥): **0.45**
- 238 pairs, 5050 elements

> **QMSUM_AUTO is silver.** Its labels are NLI-produced, so the `source=qmsum_auto` rows for the NLI detector measure self-consistency, not accuracy. Read `source=qmsum` (5 hand-gold) and `source=synthetic` (constructed labels) for real accuracy, plus the human spot-check.

## lexical

**Gap class:** P=0.957 · R=0.97 · F1=0.963 · n=5050 · base rate=0.925
**Present class (the hard half):** P=0.553 · R=0.459 · F1=0.501
**Balanced accuracy: 0.714** (all-gap detector scores 0.5) · raw acc=0.932
Confusion: tp=4533 fp=204 fn=140 tn=173

> **Base-rate warning.** 92% of these elements are gaps, so a detector that called *everything* a gap would already score F1 0.961. Read the `by_in_document` table below (accuracy on the *present* rows) and the balanced `source=synthetic` rows, not this headline.

### lexical — by_source

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| qmsum | 50 | 0.76 | 0.822 | 0.974 | 0.892 | 0.333 | **0.654** |
| qmsum_auto | 4930 | 0.932 | 0.96 | 0.971 | 0.966 | 0.451 | **0.711** |
| synthetic | 70 | 0.6 | 0.756 | 0.81 | 0.782 | 0.607 | **0.708** |

### lexical — by_domain

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| academic | 854 | 0.946 | 0.973 | 0.98 | 0.977 | 0.522 | **0.751** |
| cloud_platform | 70 | 0.6 | 0.756 | 0.81 | 0.782 | 0.607 | **0.708** |
| committee | 1383 | 0.978 | 0.98 | 0.992 | 0.986 | 0.1 | **0.546** |
| product | 2743 | 0.9 | 0.943 | 0.957 | 0.95 | 0.473 | **0.715** |

### lexical — by_element_type

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| alternative | 190 | 0.889 | 0.942 | 0.964 | 0.953 | 0.524 | **0.744** |
| approver | 10 | 0.8 | 0.8 | 1.0 | 0.889 | 0.0 | **0.5** |
| condition | 90 | 0.911 | 0.963 | 0.951 | 0.957 | 0.625 | **0.788** |
| decision | 1461 | 0.897 | 0.943 | 0.956 | 0.95 | 0.497 | **0.727** |
| dissent | 90 | 0.967 | 1.0 | 0.989 | 0.994 | 1.0 | **0.994** |
| owner | 10 | 0.5 | 0.5 | 1.0 | 0.667 | 0.0 | **0.5** |
| rationale | 3199 | 0.942 | 0.965 | 0.976 | 0.97 | 0.422 | **0.699** |

### lexical — by_in_document

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| omitted | 4673 | 1.0 | 1.0 | 0.97 | 0.985 | 0.0 | **0.485** |
| paraphrased | 17 | 0.0 | 0.0 | 0.0 | 0.0 | 0.765 | **0.382** |
| present_unspecified | 348 | 0.0 | 0.0 | 0.0 | 0.0 | 0.448 | **0.224** |
| verbatim | 12 | 0.0 | 0.0 | 0.0 | 0.0 | 0.333 | **0.167** |
