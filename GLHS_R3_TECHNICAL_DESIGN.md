# GLHS R3 TECHNICAL DESIGN

**Base branch:** `research/glhs-q2-r2-experiments`  
**Base SHA:** `e7a073749d8d3d434f6d47204238cc6655431f76`

---

## 1. Design principle

The R3 architecture treats the inference boundary as an auditable systems boundary.

Failure to prevent:

```text
A governed disclosure H1 was compiled.
The model actually saw H2, or no verifiable H at all.
A proposal P later claims H1.
Current auth/state checks happen to pass.
P is persisted.
```

R3 therefore requires:

```text
GovernedDisclosure
      |
      v
InferenceContextBinding
      |
      v
ProposalLineage
      |
      v
AdmissionContract
      |
      v
AtomicCommitKernel
      |
      v
AppliedTransition
```

---

## 2. GovernedDisclosure

Reuse existing THSS/snapshot infrastructure.

Responsibilities:
- task-bound minimization;
- state/governance coordinates;
- provenance/evidence manifest;
- canonical projection;
- validity;
- stable digests.

No LLM or client may author authoritative disclosure coordinates.

---

## 3. InferenceContextBinding

### 3.1 Purpose
Prove that the trusted application bound one specific governed disclosure to one specific inference request.

### 3.2 Recommended schema

```text
GlhsInferenceContextBinding
  id
  public_id
  profile_id
  snapshot_manifest_id

  projection_digest
  manifest_digest
  disclosure_slot_digest
  request_envelope_digest

  actor_id
  actor_role
  purpose
  task

  prompt_template_version
  system_prompt_version

  provider
  requested_model_id
  reported_model_id

  request_started_at
  request_completed_at
  response_digest

  canonicalization_profile
  status
  created_at
```

### 3.3 Creation point
Create binding after final request construction and immediately before provider dispatch.

Do not create authoritative consumption evidence merely when THSS is compiled.

### 3.4 Finalization
After provider response:
- record reported model;
- optionally record response digest;
- set `COMPLETED`, `FAILED`, or `ABORTED`.

Failed/aborted bindings cannot be used for strict proposal admission.

---

## 4. Canonical request envelope

Define an internal canonical envelope:

```json
{
  "schema": "clara.inference-envelope.v1",
  "model_route": "...",
  "requested_model_id": "...",
  "prompt_template_version": "...",
  "system_prompt_version": "...",
  "purpose": "...",
  "task": "...",
  "disclosure": {
    "snapshot_id": "...",
    "projection_digest": "...",
    "manifest_digest": "..."
  },
  "model_visible_projection": {}
}
```

Hash using the authoritative canonical JSON profile.

Exclude:
- secrets;
- auth headers;
- unstable transport timestamps;
- provider-generated request IDs.

Record provider adapter version separately.

---

## 5. AdmissionContract

Suggested interface:

```python
@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reason_codes: tuple[str, ...]
    disclosure_id: str | None
    inference_binding_id: str | None
    dependency_digest: str | None
    current_coordinates: dict[str, object]

def evaluate_grwc_admission(
    db: Session,
    proposal: Proposal,
    *,
    now: datetime,
) -> AdmissionDecision:
    ...
```

Required checks:

```text
verify_lineage()
verify_inference_binding()
verify_disclosure_identity()
verify_projection_digest()
verify_manifest_digest()
verify_evidence_membership()
derive_required_dependencies()
verify_dependency_completeness()
verify_current_state()
verify_current_policy()
verify_current_consent()
verify_actor_role_purpose_task()
verify_snapshot_validity()
```

The decision must be evaluated inside the same transaction as the persistent write.

---

## 6. Proposal lineage

### Root model proposal
```text
root_proposal_id = proposal_id
inference_binding_id != null
origin = model
```

### Human-reviewed child
```text
parent_proposal_id = previous proposal
root_proposal_id = original model proposal
inference_binding_id = inherited
origin = human_review
```

Human edits do not erase model lineage.

### New inference
A new inference produces a new binding and a new explicit lineage branch.

---

