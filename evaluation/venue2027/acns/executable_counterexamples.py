"""ACNS-X07_witness_gallery — runnable evidence-boundary counterexample witnesses (SoK, RQ2).

Purpose
-------
Task ACNS-X07_witness_gallery (Phase P04, venue acns) delivers the *witness
gallery* of the SoK "Evidence Boundaries of Attestation in Tool-Using AI
Systems" (``research/venue2027/VENUES/acns/RESEARCH_BLUEPRINT.md``, RQ2): a
registry of small, runnable, minimal counterexample tests — one per
evidence-boundary gap on the tool-dispatch path — each demonstrating that a
claimed implication pair FAILS when the concrete missing proof is absent, and
naming that missing proof exactly. Per the signed novelty contract this is a
SoK instrument: witnesses are *instruments of falsification for implication
pairs*, never deployable enforcement, and no mechanism is proposed. The five
mandated witnesses (task procedure, taxonomy nodes N1-N5, threat model §6
register G1-G9):

- ``assembled-not-sent``          — payload assembled (N1) but never dispatched;
  the "dispatched" claim floats with no transport event (gap G7, A4+A2
  evidence theater / egress suppression).
- ``dispatched-not-acknowledged`` — transport ACK observed (N2) but no
  provider-signed receipt; "the provider received/processed" is unsupported
  (gap G1, A1; taxonomy edge E03 invalid).
- ``acknowledged-not-executed``   — verified receipt (N3) but no TEE-attested
  execution anchor; "the model executed the tool" is capped at L2
  (gap G2, A4+A3; edge E04 invalid).
- ``executed-not-committed``      — attested execution (N4) but no persisted
  side-effect record; "committed" is unsupported (gap G3, A4; edge E05).
- ``signed-receipt-wrong-context`` — a signature-valid receipt bound to
  another request is presented for THIS request (gap G4, A5; threat model §2
  replay row: signature validity is not context validity).

Core contract
-------------
- :func:`run_counterexample` — ``run_counterexample(level_transition, case=None)
  -> ProofArtifact`` (the task-manifest signature; ``case`` is optional and
  defaults to the frozen gallery fixture). It *certifies counterexamples*: if
  the supplied case's evidence actually demonstrates the asserted level, the
  case is refused with ``NOT_A_COUNTEREXAMPLE`` — a supported claim is never
  passed off as a counterexample.
- :func:`evaluate_claim_case` — ``evaluate_claim_case(case) -> ProofArtifact``:
  the open, honest evaluation used for repaired cases; returns ADMIT when the
  evidence demonstrates the asserted level, REJECT with the gap code and the
  concrete missing proof otherwise.
- :func:`run_witness` — ``run_witness(name) -> ProofArtifact`` over the
  :data:`WITNESS_GALLERY` registry (one frozen fixture per gap).
- :func:`emit_witness_gallery` — writes
  ``artifacts/venue2027/acns/<run_id>/witness_gallery.json`` with every
  witness artifact, its frozen expected label, the label-reproduction report
  and input/output SHA256 digests. Deterministic: no clock, no randomness.

Allowed input
-------------
``case``: a JSON-serializable mapping with ``transition`` (registry id or
level-pair alias), ``claim`` (``asserted_level`` on the six-level lattice plus
a request ``context``), ``capability`` (adversarial model declaration from the
registered unprivileged/semi-trusted axes A1-A7 of threat model §1.1) and
``evidence`` (list of typed evidence items classified by the five taxonomy
node classes). All input is synthetic (``synthetic-acns-2027``): no PHI/PII,
no network, no database, no clock, no randomness, no live provider, no LLM.

Failure semantics (stable reason codes)
---------------------------------------
:class:`WitnessError` carries one stable uppercase ``reason_code``; no
unhandled exception escapes and no INDETERMINATE/incomplete outcome is ever
counted as a safe rejection or a completion:

- ``UNKNOWN_TRANSITION`` / ``UNKNOWN_WITNESS`` — unregistered transition or
  gallery name; refused, never defaulted.
- ``NOT_A_COUNTEREXAMPLE`` — the supplied evidence demonstrates the asserted
  level, so there is nothing to counter; the runner refuses to certify it.
- ``PRIVILEGED_ATTACKER`` — the declared capability is outside the registered
  A1-A7 axes (hardware-root or primitive-break attackers are out of scope per
  threat model ED1/ED2): a witness relying on a privileged unrealistic
  attacker is refused, not scored.
- ``MALFORMED_CASE`` / ``MALFORMED_EVIDENCE`` — malformed claim, evidence list
  or field types; fail closed.
- ``TRANSITION_MISMATCH`` — the case's declared transition disagrees with the
  requested one.
- ``MALFORMED_RUN_ID`` / ``GALLERY_DRIFT`` / ``OUTCOME_BUCKET_DRIFT`` —
  emission and consistency fail-closed guards.

Evidence-boundary semantics (the verifier)
------------------------------------------
Each evidence item supports exactly the level of its taxonomy node class
(sender_known_bytes→ASSEMBLED, transport_delivery→DISPATCHED,
provider_signed_receipt→ACKNOWLEDGED, execution→EXECUTED,
persisted_side_effect→COMMITTED), degraded fail-closed by boundary checks:
unverifiable artifacts prove nothing (TC1: unpinned → L0); a receipt without
an upstream-verifiable signature chain, an execution item without
``attested_execution`` (TC3: absent TEE, execution claims cap at L2), or a
side-effect record without persistence and lineage all degrade. Context
fields (request/nonce/tenant/purpose) that disagree with the claim's context,
or a receipt digest unbound to the dispatched bytes, raise the G4
signature-as-context refusal and cap that item's support at DISPATCHED. The
demonstrated level is the strongest surviving support; a claim is ADMITted
only at or below it — never above (the lattice cap).

Version
-------
``WITNESS_GALLERY_VERSION = "1.0.0"``, contract
``clara.venue2027.acns.witness-gallery.v1``. All outputs are JSON-serializable
via :meth:`ProofArtifact.to_dict`.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared.harness import OUTCOME_BUCKETS

WITNESS_GALLERY_VERSION: Final[str] = "1.0.0"
CONTRACT_ID: Final[str] = "clara.venue2027.acns.witness-gallery.v1"
SCHEMA_VERSION: Final[str] = "1"
DEFAULT_RUN_ID: Final[str] = "acns-x07-witness-gallery-1.0.0"
FIXTURE_DATASET: Final[str] = "synthetic-acns-2027"
BACKEND: Final[str] = "pure-function-reference"

_MODULE_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: Six-level evidence-to-claim lattice (threat model §1.2; taxonomy lattice
#: ASSUMED..COMMITTED with the transport-acknowledgment rung L1.5).
LATTICE_LEVELS: Final[tuple[str, ...]] = (
    "L0-ASSUMED",
    "L1-ASSEMBLED",
    "L1.5-DISPATCHED",
    "L2-ACKNOWLEDGED",
    "L3-EXECUTED",
    "L4-COMMITTED",
)
LEVEL_RANK: Final[dict[str, int]] = {level: rank for rank, level in enumerate(LATTICE_LEVELS)}

_LEVEL_TOKENS: Final[dict[str, str]] = {}
for _level in LATTICE_LEVELS:
    _short, _name = _level.split("-", 1)
    _LEVEL_TOKENS[_level.upper()] = _level
    _LEVEL_TOKENS[_name] = _level
    _LEVEL_TOKENS[_short] = _level

#: The five taxonomy node classes (evidence_taxonomy.yaml) and the lattice
#: level each class supports when its own boundary checks pass.
NODE_CLASS_SUPPORT: Final[Mapping[str, str]] = {
    "sender_known_bytes": "L1-ASSEMBLED",
    "transport_delivery": "L1.5-DISPATCHED",
    "provider_signed_receipt": "L2-ACKNOWLEDGED",
    "execution": "L3-EXECUTED",
    "persisted_side_effect": "L4-COMMITTED",
}

#: Gap-register codes used by the gallery (threat model §6 G1-G9; restated
#: locally, never imported from a candidate module).
GAP_NONE: Final[str] = "none"
G1_TRANSPORT_ACK_AS_PROCESSING: Final[str] = "G1_TRANSPORT_ACK_AS_PROCESSING"
G2_RECEIPT_AS_EXECUTION: Final[str] = "G2_RECEIPT_AS_EXECUTION"
G3_EXECUTION_AS_CONSUMPTION: Final[str] = "G3_EXECUTION_AS_CONSUMPTION"
G4_SIGNATURE_AS_CONTEXT: Final[str] = "G4_SIGNATURE_AS_CONTEXT"
G7_LEVEL_IMPLICIT_UPGRADE: Final[str] = "G7_LEVEL_IMPLICIT_UPGRADE"

#: Registered attacker/observer capability axes (threat model §1.1). Anything
#: outside them is a privileged unrealistic attacker (ED1/ED2) and is refused.
REGISTERED_CAPABILITIES: Final[frozenset[str]] = frozenset({f"A{i}" for i in range(1, 8)})

VERDICT_ADMIT: Final[str] = "ADMIT"
VERDICT_REJECT: Final[str] = "REJECT"

G4_MISSING_PROOF: Final[str] = (
    "a receipt whose bound nonce, digest, purpose and tenant fields match THIS "
    "request's context, with the TC2 anti-replay binding check passing at "
    "verification time; the presented receipt is bound to a different request"
)

# Synthetic digest fixtures (64-hex content digests; synthetic-acns-2027).
_D1: Final[str] = "sha256:" + "11" * 32
_D2: Final[str] = "sha256:" + "22" * 32
_D3: Final[str] = "sha256:" + "33" * 32
_D4: Final[str] = "sha256:" + "44" * 32
_D5A: Final[str] = "sha256:" + "5a" * 32
_D5B: Final[str] = "sha256:" + "5b" * 32

_CTX_W1: Final[Mapping[str, str]] = {
    "request_id": "req-w1",
    "nonce": "nonce-w1",
    "tenant": "tenant-demo",
    "purpose": "self-care",
}
_CTX_W2: Final[Mapping[str, str]] = {
    "request_id": "req-w2",
    "nonce": "nonce-w2",
    "tenant": "tenant-demo",
    "purpose": "self-care",
}
_CTX_W3: Final[Mapping[str, str]] = {
    "request_id": "req-w3",
    "nonce": "nonce-w3",
    "tenant": "tenant-demo",
    "purpose": "self-care",
}
_CTX_W4: Final[Mapping[str, str]] = {
    "request_id": "req-w4",
    "nonce": "nonce-w4",
    "tenant": "tenant-demo",
    "purpose": "self-care",
}
_CTX_W5: Final[Mapping[str, str]] = {
    "request_id": "req-w5",
    "nonce": "nonce-w5",
    "tenant": "tenant-demo",
    "purpose": "self-care",
}


class WitnessError(Exception):
    """Fail-closed refusal carrying a stable uppercase ``reason_code``."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class TransitionRule:
    """One evidence-boundary transition: the implication under attack."""

    transition_id: str
    from_level: str
    to_level: str
    gap_code: str
    claim_text: str
    missing_proof: str
    trust_assumptions: str
    capability: str
    failure_family: str
    edge_ref: str


