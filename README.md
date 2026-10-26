# EDIA — Explainable Decision Intelligence Assistant

**Where meeting reasoning gets lost: a feasibility study of decision-context gap detection in enterprise meetings.**

Meetings end in decisions, but the written minutes usually record *what* was decided and drop
*why*: the alternatives weighed, the rationale, the conditions, the dissent. EDIA asks whether
current open language models can (1) recover that reasoning from a meeting transcript and
(2) detect which of it the filed document left out, and it measures, carefully, where and why
this breaks.

Capstone project, Dept. of Computer Science and Business Systems, Mukesh Patel School of
Technology Management and Engineering, NMIMS, Mumbai.
**Team:** Jaitra Shah, Manan Mehta, Soham Dwivedi, Aayusman Pati.

## What is in this repository

| | |
|---|---|
| **EDIA pipeline** | Transcript → chunks → structured decision records (Mistral 7B via Ollama, temperature 0) → gap detectors (lexical, NLI, LLM judge, ensemble). `edia/` |
| **`edia_db` benchmark** | 371 transcript–document pairs, 6,647 labelled reasoning elements, in three tiers (5 hand-labelled, 227 NLI-labelled, 139 synthetic). Locked. `data/benchmark/pairs/`, card in `outputs/dataset_card.md` |
| **Experiments** | Gap-detector comparison, extraction completeness and precision, corpus-wide grounding, failure taxonomy, and comparisons against chain-of-thought, GraphRAG and multi-hop retrieval. `scripts/`, results in `outputs/` |
| **Paper** | IEEE-format paper (`paper/edia_ieee.tex` / `.docx`) with its figure and bibliography, and a plain-language guide to it (`paper/EDIA_explained.docx`) |

## Main results

| Question | Result |
|---|---|
| Which detector best spots reasoning the minutes dropped? | A simple word-overlap (lexical) detector beats NLI on the only balanced tier: balanced accuracy **0.775 vs 0.629**. The LLM judge is at chance (0.495). |
| Why does NLI lose? | It misses content that *did* survive into a short summary, including word-for-word copies (accuracy 0.292). |
| How much reasoning does extraction recover? | **33.3%** (strict word matching) to **58.3%** (meaning-based) on the five hand-labelled meetings. |
| Why are the rest missed? | **55%** of the residual misses need multi-hop reasoning across distant or implicit turns. None came from chunk boundaries and none from invented quotes. |
| Does the model make up evidence? | Unsupported quotes: **14.6%** across all 227 meetings, **5.4%** excluding quotes that were only tidied (words dropped, none added). |
| Do other methods do better? | No. Chain-of-thought 62.5% recall but lower F1 (18.3 vs 22.0); GraphRAG 4.2–18.8%; multi-hop retrieval 0.0–12.8%. |
| Is the benchmark's auto-labelling trustworthy? | Only partly. A blind human check (52 elements, one annotator) found about half of the NLI-flagged gaps were actually present in the summary. Corpus gap rates are upper bounds. |

Answer to the feasibility question: **partially**. Full detail, tables and caveats are in the
paper; `paper/NUMBERS.md` traces every number in it to a file in `outputs/`.

## Repository layout

```
edia/
  ingestion/            parse transcripts and documents (txt, json, csv, docx, pdf)
  extraction/           chunker, Ollama client, prompts, extractor, frozen DecisionRecord schema
  gapdetect/            lexical, NLI, LLM-judge and ensemble gap detectors, metrics
  benchmark/            dataset schema, QMSum folding, synthetic generator, scoring, annotation tools
scripts/                runnable entry points (one per experiment, see below)
tests/                  159 offline tests (+2 NLI tests behind --run-nli)
data/
  benchmark/pairs/      the 371 benchmark pairs
  benchmark/spotcheck_mini/   the human spot-check sample and annotations
  qmsum/                the five hand-labelled gold meetings
outputs/                every result file (markdown + json) and the dataset card
paper/                  the paper, figure, bibliography, NUMBERS.md (source of every number)
```

## Setup

Python 3.10–3.12.

```bash
pip install -r requirements.txt            # includes torch and transformers (~2 GB)
python -m pytest -q                         # 159 passed, 2 skipped
```

For GPU use, install the CUDA build of PyTorch from <https://pytorch.org> instead of the default
wheel (a CPU-only wheel makes the NLI evaluation hours slower).

