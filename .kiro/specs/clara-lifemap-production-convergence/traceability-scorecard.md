# LifeMap requirement traceability and GA scorecard

Date: 2026-07-28

## Traceability record template

Every requirement/task promotion record must include:

| Field | Required evidence |
| --- | --- |
| Requirement | Stable requirement ID and exact supported behavior |
| Hazards | Linked hazard IDs and mitigations |
| Implementation | Code, schema, configuration, and owner |
| Positive tests | Expected success paths |
| Negative tests | Invalid state, input, dependency, and degraded paths |
| Authorization | Cross-profile, grant, role, consent, and revocation tests |
| Privacy | Data classes, purpose, retention, redaction, no-PII telemetry |
| Clinical safety | Emergency/FIDES/legal guard and human-review evidence |
| Accessibility | Keyboard/screen reader/text scale/reduced motion where applicable |
| Operations | Metrics, alerts, SLO, runbook, backup/recovery |
| Rollout | Flag, allowlist/cohort, kill-switch owner, rollback window |
| Approval | Named Product/Clinical/Privacy/Security/Platform approvers |
| Result | Pass, fail, blocked, or not assessed—with date and artifact |

## GA scorecard

No section may be inferred from code completion. `PASS` requires immutable
evidence and the accountable owner’s approval.

| Gate | Accountable owner | Current state |
| --- | --- | --- |
| Intended/prohibited use and jurisdiction | Clinical Safety/Legal | BLOCKED—approval required |
| Hazard log and residual-risk acceptance | Clinical Safety | BLOCKED—approval required |
| Profile isolation and authorization | Security/API | FOUNDATION PASS |
| Truth/provenance/idempotency | API/Clinical Safety | FOUNDATION IMPLEMENTED; phase evidence incomplete |
| Durable outbox/recovery | Platform/API | ENGINEERING PASS |
| Universal Capture safety/evaluation | ML/Clinical Safety | NOT STARTED |
| Medication safety convergence | Clinical Safety/API | EXISTING SAFETY FLOOR; convergence incomplete |
| Visit extraction grounding | ML/Clinical Safety | BLOCKED—evaluation required |
| Family revocation/privacy | Privacy/Security | INCOMPLETE |
| Living Evidence applicability | Research/Clinical Safety | INCOMPLETE |
| FHIR/IPS conformance/licensing | Interoperability/Legal | BLOCKED—strategy and validator required |
| Web/mobile parity and accessibility | Web/Mobile/Product | FOUNDATION PASS; V2 flows incomplete |
| Penetration/privacy/DSAR certification | Security/Privacy | BLOCKED—formal exercises required |
| Load/restore/rebuild SLO | Platform | Worker engineering pass; GA certification incomplete |
| AI registry/artifact governance | ML/Security | INCOMPLETE |
| Prospective AI/user evaluation | Clinical Safety/Product | BLOCKED—approved study required |
| Migration/rollback/legacy retirement | Product/Platform | NOT ELIGIBLE |

## Release decision

General availability is denied while any required gate is `BLOCKED`,
`INCOMPLETE`, `NOT STARTED`, or `NOT ELIGIBLE`. Dark flags and compatibility
adapters must remain in place. A deployment of foundation code is not a GA
approval.