_TRANSITIONS: Final[dict[str, TransitionRule]] = {
    "assembled-not-sent": TransitionRule(
        transition_id="assembled-not-sent",
        from_level="L1-ASSEMBLED",
        to_level="L1.5-DISPATCHED",
        gap_code=G7_LEVEL_IMPLICIT_UPGRADE,
        claim_text="the assembled payload bytes were dispatched to the provider",
        missing_proof=(
            "a sender-side transport-stack dispatch observation binding the "
            "assembled digest to an observed send (taxonomy node N2_DISPATCHED, "
            "class transport_delivery); the bytes never left the host, so no "
            "external witness of egress exists"
        ),
        trust_assumptions=(
            "taxonomy edge E02 holds only under trust in the sender-side "
            "transport stack reporting its own socket events honestly; the "
            "witness removes even that: egress is suppressed under A2, no "
            "transport event exists, and per RFC 9334 no Attester has produced "
            "Evidence above the sender-known-bytes class"
        ),
        capability="A4+A2",
        failure_family="model_agency",
        edge_ref="E02_assembled_to_dispatched",
    ),
    "dispatched-not-acknowledged": TransitionRule(
        transition_id="dispatched-not-acknowledged",
        from_level="L1.5-DISPATCHED",
        to_level="L2-ACKNOWLEDGED",
        gap_code=G1_TRANSPORT_ACK_AS_PROCESSING,
        claim_text="the provider received and processed the dispatched bytes",
        missing_proof=(
            "a provider-signed receipt for the dispatched digest, verifiable "
            "offline against pinned receipt-verification roots (TC1) through "
            "the deterministic fail-closed TC2 chain with a verification-time "
            "schedule check"
        ),
        trust_assumptions=(
            "would require provider-side signing anchored in pinned roots "
            "(TC1), the TC2 verification chain and bounded issuance honesty "
            "(TC4); a bare transport acknowledgment is observed sender-side "
            "only, binds no context, and is not RFC 9334 Evidence (edge E03 "
            "invalid, gap G1)"
        ),
        capability="A1",
        failure_family="replay",
        edge_ref="E03_transport_ack_to_receipt",
    ),
    "acknowledged-not-executed": TransitionRule(
        transition_id="acknowledged-not-executed",
        from_level="L2-ACKNOWLEDGED",
        to_level="L3-EXECUTED",
        gap_code=G2_RECEIPT_AS_EXECUTION,
        claim_text="the model executed the tool on the received request",
        missing_proof=(
            "a TEE-attested execution anchor (TC3) covering the exact tool "
            "binary and measured input, appraised against pinned attestation "
            "roots (TC1)"
        ),
        trust_assumptions=(
            "would require trusted-execution attestation of the exact binary "
            "and measured inputs (TC3) anchored in pinned roots (TC1); a "
            "receipt attests receipt semantics only (TC4) and under model "
            "agency A4 the agent may divert work after receipt (edge E04 "
            "invalid, gap G2: the receipt alone caps the claim at L2 forever)"
        ),
        capability="A4+A3",
        failure_family="model_agency",
        edge_ref="E04_receipt_to_execution",
    ),
    "executed-not-committed": TransitionRule(
        transition_id="executed-not-committed",
        from_level="L3-EXECUTED",
        to_level="L4-COMMITTED",
        gap_code=G3_EXECUTION_AS_CONSUMPTION,
        claim_text="the requested side effect was durably committed",
        missing_proof=(
            "the persisting service's own verified durable record of the side "
            "effect with lineage attribution (W3C PROV wasGeneratedBy; "
            "optionally RFC 9162-style inclusion proof)"
        ),
        trust_assumptions=(
            "would require the persisting service's own tamper-evident record "
            "with lineage attribution; execution evidence ends at the trusted "
            "boundary and implies nothing downstream of it (edge E05 invalid, "
            "gap G3)"
        ),
        capability="A4",
        failure_family="model_agency",
        edge_ref="E05_execution_to_committed",
    ),
    "signed-receipt-wrong-context": TransitionRule(
        transition_id="signed-receipt-wrong-context",
        from_level="L2-ACKNOWLEDGED",
        to_level="L2-ACKNOWLEDGED",
        gap_code=G4_SIGNATURE_AS_CONTEXT,
        claim_text="the presented receipt proves THIS request in THIS context",
        missing_proof=G4_MISSING_PROOF,
        trust_assumptions=(
            "signature validity is verified under pinned roots (TC1/TC2), but "
            "context validity requires the nonce+digest+purpose/tenant binding "
            "of the receipt to THIS request checked at verification time "
            "(TC2 anti-replay chain); the presented receipt is bound to "
            "another request (threat model §2 replay row, capability A5)"
        ),
        capability="A5",
        failure_family="replay",
        edge_ref="threat_model §2 replay row (G4)",
    ),
}

