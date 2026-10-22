# Risk Register — PH10 A01 (Event/Assertion/Evidence Typed Contract)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH10-A01-01 | Unlinked clinical assertions floating without source evidence provenance | Critical | Low | Contract mandates non-empty `evidence_id` and content hash for confirmed assertions. | Mitigated |
| RISK-PH10-A01-02 | Erasure of disputed clinical events under false consensus | High | Low | Assertion vocabulary explicitly includes `UNCERTAIN` and `REFUTED` to preserve clinical disagreement. | Mitigated |
