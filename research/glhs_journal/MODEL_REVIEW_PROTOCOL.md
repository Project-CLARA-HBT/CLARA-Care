# Dual-Model Blinded Adjudication Surrogate

Status: `NOT RUN` until a frozen case manifest and `CLARA_ROUTER_API_KEY` are available.

Two locked models independently assess frozen subject/output packets using the same evidence-grounded rubric. This is a dual-model blinded adjudication surrogate, not clinician validation, expert adjudication, clinical effectiveness evidence, or a replacement for reference evidence. Labels cover current-state correctness, omission, unsupported assertion, stale-state use, conflict resolution, prohibited disclosure, material reasoning error when reference evidence determines it, and abstain/insufficient evidence.

Per-model labels, pre/post reconciliation agreement, Cohen's kappa, unresolved rate, and subject-level confidence intervals are reported. Calls, retries, and optional 10% duplicate consistency packets are not extra subjects.