_TRANSITION_ALIASES: Final[Mapping[str, str]] = {
    "ASSEMBLED->DISPATCHED": "assembled-not-sent",
    "DISPATCHED->ACKNOWLEDGED": "dispatched-not-acknowledged",
    "ACKNOWLEDGED->EXECUTED": "acknowledged-not-executed",
    "EXECUTED->COMMITTED": "executed-not-committed",
    "ACKNOWLEDGED@WRONG-CONTEXT": "signed-receipt-wrong-context",
}


@dataclasses.dataclass(frozen=True)
class EvidenceItem:
    """One typed evidence item classified by a taxonomy node class."""

    evidence_id: str
    node_class: str
    verifiable: bool = True
    context: Mapping[str, str] = dataclasses.field(default_factory=dict)
    digest_binding: str = ""
    attested_execution: bool = False
    persisted: bool = False
    lineage_recorded: bool = False


@dataclasses.dataclass(frozen=True)
class AttestationClaim:
    """The claim under attack: an asserted lattice level plus request context."""

    claim_id: str
    asserted_level: str
    context: Mapping[str, str]


@dataclasses.dataclass(frozen=True)
class ProofArtifact:
    """JSON-serializable evidence-boundary verdict for one witness run.

    ``verdict`` is REJECT (the claimed implication fails; ``gap_code`` names
    the pre-registered register entry and ``missing_proof`` is the concrete
    missing component) or ADMIT (the evidence demonstrates the asserted
    level). ``observed_outcome`` carries the shared harness bucket vocabulary.
    """

    witness_id: str
    case_id: str
    transition_id: str
    edge_ref: str
    claimed_transition: str
    claim_text: str
    asserted_level: str
    demonstrated_level: str
    verdict: str
    observed_outcome: str
    gap_code: str
    missing_proof: str
    capability: str
    failure_family: str
    trust_assumptions: str
    context_binding: str
    observed_evidence: tuple[dict[str, Any], ...]
    witness_version: str = WITNESS_GALLERY_VERSION
    schema_version: str = SCHEMA_VERSION
    contract_id: str = CONTRACT_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "witness_id": self.witness_id,
            "case_id": self.case_id,
            "transition_id": self.transition_id,
            "edge_ref": self.edge_ref,
            "claimed_transition": self.claimed_transition,
            "claim_text": self.claim_text,
            "asserted_level": self.asserted_level,
            "demonstrated_level": self.demonstrated_level,
            "verdict": self.verdict,
            "observed_outcome": self.observed_outcome,
            "gap_code": self.gap_code,
            "missing_proof": self.missing_proof,
            "capability": self.capability,
            "failure_family": self.failure_family,
            "trust_assumptions": self.trust_assumptions,
            "context_binding": self.context_binding,
            "observed_evidence": [dict(item) for item in self.observed_evidence],
            "witness_version": self.witness_version,
            "schema_version": self.schema_version,
            "contract_id": self.contract_id,
        }


