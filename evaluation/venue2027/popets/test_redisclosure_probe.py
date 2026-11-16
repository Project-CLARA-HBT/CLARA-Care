"""Tests for POPETS-X04_redisclosure_probe (redisclosure probe).

Positive controls (must pass):
- Clean response -> no leak:
  An outbound response without any canary tokens returns canary_detected=False,
  matched_tokens=[], and violation_type="NONE".
- Known canary in outbound response -> detected leak with accurate token match:
  An outbound response containing a canary token returns canary_detected=True,
  violation_type="REVOCATION_LEAK", and the matched token in matched_tokens.
- Multi-field response isolation and byte-accurate accounting:
  Outbound fields (e.g. dict mapping) record byte-accurate UTF-8 length, SHA-256
  digests, and field-level canary flags. Total bytes match sum of field bytes.
- Multiple canaries with partial match:
  When a subset of monitored canaries appears in the response, exactly that subset
  is returned in matched_tokens in deterministic sorted order.
- Target contract probe(history, config) -> DisclosureReport:
  Aggregates multiple dispatches and computes total byte counts and violation counts.
- Black-box observer:
  Probe inspects only the outbound fields without scanning model internals
  (model_internals_inspected=False).
- JSON serializability and determinism.

Adversarial controls (must be refused / fail closed):
- Tampered lineage refused:
  Lineage with digest mismatch, explicit is_tampered flag, or cycle metadata
  raises RedisclosureProbeError with stable reason code LINEAGE_TAMPERED.
- Canary token casing/normalization check:
  Casing evasion (uppercase token in lowercase response, lowercase token in uppercase
  response, mixed casing, unicode NFKC normalization) is detected as a leak.
  Malformed, empty, whitespace-only, or non-string canary tokens are refused
  fail-closed with CANARY_TOKEN_MALFORMED.
- Empty context refused:
  Empty context ({}, None, "") is refused fail-closed with CONTEXT_EMPTY.
  Missing or whitespace-only tenant/purpose is refused with CONTEXT_MALFORMED.
- Outbound malformed refused:
  None outbound_response is refused fail-closed with OUTBOUND_MALFORMED.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.popets.redisclosure_probe import (
    REASON_CANARY_DETECTED,
    REASON_CANARY_TOKEN_MALFORMED,
    REASON_CONTEXT_EMPTY,
    REASON_CONTEXT_MALFORMED,
    REASON_LINEAGE_MALFORMED,
    REASON_LINEAGE_TAMPERED,
    REASON_OUTBOUND_MALFORMED,
    REASON_PROBE_CLEAN,
    REDISCLOSURE_PROBE_VERSION,
    VIOLATION_NONE,
    VIOLATION_REVOCATION_LEAK,
    CacheLineage,
    DisclosureReport,
    ProbeResult,
    RedisclosureProbeError,
    TenantPurposeContext,
    compute_lineage_digest,
    probe,
    probe_redisclosure,
)


@pytest.fixture
def valid_context() -> dict[str, str]:
    return {"tenant_id": "tenant-popets-42", "purpose": "treatment"}


@pytest.fixture
def valid_lineage() -> CacheLineage:
    nodes = ("artifact-ehr-001", "artifact-summary-002", "artifact-cache-003")
    digest = compute_lineage_digest(nodes)
    return CacheLineage(nodes=nodes, digest=digest)


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_positive_clean_response_no_leak(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """Clean outbound response with no canary tokens must report no leak."""
    clean_payload = "Patient vitals: BP 120/80 mmHg, HR 72 bpm, SpO2 98%."
    canary_tokens = ["CANARY-SECRET-TOKEN-99", "CANARY-PATIENT-DIAGNOSIS-88"]

    result = probe_redisclosure(
        outbound_response=clean_payload,
        canary_tokens=canary_tokens,
        tenant_purpose_ctx=valid_context,
        cache_lineage=valid_lineage,
    )

    assert isinstance(result, ProbeResult)
    assert result.canary_detected is False
    assert result.violation_type == VIOLATION_NONE
    assert result.matched_tokens == []
    assert result.reason_code == REASON_PROBE_CLEAN
    assert result.byte_count == len(clean_payload.encode("utf-8"))
    assert result.model_internals_inspected is False
    assert len(result.field_observations) == 1
    assert result.field_observations[0].canary_detected is False


def test_positive_known_canary_detected_leak(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """Known canary in outbound payload must be detected with accurate match."""
    canary = "CANARY-REVOKED-PATIENT-777"
    leaked_payload = f"Clinical advice based on prior context: Ref={canary} - Continue Metformin."

    result = probe_redisclosure(
        outbound_response=leaked_payload,
        canary_tokens=[canary],
        tenant_purpose_ctx=valid_context,
        cache_lineage=valid_lineage,
    )

    assert result.canary_detected is True
    assert result.violation_type == VIOLATION_REVOCATION_LEAK
    assert result.matched_tokens == [canary]
    assert result.reason_code == REASON_CANARY_DETECTED
    assert result.byte_count == len(leaked_payload.encode("utf-8"))
    assert len(result.field_observations) == 1
    assert result.field_observations[0].canary_detected is True
    assert result.field_observations[0].matched_tokens == (canary,)


def test_positive_multi_field_observation_accuracy(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """Multi-field structured outbound response tracks byte counts and leaks per field."""
    canary = "CANARY-ALLERGY-PENICILLIN-33"
    structured_payload = {
        "summary": "Patient review scheduled for next week.",
        "confidential_note": f"Alert: Previous adverse reaction documented as {canary}.",
        "status_code": 200,
    }

    result = probe_redisclosure(
        outbound_response=structured_payload,
        canary_tokens=[canary],
        tenant_purpose_ctx=valid_context,
        cache_lineage=valid_lineage,
    )

    assert result.canary_detected is True
    assert result.matched_tokens == [canary]
    assert len(result.field_observations) == 3

    obs_map = {obs.field_name: obs for obs in result.field_observations}
    assert obs_map["summary"].canary_detected is False
    assert obs_map["status_code"].canary_detected is False
    assert obs_map["confidential_note"].canary_detected is True
    assert obs_map["confidential_note"].matched_tokens == (canary,)

    # Total byte count matches sum of field byte counts
    expected_total_bytes = sum(obs.byte_count for obs in result.field_observations)
    assert result.byte_count == expected_total_bytes


def test_positive_partial_canary_subset_matching(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """When only a subset of canaries is present, only that subset is reported."""
    canaries = ["CANARY_ALPHA", "CANARY_BETA", "CANARY_GAMMA", "CANARY_DELTA"]
    payload = "Diagnostic review: Found CANARY_GAMMA and also CANARY_ALPHA in history."

    result = probe_redisclosure(
        outbound_response=payload,
        canary_tokens=canaries,
        tenant_purpose_ctx=valid_context,
        cache_lineage=valid_lineage,
    )

    assert result.canary_detected is True
    assert result.matched_tokens == ["CANARY_ALPHA", "CANARY_GAMMA"]


def test_positive_black_box_and_serializability(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """Probe result is black-box and cleanly serializable to JSON."""
    result = probe_redisclosure(
        outbound_response="Observation payload",
        canary_tokens=["CANARY-TEST"],
        tenant_purpose_ctx=valid_context,
        cache_lineage=valid_lineage,
    )

    assert result.model_internals_inspected is False
    data = result.to_dict()
    serialized = json.dumps(data)
    deserialized = json.loads(serialized)

    assert deserialized["canary_detected"] is False
    assert deserialized["tenant_id"] == "tenant-popets-42"
    assert deserialized["purpose"] == "treatment"
    assert deserialized["model_internals_inspected"] is False


def test_positive_probe_history_wrapper(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """Target contract probe(history, config) -> DisclosureReport aggregates correctly."""
    history = [
        "Clean dispatch 1",
        "Leaked dispatch 2 with CANARY_REVOKED_1",
        "Clean dispatch 3",
    ]
    config = {
        "canary_tokens": ["CANARY_REVOKED_1", "CANARY_REVOKED_2"],
        "tenant_purpose_ctx": valid_context,
        "cache_lineage": valid_lineage,
    }

    report = probe(history, config)

    assert isinstance(report, DisclosureReport)
    assert report.canary_detected is True
    assert report.violation_count == 1
    assert len(report.results) == 3
    assert report.matched_tokens == ["CANARY_REVOKED_1"]

    rep_dict = report.to_dict()
    assert json.dumps(rep_dict) is not None


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_adversarial_tampered_lineage_refused(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """Tampered cache lineage (digest mismatch or tampered flag) must be refused."""
    # 1. Digest mismatch on CacheLineage
    tampered_lineage = CacheLineage(
        nodes=valid_lineage.nodes,
        digest="badf00d" * 8,  # forged/tampered digest
    )
    with pytest.raises(RedisclosureProbeError) as exc_digest:
        probe_redisclosure(
            outbound_response="Response text",
            canary_tokens=["CANARY-X"],
            tenant_purpose_ctx=valid_context,
            cache_lineage=tampered_lineage,
        )
    assert exc_digest.value.reason_code == REASON_LINEAGE_TAMPERED

    # 2. Explicit is_tampered flag
    flagged_lineage = CacheLineage(
        nodes=valid_lineage.nodes,
        digest=valid_lineage.digest,
        is_tampered=True,
    )
    with pytest.raises(RedisclosureProbeError) as exc_flag:
        probe_redisclosure(
            outbound_response="Response text",
            canary_tokens=["CANARY-X"],
            tenant_purpose_ctx=valid_context,
            cache_lineage=flagged_lineage,
        )
    assert exc_flag.value.reason_code == REASON_LINEAGE_TAMPERED

    # 3. Tampered mapping representation
    tampered_map = {
        "nodes": list(valid_lineage.nodes),
        "digest": "deadbeef" * 8,
    }
    with pytest.raises(RedisclosureProbeError) as exc_map:
        probe_redisclosure(
            outbound_response="Response text",
            canary_tokens=["CANARY-X"],
            tenant_purpose_ctx=valid_context,
            cache_lineage=tampered_map,
        )
    assert exc_map.value.reason_code == REASON_LINEAGE_TAMPERED

    # 4. Cycle metadata in mapping
    cycle_map = {
        "nodes": list(valid_lineage.nodes),
        "has_cycle": True,
    }
    with pytest.raises(RedisclosureProbeError) as exc_cycle:
        probe_redisclosure(
            outbound_response="Response text",
            canary_tokens=["CANARY-X"],
            tenant_purpose_ctx=valid_context,
            cache_lineage=cycle_map,
        )
    assert exc_cycle.value.reason_code == REASON_LINEAGE_TAMPERED

    # 5. Malformed None lineage
    with pytest.raises(RedisclosureProbeError) as exc_none:
        probe_redisclosure(
            outbound_response="Response text",
            canary_tokens=["CANARY-X"],
            tenant_purpose_ctx=valid_context,
            cache_lineage=None,
        )
    assert exc_none.value.reason_code == REASON_LINEAGE_MALFORMED


def test_adversarial_canary_token_casing_and_normalization_check(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """Canary detection must succeed across casing mutations and unicode normalization."""
    token = "CANARY_SECRET_MUTATION_42"

    # 1. Lowercase evasion attempt
    payload_lower = "Outbound text containing canary_secret_mutation_42 in lowercase."
    res_lower = probe_redisclosure(
        outbound_response=payload_lower,
        canary_tokens=[token],
        tenant_purpose_ctx=valid_context,
        cache_lineage=valid_lineage,
    )
    assert res_lower.canary_detected is True
    assert res_lower.matched_tokens == [token]

    # 2. Mixed case evasion attempt
    payload_mixed = "Outbound text containing CaNaRy_SeCrEt_MuTaTiOn_42 in mixed case."
    res_mixed = probe_redisclosure(
        outbound_response=payload_mixed,
        canary_tokens=[token],
        tenant_purpose_ctx=valid_context,
        cache_lineage=valid_lineage,
    )
    assert res_mixed.canary_detected is True
    assert res_mixed.matched_tokens == [token]

    # 3. Unicode normalization (NFKD vs NFKC)
    token_accent = "CANARY_CLÍNICA"
    payload_accent = "Outbound containing canary_clínica with lowercase."
    res_accent = probe_redisclosure(
        outbound_response=payload_accent,
        canary_tokens=[token_accent],
        tenant_purpose_ctx=valid_context,
        cache_lineage=valid_lineage,
    )
    assert res_accent.canary_detected is True

    # 4. Empty and whitespace-only canary tokens refused fail-closed
    with pytest.raises(RedisclosureProbeError) as exc_empty:
        probe_redisclosure(
            outbound_response="Outbound payload",
            canary_tokens=[""],
            tenant_purpose_ctx=valid_context,
            cache_lineage=valid_lineage,
        )
    assert exc_empty.value.reason_code == REASON_CANARY_TOKEN_MALFORMED

    with pytest.raises(RedisclosureProbeError) as exc_ws:
        probe_redisclosure(
            outbound_response="Outbound payload",
            canary_tokens=["   "],
            tenant_purpose_ctx=valid_context,
            cache_lineage=valid_lineage,
        )
    assert exc_ws.value.reason_code == REASON_CANARY_TOKEN_MALFORMED

    # 5. Non-string canary token refused fail-closed
    with pytest.raises(RedisclosureProbeError) as exc_type:
        probe_redisclosure(
            outbound_response="Outbound payload",
            canary_tokens=[12345],  # type: ignore[list-item]
            tenant_purpose_ctx=valid_context,
            cache_lineage=valid_lineage,
        )
    assert exc_type.value.reason_code == REASON_CANARY_TOKEN_MALFORMED


def test_adversarial_empty_context_refused(valid_lineage: CacheLineage) -> None:
    """Empty or malformed tenant/purpose context must be refused fail-closed."""
    # 1. Empty dict refused CONTEXT_EMPTY
    with pytest.raises(RedisclosureProbeError) as exc_empty_dict:
        probe_redisclosure(
            outbound_response="Payload",
            canary_tokens=["CANARY-A"],
            tenant_purpose_ctx={},
            cache_lineage=valid_lineage,
        )
    assert exc_empty_dict.value.reason_code == REASON_CONTEXT_EMPTY

    # 2. None context refused CONTEXT_EMPTY
    with pytest.raises(RedisclosureProbeError) as exc_none:
        probe_redisclosure(
            outbound_response="Payload",
            canary_tokens=["CANARY-A"],
            tenant_purpose_ctx=None,
            cache_lineage=valid_lineage,
        )
    assert exc_none.value.reason_code == REASON_CONTEXT_EMPTY

    # 3. Empty string refused CONTEXT_EMPTY
    with pytest.raises(RedisclosureProbeError) as exc_str:
        probe_redisclosure(
            outbound_response="Payload",
            canary_tokens=["CANARY-A"],
            tenant_purpose_ctx="",
            cache_lineage=valid_lineage,
        )
    assert exc_str.value.reason_code == REASON_CONTEXT_EMPTY

    # 4. Context missing purpose refused CONTEXT_MALFORMED
    with pytest.raises(RedisclosureProbeError) as exc_no_purpose:
        probe_redisclosure(
            outbound_response="Payload",
            canary_tokens=["CANARY-A"],
            tenant_purpose_ctx={"tenant_id": "tenant-1"},
            cache_lineage=valid_lineage,
        )
    assert exc_no_purpose.value.reason_code == REASON_CONTEXT_MALFORMED

    # 5. Context with empty/whitespace tenant refused CONTEXT_MALFORMED
    with pytest.raises(RedisclosureProbeError) as exc_ws_tenant:
        probe_redisclosure(
            outbound_response="Payload",
            canary_tokens=["CANARY-A"],
            tenant_purpose_ctx={"tenant_id": "   ", "purpose": "treatment"},
            cache_lineage=valid_lineage,
        )
    assert exc_ws_tenant.value.reason_code == REASON_CONTEXT_MALFORMED


def test_adversarial_malformed_outbound_response(
    valid_context: dict[str, str], valid_lineage: CacheLineage
) -> None:
    """None outbound_response must be refused fail-closed."""
    with pytest.raises(RedisclosureProbeError) as exc:
        probe_redisclosure(
            outbound_response=None,
            canary_tokens=["CANARY-1"],
            tenant_purpose_ctx=valid_context,
            cache_lineage=valid_lineage,
        )
    assert exc.value.reason_code == REASON_OUTBOUND_MALFORMED


def test_version_constant() -> None:
    """Module version string is defined."""
    assert REDISCLOSURE_PROBE_VERSION == "1.0.0"


def test_tenant_purpose_context_object() -> None:
    """TenantPurposeContext typed input model validates and serializes."""
    ctx = TenantPurposeContext(
        tenant_id="tenant-alpha",
        purpose="research",
        consent_epoch=3,
        revocation_time=100,
        metadata={"arm": "C0"},
    )
    assert ctx.tenant_id == "tenant-alpha"
    assert ctx.purpose == "research"
    d = ctx.to_dict()
    assert d["consent_epoch"] == 3
    assert d["revocation_time"] == 100
    assert d["metadata"] == {"arm": "C0"}

    # Pass typed context into probe_redisclosure directly
    nodes = ("art-1",)
    lineage = CacheLineage(nodes=nodes, digest=compute_lineage_digest(nodes))
    res = probe_redisclosure(
        outbound_response="Payload",
        canary_tokens=["CANARY-X"],
        tenant_purpose_ctx=ctx,
        cache_lineage=lineage,
    )
    assert res.tenant_id == "tenant-alpha"
    assert res.purpose == "research"
    assert res.observation_metadata["consent_epoch"] == 3
