# Risk Register — PH40 A01 (Web Route Capability Inventory)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH40-A01-01 | Drift between route-capability matrix markdown and live Next.js app routes | Medium | Low | Checked-in machine contract `contracts/control-plane/web_routes_capability_inventory.v1.json` validated against `route-matrix:check` CI script. | Mitigated |
| RISK-PH40-A01-02 | Unintended public exposure of control plane endpoints on port 8000 | High | Low | Control router explicitly mounted under isolated `/control/v1` prefix and designed for segregated port 8200 binding. | Mitigated |