@dataclasses.dataclass(frozen=True)
class WitnessSpec:
    """One frozen gallery witness: fixture + expected evidence-boundary label.

    ``expected_verdict``/``expected_gap_code`` are design-time labels frozen
    before execution (TC5/TC6); a witness that fails to reproduce its label is
    reported as a negative result and the label is never repaired to match.
    """

    witness_id: str
    transition_id: str
    title: str
    expected_verdict: str
    expected_gap_code: str
    expected_demonstrated_level: str
    capability: str
    fixture: Mapping[str, Any]


# ---------------------------------------------------------------------------
# Frozen gallery fixtures (synthetic-acns-2027; no PHI/PII, literal data).
# Each fixture = one claim asserting a level + the evidence actually held.
# ---------------------------------------------------------------------------
def _claim(claim_id: str, asserted: str, ctx: Mapping[str, str]) -> dict[str, Any]:
    return {"claim_id": claim_id, "asserted_level": asserted, "context": dict(ctx)}


_W1_ASSEMBLED = {
    "evidence_id": "ev-w1-buffer",
    "node_class": "sender_known_bytes",
    "verifiable": True,
    "context": dict(_CTX_W1),
    "digest_binding": _D1,
}

_W2_ACK = {"evidence_id": "ev-w2-ack", "node_class": "transport_delivery", "context": dict(_CTX_W2)}

_W3_RECEIPT = {
    "evidence_id": "ev-w3-receipt",
    "node_class": "provider_signed_receipt",
    "verifiable": True,
    "context": dict(_CTX_W3),
    "digest_binding": _D3,
}

_W4_EXEC = {
    "evidence_id": "ev-w4-exec",
    "node_class": "execution",
    "verifiable": True,
    "context": dict(_CTX_W4),
    "digest_binding": _D4,
    "attested_execution": True,
}

_W5A_FOREIGN_RECEIPT = {
    "evidence_id": "ev-w5-foreign-receipt",
    "node_class": "provider_signed_receipt",
    "verifiable": True,
    "context": dict(_CTX_W1),
    "digest_binding": _D5A,
}
_W5B_DISPATCH = {
    "evidence_id": "ev-w5-dispatch",
    "node_class": "transport_delivery",
    "context": dict(_CTX_W5),
    "digest_binding": _D5B,
}


