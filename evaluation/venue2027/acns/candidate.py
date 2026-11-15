"""CLARA-Care 2027 ACNS task ACNS-candidate — SoK evidence-boundary analysis instrument.

Purpose
-------
Task ACNS-candidate (Phase P04, venue acns) delivers the *analysis instrument*
of the SoK "Evidence Boundaries of Attestation in Tool-Using AI Systems"
(``research/venue2027/VENUES/acns/RESEARCH_BLUEPRINT.md``, RQ1-RQ3). Per the
signed novelty contract (``research/venue2027/acns/novelty_contract.md`` §1)
this study is a **SoK**: what P04 contributes is an ANALYTIC INSTRUMENT — a
deterministic classifier that reads an attestation claim record against the
evidence-to-claim lattice (threat model §1.2) and the pre-registered gap
register G1-G9 (threat model §6) — **NOT a mechanism**. No new cryptographic
primitive, authorization protocol, detector, attestation scheme, defense, or
benchmark is proposed or evaluated; nothing here enforces, prevents, or
detects anything at runtime. The instrument exists so corpus coding (RQ1),
the counterexample-witness gallery (RQ2), and reliability statistics (RQ3)
have a reproducible mechanical boundary reading of a claim record:

- :func:`classify_claim` — ``classify_claim(claim) -> BoundaryAssessment``:
  decides whether one attestation claim is (a) within a verifiable evidence
  boundary (``IN_BOUNDARY``), (b) a boundary gap — a claim whose asserted
  level is not bound by the record's evidence (``BOUNDARY_GAP``, annotated
  with the specific G-codes from the register), or (c) ``INDETERMINATE`` when
  a coding input is undecidable (retained, never coerced — rater manual §5
  IND rules).
- :func:`coverage_matrix` — ``coverage_matrix(claims) -> Coverage``:
  quantifies evidence-boundary coverage across records (in-boundary fraction,
  gap-register coverage, per-code counts, deterministic digest).
- :func:`ablation_ignore_gaps` — the ablation arm that treats every claim as
  in-boundary: the coverage matrix's gap-register coverage collapses to zero
  and the in-boundary fraction inflates to an unsound 1.0, demonstrating that
  the gap detection *is* the instrument.
- :func:`describe_mechanism` — the machine-readable declaration that this
  module is an ANALYTIC INSTRUMENT and not a mechanism.
- :func:`run_candidate` — the task-manifest adapter
  ``run_candidate(case, ctx) -> Outcome`` over the instrument.

Allowed input
-------------
``claim``: a JSON-serializable mapping describing one attestation claim
record: ``claim_id``, optional ``record_id``, ``dimension`` (``dispatch`` |
``receipt`` | ``execution`` | ``consumption``), ``asserted_level``
(``L0-ASSUMED`` .. ``L4-COMMITTED``; short forms such as ``L2`` accepted),
optional ``evidence_bindings`` list (``binding_kind`` in ``receipt-bound`` /
``attested-bound`` / ``trace-bound`` / ``log-bound`` / ``transport-ack`` /
``egress-bound`` / ``none``), and the optional fields the register reads:
``attested_execution``, ``consumption_record``,
``schedule_checked_at_rely_time``, ``timestamp``, ``trust_parties_named``,
``purpose_scope`` (``authorized_purpose`` / ``claimed_purpose``),
``purpose_binding_checked``. ``receipts`` (keyword argument or case field) is
the optional record-level receipt table used to verify that a ``receipt-bound``
artifact is bound to *this* claim (G4). All input is synthetic
(``synthetic-acns-2027`` fixtures or inline literals): no PHI/PII, no network,
no clock, no database, no live provider.

Failure semantics
-----------------
All failures are stable uppercase reason codes carried on the returned
assessment; no unhandled exception escapes :func:`classify_claim` or
:func:`run_candidate`. A non-mapping claim is ``INDETERMINATE`` /
``MALFORMED_CLAIM``; a missing or unparseable ``asserted_level`` or a missing
``dimension`` is ``INDETERMINATE`` / ``FIELD_UNDECIDABLE_*`` (retained for
adjudication, never coerced to a safe verdict — rater manual §5 IND3); a
dimension outside the lattice vocabulary is a ``G9`` boundary gap. Gap
detection is additive and register-ordered: every register row whose boundary
condition fails is reported; specific rows (G1-G6, G8) take precedence over
the residual implicit-upgrade row G7, and a context-invalid artifact (G4)
subsumes the level-upgrade rows for that artifact. When the record's receipt
table is unavailable, a declared binding is taken as declared (the instrument
never fabricates a G4 from missing verification input); with the table
available the binding is verified. ``run_candidate`` refuses unregistered arms
(``UNKNOWN_ARM``) and malformed cases (``MALFORMED_CASE``), and answers
``NOT_RUN_EXTERNAL`` (retriable, never counted as an acceptance) when the
declared synthetic fixture record cannot be located.

Version
-------
``CANDIDATE_ID = "clara.acns.candidate.evidence-boundary-sok-instrument"``,
``CANDIDATE_VERSION = "1.0.0"``. All output types are JSON-serializable via
``to_dict``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome

CANDIDATE_ID: Final[str] = "clara.acns.candidate.evidence-boundary-sok-instrument"
CANDIDATE_VERSION: Final[str] = "1.0.0"

#: Evidence-to-claim lattice (threat model §1.2). L1.5 (transport
#: acknowledgment) is a distinct evidence class, not a claim-strength upgrade
#: of L1 (rater manual §1.1); ranks are spaced so L1.5 sits between L1 and L2.
LATTICE_LEVELS: Final[tuple[str, ...]] = (
    "L0-ASSUMED",
    "L1-ASSEMBLED",
    "L1.5-TRANSPORT_ACK",
    "L2-ACKNOWLEDGED",
    "L3-EXECUTED",
    "L4-COMMITTED",
)

LEVEL_RANK: Final[dict[str, int]] = {level: rank for rank, level in enumerate(LATTICE_LEVELS)}

#: The six evidence classes of the lattice (blueprint contribution, §1).
EVIDENCE_CLASSES: Final[tuple[str, ...]] = (
    "assembly",
    "egress",
    "transport_acknowledgment",
    "provider_attested_receipt",
    "execution_trace",
    "semantic_consumption",
)

#: Claim dimensions and the minimum lattice level each requires for the claim
#: as stated to be entitled to its asserted level (baselines parity table).
DIMENSION_MINIMUM_LEVEL: Final[dict[str, str]] = {
    "dispatch": "L1-ASSEMBLED",
    "receipt": "L2-ACKNOWLEDGED",
    "execution": "L3-EXECUTED",
    "consumption": "L4-COMMITTED",
}

#: Pre-registered gap register (threat model §6, G1-G9), restated locally as
#: code -> claimed-implication so the assessment cites the exact register row.
GAP_REGISTER: Final[Mapping[str, str]] = {
    "G1_TRANSPORT_ACK_AS_PROCESSING": "transport acknowledgment => provider processed",
    "G2_RECEIPT_AS_EXECUTION": "provider receipt => model executed tool",
    "G3_EXECUTION_AS_CONSUMPTION": "execution trace => semantic consumption persisted",
    "G4_SIGNATURE_AS_CONTEXT": "signature validity => context validity (single use)",
    "G5_MINT_TIME_AS_RELY_TIME": "valid at mint => valid at rely",
    "G6_TIMESTAMP_AS_ORDERING": "timestamp presence => event ordering/proof",
    "G7_LEVEL_IMPLICIT_UPGRADE": "evidence at level Ln => all claims at Ln+1",
    "G8_AUTHORITY_SCOPE_CROSSING": "authority minted for P1 => authority for P2",
    "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE": "published claim => claim supported by paper's evidence",
}

KNOWN_GAP_CODES: Final[frozenset[str]] = frozenset(GAP_REGISTER)

#: Binding kinds that bind an artifact to THIS claim's context (nonce/digest/
#: purpose) versus artifacts that only evidence a weaker lattice level.
CONTEXT_BOUND_KINDS: Final[frozenset[str]] = frozenset({"receipt-bound", "attested-bound"})
ATTESTED_KINDS: Final[frozenset[str]] = frozenset({"attested-bound", "trace-bound"})

STATUS_IN_BOUNDARY: Final[str] = "IN_BOUNDARY"
STATUS_BOUNDARY_GAP: Final[str] = "BOUNDARY_GAP"
STATUS_INDETERMINATE: Final[str] = "INDETERMINATE"

REASON_OK: Final[str] = "OK"
REASON_MALFORMED_CLAIM: Final[str] = "MALFORMED_CLAIM"
REASON_FIELD_UNDECIDABLE_LEVEL: Final[str] = "FIELD_UNDECIDABLE_ASSERTED_LEVEL"
REASON_FIELD_UNDECIDABLE_DIMENSION: Final[str] = "FIELD_UNDECIDABLE_DIMENSION"

#: Run adapter reason codes.
STATUS_REASON_UNKNOWN_ARM = "UNKNOWN_ARM"
STATUS_REASON_MALFORMED_CASE = "MALFORMED_CASE"
STATUS_REASON_NOT_RUN_EXTERNAL = "NOT_RUN_EXTERNAL"


@dataclasses.dataclass(frozen=True)
class BoundaryAssessment:
    """JSON-serializable evidence-boundary assessment of ONE claim record.

    ``boundary_status`` is ``IN_BOUNDARY`` (claim stays within the evidence
    boundary its bound artifacts support), ``BOUNDARY_GAP`` (asserted level
    not bound by the record's evidence; see ``gap_codes``) or
    ``INDETERMINATE`` (a coding input is undecidable — retained for human
    adjudication, never coerced). ``gap_codes`` cites the pre-registered
    register rows whose boundary conditions fail; ``undecidable_fields`` names
    the fields that forced ``INDETERMINATE`` (rater manual §5 IND4).
    """

    claim_id: str
    dimension: str
    asserted_level: str
    demonstrated_level: str
    boundary_status: str
    gap_codes: tuple[str, ...]
    undecidable_fields: tuple[str, ...]
    reason_code: str = REASON_OK
    instrument_id: str = CANDIDATE_ID
    instrument_version: str = CANDIDATE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "dimension": self.dimension,
            "asserted_level": self.asserted_level,
            "demonstrated_level": self.demonstrated_level,
            "boundary_status": self.boundary_status,
            "gap_codes": list(self.gap_codes),
            "undecidable_fields": list(self.undecidable_fields),
            "reason_code": self.reason_code,
            "instrument_id": self.instrument_id,
            "instrument_version": self.instrument_version,
        }


@dataclasses.dataclass(frozen=True)
class Coverage:
    """Evidence-boundary coverage across a set of claim records.

    ``in_boundary_count`` / ``boundary_gap_count`` / ``indeterminate_count``
    partition the classified records; ``gap_register_coverage`` is the
    fraction of the nine pre-registered register rows (G1-G9) that the corpus
    actually exercises — the coverage metric the SoK reports (RQ1); the
    per-code ``gap_code_counts`` and a deterministic ``digest`` complete the
    matrix. ``ablated`` marks an :func:`ablation_ignore_gaps` run.
    """

    total_claims: int
    in_boundary_count: int
    boundary_gap_count: int
    indeterminate_count: int
    gap_register_coverage: float
    gap_code_counts: Mapping[str, int]
    instrument_id: str = CANDIDATE_ID
    instrument_version: str = CANDIDATE_VERSION
    ablated: bool = False
    digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_claims": self.total_claims,
            "in_boundary_count": self.in_boundary_count,
            "boundary_gap_count": self.boundary_gap_count,
            "indeterminate_count": self.indeterminate_count,
            "in_boundary_fraction": self.in_boundary_fraction,
            "gap_register_coverage": self.gap_register_coverage,
            "gap_code_counts": dict(self.gap_code_counts),
            "instrument_id": self.instrument_id,
            "instrument_version": self.instrument_version,
            "ablated": self.ablated,
            "digest": self.digest,
        }

    @property
    def in_boundary_fraction(self) -> float:
        if self.total_claims <= 0:
            return 0.0
        return self.in_boundary_count / self.total_claims


def _norm_level(value: Any) -> str:
    """Canonicalize a level token ('L2', 'L2-ACKNOWLEDGED', 'l1.5' all work)."""
    if not isinstance(value, str) or not value.strip():
        return ""
    token = value.strip().upper()
    for level in LATTICE_LEVELS:
        head, _, tail = level.partition("-")
        if token in (level, head, tail):
            return level
    return ""


def _str_field(claim: Mapping[str, Any], key: str) -> str:
    value = claim.get(key)
    return value.strip() if isinstance(value, str) else ""


def _bool_field(claim: Mapping[str, Any], key: str) -> bool:
    return claim.get(key) is True


def _bindings_of(claim: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    bindings = claim.get("evidence_bindings")
    if not isinstance(bindings, Sequence) or isinstance(bindings, str | bytes):
        return []
    return [binding for binding in bindings if isinstance(binding, Mapping)]


def _binding_for_dimension(
    bindings: Sequence[Mapping[str, Any]], dimension: str
) -> Mapping[str, Any] | None:
    for binding in bindings:
        if str(binding.get("dimension", "")) == dimension:
            return binding
    return None


def _receipt_supports_claim(
    receipt_id: str, claim_id: str, receipts: Mapping[str, Any] | None
) -> bool | None:
    """Verify a receipt artifact against the record's receipt table.

    Returns True (bound to this claim), False (transplanted/replayed: G4) or
    None (no receipt table available: the declared binding is taken as
    declared — the instrument never fabricates a G4 from missing input).
    """
    if receipts is None or not isinstance(receipts, Mapping):
        return None
    receipt = receipts.get(receipt_id)
    if not isinstance(receipt, Mapping):
        return False
    return receipt.get("bound_to_claim_id") == claim_id


def _detect_gaps(
    claim: Mapping[str, Any],
    dimension: str,
    asserted: str,
    bindings: Sequence[Mapping[str, Any]],
    receipts: Mapping[str, Any] | None,
) -> list[str]:
    """Run the pre-registered G1-G9 register over one classified claim.

    Additive and register-ordered: every register row whose boundary
    condition fails under the record's declared evidence is reported.
    Specific rows (G1-G6, G8) precede the residual implicit-upgrade row G7;
    a context-invalid artifact (G4) subsumes the level-upgrade rows G2/G3
    for that artifact (the transplant already explains the upgrade).
    """
    claim_id = _str_field(claim, "claim_id")
    gap_codes: list[str] = []
    binding = _binding_for_dimension(bindings, dimension)
    binding_kind = str(binding.get("binding_kind", "")) if binding is not None else ""

    # G1 — transport acknowledgment read as provider processing.
    if binding_kind == "transport-ack" and LEVEL_RANK[asserted] > LEVEL_RANK["L1.5-TRANSPORT_ACK"]:
        gap_codes.append("G1_TRANSPORT_ACK_AS_PROCESSING")

    # G4 — signature-valid, context-invalid artifact (replay/transplant).
    context_invalid = False
    if binding is not None and binding_kind in CONTEXT_BOUND_KINDS:
        receipt_id = str(binding.get("receipt_id", ""))
        support = _receipt_supports_claim(receipt_id, claim_id, receipts)
        if support is False:
            gap_codes.append("G4_SIGNATURE_AS_CONTEXT")
            context_invalid = True

    # G2 — receipt (or context-invalid artifact) quoted as execution proof.
    if (
        dimension in ("execution", "consumption")
        and LEVEL_RANK[asserted] >= LEVEL_RANK["L3-EXECUTED"]
    ):
        has_attested_anchor = _bool_field(claim, "attested_execution") or (
            binding is not None and binding_kind in ATTESTED_KINDS
        )
        if not has_attested_anchor and not (context_invalid and binding_kind == "receipt-bound"):
            gap_codes.append("G2_RECEIPT_AS_EXECUTION")

    # G3 — execution trace quoted as persisted semantic consumption.
    if dimension == "consumption" and not _bool_field(claim, "consumption_record"):
        gap_codes.append("G3_EXECUTION_AS_CONSUMPTION")

    # G5 — mint-time validity read as rely-time validity.
    if (
        binding is not None
        and binding_kind in CONTEXT_BOUND_KINDS
        and not _bool_field(claim, "schedule_checked_at_rely_time")
    ):
        gap_codes.append("G5_MINT_TIME_AS_RELY_TIME")

    # G6 — timestamp presence read as ordering/proof.
    if not _str_field(claim, "timestamp") and LEVEL_RANK[asserted] > LEVEL_RANK["L1-ASSEMBLED"]:
        gap_codes.append("G6_TIMESTAMP_AS_ORDERING")

    # G8 — authority crossing purpose/tenant scope.
    purpose_scope = claim.get("purpose_scope")
    if isinstance(purpose_scope, Mapping):
        authorized = purpose_scope.get("authorized_purpose")
        claimed = purpose_scope.get("claimed_purpose")
        checked = _bool_field(claim, "purpose_binding_checked")
        if authorized is not None and claimed is not None and authorized != claimed and not checked:
            gap_codes.append("G8_AUTHORITY_SCOPE_CROSSING")

    # G7 — residual implicit level upgrade: asserted level with NO evidence
    # binding at all on the claimed dimension (the upgrade Ln => Ln+1 has no
    # named trusted component). Reported only when no specific row already
    # explains the upgrade for this dimension.
    if binding is None and LEVEL_RANK[asserted] > LEVEL_RANK["L0-ASSUMED"] and not gap_codes:
        gap_codes.append("G7_LEVEL_IMPLICIT_UPGRADE")

    # G9 — claim outside any disclosed evidence dimension.
    if dimension not in DIMENSION_MINIMUM_LEVEL:
        gap_codes.append("G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE")

    # Register order for deterministic output.
    order = list(GAP_REGISTER)
    return sorted(set(gap_codes), key=order.index)


def classify_claim(
    claim: Mapping[str, Any], receipts: Mapping[str, Any] | None = None
) -> BoundaryAssessment:
    """Classify ONE attestation claim record against the evidence boundary.

    Deterministic and pure. Returns (a) ``IN_BOUNDARY`` when the asserted
    level is bound by the record's evidence under the lattice, (b)
    ``BOUNDARY_GAP`` with the failing G-codes when the claim exceeds its
    bound evidence, or (c) ``INDETERMINATE`` with ``undecidable_fields`` when
    a coding input (claim shape, asserted level, dimension) is undecidable —
    retained for adjudication, never coerced to a safe verdict.
    """
    if not isinstance(claim, Mapping):
        return BoundaryAssessment(
            claim_id="",
            dimension="",
            asserted_level="",
            demonstrated_level="",
            boundary_status=STATUS_INDETERMINATE,
            gap_codes=(),
            undecidable_fields=("claim",),
            reason_code=REASON_MALFORMED_CLAIM,
        )

    claim_id = _str_field(claim, "claim_id")
    asserted = _norm_level(claim.get("asserted_level"))
    dimension = _str_field(claim, "dimension")

    if not asserted:
        return BoundaryAssessment(
            claim_id=claim_id,
            dimension=dimension,
            asserted_level="",
            demonstrated_level="",
            boundary_status=STATUS_INDETERMINATE,
            gap_codes=(),
            undecidable_fields=("asserted_level",),
            reason_code=REASON_FIELD_UNDECIDABLE_LEVEL,
        )
    if not dimension:
        return BoundaryAssessment(
            claim_id=claim_id,
            dimension="",
            asserted_level=asserted,
            demonstrated_level="",
            boundary_status=STATUS_INDETERMINATE,
            gap_codes=(),
            undecidable_fields=("dimension",),
            reason_code=REASON_FIELD_UNDECIDABLE_DIMENSION,
        )

    bindings = _bindings_of(claim)
    gap_codes = _detect_gaps(claim, dimension, asserted, bindings, receipts)

    # The demonstrated level is the claimed dimension's minimum lattice level,
    # capped one level below the highest failing register row's dimension.
    demonstrated = DIMENSION_MINIMUM_LEVEL.get(dimension, "L0-ASSUMED")
    if gap_codes:
        demonstrated = min(
            demonstrated,
            LATTICE_LEVELS[max(LEVEL_RANK[asserted] - 1, 0)],
            key=lambda lvl: abs(LEVEL_RANK[lvl] - LEVEL_RANK[asserted]),
        )
        boundary_status = STATUS_BOUNDARY_GAP
    else:
        boundary_status = STATUS_IN_BOUNDARY

    return BoundaryAssessment(
        claim_id=claim_id,
        dimension=dimension,
        asserted_level=asserted,
        demonstrated_level=demonstrated,
        boundary_status=boundary_status,
        gap_codes=tuple(gap_codes),
        undecidable_fields=(),
        reason_code=REASON_OK if not gap_codes else gap_codes[0],
    )


def _claim_id_of(claim: Mapping[str, Any], index: int) -> str:
    return _str_field(claim, "claim_id") or f"claim-{index}"


def _gap_digest(gap_code_counts: Mapping[str, int], total: int, ablated: bool) -> str:
    payload = json.dumps(
        {"counts": dict(gap_code_counts), "total": total, "ablated": ablated},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def coverage_matrix(
    claims: Sequence[Mapping[str, Any]], receipts: Mapping[str, Any] | None = None
) -> Coverage:
    """Quantify evidence-boundary coverage of the instrument across records.

    Classifies every claim (undecidable claims are counted, never dropped)
    and reports the in-boundary fraction, the fraction of the pre-registered
    G1-G9 register exercised by the corpus, per-code counts, and a
    deterministic digest. ``total_claims <= 0`` yields an all-zero matrix
    rather than a fabricated fraction.
    """
    claims_seq = (
        list(claims) if isinstance(claims, Sequence) and not isinstance(claims, str | bytes) else []
    )
    counts = {code: 0 for code in GAP_REGISTER}
    in_boundary = gaps = indeterminate = 0
    for claim in claims_seq:
        if not isinstance(claim, Mapping):
            indeterminate += 1
            continue
        assessment = classify_claim(claim, receipts)
        if assessment.boundary_status == STATUS_IN_BOUNDARY:
            in_boundary += 1
        elif assessment.boundary_status == STATUS_BOUNDARY_GAP:
            gaps += 1
            for code in assessment.gap_codes:
                counts[code] = counts.get(code, 0) + 1
        else:
            indeterminate += 1
    exercised = sum(1 for count in counts.values() if count > 0)
    return Coverage(
        total_claims=len(claims_seq),
        in_boundary_count=in_boundary,
        boundary_gap_count=gaps,
        indeterminate_count=indeterminate,
        gap_register_coverage=(exercised / len(GAP_REGISTER)) if GAP_REGISTER else 0.0,
        gap_code_counts=counts,
        digest=_gap_digest(counts, len(claims_seq), False),
    )


def ablation_ignore_gaps(
    claims: Sequence[Mapping[str, Any]], receipts: Mapping[str, Any] | None = None
) -> Coverage:
    """Ablation arm: treat EVERY claim as in-boundary.

    Identical accounting to :func:`coverage_matrix` except gap detection is
    switched off — every claim is accepted at face value. The returned
    matrix's gap-register coverage collapses to 0.0 and the in-boundary
    fraction inflates to 1.0 on any corpus: the measurable proof that the gap
    detection, not the accounting, is the instrument. Flagged ``ablated`` so
    an ablated matrix can never be presented as a real coverage result.
    """
    claims_seq = (
        list(claims) if isinstance(claims, Sequence) and not isinstance(claims, str | bytes) else []
    )
    counts = {code: 0 for code in GAP_REGISTER}
    return Coverage(
        total_claims=len(claims_seq),
        in_boundary_count=len(claims_seq),
        boundary_gap_count=0,
        indeterminate_count=0,
        gap_register_coverage=0.0,
        gap_code_counts=counts,
        ablated=True,
        digest=_gap_digest(counts, len(claims_seq), True),
    )


def describe_mechanism() -> dict[str, Any]:
    """Machine-readable contribution-class declaration for this module.

    Contribution class: ANALYTIC INSTRUMENT (SoK evidence-boundary analysis),
    NOT a mechanism. This is the novelty-contract §1 declaration in
    machine-checkable form: nothing here enforces, prevents, detects, or
    attests anything at runtime; the module reads claim records against the
    pre-registered lattice and gap register and emits codable assessments.
    """
    return {
        "candidate_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "contribution_class": "ANALYTIC_INSTRUMENT",
        "is_mechanism": False,
        "is_new_mechanism_claim": False,
        "study_class": "SoK",
        "task_id": "ACNS-candidate",
        "paper": "SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems",
        "novelty_contract": "research/venue2027/acns/novelty_contract.md#1",
        "declaration": (
            "ANALYTIC INSTRUMENT, not a mechanism: a deterministic classifier "
            "that reads attestation claim records against the evidence-to-claim "
            "lattice (threat model section 1.2) and the pre-registered gap "
            "register G1-G9 (threat model section 6). It enforces nothing, "
            "prevents nothing, detects nothing at runtime, and proposes no new "
            "cryptographic primitive, protocol, detector, attestation scheme, "
            "defense, or benchmark."
        ),
        "gates_enforced": [],
        "runtime_enforcement": False,
        "detects_attacks": False,
        "prevents_attacks": False,
        "registers_used": {
            "lattice_levels": list(LATTICE_LEVELS),
            "gap_register": dict(GAP_REGISTER),
        },
        "dataset": "synthetic-acns-2027",
        "interfaces": {
            "classify_claim": "classify_claim(claim, receipts=None) -> BoundaryAssessment",
            "coverage_matrix": "coverage_matrix(claims, receipts=None) -> Coverage",
            "ablation_ignore_gaps": "ablation_ignore_gaps(claims, receipts=None) -> Coverage",
            "run_candidate": "run_candidate(case, ctx) -> Outcome",
        },
    }


def _load_fixture_records() -> dict[tuple[str, str], dict[str, Any]]:
    """Import the synthetic fixture records keyed by (record_id, variant)."""
    from evaluation.venue2027.acns import _smoke_fixtures

    records = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS
    if not isinstance(records, Mapping) or not records:
        raise ValueError("FIXTURE_RECORDS_UNAVAILABLE: synthetic claim records missing or empty")
    return {key: dict(value) for key, value in records.items()}


def _error_outcome(reason_code: str, detail: str) -> Outcome:
    return Outcome(
        observed_outcome="INVALID_RESULT",
        counted_as_success=False,
        retriable=False,
        detail=f"{reason_code}: {detail}",
    )


def _unavailable_outcome(case_id: str, detail: str) -> Outcome:
    return Outcome(
        observed_outcome="NOT_RUN_EXTERNAL",
        counted_as_success=False,
        retriable=True,
        detail=f"{STATUS_REASON_NOT_RUN_EXTERNAL}: case {case_id!r} | {detail}",
    )


def run_candidate(case: Mapping[str, Any], ctx: Mapping[str, Any] | None = None) -> Outcome:
    """Run the evidence-boundary instrument over one synthetic claim case.

    Contract (task manifest signature ``run_candidate(case,ctx)->Outcome``):
    returns a shared-harness :class:`Outcome` whose ``detail`` carries the
    per-claim :class:`BoundaryAssessment` JSON plus the case-level
    :class:`Coverage` matrix. Failure semantics:

    - ``ctx.arm_id`` naming an unregistered arm -> ``INVALID_RESULT`` /
      UNKNOWN_ARM (a constant-allow stub can never masquerade as an arm).
    - malformed case -> ``INVALID_RESULT`` / MALFORMED_CASE.
    - case whose ``(record_id, variant)`` is not in the synthetic fixture set
      -> ``NOT_RUN_EXTERNAL`` (honest, retriable, never counted as success).
    - otherwise ``ADMIT`` (case fully in-boundary) or ``REJECT`` (boundary
      gap detected) with the structured evidence-boundary reading attached.
    """
    ctx = ctx if isinstance(ctx, Mapping) else {}
    arm_id = str(ctx.get("arm_id", "") or CANDIDATE_ID)
    if arm_id not in (CANDIDATE_ID, "ACNS-candidate", "candidate"):
        return _error_outcome(
            STATUS_REASON_UNKNOWN_ARM,
            f"ctx arm {arm_id!r} is not a preregistered instrument arm",
        )
    if not isinstance(case, Mapping):
        return _error_outcome(
            STATUS_REASON_MALFORMED_CASE, f"case must be a mapping, got {type(case).__name__}"
        )
    case_id = str(case.get("case_id", ""))
    record_key = (str(case.get("record_id", "")), str(case.get("variant", "")))
    try:
        records = _load_fixture_records()
    except ValueError as exc:
        return _unavailable_outcome(case_id, str(exc))
    record = records.get(record_key)
    if record is None:
        return _unavailable_outcome(
            case_id, f"record_id/variant {record_key!r} not in synthetic fixture set"
        )

    claim_case = record.get("claims_case")
    receipts = record.get("receipts")
    claims = claim_case.get("claims") if isinstance(claim_case, Mapping) else None
    if not isinstance(claims, Sequence) or isinstance(claims, str | bytes) or not claims:
        return _error_outcome(
            STATUS_REASON_MALFORMED_CASE,
            f"fixture record {record_key!r} lacks a claims list",
        )
    receipts_table = receipts if isinstance(receipts, Mapping) else None

    assessments = [
        classify_claim(claim, receipts_table) for claim in claims if isinstance(claim, Mapping)
    ]
    coverage = coverage_matrix(claims, receipts_table)
    in_boundary = all(a.boundary_status == STATUS_IN_BOUNDARY for a in assessments) and bool(
        assessments
    )
    payload = {
        "instrument_id": CANDIDATE_ID,
        "instrument_version": CANDIDATE_VERSION,
        "case_id": case_id,
        "record_id": record_key[0],
        "variant": record_key[1],
        "assessments": [a.to_dict() for a in assessments],
        "coverage": coverage.to_dict(),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    payload["verdict_digest"] = digest
    return Outcome(
        observed_outcome="ADMIT" if in_boundary else "REJECT",
        counted_as_success=in_boundary,
        retriable=False,
        detail=json.dumps(payload, sort_keys=True),
    )
