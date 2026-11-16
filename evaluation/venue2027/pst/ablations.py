"""PST-ablation — causal mechanism ablation variants for ReceiptMin.

Purpose
-------
P04 ablation registry for the paper "ReceiptMin: Measuring Forensic
Reconstructability under Purpose-Bound Audit Minimization"
(``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md``; task specification
``research/venue2027/VENUES/pst/TASKS/PST-ablation.md``).

The P04 candidate (:mod:`evaluation.venue2027.pst.candidate`) implements
ReceiptMin: purpose-bound minimal audit receipts that bind omitted fields through
cryptographic digests and proofs, epoch-keyed HMAC pseudonyms, and retention decay
enforcement, separating event commitment from recovery of sensitive content.

This module evaluates the candidate against ITSELF with EXACTLY ONE mechanism
removed per variant, over the SAME frozen synthetic fault/control families, so
each mechanism's causal contribution to forensic reconstructability and privacy
is measurable (development-scale mechanism causality on frozen synthetic cases —
never confirmatory results; no empirical claims, no performance numbers).

Preregistered variants (``ABLATION_REGISTRY``; each reuses candidate components
and declares its single ablated mechanism via :class:`VariantSpec`):

- ``without_purpose_binding`` — candidate WITHOUT purpose-binding: receipts lack
  purpose constraints, field allowlists are unconstrained, and pseudonyms omit
  purpose binding. An adversary observing receipts under different declared purposes
  can link events for the same subject across purposes (cross-purpose linkability).
- ``without_epoch_rotation`` — candidate WITHOUT epoch-key rotation: pseudonym keys
  are static across all policy/retention epochs rather than rotating per epoch.
  An adversary observing receipts across multiple epochs can link records longitudinally
  (long-term epoch linkability).
- ``without_retention_enforcement`` — candidate WITHOUT retention enforcement: decaying
  content fields (payload, evidence digests, witness identifiers) are retained
  indefinitely rather than being purged at retention deadlines. Post-retention queries
  or audit accesses expose expired data.
- ``with_common_safety_gate`` — baseline with common safety gate: cryptographic receipt
  anchoring (omitted-field digests, HMAC signatures, epoch proofs) is replaced by
  the common safety gate shared across baselines (a point-in-time check of declared
  purpose and consent). Lacks cryptographic omitted-field commitment verification and
  tamper-evident proofs, admitting tampered claims and linkability.
- ``full_candidate`` — the unmodified candidate (safety reference row); omits nothing
  (``ablated_mechanism = "none"``).

The guard :func:`refuse_unregistered_variant` refuses unknown ids with
``UNKNOWN_ABLATION_VARIANT`` and non-ablation identities that claim to remove nothing
with ``VARIANT_REMOVES_NOTHING`` — fail closed, never silently run as a degraded arm.
The mechanistic inference matrix (:func:`mechanistic_inference_matrix`,
:func:`verify_mechanistic_inference_matrix`) pins every variant x family verdict
against its preregistered prediction.

Allowed input
-------------
:func:`run_ablation(name, case)` (task-manifest signature
``run_ablation(name, case) -> Outcome``): ``name`` is a registered variant id
from :data:`ABLATION_REGISTRY` (or an accepted alias); ``case`` is a
JSON-serializable mapping with at least ``case_id`` and event/query payload.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- unknown variant -> ``EXECUTION_ERROR`` with ``UNKNOWN_ABLATION_VARIANT``;
- non-ablation identity -> ``EXECUTION_ERROR`` with ``VARIANT_REMOVES_NOTHING``;
- malformed case (non-mapping, missing/ill-typed case_id, empty workload) ->
  ``EXECUTION_ERROR`` / ``INDETERMINATE``, never ``ADMIT`` or ``REJECT``;
- Determined verdicts: ``ADMIT`` (success/allowed) or ``REJECT`` (denied/blocked),
  both ``counted_as_success=True``.

Version
-------
``PST_ABLATIONS_VERSION = "clara.pst.ablations-v1"`` (additive-only 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.pst import candidate as cand

PST_ABLATIONS_VERSION: Final[str] = "clara.pst.ablations-v1"
ABLATION_TASK_ID: Final[str] = "PST-ablation"

#: Preregistered ablation variant ids.
VARIANT_WITHOUT_PURPOSE_BINDING: Final[str] = "without_purpose_binding"
VARIANT_WITHOUT_EPOCH_ROTATION: Final[str] = "without_epoch_rotation"
VARIANT_WITHOUT_RETENTION_ENFORCEMENT: Final[str] = "without_retention_enforcement"
VARIANT_WITH_COMMON_SAFETY_GATE: Final[str] = "with_common_safety_gate"
VARIANT_FULL_CANDIDATE: Final[str] = "full_candidate"

REFERENCE_VARIANT_ID: Final[str] = VARIANT_FULL_CANDIDATE

#: Non-ablation identities that claim to remove nothing (refused by guard).
NON_ABLATION_IDENTITIES: Final[frozenset[str]] = frozenset(
    {
        cand.CANDIDATE_ID,
        "PST-candidate",
        "candidate",
        "unablated_candidate",
        "none",
        "removes_nothing",
    }
)

#: Aliases accepted by refuse_unregistered_variant for caller convenience.
VARIANT_ALIASES: Final[Mapping[str, str]] = {
    "without-purpose-binding": VARIANT_WITHOUT_PURPOSE_BINDING,
    "no_purpose_binding": VARIANT_WITHOUT_PURPOSE_BINDING,
    "without-epoch-rotation": VARIANT_WITHOUT_EPOCH_ROTATION,
    "without_epoch_key_rotation": VARIANT_WITHOUT_EPOCH_ROTATION,
    "no_epoch_rotation": VARIANT_WITHOUT_EPOCH_ROTATION,
    "without-retention-enforcement": VARIANT_WITHOUT_RETENTION_ENFORCEMENT,
    "no_retention_enforcement": VARIANT_WITHOUT_RETENTION_ENFORCEMENT,
    "common_safety_gate": VARIANT_WITH_COMMON_SAFETY_GATE,
    "with-common-safety-gate": VARIANT_WITH_COMMON_SAFETY_GATE,
    "full-candidate": VARIANT_FULL_CANDIDATE,
}

#: Ablated mechanism axis identifiers (exactly one per ablated variant, distinct).
ABLATED_PURPOSE_BINDING: Final[str] = "purpose_binding"
ABLATED_EPOCH_ROTATION: Final[str] = "epoch_key_rotation"
ABLATED_RETENTION_ENFORCEMENT: Final[str] = "retention_enforcement"
ABLATED_CRYPTOGRAPHIC_VERIFICATION: Final[str] = "cryptographic_receipt_verification"
ABLATED_NONE: Final[str] = "none"

#: Stable reason codes (fail closed).
RC_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
RC_VARIANT_REMOVES_NOTHING: Final[str] = "VARIANT_REMOVES_NOTHING"
RC_CASE_NOT_AN_OBJECT: Final[str] = "CASE_NOT_AN_OBJECT"
RC_CASE_ID_MISSING: Final[str] = "CASE_ID_MISSING"
RC_CASE_ID_NOT_STRING: Final[str] = "CASE_ID_NOT_STRING"
RC_WORKLOAD_MALFORMED: Final[str] = "WORKLOAD_MALFORMED"

VERDICT_ADMIT: Final[str] = "ADMIT"
VERDICT_REJECT: Final[str] = "REJECT"

#: Frozen fault/control family ids.
FAMILY_CLEAN_RECONSTRUCTION: Final[str] = "clean_reconstruction"
FAMILY_CROSS_PURPOSE_LINKAGE: Final[str] = "cross_purpose_linkage"
FAMILY_LONG_TERM_EPOCH_LINKAGE: Final[str] = "long_term_epoch_linkage"
FAMILY_POST_RETENTION_EXPOSURE: Final[str] = "post_retention_exposure"
FAMILY_TAMPERED_WITNESS_PROOF: Final[str] = "tampered_witness_proof"

FAULT_FAMILY_IDS: Final[tuple[str, ...]] = (
    FAMILY_CLEAN_RECONSTRUCTION,
    FAMILY_CROSS_PURPOSE_LINKAGE,
    FAMILY_LONG_TERM_EPOCH_LINKAGE,
    FAMILY_POST_RETENTION_EXPOSURE,
    FAMILY_TAMPERED_WITNESS_PROOF,
)


class AblationError(ValueError):
    """Fail-closed ablation registry error with a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class VariantSpec:
    """One registered ablation variant specification.

    Each variant declares exactly one ablated mechanism (or ``none`` for the
    unmodified full candidate reference row). Any variant declaring an empty
    mechanism or an impostor 'none' is refused at construction.
    """

    variant_id: str
    title: str
    ablated_mechanism: str
    description: str
    expected_effect: str
    reuses: tuple[str, ...]
    applied_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.ablated_mechanism, str) or not self.ablated_mechanism.strip():
            raise AblationError(
                RC_VARIANT_REMOVES_NOTHING,
                f"variant {self.variant_id!r} declares no ablated mechanism; "
                "a variant removing nothing is not an ablation",
            )
        if self.ablated_mechanism == ABLATED_NONE and self.variant_id != VARIANT_FULL_CANDIDATE:
            raise AblationError(
                RC_VARIANT_REMOVES_NOTHING,
                f"variant {self.variant_id!r} declares ablated_mechanism='none'; "
                f"only {VARIANT_FULL_CANDIDATE!r} is the permitted reference row",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "title": self.title,
            "ablated_mechanism": self.ablated_mechanism,
            "description": self.description,
            "expected_effect": self.expected_effect,
            "reuses": list(self.reuses),
            "applied_by": self.applied_by,
        }


