# Phase 3.3 — multi-hop retrieval baseline

- retriever: TF-IDF cosine, top-3 turns per hop
- decisions are given as input (the plan's own `multihop_extract(text, decision)` signature) -- decision recall is 100% by construction and excluded from the fair comparison column
- conditions are outside the plan's 3-hop chain (rationale -> alternatives -> objections) and are always misses here
- owner/approver are excluded from every column, as in EDIA's completeness
- excl.-decision columns match the gold elements against the RETRIEVED turns only: the handed-in decision text often resembles a gold rationale, and crediting that would count the method's own input as something it found

Both matchers are reported, with the same thresholds as the EDIA baseline (lexical 0.45, semantic 0.55).

| pair | lexical, incl. seeded decision | lexical, excl. decision | semantic, excl. decision |
|---|--:|--:|--:|
| QSUM_001 | 0.273 (3/11) | 0.000 (0/9) | 0.000 (0/9) |
| QSUM_002 | 0.125 (1/8) | 0.000 (0/7) | 0.000 (0/7) |
| QSUM_003 | 0.444 (4/9) | 0.000 (0/7) | 0.143 (1/7) |
| QSUM_004 | 0.286 (4/14) | 0.000 (0/11) | 0.273 (3/11) |
| QSUM_005 | 0.333 (2/6) | 0.000 (0/5) | 0.200 (1/5) |
| **total** | **0.292** (14/48) | **0.000** (0/39) | **0.128** (5/39) |

## Reading

**Use the excl.-decision columns for Table 4: 0.0% lexical / 12.8% semantic.** This baseline is handed its decisions, so the seeded column would flatter it on the one thing it was not asked to do.

Against EDIA's semantic-scored 58.3%, multi-hop retrieval's 12.8% semantic is the failure mode the plan predicted: rationale is retrieved by similarity to the decision text alone, before anything about *why* is known, so hop 1 frequently returns adjacent-topic turns rather than the actual reasoning -- and hops 2-3 compound that error since they query using hop 1's (possibly wrong) output.