def _fixture(
    transition: str,
    claim_id: str,
    asserted: str,
    ctx: Mapping[str, str],
    capability: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "transition": transition,
        "claim": _claim(claim_id, asserted, ctx),
        "capability": capability,
        "evidence": evidence,
    }


_FROZEN_FIXTURES: Final[dict[str, dict[str, Any]]] = {
    "assembled-not-sent": _fixture(
        "assembled-not-sent",
        "claim-w1-dispatch",
        "L1.5-DISPATCHED",
        _CTX_W1,
        "A4+A2",
        [_W1_ASSEMBLED],
    ),
    "dispatched-not-acknowledged": _fixture(
        "dispatched-not-acknowledged",
        "claim-w2-receipt",
        "L2-ACKNOWLEDGED",
        _CTX_W2,
        "A1",
        [_W2_ACK],
    ),
    "acknowledged-not-executed": _fixture(
        "acknowledged-not-executed",
        "claim-w3-execution",
        "L3-EXECUTED",
        _CTX_W3,
        "A4+A3",
        [_W3_RECEIPT],
    ),
    "executed-not-committed": _fixture(
        "executed-not-committed",
        "claim-w4-commit",
        "L4-COMMITTED",
        _CTX_W4,
        "A4",
        [_W4_EXEC],
    ),
    "signed-receipt-wrong-context": _fixture(
        "signed-receipt-wrong-context",
        "claim-w5-context",
        "L2-ACKNOWLEDGED",
        _CTX_W5,
        "A5",
        [_W5A_FOREIGN_RECEIPT, _W5B_DISPATCH],
    ),
}


def _build_gallery() -> dict[str, WitnessSpec]:
    expected = {
        "assembled-not-sent": ("REJECT", G7_LEVEL_IMPLICIT_UPGRADE, "L1-ASSEMBLED"),
        "dispatched-not-acknowledged": (
            "REJECT",
            G1_TRANSPORT_ACK_AS_PROCESSING,
            "L1.5-DISPATCHED",
        ),
        "acknowledged-not-executed": ("REJECT", G2_RECEIPT_AS_EXECUTION, "L2-ACKNOWLEDGED"),
        "executed-not-committed": ("REJECT", G3_EXECUTION_AS_CONSUMPTION, "L3-EXECUTED"),
        "signed-receipt-wrong-context": ("REJECT", G4_SIGNATURE_AS_CONTEXT, "L1.5-DISPATCHED"),
    }
    titles = {
        "assembled-not-sent": "assembled bytes asserted as dispatched",
        "dispatched-not-acknowledged": "transport ACK asserted as provider receipt",
        "acknowledged-not-executed": "provider receipt asserted as tool execution",
        "executed-not-committed": "attested execution asserted as durable side effect",
        "signed-receipt-wrong-context": "signature-valid receipt presented in the wrong context",
    }
    gallery: dict[str, WitnessSpec] = {}
    for tid, rule in _TRANSITIONS.items():
        verdict, gap, level = expected[tid]
        gallery[tid] = WitnessSpec(
            witness_id=f"ACNS-X07-{tid}",
            transition_id=tid,
            title=titles[tid],
            expected_verdict=verdict,
            expected_gap_code=gap,
            expected_demonstrated_level=level,
            capability=rule.capability,
            fixture=_FROZEN_FIXTURES[tid],
        )
    return gallery


#: The witness gallery registry: exactly one frozen witness per evidence-boundary
#: gap. ``run_witness(name)`` resolves names against this registry.
WITNESS_GALLERY: Final[Mapping[str, WitnessSpec]] = _build_gallery()

WITNESS_IDS: Final[tuple[str, ...]] = tuple(WITNESS_GALLERY)