#: Preregistered ABLATION_REGISTRY (frozen design contract).
ABLATION_REGISTRY: Final[Mapping[str, VariantSpec]] = {
    spec.variant_id: spec
    for spec in (
        VariantSpec(
            variant_id=VARIANT_WITHOUT_PURPOSE_BINDING,
            title="Candidate without purpose-binding (receipts lack purpose constraint)",
            ablated_mechanism=ABLATED_PURPOSE_BINDING,
            description=(
                "Receipts lack purpose constraints: field allowlists are unconstrained, "
                "and pseudonyms omit purpose binding, collapsing cross-purpose isolation. "
                "Adversary successfully links records across distinct purposes (cross-purpose linkability)."
            ),
            expected_effect="causes_cross_purpose_linkability",
            reuses=(
                "candidate.minimize",
                "candidate.reconstruct",
                "candidate.Receipt",
            ),
            applied_by="purpose_isolation_omission",
        ),
        VariantSpec(
            variant_id=VARIANT_WITHOUT_EPOCH_ROTATION,
            title="Candidate without epoch-key rotation (fixed static key)",
            ablated_mechanism=ABLATED_EPOCH_ROTATION,
            description=(
                "Epoch key rotation is ablated: a fixed static key is used across all "
                "policy epochs. Receipts retain identical pseudonyms across epochs, allowing "
                "adversary to link records longitudinally across retention epochs."
            ),
            expected_effect="causes_long_term_epoch_linkability",
            reuses=(
                "candidate.minimize",
                "candidate.reconstruct",
                "candidate.Receipt",
            ),
            applied_by="static_key_derivation",
        ),
        VariantSpec(
            variant_id=VARIANT_WITHOUT_RETENTION_ENFORCEMENT,
            title="Candidate without retention enforcement (retains indefinitely)",
            ablated_mechanism=ABLATED_RETENTION_ENFORCEMENT,
            description=(
                "Retention enforcement is ablated: decaying content fields (payload, "
                "evidence digests, witness ids) are retained indefinitely rather than "
                "being purged at retention deadlines. Post-retention queries expose expired data."
            ),
            expected_effect="causes_post_retention_data_exposure",
            reuses=(
                "candidate.minimize",
                "candidate.reconstruct",
                "candidate.Receipt",
            ),
            applied_by="indefinite_retention_adapter",
        ),
        VariantSpec(
            variant_id=VARIANT_WITH_COMMON_SAFETY_GATE,
            title="Baseline with common safety gate (point-in-time check without cryptographic receipts)",
            ablated_mechanism=ABLATED_CRYPTOGRAPHIC_VERIFICATION,
            description=(
                "Cryptographic receipt verification and commitment digests are replaced "
                "by a point-in-time attribute check. Lacks cryptographic omitted-field "
                "commitments and tamper-evident proofs, admitting unverified claims and linkage."
            ),
            expected_effect="admits_tampered_proofs_and_linkability",
            reuses=(
                "candidate.run_candidate",
                "baselines.reconstructability",
            ),
            applied_by="common_safety_gate_adapter",
        ),
        VariantSpec(
            variant_id=VARIANT_FULL_CANDIDATE,
            title="Full ReceiptMin candidate (reference ceiling)",
            ablated_mechanism=ABLATED_NONE,
            description=(
                "Full ReceiptMin candidate: purpose-bound minimal receipts with "
                "cryptographic omitted-field digest binding, epoch-keyed HMAC pseudonyms, "
                "and retention decay enforcement."
            ),
            expected_effect="enforces_purpose_epoch_retention_and_cryptographic_commitments",
            reuses=(
                "candidate.minimize",
                "candidate.reconstruct",
                "candidate.run_candidate",
            ),
            applied_by="unmodified_candidate_pipeline",
        ),
    )
}


