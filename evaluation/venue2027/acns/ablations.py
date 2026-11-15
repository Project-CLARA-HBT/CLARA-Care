"""ACNS-ablation — causal mechanism ablations of the SoK evidence-boundary instrument.

Purpose
-------
Task ACNS-ablation (Phase P04, venue acns) registers the four *SoK
reference-class ablation variants* behind the task-manifest signature
``run_ablation(name, case) -> Outcome``. This study is a **SoK**
(``research/venue2027/acns/novelty_contract.md`` §1): the variants are analytic
classifiers over synthetic evidence-claim records, not deployable systems, and
each ablation omits exactly ONE evidence component from the full
evidence-boundary reference (B3) so the mechanistic inference matrix can show
*which* gap register row (G1-G9, threat model §6) each weakened stance can no
longer detect — the causal witness that the omitted component *is* the
detection mechanism for that gap.

Variants (each reuses the existing EVIDENCE-BOUNDARY reference-class
classifiers in :mod:`evaluation.venue2027.acns.baselines` — no classifier is
duplicated or reimplemented here; the ablation deletes one evidence component
by passing an EMPTY record table for it, which is exactly the fixture-level
expression of "this component does not exist"):

- ``B0-attestation-only`` — omits the receipt/evidence table entirely
  (``omitted_component = "receipt_table"``): accepts any *claimed* attestation
  level as stated, without checking that a receipt (or any artifact) is bound
  to the claim. Mechanistically blind to G2/G4/G5 on the artifacts it never
  sees, and (by construction) detects nothing at all.
- ``B1-receipt-without-binding`` — omits the receipt-to-claim binding field
  (``omitted_component = "receipt_binding"``): a receipt artifact is *present*
  but its ``bound_to_claim_id`` link to THIS claim is deleted, so a
  transplanted receipt is indistinguishable from a genuine one (G4).
- ``B2-timestamp-only`` — omits every artifact component (receipts AND
  bindings AND attestation anchors; ``omitted_component = "all_artifacts"``):
  trust is inferred purely from timestamps, so timestamp-fresh claims with no
  evidence at all pass (G2/G4/G5/G7 all undetectable).
- ``B3-evidence-boundary-aware`` — the full reference: omits NOTHING
  (``omitted_component = "none"``); every required claim dimension must carry
  a bound, verifiable evidence pointer whose boundary conditions hold.

Each variant returns the structured, JSON-serializable
:class:`EvidenceBoundaryVerdict` of the reused classifier, carrying the granted
lattice level (L0..L4), ACCEPT/REJECT, and the detected gap codes from the
pre-registered register G1-G9. Ablation rows are typed
:class:`AblationVariant` (variant id, omitted component, blind register rows,
description) and the module exposes :func:`inference_matrix` — the mechanistic
matrix whose rows are the register gaps G1-G9 and whose cells record, per
variant, whether the variant can possibly detect that gap
(``detects`` / ``blind`` / ``not_applicable``) together with the mechanical
reason.

Allowed input
-------------
- ``case``: a JSON-serializable mapping over the synthetic ``synthetic-acns-2027``
  fixture set (``record_id``/``variant``/``case_id``; see ``_smoke_fixtures.py``).
  Malformed input fails closed with a stable reason code.
- ``name``: a variant id preregistered in :data:`ABLATION_REGISTRY`. Any other
  name — including a variant that omits nothing but is not the registered
  B3 row — is refused by :func:`refuse_unregistered_variant` /
  :func:`run_ablation` (``UNKNOWN_ABLATION_VARIANT``); a constant-allow stub
  can never masquerade as an ablation arm.

Failure semantics
-----------------
All errors are stable uppercase reason codes carried on the returned shared
harness :class:`Outcome` (``UNKNOWN_ABLATION_VARIANT``, ``MALFORMED_CASE``,
``NOT_RUN_EXTERNAL``); no unhandled exception escapes and no
incomplete/unknown verdict is ever counted as a safe acceptance. Unknown
cases are ``NOT_RUN_EXTERNAL`` (retriable, never counted as success). The
module is pure: no clock, no randomness, no network, no database, no live
provider.

Version
-------
``ACNS_ABLATIONS_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.acns import baselines

ACNS_ABLATIONS_VERSION: Final[str] = "1.0.0"

ABLATION_TASK_ID: Final[str] = "ACNS-ablation"

#: The register of evidence components an ablation may omit. ``none`` is the
#: full-reference row (B3); a variant omitting nothing must be registered as
#: exactly that row — there is no second "omits nothing" variant.
COMPONENT_NONE: Final[str] = "none"
COMPONENT_RECEIPT_TABLE: Final[str] = "receipt_table"
COMPONENT_RECEIPT_BINDING: Final[str] = "receipt_binding"
COMPONENT_ALL_ARTIFACTS: Final[str] = "all_artifacts"

#: Mechanistic inference-matrix cell values: ``detects`` — the variant can
#: fire this register row on some fixture case; ``blind`` — the omitted
#: component is the detection mechanism for this row, so the ablation is
#: structurally unable to fire it; ``not_applicable`` — the row's boundary
#: condition lies outside every variant's fixture surface (no case exercises
#: it, e.g. G3/G8), so no variant is credited or debited.
CELL_DETECTS: Final[str] = "detects"
CELL_BLIND: Final[str] = "blind"
CELL_NOT_APPLICABLE: Final[str] = "not_applicable"

REASON_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
REASON_MALFORMED_CASE: Final[str] = "MALFORMED_CASE"

VARIANT_B0: Final[str] = "B0-attestation-only"
VARIANT_B1: Final[str] = "B1-receipt-without-binding"
VARIANT_B2: Final[str] = "B2-timestamp-only"
VARIANT_B3: Final[str] = "B3-evidence-boundary-aware"

ABLATION_IDS: Final[tuple[str, ...]] = (VARIANT_B0, VARIANT_B1, VARIANT_B2, VARIANT_B3)


@dataclasses.dataclass(frozen=True)
class AblationVariant:
    """One registered ablation variant: what it omits and what that blinds."""

    variant_id: str
    omitted_component: str
    description: str
    blind_gap_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "omitted_component": self.omitted_component,
            "description": self.description,
            "blind_gap_codes": list(self.blind_gap_codes),
        }


#: The SoK reference-class ablation registry. Each entry omits exactly one
#: evidence component from the full B3 reference and reuses the existing
#: reference-class classifier from :mod:`...acns.baselines` verbatim.
ABLATION_REGISTRY: Final[Mapping[str, AblationVariant]] = {
    VARIANT_B0: AblationVariant(
        variant_id=VARIANT_B0,
        omitted_component=COMPONENT_RECEIPT_TABLE,
        description=(
            "omits the receipt/evidence table entirely: accepts any claimed "
            "attestation level as stated (RFC 9334 vocabulary as bare "
            "claim-reading); structurally blind to G2/G4/G5 on artifacts it "
            "never sees and, by construction, detects nothing at all"
        ),
        blind_gap_codes=(
            "G2_RECEIPT_AS_EXECUTION",
            "G4_SIGNATURE_AS_CONTEXT",
            "G5_MINT_TIME_AS_RELY_TIME",
        ),
    ),
    VARIANT_B1: AblationVariant(
        variant_id=VARIANT_B1,
        omitted_component=COMPONENT_RECEIPT_BINDING,
        description=(
            "omits the receipt-to-claim binding field: a receipt artifact is "
            "present but its bound_to_claim_id link to THIS claim is deleted, "
            "so a transplanted/replayed receipt is indistinguishable from a "
            "genuine one (G4 undetectable) and no anchor/schedule check "
            "remains (G2/G5 undetectable)"
        ),
        blind_gap_codes=(
            "G2_RECEIPT_AS_EXECUTION",
            "G4_SIGNATURE_AS_CONTEXT",
            "G5_MINT_TIME_AS_RELY_TIME",
        ),
    ),
    VARIANT_B2: AblationVariant(
        variant_id=VARIANT_B2,
        omitted_component=COMPONENT_ALL_ARTIFACTS,
        description=(
            "omits every artifact component (receipts, bindings, attestation "
            "anchors): trust is inferred purely from timestamps, so a "
            "timestamp-fresh claim with no evidence at all passes (G2/G4/G5/G7 "
            "all undetectable)"
        ),
        blind_gap_codes=(
            "G2_RECEIPT_AS_EXECUTION",
            "G4_SIGNATURE_AS_CONTEXT",
            "G5_MINT_TIME_AS_RELY_TIME",
            "G7_LEVEL_IMPLICIT_UPGRADE",
        ),
    ),
    VARIANT_B3: AblationVariant(
        variant_id=VARIANT_B3,
        omitted_component=COMPONENT_NONE,
        description=(
            "full evidence-boundary reference: omits nothing; every required "
            "claim dimension must carry a bound, verifiable evidence pointer "
            "whose boundary conditions (context binding, attested-execution "
            "anchor, verification-time schedule check) hold"
        ),
        blind_gap_codes=(),
    ),
}

#: Precomputed mechanistic inference matrix (design-time, mechanically
#: derived from the classifiers' check structure): for each gap register row,
#: which variants can detect it on the fixture surface and why. Frozen before
#: any ablation run; :func:`inference_matrix` verifies it against executed
#: behavior and raises on divergence.
_INFERENCE_MATRIX: Final[Mapping[str, Mapping[str, str]]] = {
    "G1_TRANSPORT_ACK_AS_PROCESSING": {
        VARIANT_B0: CELL_NOT_APPLICABLE,
        VARIANT_B1: CELL_NOT_APPLICABLE,
        VARIANT_B2: CELL_NOT_APPLICABLE,
        VARIANT_B3: CELL_NOT_APPLICABLE,
    },
    "G2_RECEIPT_AS_EXECUTION": {
        VARIANT_B0: CELL_BLIND,
        VARIANT_B1: CELL_BLIND,
        VARIANT_B2: CELL_BLIND,
        VARIANT_B3: CELL_DETECTS,
    },
    "G3_EXECUTION_AS_CONSUMPTION": {
        VARIANT_B0: CELL_NOT_APPLICABLE,
        VARIANT_B1: CELL_NOT_APPLICABLE,
        VARIANT_B2: CELL_NOT_APPLICABLE,
        VARIANT_B3: CELL_NOT_APPLICABLE,
    },
    "G4_SIGNATURE_AS_CONTEXT": {
        VARIANT_B0: CELL_BLIND,
        VARIANT_B1: CELL_BLIND,
        VARIANT_B2: CELL_BLIND,
        VARIANT_B3: CELL_DETECTS,
    },
    "G5_MINT_TIME_AS_RELY_TIME": {
        VARIANT_B0: CELL_BLIND,
        VARIANT_B1: CELL_BLIND,
        VARIANT_B2: CELL_BLIND,
        VARIANT_B3: CELL_NOT_APPLICABLE,
    },
    "G6_TIMESTAMP_AS_ORDERING": {
        VARIANT_B0: CELL_BLIND,
        VARIANT_B1: CELL_BLIND,
        VARIANT_B2: CELL_NOT_APPLICABLE,
        VARIANT_B3: CELL_NOT_APPLICABLE,
    },
    "G7_LEVEL_IMPLICIT_UPGRADE": {
        VARIANT_B0: CELL_BLIND,
        VARIANT_B1: CELL_NOT_APPLICABLE,
        VARIANT_B2: CELL_BLIND,
        VARIANT_B3: CELL_DETECTS,
    },
    "G8_AUTHORITY_SCOPE_CROSSING": {
        VARIANT_B0: CELL_NOT_APPLICABLE,
        VARIANT_B1: CELL_NOT_APPLICABLE,
        VARIANT_B2: CELL_NOT_APPLICABLE,
        VARIANT_B3: CELL_NOT_APPLICABLE,
    },
    "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE": {
        VARIANT_B0: CELL_NOT_APPLICABLE,
        VARIANT_B1: CELL_DETECTS,
        VARIANT_B2: CELL_NOT_APPLICABLE,
        VARIANT_B3: CELL_NOT_APPLICABLE,
    },
}


def _norm_level(value: Any) -> str:
    """Canonicalize a level token (accepts 'L2' / 'L2-ACKNOWLEDGED' spellings)."""
    if not isinstance(value, str) or not value.strip():
        return ""
    token = value.strip().upper()
    for level in baselines.LATTICE_LEVELS:
        if token in (level, level.split("-", 1)[0], level.split("-", 1)[1]):
            return level
    return ""


def refuse_unregistered_variant(name: str) -> Outcome | None:
    """Return the refusal Outcome for an unregistered variant, else ``None``.

    Fail-closed gate: only the four preregistered reference-class rows in
    :data:`ABLATION_REGISTRY` may run. A variant that omits nothing but is
    not the registered B3 row is by definition not in the registry and is
    refused here — omission completeness is a property OF the registered row,
    not of the caller's intent.
    """
    if name in ABLATION_REGISTRY:
        return None
    return Outcome(
        observed_outcome="INVALID_RESULT",
        counted_as_success=False,
        retriable=False,
        detail=(
            f"{REASON_UNKNOWN_ABLATION_VARIANT}: ablation variant {name!r} is not a "
            f"preregistered reference-class row of ABLATION_REGISTRY "
            f"(registered: {list(ABLATION_REGISTRY)})"
        ),
    )


def _ablate_record(
    record: Mapping[str, Any], omitted_component: str, variant_id: str
) -> dict[str, Any]:
    """Build the component-omitted copy of one fixture record for one variant.

    The ablation deletes exactly the omitted evidence component from the
    record copy — an empty/deleted receipt table, stripped receipt-to-claim
    bindings, or nothing — and then lets the EXISTING reference-class
    classifier run unchanged over the result. The classifier is never
    modified: the ablation is expressed purely as the absence of the
    component on the input record.
    """
    ablated: dict[str, Any] = dict(record)

    if omitted_component == COMPONENT_RECEIPT_TABLE:
        # B0: the record carries no evidence artifacts at all — any claimed
        # level is accepted as stated.
        ablated["receipts"] = {}
        ablated["claims_case"] = _claims_with_component_stripped(
            record, strip_receipt_ids=True, strip_attestation_anchor=True
        )
        return ablated

    if omitted_component == COMPONENT_RECEIPT_BINDING:
        # B1: receipts exist, but the binding field tying each receipt to
        # THIS claim (bound_to_claim_id) is deleted — presence without linkage.
        ablated["receipts"] = {
            receipt_id: {key: value for key, value in receipt.items() if key != "bound_to_claim_id"}
            if isinstance(receipt, Mapping)
            else receipt
            for receipt_id, receipt in (record.get("receipts") or {}).items()
        }
        ablated["claims_case"] = _claims_with_component_stripped(
            record, strip_receipt_ids=True, strip_attestation_anchor=True
        )
        return ablated

    if omitted_component == COMPONENT_ALL_ARTIFACTS:
        # B2: no artifacts whatsoever — timestamps carry all the evidential
        # weight.
        ablated["receipts"] = {}
        ablated["claims_case"] = _claims_with_component_stripped(
            record,
            strip_receipt_ids=True,
            strip_attestation_anchor=True,
            strip_bindings=True,
        )
        return ablated

    if omitted_component == COMPONENT_NONE:
        # B3 reference row: nothing is omitted.
        return ablated

    raise ValueError(
        f"{REASON_UNKNOWN_ABLATION_VARIANT}: variant {variant_id!r} omits unknown "
        f"component {omitted_component!r}"
    )


def _claims_with_component_stripped(
    record: Mapping[str, Any],
    *,
    strip_receipt_ids: bool = False,
    strip_attestation_anchor: bool = False,
    strip_bindings: bool = False,
) -> dict[str, Any]:
    """Copy the record's claims_case with the named claim fields removed."""
    claims_case = record.get("claims_case")
    if not isinstance(claims_case, Mapping):
        return {}
    claims = claims_case.get("claims")
    if not isinstance(claims, Sequence) or isinstance(claims, str | bytes):
        claims = []
    stripped_claims: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            stripped_claims.append({})
            continue
        stripped = dict(claim)
        bindings = stripped.get("evidence_bindings")
        if (
            strip_receipt_ids
            and isinstance(bindings, Sequence)
            and not isinstance(bindings, str | bytes)
        ):
            stripped["evidence_bindings"] = [
                {k: v for k, v in binding.items() if k != "receipt_id"}
                if isinstance(binding, Mapping)
                else binding
                for binding in bindings
            ]
        if strip_attestation_anchor:
            stripped.pop("attested_execution", None)
            stripped.pop("schedule_checked_at_rely_time", None)
        if strip_bindings:
            stripped.pop("evidence_bindings", None)
        stripped_claims.append(stripped)
    return {"claims": stripped_claims}


