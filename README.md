# EDIA — extraction pipeline (Task 4) and benchmark dataset (Task 5)

Builds on Tasks 1–3, whose outputs are in `outputs/`:
`gap_validation_results.md` (5 hand-validated QMSum pairs), `nli_transfer_test_results.md`
(roberta-large-mnli at 95.5% on 22 elements), `task3_ingestion_output_summary.md`.

```
edia/
  ingestion/          # Task 3, moved in unchanged
  extraction/
    schema.py         # FROZEN DecisionRecord -- v1.0.0, fingerprint-pinned
    chunker.py        # turn-aware overlapping chunks
    llm_client.py     # Ollama, temperature=0 enforced structurally
    prompts.py        # extraction prompt + the negative few-shot example
    extractor.py      # chunk -> DecisionRecord, no cross-chunk merging
  benchmark/
    qmsum_ground_truth.py  # Task 1's five tables as DecisionRecords
    score.py               # completeness + hallucination scoring
    dataset.py             # BenchmarkPair: one format for synthetic + QMSum pairs
    topics.py              # the 10 topics x 5 = 50 plan
    generate.py            # synthetic pair generation, checkpointed
    fold_qmsum.py          # QSUM_001-005 fold-in
    annotate.py            # human annotation CLI
    agreement.py           # Jaccard + Cohen's kappa
scripts/                   # runnable entry points
tests/                     # 96 tests, all offline
```

## Setup

```bash
pip install -r requirements.txt
ollama pull mistral
```

## Task 4 — run the extraction pipeline

```bash
python scripts/prepare_qmsum.py       # cut the 5 Task 1 meetings out of QMSum
python scripts/run_qmsum_eval.py      # extract + score -> outputs/task4_extraction_results.md
```

Both are checkpointed per chunk (`outputs/extractions/chunks/`), so an interrupted run
resumes rather than restarting. `--semantic` swaps the lexical element matcher for
sentence-transformer similarity; `--force` ignores the cache.

Extract from any file:

```bash
python -m edia.extraction.extractor path/to/transcript.json --out records.json
```

### Constraints enforced in code, not by convention

| Constraint | How it is enforced |
|---|---|
| `temperature=0` | `OllamaClient.__init__` raises unless `allow_sampling=True`; only the synthetic generator passes it, and it records temperature and seed per pair |
| schema frozen | `tests/test_schema_frozen.py` pins a SHA-256 of the JSON schema; any field change fails CI until `SCHEMA_VERSION` is bumped deliberately |
| no cross-chunk merging | every `DecisionRecord` keeps its `chunk_id`; `ExtractionResult.merged_across_chunks` stays `False`; a test asserts the same decision seen twice stays two records |

## Task 5 — build the benchmark

```bash
python -m edia.benchmark.fold_qmsum              # QSUM_001-005 (done)
python scripts/generate_synthetic.py             # 50 synthetic pairs, resumable
python scripts/generate_synthetic.py --status    # progress + dataset stats
python -m edia.benchmark.annotate --annotator <name>            # first pass
python -m edia.benchmark.annotate --annotator <name2> --double  # blind second pass
python -m edia.benchmark.agreement               # Jaccard + kappa
```

Ground truth for the synthetic pairs is **constructed, not annotated after the fact**:
the pipeline picks the reasoning elements and decides which ones the document may keep
*before* writing either text, then writes both to that plan and leak-checks the result.
The human pass is therefore verification, which is what makes the agreement number
meaningful.

## Two measurement decisions worth knowing before reading any number

**"Unmatched" is not "hallucinated."** Two separate rates are reported. *Unsupported
evidence* — model quotes that do not occur in the source chunk — is objective and needs
no ground truth; that is the hallucination rate. *Unmatched extracted* — elements with no
counterpart in Task 1's tables — is not, because those tables were built to answer "did
the document drop this?", not to enumerate everything the discussion contained. Unmatched
items are listed individually for adjudication rather than counted as errors.

**Owner/approver is a dataset limitation, not an extractor miss.** AMI-style meetings
record no formal sign-off (Task 1 caveat 1), so those elements are scored separately and
kept out of headline completeness.

## Known limitations

- The 10 synthetic topics in `topics.py` are a stand-in: the "existing topic list" the
  brief refers to was not in the Task 1–3 handover. Replacing `TOPICS` is a one-file
  change, and pair ids derive from list position, so swap it before generating.
- QMSum "documents" are annotator-written general summaries standing in for filed
  decision records — Task 1's substitution, carried forward unchanged.
- Synthetic transcripts are mistral-written and are cleaner than real meetings:
  fewer disfluencies, tighter turns. The five QMSum pairs are in the same format
  specifically so a method that only works on the tidy ones is visible.
