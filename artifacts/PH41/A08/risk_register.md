# Risk Register — PH41 A08 (Threat Model & Network Segmentation)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH41-A08-01 | Shared reverse proxy misconfiguration exposing port 8200 control plane publicly | Critical | Low | Deploy specifications mandate separate ingress controller and VPN restriction for port 8200. | Mitigated |
| RISK-PH41-A08-02 | Browser cache retaining sensitive administrative views | High | Low | Control plane responses mandate `Cache-Control: no-store, private` headers unconditionally. | Mitigated |