def _case_records() -> dict[tuple[str, str], dict[str, Any]]:
    """Load the synthetic fixture records via the baselines loader."""
    return baselines.load_reference_records()


def run_ablation(name: str, case: Mapping[str, Any]) -> Outcome:
    """Task-manifest signature: run ONE ablation variant on ONE case -> Outcome.

    Contract ``run_ablation(name, case) -> Outcome``:

    - unknown/unregistered variant (including any omit-nothing variant other
      than the registered B3 row) -> ``INVALID_RESULT`` /
      ``UNKNOWN_ABLATION_VARIANT`` (never silently run as the full reference);
    - malformed case -> ``INVALID_RESULT`` / ``MALFORMED_CASE``;
    - case whose ``(record_id, variant)`` is not in the synthetic fixture set
      -> ``NOT_RUN_EXTERNAL`` (honest, retriable, never counted as success);
    - otherwise ``ADMIT``/``REJECT`` with the reused classifier's structured
      evidence-boundary verdict (granted lattice level + G-code gaps) in
      ``detail``.
    """
    refusal = refuse_unregistered_variant(name)
    if refusal is not None:
        return refusal

    if not isinstance(case, Mapping):
        return Outcome(
            observed_outcome="INVALID_RESULT",
            counted_as_success=False,
            retriable=False,
            detail=f"{REASON_MALFORMED_CASE}: case must be a mapping, got {type(case).__name__}",
        )

    spec = ABLATION_REGISTRY[name]
    try:
        records = _case_records()
    except baselines.BaselineInputError as exc:
        payload = {
            "ablation_id": name,
            "case_id": str(case.get("case_id", "")),
            "omitted_component": spec.omitted_component,
            "reason_code": baselines.STATUS_REASON_NOT_RUN_EXTERNAL,
        }
        return Outcome(
            observed_outcome="NOT_RUN_EXTERNAL",
            counted_as_success=False,
            retriable=True,
            detail=json.dumps(payload, sort_keys=True) + " | " + exc.detail,
        )

    record_key = (str(case.get("record_id", "")), str(case.get("variant", "")))
    record = records.get(record_key)
    if record is None:
        payload = {
            "ablation_id": name,
            "case_id": str(case.get("case_id", "")),
            "omitted_component": spec.omitted_component,
            "reason_code": baselines.STATUS_REASON_NOT_RUN_EXTERNAL,
            "record_id": record_key[0],
            "variant": record_key[1],
        }
        return Outcome(
            observed_outcome="NOT_RUN_EXTERNAL",
            counted_as_success=False,
            retriable=True,
            detail=json.dumps(payload, sort_keys=True)
            + f" | record_id/variant {record_key!r} not in synthetic fixture set",
        )

    ablated_record = _ablate_record(record, spec.omitted_component, name)
    # Reuse the EXISTING reference-class classifier over the ablated record.
    # The classifier call shape mirrors baselines.run_baseline's internal
    # merge: the fixture record's claims_case IS the classified case.
    merged_case: dict[str, Any] = dict(ablated_record.get("claims_case") or {})
    merged_case["case_id"] = str(case.get("case_id", merged_case.get("case_id", record_key[0])))
    verdict = baselines._classify(
        name, merged_case, baselines._CLASS_POLICIES[name], ablated_record.get("receipts") or {}
    )
    observed = {"ACCEPT": "ADMIT", "REJECT": "REJECT"}.get(verdict.verdict, "INDETERMINATE")
    payload = {
        **verdict.to_dict(),
        "ablation_version": ACNS_ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "omitted_component": spec.omitted_component,
        "blind_gap_codes": list(spec.blind_gap_codes),
    }
    return Outcome(
        observed_outcome=observed,
        counted_as_success=verdict.verdict == "ACCEPT",
        retriable=False,
        detail=json.dumps(payload, sort_keys=True),
    )


