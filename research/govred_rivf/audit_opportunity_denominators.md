# GovRed RIVF — Audit opportunity denominators (E-007/E-008, GRD-04)

GRD-04 defines separate denominators and requires completeness to be reported **only within each eligible opportunity set**. Raw cross-arm counts (e.g. ``audit_reconstruction_complete`` totals) are never completeness.

## Opportunity kinds and eligibility

| Kind | Eligible set | Required record |
| --- | --- | --- |
| rejected_operation_decision_record | executed **rejected** operations | rejection reason code + coordinates + zero-transition-rows |
| committed_operation_exact_reconstruction | executed **committed** operations | exact reconstruction (transition + state version + snapshot linkage) |
| governance_mutation_trace_linkage | executed governance-mutation families | transaction trace + commit-order evidence |

## Summary (completeness within eligible sets only)

| Kind | eligible_n | complete_n | completeness (eligible set only) | observer emitted? |
| --- | ---: | ---: | ---: | --- |
| rejected_operation_decision_record | 630 | 0 | 0.000 | no |
| committed_operation_exact_reconstruction | 450 | 180 | 0.400 | yes |
| governance_mutation_trace_linkage | 960 | 0 | 0.000 | no |

## Per family/arm detail (eligibility only)

| opportunity_kind | arm | family | eligible_n | complete_n | completeness | observer emitted? |
| --- | --- | --- | ---: | ---: | ---: | --- |
| rejected_operation_decision_record | GLHS_STRICT | authorization_consent_toctou | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | GLHS_STRICT | cross_subject_proposal_write | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | GLHS_STRICT | derived_cache_persistence_after_revocation | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | GLHS_STRICT | digest_expiry_tamper_replay | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | GLHS_STRICT | revoked_consent_cache_index_reuse | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | GLHS_STRICT | role_mismatch | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | GLHS_STRICT | stale_thss_replay | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | SNAPSHOT_BOUND_STATE_ONLY | cross_subject_proposal_write | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | SNAPSHOT_BOUND_STATE_ONLY | derived_cache_persistence_after_revocation | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | SNAPSHOT_BOUND_STATE_ONLY | digest_expiry_tamper_replay | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | SNAPSHOT_BOUND_STATE_ONLY | revoked_consent_cache_index_reuse | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | SNAPSHOT_BOUND_STATE_ONLY | stale_thss_replay | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | STATE_VERSION_ONLY | cross_subject_proposal_write | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | STATE_VERSION_ONLY | derived_cache_persistence_after_revocation | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | STATE_VERSION_ONLY | digest_expiry_tamper_replay | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | STATE_VERSION_ONLY | revoked_consent_cache_index_reuse | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | STATE_VERSION_ONLY | stale_thss_replay | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | UNBOUND | cross_subject_proposal_write | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | UNBOUND | derived_cache_persistence_after_revocation | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | UNBOUND | digest_expiry_tamper_replay | 30 | 0 | 0.000 | no |
| rejected_operation_decision_record | UNBOUND | revoked_consent_cache_index_reuse | 30 | 0 | 0.000 | no |
| committed_operation_exact_reconstruction | GLHS_STRICT | audit_reconstruction_failure | 30 | 30 | 1.000 | yes |
| committed_operation_exact_reconstruction | GLHS_STRICT | concurrent_stale_state_write | 30 | 30 | 1.000 | yes |
| committed_operation_exact_reconstruction | SNAPSHOT_BOUND_STATE_ONLY | audit_reconstruction_failure | 30 | 30 | 1.000 | yes |
| committed_operation_exact_reconstruction | SNAPSHOT_BOUND_STATE_ONLY | authorization_consent_toctou | 30 | 30 | 1.000 | yes |
| committed_operation_exact_reconstruction | SNAPSHOT_BOUND_STATE_ONLY | concurrent_stale_state_write | 30 | 30 | 1.000 | yes |
| committed_operation_exact_reconstruction | SNAPSHOT_BOUND_STATE_ONLY | role_mismatch | 30 | 30 | 1.000 | yes |
| committed_operation_exact_reconstruction | STATE_VERSION_ONLY | audit_reconstruction_failure | 30 | 0 | 0.000 | yes |
| committed_operation_exact_reconstruction | STATE_VERSION_ONLY | authorization_consent_toctou | 30 | 0 | 0.000 | yes |
| committed_operation_exact_reconstruction | STATE_VERSION_ONLY | concurrent_stale_state_write | 30 | 0 | 0.000 | yes |
| committed_operation_exact_reconstruction | STATE_VERSION_ONLY | role_mismatch | 30 | 0 | 0.000 | yes |
| committed_operation_exact_reconstruction | UNBOUND | audit_reconstruction_failure | 30 | 0 | 0.000 | yes |
| committed_operation_exact_reconstruction | UNBOUND | authorization_consent_toctou | 30 | 0 | 0.000 | yes |
| committed_operation_exact_reconstruction | UNBOUND | concurrent_stale_state_write | 30 | 0 | 0.000 | yes |
| committed_operation_exact_reconstruction | UNBOUND | role_mismatch | 30 | 0 | 0.000 | yes |
| committed_operation_exact_reconstruction | UNBOUND | stale_thss_replay | 30 | 0 | 0.000 | yes |
| governance_mutation_trace_linkage | GLHS_STRICT | authorization_consent_toctou | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | GLHS_STRICT | concurrent_stale_state_write | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | GLHS_STRICT | cross_subject_proposal_write | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | GLHS_STRICT | derived_cache_persistence_after_revocation | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | GLHS_STRICT | digest_expiry_tamper_replay | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | GLHS_STRICT | revoked_consent_cache_index_reuse | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | GLHS_STRICT | role_mismatch | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | GLHS_STRICT | stale_thss_replay | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | SNAPSHOT_BOUND_STATE_ONLY | authorization_consent_toctou | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | SNAPSHOT_BOUND_STATE_ONLY | concurrent_stale_state_write | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | SNAPSHOT_BOUND_STATE_ONLY | cross_subject_proposal_write | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | SNAPSHOT_BOUND_STATE_ONLY | derived_cache_persistence_after_revocation | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | SNAPSHOT_BOUND_STATE_ONLY | digest_expiry_tamper_replay | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | SNAPSHOT_BOUND_STATE_ONLY | revoked_consent_cache_index_reuse | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | SNAPSHOT_BOUND_STATE_ONLY | role_mismatch | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | SNAPSHOT_BOUND_STATE_ONLY | stale_thss_replay | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | STATE_VERSION_ONLY | authorization_consent_toctou | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | STATE_VERSION_ONLY | concurrent_stale_state_write | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | STATE_VERSION_ONLY | cross_subject_proposal_write | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | STATE_VERSION_ONLY | derived_cache_persistence_after_revocation | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | STATE_VERSION_ONLY | digest_expiry_tamper_replay | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | STATE_VERSION_ONLY | revoked_consent_cache_index_reuse | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | STATE_VERSION_ONLY | role_mismatch | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | STATE_VERSION_ONLY | stale_thss_replay | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | UNBOUND | authorization_consent_toctou | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | UNBOUND | concurrent_stale_state_write | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | UNBOUND | cross_subject_proposal_write | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | UNBOUND | derived_cache_persistence_after_revocation | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | UNBOUND | digest_expiry_tamper_replay | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | UNBOUND | revoked_consent_cache_index_reuse | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | UNBOUND | role_mismatch | 30 | 0 | 0.000 | no |
| governance_mutation_trace_linkage | UNBOUND | stale_thss_replay | 30 | 0 | 0.000 | no |

## Honest interpretation

- The frozen final-003 observer emits only the single ``audit_reconstruction_complete`` boolean and no persisted rejection decision row (AUD-021). Its per-kind completeness is therefore reported as `not_emitted`/0 within the eligible set — this is a record-format statement, not a completeness claim and not a failure count.
- The structured rejection record and transaction trace are defined by the newer observer schema (`glhs-postgres-governance-toctou-final-v2.1`); a future freeze can raise completeness within the same eligible sets.
- Never divide eligible counts of one kind by the total of another; each completeness fraction uses its own denominator.
