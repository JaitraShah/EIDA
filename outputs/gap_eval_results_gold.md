# Gap detection — benchmark results

- threshold (present if entail/score ≥): **0.55**
- NLI model: `roberta-large-mnli`
- 5 pairs, 50 elements

> **QMSUM_AUTO is silver.** Its labels are NLI-produced, so the `source=qmsum_auto` rows for the NLI detector measure self-consistency, not accuracy. Read `source=qmsum` (5 hand-gold) and `source=synthetic` (constructed labels) for real accuracy, plus the human spot-check.

## nli:roberta-large-mnli

**Overall (gap class):** P=0.829 · R=0.895 · F1=0.861 · acc=0.78 · n=50 · base rate=0.76
Confusion: tp=34 fp=7 fn=4 tn=5

### nli:roberta-large-mnli — by_source

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| qmsum | 50 | 0.76 | 0.829 | 0.895 | 0.861 | 0.78 |

### nli:roberta-large-mnli — by_domain

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| product | 50 | 0.76 | 0.829 | 0.895 | 0.861 | 0.78 |

### nli:roberta-large-mnli — by_element_type

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| alternative | 21 | 0.714 | 0.765 | 0.867 | 0.812 | 0.714 |
| approver | 2 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| condition | 4 | 0.75 | 0.75 | 1.0 | 0.857 | 0.75 |
| decision | 9 | 0.444 | 0.6 | 0.75 | 0.667 | 0.667 |
| dissent | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| rationale | 11 | 1.0 | 1.0 | 0.909 | 0.952 | 0.909 |

### nli:roberta-large-mnli — by_in_document

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| omitted | 38 | 1.0 | 1.0 | 0.895 | 0.944 | 0.895 |
| paraphrased | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| present_unspecified | 11 | 0.0 | 0.0 | 0.0 | 0.0 | 0.455 |

## lexical

**Overall (gap class):** P=0.792 · R=1.0 · F1=0.884 · acc=0.8 · n=50 · base rate=0.76
Confusion: tp=38 fp=10 fn=0 tn=2

### lexical — by_source

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| qmsum | 50 | 0.76 | 0.792 | 1.0 | 0.884 | 0.8 |

### lexical — by_domain

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| product | 50 | 0.76 | 0.792 | 1.0 | 0.884 | 0.8 |

### lexical — by_element_type

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| alternative | 21 | 0.714 | 0.75 | 1.0 | 0.857 | 0.762 |
| approver | 2 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| condition | 4 | 0.75 | 0.75 | 1.0 | 0.857 | 0.75 |
| decision | 9 | 0.444 | 0.5 | 1.0 | 0.667 | 0.556 |
| dissent | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| rationale | 11 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

### lexical — by_in_document

| bucket | n | base rate | P | R | F1 | acc |
|---|--:|--:|--:|--:|--:|--:|
| omitted | 38 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| paraphrased | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| present_unspecified | 11 | 0.0 | 0.0 | 0.0 | 0.0 | 0.182 |
