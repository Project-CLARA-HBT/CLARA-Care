"""ACNS-baselines — EVIDENCE-BOUNDARY reference-class baselines for the ACNS SoK.

Purpose
-------
Task ACNS-baselines (Phase P03, venue acns) implements
``run_baseline(baseline_id, case, ctx) -> Outcome`` for four *analytic
reference classes* over evidence claims. Per the signed novelty contract
(``research/venue2027/acns/novelty_contract.md`` §1) this study is a **SoK**:
the baselines are analytic classifiers over evidence-claim records, not
deployable systems, and no new mechanism is proposed or evaluated. Each
reference class encodes the claim-acceptance semantics of a published
attestation-evidence stance so the SoK can demonstrate — with executable
counterexample witnesses — which implication pairs each stance fails to
police:

- ``B0-attestation-only`` — accepts any *claimed* attestation level as stated,
  without checking that a receipt (or any artifact) is bound to the claim
  (the RFC 9334 vocabulary applied as bare claim-reading, blueprint arm B0).
- ``B1-receipt-without-binding`` — checks that a receipt artifact is *present*
  but ignores whether it is cryptographically/field-wise linked to the claim
  (the "a receipt exists, therefore the claim holds" stance).
- ``B2-timestamp-only`` — infers trust purely from timestamps (freshness
  heuristics), ignoring artifacts and binding entirely.
- ``B3-evidence-boundary-aware`` — the candidate reference: accepts a claim
  only when every required claim dimension carries a bound, verifiable
  evidence pointer whose boundary conditions (nonce/context binding, digest
  binding, verification-time schedule check, attested-execution anchor) hold.

Each baseline returns a structured, JSON-serializable evidence-boundary
verdict carrying: the lattice level granted to the claim (L0..L4 per the
threat model §1.2), stable gap codes from the pre-registered register
G1–G9 (``research/venue2027/acns/threat_model.md`` §6), and per-claim gap
detail. Gaps are *descriptions of detected boundary violations*, not
defensive actions — the witnesses exist to map where implications fail.

Unavailable upstream -> NOT_RUN_EXTERNAL
----------------------------------------
The pinned upstream artifacts for arms B0/B1/B2 (RFC 9334 taxonomy port,
PROV-DM lineage port, AgentDojo/ToolEmu extraction port) do not exist in this
worktree (``evaluation/venue2027/acns`` was absent; see
``research/venue2027/acns/literature_matrix.csv`` fidelity rows, all
UNAVAILABLE_NOT_RUN at task start). Per EXECUTION_CONTRACT rule 8 ("never
replace an unavailable baseline by a custom toy and keep the same name"), the
*registry-named comparator arms* are not fabricated here. Instead, this
module implements the task-manifest reference classes over the synthetic
fixture records in ``_smoke_fixtures.py`` (synthetic-acns-2027) and answers
with ``NOT_RUN_EXTERNAL`` whenever a case's declared upstream evidence cannot
be located — the honest, transparent status that prevents unsupported
comparative claims (RESEARCH_BLUEPRINT.md, "Strong baselines and purpose").

Allowed input
-------------
- ``case``: a JSON-serializable mapping (synthetic evidence-claim record;
  see ``_smoke_fixtures.py`` / ``make_claim_case``). Malformed input fails
  closed with a stable reason code — it is never silently accepted.
- ``ctx``: a mapping or ``harness.RunContext``-like object carrying
  ``arm_id``/``case_id``/``seed``; arms not preregistered in
  ``BASELINE_IDS`` are refused (``UNKNOWN_BASELINE``) so a constant-allow
  stub can never masquerade as an arm.

Failure semantics
-----------------
All errors are stable uppercase reason codes carried on the returned
:class:`Outcome` (``observed_outcome`` in the shared harness bucket set);
no unhandled exception escapes and no incomplete/unknown verdict is ever
counted as a safe acceptance. Unknown cases (no fixture record) are
``NOT_RUN_EXTERNAL``. The module is pure: no clock, no randomness, no
network, no database, no live provider.

Version
-------
``ACNS_BASELINES_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

ACNS_BASELINES_VERSION = "1.0.0"

BASELINE_IDS: tuple[str, ...] = (
    "B0-attestation-only",
    "B1-receipt-without-binding",
    "B2-timestamp-only",
    "B3-evidence-boundary-aware",
)

#: Lattice levels of the evidence-to-claim lattice (threat model §1.2).
LATTICE_LEVELS: tuple[str, ...] = (
    "L0-ASSUMED",
    "L1-ASSEMBLED",
    "L2-ACKNOWLEDGED",
    "L3-EXECUTED",
    "L4-COMMITTED",
)

#: Pre-registered gap codes (threat model §6 register G1-G9).
KNOWN_GAP_CODES: frozenset[str] = frozenset(
    {
        "G1_TRANSPORT_ACK_AS_PROCESSING",
        "G2_RECEIPT_AS_EXECUTION",
        "G3_EXECUTION_AS_CONSUMPTION",
        "G4_SIGNATURE_AS_CONTEXT",
        "G5_MINT_TIME_AS_RELY_TIME",
        "G6_TIMESTAMP_AS_ORDERING",
        "G7_LEVEL_IMPLICIT_UPGRADE",
        "G8_AUTHORITY_SCOPE_CROSSING",
        "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
    }
)

LEVEL_RANK: dict[str, int] = {level: index for index, level in enumerate(LATTICE_LEVELS)}

#: Claim dimensions and the minimum lattice level each requires for the
#: claim as stated to be entitled to its asserted level.
DIMENSION_MINIMUM_LEVEL: dict[str, str] = {
    "dispatch": "L1-ASSEMBLED",
    "receipt": "L2-ACKNOWLEDGED",
    "execution": "L3-EXECUTED",
    "consumption": "L4-COMMITTED",
}

STATUS_REASON_UNKNOWN_BASELINE = "UNKNOWN_BASELINE"
STATUS_REASON_MALFORMED_CASE = "MALFORMED_CASE"
STATUS_REASON_NOT_RUN_EXTERNAL = "NOT_RUN_EXTERNAL"
STATUS_REASON_UNKNOWN_CASE = "UNKNOWN_CASE"


class BaselineInputError(ValueError):
    """Fail-closed input violation with a stable machine-checkable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class ClaimGap:
    """One detected evidence-boundary gap on one claim dimension."""

    claim_id: str
    dimension: str
    gap_code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "claim_id": self.claim_id,
            "dimension": self.dimension,
            "gap_code": self.gap_code,
            "detail": self.detail,
        }


