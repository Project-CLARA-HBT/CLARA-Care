# Risk Register — PH43 A06 (Permission Diff/Preview Modal)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH43-A06-01 | Unintended permission expansion accepted due to obscured visual diff | High | Low | Modal visually splits added (green +) and removed (red -) permissions explicitly. | Mitigated |
| RISK-PH43-A06-02 | Privileged changes bypassing step-up warning | Critical | Low | Banner flags `diff.requiresMfaApproval` prominently when destructive permissions are modified. | Mitigated |
