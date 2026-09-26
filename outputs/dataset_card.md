# EDIA gap-detection benchmark — dataset card

*Numbers marked ⟨fill after build⟩ are produced by the GPU-box runs in `RUNBOOK.md`.
Everything else is fixed by construction.*

## What a pair is

One `BenchmarkPair` (`edia/benchmark/dataset.py`): a meeting **transcript**, the
short filed **document** that is supposed to summarise it, a list of reasoning
**elements** from the discussion, and for each element an `in_document` label —
`omitted` (the document dropped it = a gap), `verbatim`, `paraphrased`, or
`present_unspecified`. `element.gold_gap` (label is `omitted`) is what a gap
detector is scored on.

## Composition

| tier | source | pairs | elements | gap rate | label provenance | feeds |
|---|---|--:|--:|--:|---|---|
| gold | `qmsum` | 5 | 50 | 0.76 | `hand` (Task 1 human validation) | gap detection **and** extraction completeness |
| corpus | `qmsum_auto` | 227 | 4 930 | 0.93 | `nli:roberta-large-mnli` @ 0.55 | gap detection only (`decisions=[]`) |
| synthetic | `synthetic` | 139 (locked; plan target was ~2040) | 1 667 | 0.59 | `constructed` (labels fixed before the text is written) | gap detection **and** extraction completeness |

- **QMSum corpus scope:** all 232 QMSum meetings, 3 domains (Academic 59,
  Committee 36, Product 137), all train/val/test splits, minus the 5 gold held out
  → 227 auto pairs. 1 543 `specific_query_list` answers → 4 930 sentence elements.
- **Element types on `qmsum_auto` are weak by measurement, not assumption**: only
  **20.9%** of sentences match a reasoning cue
  (`outputs/qmsum_element_type_coverage.json`). QMSum answers are narrative
  summaries, so `rationale` here means "unclassified narrative" and most
  `decision` labels come from a positional first-sentence rule. Read the
  by-element-type breakdown for this tier as indicative only.
- **Spot-check.** Two passes exist; only the second is human.
  - *Model pass, not validation* (17 pairs / 382 elements, annotator `llm-review`,
    `outputs/qmsum_spotcheck_report.md`): balanced accuracy 0.836, ~7% false-positive
    gaps. Do not cite as validation.
  - *Human pass* (1 annotator, blind, 52 elements / 3 pairs,
    `outputs/qmsum_spotcheck_mini_report.json`): gap recall 1.0 but gap precision
    **0.478**, present recall 0.20, **balanced accuracy 0.60** — 24 of 46 silver gaps
    were judged present (23 paraphrases). The silver labels substantially over-call
    gaps; treat corpus gap rates as upper bounds.
- **Synthetic scope:** 12 organisational domains × 10 decision archetypes = 120
  topics × 17 variants. Per-pair scenario colour + temperature jitter (0.7–0.95)
  to resist mode collapse; near-duplicates flagged post-hoc
  (`scripts/dedupe_synthetic.py`).

## Label provenance — read before quoting any number

Three different label sources, three different trust levels:

1. **`hand` (5 pairs)** — human, cross-checked against raw transcript spans in
   Task 1. The trust anchor. Small (n=5, one domain) — a regression fixture, not
   an accuracy estimate.
2. **`constructed` (synthetic)** — the label is *decided before either text is
   written* (`generate.py`): pick elements → assign omitted/verbatim/paraphrased →
   write the discussion with all of them → write the document with only the
   survivors → automated leak-check. The human pass is verification, which is why
   agreement on it is meaningful.
3. **`nli:...` (qmsum_auto) — SILVER.** Produced by the NLI detector. **Scoring
   that same detector against these labels measures self-consistency, not
   accuracy.** Real accuracy for this tier: (a) calibration on the 5 gold pairs
   (`outputs/qmsum_label_calibration.md`: gold F1 ≈ 0.86 on terse fragments;
   threshold 0.55 chosen against both gold F1 and the corpus gap-rate sweep), and
   (b) the human blind spot-check (`outputs/qmsum_spotcheck_mini_report.json`:
   52 elements, gap precision 0.478, balanced accuracy 0.60 — about half of silver
   gaps are paraphrase-present content). The earlier `llm-review` pass
   (F1 0.964, fp ~7%) was a model pass and is superseded.

## Known limitations (carried forward + new)

- **Auto-label circularity** (new): as above — every report separates
  `source=qmsum_auto` NLI rows and calls them consistency, not accuracy.
- **`element_type` on qmsum_auto is a cue-word heuristic** — the by-element-type
  breakdown for that tier is indicative only.
- **qmsum_auto pairs carry no `DecisionRecord`s** → excluded from
  extraction-completeness scoring by design (`has_reasoning_ground_truth` is False).
- **QMSum "documents" are annotator-written general summaries** standing in for
  filed decision records — Task 1's substitution, unchanged.
- **Synthetic transcripts are mistral-written** and cleaner than real meetings
  (fewer disfluencies, tighter turns). The QMSum tiers are in the same schema so a
  method that only works on the tidy half is visible.
- **Sentence decomposition under-segments compound clauses** ("rejected because of
  cost and localisation burden" → one unit, not two). Visible to the spot-check;
  fixable by swapping in `LlmDecomposer` with no schema change.
- **n=5 hand-gold, one domain** — the whole reason the corpus + synthetic tiers exist.

## Versions

- Extraction wire schema: `SCHEMA_VERSION = 1.0.0` (frozen, SHA-pinned — untouched
  by this work).
- Benchmark schema: `DATASET_VERSION = 1.1.0` (added `PairSource.QMSUM_AUTO`,
  `BenchmarkPair.label_provenance`).
- Synthetic prompts: `PROMPT_VERSION = synth-v2`.
