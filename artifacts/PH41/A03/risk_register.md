# Risk Register — PH41 A03 (Service-Token Gateway & Tenant Governor)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH41-A03-01 | Replay attack using captured internal service tokens | High | Low | Tokens carry explicit 300-second TTL timestamp and constant-time signature verification. | Mitigated |
| RISK-PH41-A03-02 | Service token interchange with end-user JWT authorization | Critical | Low | Distinct audience claim and cryptographic signing secret partitioned from user session keys. | Mitigated |