def run_ablation_suite() -> dict[str, Any]:
    """Run every registered variant over the SAME synthetic fixture set.

    Returns the per-variant per-case outcome grid plus the mechanistic
    inference matrix and the witnessed gap-detection comparison (which gaps
    each weaker variant demonstrably misses that B3 catches). Same-cases
    invariant: every variant sees the identical (record_id, variant) keys.
    """
    records = _case_records()
    grid: dict[str, dict[str, str]] = {}
    detected: dict[str, set[str]] = {}
    for name in ABLATION_REGISTRY:
        grid[name] = {}
        detected[name] = set()
        for record_key in sorted(records):
            outcome = run_ablation(name, {"record_id": record_key[0], "variant": record_key[1]})
            grid[name][f"{record_key[0]}/{record_key[1]}"] = outcome.observed_outcome
            if outcome.observed_outcome == "REJECT":
                try:
                    verdict = json.loads(outcome.detail)
                except json.JSONDecodeError:
                    continue
                for gap in verdict.get("gaps", []):
                    code = str(gap.get("gap_code", ""))
                    if code:
                        detected[name].add(code)
    matrix = inference_matrix()
    matrix_verified = verify_inference_matrix(detected)
    comparison = {
        "gaps_b3_catches": sorted(detected[VARIANT_B3]),
        "gaps_missed_by_weaker_variants": {
            name: sorted(detected[VARIANT_B3] - detected[name])
            for name in (VARIANT_B0, VARIANT_B1, VARIANT_B2)
        },
    }
    return {
        "ablation_version": ACNS_ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "dataset": "synthetic-acns-2027",
        "case_keys": [f"{key[0]}/{key[1]}" for key in sorted(records)],
        "outcome_grid": grid,
        "detected_gap_codes": {name: sorted(codes) for name, codes in detected.items()},
        "inference_matrix": matrix,
        "inference_matrix_verified": matrix_verified,
        "comparison": comparison,
    }


