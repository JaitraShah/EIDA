# Phase 3.3 — multi-hop retrieval baseline

- retriever: TF-IDF cosine, top-3 turns per hop
- decisions are given as input (the plan's own `multihop_extract(text, decision)` signature) -- decision recall is 100% by construction and excluded from the fair comparison column
- conditions/owner/approver are outside the plan's 3-hop chain (rationale -> alternatives -> objections) and are always misses here

| pair | completeness (incl. seeded decision) | completeness (excl. decision, fair vs EDIA) |
|---|--:|--:|
| QSUM_001 | 0.273 (3/11) | 0.111 (1/9) |
| QSUM_002 | 0.125 (1/8) | 0.000 (0/7) |
| QSUM_003 | 0.444 (4/9) | 0.286 (2/7) |
| QSUM_004 | 0.267 (4/15) | 0.083 (1/12) |
| QSUM_005 | 0.286 (2/7) | 0.167 (1/6) |
| **total** | **0.280** (14/50) | **0.122** (5/41) |

## Reading

**Use 12.2% for Table 4** (the EDIA pipeline column also excludes nothing, but must discover its decisions -- this baseline is handed them, so comparing the seeded number would flatter multi-hop retrieval on the one thing it was not asked to do).

Against EDIA's semantic-scored 58.3%, multi-hop retrieval's 12.2% is the failure mode the plan predicted: rationale is retrieved by similarity to the decision text alone, before anything about *why* is known, so hop 1 frequently returns adjacent-topic turns rather than the actual reasoning -- and hops 2-3 compound that error since they query using hop 1's (possibly wrong) output.
