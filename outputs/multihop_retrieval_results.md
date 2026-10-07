# Phase 3.3 — multi-hop retrieval baseline

- retriever: TF-IDF cosine, top-3 turns per hop
- decisions are given as input (the plan's own `multihop_extract(text, decision)` signature) -- decision recall is 100% by construction and excluded from the fair comparison column
- conditions/owner/approver are outside the plan's 3-hop chain (rationale -> alternatives -> objections) and are always misses here

Both matchers are reported, with the same thresholds as the EDIA baseline (lexical 0.45, semantic 0.55).

| pair | lexical, incl. seeded decision | lexical, excl. decision | semantic, excl. decision |
|---|--:|--:|--:|
| QSUM_001 | 0.273 (3/11) | 0.111 (1/9) | 0.222 (2/9) |
| QSUM_002 | 0.125 (1/8) | 0.000 (0/7) | 0.143 (1/7) |
| QSUM_003 | 0.444 (4/9) | 0.286 (2/7) | 0.286 (2/7) |
| QSUM_004 | 0.267 (4/15) | 0.083 (1/12) | 0.333 (4/12) |
| QSUM_005 | 0.286 (2/7) | 0.167 (1/6) | 0.333 (2/6) |
| **total** | **0.280** (14/50) | **0.122** (5/41) | **0.268** (11/41) |

## Reading

**Use the excl.-decision columns for Table 4: 12.2% lexical / 26.8% semantic.** This baseline is handed its decisions, so the seeded column would flatter it on the one thing it was not asked to do.

Against EDIA's semantic-scored 58.3%, multi-hop retrieval's 26.8% semantic is the failure mode the plan predicted: rationale is retrieved by similarity to the decision text alone, before anything about *why* is known, so hop 1 frequently returns adjacent-topic turns rather than the actual reasoning -- and hops 2-3 compound that error since they query using hop 1's (possibly wrong) output.
