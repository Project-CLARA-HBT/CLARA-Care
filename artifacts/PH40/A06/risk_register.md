# Risk Register — PH40 A06 (Mobile Screen Entrypoints & Dark Flags Audit)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH40-A06-01 | Mistaking intentional fail-closed safety gates for defective or stubbed implementations | High | Medium | Verified with clinical invariants: unconsented or unauthorized states MUST show inert placeholders rather than executing network actions. | Mitigated |
| RISK-PH40-A06-02 | Stale feature flags lingering in client code beyond pilot duration | Medium | Low | Feature flags cataloged and audited against central configuration in `services/api/src/clara_api/core/config.py`. | Mitigated |