@dataclasses.dataclass(frozen=True)
class EvidenceBoundaryVerdict:
    """Structured verdict: granted lattice level + detected gaps (additive-only)."""

    baseline_id: str
    case_id: str
    granted_level: str
    verdict: str
    reason_code: str
    gaps: tuple[ClaimGap, ...]
    baseline_version: str = ACNS_BASELINES_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "case_id": self.case_id,
            "granted_level": self.granted_level,
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "gaps": [gap.to_dict() for gap in self.gaps],
            "baseline_version": self.baseline_version,
        }


def _level_at_least(granted: str, required: str) -> bool:
    return LEVEL_RANK.get(granted, -1) >= LEVEL_RANK.get(required, 99)


def _norm_level(value: Any) -> str:
    """Canonicalize a level token (accepts 'L2' / 'L2-ACKNOWLEDGED' spellings)."""
    if not isinstance(value, str) or not value.strip():
        return ""
    token = value.strip().upper()
    for level in LATTICE_LEVELS:
        if token in (level, level.split("-", 1)[0], level.split("-", 1)[1]):
            return level
    return ""


def _ctx_get(ctx: Any, key: str, default: Any = None) -> Any:
    if isinstance(ctx, Mapping):
        return ctx.get(key, default)
    return getattr(ctx, key, default)


