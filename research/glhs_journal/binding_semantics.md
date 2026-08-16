# Mandatory THSS binding semantics

The gateway now exposes an explicit input coordinate:

```text
proposal_consumed_thss == true -> source_snapshot_id != null
                                      and source_snapshot_digest is required
```

`propose_assertion` rejects a THSS-consuming proposal missing its snapshot with
`proposal_snapshot_binding_required`. Snapshot-bound activation subsequently
revalidates profile, actor, role, purpose, task, state version, policy,
consent, expiry, payload digest, manifest digest, and disclosed evidence.

At activation, those scope coordinates come from the **current commit scope**,
not merely from the actor that created the candidate assertion. Consequently a
different actor or purpose cannot use a previously bound assertion as a
commit-time fallback; it must obtain a new admissible disclosure/snapshot.

The explicit `base_version_only` commitment path remains available only for a
proposal that did not declare THSS consumption. It is not a fallback for a
THSS-consuming model proposal.

Evidence: `services/api/tests/test_glhs_mandatory_thss_binding.py` verifies the
direct gateway rejection. `services/api/tests/test_commitment_endpoints_integration.py`
also verifies that the public commitment proposal API rejects a request that
omits either required snapshot-binding coordinate and rejects a snapshot issued
for a different profile. The generic assertion API does not expose a
model-derived THSS proposal route; introducing one requires the same explicit
declaration and binding checks. `services/api/tests/test_glhs_gateway.py`
verifies current-actor and current-purpose revalidation at generic assertion
activation. PostgreSQL governance-TOCTOU coverage remains an open revision
blocker.

`model_thss_write_path_audit.md` records the current surface inventory. The
generic assertion gateway rejects `process_kind="model"` outright, so no
model-originated generic base-version-only write path currently exists. This
is implementation-conformance evidence, not a statement about future routes
or PostgreSQL governance-writer race atomicity.