def inference_matrix() -> dict[str, dict[str, str]]:
    """The mechanistic inference matrix (register gap x variant cell).

    Rows are the pre-registered gap register rows G1-G9 (threat model §6);
    columns are the four registered variants. Cell semantics:
    ``detects`` — the variant fires this row on the fixture surface;
    ``blind`` — the variant's omitted component IS the detection mechanism
    for this row, so the ablation structurally cannot fire it;
    ``not_applicable`` — no fixture case exercises this row's boundary
    condition for this variant (no credit, no debit).
    """
    return {gap: dict(cells) for gap, cells in _INFERENCE_MATRIX.items()}


def verify_inference_matrix(detected: Mapping[str, Mapping[str, Any]]) -> bool:
    """Verify executed detection behavior against the frozen design matrix.

    ``detected`` maps variant id -> collection of gap codes it actually fired
    on the fixture surface. Every cell marked ``detects`` must have fired;
    every cell marked ``blind`` must NOT have fired (the omitted component is
    the mechanism — if a blind variant fires the row, the matrix was wrong
    and the caller must stop, never repair the matrix post hoc). Cells marked
    ``not_applicable`` are outside the assertion surface.
    """
    for gap, cells in _INFERENCE_MATRIX.items():
        for variant_id, cell in cells.items():
            fired = gap in (detected.get(variant_id) or set())
            if cell == CELL_DETECTS and not fired:
                return False
            if cell == CELL_BLIND and fired:
                return False
    return True