def _resolve_arm_id(baseline_id: str, ctx: Any) -> str:
    arm_id = str(_ctx_get(ctx, "arm_id", "") or "")
    return arm_id or baseline_id


def _case_field(case: Mapping[str, Any], key: str) -> Any:
    value = case.get(key)
    if value is None and "claim_record" in case:
        nested = case["claim_record"]
        if isinstance(nested, Mapping):
            return nested.get(key)
    return value


def load_reference_records() -> dict[tuple[str, str], dict[str, Any]]:
    """Import the synthetic fixture records keyed by (record_id, variant).

    Returns a fresh copy per call so external mutation cannot cross-contaminate
    baselines. Raises ``BaselineInputError("FIXTURE_RECORDS_UNAVAILABLE")``
    if the fixture module cannot be loaded — callers must then answer
    ``NOT_RUN_EXTERNAL`` rather than fabricate records.
    """
    from evaluation.venue2027.acns import _smoke_fixtures

    records = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS
    if not isinstance(records, Mapping) or not records:
        raise BaselineInputError(
            "FIXTURE_RECORDS_UNAVAILABLE", "synthetic claim records missing or empty"
        )
    return {key: dict(value) for key, value in records.items()}


def _unavailable_outcome(baseline_id: str, case: Mapping[str, Any], detail: str) -> Outcome:
    payload = {
        "baseline_id": baseline_id,
        "case_id": str(case.get("case_id", "")),
        "granted_level": "",
        "verdict": "NOT_RUN",
        "reason_code": STATUS_REASON_NOT_RUN_EXTERNAL,
        "gaps": [],
    }
    return Outcome(
        observed_outcome="NOT_RUN_EXTERNAL",
        counted_as_success=False,
        retriable=True,
        detail=json.dumps(
            {"reason_code": STATUS_REASON_NOT_RUN_EXTERNAL, **payload}, sort_keys=True
        )
        + " | "
        + detail,
    )


def _error_outcome(reason_code: str, detail: str) -> Outcome:
    return Outcome(
        observed_outcome="INVALID_RESULT",
        counted_as_success=False,
        retriable=False,
        detail=f"{reason_code}: {detail}",
    )


