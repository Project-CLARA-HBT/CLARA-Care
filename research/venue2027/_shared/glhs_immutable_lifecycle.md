# GLHS Immutable Lifecycle: Proposal Projection & Append-Only Ledger

> Task `SH-repair_immutable` (phase P00, shared, P0 CRITICAL) · R4 defect fix
> Incident evidence: `research/venue2027/_shared/r4_regression_trace.md`

## Persisted lifecycle diagram

```
                         CANONICAL (immutable-by-design)
        ┌─────────────────────────────────────────────────────────────┐
        │  GlhsClinicalCommitmentProposal — INSERT only                │
        │  canonical fields: origin, proposed_transition,              │
        │  source_snapshot_digest, observed_evidence_ids_json,         │
        │  reviewed_proposal_id, proposal_digest, policy_version,      │
        │  consent_version, actor_user_id, actor_role, ...             │
        │  → any UPDATE of these fields raises ValueError("immutable") │
        └─────────────────────────────────────────────────────────────┘
                                   │
                     INSERT (sealed canonical envelope,
                     proposal_digest stamped pre-commit)
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │  state: PENDING          │
                    │  admission_decision=NULL │
                    │  sealed_at=NULL          │
                    └──────────────────────────┘
                     │                       │
     GRWC admission  │                       │  GRWC admission
     ADMIT           │                       │  REJECT
     (projection)    ▼                       ▼    (projection)
        ┌──────────────────────┐   ┌──────────────────────┐
        │ admission_decision=  │   │ admission_decision=  │
        │   "ADMITTED"         │   │   "REJECTED"         │
        │ sealed_at=<now>      │   │ sealed_at=<now>      │
        └──────────────────────┘   └──────────────────────┘
        ✓ permitted via projection  ✓ permitted via projection
          allow-list                  allow-list
                     │                       │
                     └───────────┬───────────┘
                                 ▼
                  ┌────────────────────────────────────────┐
                  │  GlhsClinicalCommitmentTransition       │
                  │  + GlhsAppliedTransition etc. —         │
                  │  NEW LEDGER ROWS (append-only)          │
                  │  never an UPDATE to the proposal row    │
                  └────────────────────────────────────────┘
```

The only two mutable columns on `GlhsClinicalCommitmentProposal` are the
admission projection fields `admission_decision` and `sealed_at`, written by
the GRWC admission path at `services/api/src/clara_api/glhs/admission.py:698-700`.
Both are absent from the canonical proposal envelope
(`clara_api/glhs/commitment_gateway._proposal_envelope`), so stamping them can
never alter `proposal_digest` — verified by
`tests/test_glhs_immutable_projection_contract.py::test_projection_whitelist`.

## Guard architecture

`services/api/src/clara_api/db/models.py` (end of file):

| Model | `before_update` | `before_delete` |
| --- | --- | --- |
| `GlhsAssertion` | `_protect_glhs_assertion_content` (allow-list: `lifecycle_status`, `confirmed_at`, `superseded_at`) | `_reject_glhs_ledger_mutation` |
| `GlhsConflict` | `_protect_glhs_conflict_content` (allow-list: `status`, `resolved_transition_id`, `resolved_at`) | `_reject_glhs_ledger_mutation` |
| `GlhsInferenceContextBinding` | `_protect_glhs_inference_binding_content` (attestation/projection allow-list) | `_reject_glhs_ledger_mutation` |
| `GlhsClinicalCommitmentProposal` | **`_protect_glhs_proposal_content` (allow-list: `admission_decision`, `sealed_at`)** | `_reject_glhs_ledger_mutation` |
| `GlhsStateVersion`, `GlhsEvidence`, `GlhsAssertionEvidence`, `GlhsRelation`, `GlhsTransition`, `GlhsTransitionItem`, `GlhsSnapshotManifest`, `GlhsClinicalCommitment`, `GlhsClinicalCommitmentVersion`, `GlhsClinicalCommitmentTransition`, `GlhsProposalDependency`, `GlhsAppliedTransition`, `GlhsTransitionPartitionLink` | `_reject_glhs_ledger_mutation` (any UPDATE rejected) | `_reject_glhs_ledger_mutation` |

`_protect_glhs_proposal_content` delegates to
`_reject_glhs_canonical_content_mutation`, which inspects the flush-time change
set (`sa_inspect(target).attrs[*].history.has_changes()`) and raises
`ValueError` when any changed attribute falls outside `projection_fields`:
`frozenset({"admission_decision", "sealed_at"})`.

## Whitelist rationale

1. **Canonical content is already immutable-by-design.** Reviewing a proposal
   produces a *new* reviewed proposal row (`reviewed_proposal_id` linkage);
   governance never rewrites an existing row's origin, proposed transition,
   source snapshot digest, evidence ids, digests, policy/consent versions, or
   actor fields. Rejecting those updates enforces the append-only contract.
2. **The admission decision is a lifecycle projection, not a content rewrite.**
   `admission_decision` and `sealed_at` record *when and how* governance
   finalized the row. They are sealed exactly once by the GRWC admission path,
   are excluded from the canonical envelope/digest, and were the sole mutation
   path blocked by the R4 regression (4 failing tests, reason
   "GLHS ledger rows are immutable; append a governed transition").
3. **Consistency with existing guards.** The allow-list mirrors
   `_protect_glhs_assertion_content` / `_protect_glhs_conflict_content` /
   `_protect_glhs_inference_binding_content`: lifecycle-status columns are
   updatable, canonical content never is. Fail-closed: any changed field not in
   the whitelist raises before the flush reaches the database; deletes remain
   unconditionally rejected by `_reject_glhs_ledger_mutation`.
4. **Immutability is preserved for every other GLHS model.** Only
   `GlhsClinicalCommitmentProposal` moved from the blanket loop to a dedicated
   allow-list listener; all 13 other models in the blanket loop keep
   `_reject_glhs_ledger_mutation` on both `before_update` and `before_delete`.

## Verification

- R4 gate suite: 11 test modules, 64 passed, exit 0
  (`research/venue2027/proof/logs/SH-repair_immutable_r4_gate_suite.log`).
- Security regression (`test_glhs_r4_admission.py` +
  `test_glhs_grwc_lineage.py`): 16 passed, exit 0
  (`research/venue2027/proof/logs/SH-repair_immutable_security_regression.log`).
- The adversarial controls `test_reject_canonical_update` and
  `test_atomic_rollback_preserves_canonical_hash` still pass unchanged; only
  the obsolete `xfail(strict=True)` defect marker was removed from
  `test_projection_whitelist`.
