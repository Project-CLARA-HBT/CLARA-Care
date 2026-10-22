# Risk Register — PH09 A06 (Background Job Card & Status UX)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A06-01 | Failed background task left without user recovery pathway | High | Low | UI presents explicit 'Thử lại' button wired to client retry callback. | Mitigated |
| RISK-PH09-A06-02 | Indefinite indeterminate loading bar misleading user on progress | Medium | Low | Uses bounded progress when value > 0; falls back to indeterminate animation gracefully. | Mitigated |
