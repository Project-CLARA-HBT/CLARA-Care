"""Tests for ACNS-X04_claim_extractor (deterministic claim extraction).

Purpose
-------
Machine-checks task ``ACNS-X04_claim_extractor`` (venue ``acns``, phase
``P04``) against its deliverable contract
``evaluation/venue2027/acns/claim_extractor.py``: a deterministic, rule-based
(NO LLM) extractor mapping title/abstract-like paper records to typed
:class:`Claim` objects, each labeled with an evidence-boundary category of the
pre-registered taxonomy (selection protocol §8.2), plus the fail-closed gate
:func:`assert_no_unsupported_claim`.

Vector plan (written per task step 2, before the algorithm):

- **Positive P1** — receipt-scope sentence over provider-receipt evidence
  extracts one deterministic existence claim at ``BND_VALID`` / ``L2``.
- **Positive P2** — an overreading receipt-as-execution sentence extracts at
  ``BND_OVERREAD`` with gap ``G2_RECEIPT_AS_EXECUTION`` (threat model §2 row
  ``model_agency``).
- **Positive P3** — a negative boundary claim ("a transport acknowledgment is
  not evidence that the model executed the tool") is extracted as a
  *boundary* claim, not misread as a positive one, at ``BND_VALID``.
- **Positive P4** — extraction is deterministic: identical record → identical
  claim lists (twice, plus a stable claim id / pointer structure).
- **Positive P5** — titles/abstracts both feed the extractor; scope and
  subject are populated from the declared vocabularies; output is
  JSON-serializable via ``to_dict``.
- **Adversarial A1** — a claim sentence asserting a guarantee with **no
  evidence boundary** is extracted (retained, low confidence, gap G9) and
  :func:`assert_no_unsupported_claim` *refuses* the list with the stable
  reason code ``UNSUPPORTED_CLAIM_NO_EVIDENCE_BOUNDARY`` — fail closed, not a
  silent pass.
- **Adversarial A2** — a marketing-only record (vendor "trust platform"
  boilerplate, no disclosed evidence artifact) yields **no confident claim**
  (empty list), never a fabricated high-confidence claim; and a clean record
  still extracts, proving the gate is record-specific.
- **Adversarial A3** — captions (``Figure 3: ...``) and ablation footnotes are
  never extracted as claims (task negative vector).
- **Adversarial A4** — malformed input fails closed with stable reason codes
  (``MALFORMED_RECORD``, ``EMPTY_TEXT``, ``MALFORMED_CLAIM_LIST``,
  ``MALFORMED_CLAIM``); no unhandled exception shape escapes.
- **Adversarial A5** — hedged wording (``may``) under-determines the asserted
  level: the claim is retained as ``BND_INDETERMINATE`` with the ambiguity
  flag — never coerced to a definite verdict (rater manual §5 IND rules).

Allowed input
-------------
Inline synthetic record literals only (``synthetic-acns-2027``-style): no
network, no database, no clock, no randomness, no LLM, no PHI/PII.

Failure semantics
-----------------
Each violation raises the module's typed error or ``AssertionError`` with a
stable message prefix ``ACNS_X04_``; pytest reports the failing check
directly. Stdlib-only besides pytest itself.

Version
-------
``ACNS_X04_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from evaluation.venue2027.acns.claim_extractor import (  # noqa: E402
    BND_INDETERMINATE,
    BND_OVERREAD,
    BND_UNDERREAD,
    BND_VALID,
    CLAIM_EXTRACTOR_VERSION,
    TAXONOMY_BOUNDARY_CODES,
    Claim,
    ClaimExtractorError,
    UnsupportedClaimError,
    assert_no_unsupported_claim,
    extract_claims,
)

ACNS_X04_TEST_VERSION = "1.0.0"

RECORD_ID = "sok-x04-record-1"

RECEIPT_SCOPE_RECORD = {
    "record_id": RECORD_ID,
    "title": "Provider-attested receipts for tool-using agents",
    "abstract": (
        "Every request submitted to the provider is bound to a digest and "
        "acknowledged by a provider signature. The agent dispatches each tool "
        "call over an attested channel."
    ),
}

OVERREAD_RECORD = {
    "record_id": RECORD_ID,
    "title": "Signed acknowledgments for agent tool calls",
    "abstract": (
        "Because the provider returned a signed acknowledgment, the agent's "
        "tool executed successfully. Receipts are issued for every tool "
        "invocation."
    ),
}

NEGATED_BOUNDARY_RECORD = {
    "record_id": RECORD_ID,
    "title": "What transport acknowledgments do not prove",
    "abstract": (
        "A transport acknowledgment is not evidence that the model executed "
        "the tool. Signed receipts are issued for every tool invocation."
    ),
}

UNSUPPORTED_RECORD = {
    "record_id": RECORD_ID,
    "title": "End-to-end guarantees for agent pipelines",
    "abstract": (
        "Our harness guarantees that every tool call is executed end-to-end. "
        "The evaluation covers three benchmark suites."
    ),
}

MARKETING_RECORD = {
    "record_id": "sok-x04-marketing",
    "title": "The revolutionary trust platform for next-generation agents",
    "abstract": (
        "Our seamless, cutting-edge platform delivers best-in-class agent "
        "experiences. Contact us to request a demo of the world-class "
        "integration."
    ),
}

CAPTION_ABLATION_RECORD = {
    "record_id": RECORD_ID,
    "title": "Receipts under ablation",
    "abstract": (
        "Receipts are issued for every tool invocation. Figure 3: receipts "
        "per second across workloads. In the ablation, receipts are issued "
        "for every tool invocation without digest binding."
    ),
}

HEDGED_RECORD = {
    "record_id": RECORD_ID,
    "title": "Toward attested dispatch",
    "abstract": (
        "Signed provider receipts are issued for every tool invocation; the "
        "receipt may attest execution of the tool. The pipeline dispatches "
        "each request after assembly."
    ),
}

UNDERREAD_RECORD = {
    "record_id": RECORD_ID,
    "title": "TEE-attested execution with modest claims",
    "abstract": (
        "The trusted execution environment attests every tool invocation and "
        "records an execution trace. The provider acknowledged receiving the "
        "request."
    ),
}


def _by_id(claims: list[Claim]) -> dict[str, Claim]:
    return {claim.claim_id.rsplit(":", 1)[-1]: claim for claim in claims}


def test_p1_receipt_scope_claim_is_valid_at_l2() -> None:
    claims = extract_claims(RECEIPT_SCOPE_RECORD)
    assert claims, "P1: receipt-scope record must yield at least one claim"
    by_suffix = _by_id(claims)
    receipt_claim = next(
        (c for c in claims if c.evidence_class == "provider_attested_receipt"), None
    )
    assert receipt_claim is not None, "P1: provider-receipt evidence must be detected"
    assert receipt_claim.evidence_boundary == BND_VALID
    assert receipt_claim.asserted_guarantee == "L2-ACKNOWLEDGED"
    assert receipt_claim.claim_kind == "existence"
    assert receipt_claim.scope in ("universal", "existential", "unscoped")
    assert receipt_claim.subject == "provider receipt"
    assert receipt_claim.record_id == RECORD_ID
    assert receipt_claim.ambiguous is False
    assert receipt_claim.confidence == "high"
    assert by_suffix, "P1: claim ids must be non-trivial"


def test_p2_receipt_as_execution_is_overread_g2() -> None:
    claims = extract_claims(OVERREAD_RECORD)
    overreads = [c for c in claims if c.evidence_boundary == BND_OVERREAD]
    assert overreads, "P2: receipt-as-execution must be labeled BND_OVERREAD"
    target = overreads[0]
    assert target.asserted_guarantee == "L3-EXECUTED"
    assert target.evidence_class == "provider_attested_receipt"
    assert target.gap_codes == ("G2_RECEIPT_AS_EXECUTION",)
    assert target.quote in OVERREAD_RECORD["abstract"]
    start, end = target.text_pointer
    assert 0 <= start < end


def test_p3_negated_proof_is_boundary_claim() -> None:
    claims = extract_claims(NEGATED_BOUNDARY_RECORD)
    assert claims, "P3: negated-proof record must still yield its claims"
    boundary = [c for c in claims if c.claim_kind == "boundary"]
    assert boundary, "P3: the negated sentence must be a boundary claim"
    target = boundary[0]
    assert target.evidence_boundary == BND_VALID
    assert target.asserted_guarantee is None
    assert target.ambiguous is False
    positive = [c for c in claims if c.claim_kind == "existence"]
    assert positive, "P3: the second sentence is a positive existence claim"


def test_p4_deterministic_and_structurally_stable() -> None:
    first = extract_claims(RECEIPT_SCOPE_RECORD)
    second = extract_claims(RECEIPT_SCOPE_RECORD)
    assert [c.to_dict() for c in first] == [c.to_dict() for c in second]
    for claim in first:
        assert claim.claim_id.startswith(RECORD_ID + ":claim-")
        assert claim.text_pointer[0] < claim.text_pointer[1]
        assert claim.quote.strip() == claim.quote


def test_p5_schema_vocabulary_and_json_serializable() -> None:
    claims = extract_claims(HEDGED_RECORD)
    assert claims, "P5: hedged record must still yield claims"
    for claim in claims:
        assert claim.claim_kind in ("existence", "boundary", "performance")
        assert claim.scope in ("universal", "existential", "unscoped")
        assert claim.confidence in ("high", "low")
        assert claim.evidence_boundary is None or claim.evidence_boundary in (
            *TAXONOMY_BOUNDARY_CODES,
        )
        assert claim.asserted_guarantee is None or claim.asserted_guarantee in (
            "L0-ASSUMED",
            "L1-ASSEMBLED",
            "L1.5-TRANSPORT_ACK",
            "L2-ACKNOWLEDGED",
            "L3-EXECUTED",
            "L4-COMMITTED",
        )
        payload = claim.to_dict()
        json.dumps(payload)
        assert payload["extractor_version"] == CLAIM_EXTRACTOR_VERSION
    indeterminate = [c for c in claims if c.evidence_boundary == BND_INDETERMINATE]
    assert indeterminate, "P5: hedged sentence must be retained as INDETERMINATE"
    assert all(c.ambiguous and c.confidence == "low" for c in indeterminate)


def test_a1_unsupported_claim_is_reflosed_fail_closed() -> None:
    claims = extract_claims(UNSUPPORTED_RECORD)
    unsupported = [c for c in claims if c.evidence_boundary is None]
    assert unsupported, "A1: guarantee-without-evidence sentence must be extracted"
    target = unsupported[0]
    assert target.asserted_guarantee is not None, "A1: the guarantee must be asserted"
    assert target.gap_codes == ("G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",)
    assert target.ambiguous is True
    assert target.confidence == "low"
    try:
        assert_no_unsupported_claim(claims)
    except UnsupportedClaimError as error:
        assert error.reason_code == "UNSUPPORTED_CLAIM_NO_EVIDENCE_BOUNDARY"
        assert "no evidence boundary" in str(error)
    else:
        raise AssertionError("A1: assert gate must refuse unsupported claims (fail closed)")
    supported_only = [c for c in claims if c.evidence_boundary is not None]
    assert_no_unsupported_claim(supported_only)
    assert_no_unsupported_claim([])


def test_a2_marketing_only_record_yields_no_confident_claim() -> None:
    assert extract_claims(MARKETING_RECORD) == []
    assert extract_claims(RECEIPT_SCOPE_RECORD), "A2: clean record must still extract"


def test_a3_captions_and_ablations_are_not_claims() -> None:
    claims = extract_claims(CAPTION_ABLATION_RECORD)
    assert claims, "A3: the record's first sentence is a real claim"
    for claim in claims:
        assert not claim.quote.lower().startswith("figure 3")
        assert "ablation" not in claim.quote.lower()
    assert len(claims) == 1, "A3: exactly the non-caption, non-ablation sentence survives"


def test_a4_malformed_input_fails_closed_with_stable_codes() -> None:
    for bad_record in (123, 4.5, None, ["x"]):
        try:
            extract_claims(bad_record)  # type: ignore[arg-type]
        except ClaimExtractorError as error:
            assert error.reason_code == "MALFORMED_RECORD"
        else:
            raise AssertionError(f"A4: record {bad_record!r} must fail closed")
    for empty in ({"record_id": "r"}, {"title": "   ", "abstract": ""}, {"text": ""}, ""):
        try:
            extract_claims(empty)  # type: ignore[arg-type]
        except ClaimExtractorError as error:
            assert error.reason_code == "EMPTY_TEXT"
        else:
            raise AssertionError(f"A4: empty record {empty!r} must fail closed")
    for bad_list in ("claims", None, [1, 2], ["x"], [None]):
        try:
            assert_no_unsupported_claim(bad_list)  # type: ignore[arg-type]
        except UnsupportedClaimError as error:
            assert error.reason_code in ("MALFORMED_CLAIM_LIST", "MALFORMED_CLAIM")
        else:
            raise AssertionError(f"A4: malformed claim list {bad_list!r} must fail closed")


def test_a5_hedged_wording_retained_as_indeterminate() -> None:
    claims = extract_claims(HEDGED_RECORD)
    hedged = [c for c in claims if "may attest" in c.quote]
    assert hedged, "A5: the hedged sentence must be extracted"
    target = hedged[0]
    assert target.evidence_boundary == BND_INDETERMINATE
    assert target.ambiguous is True
    assert target.confidence == "low"
    assert_no_unsupported_claim(claims)


def test_a6_underread_coverage_insight() -> None:
    claims = extract_claims(UNDERREAD_RECORD)
    underreads = [c for c in claims if c.evidence_boundary == BND_UNDERREAD]
    assert underreads, "A6: L2 claim over TEE evidence must be BND_UNDERREAD"
    target = underreads[0]
    assert target.evidence_class == "execution_trace"
    assert target.asserted_guarantee == "L2-ACKNOWLEDGED"
    assert target.gap_codes == ()