def _gaps_for_claim(
    baseline_id: str,
    claim: Mapping[str, Any],
    policy: _ClassPolicy,
    record_bindings: Mapping[str, Mapping[str, Any]],
) -> list[ClaimGap]:
    """Detect boundary gaps on one claim under one reference-class policy.

    ``policy`` encodes what the reference class *checks*; a check the class
    does not perform simply never produces a gap, which is exactly how the
    SoK witnesses expose each stance's blind spots.
    """
    gaps: list[ClaimGap] = []
    claim_id = str(claim.get("claim_id", ""))
    dimension = str(claim.get("dimension", ""))
    required = DIMENSION_MINIMUM_LEVEL.get(dimension)
    asserted = _norm_level(claim.get("asserted_level"))

    if required is None:
        gaps.append(
            ClaimGap(
                claim_id=claim_id,
                dimension=dimension or "unknown",
                gap_code="G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
                detail=f"claim dimension {dimension!r} is outside the lattice dimensions",
            )
        )
        return gaps

    bindings = claim.get("evidence_bindings")
    if not isinstance(bindings, Sequence) or isinstance(bindings, str | bytes):
        bindings = []
    bound_dimensions = {str(binding.get("dimension", "")) for binding in bindings}
    dimension_bound = dimension in bound_dimensions

    # --- binding checks (B0 skips entirely; B1 checks presence only) --------
    if not dimension_bound:
        if policy.require_binding:
            gaps.append(
                ClaimGap(
                    claim_id=claim_id,
                    dimension=dimension,
                    gap_code="G7_LEVEL_IMPLICIT_UPGRADE",
                    detail=(
                        f"claim asserts {asserted or 'a level'} without any evidence binding "
                        f"on dimension {dimension!r}"
                    ),
                )
            )
        elif policy.require_receipt_presence:
            gaps.append(
                ClaimGap(
                    claim_id=claim_id,
                    dimension=dimension,
                    gap_code="G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
                    detail=(
                        "receipt presence not even disclosable: no binding artifact exists "
                        "for dimension " + repr(dimension)
                    ),
                )
            )
        # B0: no gap recorded here — its blind spot by construction.
    elif policy.require_binding and policy.require_receipt_presence is not False and False:
        # Unreachable guard kept for explicitness of the policy lattice.
        pass

    # --- receipt binding depth (G4-style context binding) -------------------
    if dimension_bound and policy.require_binding:
        binding = next(b for b in bindings if str(b.get("dimension", "")) == dimension)
        binding_kind = str(binding.get("binding_kind", ""))
        if binding_kind not in ("receipt-bound", "attested-bound"):
            gaps.append(
                ClaimGap(
                    claim_id=claim_id,
                    dimension=dimension,
                    gap_code="G4_SIGNATURE_AS_CONTEXT",
                    detail=(
                        f"binding kind {binding_kind!r} does not bind the artifact to this "
                        "claim's context (nonce/digest/purpose)"
                    ),
                )
            )

    # --- B2: timestamp-only inference gap (G6) ------------------------------
    if policy.infer_from_timestamps:
        ts = claim.get("timestamp")
        if not isinstance(ts, str) or not ts:
            gaps.append(
                ClaimGap(
                    claim_id=claim_id,
                    dimension=dimension,
                    gap_code="G6_TIMESTAMP_AS_ORDERING",
                    detail="timestamp-only stance: no usable timestamp to infer from",
                )
            )

    # --- upstream receipt verification (B3 only) ----------------------------
    if policy.require_upstream_receipt and dimension_bound:
        binding = next(b for b in bindings if str(b.get("dimension", "")) == dimension)
        receipt_id = str(binding.get("receipt_id", ""))
        if receipt_id:
            receipt = record_bindings.get(receipt_id)
            if receipt is None:
                gaps.append(
                    ClaimGap(
                        claim_id=claim_id,
                        dimension=dimension,
                        gap_code="G2_RECEIPT_AS_EXECUTION",
                        detail=f"referenced receipt {receipt_id!r} not found in the record set",
                    )
                )
            elif not receipt.get("bound_to_claim_id") == claim_id:
                gaps.append(
                    ClaimGap(
                        claim_id=claim_id,
                        dimension=dimension,
                        gap_code="G4_SIGNATURE_AS_CONTEXT",
                        detail=(
                            f"receipt {receipt_id!r} is not bound to claim {claim_id!r} "
                            "(replayed or transplanted artifact)"
                        ),
                    )
                )
        else:
            gaps.append(
                ClaimGap(
                    claim_id=claim_id,
                    dimension=dimension,
                    gap_code="G7_LEVEL_IMPLICIT_UPGRADE",
                    detail="binding present but no receipt identifier to verify against",
                )
            )

    # --- attested-execution anchor (G2) for execution/consumption claims ----
    if dimension in ("execution", "consumption") and _level_at_least(
        asserted or "L0-ASSUMED", "L3-EXECUTED"
    ):
        anchored = bool(claim.get("attested_execution"))
        if policy.require_attested_execution and not anchored:
            gaps.append(
                ClaimGap(
                    claim_id=claim_id,
                    dimension=dimension,
                    gap_code="G2_RECEIPT_AS_EXECUTION",
                    detail=(
                        "execution/consumption claim asserted without a TEE-attested "
                        "execution anchor (receipt alone caps at L2)"
                    ),
                )
            )

    # --- verification-time schedule check (G5) ------------------------------
    if policy.require_schedule_check and not claim.get("schedule_checked_at_rely_time"):
        gaps.append(
            ClaimGap(
                claim_id=claim_id,
                dimension=dimension,
                gap_code="G5_MINT_TIME_AS_RELY_TIME",
                detail="no verification-time revocation/schedule check at rely time",
            )
        )

    return gaps


