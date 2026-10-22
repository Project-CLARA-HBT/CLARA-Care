# Risk Register — PH42 A06 (Session Inventory & Revocation UX)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A06-01 | Accidental self-lockout from clicking revoke on current active device session | High | Low | UI omits revocation button for `sess.isCurrent` and distinguishes current device clearly. | Mitigated |
| RISK-PH42-A06-02 | Stale session list causing repeated failed termination requests | Medium | Low | Session list updates immediately after calling `onRevokeOtherDevices` or `onRevokeSession`. | Mitigated |
