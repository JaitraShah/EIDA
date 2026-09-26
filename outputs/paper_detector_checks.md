# Detector checks for the paper (Table 1)

## Same stratified sample, gold + synthetic (n=200, threshold 0.55)

| detector | bal acc | present F1 |
|---|--:|--:|
| nli:roberta-large-mnli | 0.611 | 0.432 |
| lexical | 0.728 | 0.637 |
| llm | 0.492 | 0.596 |
| ensemble | 0.521 | 0.624 |

## Accuracy by label, gold + synthetic only

| label | n | NLI acc | lexical acc |
|---|--:|--:|--:|
| omitted | 1017 | 0.916 | 0.974 |
| paraphrased | 453 | 0.366 | 0.640 |
| verbatim | 236 | 0.292 | 0.453 |
| present_unspecified | 11 | 0.455 | 0.182 |
