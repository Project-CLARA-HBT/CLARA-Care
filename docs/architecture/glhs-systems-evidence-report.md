# GLHS systems evidence report

Updated: 2026-08-12. This is synthetic engineering evidence, not a production,
clinical, interoperability or publication-quality claim.

## Verified outcomes

The atomic-transition contract ran on rootless PostgreSQL 16.14. For each of
the same-slot and unrelated-slot workloads, four writers declared base version
zero concurrently; exactly one committed and three failed closed as stale. The
pytest result was 1 passed with two unrelated FastAPI deprecation warnings.
JUnit SHA-256:
`046c3a1399027894617f8781919e8990efb79b8de944b6851ac26d2711e3abfb`.

The clean service-layer run used implementation commit
`36642787931e5ce429f73e8087c6a2ef66e71307`, PostgreSQL image digest
`sha256:7a396fd264a2067788b6551122b50f162bf6136312c7fc9d74381cb92c648382`,
Alembic revision `20260811_0055`, read-committed isolation, synchronous commit,
one worker, history depth 50 and 30 repetitions per operation. The manifest
records `tracked_worktree_clean=true` and no PHI. Raw evidence is under
`evaluation/fullstack_benchmark/evidence/2026-08-12-clean-service-layer/`;
the checksum-inventory SHA-256 is
`75115757d7acec428d9291c567e12a2477f909990627d3f10e8bce40a8911336`.

| Service-layer operation | p50 ms | p95 ms | p99 ms | ops/s | SQL reads | SQL writes | writes/op |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GST transition | 30.967 | 54.685 | 80.501 | 29.952 | 418 | 270 | 9.0 |
| State reconstruction | 7.298 | 12.299 | 13.372 | 129.688 | 90 | 0 | 0.0 |
| THSS snapshot compilation | 61.806 | 68.889 | 73.277 | 16.937 | 1,740 | 60 | 2.0 |
| Governed-decision reconstruction | 10.537 | 17.011 | 17.347 | 95.350 | 240 | 0 | 0.0 |
| Audit lookup | 2.122 | 5.501 | 5.564 | 399.149 | 60 | 0 | 0.0 |
| Invalidation and rebuild | 52.996 | 74.336 | 77.892 | 18.295 | 1,515 | 210 | 7.0 |
| Enter-in-error and rebuild | 69.314 | 87.309 | 169.471 | 13.818 | 1,440 | 480 | 16.0 |

SQL counts are totals over 30 repetitions; `writes/op` is the corresponding
amplification. Latencies include transaction finalization in the in-process
API-owned gateway path. Provider/model inference is absent. Peak process RSS
across rows was 114,569,216 bytes; this single-process observation is not a
capacity estimate.

## Failed/developmental run ledger

1. The original runner failed with `transition_action_forbidden`; its fixture
   scope omitted the `correct` and `invalidate` permissions required by the
   operations it attempted. No result artifact was emitted.
2. After that repair, a five-operation run completed but was invalidated for
   evidence use: it created tables from ORM metadata rather than Alembic and
   incorrectly labelled `enter_in_error` as source revocation.
3. The first v2 attempt failed closed with
   `proposal_manifest_digest_mismatch`; the bound-decision fixture supplied the
   payload fingerprint where the contract requires the manifest fingerprint.
   No result artifact was emitted.
4. A corrected v2 developmental run validated but recorded a dirty tracked
   worktree, so it was not retained as the clean result.
5. The clean-SHA run above passed the v2 schema, metric, environment, operation,
   finite-number and SHA-256 validators.

## Explicit gaps

- The metrics are service-layer, concurrency-one measurements; HTTP transport
  and worker/process scaling were not measured.
- The full-stack runner does not yet execute actual source-revocation
  propagation or concurrent transitions. It names `enter_in_error` accurately
  and lists all three omissions in `coverage_gaps`.
- The N=4 race establishes atomic safety for two enumerated workloads. It does
  not measure false-stale rate, retry behavior, alternative version strategies,
  or levels 1/2/4/8/16.
- No deployed-boundary adversarial matrix, provider call, clinical label or
  real-world dataset was used. Workstream C therefore remains PARTIAL.

Revalidate the saved artifact without network access:

```bash
PYTHONPATH=. services/api/.venv/bin/python \
  -m evaluation.fullstack_benchmark.validate_metrics \
  --metrics evaluation/fullstack_benchmark/evidence/2026-08-12-clean-service-layer/fullstack_metrics.csv \
  --manifest evaluation/fullstack_benchmark/evidence/2026-08-12-clean-service-layer/fullstack_manifest.json
```
