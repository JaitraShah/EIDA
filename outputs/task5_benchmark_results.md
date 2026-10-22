# Benchmark results — edia_db

*Dataset locked at `edia_db`. All phases complete as of 2026-09-26: gap detection
(NLI, lexical, LLM, ensemble), extraction on the 5 gold meetings and corpus-wide,
the comparative analysis, and a human mini spot-check. The paper draft is in
`paper/`; `paper/NUMBERS.md` maps every paper number to its source file.*

## Dataset

| tier | source | pairs | elements | gap rate | label provenance |
|---|---|--:|--:|--:|---|
| gold | `qmsum` | 5 | 50 | 0.76 | hand (Task 1) |
| corpus | `qmsum_auto` | 227 | 4 930 | 0.93 | nli:roberta-large-mnli @ 0.55 |
| synthetic | `synthetic` | 139 | 1 667 | 0.59 | constructed |
| **total** | | **371** | **6 647** | 0.844 | |

QMSum corpus: all 232 meetings, 3 domains (Academic 59 / Committee 36 /
Product 137), all splits, 5 gold held out.

---

## Table 1 — gap detection, by tier

Threshold 0.55. `bal acc` is the mean of gap-recall and present-recall: an
all-gap detector scores 0.5 no matter how skewed the data is.

| detector | tier | n | base rate | gap F1 | **bal acc** | present F1 |
|---|---|--:|--:|--:|--:|--:|
| NLI | gold | 50 | 0.760 | 0.861 | **0.656** | 0.476 |
| NLI | corpus | 4 930 | 0.932 | ~~1.000~~ | ~~1.000~~ | ~~1.000~~ |
| NLI | **synthetic** | 1 667 | 0.587 | 0.771 | **0.629** | 0.468 |
| lexical | gold | 50 | 0.760 | 0.884 | **0.583** | 0.286 |
| lexical | corpus | 4 930 | 0.932 | 0.970 | **0.669** | 0.457 |
| lexical | **synthetic** | 1 667 | 0.587 | 0.857 | **0.775** | 0.715 |

**The struck-through row is not a result.** The corpus labels *were produced by*
`nli @ 0.55`, so scoring NLI against them at the same threshold is a tautology and
returns 1.000 by construction. It is shown only to make the circularity explicit.
It also means NLI's pooled "all tiers" figures (gap F1 0.953, bal acc 0.771) are
**74% self-scored and must not be quoted** — the honest NLI numbers are the gold
and synthetic rows.

### Reading Table 1

**On the only balanced tier, lexical beats NLI.** Synthetic is the sole tier with a
gap rate near parity (0.587), and there lexical wins on every honest metric —
bal acc 0.775 vs 0.629, present F1 0.715 vs 0.468. On gold (n=50) the two are
close and both weak on the present class.

This **reverses the expectation the project carried into Phase 1**, which was that
NLI's advantage would show up on paraphrased-present elements once a tier had
enough of them. It has 453 of them, and NLI loses.

---

## Why NLI loses: it cannot see content that survived

Accuracy within each `in_document` bucket. (Balanced accuracy is degenerate here —
every element in a bucket shares one gold label — so only accuracy is meaningful.)

| `in_document` | n | NLI acc | lexical acc |
|---|--:|--:|--:|
| omitted (gold label = gap) | 5 610 | 0.985* | 0.984 |
| **paraphrased** (present) | 453 | **0.366** | **0.640** |
| **verbatim** (present) | 236 | **0.292** | **0.453** |
| present_unspecified | 348 | 0.983 | 0.348 |

Two things to take from this:

\* **Circular — do not quote.** 4 593 of the 5 610 `omitted` elements are
NLI-labelled corpus items, so this row is mostly NLI agreeing with itself. On gold +
synthetic only (n=1 017) NLI scores **0.916** and lexical **0.974**
(`outputs/paper_detector_checks.md`). The `paraphrased` and `verbatim` rows contain
no corpus items and are unaffected.

1. **NLI is good on gaps and near-useless on present content.** It calls
   present elements "gap" roughly two times in three.