def describe_ablation() -> dict[str, Any]:
    """Machine-readable ablation design record (no empirical results here)."""
    return {
        "ablation_version": ACNS_ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "phase": "P04 (SoK reference-class ablation variants)",
        "study_class": "SoK",
        "paper": "SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems",
        "reused_classifier": "evaluation/venue2027/acns/baselines.py",
        "variants": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "inference_matrix": inference_matrix(),
        "manifest_signature": "run_ablation(name: str, case: Mapping) -> Outcome",
        "refusal_reason_code": REASON_UNKNOWN_ABLATION_VARIANT,
    }


__all__ = [
    "ABLATION_IDS",
    "ABLATION_REGISTRY",
    "ABLATION_TASK_ID",
    "ACNS_ABLATIONS_VERSION",
    "AblationVariant",
    "CELL_BLIND",
    "CELL_DETECTS",
    "CELL_NOT_APPLICABLE",
    "COMPONENT_ALL_ARTIFACTS",
    "COMPONENT_NONE",
    "COMPONENT_RECEIPT_BINDING",
    "COMPONENT_RECEIPT_TABLE",
    "REASON_MALFORMED_CASE",
    "REASON_UNKNOWN_ABLATION_VARIANT",
    "VARIANT_B0",
    "VARIANT_B1",
    "VARIANT_B2",
    "VARIANT_B3",
    "describe_ablation",
    "inference_matrix",
    "refuse_unregistered_variant",
    "run_ablation",
    "run_ablation_suite",
    "verify_inference_matrix",
]
