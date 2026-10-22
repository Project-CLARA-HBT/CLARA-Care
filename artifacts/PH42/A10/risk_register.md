# Risk Register — PH42 A10 (Hostile OIDC MFA Tests & Quality Gate)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A10-01 | Adversarial tampering with JWT claims to claim administrative roles | Critical | Low | HMAC/RSA signatures verified against pinned public keysets rejecting `alg: none`. | Mitigated |
| RISK-PH42-A10-02 | Quality gate drift from frozen baseline commit invariants | High | Low | Automated SHA verification anchored to pinned commit with DAG merge-base descent checks. | Mitigated |