@dataclasses.dataclass(frozen=True)
class _ClassPolicy:
    """What each reference class checks (absence = that class's blind spot)."""

    require_binding: bool
    require_receipt_presence: bool
    infer_from_timestamps: bool
    require_upstream_receipt: bool
    require_attested_execution: bool
    require_schedule_check: bool


_CLASS_POLICIES: dict[str, _ClassPolicy] = {
    "B0-attestation-only": _ClassPolicy(
        require_binding=False,
        require_receipt_presence=False,
        infer_from_timestamps=False,
        require_upstream_receipt=False,
        require_attested_execution=False,
        require_schedule_check=False,
    ),
    "B1-receipt-without-binding": _ClassPolicy(
        require_binding=False,
        require_receipt_presence=True,
        infer_from_timestamps=False,
        require_upstream_receipt=False,
        require_attested_execution=False,
        require_schedule_check=False,
    ),
    "B2-timestamp-only": _ClassPolicy(
        require_binding=False,
        require_receipt_presence=False,
        infer_from_timestamps=True,
        require_upstream_receipt=False,
        require_attested_execution=False,
        require_schedule_check=False,
    ),
    "B3-evidence-boundary-aware": _ClassPolicy(
        require_binding=True,
        require_receipt_presence=True,
        infer_from_timestamps=False,
        require_upstream_receipt=True,
        require_attested_execution=True,
        require_schedule_check=True,
    ),
}


def _grant_level_for_gaps(asserted: str, gaps: Sequence[ClaimGap]) -> str:
    """Cap the granted level below the first dimension with a detected gap.

    The cap follows the lattice: any gap on a dimension caps the granted
    level to the highest level whose full dimension chain is gap-free.
    """
    if not gaps:
        return asserted or "L0-ASSUMED"
    capped_by_dimension = min(
        (
            LEVEL_RANK.get(DIMENSION_MINIMUM_LEVEL.get(gap.dimension, "L4-COMMITTED"), 4)
            for gap in gaps
        ),
        default=4,
    )
    capped = max(capped_by_dimension - 1, 0)
    return LATTICE_LEVELS[capped]


def _classify(
    baseline_id: str,
    case: Mapping[str, Any],
    policy: _ClassPolicy,
    record_bindings: Mapping[str, Mapping[str, Any]],
) -> EvidenceBoundaryVerdict:
    case_id = str(case.get("case_id", ""))
    claims = case.get("claims")
    if not isinstance(claims, Sequence) or isinstance(claims, str | bytes) or not claims:
        return EvidenceBoundaryVerdict(
            baseline_id=baseline_id,
            case_id=case_id,
            granted_level="",
            verdict="INDETERMINATE",
            reason_code=STATUS_REASON_MALFORMED_CASE,
            gaps=(),
        )

    all_gaps: list[ClaimGap] = []
    asserted_overall = "L0-ASSUMED"
    for claim in claims:
        if not isinstance(claim, Mapping):
            all_gaps.append(
                ClaimGap(
                    claim_id="?",
                    dimension="unknown",
                    gap_code="G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
                    detail="claim entry is not an object",
                )
            )
            continue
        asserted = _norm_level(claim.get("asserted_level"))
        if not asserted:
            all_gaps.append(
                ClaimGap(
                    claim_id=str(claim.get("claim_id", "")),
                    dimension=str(claim.get("dimension", "")),
                    gap_code="G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
                    detail=f"asserted_level {claim.get('asserted_level')!r} is not a lattice level",
                )
            )
            continue
        asserted_overall = max(asserted_overall, asserted, key=lambda lvl: LEVEL_RANK.get(lvl, 0))
        all_gaps.extend(_gaps_for_claim(baseline_id, claim, policy, record_bindings))

    granted = _grant_level_for_gaps(asserted_overall, all_gaps)
    verdict = "ACCEPT" if granted == asserted_overall else "REJECT"
    reason = "OK" if not all_gaps else all_gaps[0].gap_code
    return EvidenceBoundaryVerdict(
        baseline_id=baseline_id,
        case_id=case_id,
        granted_level=granted,
        verdict=verdict,
        reason_code=reason,
        gaps=tuple(all_gaps),
    )


