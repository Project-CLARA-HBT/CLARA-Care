# LifeMap V2 threat model

Status: implemented security baseline; review owner: Security
Last updated: 2026-07-28

## Assets and trust boundaries

LifeMap facts, revisions, episodes, tasks, commands, grants, source references,
and derived projections are health data. Browser/mobile profile identifiers are
untrusted hints. The API is the authorization boundary; PostgreSQL is the
canonical store; the standalone outbox worker receives only committed,
profile-bound minimum-data envelopes. ML/OCR outputs are untrusted candidates
and never authority for confirmation.

## Threats and enforced controls

| Threat | Control | Regression evidence |
| --- | --- | --- |
| IDOR through object or profile IDs | Server-resolved `ProfileScope`; every object query includes canonical `profile_id`; public V2 IDs are opaque | `test_profile_context_cannot_be_used_as_an_idor_or_enumeration_oracle`, `test_every_lifemap_object_route_enforces_profile_non_interference` |
| Identifier enumeration | Unknown and unauthorized profiles return the same 404/code/body; no numeric IDs in V2 responses | `test_profile_context_cannot_be_used_as_an_idor_or_enumeration_oracle`, `test_generic_capture_cannot_claim_confirmation_and_ids_are_opaque` |
| Role confused with capability | Doctor/admin role grants no health-data access. Clinicians require a live explicit grant; admin/support requires a separate break-glass design and is denied/audited now | `test_doctor_requires_a_live_grant_and_admin_role_is_not_profile_access` |
| Confused deputy / profile swap | Grants bind grantee, exact profile, object, data class, action, purpose, and time window | `test_expired_grant_and_confused_deputy_profile_swap_fail_closed`, `test_family_grant_rejects_data_class_escalation` |
| Invitation/token replay | Capability is recipient-bound, hashed at rest, excluded from URL handling, and materializes at most one grant | `test_family_accept_uses_body_or_header_and_is_idempotent`, migration constraint `uq_family_access_grants_invitation` |
| Expired/revoked grant use | Every request reads authoritative live grant state; revocation increments `grant_version`; derived notifications re-resolve live state | `test_expired_grant_and_confused_deputy_profile_swap_fail_closed`, `test_doctor_requires_a_live_grant_and_admin_role_is_not_profile_access`, `test_family_notification_is_minimal_live_and_owner_auditable` |
| Cross-profile background processing | Transactional outbox rows carry an internal profile FK; worker resolves that row to exactly one opaque profile ID and emits no clinical payload | `test_drain_publishes_pending_events_and_marks_them_published`, `test_skip_locked_claims_are_disjoint_and_expired_lease_recovers` |
| Mutation replay/substitution | Actor+profile+operation+key binding, canonical request digest, and conflict-on-digest-change | `test_command_replay_is_stable_and_digest_conflicts_fail_closed` |
| Audit suppression | Changes and reads append minimum-data PHR audit rows; Family grants append allow/deny/revocation decisions; denied support attempts are recorded | `test_lifemap_reads_and_changes_append_minimum_data_audit_records`, `test_doctor_requires_a_live_grant_and_admin_role_is_not_profile_access` |
| ML prompt/document injection | Extracted content is untrusted data, cannot issue commands, and cannot become confirmed truth without typed user review | Capture and extraction phases retain this as an exit-gate requirement |

## Residual risks and operational rules

- Break-glass support access is not implemented. Admin access is fail-closed
  until a separately approved, time-bounded, reason-coded workflow exists.
- Do not put invitation capabilities in paths, query strings, telemetry, or
  support tickets.
- A grant cache may never outlive a request. Any future cache must key on
  `grant_version` and receive revocation invalidations before rollout.
- New background consumers must accept opaque profile context from the outbox
  envelope and must not query by aggregate ID alone.
- Capture/AI phases must complete artifact malware controls and adversarial
  prompt-injection evaluation before their flags can leave the allowlist.
