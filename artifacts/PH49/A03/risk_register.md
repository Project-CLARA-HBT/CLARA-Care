# Risk Register — PH49 A03 (GLHS Reconciliation & Deny Reasons)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH49-A03-01 | Unstructured rejection notes containing raw patient PII | High | Low | Deny reason codes categorize standard rejections; notes field audited for PII markers. | Mitigated |
| RISK-PH49-A03-02 | Inaccurate deny code categorization obscuring operational root causes | Medium | Low | Canonical enum `DenyReasonCode` formalizes standardized reasons across all clinical domains. | Mitigated |