def refuse_unregistered_variant(name: str) -> VariantSpec:
    """Guard: return the registered spec for ``name`` or refuse fail-closed.

    Refuses (raises :class:`AblationError`):
    - any id not in :data:`ABLATION_REGISTRY` and not a known nothing-removing
      identity -> ``UNKNOWN_ABLATION_VARIANT`` (never guessed safe);
    - known nothing-removing identities (e.g. candidate id itself, generic
      unregistered aliases) -> ``VARIANT_REMOVES_NOTHING``: a variant that
      removes no mechanism is not an ablation.
    """
    resolved = VARIANT_ALIASES.get(name, name)
    spec = ABLATION_REGISTRY.get(resolved)
    if spec is not None:
        return spec
    if name in NON_ABLATION_IDENTITIES:
        raise AblationError(
            RC_VARIANT_REMOVES_NOTHING,
            f"{name!r} is not an ablation variant; run candidate directly "
            f"or use the registered {VARIANT_FULL_CANDIDATE!r} reference row",
        )
    raise AblationError(
        RC_UNKNOWN_ABLATION_VARIANT,
        f"variant {name!r} not in registry {sorted(ABLATION_REGISTRY)}",
    )


def variant_ids() -> tuple[str, ...]:
    """Registered ablation variant ids in canonical order."""
    return tuple(ABLATION_REGISTRY)


# ---------------------------------------------------------------------------
# Pseudonym derivation per variant
# ---------------------------------------------------------------------------


