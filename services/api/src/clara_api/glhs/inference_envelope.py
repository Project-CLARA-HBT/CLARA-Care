"""GLHS R4 Inference Envelope Specification & 3-Digest Engine (clara.inference-envelope.v1).

Defines:
- build_canonical_inference_envelope: Constructs 5-partition canonical semantic envelope (clara.inference-envelope.v1).
- compute_projection_digest: SHA-256 over JCS of clinical health projection (D1 / H_proj).
- compute_semantic_envelope_digest: SHA-256 over JCS of full application request envelope (D2 / H_sem).
- compute_transport_payload_digest: SHA-256 over exact outbound HTTP request body bytes (D3 / H_trans).
- compute_streaming_response_digest: Incremental streaming response digest over chunk digests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from clara_api.glhs.canonical_json import (
    PROFILE_V2_RFC8785,
    canonical_hash,
)

SCHEMA_VERSION_V1 = "clara.inference-envelope.v1"


def compute_projection_digest(
    model_visible_projection: Any,
    profile: str = PROFILE_V2_RFC8785,
) -> str:
    """Compute D1 / H_proj: SHA-256 over JCS of model-visible clinical health projection.

    Domain: Clinical Data Projection Layer.
    Formal Definition:
        H_proj = SHA-256(JCS(model_visible_health_projection))
    """
    target = model_visible_projection
    if isinstance(target, dict) and "model_visible_projection" in target and "disclosure_metadata" in target:
        target = target["model_visible_projection"]
    return canonical_hash(target, profile=profile)


def compute_semantic_envelope_digest(
    envelope: Any,
    profile: str = PROFILE_V2_RFC8785,
) -> str:
    """Compute D2 / H_sem: SHA-256 over JCS of full application request envelope.

    Domain: Application Semantic Layer (clara.inference-envelope.v1).
    Formal Definition:
        H_sem = SHA-256(JCS(envelope))
    """
    return canonical_hash(envelope, profile=profile)


def compute_transport_payload_digest(
    request_body_bytes: bytes | bytearray | memoryview | str,
) -> str:
    """Compute D3 / H_trans: SHA-256 over exact outbound HTTP request body bytes.

    Domain: Network Transport & Socket Egress.
    Formal Definition:
        H_trans = SHA-256(exact_serialized_request_body_bytes)
    Excludes secret headers, transport headers, and dynamic network timestamps.
    """
    if isinstance(request_body_bytes, str):
        raw = request_body_bytes.encode("utf-8")
    elif isinstance(request_body_bytes, (bytes, bytearray, memoryview)):
        raw = bytes(request_body_bytes)
    else:
        raise TypeError(f"expected_bytes_or_str_got_{type(request_body_bytes).__name__}")
    return hashlib.sha256(raw).hexdigest()


def compute_streaming_response_digest(
    chunk_digests_list: Sequence[str | bytes | bytearray | memoryview] | str | bytes | bytearray | memoryview,
) -> str:
    """Compute incremental streaming response digest over streaming response chunks.

    Accepts sequence of chunk digests (hex strings) or raw byte chunks and produces
    a deterministic 64-character SHA-256 hex digest.
    """
    if isinstance(chunk_digests_list, (str, bytes, bytearray, memoryview)):
        chunks: Sequence[str | bytes | bytearray | memoryview] = [chunk_digests_list]
    else:
        chunks = chunk_digests_list

    hasher = hashlib.sha256()
    for chunk in chunks:
        if isinstance(chunk, str):
            hasher.update(chunk.encode("utf-8"))
        elif isinstance(chunk, (bytes, bytearray, memoryview)):
            hasher.update(chunk)
        else:
            raise TypeError(f"invalid_streaming_chunk_type:{type(chunk).__name__}")
    return hasher.hexdigest()


def build_canonical_inference_envelope(
    *,
    snapshot: Any = None,
    snapshot_id: str | None = None,
    manifest_digest: str | None = None,
    model_visible_projection: Any = None,
    model_route: str = "",
    requested_model_id: str = "",
    prompt_template_version: str = "",
    system_prompt_version: str = "",
    purpose: str = "",
    task: str = "",
    conversation_context: Any = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
    runtime_parameters: Mapping[str, Any] | None = None,
    provider: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    seed: int | None = None,
    system_prompt: Mapping[str, Any] | None = None,
    base_system_prompt_digest: str | None = None,
    clinical_guardrails: Any = None,
    task_instructions: Mapping[str, Any] | None = None,
    task_parameters: Mapping[str, Any] | None = None,
    output_format_spec: Mapping[str, Any] | None = None,
    disclosure_metadata: Mapping[str, Any] | None = None,
    health_state_projection: Mapping[str, Any] | None = None,
    include_legacy_flat_keys: bool = True,
    profile: str = PROFILE_V2_RFC8785,
) -> dict[str, Any]:
    """Construct canonical 5-partition envelope `clara.inference-envelope.v1`.

    Partitions:
    1. system_prompt (prompt_template_version, system_prompt_version, base_system_prompt_digest, clinical_guardrails)
    2. health_state_projection (disclosure_metadata, model_visible_projection, projection_digest)
    3. conversation_context (messages, context_window_strategy)
    4. task_instructions (purpose, task, task_parameters, output_format_spec)
    5. runtime_parameters (model_route, requested_model_id, provider, temperature, max_tokens, top_p, seed)

    Retains top-level legacy keys when include_legacy_flat_keys=True for backward compatibility.
    """
    snap_id = snapshot_id
    man_digest = manifest_digest
    if snapshot is not None:
        if snap_id is None:
            snap_id = getattr(snapshot, "public_id", None) or getattr(snapshot, "id", None)
        if man_digest is None:
            man_digest = getattr(snapshot, "manifest_digest", None)

    # 1. System Prompt Partition
    sys_prompt_part: dict[str, Any] = {}
    if system_prompt is not None:
        sys_prompt_part.update(system_prompt)
    sys_prompt_part.setdefault("prompt_template_version", prompt_template_version)
    sys_prompt_part.setdefault("system_prompt_version", system_prompt_version)
    if base_system_prompt_digest is not None:
        sys_prompt_part["base_system_prompt_digest"] = base_system_prompt_digest
    if clinical_guardrails is not None:
        sys_prompt_part["clinical_guardrails"] = clinical_guardrails

    # 2. Health State Projection Partition & D1 Digest
    proj_payload = model_visible_projection if model_visible_projection is not None else {}
    if health_state_projection is not None and "model_visible_projection" in health_state_projection:
        proj_payload = health_state_projection["model_visible_projection"]

    proj_digest = compute_projection_digest(proj_payload, profile=profile)

    meta: dict[str, Any] = {
        "snapshot_id": snap_id or "",
        "manifest_digest": man_digest or "",
        "projection_digest": proj_digest,
    }
    if disclosure_metadata:
        meta.update(disclosure_metadata)

    proj_part: dict[str, Any] = {
        "disclosure_metadata": meta,
        "model_visible_projection": proj_payload,
    }
    if health_state_projection is not None:
        for k, v in health_state_projection.items():
            if k not in proj_part:
                proj_part[k] = v

    # 3. Conversation Context Partition
    conv_part: dict[str, Any] = {}
    if conversation_context is not None and isinstance(conversation_context, dict):
        conv_part.update(conversation_context)
    if "messages" not in conv_part:
        conv_part["messages"] = list(messages) if messages is not None else []

    # 4. Task Instructions Partition
    task_part: dict[str, Any] = {}
    if task_instructions is not None:
        task_part.update(task_instructions)
    task_part.setdefault("purpose", purpose)
    task_part.setdefault("task", task)
    if task_parameters is not None:
        task_part["task_parameters"] = task_parameters
    if output_format_spec is not None:
        task_part["output_format_spec"] = output_format_spec

    # 5. Runtime Parameters Partition
    runtime_part: dict[str, Any] = {}
    if runtime_parameters is not None:
        runtime_part.update(runtime_parameters)
    runtime_part.setdefault("model_route", model_route)
    runtime_part.setdefault("requested_model_id", requested_model_id)
    if provider is not None:
        runtime_part["provider"] = provider
    if temperature is not None:
        runtime_part["temperature"] = temperature
    if max_tokens is not None:
        runtime_part["max_tokens"] = max_tokens
    if top_p is not None:
        runtime_part["top_p"] = top_p
    if seed is not None:
        runtime_part["seed"] = seed

    envelope: dict[str, Any] = {
        "schema": SCHEMA_VERSION_V1,
        "system_prompt": sys_prompt_part,
        "health_state_projection": proj_part,
        "conversation_context": conv_part,
        "task_instructions": task_part,
        "runtime_parameters": runtime_part,
    }

    if include_legacy_flat_keys:
        envelope["disclosure"] = {
            "snapshot_id": snap_id or "",
            "projection_digest": proj_digest,
            "manifest_digest": man_digest or "",
        }
        envelope["model_visible_projection"] = proj_payload
        envelope["model_route"] = runtime_part.get("model_route", "")
        envelope["requested_model_id"] = runtime_part.get("requested_model_id", "")
        envelope["prompt_template_version"] = sys_prompt_part.get("prompt_template_version", "")
        envelope["system_prompt_version"] = sys_prompt_part.get("system_prompt_version", "")
        envelope["purpose"] = task_part.get("purpose", "")
        envelope["task"] = task_part.get("task", "")

    return envelope
