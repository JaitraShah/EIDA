# Task 5 — benchmark results

*Status: infrastructure complete; headline numbers pending the GPU-box build
(`RUNBOOK.md` phases A–D). This file currently reports the smoke run on the 5 gold
pairs only. Replace each ⟨pending⟩ once the full set exists.*

## Dataset

| tier | pairs | elements | gap rate | label provenance |
|---|--:|--:|--:|---|
| gold (`qmsum`) | 5 | 50 | 0.76 | hand |
| corpus (`qmsum_auto`) | ⟨~227⟩ | ⟨~4–6k⟩ | ⟨pending⟩ | nli:roberta-large-mnli @ 0.55 |
| synthetic | ⟨~2040⟩ | ⟨~18–22k⟩ | ⟨pending⟩ | constructed |

Regenerate this table with:
`python -c "from edia.benchmark.dataset import *; import json; print(json.dumps(dataset_stats(load_all('data/benchmark/pairs')),indent=2))"`

## Gap detection — smoke run (5 gold pairs, threshold 0.55)

From `outputs/gap_eval_results.json`:

| detector | P | R | F1 | acc | FN |
|---|--:|--:|--:|--:|--:|
| `nli:roberta-large-mnli` | 0.83 | 0.90 | 0.86 | 0.78 | 4 |
| `lexical:token_f1` | 0.79 | 1.00 | 0.88 | 0.80 | 0 |

Caveats for this smoke run (all resolved by the full build):

- n=50, one domain, terse fragment hypotheses from `qmsum_ground_truth` — see
  `outputs/qmsum_label_calibration.md`. The full corpus uses full sentences, which
  is Task 2's 95.5% regime.
- No `synthetic` or `qmsum_auto` rows yet, so the source/domain breakdowns are
  single-bucket.
- The `by_in_document` breakdown already shows the expected shape: NLI handles
  `omitted` well (F1 0.94) and over-flags `present_unspecified` (the precision
  cost). The `paraphrased` sub-label (n=1 here, hundreds after the synthetic build)
  is the one to watch — it is where lexical is expected to collapse and NLI to hold.

## Corpus extraction (hallucination) — ⟨pending⟩

`python scripts/run_corpus_extraction.py` → `outputs/corpus_extraction_results.md`,
per-domain evidence-grounding / strict-verbatim rates over all 232 QMSum meetings.

## Auto-label spot-check — ⟨pending⟩

`python scripts/spotcheck_report.py` → auto-vs-human gap-class P/R/F1 and
human-vs-human Jaccard/κ on a ~350-element stratified sample. This is the trust
number for the `qmsum_auto` tier.