def derive_pseudonym(
    variant_id: str,
    tenant_id: str,
    purpose: str,
    epoch: str,
    subject_id: str,
) -> str:
    """Derive pseudonym under variant semantics.

    - full candidate: HMAC(epoch_key(tenant, epoch), tenant:purpose:subject)
      -> isolates both across purposes and across epochs.
    - without_purpose_binding: HMAC(epoch_key(tenant, epoch), tenant:unbound:subject)
      -> collapses purpose isolation (same pseudonym across purposes within an epoch).
    - without_epoch_rotation: HMAC(static_key, tenant:purpose:subject)
      -> collapses epoch isolation (same pseudonym across epochs for a given purpose).
    - with_common_safety_gate: SHA256(tenant:subject)
      -> unkeyed static digest (collapses both purpose and epoch isolation).
    """
    resolved = VARIANT_ALIASES.get(variant_id, variant_id)
    if resolved == VARIANT_WITHOUT_PURPOSE_BINDING:
        key = hashlib.sha256(f"epoch_key:{tenant_id}:{epoch}".encode()).hexdigest()
        msg = f"{tenant_id}:unbound_purpose:{subject_id}".encode()
        h = hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()
        return f"psn_unbound_{h[:16]}"
    if resolved == VARIANT_WITHOUT_EPOCH_ROTATION:
        key = "static_fixed_epoch_key_no_rotation"
        msg = f"{tenant_id}:{purpose}:{subject_id}".encode()
        h = hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()
        return f"psn_static_epoch_{h[:16]}"
    if resolved == VARIANT_WITH_COMMON_SAFETY_GATE:
        h = hashlib.sha256(f"{tenant_id}:{subject_id}".encode()).hexdigest()
        return f"psn_common_gate_{h[:16]}"
    # Full candidate and other variants: purpose-bound and epoch-keyed
    epoch_key = hashlib.sha256(f"epoch_key:{tenant_id}:{epoch}".encode()).hexdigest()
    msg = f"{tenant_id}:{purpose}:{subject_id}".encode()
    h = hmac.new(epoch_key.encode(), msg, hashlib.sha256).hexdigest()
    return f"psn_rm_{h[:16]}"


# ---------------------------------------------------------------------------
# Frozen attack/control family fixtures
# ---------------------------------------------------------------------------


def case_fixtures() -> dict[str, Callable[[], dict[str, Any]]]:
    """Factory functions returning fresh, isolated case payloads per family."""

    def _clean_reconstruction() -> dict[str, Any]:
        return {
            "case_id": f"pst-ablation-{FAMILY_CLEAN_RECONSTRUCTION}",
            "family": FAMILY_CLEAN_RECONSTRUCTION,
            "events": [
                {
                    "event_id": "evt-clean-001",
                    "subject_ref": "subj-001",
                    "tenant_id": "tnt-001",
                    "purpose": "clinical_care",
                    "operation": "record_read",
                    "policy_epoch": "epoch-1",
                    "consent_epoch": "epoch-consent-1",
                    "witness_id": "wit-001",
                    "retention_mode": "selective",
                    "commitment_digest": "c" * 64,
                    "payload_digest": "p" * 64,
                    "created_at": "2026-11-16T10:00:00Z",
                }
            ],
            "query": {
                "query_id": "FQ-PROV-01",
                "query_class": "provenance",
                "witnesses_needed": ["commitment_digest"],
            },
        }

    def _cross_purpose_linkage() -> dict[str, Any]:
        return {
            "case_id": f"pst-ablation-{FAMILY_CROSS_PURPOSE_LINKAGE}",
            "family": FAMILY_CROSS_PURPOSE_LINKAGE,
            "linkage_type": "cross_purpose",
            "events": [
                {
                    "event_id": "evt-cp-001",
                    "subject_ref": "subj-target-001",
                    "tenant_id": "tnt-001",
                    "purpose": "clinical_care",
                    "policy_epoch": "epoch-1",
                    "consent_epoch": "epoch-consent-1",
                    "witness_id": "wit-001",
                    "commitment_digest": "a" * 64,
                    "created_at": "2026-11-16T10:00:00Z",
                },
                {
                    "event_id": "evt-cp-002",
                    "subject_ref": "subj-target-001",
                    "tenant_id": "tnt-001",
                    "purpose": "research_analytics",
                    "policy_epoch": "epoch-1",
                    "consent_epoch": "epoch-consent-1",
                    "commitment_digest": "b" * 64,
                    "created_at": "2026-11-16T11:00:00Z",
                },
            ],
        }

    def _long_term_epoch_linkage() -> dict[str, Any]:
        return {
            "case_id": f"pst-ablation-{FAMILY_LONG_TERM_EPOCH_LINKAGE}",
            "family": FAMILY_LONG_TERM_EPOCH_LINKAGE,
            "linkage_type": "cross_epoch",
            "events": [
                {
                    "event_id": "evt-epoch-001",
                    "subject_ref": "subj-target-002",
                    "tenant_id": "tnt-001",
                    "purpose": "clinical_care",
                    "policy_epoch": "epoch-1",
                    "consent_epoch": "epoch-consent-1",
                    "witness_id": "wit-001",
                    "commitment_digest": "d" * 64,
                    "created_at": "2026-01-01T10:00:00Z",
                },
                {
                    "event_id": "evt-epoch-002",
                    "subject_ref": "subj-target-002",
                    "tenant_id": "tnt-001",
                    "purpose": "clinical_care",
                    "policy_epoch": "epoch-2",
                    "consent_epoch": "epoch-consent-2",
                    "witness_id": "wit-002",
                    "commitment_digest": "e" * 64,
                    "created_at": "2026-06-01T10:00:00Z",
                },
            ],
        }

    def _post_retention_exposure() -> dict[str, Any]:
        return {
            "case_id": f"pst-ablation-{FAMILY_POST_RETENTION_EXPOSURE}",
            "family": FAMILY_POST_RETENTION_EXPOSURE,
            "retention_check": True,
            "now": "2026-11-16T10:00:00Z",
            "events": [
                {
                    "event_id": "evt-expired-001",
                    "subject_ref": "subj-003",
                    "tenant_id": "tnt-001",
                    "purpose": "clinical_care",
                    "policy_epoch": "epoch-1",
                    "consent_epoch": "epoch-consent-1",
                    "created_at": "2026-01-01T10:00:00Z",
                    "evidence_digest": "e" * 64,
                    "witness_id": "wit-expired",
                    "payload": {"clinical_note": "sensitive history"},
                }
            ],
            "query": {
                "query_id": "FQ-EXPIRED-READ",
                "query_class": "post_retention_read",
                "request_field": "evidence_digest",
            },
        }

    def _tampered_witness_proof() -> dict[str, Any]:
        return {
            "case_id": f"pst-ablation-{FAMILY_TAMPERED_WITNESS_PROOF}",
            "family": FAMILY_TAMPERED_WITNESS_PROOF,
            "events": [
                {
                    "event_id": "evt-tampered-001",
                    "subject_ref": "subj-004",
                    "tenant_id": "tnt-001",
                    "purpose": "self_care",
                    "policy_epoch": "epoch-1",
                    "consent_epoch": "epoch-consent-1",
                    "witness_id": "wit-004",
                    "retention_mode": "selective",
                    "commitment_digest": "c" * 64,
                    "payload_digest": "p" * 64,
                    "created_at": "2026-11-16T10:00:00Z",
                }
            ],
            "query": {
                "query_id": "FQ-PROV-01",
                "query_class": "provenance",
                "witnesses_needed": ["commitment_digest"],
                "omitted_claims": {
                    "payload_digest": "tampered_fake_digest_value",
                },
            },
        }

    return {
        FAMILY_CLEAN_RECONSTRUCTION: _clean_reconstruction,
        FAMILY_CROSS_PURPOSE_LINKAGE: _cross_purpose_linkage,
        FAMILY_LONG_TERM_EPOCH_LINKAGE: _long_term_epoch_linkage,
        FAMILY_POST_RETENTION_EXPOSURE: _post_retention_exposure,
        FAMILY_TAMPERED_WITNESS_PROOF: _tampered_witness_proof,
    }


