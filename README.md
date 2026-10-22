# EDIA — extraction pipeline (Task 4), gap detection (Task 2) and benchmark (Task 5)

Builds on Tasks 1–3, whose outputs are in `outputs/`:
`gap_validation_results.md` (5 hand-validated QMSum pairs), `nli_transfer_test_results.md`
(roberta-large-mnli at 95.5% on 22 elements), `task3_ingestion_output_summary.md`.

The benchmark (`edia_db`, **locked**) spans the **whole QMSum corpus** (all 232
meetings, 3 domains: 5 hand-labelled + 227 auto-labelled) plus **139 synthetic
pairs** — 371 pairs / 6 647 elements in total. See `CONTINUATION_RUNBOOK.md` for how
every result was produced, `outputs/dataset_card.md` for composition and label
provenance, and `paper/` for the IEEE paper draft (numbers traced in
`paper/NUMBERS.md`).

```
edia/
  ingestion/          # Task 3, moved in unchanged (turns_to_text factored out for reuse)
  extraction/
    schema.py         # FROZEN DecisionRecord -- v1.0.0, fingerprint-pinned
    chunker.py        # turn-aware overlapping chunks
    llm_client.py     # Ollama, temperature=0 enforced structurally
    prompts.py        # extraction prompt + the negative few-shot example
    extractor.py      # chunk -> DecisionRecord, no cross-chunk merging
  gapdetect/          # Task 2, in code: is a reasoning element in the document?
    nli.py            # NliGapDetector -- premise=doc, hypothesis=element, P(entail)
    lexical.py        # token-F1 baseline
    entailment_llm.py # Ollama yes/no ablation
    metrics.py        # gap-class P/R/F1, threshold sweep
  benchmark/
    qmsum_ground_truth.py  # Task 1's five tables as DecisionRecords (the 5 gold)
    qmsum_corpus.py        # iterate ALL of QMSum -> QMSUM_AUTO BenchmarkPairs
    decompose.py           # specific-query answer -> atomic elements (sentence / LLM)
    score.py               # completeness + hallucination scoring (truth=None -> hall. only)
    dataset.py             # BenchmarkPair; DATASET_VERSION 1.1.0; PairSource.QMSUM_AUTO
    topics.py              # 12 domains x 10 archetypes = 120 topics x 17 = 2040 plan
    generate.py            # synthetic pair generation, checkpointed, sharded
    fold_qmsum.py          # QSUM_001-005 fold-in
    annotate.py / agreement.py   # human annotation CLI + Jaccard/kappa
scripts/                   # runnable entry points (see RUNBOOK.md)
tests/                     # 159 offline; +2 NLI tests behind `pytest --run-nli`
```

## Setup

```bash
pip install -r requirements.txt          # ~2 GB: adds transformers + torch for gapdetect
ollama pull mistral                       # for extraction + synthetic generation
```

The NLI model (`roberta-large-mnli`, ~1.4 GB) downloads on first use.

## Task 4 — run the extraction pipeline

```bash
python scripts/prepare_qmsum.py       # cut the 5 Task 1 meetings out of QMSum
python scripts/run_qmsum_eval.py      # extract + score -> outputs/task4_extraction_results.md
python scripts/run_corpus_extraction.py   # same extractor over ALL of QMSum; hallucination-only
```

Both are checkpointed per chunk (`outputs/extractions/chunks/`), so an interrupted run
resumes rather than restarting. `--semantic` swaps the lexical element matcher for
sentence-transformer similarity; `--force` ignores the cache. `run_corpus_extraction.py`
scores only the objective half (evidence grounding) because completeness needs the
hand-built ground truth that exists for the 5 gold pairs only.

Extract from any file:

```bash
python -m edia.extraction.extractor path/to/transcript.json --out records.json
```

### Constraints enforced in code, not by convention

| Constraint | How it is enforced |
|---|---|
| `temperature=0` | `OllamaClient.__init__` raises unless `allow_sampling=True`; only the synthetic generator passes it, and it records temperature and seed per pair |
| schema frozen | `tests/test_schema_frozen.py` pins a SHA-256 of the JSON schema; any field change fails CI until `SCHEMA_VERSION` is bumped deliberately. The benchmark-side `DATASET_VERSION` (1.1.0) is separate and not in that hash. |
| no cross-chunk merging | every `DecisionRecord` keeps its `chunk_id`; `ExtractionResult.merged_across_chunks` stays `False`; a test asserts the same decision seen twice stays two records |

