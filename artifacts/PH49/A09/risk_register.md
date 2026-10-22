# Risk Register — PH49 A09 (Scientific Claim Linkage & Incident Support Runbook)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH49-A09-01 | Forensic export containing unredacted raw audio recordings | Critical | Low | Trace export bundles emit verified transcripts and hashes, excluding raw biometric audio. | Mitigated |
| RISK-PH49-A09-02 | Inability to reproduce historical snapshot digest | High | Low | Snapshot manifests store exact RFC 8785 canonical JSON bytes ensuring reproducible hashing. | Mitigated |
