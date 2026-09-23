# Corpus extraction — hallucination scoring over QMSum

- model: `mistral` (temperature=0, seed=0)
- meetings scored: 1 / 227 in scope
- completeness/recall NOT scored here (no hand ground truth beyond the 5 gold)

| domain/split | meetings | records | quotes grounded | unsupported | strict verbatim | chunks failed |
|---|--:|--:|--:|--:|--:|--:|
| Academic/train | 1 | 26 | 74/91 (81%) | 19% | 76% | 1 |
