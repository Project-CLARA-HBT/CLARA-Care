# GLHS — Limitations & Reproducibility

## Limitations

1. TOCTOU-03 (concurrent governance writer vs proposal writer) committed a transition whose interleaving could not be established; it is reported INDETERMINATE, not as a success or a violation.
2. TOCTOU-05 audit-completeness is asserted by the observer contract (proposal commit, not transition commit); this interpretation must be accepted by a reviewer per the statistics plan.
3. No frozen subject/output adjudication packets existed, so the dual-model run is protocol QA only; it is never described as human/clinician/expert adjudication.
4. The matrix uses synthetic governance records on a fresh isolated PostgreSQL; it is not a production conformance certificate.

## Reproducibility

- Code revision: `2074f87550c5ee32302bde47bc0b9e6be6af36b5`
- Runner: `evaluation/glhs_postgres_toctou/final_frozen_runner.py --execute`
- Observer: `evaluation.glhs_postgres_toctou.postgres_observer:observe`
- Protocol: `research/glhs_journal/postgres_toctou_protocol.json`
- DB: fresh `glhs_final` on isolated postgres `clara-rivf-20260817-final001-postgres-1`, random schema, dropped after run
- Raw result: `artifacts/glhs-postgres-toctou/GLHS-POSTGRES-TOCTOU-FINAL-20260817-01/result.json`
- Analysis: `research/glhs_journal/results/analysis.json`
- Sealed inventory: `artifacts/glhs-postgres-toctou/GLHS-POSTGRES-TOCTOU-FINAL-20260817-01/artifact-sha256.json`
