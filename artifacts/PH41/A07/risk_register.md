# Risk Register — PH41 A07 (Forbidden Cross-Origin Admin Use)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH41-A07-01 | Browser cross-site script accessing administrative control endpoints | Critical | Low | Strict origin segregation, absence of public CORS headers, and port isolation. | Mitigated |
| RISK-PH41-A07-02 | End-user JWT token accepted by control-plane API | High | Low | Control-plane uses separate token verification logic rejecting end-user session subjects. | Mitigated |
