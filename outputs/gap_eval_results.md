# Gap detection — benchmark results

- threshold (present if entail/score ≥): **0.55**
- NLI model: `roberta-large-mnli`
- 371 pairs, 6647 elements

> **QMSUM_AUTO is silver.** Its labels are NLI-produced, so the `source=qmsum_auto` rows for the NLI detector measure self-consistency, not accuracy. Read `source=qmsum` (5 hand-gold) and `source=synthetic` (constructed labels) for real accuracy, plus the human spot-check.

## nli:roberta-large-mnli

**Gap class:** P=0.923 · R=0.985 · F1=0.953 · n=6647 · base rate=0.844
**Present class (the hard half):** P=0.872 · R=0.556 · F1=0.679
**Balanced accuracy: 0.771** (all-gap detector scores 0.5) · raw acc=0.918
Confusion: tp=5525 fp=460 fn=85 tn=577

### nli:roberta-large-mnli — by_source

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| qmsum | 50 | 0.76 | 0.829 | 0.895 | 0.861 | 0.417 | **0.656** |
| qmsum_auto | 4930 | 0.932 | 1.0 | 1.0 | 1.0 | 1.0 | **1.0** |
| synthetic | 1667 | 0.587 | 0.665 | 0.917 | 0.771 | 0.342 | **0.629** |

### nli:roberta-large-mnli — by_domain

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| academic | 854 | 0.946 | 1.0 | 1.0 | 1.0 | 1.0 | **1.0** |
| architecture | 117 | 0.675 | 0.745 | 0.962 | 0.84 | 0.316 | **0.639** |
| cloud_platform | 819 | 0.571 | 0.648 | 0.915 | 0.759 | 0.339 | **0.627** |
| committee | 1383 | 0.978 | 1.0 | 1.0 | 1.0 | 1.0 | **1.0** |
| data_governance | 121 | 0.628 | 0.68 | 0.895 | 0.773 | 0.289 | **0.592** |
| hiring | 121 | 0.628 | 0.69 | 0.908 | 0.784 | 0.311 | **0.61** |
| pricing_packaging | 119 | 0.571 | 0.642 | 0.897 | 0.748 | 0.333 | **0.615** |
| product | 2743 | 0.9 | 0.997 | 0.998 | 0.998 | 0.974 | **0.986** |
| release_scope | 117 | 0.556 | 0.612 | 0.923 | 0.736 | 0.269 | **0.596** |
| security_incident | 127 | 0.575 | 0.731 | 0.932 | 0.819 | 0.537 | **0.734** |
| vendor_tooling | 126 | 0.587 | 0.66 | 0.919 | 0.768 | 0.327 | **0.623** |

### nli:roberta-large-mnli — by_element_type

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| alternative | 587 | 0.78 | 0.831 | 0.989 | 0.903 | 0.287 | **0.638** |
| approver | 134 | 0.56 | 0.579 | 0.933 | 0.714 | 0.136 | **0.534** |
| condition | 340 | 0.547 | 0.664 | 0.903 | 0.765 | 0.448 | **0.676** |
| decision | 1594 | 0.83 | 0.945 | 0.998 | 0.971 | 0.716 | **0.857** |
| dissent | 284 | 0.877 | 0.931 | 0.968 | 0.949 | 0.486 | **0.727** |
| owner | 143 | 0.476 | 0.546 | 0.956 | 0.695 | 0.28 | **0.618** |
| rationale | 3565 | 0.912 | 0.975 | 0.987 | 0.981 | 0.736 | **0.861** |

### nli:roberta-large-mnli — by_in_document

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| omitted | 5610 | 1.0 | 1.0 | 0.985 | 0.992 | 0.0 | **0.492** |
| paraphrased | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.366 | **0.183** |
| present_unspecified | 348 | 0.0 | 0.0 | 0.0 | 0.0 | 0.983 | **0.491** |
| verbatim | 236 | 0.0 | 0.0 | 0.0 | 0.0 | 0.292 | **0.146** |

## lexical

**Gap class:** P=0.914 · R=0.984 · F1=0.948 · n=6647 · base rate=0.844
**Present class (the hard half):** P=0.851 · R=0.5 · F1=0.629
**Balanced accuracy: 0.742** (all-gap detector scores 0.5) · raw acc=0.908
Confusion: tp=5519 fp=519 fn=91 tn=518

### lexical — by_source

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| qmsum | 50 | 0.76 | 0.792 | 1.0 | 0.884 | 0.167 | **0.583** |
| qmsum_auto | 4930 | 0.932 | 0.954 | 0.986 | 0.97 | 0.353 | **0.669** |
| synthetic | 1667 | 0.587 | 0.766 | 0.973 | 0.857 | 0.577 | **0.775** |

### lexical — by_domain

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| academic | 854 | 0.946 | 0.972 | 0.99 | 0.981 | 0.5 | **0.745** |
| architecture | 117 | 0.675 | 0.857 | 0.987 | 0.918 | 0.658 | **0.823** |
| cloud_platform | 819 | 0.571 | 0.746 | 0.966 | 0.842 | 0.561 | **0.764** |
| committee | 1383 | 0.978 | 0.98 | 0.997 | 0.988 | 0.067 | **0.532** |
| data_governance | 121 | 0.628 | 0.791 | 0.947 | 0.862 | 0.578 | **0.763** |
| hiring | 121 | 0.628 | 0.773 | 0.987 | 0.867 | 0.511 | **0.749** |
| pricing_packaging | 119 | 0.571 | 0.756 | 1.0 | 0.861 | 0.569 | **0.784** |
| product | 2743 | 0.9 | 0.932 | 0.979 | 0.955 | 0.352 | **0.665** |
| release_scope | 117 | 0.556 | 0.739 | 1.0 | 0.85 | 0.558 | **0.779** |
| security_incident | 127 | 0.575 | 0.852 | 0.945 | 0.896 | 0.778 | **0.861** |
| vendor_tooling | 126 | 0.587 | 0.74 | 1.0 | 0.851 | 0.5 | **0.75** |

### lexical — by_element_type

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| alternative | 587 | 0.78 | 0.883 | 0.989 | 0.933 | 0.535 | **0.762** |
| approver | 134 | 0.56 | 0.578 | 0.987 | 0.729 | 0.085 | **0.536** |
| condition | 340 | 0.547 | 0.869 | 0.962 | 0.913 | 0.825 | **0.894** |
| decision | 1594 | 0.83 | 0.898 | 0.98 | 0.937 | 0.458 | **0.719** |
| dissent | 284 | 0.877 | 0.972 | 0.988 | 0.98 | 0.8 | **0.894** |
| owner | 143 | 0.476 | 0.544 | 1.0 | 0.705 | 0.24 | **0.62** |
| rationale | 3565 | 0.912 | 0.95 | 0.985 | 0.968 | 0.468 | **0.727** |

### lexical — by_in_document

| bucket | n | base rate | gap P | gap R | gap F1 | present R | **bal acc** |
|---|--:|--:|--:|--:|--:|--:|--:|
| omitted | 5610 | 1.0 | 1.0 | 0.984 | 0.992 | 0.0 | **0.492** |
| paraphrased | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.64 | **0.32** |
| present_unspecified | 348 | 0.0 | 0.0 | 0.0 | 0.0 | 0.348 | **0.174** |
| verbatim | 236 | 0.0 | 0.0 | 0.0 | 0.0 | 0.453 | **0.227** |
