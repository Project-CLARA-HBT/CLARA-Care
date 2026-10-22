# Risk Register — PH07 A02 (D2 Semantic Digest Indexing)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A02-01 | Slow table scan during D2 semantic envelope digest verification in GRWC Phase 3 | Medium | Low | Indexes created on `semantic_envelope_digest` and `transport_payload_digest`. | Mitigated |
| RISK-PH07-A02-02 | Index locking blocking write traffic | Low | Low | Standard b-tree indexes created cleanly via Alembic batch alter table. | Mitigated |
