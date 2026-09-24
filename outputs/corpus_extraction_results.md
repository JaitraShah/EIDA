# Corpus extraction — hallucination scoring over QMSum

- model: `mistral` (temperature=0, seed=0)
- meetings scored: 227 / 227 in scope
- completeness/recall NOT scored here (no hand ground truth beyond the 5 gold)

| domain/split | meetings | records | quotes grounded | unsupported | strict verbatim | chunks failed |
|---|--:|--:|--:|--:|--:|--:|
| Academic/test | 9 | 321 | 729/986 (74%) | 26% | 65% | 3 |
| Academic/train | 41 | 1244 | 3153/4334 (73%) | 27% | 65% | 22 |
| Academic/val | 9 | 299 | 763/1021 (75%) | 25% | 67% | 4 |
| Committee/test | 6 | 368 | 936/969 (97%) | 3% | 97% | 1 |
| Committee/train | 24 | 1476 | 3341/3535 (94%) | 6% | 94% | 3 |
| Committee/val | 6 | 386 | 885/937 (94%) | 6% | 94% | 0 |
| Product/test | 15 | 300 | 1237/1356 (91%) | 9% | 87% | 0 |
| Product/train | 97 | 1813 | 6159/7095 (87%) | 13% | 82% | 2 |
| Product/val | 20 | 395 | 1549/1716 (90%) | 10% | 85% | 1 |
