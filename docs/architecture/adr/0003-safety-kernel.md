# ADR 0003: Safety kernel ownership

Status: accepted for PR-04/14 convergence.

Deterministic services own authorization, consent, CSRF, emergency escalation,
DrugBank readiness/lookup, schema/state validation, audit and final
allow/block/abstain. ML receives only permitted tasks and cannot override this
result. High-risk generated content requires independent verification/policy or
human review.

Rollback: safety guards are additive; model integrations may be disabled without
disabling existing deterministic controls.
