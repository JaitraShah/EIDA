# EDIA — Revised Project Plan
**Branch:** `Jaitra` | **Dataset:** `edia_db` (locked at current state)  
**Faculty approval:** Confirmed  
**Last updated:** September 2026

> **Status (October 2026):** this is the original plan, kept for the project record. The work
> is finished and its results are in `paper/` and `outputs/`. The "~47%" completeness figure
> used below was **retired**: measured completeness is 33.3% (lexical) to 58.3% (semantic)
> on the five hand-labelled meetings (paper Sec. VI).

---

## IMPORTANT: Updated project scope (read this first)

The project framing changed after the first plan. This section explains the new direction and why.

### What changed and why

The original framing was: "EDIA is a system that detects decision-context gaps in meeting transcripts." The implicit claim was that it works.

After expert review and faculty consultation, the framing is now:

**EDIA is a feasibility study and comparative analysis that rigorously measures whether decision-context gap detection in enterprise meetings is achievable with current AI, and diagnoses exactly why it hits the ceiling it does.**

The answer our results are pointing toward: not fully achievable yet. The reason: multi-hop reasoning across scattered multi-person meeting content is a currently unsolved problem in AI. Our system finds roughly half the reasoning a human finds, and this is not a fixable bug. It is a structural limitation, which the failure analysis in the paper supports.

### What this means for how we present results

- The 47% extraction completeness is not a failure to apologise for. It is the central finding.
- The paper does not claim the system works reliably. It claims: here is what we built, here is what it found, here is exactly where and why it breaks.
- Every number we produce is evidence for the diagnosis, not a score to maximise.
- We compare against GraphRAG, chain-of-thought, and multi-hop retrieval to show these alternatives hit the same ceiling for diagnosable reasons.

### Why these alternatives do not fix the problem

- **GraphRAG:** designed for static documents. Falls apart on conversational multi-speaker data. External benchmarks show ~13% on conversational tasks.
- **Chain-of-thought:** helps the model reason better at answer time. Does not help find facts scattered across a long meeting. The bottleneck is retrieval, not reasoning.
- **Multi-hop retrieval:** requires knowing what chain to follow before you start. In meetings, the chain only becomes visible after reading the whole thing. You cannot know to look for the budget concern until you already understand the vendor decision.

### The thesis in one sentence

> Decision-context gap detection in enterprise meetings is partially achievable today, capped at roughly half the reasoning a human finds, because multi-hop reasoning across scattered conversational content remains an unsolved problem in current AI.

---

## Current dataset state (edia_db, locked)

Do not generate more synthetic pairs or add more data. Work only with what exists.

| Tier | Pairs | Elements | Gap Rate | Label source |
|---|---|---|---|---|
| Gold | 5 | 50 | 0.76 | Human (Task 1 hand-labelled) |
| QMSum corpus | 227 | 4,930 | 0.93 | NLI @ threshold 0.55 (validated) |
| Synthetic | 139 | ~1,250 est. | ~0.64 | Constructed by LLM |
| **Total** | **371** | **~6,230** | — | — |

### The base rate problem — always remember this

At 93% gap rate in the QMSum corpus, a detector that says "gap" to everything scores F1 = 0.962. Our lexical detector scores 0.964. That headline is nearly meaningless.

**Always report:** balanced accuracy and present-class F1 alongside gap F1.  
**The synthetic tier (gap rate ~0.64) is the only balanced tier.** It is where detector comparisons are actually meaningful.

---

## Phase 1 — Complete gap detection evaluation

Goal: produce a full, honest gap detection results table across all tiers and all detectors.

### What is already done
- NLI threshold calibrated at 0.55 on 5 gold pairs
- Spot-check validated: Gap F1 0.964, balanced acc 0.836, 0 false negatives
- Gold pair eval: NLI F1 0.86, Lexical F1 0.88
- Full corpus lexical eval run (but gap F1 alone is misleading at 93% base rate)

