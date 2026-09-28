# E04 PostgreSQL TOCTOU Campaign: Derived Summary

## Executive Summary
- **Total Schedules Executed:** 2,280 against PostgreSQL 16.14 under SERIALIZABLE isolation
- **Forbidden Commits:** 0 (0/2,280, Upper 95% Clopper-Pearson bound: < 0.16%)
- **Deadlocks:** 0 observed (100% total lock hierarchy ordering)
- **Clean Control Commit Rate:** 100.0% (1,140/1,140)
- **Claim Eligibility:** TRUE
