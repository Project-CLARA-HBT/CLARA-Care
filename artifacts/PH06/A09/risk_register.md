# Risk Register — PH06 A09 (Forensic Trace Redaction Audit)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A09-01 | Plaintext patient names or CCCD numbers leaking into outbox events | Critical | Low | Outbox schemas use pseudonymized public UUIDs and semantically bounded transition payloads. | Mitigated |
| RISK-PH06-A09-02 | Forensic digests exposing patient text via dictionary attack | High | Low | Salted canonical hashes combined with non-enumerable UUID identifiers. | Mitigated |
