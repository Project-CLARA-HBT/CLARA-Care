# Risk Register — PH40 A04 (ML Provider Boundaries & Safe Fallbacks)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH40-A04-01 | Silent fallback to ungrounded or mock LLM generation upon API timeout | Critical | Low | Circuit breaker trips directly to safe emergency escalation; FIDES critical checks fail-closed. | Mitigated |
| RISK-PH40-A04-02 | Leakage of medical queries to unauthorized cloud model endpoints | Critical | Low | Strict DeepSeek-only runtime enforced (`LLM_DEEPSEEK_ONLY=true`) with audited provider adapters. | Mitigated |