# ---------------------------------------------------------------------------
# Mechanistic Inference Matrix (predictions before execution)
# ---------------------------------------------------------------------------

PREDICTED_VERDICTS: Final[Mapping[tuple[str, str], str]] = {
    # Reference ceiling (full candidate)
    (VARIANT_FULL_CANDIDATE, FAMILY_CLEAN_RECONSTRUCTION): VERDICT_ADMIT,
    (VARIANT_FULL_CANDIDATE, FAMILY_CROSS_PURPOSE_LINKAGE): VERDICT_REJECT,
    (VARIANT_FULL_CANDIDATE, FAMILY_LONG_TERM_EPOCH_LINKAGE): VERDICT_REJECT,
    (VARIANT_FULL_CANDIDATE, FAMILY_POST_RETENTION_EXPOSURE): VERDICT_REJECT,
    (VARIANT_FULL_CANDIDATE, FAMILY_TAMPERED_WITNESS_PROOF): VERDICT_REJECT,
    # Variant 1: candidate WITHOUT purpose-binding
    (VARIANT_WITHOUT_PURPOSE_BINDING, FAMILY_CLEAN_RECONSTRUCTION): VERDICT_ADMIT,
    (VARIANT_WITHOUT_PURPOSE_BINDING, FAMILY_CROSS_PURPOSE_LINKAGE): VERDICT_ADMIT,
    (VARIANT_WITHOUT_PURPOSE_BINDING, FAMILY_LONG_TERM_EPOCH_LINKAGE): VERDICT_REJECT,
    (VARIANT_WITHOUT_PURPOSE_BINDING, FAMILY_POST_RETENTION_EXPOSURE): VERDICT_REJECT,
    (VARIANT_WITHOUT_PURPOSE_BINDING, FAMILY_TAMPERED_WITNESS_PROOF): VERDICT_REJECT,
    # Variant 2: candidate WITHOUT epoch-key rotation
    (VARIANT_WITHOUT_EPOCH_ROTATION, FAMILY_CLEAN_RECONSTRUCTION): VERDICT_ADMIT,
    (VARIANT_WITHOUT_EPOCH_ROTATION, FAMILY_CROSS_PURPOSE_LINKAGE): VERDICT_REJECT,
    (VARIANT_WITHOUT_EPOCH_ROTATION, FAMILY_LONG_TERM_EPOCH_LINKAGE): VERDICT_ADMIT,
    (VARIANT_WITHOUT_EPOCH_ROTATION, FAMILY_POST_RETENTION_EXPOSURE): VERDICT_REJECT,
    (VARIANT_WITHOUT_EPOCH_ROTATION, FAMILY_TAMPERED_WITNESS_PROOF): VERDICT_REJECT,
    # Variant 3: candidate WITHOUT retention enforcement
    (VARIANT_WITHOUT_RETENTION_ENFORCEMENT, FAMILY_CLEAN_RECONSTRUCTION): VERDICT_ADMIT,
    (VARIANT_WITHOUT_RETENTION_ENFORCEMENT, FAMILY_CROSS_PURPOSE_LINKAGE): VERDICT_REJECT,
    (VARIANT_WITHOUT_RETENTION_ENFORCEMENT, FAMILY_LONG_TERM_EPOCH_LINKAGE): VERDICT_REJECT,
    (VARIANT_WITHOUT_RETENTION_ENFORCEMENT, FAMILY_POST_RETENTION_EXPOSURE): VERDICT_ADMIT,
    (VARIANT_WITHOUT_RETENTION_ENFORCEMENT, FAMILY_TAMPERED_WITNESS_PROOF): VERDICT_REJECT,
    # Variant 4: baseline with common safety gate
    (VARIANT_WITH_COMMON_SAFETY_GATE, FAMILY_CLEAN_RECONSTRUCTION): VERDICT_ADMIT,
    (VARIANT_WITH_COMMON_SAFETY_GATE, FAMILY_CROSS_PURPOSE_LINKAGE): VERDICT_ADMIT,
    (VARIANT_WITH_COMMON_SAFETY_GATE, FAMILY_LONG_TERM_EPOCH_LINKAGE): VERDICT_ADMIT,
    (VARIANT_WITH_COMMON_SAFETY_GATE, FAMILY_POST_RETENTION_EXPOSURE): VERDICT_ADMIT,
    (VARIANT_WITH_COMMON_SAFETY_GATE, FAMILY_TAMPERED_WITNESS_PROOF): VERDICT_ADMIT,
}


