# Risk Register — PH42 A03 (OIDC Validation & Token Binding)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A03-01 | Stolen JWT token used on unauthorized physical device | Critical | Low | Device binding check validates `token.device_id == client_device_id`. | Mitigated |
| RISK-PH42-A03-02 | Service outage during signing key rotation | High | Low | Dual-key rotation supports both active and retiring keys simultaneously. | Mitigated |
