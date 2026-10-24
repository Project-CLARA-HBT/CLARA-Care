# Risk Register — PH51 A06 (Retry Approval & Redacted Failure Inspector Components)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A06-01 | Hasty retry without understanding failure context or consent revocation | High | Low | Modal enforces mandatory explanation (>5 chars) and explicit checkbox certification of consent check. | Mitigated |
| RISK-PH51-A06-02 | Leakage of stack traces containing patient query or prescription details | Critical | Low | Inspector displays sanitizedStackTrace with explicit PHI redaction badge. | Mitigated |
