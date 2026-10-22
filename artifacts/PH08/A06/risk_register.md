# Risk Register — PH08 A06 (Staleness UI Rejection Taxonomy)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A06-01 | Silent discard of offline clinician documentation upon server version conflict | Critical | Low | Taxonomy directs UI to auto-refresh background data while retaining local unsaved draft text. | Mitigated |
| RISK-PH08-A06-02 | Unrecognized error string causing app crash | Medium | Low | Safe default fallback maps unclassified errors to `unknownConflict` with graceful retry. | Mitigated |