2. **It fails hardest on `verbatim` (0.292)** — elements copied word-for-word into
   the document. A detector that cannot recognise a literal copy is not doing
   entailment in any useful sense here; it is reacting to the length and
   abstractiveness of the premise. Entailment against a ~100-word compressed
   summary reads *almost everything* as not-entailed.

This is the same failure `ensemble.py` was written for, now quantified on a tier
with constructed ground truth rather than inferred from corpus behaviour.

### Consequence for the corpus labels

The 227-meeting corpus is labelled by exactly this detector. If NLI recognises
present content at 0.29–0.37, the corpus's **0.93 gap rate is inflated** and its
silver labels carry a systematic present-class bias. A model-assisted review pass
over 17 corpus pairs (382 elements) already saw the direction of this — 23
false-positive gaps, ~7%, all paraphrase-present — and Table 1 gives it a
magnitude. **That review is not a human pass** (annotator `llm-review`, whose
own note says it is not a substitute for one), so it cannot be cited as validation;
Phase 1.5 is the human check, and it is still outstanding. Corpus-tier numbers should be read as an upper bound
on the gap rate, not an estimate of it.

---

## Table 2 — extraction completeness (5 gold Product meetings)

Completeness requires hand-built reasoning ground truth, which exists only for
QSUM_001–005, all Product/test. **This is a stated limitation, not an oversight:**
Academic and Committee meetings are not labelled for completeness and deliberately
were not labelled for it. The corpus-wide run reports the objective half only
(hallucination + verbatim rate) across all domains.

| pair | lexical | semantic |
|---|--:|--:|
| QSUM_001 | 0.455 | 0.636 |
| QSUM_002 | 0.500 | 0.875 |
| QSUM_003 | 0.111 | 0.222 |
| QSUM_004 | 0.286 | 0.643 |
| QSUM_005 | 0.333 | 0.500 |
| **total** | **0.333** (16/48) | **0.583** (28/48) |

Both scorers are reported because neither is trustworthy alone, and the gap
between them is large enough to change the headline claim.

**The completeness figure is a range: 33–58%.** An earlier draft quoted "~47%",
which was the average of QSUM_001 and QSUM_002 under lexical scoring at a point
when only those two had been scored. With all five scored it does not reproduce
under either scorer and should not be used.

**14 of the 32 lexical misses are correct extractions the token-F1 matcher
under-credited**, including `"battery"` at 0.00 and `"Kryptonite was chosen as the
preferred energy source"` — the headline decision, correctly extracted — at 0.36.
Lexical completeness is therefore a floor, not an estimate, and the true value sits
near the semantic figure.

Owner/approver elements are excluded from completeness (N/A in AMI-style data,
Task 1 caveat 1) and scored separately.

---

## Table 3 — failure taxonomy (Phase 2.4)

All 20 residual misses on the 5 gold meetings, categorised by reading the
transcript evidence for each: where the supporting content actually sits, how far
apart those turns are, which chunk they fall in, and what the extractor said that
was closest (`outputs/failure_analysis_evidence.json`).

Misses are the **semantic** residual. Using the lexical misses would have added 14
scorer artifacts and manufactured a "paraphrase" category that is not an
extraction failure at all.

| failure category | n | share |
|---|--:|--:|
| Multi-hop: implicit — connection never stated, must be inferred | 6 | 30% |
| Multi-hop: scattered — reasoning spread across turns far apart | 5 | 25% |
| Paraphrase miss — found, worded differently, scorer missed it | 5 | 25% |
| Out of scope — present and local, model did not extract it | 4 | 20% |
| **Chunking boundary** | **0** | **0%** |
| **Model hallucination** | **0** | **0%** |

**Multi-hop accounts for 11/20 (55%)** of what the extractor fails to recover.

The two zeros carry as much weight as the leading category:

- **No miss was caused by a chunk cut.** At 1 200 tokens with 2 turns of overlap,
  chunking is not the bottleneck — so "use a longer context window" does not
  address these failures. The distances involved are ~670 turns (QSUM_005: chip
  tiers at t130–138, speech-recognition-in-chip at t805–818), far beyond a
  window-size fix.