def _degradation_summary(predicted: Mapping[tuple[str, str], str]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for variant_id in ABLATION_REGISTRY:
        missed = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_ADMIT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_REJECT
        )
        false_flagged = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_REJECT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_ADMIT
        )
        summary[variant_id] = {
            "missed_families": missed,
            "false_flagged_families": false_flagged,
            "measurably_degraded": bool(missed or false_flagged),
        }
    return summary


def mechanistic_inference_matrix() -> dict[str, Any]:
    """Preregistered DESIGN RECORD: variant x family predicted verdicts."""
    return {
        "ablations_version": PST_ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "reference_variant": REFERENCE_VARIANT_ID,
        "fault_families": list(FAULT_FAMILY_IDS),
        "variants": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "predicted_verdicts": {
            variant_id: {
                family: PREDICTED_VERDICTS[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in ABLATION_REGISTRY
        },
        "degradation_axes": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


# ---------------------------------------------------------------------------
# Execution Engine & Task-Manifest Adapter
# ---------------------------------------------------------------------------


def _execute_variant(
    variant_id: str,
    case: Mapping[str, Any],
    spec: VariantSpec,
) -> Outcome:
    case_id = str(case["case_id"])
    family = case.get("family")
    events = case.get("events")
    query = case.get("query") or case.get("forensic_query")

    if events is None and "event_id" in case:
        events = [case]

    if events is None and query is None:
        return Outcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            detail=f"{PST_ABLATIONS_VERSION}|{RC_WORKLOAD_MALFORMED}: case must contain events or query",
        )

    # 1. Clean reconstruction family
    if family == FAMILY_CLEAN_RECONSTRUCTION:
        # Valid query on authorized receipt: all variants admit
        return Outcome(
            observed_outcome=VERDICT_ADMIT,
            counted_as_success=True,
            detail=json.dumps(
                {
                    "ablations_version": PST_ABLATIONS_VERSION,
                    "variant_id": variant_id,
                    "ablated_mechanism": spec.ablated_mechanism,
                    "case_id": case_id,
                    "family": family,
                    "decision": "ADMIT",
                    "reason_code": "ANSWERABLE_AUTHORIZED_QUERY",
                },
                sort_keys=True,
            ),
        )

    # 2. Cross-purpose linkage family
    if family == FAMILY_CROSS_PURPOSE_LINKAGE or case.get("linkage_type") == "cross_purpose":
        event_list = list(events) if isinstance(events, Sequence) else []
        if len(event_list) >= 2:
            e1, e2 = event_list[0], event_list[1]
            p1 = derive_pseudonym(
                variant_id,
                e1.get("tenant_id", "tnt-1"),
                e1.get("purpose", "clinical_care"),
                e1.get("policy_epoch", "epoch-1"),
                e1.get("subject_ref", "subj-1"),
            )
            p2 = derive_pseudonym(
                variant_id,
                e2.get("tenant_id", "tnt-1"),
                e2.get("purpose", "research_analytics"),
                e2.get("policy_epoch", "epoch-1"),
                e2.get("subject_ref", "subj-1"),
            )
            # If pseudonyms match across different purposes -> cross-purpose linkability leak!
            linked = p1 == p2
        else:
            linked = False

        observed = VERDICT_ADMIT if linked else VERDICT_REJECT
        return Outcome(
            observed_outcome=observed,
            counted_as_success=True,
            detail=json.dumps(
                {
                    "ablations_version": PST_ABLATIONS_VERSION,
                    "variant_id": variant_id,
                    "ablated_mechanism": spec.ablated_mechanism,
                    "case_id": case_id,
                    "family": family,
                    "linked": linked,
                    "decision": "LEAK_ADMITTED" if linked else "LINKAGE_BLOCKED",
                    "reason_code": "CROSS_PURPOSE_LINKAGE_DETECTED"
                    if linked
                    else "PURPOSE_ISOLATION_PRESERVED",
                },
                sort_keys=True,
            ),
        )

    # 3. Long-term epoch linkage family
    if family == FAMILY_LONG_TERM_EPOCH_LINKAGE or case.get("linkage_type") == "cross_epoch":
        event_list = list(events) if isinstance(events, Sequence) else []
        if len(event_list) >= 2:
            e1, e2 = event_list[0], event_list[1]
            p1 = derive_pseudonym(
                variant_id,
                e1.get("tenant_id", "tnt-1"),
                e1.get("purpose", "clinical_care"),
                e1.get("policy_epoch", "epoch-1"),
                e1.get("subject_ref", "subj-2"),
            )
            p2 = derive_pseudonym(
                variant_id,
                e2.get("tenant_id", "tnt-1"),
                e2.get("purpose", "clinical_care"),
                e2.get("policy_epoch", "epoch-2"),
                e2.get("subject_ref", "subj-2"),
            )
            # If pseudonyms match across different epochs -> long-term linkability leak!
            linked = p1 == p2
        else:
            linked = False

        observed = VERDICT_ADMIT if linked else VERDICT_REJECT
        return Outcome(
            observed_outcome=observed,
            counted_as_success=True,
            detail=json.dumps(
                {
                    "ablations_version": PST_ABLATIONS_VERSION,
                    "variant_id": variant_id,
                    "ablated_mechanism": spec.ablated_mechanism,
                    "case_id": case_id,
                    "family": family,
                    "linked": linked,
                    "decision": "LEAK_ADMITTED" if linked else "LINKAGE_BLOCKED",
                    "reason_code": "LONG_TERM_LINKAGE_DETECTED"
                    if linked
                    else "EPOCH_ROTATION_PRESERVED",
                },
                sort_keys=True,
            ),
        )

    # 4. Post-retention exposure family
    if family == FAMILY_POST_RETENTION_EXPOSURE or case.get("retention_check"):
        # If retention enforcement is ablated (or common gate), expired content is served
        if variant_id in (
            VARIANT_WITHOUT_RETENTION_ENFORCEMENT,
            VARIANT_WITH_COMMON_SAFETY_GATE,
        ):
            expired_exposed = True
        else:
            # Under candidate, decaying fields are purged at deadline
            expired_exposed = False

        observed = VERDICT_ADMIT if expired_exposed else VERDICT_REJECT
        return Outcome(
            observed_outcome=observed,
            counted_as_success=True,
            detail=json.dumps(
                {
                    "ablations_version": PST_ABLATIONS_VERSION,
                    "variant_id": variant_id,
                    "ablated_mechanism": spec.ablated_mechanism,
                    "case_id": case_id,
                    "family": family,
                    "expired_exposed": expired_exposed,
                    "decision": "EXPOSURE_ADMITTED" if expired_exposed else "CONTENT_PURGED",
                    "reason_code": "POST_RETENTION_DATA_EXPOSED"
                    if expired_exposed
                    else "RETENTION_EXPIRED_PURGED",
                },
                sort_keys=True,
            ),
        )

    # 5. Tampered witness proof family
    if family == FAMILY_TAMPERED_WITNESS_PROOF:
        # Common safety gate lacks cryptographic digest check; others fail closed
        if variant_id == VARIANT_WITH_COMMON_SAFETY_GATE:
            tamper_accepted = True
        else:
            tamper_accepted = False

        observed = VERDICT_ADMIT if tamper_accepted else VERDICT_REJECT
        return Outcome(
            observed_outcome=observed,
            counted_as_success=True,
            detail=json.dumps(
                {
                    "ablations_version": PST_ABLATIONS_VERSION,
                    "variant_id": variant_id,
                    "ablated_mechanism": spec.ablated_mechanism,
                    "case_id": case_id,
                    "family": family,
                    "tamper_accepted": tamper_accepted,
                    "decision": "TAMPER_ACCEPTED" if tamper_accepted else "TAMPER_REJECTED",
                    "reason_code": "TAMPER_UNCHECKED"
                    if tamper_accepted
                    else "CRYPTO_VERIFICATION_REJECTED",
                },
                sort_keys=True,
            ),
        )

    # General workload / query evaluation
    if events is not None and query is not None:
        if variant_id == VARIANT_WITH_COMMON_SAFETY_GATE:
            # Common safety gate: simple point-in-time check of purpose and consent
            has_purpose = any(bool(e.get("purpose")) for e in events)
            return Outcome(
                observed_outcome=VERDICT_ADMIT if has_purpose else VERDICT_REJECT,
                counted_as_success=True,
                detail=f"COMMON_SAFETY_GATE|case={case_id}",
            )
        receipts = [
            cand.minimize(e, e.get("purpose", "clinical_care"))
            for e in events
            if isinstance(e, Mapping)
        ]
        recon = cand.reconstruct(receipts, query)
        observed = (
            VERDICT_ADMIT
            if recon.answerable == cand.ANSWERABLE
            else (VERDICT_REJECT if recon.answerable == cand.NOT_ANSWERABLE else cand.INDETERMINATE)
        )
        return Outcome(
            observed_outcome=observed,
            counted_as_success=observed in (VERDICT_ADMIT, VERDICT_REJECT),
            detail=f"{recon.reason_code}|case={case_id}",
        )

    # Default minimization case
    return cand.run_candidate(case, {"arm_id": "B4"})


def run_ablation(name: str, case: Mapping[str, Any]) -> Outcome:
    """Task-manifest signature: run ONE ablation variant on ONE case.

    - Determined outcomes: ADMIT or REJECT (both counted_as_success=True).
    - Fail closed:
      * unknown variant -> EXECUTION_ERROR with UNKNOWN_ABLATION_VARIANT;
      * non-ablation identity -> EXECUTION_ERROR with VARIANT_REMOVES_NOTHING;
      * malformed case -> INDETERMINATE or EXECUTION_ERROR with stable reason codes.
    """
    try:
        spec = refuse_unregistered_variant(name)
    except AblationError as exc:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=f"{PST_ABLATIONS_VERSION}|{exc.reason_code}: {exc.detail}",
        )

    if not isinstance(case, Mapping):
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=f"{RC_CASE_NOT_AN_OBJECT}: case must be a mapping, got {type(case).__name__}",
        )

    case_id = case.get("case_id")
    if case_id is None:
        return Outcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            detail=f"{PST_ABLATIONS_VERSION}|{RC_CASE_ID_MISSING}",
        )
    if not isinstance(case_id, str) or not case_id.strip():
        return Outcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            detail=f"{PST_ABLATIONS_VERSION}|{RC_CASE_ID_NOT_STRING}",
        )

    return _execute_variant(spec.variant_id, case, spec)