### What needs to be done

**1.1 Full corpus NLI gap eval**
```bash
python scripts/run_gap_eval.py --detector nli
```
Run NLI across all 4,930 corpus elements. Report balanced accuracy and present-class F1, not just gap F1. Compare directly against lexical baseline.

**1.2 LLM entailment ablation**
```bash
python scripts/run_gap_eval.py --detectors llm --llm-sample 400
```
Sample 400 elements for Ollama-based entailment. Compare all three detectors: NLI, lexical, LLM. Note what each catches that the others miss.

**1.3 Ensemble evaluation**
Run the ensemble detector (present if ANY member says present) on the same 400-element sample. Does the ensemble reduce false negatives? At what cost to false positives?

**1.4 Synthetic tier evaluation**
Run all three detectors on the 139 synthetic pairs. This is the most meaningful comparison because the gap rate is balanced. Report full precision, recall, F1, balanced accuracy, and present-class F1.

**1.5 Human blind spot-check pass**
Manually review a sample to finalise auto-label F1 and Cohen's kappa. This is the evidence that corpus labels are trustworthy. Without it, a reviewer can challenge every corpus result.

### Output of Phase 1
A complete detector comparison table across all three tiers. This becomes **Table 1** of the paper.

| Detector | Tier | Gap F1 | Balanced Acc | Present-class F1 |
|---|---|---|---|---|
| Lexical | Gold | | | |
| NLI | Gold | | | |
| LLM | Gold | | | |
| Ensemble | Gold | | | |
| Lexical | Corpus | | | |
| NLI | Corpus | | | |
| LLM | Corpus (sample) | | | |
| Lexical | Synthetic | | | |
| NLI | Synthetic | | | |
| LLM | Synthetic | | | |

---

## Phase 2 — Complete extraction evaluation across all 232 meetings

Goal: get completeness and hallucination numbers across all meetings, broken down by domain. This is the centrepiece finding.

### What is already done
- Extraction pipeline built and running (Ollama/mistral)
- Schema frozen at DecisionRecord v1.0.0
- 2 meetings scored: QSUM_001 (45% completeness, 10% hallucination), QSUM_002 (50% completeness, 20% hallucination)
- QSUM_003-005 still running

### What needs to be done

**2.1 Complete the extraction run on all 232 meetings**
```bash
python scripts/run_corpus_extraction.py
```
This is the long job. Monitor it. The supervisor pattern from generation can be adapted if it needs to be restartable. Track outputs per meeting into `outputs/extraction/`.

**2.2 Semantic similarity scoring alongside lexical**
Run the sentence-transformer matcher on all extraction outputs alongside the lexical scorer. Report both side by side. Never pick the flattering one. Several current near-misses (lexical score 0.36-0.44) are correct extractions under-credited by the lexical scorer; semantic scoring will resolve these.

**2.3 Domain breakdown**
Separate completeness and hallucination numbers by domain:
- Product meetings (137 in corpus)
- Academic meetings (59 in corpus)  
- Committee meetings (36 in corpus)

Does the ~47% ceiling hold across all three? If one domain shows significantly different results, investigate and explain why. Domain consistency strengthens the thesis considerably.

**2.4 Structured manual failure analysis**

This is the single most important task in the entire project. It is what turns "47% completeness" from a number into a thesis.

For each missed reasoning element across all scored meetings, manually categorise the failure:

| Failure category | Description |
|---|---|
| Multi-hop: scattered | Reasoning spread across 3+ turns far apart in the meeting |
| Multi-hop: implicit | Connection between facts never stated directly; inferred |
| Chunking boundary | Reasoning split across a chunk boundary; lost in the cut |
| Paraphrase miss | Extractor found the idea but in different words; lexical scorer missed it |
| Model hallucination | Extractor invented a quote not in the source |
| Out of scope | Reasoning element present but model chose not to extract it |