def _canonical_digest(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _normalize_level(value: Any) -> str:
    """Canonicalize a level token (accepts L2 / L2-ACKNOWLEDGED / ACKNOWLEDGED)."""
    if not isinstance(value, str) or not value.strip():
        return ""
    return _LEVEL_TOKENS.get(value.strip().upper(), "")


def _resolve_transition(level_transition: Any) -> TransitionRule:
    if isinstance(level_transition, TransitionRule):
        return level_transition
    if not isinstance(level_transition, str) or not level_transition.strip():
        raise WitnessError(
            "UNKNOWN_TRANSITION",
            f"level_transition must be a registry id or alias, got {level_transition!r}",
        )
    token = level_transition.strip()
    if token in _TRANSITIONS:
        return _TRANSITIONS[token]
    alias_key = token.upper().replace(" ", "")
    if alias_key in _TRANSITION_ALIASES:
        return _TRANSITIONS[_TRANSITION_ALIASES[alias_key]]
    collapsed = re.sub(r"[_\s]+", "-", token.lower())
    if collapsed in _TRANSITIONS:
        return _TRANSITIONS[collapsed]
    raise WitnessError(
        "UNKNOWN_TRANSITION",
        f"level_transition {level_transition!r} is not a registered gallery transition",
    )


def _parse_claim(raw: Any) -> AttestationClaim:
    if not isinstance(raw, Mapping):
        raise WitnessError("MALFORMED_CASE", f"claim must be a mapping, got {type(raw).__name__}")
    claim_id = str(raw.get("claim_id", ""))
    asserted = _normalize_level(raw.get("asserted_level"))
    context = raw.get("context")
    if not claim_id:
        raise WitnessError("MALFORMED_CASE", "claim.claim_id is required")
    if not asserted:
        raise WitnessError(
            "MALFORMED_CASE",
            f"claim.asserted_level {raw.get('asserted_level')!r} is not a lattice level",
        )
    if not isinstance(context, Mapping):
        raise WitnessError("MALFORMED_CASE", "claim.context must be a mapping of context fields")
    ctx: dict[str, str] = {str(k): str(v) for k, v in context.items()}
    return AttestationClaim(claim_id=claim_id, asserted_level=asserted, context=ctx)


def _parse_evidence_item(raw: Any, position: int) -> EvidenceItem:
    if not isinstance(raw, Mapping):
        raise WitnessError(
            "MALFORMED_EVIDENCE", f"evidence[{position}] is not a mapping ({type(raw).__name__})"
        )
    node_class = str(raw.get("node_class", ""))
    if node_class not in NODE_CLASS_SUPPORT:
        raise WitnessError(
            "MALFORMED_EVIDENCE",
            f"evidence[{position}].node_class {node_class!r} is not a taxonomy node class",
        )
    context = raw.get("context")
    ctx: dict[str, str] = {}
    if context is not None:
        if not isinstance(context, Mapping):
            raise WitnessError(
                "MALFORMED_EVIDENCE", f"evidence[{position}].context must be a mapping"
            )
        ctx = {str(k): str(v) for k, v in context.items()}
    digest = raw.get("digest_binding", "")
    if digest is not None and not isinstance(digest, str):
        raise WitnessError("MALFORMED_EVIDENCE", f"evidence[{position}].digest_binding must be str")
    verifiable = raw.get("verifiable", True)
    attested = raw.get("attested_execution", False)
    persisted = raw.get("persisted", False)
    lineage = raw.get("lineage_recorded", False)
    for flag, name in (
        (verifiable, "verifiable"),
        (attested, "attested_execution"),
        (persisted, "persisted"),
        (lineage, "lineage_recorded"),
    ):
        if not isinstance(flag, bool):
            raise WitnessError("MALFORMED_EVIDENCE", f"evidence[{position}].{name} must be boolean")
    return EvidenceItem(
        evidence_id=str(raw.get("evidence_id", f"evidence-{position:03d}")),
        node_class=node_class,
        verifiable=verifiable,
        context=ctx,
        digest_binding=digest,
        attested_execution=attested,
        persisted=persisted,
        lineage_recorded=lineage,
    )


def _parse_case(
    case: Mapping[str, Any], rule: TransitionRule
) -> tuple[AttestationClaim, str, list[EvidenceItem]]:
    if not isinstance(case, Mapping):
        raise WitnessError("MALFORMED_CASE", f"case must be a mapping, got {type(case).__name__}")
    declared = case.get("transition", rule.transition_id)
    declared_rule = _resolve_transition(declared)
    if declared_rule.transition_id != rule.transition_id:
        raise WitnessError(
            "TRANSITION_MISMATCH",
            f"case declares transition {declared_rule.transition_id!r} but the runner was "
            f"asked for {rule.transition_id!r}",
        )
    capability = str(case.get("capability", ""))
    if not capability:
        raise WitnessError("MALFORMED_CASE", "case.capability (adversarial model) is required")
    _parse_capability(capability)
    claim = _parse_claim(case.get("claim"))
    raw_evidence = case.get("evidence")
    if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, str | bytes):
        raise WitnessError(
            "MALFORMED_EVIDENCE", "case.evidence must be a list of typed evidence items"
        )
    items = [_parse_evidence_item(raw, pos) for pos, raw in enumerate(raw_evidence)]
    return claim, capability, items


def _parse_capability(capability: str) -> str:
    """Validate the declared capability axes (threat model §1.1, ED1/ED2)."""
    axes = [part for part in re.split(r"[+\s]+", capability.strip()) if part]
    if not axes:
        raise WitnessError("PRIVILEGED_ATTACKER", "capability declaration is empty")
    for axis in axes:
        if axis not in REGISTERED_CAPABILITIES:
            raise WitnessError(
                "PRIVILEGED_ATTACKER",
                f"capability {axis!r} (from {capability!r}) is outside the registered A1-A7 "
                "axes; hardware-root/prime-break attackers are out of scope (ED1/ED2) and a "
                "witness relying on a privileged unrealistic attacker is refused",
            )
    return "+".join(axes)


def _context_matches(claim: AttestationClaim, item_context: Mapping[str, str]) -> bool:
    """A receipt/execution/context artifact must agree with the claim's context."""
    if not item_context:
        return True
    for key, value in claim.context.items():
        if key in item_context and item_context[key] != value:
            return False
    return True