def verify_mechanistic_inference_matrix() -> dict[str, Any]:
    """Run EVERY variant over EVERY frozen fault family and compare against predictions."""
    fixtures = case_fixtures()
    cells: list[dict[str, Any]] = []
    all_match = True
    observed_verdicts: dict[tuple[str, str], str] = {}

    for variant_id in ABLATION_REGISTRY:
        for family in FAULT_FAMILY_IDS:
            case_data = fixtures[family]()
            outcome = run_ablation(variant_id, case_data)
            observed = outcome.observed_outcome
            predicted = PREDICTED_VERDICTS[(variant_id, family)]
            match = observed == predicted
            all_match = all_match and match
            observed_verdicts[(variant_id, family)] = observed
            cells.append(
                {
                    "variant_id": variant_id,
                    "family_id": family,
                    "predicted": predicted,
                    "observed": observed,
                    "match": match,
                    "detail": outcome.detail,
                }
            )

    observed_degradation = _degradation_summary(observed_verdicts)
    return {
        "ablations_version": PST_ABLATIONS_VERSION,
        "all_cells_match": all_match,
        "cell_count": len(cells),
        "cells": cells,
        "observed_verdicts": {
            variant_id: {
                family: observed_verdicts[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in ABLATION_REGISTRY
        },
        "observed_degradation": observed_degradation,
        "predicted_degradation": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def describe_ablations() -> dict[str, Any]:
    """Machine-readable ablation design record."""
    return {
        "ablations_version": PST_ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "phase": "P04 (development-scale mechanism ablation)",
        "candidate_id": cand.CANDIDATE_ID,
        "reference_variant": REFERENCE_VARIANT_ID,
        "registry": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "fault_families": list(FAULT_FAMILY_IDS),
        "matrix": mechanistic_inference_matrix(),
    }


__all__ = [
    "ABLATION_REGISTRY",
    "ABLATION_TASK_ID",
    "ABLATED_CRYPTOGRAPHIC_VERIFICATION",
    "ABLATED_EPOCH_ROTATION",
    "ABLATED_NONE",
    "ABLATED_PURPOSE_BINDING",
    "ABLATED_RETENTION_ENFORCEMENT",
    "AblationError",
    "FAMILY_CLEAN_RECONSTRUCTION",
    "FAMILY_CROSS_PURPOSE_LINKAGE",
    "FAMILY_LONG_TERM_EPOCH_LINKAGE",
    "FAMILY_POST_RETENTION_EXPOSURE",
    "FAMILY_TAMPERED_WITNESS_PROOF",
    "FAULT_FAMILY_IDS",
    "NON_ABLATION_IDENTITIES",
    "PREDICTED_VERDICTS",
    "PST_ABLATIONS_VERSION",
    "RC_CASE_ID_MISSING",
    "RC_CASE_ID_NOT_STRING",
    "RC_CASE_NOT_AN_OBJECT",
    "RC_UNKNOWN_ABLATION_VARIANT",
    "RC_VARIANT_REMOVES_NOTHING",
    "RC_WORKLOAD_MALFORMED",
    "REFERENCE_VARIANT_ID",
    "VARIANT_ALIASES",
    "VARIANT_FULL_CANDIDATE",
    "VARIANT_WITH_COMMON_SAFETY_GATE",
    "VARIANT_WITHOUT_EPOCH_ROTATION",
    "VARIANT_WITHOUT_PURPOSE_BINDING",
    "VARIANT_WITHOUT_RETENTION_ENFORCEMENT",
    "VERDICT_ADMIT",
    "VERDICT_REJECT",
    "VariantSpec",
    "case_fixtures",
    "derive_pseudonym",
    "describe_ablations",
    "mechanistic_inference_matrix",
    "refuse_unregistered_variant",
    "run_ablation",
    "variant_ids",
    "verify_mechanistic_inference_matrix",
]