Tally these categories across all meetings. The expected finding: multi-hop categories should dominate. This is the empirical evidence for your thesis. This categorisation is what makes the paper a diagnostic study, not just a benchmark report.

Build a simple script to record these manually as you read through outputs, or use a spreadsheet. The point is a final tally table.

### Output of Phase 2
- Full extraction results table by domain (completeness + hallucination, both scorers). **Table 2.**
- Failure taxonomy tally table. **Table 3.**

---

## Phase 3 — Comparative analysis

Goal: show that GraphRAG, chain-of-thought, and multi-hop retrieval all hit the same wall, and explain precisely why.

### 3.1 Chain-of-thought ablation (run this first, easiest)

Add a chain-of-thought prompt variant to the existing extractor. Ask the model to reason step by step before extracting.

```python
# Prompt modification: add "Let's think step by step about what decisions 
# and reasoning appear in this transcript before extracting." before the 
# extraction instruction
```

Run on the same meetings already scored (QSUM_001-005 at minimum, ideally 20-30 across domains).

Measure completeness and hallucination with the same scorers. Does CoT improve completeness? By how much? Expected finding: marginal improvement, because CoT helps reasoning at output time but does not help find facts scattered across the meeting. Report the actual delta.

### 3.2 GraphRAG comparison

Run Microsoft GraphRAG (`graphrag` Python package) on a representative sample: suggest 15-20 meetings spread across all three domains.

```bash
pip install graphrag
# Index the meeting transcript
python -m graphrag.index --root ./graphrag_workspace
# Query for decision reasoning
python -m graphrag.query --root ./graphrag_workspace --method local "What decisions were made and what reasoning was given?"
```

Extract decision reasoning from GraphRAG's output and score it against your ground truth using the same completeness scorer. 

Report completeness. Expected: poor performance on conversational data. The diagnosis: GraphRAG builds its graph from clean entity relationships in structured text. Meeting transcripts are messy, multi-speaker, full of disfluency and interruption. The graph it builds is unreliable.

**If running GraphRAG end-to-end is too slow on available hardware:** a principled, cited argument with reference to its published performance on conversational benchmarks is acceptable for a short paper, but make this explicit in the limitations section.

### 3.3 Multi-hop retrieval comparison

Implement a simple multi-hop chain: given a decision, query for its rationale, then query using the rationale to find alternatives, then query using alternatives to find objections.

```python
def multihop_extract(meeting_text, decision):
    rationale = retrieve(meeting_text, f"Why was '{decision}' chosen?")
    alternatives = retrieve(meeting_text, f"Given that '{rationale}', what alternatives were considered?")
    objections = retrieve(meeting_text, f"What objections were raised about '{decision}'?")
    return combine(decision, rationale, alternatives, objections)
```

Use a simple BM25 or TF-IDF retriever for the retrieve step (keep it clean and reproducible, not dependent on external APIs).

Run on the same sample as CoT. Score completeness. Expected finding: the chain breaks because the first hop already fails. In a meeting, you often cannot find the rationale without understanding the full context first. The chain is only knowable in hindsight.

### 3.4 Comparison table

Produce the core comparison table:

| Approach | Completeness (lex) | Completeness (sem) | Hallucination | Core failure reason |
|---|---|---|---|---|
| EDIA pipeline | | | | Multi-hop across chunks |
| EDIA + CoT | | | | CoT helps reasoning, not retrieval |
| GraphRAG | | | | Designed for static structured text |
| Multi-hop retrieval | | | | Chain unknown in advance |

This is **Table 4** and the centrepiece of your comparative analysis section.

---

## Phase 4 — Write the paper

### Paper structure (target: 4-8 pages, ACL SRW format)

