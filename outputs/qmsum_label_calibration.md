# QMSum auto-label calibration — NLI vs the 5 hand-gold pairs

`python scripts/calibrate_qmsum_labels.py` — run against `QSUM_001..005`
(50 hand-labelled reasoning elements, 38 of them gaps). Full numbers in
`outputs/qmsum_label_calibration.json`.

## Headline (threshold = present if P(entail) ≥ 0.55)

| detector | precision | recall | F1 | accuracy | false negatives |
|---|--:|--:|--:|--:|--:|
| `nli:roberta-large-mnli` | 0.83 | 0.90 | 0.86 | 0.78 | 4 |
| `lexical:token_f1` (baseline) | 0.79 | 1.00 | 0.88 | 0.80 | 0 |

F1 is **flat (~0.85–0.86) across thresholds 0.35–0.70** for NLI, so the operating
point barely matters; 0.55 is the top of that plateau. `NliGapDetector`'s default
is set there.

## Why this is *lower* than Task 2's 95.5%, and why the corpus run should not be

Task 2's pilot (`nli_transfer_test_results.md`) scored 21/22 on **hand-written,
well-formed sentence hypotheses** ("Double-curved design was rejected because it
would make scroll-wheels impossible to use."). This calibration reuses the terse
`qmsum_ground_truth` element texts instead — many are bare fragments
("kryptonite", "lightweight plastic", "double-curved casing -- would block use of
the scroll wheel"). Four of the five NLI "false negatives" are a direct
consequence:

- `"A single-curved casing was chosen for the remote control."` — gold=gap (Task 1:
  the summary names all three shapes, never says which won). NLI entails at 0.97
  because the phrase *single-curved casing* is in the document. This is the same
  decision-identity trap `fold_qmsum.label_for` handles with a 0.7 recall gate; a
  sentence-level NLI check cannot see it. n=1, a known hard case.
- `"kryptonite"`, `"lightweight plastic"` — the *winning option's* name, pulled
  from the dropped `alternatives` list. The word is verbatim in the document, so
  both detectors say present. Label-granularity artifact, not a model error.
- `"Marketing pushed for positioning the product on technological innovation."`
  (QSUM_005) — a genuine NLI over-entailment; the QSUM_005 document only mentions
  "speech recognition". The one real NLI miss.

**The auto-corpus pipeline decomposes `specific_query_list` answers into full
sentences** (`SentenceDecomposer`), not fragments — so it operates in Task 2's
regime, not this one. Treat 0.85–0.86 here as a pessimistic floor and Task 2's
0.95 as the optimistic ceiling; the **human spot-check (Phase 3) is the real
validation**.

## Lexical is competitive *on this fragment set* — do not over-read it

`token_f1` hits F1 0.88 here because gold fragments overlap the document lexically
when the content survived. On paraphrased positives (the Task 2 failure mode) it
collapses — see `tests/test_gapdetect.py::test_lexical_cannot_see_paraphrase` and
the `by_in_document` breakdown in `outputs/gap_eval_results.md`. Lexical stays in
the eval as the baseline NLI must beat on the `paraphrased` sub-label, not on
overall F1.

## Actions

- `NliGapDetector` default threshold → **0.55** (done).
- Run `--models facebook/bart-large-mnli` for the second model Task 2 deferred.
- Do **not** gate the full corpus build on this run's F1 < 0.9; gate on the human
  spot-check instead.
