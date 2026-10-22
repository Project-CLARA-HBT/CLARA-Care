# Risk Register — PH07 A07 (User-Facing Attestation Disclosure)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A07-01 | Fraudulent elevation of unverified model responses to L2/L3 in user UI | Critical | Low | Mapping function strictly requires `provider_receipt_verified == True` before elevation. | Mitigated |
| RISK-PH07-A07-02 | Null or missing binding crashing disclosure presentation | Medium | Low | Safe default fallback to `APPLICATION_ENVELOPE_ONLY` (L0) on null binding. | Mitigated |
