# Risk Register — PH06 A08 (Stale-Write & Downgrade Threat Model)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A08-01 | Stale write overwriting concurrent clinician medication changes | Critical | Low | Optimistic Concurrency Control (OCC) revalidates version under lock and rejects stale observed versions with 409. | Mitigated |
| RISK-PH06-A08-02 | Review proposal circular reference locking commit kernel | High | Low | Traversal algorithm tracks visited IDs and enforces depth <= 4 bound. | Mitigated |
