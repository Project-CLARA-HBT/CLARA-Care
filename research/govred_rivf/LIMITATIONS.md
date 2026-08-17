# RIVF / GovRed — Limitations & Reproducibility

## Limitations

1. Synthetic-data-only study; no production traffic or clinical content involved.
2. `NOT_RUN` cases (180 per arm) are protocol exclusions/unsupported adapter families; they contribute to no denominator and are never counted as zero failures.
3. Concurrent governance-writer interleavings whose ordering cannot be established are not claimed as safe; per-arm concurrency classification is preserved in raw observations.
4. Cache invalidation is service-owned; the adapter seeds disclosure through the ordinary application route and observes, never directly invalidates cache.
5. Dual-model protocol QA for RIVF is pending router availability and is recorded as such; this does not alter the executed matrix.

## Reproducibility

- Code revision: `5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb`
- Adapter: `evaluation.governance_adversarial.isolated_boundary_adapter:adapter`
- Manifest: `artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json`
- Env: isolated compose project `clara-rivf-20260817-final001`, port 18180, dedicated postgres/redis
- Raw results: `artifacts/govred/2026-08-17-rivf-final-003/{ARM}/raw_results.csv`
- Analysis: `research/govred_rivf/results/analysis.json`
- Sealed inventory: `artifacts/govred/2026-08-17-rivf-final-003/artifact-sha256.json`