The extraction and LLM-judge experiments need [Ollama](https://ollama.com) with the model used
throughout the study:

```bash
ollama pull mistral
```

The NLI model (`roberta-large-mnli`, ~1.4 GB) and the sentence-embedding model
(`all-MiniLM-L6-v2`) download on first use. GraphRAG (optional, one experiment) additionally
needs `pip install graphrag` in a separate environment and `ollama pull nomic-embed-text`.

## Reproducing the results

Everything below runs from a fresh clone, using the result files committed in `outputs/`.

```bash
# extraction precision / recall / F1 for every approach (Table VII of the paper;
# takes several minutes on a laptop)
python scripts/extraction_precision.py

# multi-hop retrieval baseline, then the comparison table (Table VI)
python scripts/multihop_retrieval.py
python scripts/build_comparison_table.py --graphrag 0.146 --graphrag-lex 0.042 \
    --graphrag-note "5 gold meetings, local search; 4.2% / 18.8% without the converter support filter"

# GraphRAG: re-score the stored answers (no model calls)
python scripts/run_graphrag_comparison.py --rescore-only

# gap detectors (NLI + lexical) on the whole benchmark; add `llm ensemble --llm-sample 400`
# for the LLM judge (needs Ollama)
python scripts/run_gap_eval.py --detectors nli lexical --threshold 0.55

# chain-of-thought ablation; --no-cot re-extracts the plain baseline on the same runtime
python scripts/run_cot_ablation.py [--no-cot]

# extraction over the five gold meetings, lexical and semantic scoring
python scripts/run_qmsum_eval.py
python scripts/run_qmsum_eval.py --semantic --threshold 0.55

# human spot-check report (the committed sample)
python scripts/spotcheck_report.py --dir data/benchmark/spotcheck_mini
```

Experiments that need the full QMSum release (`run_corpus_extraction.py`, `build_qmsum_corpus.py`)
read `data/qmsum/raw/`, which is **not** committed. Get it from the QMSum repository
(<https://github.com/Yale-LILY/QMSum>) and copy each domain's `train/val/test` `.jsonl` files
into `data/qmsum/raw/{Academic,Committee,Product}/`. Large intermediate caches
(`outputs/gap_eval_scores.jsonl`, per-chunk checkpoints) are also not committed; the scripts
recompute them and resume if interrupted.

Experiments that call the model are deterministic in intent (temperature 0, top-k 1, fixed seed)
but not bit-for-bit across inference-engine versions; the paper reports this as a finding
(Sec. VII, runtime sensitivity).

### Constraints enforced in code, not by convention

| Constraint | How it is enforced |
|---|---|
| `temperature=0` | `OllamaClient.__init__` raises unless `allow_sampling=True`; only the synthetic generator passes it, and it records temperature and seed per pair |
| Schema frozen | `tests/test_schema_frozen.py` pins a SHA-256 of the JSON schema; any field change fails the test until `SCHEMA_VERSION` is bumped deliberately |
| No cross-chunk merging | every `DecisionRecord` keeps its `chunk_id`; a test asserts the same decision seen twice stays two records |

## How results are measured

Three decisions shape every number, and the paper explains each in full.

- **Balanced accuracy, not plain accuracy or F1.** About 93% of corpus elements are gaps, so a
  detector that always answers "gap" scores F1 ≈ 0.96 and does nothing useful. Balanced accuracy
  gives it 0.5.
- **Two matchers, always both.** Completeness is reported with strict word-overlap matching and
  with meaning-based (sentence-embedding) matching. The truth lies between them.
- **Hallucination means unsupported quotes.** A quote is unsupported when it does not occur in its
  own source chunk. Precision against the hand labels is reported separately and only as a lower
  bound, because the hand labels are not exhaustive.

## Limitations

- **Completeness is measured on five hand-labelled meetings only**, all Product design. Across the
  three domains we measured grounding (hallucination), not completeness, so the 33–58% ceiling is
  not claimed to hold everywhere.
- **The 227-meeting corpus labels are NLI-produced ("silver")** and overstate the gap rate. Scoring
  NLI against them is circular and is excluded from the paper.
- **The human spot-check is small:** one annotator, 52 elements from three pairs, no second
  annotator, so no inter-annotator agreement.
- **Synthetic transcripts are model-written** and cleaner than real meetings. QMSum's summaries
  stand in for filed decision records.
- **Only 7B-scale open models, run locally.** Larger models may behave differently.

Full list in `outputs/dataset_card.md` and in the paper's Discussion section.

## Data and licensing

The benchmark is built from **QMSum** (Zhong et al., NAACL 2021), a public meeting-summarisation
benchmark over the ICSI, AMI and parliamentary-committee corpora. The pairs in
`data/benchmark/pairs/` contain transcript text and summaries derived from QMSum; they remain
subject to QMSum's and the original corpora's terms. Please cite QMSum and consult its repository
for its license before reusing that data. The synthetic pairs and all code in this repository are
original work of the team.
