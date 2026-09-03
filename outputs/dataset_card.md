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

| tier | source | pairs | label provenance | feeds |
|---|---|--:|---|---|
| gold | `qmsum` | 5 | `hand` (Task 1 human validation) | gap detection **and** extraction completeness |
| corpus | `qmsum_auto` | ⟨~227⟩ | `nli:roberta-large-mnli` @ 0.55 | gap detection only (`decisions=[]`) |
| synthetic | `synthetic` | ⟨~2040⟩ | `constructed` (labels fixed before the text is written) | gap detection **and** extraction completeness |

- **QMSum corpus scope:** all 232 QMSum meetings, 3 domains (Academic 59,
  Committee 36, Product 137), all train/val/test splits, minus the 5 gold held out
  → 227 auto pairs. 1 543 `specific_query_list` answers decomposed to sentences.
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
   accuracy.** Real accuracy for this tier comes only from (a) calibration on the
   5 gold pairs (`outputs/qmsum_label_calibration.md`: F1 ≈ 0.85–0.86 on terse
   gold fragments, expected higher on the sentence-level corpus) and (b) the human
   spot-check ⟨`outputs/qmsum_spotcheck_report.json`: auto-vs-human F1 = fill,
   human-vs-human κ = fill⟩.

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
