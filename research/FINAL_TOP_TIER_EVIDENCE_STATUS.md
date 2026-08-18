# CLARA-Care Q1/SOTA Evidence Upgrade — Final Status

Status generated from sealed evidence and the master-spec Section 20 gate. This is an
honest self-assessment; every box reflects actual sealed artifacts, not aspirational state.

## Stream results (sealed)

### RIVF / GovRed
- Run `2026-08-17-rivf-final-003`, source `5b2c0dbf`, 270 executed/arm, primary denominator 210/arm, NOT_RUN 180/arm (excluded, never zeroed).
- Primary (stale/unauthorized-commit acceptance): UNBOUND 0.571 (0.504-0.636), STATE_VERSION_ONLY 0.429 (0.364-0.496), SNAPSHOT_BOUND_STATE_ONLY 0.429 (0.364-0.496), GLHS_STRICT 0.143 (0.102-0.197).
- Paired exact McNemar GLHS_STRICT vs UNBOUND: b=90, c=0, p=1.62e-27 (log10 -26.79). No underflowed zero.
- Residual localization (W1): all 30 GLHS_STRICT primary residuals are family `concurrent_stale_state_write` (INDETERMINATE_ORDERING); serial authorization-drift families = 0 invalid commits.
- Prohibited disclosure 0/270 every arm. Cache measurement now observer-only (AUD-014 fixed).
- Gate boxes: integrity PASS; mandatory-primary NOT_RUN=0 FAIL (180/arm); fresh-holdout deterministic 0-invalid-commit FAIL (not yet run); valid-operation noninferiority controls FAIL (schema+controls exist, not executed); no-disclosure with CI PASS; cache observer-only PASS; rejection auditability FAIL (contract exists, not executed); committed reconstruction PASS (v2). NOT top-tier candidate yet.

### GLHS Journal
- v1 run `GLHS-POSTGRES-TOCTOU-FINAL-20260817-01` (5 schedules) + v2 run `GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01` (12 schedules, source `67e528b6`).
- v2: 12 schedules, 10 rejected, 1 committed-before-revoke control, 0 forbidden commits, persisted writers consent/role/policy-epoch, 0 indeterminate, 0 deadlock-as-safety.
- Formal assurance: 21,361 states / 90,432 transitions, 0 invariant violations (bounded, not universal proof).
- Gate boxes: persisted writers PASS; ordering evidence PASS; indeterminate never counted safe PASS; barrier-controlled interleavings PASS; compound drift PASS; false-stale burden FAIL (not measured); operational metrics PARTIAL (latency recorded). Not a complete top-tier concurrency study yet.

### SOICT / GovMut
- Freeze `govmut-soict-2026-final-v2`, source `ab877e04`, 45 mutants x 16 slots = 720, 0 infra errors.
- Mutation scores: M0 0.356, M1 0.089, M2 0.133, M3 0.444. M3 subsumes M0 and significantly beats M1/M2 (McNemar p=3.05e-05 vs M1).
- Unmutated baseline preflight: all 16 method/seed PASS (no false kills).
- Gate boxes: current 45-mutant sealed PASS; no-false-kill PASS; seed aggregation prespecified PASS; M0-M3 complete PASS; family/invariant stratification PASS; paired comparisons PASS; infra not counted PASS. GovMut gate PASS.

## Direct-comparison honesty
- No faithful same-task MemTX/MemTxn/CommitGuard execution exists (ASSET_GATED). The strongest permissible wording is per-stream (GLHS_STRICT vs UNBOUND/STATE_VERSION_ONLY/SNAPSHOT_BOUND_STATE_ONLY on the prespecified endpoint), never "better than all prior work."

## Remaining blockers to TOP_TIER
1. RIVF: run fresh confirmatory holdout (dev/validation/final partitions), valid-operation noninferiority controls, rejection-auditability execution, mandatory-primary NOT_RUN=0.
2. GLHS: false-stale burden measurement, concurrency level scaling (1/2/4/8/16), commit of policy-epoch schema migration.
3. W6 utility: source-disjoint cohort execution needs CLARA_ROUTER_API_KEY (not present in this session); then safety + noninferiority + latency.
4. W9: proposed 11-mutant follow-up corpus needs new freeze + hardened W7 review + M0-M3 + seal.

CareGuard-VN: PAUSED_BY_OPERATOR.
No DAV crawl or CareGuard source acquisition was performed by this evidence-upgrade program.