def _item_support_level(item: EvidenceItem, claim: AttestationClaim) -> tuple[str, str]:
    """Return (supported_level, binding_note) for one evidence item.

    Fail-closed boundary checks per node class: unverifiable artifacts prove
    nothing; receipts need upstream-verifiable signatures; execution needs the
    TEE anchor (TC3); side effects need persistence and lineage. A context
    mismatch (receipt for another request) caps the item at DISPATCHED and
    reports the G4 binding violation.
    """
    base = NODE_CLASS_SUPPORT[item.node_class]
    if not item.verifiable:
        return "L0-ASSUMED", "unverifiable artifact (TC1 unpinned): proves nothing"
    if item.node_class == "provider_signed_receipt" and not item.digest_binding:
        return (
            "L0-ASSUMED",
            "receipt without a digest binding to dispatched bytes: proves nothing",
        )
    if item.node_class == "execution" and not item.attested_execution:
        return (
            "L2-ACKNOWLEDGED",
            "execution event without the TEE attestation anchor (TC3 absent): capped at L2",
        )
    if item.node_class == "persisted_side_effect" and not (
        item.persisted and item.lineage_recorded
    ):
        return (
            "L3-EXECUTED",
            "side-effect record without durability + lineage: capped at L3",
        )
    if not _context_matches(claim, item.context):
        return (
            "L1.5-DISPATCHED",
            "context binding violated: artifact bound to another request/nonce/purpose (G4); "
            "signature validity is not context validity",
        )
    return base, "binding holds"


def _evaluate(
    case_id: str,
    rule: TransitionRule,
    claim: AttestationClaim,
    capability: str,
    items: list[EvidenceItem],
) -> ProofArtifact:
    """Evidence-boundary evaluation core: strongest surviving support vs claim."""
    demonstrated = "L0-ASSUMED"
    binding_notes: list[str] = []
    g4_seen = False
    observed: list[dict[str, Any]] = []
    for item in items:
        supported, note = _item_support_level(item, claim)
        if "G4" in note:
            g4_seen = True
        binding_notes.append(f"{item.evidence_id}: {note}")
        demonstrated = max(demonstrated, supported, key=lambda lvl: LEVEL_RANK[lvl])
        observed.append(
            {
                "evidence_id": item.evidence_id,
                "node_class": item.node_class,
                "supported_level": supported,
                "binding": note,
            }
        )

    asserted_rank = LEVEL_RANK[claim.asserted_level]
    demonstrated_rank = LEVEL_RANK[demonstrated]
    admitted = asserted_rank <= demonstrated_rank

    if g4_seen and not admitted:
        gap_code = G4_SIGNATURE_AS_CONTEXT
    elif admitted:
        gap_code = GAP_NONE
    else:
        gap_code = rule.gap_code

    verdict = VERDICT_ADMIT if admitted else VERDICT_REJECT
    context_binding = (
        "all artifact context fields agree with the claim context"
        if not g4_seen
        else "; ".join(binding_notes)
    )
    missing = (
        "none: the evidence demonstrates the asserted level" if admitted else rule.missing_proof
    )
    return ProofArtifact(
        witness_id="ACNS-X07-adhoc" if case_id.startswith("adhoc") else case_id,
        case_id=case_id,
        transition_id=rule.transition_id,
        edge_ref=rule.edge_ref,
        claimed_transition=f"{rule.from_level}->{rule.to_level}",
        claim_text=rule.claim_text,
        asserted_level=claim.asserted_level,
        demonstrated_level=demonstrated,
        verdict=verdict,
        observed_outcome=verdict,
        gap_code=gap_code,
        missing_proof=missing,
        capability=capability,
        failure_family=rule.failure_family if not admitted else "none",
        trust_assumptions=rule.trust_assumptions,
        context_binding=context_binding,
        observed_evidence=tuple(observed),
    )


def run_counterexample(
    level_transition: str, case: Mapping[str, Any] | None = None
) -> ProofArtifact:
    """Run one evidence-boundary counterexample witness (the task contract).

    ``run_counterexample(level_transition) -> ProofArtifact``: with no case the
    frozen gallery fixture for the transition is used. The method *certifies
    counterexamples*: the case is first evaluated honestly, and if its evidence
    actually demonstrates the asserted level the runner refuses with
    ``NOT_A_COUNTEREXAMPLE`` — a supported claim is never certified as a
    counterexample witness (a witness that omits nothing is refused as such).
    """
    rule = _resolve_transition(level_transition)
    fixture = (
        copy.deepcopy(dict(case))
        if case is not None
        else copy.deepcopy(dict(WITNESS_GALLERY[rule.transition_id].fixture))
    )
    claim, capability, items = _parse_case(fixture, rule)
    artifact = _evaluate(f"adhoc-{rule.transition_id}", rule, claim, capability, items)
    if artifact.verdict == VERDICT_ADMIT:
        raise WitnessError(
            "NOT_A_COUNTEREXAMPLE",
            f"case {fixture.get('claim', {}).get('claim_id', '?')!r} supplies proof at or above "
            f"the asserted level ({artifact.demonstrated_level}); the claimed implication holds "
            "for it, so it certifies no counterexample — use evaluate_claim_case for honest "
            "supported-claim evaluation",
        )
    return artifact


def evaluate_claim_case(case: Mapping[str, Any]) -> ProofArtifact:
    """Evaluate one claim case honestly (open verdict: ADMIT or REJECT).

    The open-evaluation counterpart of :func:`run_counterexample`: a case
    whose evidence demonstrates the asserted level is ADMITted exactly at the
    demonstrated level; anything incomplete/stale is REJECTed with the
    pre-registered gap code and the concrete missing proof — never coerced.
    """
    if not isinstance(case, Mapping):
        raise WitnessError("MALFORMED_CASE", f"case must be a mapping, got {type(case).__name__}")
    rule = _resolve_transition(case.get("transition"))
    claim, capability, items = _parse_case(case, rule)
    return _evaluate(f"adhoc-{rule.transition_id}", rule, claim, capability, items)


