# GLHS malformed-output offline audit (GLHS-M01..M03)

Status: **OFFLINE / DESCRIPTIVE** — no model was rerun; no run artifact was modified.

## 1. Primary comparison is UNCHANGED

The sealed 384-subject primary comparison remains unchanged (GLHS-M01): malformed outputs are fail-closed errors under the original scoring. This audit only decomposes immutable raw results; it never re-scores, never excludes, and never replaces the primary null endpoint.

## 2. Seal / checksum verification (read-only)

- `checksums.sha256`: **VERIFIED**
- Files checked: 49

| Status | Count |
| --- | ---: |
| OK | 49 |

## 3. Total malformed outputs

- **Actual malformed in the audited run directory: 0** of 360 expected solver cells.
- Source artifact subjects: 2; the original primary null endpoint remains the sealed 384-subject comparison.
- Parsed outputs: 360; missing outputs: 0.

> The manuscript companion figure (~220 malformed) refers to the sealed **v5-batch5 384-subject router run** (3,456 cells, 3,236 parsed + 220 malformed). Its raw outputs were retained outside the tracked tree (`/tmp/clara-glhs-v5-batch5-live-run`) and are **not present in this repository**, so the ~220 decomposition cannot be reproduced from tracked artifacts. This report states the actual count for the artifacts that ARE present and verifiable.

## 4. Rate by context condition

| Condition | Malformed | Denominator | Rate |
| --- | ---: | ---: | ---: |
| btsa | 0 | 40 | 0.000000 |
| full_authorized_history | 0 | 40 | 0.000000 |
| glhs_hybrid | 0 | 40 | 0.000000 |
| glhs_hybrid_thss_strict | 0 | 40 | 0.000000 |
| glhs_no_bitemporal_knowledge_time | 0 | 40 | 0.000000 |
| glhs_no_predicate_engine | 0 | 40 | 0.000000 |
| long_context_chronological | 0 | 40 | 0.000000 |
| lww | 0 | 40 | 0.000000 |
| naive_rag | 0 | 40 | 0.000000 |

## 5. Rate by task

| Task | Malformed | Denominator | Rate |
| --- | ---: | ---: | ---: |
| reconcile_future_oriented_commitment | 0 | 360 | 0.000000 |

## 6. Rate by subject stratum

| Stratum | Malformed | Denominator | Rate |
| --- | ---: | ---: | ---: |
| validation | 0 | 360 | 0.000000 |

## 7. Failure-type distribution (parse / schema / format / other)

| Failure type | Count |
| --- | ---: |
| parse | 0 |
| schema | 0 |
| format | 0 |
| other | 0 |

## 8. Paired Strict vs full-history malformed contingency (per subject)

| Bucket | Count |
| --- | ---: |
| both | 0 |
| strict_only | 0 |
| full_only | 0 |
| neither | 2 |

- Subjects with a malformed output under `glhs_hybrid_thss_strict` and/or `full_authorized_history`; subjects with no malformed cell in either condition are `neither`.

## 9. Sensitivity (GLHS-M03)

Any alternative analysis (complete-case, parse-recoverable subset, etc.) is **EXPLORATORY / post-hoc** and must never replace the original null endpoint. This audit contains no such alternative analysis.

- Audited run directory: `artifacts/commitloop/local-phase-a-v6`
- Audit schema: `glhs-malformed-audit-v1`
