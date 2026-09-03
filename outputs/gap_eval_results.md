# Gap detection — benchmark results

- threshold (present if entail/score ≥): **0.45**
- 236 pairs, 5027 elements

> **QMSUM_AUTO is silver.** Its labels are NLI-produced, so the `source=qmsum_auto` rows for the NLI detector measure self-consistency, not accuracy. Read `source=qmsum` (5 hand-gold) and `source=synthetic` (constructed labels) for real accuracy, plus the human spot-check.

## lexical

**Overall (gap class):** P=0.958 · R=0.97 · F1=0.964 · acc=0.933 · n=5027 · base rate=0.927
Confusion: tp=4522 fp=198 fn=139 tn=168

> **Base-rate warning.** 93% of these elements are gaps, so a detector that called *everything* a gap would already score F1 0.962. Read the `by_in_document` table below (accuracy on the *present* rows) and the balanced `source=synthetic` rows, not this headline.

### lexical — by_source

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| qmsum | 50 | 0.76 | 0.822 | 0.974 | 0.892 | 0.82 |
| qmsum_auto | 4930 | 0.932 | 0.96 | 0.971 | 0.966 | 0.936 |
| synthetic | 47 | 0.638 | 0.821 | 0.767 | 0.793 | 0.745 |

### lexical — by_domain

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| academic | 854 | 0.946 | 0.973 | 0.98 | 0.977 | 0.956 |
| cloud_platform | 47 | 0.638 | 0.821 | 0.767 | 0.793 | 0.745 |
| committee | 1383 | 0.978 | 0.98 | 0.992 | 0.986 | 0.973 |
| product | 2743 | 0.9 | 0.943 | 0.957 | 0.95 | 0.909 |

### lexical — by_element_type

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| alternative | 184 | 0.902 | 0.947 | 0.97 | 0.958 | 0.924 |
| approver | 8 | 0.875 | 0.875 | 1.0 | 0.933 | 0.875 |
| condition | 87 | 0.931 | 0.963 | 0.951 | 0.957 | 0.92 |
| decision | 1459 | 0.898 | 0.944 | 0.956 | 0.95 | 0.91 |
| dissent | 87 | 0.966 | 1.0 | 0.988 | 0.994 | 0.989 |
| owner | 8 | 0.625 | 0.625 | 1.0 | 0.769 | 0.625 |
| rationale | 3194 | 0.942 | 0.965 | 0.976 | 0.97 | 0.944 |

### lexical — by_in_document

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| omitted | 4661 | 1.0 | 1.0 | 0.97 | 0.985 | 0.97 |
| paraphrased | 10 | 0.0 | 0.0 | 0.0 | 0.0 | 0.8 |
| present_unspecified | 348 | 0.0 | 0.0 | 0.0 | 0.0 | 0.448 |
| verbatim | 8 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5 |