## Task 5 — build the benchmark

```bash
python -m edia.benchmark.fold_qmsum                       # the 5 gold pairs
python scripts/build_qmsum_corpus.py --detector nli       # ~227 QMSUM_AUTO pairs (all of QMSum)
python scripts/calibrate_qmsum_labels.py                  # NLI vs the 5 gold -> threshold
python scripts/generate_synthetic.py --shard 0/4          # synthetic pairs -- dataset LOCKED at 139; do not regenerate
python scripts/dedupe_synthetic.py                        # flag near-duplicates
python scripts/generate_synthetic.py --status             # progress + dataset stats
python scripts/run_gap_eval.py                            # NLI vs lexical vs LLM -> outputs/gap_eval_results.md
```

Spot-check the auto labels (see `RUNBOOK.md` for the full sequence):

```bash
# CAUTION: sample_for_spotcheck.py DELETES its --out folder first (default:
# data/benchmark/spotcheck, which holds the llm-review pass) -- always pass a new --out.
# spotcheck_report.py always writes outputs/qmsum_spotcheck_report.json, whatever --dir is.
python scripts/sample_for_spotcheck.py --out data/benchmark/spotcheck_new
python -m edia.benchmark.annotate --dir data/benchmark/spotcheck --annotator <name> --blind
python -m edia.benchmark.annotate --dir data/benchmark/spotcheck --annotator <name2> --double
python scripts/spotcheck_report.py
```

Ground truth for the synthetic pairs is **constructed, not annotated after the fact**:
the pipeline picks the reasoning elements and decides which ones the document may keep
*before* writing either text, then writes both to that plan and leak-checks the result.
The human pass is therefore verification, which is what makes the agreement number
meaningful.

## Two measurement decisions worth knowing before reading any number

**"Unmatched" is not "hallucinated."** Two separate rates are reported. *Unsupported
evidence* — model quotes whose words do not occur in the source chunk — is objective and
needs no ground truth; that is the hallucination rate. *Unmatched extracted* — elements
with no counterpart in Task 1's tables — is not, because those tables were built to answer
"did the document drop this?", not to enumerate everything the discussion contained.
Unmatched items are listed individually for adjudication rather than counted as errors.

**Disfluency cleanup is not fabrication.** mistral drops QMSum's `{disfmarker}` and "uh"
when quoting. Grounding is therefore checked twice: leniently (ignoring transcription
markers and filler — this is the hallucination rate) and strictly (exact reproduction —
reported as `strict_verbatim_rate`). A quote with invented words fails both. The gap
between the two numbers is a fact about quoting fidelity, not about hallucination.

**Owner/approver is a dataset limitation, not an extractor miss.** AMI-style meetings
record no formal sign-off (Task 1 caveat 1), so those elements are scored separately and
kept out of headline completeness.

## Known limitations

Full list in `outputs/dataset_card.md`. The load-bearing ones:

- **`qmsum_auto` labels are silver** — produced by the NLI detector. Scoring NLI
  against them is a self-consistency check, not accuracy; every report separates
  those rows. Accuracy for that tier = the 5 gold pairs + the human spot-check.
- The 120-topic domain×archetype matrix in `topics.py` is a principled stand-in:
  the "existing topic list" the brief refers to was not in the Task 1–3 handover.
  Replacing `DOMAINS` / `ARCHETYPES` is a one-file change.
- QMSum "documents" are annotator-written general summaries standing in for filed
  decision records — Task 1's substitution, carried forward unchanged.
- Synthetic transcripts are mistral-written and cleaner than real meetings. The
  QMSum tiers are in the same schema so a method that only works on the tidy half
  is visible.
- `qmsum_auto` element types come from a cue-word heuristic; that breakdown is
  indicative. Those pairs carry no `DecisionRecord`s, so they do not feed
  extraction-completeness scoring.