def run_baseline(baseline_id: str, case: Mapping[str, Any], ctx: Any) -> Outcome:
    """Run one EVIDENCE-BOUNDARY reference class over one synthetic claim case.

    Contract (task manifest signature ``run_baseline(id,case,ctx)->Outcome``):
    returns a shared-harness :class:`Outcome` whose ``detail`` carries the
    structured :class:`EvidenceBoundaryVerdict` JSON. Failure semantics:

    - unknown ``baseline_id`` (not in :data:`BASELINE_IDS`, or ``ctx.arm_id``
      names an unpreregistered arm) -> ``INVALID_RESULT`` / UNKNOWN_BASELINE;
      a constant-allow stub is refused by construction because only the four
      preregistered classes ever classify.
    - malformed case / record shape -> ``INVALID_RESULT`` / MALFORMED_CASE.
    - case whose ``record_id`` is not in the synthetic fixture set ->
      ``NOT_RUN_EXTERNAL`` (upstream record unavailable; honest, retriable).
    - otherwise ACCEPT/REJECT with granted lattice level and gap list.
    """
    if baseline_id not in BASELINE_IDS:
        return _error_outcome(
            STATUS_REASON_UNKNOWN_BASELINE,
            f"baseline_id {baseline_id!r} is not a preregistered reference class",
        )
    arm_id = _resolve_arm_id(baseline_id, ctx)
    if arm_id not in BASELINE_IDS:
        return _error_outcome(
            STATUS_REASON_UNKNOWN_BASELINE,
            f"ctx arm {arm_id!r} is not a preregistered reference class",
        )
    if not isinstance(case, Mapping):
        return _error_outcome(
            STATUS_REASON_MALFORMED_CASE, f"case must be a mapping, got {type(case).__name__}"
        )
    policy = _CLASS_POLICIES[baseline_id]
    try:
        records = load_reference_records()
    except BaselineInputError as exc:
        return _unavailable_outcome(baseline_id, case, exc.detail)

    record_key = str(case.get("record_id", ""))
    variant = str(case.get("variant", ""))
    record = records.get((record_key, variant))
    if record is None:
        return _unavailable_outcome(
            baseline_id,
            case,
            f"record_id/variant {(record_key, variant)!r} not in synthetic fixture set",
        )

    record_bindings = record.get("receipts")
    if not isinstance(record_bindings, Mapping):
        record_bindings = {}
    claim_case = record.get("claims_case")
    if not isinstance(claim_case, Mapping):
        return _error_outcome(
            STATUS_REASON_MALFORMED_CASE,
            f"fixture record {(record_key, variant)!r} lacks a claims_case object",
        )
    merged_case: dict[str, Any] = dict(claim_case)
    merged_case["case_id"] = str(case.get("case_id", claim_case.get("case_id", record_key)))
    verdict = _classify(baseline_id, merged_case, policy, record_bindings)
    digest = hashlib.sha256(
        json.dumps(verdict.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    # The classification verdict (ACCEPT/REJECT) is carried in the structured
    # payload; observed_outcome uses the shared harness bucket vocabulary.
    observed = {"ACCEPT": "ADMIT", "REJECT": "REJECT"}.get(verdict.verdict, "INDETERMINATE")
    return Outcome(
        observed_outcome=observed,
        counted_as_success=verdict.verdict == "ACCEPT",
        retriable=False,
        detail=json.dumps({**verdict.to_dict(), "verdict_digest": digest}, sort_keys=True),
    )
