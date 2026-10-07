# Where every number in `edia_ieee.tex` comes from

If a source file changes, update the paper from it -- never the other way round.

| Paper location | Value(s) | Source |
|---|---|---|
| Abstract, Sec. IV, Table I | 371 pairs, 6,647 elements; tiers 5/50/0.76, 227/4,930/0.93, 139/1,667/0.59 | `outputs/task5_benchmark_results.md` (Dataset), `outputs/gap_eval_results.md` header |
| Sec. IV corpus domains | Academic 59, Committee 36, Product 132 | `python -m edia.benchmark.qmsum_corpus --stats` |
| Table II upper half | NLI/lexical gold & synthetic; lexical corpus | `outputs/gap_eval_results.md` (by_source), `outputs/task5_benchmark_results.md` Table 1 |
| Table II lower half | same-sample n=200: 0.611/0.432, 0.728/0.637, 0.492/0.596, 0.521/0.624 | `outputs/paper_detector_checks.md` (`scripts/paper_detector_checks.py`) |
| Sec. V NLI by label | 0.916 / 0.974 (omitted), 0.366 / 0.640 (paraphrased), 0.292 / 0.453 (verbatim) | `outputs/paper_detector_checks.md` -- NOT the pooled by_in_document table (its omitted row is 82% circular) |
| Sec. V LLM judge | n=296, gap recall 0.047, bal acc 0.495; ensemble 0.516 | `outputs/gap_eval_results.md` (llm, ensemble) |
| Sec. V ensemble at designed threshold | bal acc 0.500 / gap recall 0 at 0.5 (vs 0.516 at the common 0.55) | recomputed from `outputs/gap_eval_scores.jsonl` with the ensemble's vote rule (`edia/gapdetect/ensemble.py`: vote = clamp(raw − member_thr + 0.5), max) |
| Sec. VII within-runtime variation | 7 of 296 LLM-judge confidences differ between the llm run and the ensemble run (3 verdicts flip at 0.55) | same recomputation: every mismatch is in the LLM vote |
| Sec. V base-rate | Committee gap F1 0.988, bal acc 0.532 | `outputs/task5_benchmark_results.md` (base-rate section) |
| Table III | per-meeting and pooled 0.333 (16/48), 0.583 (28/48) | `outputs/task4_extraction_scores.json`, `..._semantic.json` |
| Sec. VI | 14 of 32 lexical misses under-credited; Kryptonite example 0.36 | `outputs/task5_benchmark_results.md` Table 2 notes |
| Sec. VI | gold unsupported-quote rate 16.4% | `outputs/task4_extraction_scores.json` (quotes_grounded) |
| Table IV | per-domain quotes / unsupported / tidied-excluded | `outputs/corpus_extraction_results.md`, `outputs/corpus_quote_fidelity.md` |
| Sec. VI | 3,532 chunks, 36 failed (1.0%); 72% of Academic unsupported near-verbatim | `outputs/corpus_extraction_run.log`, `outputs/corpus_quote_fidelity.md` |
| Table V | taxonomy 6/5/5/4/0/0 of 20 | `outputs/failure_taxonomy.md` |
| Sec. VI | ~670 turns apart (QSUM_005 t130-138 vs t805-818) | `outputs/task5_benchmark_results.md` Table 3 notes |
| Table VI, EDIA rows | 33.3/58.3/16.4 and same-runtime 27.1/58.3/14.1 | `outputs/comparative_analysis.md`, `outputs/baseline_rerun_scores.md` |
| Table VI, CoT | 33.3/62.5/13.9; +6.2/+4.2 same runtime; 114 vs 76 records | `outputs/cot_ablation_results.md`, `SESSION_LOG.md` (5.1 row) |
| Table VI, GraphRAG | 4.2 / 14.6 (18.8 without support filter) | `outputs/graphrag_results.md` |
| Table VI, Sec. VII multi-hop | 12.2% lexical (5/41), 26.8% semantic (11/41) | `outputs/multihop_retrieval_results.md` (thresholds 0.45 / 0.55, same as EDIA) |
| Sec. VII runtime | -6.2 lexical, 0.0 semantic | `outputs/baseline_rerun_scores.md` |
| Abstract, Sec. IV, Sec. VIII spot-check | n=52 (3 pairs: ACA_TR_002, ACA_TR_009, CMT_TR_007), 1 human annotator (jaitra), blind; gap P 0.478, R 1.0; present R 0.20; bal acc 0.60; 24 disagreements (23 paraphrased, 19 in CMT_TR_007); "about half" = 24/46 silver gaps | `outputs/qmsum_spotcheck_mini_report.json` (`scripts/spotcheck_report.py --dir data/benchmark/spotcheck_mini`; the script writes `qmsum_spotcheck_report.json` -- copy it to the `_mini_` name and restore the original). 4th pair QMS_PRD_TR_089 not annotated |

## Deliberately NOT used

- "~47% completeness" -- retired (runbook Sec. 0): averaged two meetings under lexical scoring.
- Spot-check "gap F1 0.964 / balanced accuracy 0.836" -- from the `llm-review` model pass,
  not a human (runbook Sec. 3.3).
- NLI corpus-tier row and NLI pooled "all tiers" figures -- circular (NLI produced those labels).
- "External GraphRAG benchmarks show ~13% on conversational tasks" (plan) -- no verifiable
  source located; replaced by our own end-to-end measurement.
- "Zero hallucinated quotes across all five meetings" (`task5_benchmark_results.md`) -- wrong as
  stated: the gold unsupported-quote rate is 16.4%. What holds is that none of the 20 residual
  *misses* was caused by hallucination.
