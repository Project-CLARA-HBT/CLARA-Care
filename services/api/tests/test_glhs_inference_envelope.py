"""Unit tests for GLHS R4 Inference Envelope Specification & 3-Digest Engine.

Covers:
- build_canonical_inference_envelope 5-partition envelope construction
- compute_projection_digest (D1 / H_proj)
- compute_semantic_envelope_digest (D2 / H_sem)
- compute_transport_payload_digest (D3 / H_trans)
- compute_streaming_response_digest
- Strict RFC 8785 canonical serialization consistency
- Module exports in clara_api.glhs.__init__
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pytest

from clara_api.glhs import (
    build_canonical_inference_envelope,
    compute_projection_digest,
    compute_semantic_envelope_digest,
    compute_streaming_response_digest,
    compute_transport_payload_digest,
)
from clara_api.glhs.canonical_json import (
    PROFILE_V2_RFC8785,
    canonical_hash,
)
from clara_api.glhs.inference_envelope import SCHEMA_VERSION_V1


@dataclass
class DummySnapshot:
    public_id: str
    manifest_digest: str


def test_build_canonical_inference_envelope_5_partitions() -> None:
    """Verify 5-partition structure per clara.inference-envelope.v1 spec."""
    snapshot = DummySnapshot(public_id="snap_123", manifest_digest="sha256:manifest_abc")
    projection = {"profile_id": 42, "active_medications": ["Aspirin 81mg"]}

    envelope = build_canonical_inference_envelope(
        snapshot=snapshot,
        model_visible_projection=projection,
        model_route="research_tier2",
        requested_model_id="deepseek-reasoner",
        prompt_template_version="2026.08.19-v1",
        system_prompt_version="sys-prompt-v3",
        purpose="treatment_planning",
        task="reconcile_medication_order",
        messages=[{"role": "user", "content": "Check interaction"}],
        provider="deepseek",
        temperature=0.2,
        max_tokens=1024,
    )

    assert envelope["schema"] == "clara.inference-envelope.v1"
    assert envelope["schema"] == SCHEMA_VERSION_V1

    # Partition 1: system_prompt
    assert envelope["system_prompt"]["prompt_template_version"] == "2026.08.19-v1"
    assert envelope["system_prompt"]["system_prompt_version"] == "sys-prompt-v3"

    # Partition 2: health_state_projection
    assert envelope["health_state_projection"]["disclosure_metadata"]["snapshot_id"] == "snap_123"
    assert envelope["health_state_projection"]["disclosure_metadata"]["manifest_digest"] == "sha256:manifest_abc"
    assert envelope["health_state_projection"]["model_visible_projection"] == projection

    # Partition 3: conversation_context
    assert envelope["conversation_context"]["messages"] == [{"role": "user", "content": "Check interaction"}]

    # Partition 4: task_instructions
    assert envelope["task_instructions"]["purpose"] == "treatment_planning"
    assert envelope["task_instructions"]["task"] == "reconcile_medication_order"

    # Partition 5: runtime_parameters
    assert envelope["runtime_parameters"]["model_route"] == "research_tier2"
    assert envelope["runtime_parameters"]["requested_model_id"] == "deepseek-reasoner"
    assert envelope["runtime_parameters"]["provider"] == "deepseek"
    assert envelope["runtime_parameters"]["temperature"] == 0.2
    assert envelope["runtime_parameters"]["max_tokens"] == 1024

    # Backwards compatibility flat keys
    assert envelope["disclosure"]["snapshot_id"] == "snap_123"
    assert envelope["disclosure"]["manifest_digest"] == "sha256:manifest_abc"
    assert envelope["model_visible_projection"] == projection
    assert envelope["model_route"] == "research_tier2"
    assert envelope["requested_model_id"] == "deepseek-reasoner"


def test_compute_projection_digest_d1() -> None:
    """Verify D1 / H_proj calculation over clinical projection."""
    projection = {"profile_id": 100, "allergies": ["Penicillin"]}
    d1 = compute_projection_digest(projection)

    expected = canonical_hash(projection, profile=PROFILE_V2_RFC8785)
    assert d1 == expected
    assert len(d1) == 64

    # Partition dictionary extraction support
    partition = {
        "disclosure_metadata": {"snapshot_id": "s1"},
        "model_visible_projection": projection,
    }
    assert compute_projection_digest(partition) == d1


def test_compute_semantic_envelope_digest_d2() -> None:
    """Verify D2 / H_sem calculation over full semantic envelope."""
    envelope = {
        "schema": "clara.inference-envelope.v1",
        "system_prompt": {"v": "1"},
        "health_state_projection": {"data": 123},
        "conversation_context": {"messages": []},
        "task_instructions": {"purpose": "p", "task": "t"},
        "runtime_parameters": {"model_route": "r", "requested_model_id": "m"},
    }
    d2 = compute_semantic_envelope_digest(envelope)
    expected = canonical_hash(envelope, profile=PROFILE_V2_RFC8785)
    assert d2 == expected
    assert len(d2) == 64


def test_compute_transport_payload_digest_d3() -> None:
    """Verify D3 / H_trans calculation over raw outbound HTTP request bytes."""
    payload_bytes = b'{"model":"deepseek-reasoner","messages":[{"role":"user","content":"hello"}]}'
    d3_bytes = compute_transport_payload_digest(payload_bytes)

    expected = hashlib.sha256(payload_bytes).hexdigest()
    assert d3_bytes == expected

    # String input support
    payload_str = '{"model":"deepseek-reasoner"}'
    d3_str = compute_transport_payload_digest(payload_str)
    assert d3_str == hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    with pytest.raises(TypeError):
        compute_transport_payload_digest(123)  # type: ignore[arg-type]


def test_compute_streaming_response_digest() -> None:
    """Verify incremental streaming response digest computation."""
    chunks = [
        "data: {\"token\": \"Hello\"}\n\n",
        "data: {\"token\": \" world\"}\n\n",
        "data: [DONE]\n\n",
    ]
    digest = compute_streaming_response_digest(chunks)
    expected_hasher = hashlib.sha256()
    for c in chunks:
        expected_hasher.update(c.encode("utf-8"))
    assert digest == expected_hasher.hexdigest()
    assert len(digest) == 64

    # Bytes chunk support
    byte_chunks = [b"chunk1", b"chunk2"]
    byte_digest = compute_streaming_response_digest(byte_chunks)
    assert byte_digest == hashlib.sha256(b"chunk1chunk2").hexdigest()


def test_determinism_and_invariance() -> None:
    """Verify build_canonical_inference_envelope determinism and context isolation."""
    snapshot = DummySnapshot(public_id="snap_1", manifest_digest="sha256:man_1")
    proj = {"med": "Aspirin"}

    env1 = build_canonical_inference_envelope(
        snapshot=snapshot,
        model_visible_projection=proj,
        model_route="r1",
        requested_model_id="m1",
        prompt_template_version="v1",
        system_prompt_version="s1",
        purpose="p1",
        task="t1",
    )
    env2 = build_canonical_inference_envelope(
        snapshot=snapshot,
        model_visible_projection=proj,
        model_route="r1",
        requested_model_id="m1",
        prompt_template_version="v1",
        system_prompt_version="s1",
        purpose="p1",
        task="t1",
    )

    assert env1 == env2
    assert compute_semantic_envelope_digest(env1) == compute_semantic_envelope_digest(env2)

    # Context isolation: altering messages alters D2 (H_sem), but D1 (H_proj) stays invariant
    env_with_messages = build_canonical_inference_envelope(
        snapshot=snapshot,
        model_visible_projection=proj,
        model_route="r1",
        requested_model_id="m1",
        prompt_template_version="v1",
        system_prompt_version="s1",
        purpose="p1",
        task="t1",
        messages=[{"role": "user", "content": "extra query"}],
    )

    assert compute_projection_digest(env1["model_visible_projection"]) == compute_projection_digest(
        env_with_messages["model_visible_projection"]
    )
    assert compute_semantic_envelope_digest(env1) != compute_semantic_envelope_digest(env_with_messages)