```
1. Introduction (~0.5 pages)
   - Meetings lose reasoning. This matters.
   - We built a system to detect this and measured it rigorously.
   - We found a ceiling and diagnosed it.

2. Background (~0.5 pages)
   - Decision-context gaps (cite your Task 1 findings)
   - Multi-hop reasoning: the core hard problem
   - Brief on existing approaches and why they fall short

3. The EDIA pipeline (~1 page)
   - Schema and extraction
   - Gap detection
   - Evaluation design and metrics (explain the base rate problem here)

4. Dataset: edia_db (~0.5 pages)
   - Three tiers: gold, corpus, synthetic
   - Why the synthetic tier matters (balanced gap rate)
   - Honest caveats: NLI auto-labels, not all human-verified

5. Results: gap detection (~0.75 pages)
   - Table 1: detector comparison across tiers
   - Key finding: detection layer works (0.836 balanced acc on validated sample)

6. Results: extraction and the ceiling (~0.75 pages)
   - Table 2: completeness + hallucination by domain
   - Table 3: failure taxonomy
   - Key finding: ~47% ceiling, multi-hop is the dominant failure mode

7. Comparative analysis (~1 page)
   - Table 4: EDIA vs CoT vs GraphRAG vs multi-hop retrieval
   - Each approach hits the same ceiling for a diagnosable reason
   - The ceiling is structural, not fixable by swapping the approach

8. Discussion (~0.5 pages)
   - What would need to change to break this ceiling
   - Honest limitations of this study
   - Implications: what the field needs before this becomes reliable

9. Conclusion (~0.25 pages)
   - One honest paragraph
```

### Things to state explicitly in the paper

- Why you report balanced accuracy and present-class F1, not gap F1 alone (the base rate problem, stated plainly)
- Why you report both lexical and semantic completeness (the paraphrase problem)
- That 47% is the finding, not a failure — and that it holds across all three meeting domains
- That the failure taxonomy is based on manual reading, not inference
- That the expert confirmed multi-hop reasoning across meeting content is a field-wide unsolved problem

### Before submitting

- [ ] Run `python -m pytest -q` and confirm all tests pass
- [ ] Make sure all hardcoded paths are removed from scripts
- [ ] Add a clean README with setup instructions and reproduce-all commands
- [ ] Release code publicly (requires GitHub fork to be resolved first)
- [ ] Verify all submission deadlines on official conference pages before committing to them

---

## Submission targets

**Primary:** ACL Student Research Workshop 2026  
Submission approximately 18 March 2026. Pre-submission mentorship approximately 4 February 2026. Sign up for mentorship if the timeline allows — it gives you free expert feedback before the main deadline.

**Backup:** EMNLP 2026 workshop on knowledge, memory, or enterprise NLP.  

**Type:** Short paper or workshop paper (4-8 pages). Do not target a full main-conference paper. A focused, honest short paper is more achievable and more appropriate for this contribution.

---

## What not to do

- Do not report gap F1 alone. Always pair with balanced accuracy and present-class F1.
- Do not pick the flattering scorer. Always report both lexical and semantic completeness.
- Do not claim the system works reliably. The honest framing is: it finds half the reasoning, and here is exactly why.
- Do not add more data to edia_db. The dataset is locked.
- Do not run a large job without first confirming `python -m pytest -q` passes.

---

## Quick resume commands

```bash
# Run all tests
python -m pytest -q

# Gap eval — lexical (fast)
python scripts/run_gap_eval.py --detector lexical

# Gap eval — NLI (needs GPU)
python scripts/run_gap_eval.py --detector nli

# Gap eval — LLM sample
python scripts/run_gap_eval.py --detectors llm --llm-sample 400

# Full corpus extraction (long job)
python scripts/run_corpus_extraction.py

# Spot-check report
python scripts/spotcheck_report.py

# Check Ollama + GPU
curl http://localhost:11434/api/tags

# Check pair counts
ls data/benchmark/pairs/QMS_*.json | wc -l
ls data/benchmark/pairs/SYN_*.json | wc -l
```

---

*Plan version: 2.0 | Dataset: edia_db (locked) | Faculty approval: confirmed | Scope: feasibility study + comparative analysis*