def run_witness(name: str) -> ProofArtifact:
    """Run one registered gallery witness: ``run_witness(name) -> ProofArtifact``.

    Unknown names fail closed with ``UNKNOWN_WITNESS``; a registered witness
    that fails to reproduce its frozen expected label raises ``GALLERY_DRIFT``
    (the label is never repaired to match a drifting witness).
    """
    if not isinstance(name, str) or name not in WITNESS_GALLERY:
        raise WitnessError(
            "UNKNOWN_WITNESS",
            f"witness {name!r} is not in the gallery registry {list(WITNESS_GALLERY)}",
        )
    spec = WITNESS_GALLERY[name]
    artifact = run_counterexample(spec.transition_id)
    if (
        artifact.verdict != spec.expected_verdict
        or artifact.gap_code != spec.expected_gap_code
        or artifact.demonstrated_level != spec.expected_demonstrated_level
    ):
        raise WitnessError(
            "GALLERY_DRIFT",
            f"witness {name!r} produced verdict {artifact.verdict}/{artifact.gap_code}"
            f"/{artifact.demonstrated_level} but its frozen expected label is "
            f"{spec.expected_verdict}/{spec.expected_gap_code}"
            f"/{spec.expected_demonstrated_level}",
        )
    return artifact


def _validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", run_id or ""):
        raise WitnessError(
            "MALFORMED_RUN_ID",
            f"run_id {run_id!r} must match [A-Za-z0-9._-]{{1,128}}",
        )
    return run_id


def emit_witness_gallery(run_id: str, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Emit artifacts/venue2027/acns/<run_id>/witness_gallery.json (deterministic).

    Runs every registered witness, checks each against its frozen expected
    label, records SHA256 digests of inputs and outputs, and writes the
    manifest. Raises ``GALLERY_DRIFT`` if any witness fails its frozen label;
    raises ``OUTCOME_BUCKET_DRIFT`` if any verdict falls outside the shared
    harness bucket vocabulary. Deterministic: no clock, no randomness.
    """
    _validate_run_id(run_id)
    root = Path(repo_root) if repo_root is not None else _MODULE_REPO_ROOT
    entries: list[dict[str, Any]] = []
    reproduced: list[str] = []
    failed: list[str] = []
    for name in WITNESS_IDS:
        spec = WITNESS_GALLERY[name]
        artifact = run_witness(name)
        if artifact.observed_outcome not in OUTCOME_BUCKETS:
            raise WitnessError(
                "OUTCOME_BUCKET_DRIFT",
                f"witness {name!r} outcome {artifact.observed_outcome!r} not in the shared "
                f"harness bucket set {list(OUTCOME_BUCKETS)}",
            )
        reproduced.append(name)
        entry = {
            "witness_id": spec.witness_id,
            "transition_id": spec.transition_id,
            "title": spec.title,
            "edge_ref": artifact.edge_ref,
            "capability": spec.capability,
            "fixture_sha256": _canonical_digest(spec.fixture),
            "artifact": artifact.to_dict(),
            "artifact_sha256": _canonical_digest(artifact.to_dict()),
            "expected_verdict": spec.expected_verdict,
            "expected_gap_code": spec.expected_gap_code,
            "expected_demonstrated_level": spec.expected_demonstrated_level,
            "label_reproduced": True,
        }
        entries.append(entry)

    if failed:
        raise WitnessError(
            "GALLERY_DRIFT",
            f"witnesses failed their frozen expected labels: {failed}",
        )
    gallery_digest = _canonical_digest(entries)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "witness_gallery_version": WITNESS_GALLERY_VERSION,
        "run_id": run_id,
        "fixture_dataset": FIXTURE_DATASET,
        "backend": BACKEND,
        "witness_count": len(entries),
        "witnesses": entries,
        "label_reproduction": {
            "expected_verdicts_reproduced": reproduced,
            "failed_witnesses": failed,
            "reproduction_rate_note": (
                "observed reproduction statistic enters the study only via "
                "artifacts/venue2027/acns/<run_id>/manifest.json after ACNS-freeze"
            ),
        },
        "gallery_sha256": gallery_digest,
    }
    out_dir = root / "artifacts" / "venue2027" / "acns" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "witness_gallery.json"
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


__all__ = [
    "BACKEND",
    "CONTRACT_ID",
    "DEFAULT_RUN_ID",
    "EvidenceItem",
    "FIXTURE_DATASET",
    "G1_TRANSPORT_ACK_AS_PROCESSING",
    "G2_RECEIPT_AS_EXECUTION",
    "G3_EXECUTION_AS_CONSUMPTION",
    "G4_SIGNATURE_AS_CONTEXT",
    "G7_LEVEL_IMPLICIT_UPGRADE",
    "LATTICE_LEVELS",
    "NODE_CLASS_SUPPORT",
    "ProofArtifact",
    "REGISTERED_CAPABILITIES",
    "SCHEMA_VERSION",
    "TransitionRule",
    "WITNESS_GALLERY",
    "WITNESS_GALLERY_VERSION",
    "WITNESS_IDS",
    "WitnessError",
    "WitnessSpec",
    "emit_witness_gallery",
    "evaluate_claim_case",
    "run_counterexample",
    "run_witness",
]
