# Risk Register — PH08 A01 (Clinical Dependency Schema Registry)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A01-01 | Unregistered dependency kind injected into proposal dependency vector | High | Low | Database constraint `ck_glhs_proposal_dep_kind` enforces enum membership. | Mitigated |
| RISK-PH08-A01-02 | Key collisions between different patients due to unstructured key formatting | Critical | Low | Key patterns mandate namespaced `{patient_id}` or `{session_id}` segments. | Mitigated |
