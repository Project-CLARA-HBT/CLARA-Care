# Risk Register — PH44 A05 (Org Lifecycle & Settings UI)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH44-A05-01 | Accidental suspension of active hospital tenant during high-volume hours | Critical | Low | UI provides confirmation dialogue and visually highlights suspension in red status chips. | Mitigated |
| RISK-PH44-A05-02 | Stale quota counts displayed in tenant row | Medium | Low | State updates immediately upon toggle and re-fetches from backend control plane. | Mitigated |
