# CLARA Deep Beta Research Benchmark

- run_id: `deepbeta-research-20260419`
- started_at_utc: `2026-04-19T01:42:13.283535+00:00`
- finished_at_utc: `2026-04-19T01:53:15.505738+00:00`
- endpoint: `http://127.0.0.1:8110/v1/research/tier2`
- cases: `data/demo/deepbeta_research_benchmark_cases.json`
- report_json: `artifacts/deepbeta-research/deepbeta-research-20260419/deepbeta-research-benchmark-report.json`

## Classification Metrics

| Metric | Value |
|---|---:|
| Accuracy | 50.00% |
| Precision | 50.00% |
| Recall | 100.00% |
| Specificity | 0.00% |
| F1 Score | 66.67% |
| Balanced Accuracy | 50.00% |
| Log Loss | 0.6601 |
| Brier Score | 0.2388 |

## Retrieval Metrics

| K | Precision@K (macro) | Recall@K (macro) | F1@K (macro) | Precision@K (micro) | Recall@K (micro) | F1@K (micro) |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 72.22% | 55.56% | 60.56% | 72.22% | 55.56% | 62.80% |
| 5 | 60.00% | 55.56% | 55.49% | 62.07% | 55.56% | 58.63% |
| 10 | 63.19% | 61.11% | 61.82% | 70.59% | 61.11% | 65.51% |

## Runtime Metrics

- Latency p50: **109565.73 ms**
- Latency p95: **118277.68 ms**
- Latency max: **118504.39 ms**
- Fallback rate: **0.00%**
- Keyword pass rate: **100.00%**
- End-to-end case pass rate: **50.00%**

## Per-case

| Case | Expected Risk | Pred Risk | P(risk) | Correct | Keyword Recall | Fallback | Latency (ms) | Citations | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| DBR-001 | 1 | 1 | 0.796 | 1 | 50.0% | 0 | 112613.2 | 15 | ok |
| DBR-002 | 1 | 1 | 0.718 | 1 | 60.0% | 0 | 117597.6 | 4 | ok |
| DBR-003 | 1 | 1 | 0.796 | 1 | 50.0% | 0 | 118504.4 | 15 | ok |
| DBR-004 | 0 | 1 | 0.640 | 0 | 25.0% | 0 | 104824.1 | 9 | ok |
| DBR-005 | 0 | 1 | 0.718 | 0 | 25.0% | 0 | 106518.3 | 8 | ok |
| DBR-006 | 0 | 1 | 0.587 | 0 | 25.0% | 0 | 101558.3 | 16 | ok |

## Notes

- `log_loss` ở đây là **evaluation loss** (binary cross-entropy trên xác suất dự đoán từ output runtime), không phải training loss nội bộ của model.
- `recall@k` được tính theo coverage của `expected_source_hints` trong top-k citations.