- **No miss was caused by hallucination.** None of the 20 residual misses traces
  to an invented quote: the failure mode behind the misses is omission, not
  fabrication — which matters for the claim that the ceiling is a
  retrieval/reasoning limit rather than a fluency one. (This is *not* a zero
  hallucination rate: 16.4% of evidence quotes on these meetings are unsupported,
  see `outputs/task4_extraction_scores.json` and Table 2b in the paper.)

The 4 `out_of_scope` cases are the interesting residual: content that is explicit,
local, and in a single chunk, that the model simply did not emit as a structured
element (e.g. QSUM_005 t132/t138 state "a display requires an advanced chip / the
most expensive" adjacently; QSUM_003's menu-vs-buttons exchange at t223–t246 was
summarised as "no decision was reached").

---

## The base-rate problem — read before quoting any headline F1

At the corpus gap rate of 0.93, a detector that answers "gap" to everything scores
F1 ≈ 0.962. Lexical scores 0.970. **The headline is nearly free.**

This is why every table above leads with balanced accuracy and the present class,
and why `run_gap_eval.py` prints a base-rate warning on any bucket above 0.85.
Per-domain the distortion is stark — a high gap F1 can hide near-chance behaviour:

Lexical @ 0.55, corpus domains:

| domain | n | base rate | gap F1 | **bal acc** |
|---|--:|--:|--:|--:|
| committee | 1 383 | 0.978 | 0.988 | **0.532** |
| academic | 854 | 0.946 | 0.981 | **0.745** |
| product | 2 743 | 0.900 | 0.955 | **0.665** |
| cloud_platform (synthetic) | 819 | 0.571 | 0.842 | **0.764** |

Committee looks like the detector's best domain by F1 (0.988, the highest of any
bucket) and is its worst by balanced accuracy (0.532, barely above the 0.5 an
all-gap detector scores) — those summaries are pure meta-prose, so nearly
everything is a gap and guessing "gap" wins. Balanced accuracy rises as the base
rate falls, which is the signature of a metric measuring skew rather than skill.

Three rules for reporting:

1. Never quote a corpus-tier F1 without the base rate beside it.
2. Lead with balanced accuracy and present-class numbers.
3. Detector comparison is only meaningful on the synthetic tier and the
   `by_in_document` present rows.

---

## Element-type caveat on the corpus tier

`qmsum_auto` element types come from a cue-word heuristic whose coverage was
measured, not assumed: **1 030 of 4 930 elements (20.9%)** matched an actual cue.
QMSum specific-query answers are narrative meeting summaries, so most sentences
genuinely are not an alternative, a dissent or a condition. Read the
by-element-type breakdown for `qmsum_auto` as indicative only; `rationale` there
means "reasoning-ish narrative, unclassified". Element types are trustworthy on the
synthetic tier, where they come from a typed spec.

---

## Completed after this document was first written (2026-09-26)

All four items previously listed as "still to run" are done; results live in:

- LLM-entailment + ensemble ablation (Phase 1.2/1.3): `outputs/gap_eval_results.md`
  — 296-element sample; LLM judge bal acc 0.495 (yes-bias), ensemble 0.516.
- Corpus-wide extraction by domain (Phase 2.1–2.3): `outputs/corpus_extraction_results.md`,
  `outputs/corpus_quote_fidelity.md` — unsupported quotes 14.6% overall.
- Human spot-check (Phase 1.5): `outputs/qmsum_spotcheck_mini_report.json` — one annotator,
  52 elements: silver labels over-call gaps (gap precision 0.478, bal acc 0.60). This
  **supersedes the ~7% false-positive estimate above**, which came from the
  `llm-review` model pass.
- Comparative analysis (Phase 3): `outputs/comparative_analysis.md`.

## Reproduce

```bash
python -m pytest -q
python scripts/run_gap_eval.py --detectors nli lexical llm ensemble --llm-sample 400 --threshold 0.55
python scripts/failure_analysis.py --build
python scripts/failure_analysis.py --report
```
