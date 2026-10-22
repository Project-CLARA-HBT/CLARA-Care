# Risk Register — PH41 A06 (Admin Design Tokens & Accessible Shell)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH41-A06-01 | Accessibility failure in dark-mode dense operational dashboard | Medium | Low | Design tokens enforce WCAG AAA contrast ratios for all critical text and status chips. | Mitigated |
| RISK-PH41-A06-02 | Inadvertent sharing of consumer web UI state with administrative shell | High | Low | Segregated component library under `apps/admin/components` completely isolated from `apps/web/components`. | Mitigated |
