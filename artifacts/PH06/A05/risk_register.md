# Risk Register — PH06 A05 (Commit Kernel Entity Dependency Wiring)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A05-01 | Silent lost update when two clinicians concurrently edit the same record | Critical | Low | Client attaches `observedVersion`; server OCC CAS rejection (HTTP 409) forces re-fetch and merge. | Mitigated |
| RISK-PH06-A05-02 | Client sending unparseable or malformed dependency vectors | Medium | Low | `CommitKernelClient` provides typed builder enforcing strict `ClientDependencySpec` invariants. | Mitigated |
