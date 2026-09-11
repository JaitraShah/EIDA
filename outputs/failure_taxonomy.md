# Phase 2.4 — extraction failure taxonomy

Scope: the 5 gold Product/test meetings (QSUM_001–005) — the only meetings with
hand-built reasoning ground truth. Misses are the **semantic**-scorer residual,
so lexical scoring artifacts are excluded by construction.

Annotated: **20** of 20 residual misses.

| Failure category | n | share |
|---|--:|--:|
| Multi-hop: scattered -- reasoning spread across 3+ turns far apart | 5 | 25% |
| Multi-hop: implicit -- connection never stated directly; inferred | 6 | 30% |
| Chunking boundary -- reasoning split across a chunk cut | 0 | 0% |
| Paraphrase miss -- found but worded differently; scorer missed it | 5 | 25% |
| Model hallucination -- extractor invented a quote not in source | 0 | 0% |
| Out of scope -- present in transcript, model chose not to extract | 4 | 20% |

## By meeting

| pair | multihop_scattered | multihop_implicit | chunk_boundary | paraphrase_miss | hallucination | out_of_scope |
|---|---|---|---|---|---|---|
| QSUM_001 | 2 | 1 | 0 | 1 | 0 | 0 |
| QSUM_002 | 0 | 1 | 0 | 0 | 0 | 0 |
| QSUM_003 | 2 | 3 | 0 | 1 | 0 | 1 |
| QSUM_004 | 0 | 1 | 0 | 2 | 0 | 2 |
| QSUM_005 | 1 | 0 | 0 | 1 | 0 | 1 |

## Reading

Multi-hop categories account for **11/20 (55%)** of residual misses.