## 7. Dependency contract

Operation schemas declare minimum dependencies.

Example:

```python
OperationDependencyContract(
    operation_kind="update_medication_dose",
    required_domains=("medications",),
    required_entities_from=("target.medication_id",),
    required_governance=("policy", "consent"),
    required_evidence_from=("evidence_ids",),
)
```

Algorithm:
1. derive minimum vector;
2. normalize caller vector;
3. require `minimum ⊆ declared`;
4. allow conservative superset;
5. hash normalized vector;
6. bind to proposal;
7. lock/revalidate at admission.

LLM output is never authoritative for dependency completeness.

---

## 8. Atomic DB transaction

Within one PostgreSQL transaction:

```text
T0 idempotency
T1 proposal lineage
T2 inference binding + disclosure
T3 canonical lock acquisition
T4 GRWC verification
T5 dependency derivation/completeness
T6 current state/governance re-read
T7 domain mutation
T8 CAS version advance
T9 persist AppliedTransition + lineage
T10 outbox/audit
COMMIT
```

Any validation failure rolls back.

---

## 9. Locking

Preserve canonical lock order.

If inference/disclosure records are immutable:
- enforce append-only / immutable semantics.

If mutable:
- include them in lock ordering.

No split “validate now, write later” path.

---

## 10. Stable rejection codes

```text
binding_missing
binding_not_completed
binding_profile_mismatch
binding_actor_mismatch
binding_purpose_mismatch
binding_task_mismatch
snapshot_missing
snapshot_identity_mismatch
projection_digest_mismatch
manifest_digest_mismatch
request_envelope_mismatch
evidence_undisclosed
dependency_missing
dependency_version_stale
policy_stale
consent_stale
consent_revoked
role_changed
snapshot_expired
lineage_downgrade
idempotent_replay
```

Use reason codes in experiment outputs rather than exception-string parsing.

---

## 11. Security boundaries

Trusted:
- API server;
- prompt builder;
- GLHS canonicalizer;
- database host under current threat model;
- commitment gateway/kernel.

Untrusted/partially trusted:
- browser/mobile;
- LLM output;
- provider response;
- client proposal fields.

Explicitly out-of-scope unless separately modeled:
- compromised DB admin;
- compromised application server;
- canonicalizer compromise;
- cryptographic primitive break.

---

## 12. Testing architecture

### Unit
- envelope determinism;
- binding verification;
- lineage inheritance;
- dependency derivation;
- canonicalization.

### Integration
- provider mock boundary;
- PostgreSQL admission;
- policy/consent drift;
- review lineage;
- retry/fallback binding behavior.

### Mutation
Remove each GRWC clause one at a time.

### Property-based
Generate substitutions, lineage trees, dependency omissions, governance drifts.

### End-to-end
HTTP → inference → proposal → review → commit.

---

## 13. Migration

1. inspect current schema;
2. add only missing fields;
3. mark historical unattested bindings as legacy;
4. never fabricate request-envelope digests;
5. strict R3 experiments use only strict R3 records;
6. retain backward-compatible read paths;
7. rollback migration tested.

---

## 14. Observability

Suggested metrics:
- `glhs_binding_created_total`
- `glhs_binding_failed_total`
- `glhs_admission_rejected_total{reason}`
- `glhs_dependency_missing_total`
- `glhs_downgrade_attempt_total`
- `glhs_commit_latency_seconds`
- `glhs_lock_wait_seconds`

Do not log raw clinical prompts by default.

---

## 15. Rollout

1. shadow verification;
2. compare legacy vs R3 decisions;
3. strict staging;
4. research execution;
5. production enablement only after compatibility review.

Research ablations use isolated experiment adapters. Never expose safety-clause disable flags to production.

---

## 16. Technical Definition of Done

- server-owned binding created at actual inference boundary;
- exact disclosure projection bound;
- proposal lineage immutable;
- same-transaction current governance/state validation;
- operation-derived dependency completeness;
- no downgrade route;
- deterministic reason codes;
- real PostgreSQL strict-route tests;
- research ablations isolated from production.
