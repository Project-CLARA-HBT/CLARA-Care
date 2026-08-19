# GovRed RIVF — Not Run capability audit (E-004 / GRD-03)

Capability decision for every family/arm that was `NOT_RUN` in final-003 (180 per arm). A `NOT_RUN` row contributes to no denominator and is never a zero-failure result.

## Classification counts

| Category | families |
| --- | --- |
| IMPLEMENTABLE_FAITHFULLY | cross_subject_retrieval, policy_version_change, purpose_mismatch, unrelated_disclosure_request |
| TASK_OR_ARM_SEMANTICS_UNSUPPORTED | — |
| REQUIRES_LLM_ATTACK_STUDY | gst_bypass_prompt, patient_evidence_prompt_injection |

## Per family/arm decision

| family | scope | governance writer | adapter mutation | capability |
| --- | --- | --- | --- | --- |
| cross_subject_retrieval | primary_authorization_drift | subject_cross_replay | subject_cross_replay | IMPLEMENTABLE_FAITHFULLY |
| cross_subject_retrieval | primary_authorization_drift | subject_cross_replay | subject_cross_replay | IMPLEMENTABLE_FAITHFULLY |
| cross_subject_retrieval | primary_authorization_drift | subject_cross_replay | subject_cross_replay | IMPLEMENTABLE_FAITHFULLY |
| cross_subject_retrieval | primary_authorization_drift | subject_cross_replay | subject_cross_replay | IMPLEMENTABLE_FAITHFULLY |
| gst_bypass_prompt | secondary_robustness_stress | prompt_attempt | none | REQUIRES_LLM_ATTACK_STUDY |
| gst_bypass_prompt | secondary_robustness_stress | prompt_attempt | none | REQUIRES_LLM_ATTACK_STUDY |
| gst_bypass_prompt | secondary_robustness_stress | prompt_attempt | none | REQUIRES_LLM_ATTACK_STUDY |
| gst_bypass_prompt | secondary_robustness_stress | prompt_attempt | none | REQUIRES_LLM_ATTACK_STUDY |
| patient_evidence_prompt_injection | secondary_robustness_stress | prompt_attempt | none | REQUIRES_LLM_ATTACK_STUDY |
| patient_evidence_prompt_injection | secondary_robustness_stress | prompt_attempt | none | REQUIRES_LLM_ATTACK_STUDY |
| patient_evidence_prompt_injection | secondary_robustness_stress | prompt_attempt | none | REQUIRES_LLM_ATTACK_STUDY |
| patient_evidence_prompt_injection | secondary_robustness_stress | prompt_attempt | none | REQUIRES_LLM_ATTACK_STUDY |
| policy_version_change | primary_authorization_drift | deployment_policy_version_change | policy_version_change | IMPLEMENTABLE_FAITHFULLY |
| policy_version_change | primary_authorization_drift | deployment_policy_version_change | policy_version_change | IMPLEMENTABLE_FAITHFULLY |
| policy_version_change | primary_authorization_drift | deployment_policy_version_change | policy_version_change | IMPLEMENTABLE_FAITHFULLY |
| policy_version_change | primary_authorization_drift | deployment_policy_version_change | policy_version_change | IMPLEMENTABLE_FAITHFULLY |
| purpose_mismatch | primary_authorization_drift | purpose_switch_replay | purpose_switch_replay | IMPLEMENTABLE_FAITHFULLY |
| purpose_mismatch | primary_authorization_drift | purpose_switch_replay | purpose_switch_replay | IMPLEMENTABLE_FAITHFULLY |
| purpose_mismatch | primary_authorization_drift | purpose_switch_replay | purpose_switch_replay | IMPLEMENTABLE_FAITHFULLY |
| purpose_mismatch | primary_authorization_drift | purpose_switch_replay | purpose_switch_replay | IMPLEMENTABLE_FAITHFULLY |
| unrelated_disclosure_request | secondary_robustness_stress | none | none | IMPLEMENTABLE_FAITHFULLY |
| unrelated_disclosure_request | secondary_robustness_stress | none | none | IMPLEMENTABLE_FAITHFULLY |
| unrelated_disclosure_request | secondary_robustness_stress | none | none | IMPLEMENTABLE_FAITHFULLY |
| unrelated_disclosure_request | secondary_robustness_stress | none | none | IMPLEMENTABLE_FAITHFULLY |

## Technical reasons

### cross_subject_retrieval

Two-phase subject_cross_replay schedule is implemented in the isolated adapter (commit bd0d7d65); faithful disclosure retrieval for a foreign subject is an HTTP scope-enforcement probe with a persisted-writer scenario.

### gst_bypass_prompt

Prompt-injection bypass of GST requires a real model-mediated security protocol (E-006). No frozen LLM-attack protocol exists; a synthetic request label would fake the attack and must not enter the core authorization-drift endpoint.

### patient_evidence_prompt_injection

Prompt-injection into patient evidence requires a real model-mediated security protocol (E-006). Kept outside the core authorization-drift endpoint until one is frozen.

### policy_version_change

Two-phase deployment-level GOVRED_RESEARCH_POLICY_VERSION override plus the persisted advance_governance_policy_epoch writer (commit bd0d7d65); policy epochs are real persisted rows.

### purpose_mismatch

Narrow synthetic purpose_switch_replay grant mutation (two-phase create/commit) is implemented in the isolated adapter (commit bd0d7d65) and maps to the persisted purpose_or_authorization_change governance writer.

### unrelated_disclosure_request

Request-time scope enforcement: an HTTP disclosure request for an out-of-scope subject/purpose is denied at the scope resolver (documented 404 scope_forbidden development probes). Requires a disclosure-probe mutation in the adapter; no governance writer or LLM is involved.

## Notes

- The three mandatory-primary families were completed in the adapter (`The three mandatory-primary NOT_RUN families were completed in the adapter (commit bd0d7d65): cross_subject_retrieval -> subject_cross_replay, purpose_mismatch -> purpose_switch_replay, policy_version_change two-phase. Completion is capability, not result.`).
- Prompt-injection families stay REQUIRES_LLM_ATTACK_STUDY (E-006): no real model-mediated security protocol is frozen, so they are not faked with synthetic request labels.
- `TASK_OR_ARM_SEMANTICS_UNSUPPORTED` is not forced: no family needed it, and no family is forced to execute by weakening semantics.
