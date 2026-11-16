"""CLARA-Care 2027 POPETS task POPETS-X04_redisclosure_probe — future redisclosure probe.

Purpose
-------
Instrument future dispatches and retries for the paper *Revocation-Complete Future
Disclosure for Cached Longitudinal AI Contexts*
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md`` RQ1,
``research/venue2027/VENUES/popets/TASKS/POPETS-X04_redisclosure_probe.md``).

The probe operates as a strictly black-box observer: it records byte-accurate outbound
field observations using synthetic canaries, tenant/purpose context, and cache lineage.
It does NOT scan model internals (no access to weights, attention heads, or activation
vectors; model-internal scanning is out of scope and forbidden by the threat model).

Detects if synthetic canary tokens belonging to a revoked context appear in an outbound
payload across dispatches and retry queues. Reports:
- ``canary_detected: bool``
- ``violation_type: str`` (e.g. ``REVOCATION_LEAK``, ``CROSS_PURPOSE_LEAK``, or ``NONE``)
- ``matched_tokens: list[str]``

Allowed input
-------------
- ``outbound_response``: string, bytes, or mapping of field names to values (the byte-level
  payload leaving the process boundary to an external provider or consumer).
- ``canary_tokens``: iterable of non-empty synthetic canary strings. Empty or whitespace-only
  tokens are refused.
- ``tenant_purpose_ctx``: :class:`TenantPurposeContext` or mapping specifying non-empty
  ``tenant_id`` and ``purpose``. Empty context is refused fail-closed.
- ``cache_lineage``: :class:`CacheLineage`, mapping, or node sequence representing the
  provenance of cached context. Tampered lineage (digest mismatch or tampered flag) is
  refused fail-closed.

Failure semantics (fail closed, stable uppercase reason codes):
--------------------------------------------------------------
- ``CONTEXT_EMPTY`` — empty context provided (``None``, ``{}``, or empty string).
- ``CONTEXT_MALFORMED`` — context missing valid tenant identifier or purpose.
- ``LINEAGE_TAMPERED`` — lineage digest mismatch or explicitly flagged as tampered.
- ``LINEAGE_MALFORMED`` — lineage is None, malformed, or contains invalid node identifiers.
- ``CANARY_TOKEN_MALFORMED`` — canary token is empty, whitespace-only, or not a string.
- ``OUTBOUND_MALFORMED`` — outbound response is None.

Version
-------
``REDISCLOSURE_PROBE_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any, Final

__all__ = [
    "REDISCLOSURE_PROBE_VERSION",
    "REASON_CANARY_DETECTED",
    "REASON_CANARY_TOKEN_MALFORMED",
    "REASON_CONTEXT_EMPTY",
    "REASON_CONTEXT_MALFORMED",
    "REASON_LINEAGE_MALFORMED",
    "REASON_LINEAGE_TAMPERED",
    "REASON_OUTBOUND_MALFORMED",
    "REASON_PROBE_CLEAN",
    "VIOLATION_CROSS_PURPOSE",
    "VIOLATION_LINEAGE_LEAK",
    "VIOLATION_NONE",
    "VIOLATION_REVOCATION_LEAK",
    "CacheLineage",
    "DisclosureReport",
    "FieldObservation",
    "ProbeResult",
    "RedisclosureProbeError",
    "TenantPurposeContext",
    "compute_lineage_digest",
    "probe",
    "probe_redisclosure",
]

REDISCLOSURE_PROBE_VERSION: Final[str] = "1.0.0"

#: Reason codes (stable, uppercase machine-readable identifiers).
REASON_PROBE_CLEAN: Final[str] = "CLEAN"
REASON_CANARY_DETECTED: Final[str] = "CANARY_DETECTED"
REASON_CONTEXT_EMPTY: Final[str] = "CONTEXT_EMPTY"
REASON_CONTEXT_MALFORMED: Final[str] = "CONTEXT_MALFORMED"
REASON_LINEAGE_TAMPERED: Final[str] = "LINEAGE_TAMPERED"
REASON_LINEAGE_MALFORMED: Final[str] = "LINEAGE_MALFORMED"
REASON_CANARY_TOKEN_MALFORMED: Final[str] = "CANARY_TOKEN_MALFORMED"
REASON_OUTBOUND_MALFORMED: Final[str] = "OUTBOUND_MALFORMED"

#: Violation types.
VIOLATION_NONE: Final[str] = "NONE"
VIOLATION_REVOCATION_LEAK: Final[str] = "REVOCATION_LEAK"
VIOLATION_CROSS_PURPOSE: Final[str] = "CROSS_PURPOSE_LEAK"
VIOLATION_LINEAGE_LEAK: Final[str] = "LINEAGE_LEAK"


class RedisclosureProbeError(ValueError):
    """Raised when probe inputs are malformed, empty, or tampered (fail closed)."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code
        self.message = message


@dataclasses.dataclass(frozen=True)
class FieldObservation:
    """Byte-accurate observation of a single outbound payload field."""

    field_name: str
    byte_count: int
    sha256: str
    canary_detected: bool = False
    matched_tokens: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "canary_detected": self.canary_detected,
            "matched_tokens": list(self.matched_tokens),
        }


@dataclasses.dataclass(frozen=True)
class TenantPurposeContext:
    """Security context binding the probe to a specific tenant and purpose."""

    tenant_id: str
    purpose: str
    consent_epoch: int | None = None
    revocation_time: int | None = None
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "purpose": self.purpose,
            "consent_epoch": self.consent_epoch,
            "revocation_time": self.revocation_time,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, raw: Any) -> TenantPurposeContext:
        if raw is None or raw == "":
            raise RedisclosureProbeError(
                REASON_CONTEXT_EMPTY, "tenant_purpose_ctx cannot be None or empty"
            )
        if isinstance(raw, TenantPurposeContext):
            return raw
        if not isinstance(raw, Mapping):
            raise RedisclosureProbeError(
                REASON_CONTEXT_MALFORMED,
                f"tenant_purpose_ctx must be Mapping or TenantPurposeContext, got {type(raw).__name__}",
            )
        if len(raw) == 0:
            raise RedisclosureProbeError(
                REASON_CONTEXT_EMPTY, "tenant_purpose_ctx mapping cannot be empty"
            )

        tenant = raw.get("tenant_id") or raw.get("tenant") or raw.get("principal")
        purpose = raw.get("purpose")

        if not isinstance(tenant, str) or not tenant.strip():
            raise RedisclosureProbeError(
                REASON_CONTEXT_MALFORMED, "Context missing non-empty tenant identifier"
            )
        if not isinstance(purpose, str) or not purpose.strip():
            raise RedisclosureProbeError(
                REASON_CONTEXT_MALFORMED, "Context missing non-empty purpose"
            )

        epoch = raw.get("consent_epoch")
        if epoch is not None and (
            isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0
        ):
            raise RedisclosureProbeError(
                REASON_CONTEXT_MALFORMED, f"consent_epoch must be non-negative int, got {epoch!r}"
            )

        rev_time = raw.get("revocation_time")
        if rev_time is not None and (
            isinstance(rev_time, bool) or not isinstance(rev_time, int) or rev_time < 0
        ):
            raise RedisclosureProbeError(
                REASON_CONTEXT_MALFORMED,
                f"revocation_time must be non-negative int, got {rev_time!r}",
            )

        return cls(
            tenant_id=tenant.strip(),
            purpose=purpose.strip(),
            consent_epoch=epoch,
            revocation_time=rev_time,
            metadata=dict(raw.get("metadata", {})),
        )


def compute_lineage_digest(nodes: Iterable[str]) -> str:
    """Compute a deterministic SHA-256 digest over sorted lineage node identifiers."""
    cleaned = sorted(str(n).strip() for n in nodes if str(n).strip())
    raw = ":".join(cleaned).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclasses.dataclass(frozen=True)
class CacheLineage:
    """Lineage provenance container for cached context items."""

    nodes: tuple[str, ...] = ()
    digest: str | None = None
    is_tampered: bool = False
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "digest": self.digest,
            "is_tampered": self.is_tampered,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_input(cls, raw: Any) -> CacheLineage:
        if raw is None:
            raise RedisclosureProbeError(REASON_LINEAGE_MALFORMED, "cache_lineage cannot be None")
        if isinstance(raw, CacheLineage):
            return raw

        # Check LineageGraph duck typing
        if hasattr(raw, "nodes") and not isinstance(raw, Mapping):
            graph_nodes = raw.nodes
            if callable(graph_nodes):
                graph_nodes = graph_nodes()
            if isinstance(graph_nodes, Mapping):
                node_keys = tuple(str(k) for k in graph_nodes.keys())
            elif isinstance(graph_nodes, list | tuple | set | frozenset):
                node_keys = tuple(str(n) for n in graph_nodes)
            else:
                node_keys = ()
            # If graph has tampered or cycles
            if getattr(raw, "is_tampered", False):
                raise RedisclosureProbeError(
                    REASON_LINEAGE_TAMPERED, "Lineage graph marked as tampered"
                )
            digest = compute_lineage_digest(node_keys)
            return cls(nodes=node_keys, digest=digest)

        if isinstance(raw, Mapping):
            if raw.get("tampered") is True or raw.get("is_tampered") is True:
                raise RedisclosureProbeError(
                    REASON_LINEAGE_TAMPERED, "Lineage metadata indicates tampering"
                )
            if raw.get("has_cycle") is True or raw.get("cycle_detected") is True:
                raise RedisclosureProbeError(
                    REASON_LINEAGE_TAMPERED, "Lineage cycle detected (tampered)"
                )
            nodes_val = raw.get("nodes", raw.get("lineage", []))
            if not isinstance(nodes_val, list | tuple | set | frozenset):
                raise RedisclosureProbeError(
                    REASON_LINEAGE_MALFORMED, "Lineage nodes must be a sequence or set"
                )
            node_tuple = tuple(str(n) for n in nodes_val)
            expected_digest = compute_lineage_digest(node_tuple)

            provided_digest = raw.get("digest")
            if provided_digest is not None:
                if str(provided_digest).strip() != expected_digest:
                    raise RedisclosureProbeError(
                        REASON_LINEAGE_TAMPERED,
                        f"Lineage digest mismatch: {provided_digest!r} != {expected_digest!r}",
                    )

            return cls(
                nodes=node_tuple,
                digest=expected_digest,
                is_tampered=False,
                metadata=dict(raw.get("metadata", {})),
            )

        if isinstance(raw, list | tuple | set | frozenset):
            for item in raw:
                if not isinstance(item, str) or not item.strip():
                    raise RedisclosureProbeError(
                        REASON_LINEAGE_MALFORMED,
                        f"Lineage node must be non-empty string, got {item!r}",
                    )
            node_tuple = tuple(str(n) for n in raw)
            return cls(nodes=node_tuple, digest=compute_lineage_digest(node_tuple))

        raise RedisclosureProbeError(
            REASON_LINEAGE_MALFORMED,
            f"Unsupported cache_lineage format: {type(raw).__name__}",
        )


def _validate_lineage_integrity(lineage: CacheLineage) -> None:
    """Validate that CacheLineage has not been tampered with."""
    if lineage.is_tampered:
        raise RedisclosureProbeError(
            REASON_LINEAGE_TAMPERED, "CacheLineage integrity failure: is_tampered is True"
        )
    if lineage.digest is not None:
        expected = compute_lineage_digest(lineage.nodes)
        if lineage.digest != expected:
            raise RedisclosureProbeError(
                REASON_LINEAGE_TAMPERED,
                f"CacheLineage digest mismatch: {lineage.digest!r} != {expected!r}",
            )


@dataclasses.dataclass(frozen=True)
class ProbeResult:
    """Result of black-box outbound payload probe for canary leakage."""

    canary_detected: bool
    violation_type: str
    matched_tokens: list[str]
    byte_count: int
    field_observations: tuple[FieldObservation, ...]
    tenant_id: str
    purpose: str
    lineage_digest: str | None = None
    reason_code: str = REASON_PROBE_CLEAN
    model_internals_inspected: bool = False
    observation_metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "canary_detected": self.canary_detected,
            "violation_type": self.violation_type,
            "matched_tokens": list(self.matched_tokens),
            "byte_count": self.byte_count,
            "field_observations": [f.to_dict() for f in self.field_observations],
            "tenant_id": self.tenant_id,
            "purpose": self.purpose,
            "lineage_digest": self.lineage_digest,
            "reason_code": self.reason_code,
            "model_internals_inspected": self.model_internals_inspected,
            "observation_metadata": dict(self.observation_metadata),
        }


@dataclasses.dataclass(frozen=True)
class DisclosureReport:
    """Aggregated disclosure audit report across one or more outbound dispatches."""

    report_id: str
    canary_detected: bool
    results: tuple[ProbeResult, ...]
    total_byte_count: int
    matched_tokens: list[str]
    violation_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "canary_detected": self.canary_detected,
            "results": [r.to_dict() for r in self.results],
            "total_byte_count": self.total_byte_count,
            "matched_tokens": list(self.matched_tokens),
            "violation_count": self.violation_count,
        }


def _normalize_string(text: str) -> str:
    """NFKC-normalize and casefold string for robust casing/normalization matching."""
    return unicodedata.normalize("NFKC", text).casefold()


def _extract_fields(outbound_response: Any) -> list[tuple[str, str]]:
    """Extract named fields from outbound response object or string."""
    if outbound_response is None:
        raise RedisclosureProbeError(REASON_OUTBOUND_MALFORMED, "outbound_response cannot be None")

    if isinstance(outbound_response, str):
        return [("payload", outbound_response)]

    if isinstance(outbound_response, bytes):
        return [("payload", outbound_response.decode("utf-8", errors="replace"))]

    if hasattr(outbound_response, "to_dict") and callable(outbound_response.to_dict):
        return _extract_fields(outbound_response.to_dict())

    if isinstance(outbound_response, Mapping):
        fields: list[tuple[str, str]] = []
        for k, v in outbound_response.items():
            field_name = str(k)
            if isinstance(v, str):
                val_str = v
            elif isinstance(v, bytes):
                val_str = v.decode("utf-8", errors="replace")
            elif isinstance(v, int | float | bool):
                val_str = str(v)
            elif isinstance(v, dict | list | tuple):
                val_str = json.dumps(v, sort_keys=True)
            elif v is None:
                val_str = ""
            else:
                val_str = str(v)
            fields.append((field_name, val_str))
        return fields

    if isinstance(outbound_response, list | tuple):
        fields = []
        for i, item in enumerate(outbound_response):
            if isinstance(item, str):
                fields.append((f"item_{i}", item))
            else:
                fields.append((f"item_{i}", json.dumps(item, default=str)))
        return fields

    # Fallback to string representation of object
    return [("payload", str(outbound_response))]


def _validate_canary_tokens(canary_tokens: Any) -> list[str]:
    """Validate canary token collection and refuse malformed or empty tokens."""
    if canary_tokens is None:
        return []

    if isinstance(canary_tokens, str | bytes):
        token_str = (
            canary_tokens
            if isinstance(canary_tokens, str)
            else canary_tokens.decode("utf-8", errors="replace")
        )
        canary_tokens = [token_str]

    if isinstance(canary_tokens, Mapping):
        canary_tokens = list(canary_tokens.keys())

    if not isinstance(canary_tokens, Iterable):
        raise RedisclosureProbeError(
            REASON_CANARY_TOKEN_MALFORMED,
            f"canary_tokens must be an iterable, got {type(canary_tokens).__name__}",
        )

    cleaned_tokens: list[str] = []
    for token in canary_tokens:
        if not isinstance(token, str):
            raise RedisclosureProbeError(
                REASON_CANARY_TOKEN_MALFORMED,
                f"Canary token must be a string, got {type(token).__name__}: {token!r}",
            )
        if not token.strip():
            raise RedisclosureProbeError(
                REASON_CANARY_TOKEN_MALFORMED,
                "Canary token cannot be empty or whitespace-only",
            )
        cleaned_tokens.append(token.strip())

    return cleaned_tokens


def probe_redisclosure(
    outbound_response: Any,
    canary_tokens: Any,
    tenant_purpose_ctx: Any,
    cache_lineage: Any,
    *,
    violation_type: str | None = None,
) -> ProbeResult:
    """Record byte-accurate outbound field observations and detect revoked canary leakage.

    Operates strictly as a black-box observer (does NOT scan model internals).
    Detects if any canary token belonging to a revoked context appears in outbound payload.
    Supports casing and unicode normalization matching.

    Parameters
    ----------
    outbound_response:
        The payload dispatched outbound (str, bytes, mapping, or serializable object).
    canary_tokens:
        Synthetic canary strings to detect. Empty tokens are refused.
    tenant_purpose_ctx:
        Tenant and purpose binding. Empty context is refused fail-closed.
    cache_lineage:
        Provenance metadata for the cached context. Tampered lineage is refused fail-closed.
    violation_type:
        Optional override for the violation type string when a leak is detected.
        Defaults to ``REVOCATION_LEAK``.

    Returns
    -------
    ProbeResult:
        Typed result containing ``canary_detected``, ``violation_type``, ``matched_tokens``,
        byte counts, and per-field observations.
    """
    # 1. Validate tenant/purpose context (empty context refused fail-closed)
    ctx = TenantPurposeContext.from_mapping(tenant_purpose_ctx)

    # 2. Validate cache lineage (tampered lineage refused fail-closed)
    lineage = CacheLineage.from_input(cache_lineage)
    _validate_lineage_integrity(lineage)

    # 3. Validate canary tokens (empty/whitespace/non-string tokens refused fail-closed)
    tokens = _validate_canary_tokens(canary_tokens)

    # 4. Extract byte-accurate outbound fields (black-box observation)
    fields = _extract_fields(outbound_response)

    # Pre-compute normalized canary representations for casing/normalization checks
    token_pairs = [(tok, _normalize_string(tok)) for tok in tokens]

    field_observations: list[FieldObservation] = []
    global_matched: set[str] = set()

    for field_name, field_text in fields:
        raw_bytes = field_text.encode("utf-8")
        byte_count = len(raw_bytes)
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # Black-box string inspection: check exact and normalized match
        field_norm = _normalize_string(field_text)
        field_matched: list[str] = []

        for original_token, norm_token in token_pairs:
            # Check both exact substring and normalized substring
            if original_token in field_text or norm_token in field_norm:
                field_matched.append(original_token)
                global_matched.add(original_token)

        obs = FieldObservation(
            field_name=field_name,
            byte_count=byte_count,
            sha256=sha256,
            canary_detected=bool(field_matched),
            matched_tokens=tuple(sorted(field_matched)),
        )
        field_observations.append(obs)

    sorted_matched = sorted(global_matched)
    detected = len(sorted_matched) > 0
    total_bytes = sum(obs.byte_count for obs in field_observations)

    active_violation = (violation_type or VIOLATION_REVOCATION_LEAK) if detected else VIOLATION_NONE
    reason = REASON_CANARY_DETECTED if detected else REASON_PROBE_CLEAN

    return ProbeResult(
        canary_detected=detected,
        violation_type=active_violation,
        matched_tokens=sorted_matched,
        byte_count=total_bytes,
        field_observations=tuple(field_observations),
        tenant_id=ctx.tenant_id,
        purpose=ctx.purpose,
        lineage_digest=lineage.digest,
        reason_code=reason,
        model_internals_inspected=False,  # strictly black-box observer
        observation_metadata={
            "consent_epoch": ctx.consent_epoch,
            "revocation_time": ctx.revocation_time,
            "lineage_node_count": len(lineage.nodes),
        },
    )


def probe(history: Any, config: Mapping[str, Any]) -> DisclosureReport:
    """Audit outbound dispatches in history against config parameters.

    Conforms to the ``probe(history, config)->DisclosureReport`` signature declared in
    the POPETS task registry.
    """
    if not isinstance(config, Mapping):
        raise RedisclosureProbeError(
            REASON_CONTEXT_MALFORMED,
            f"config must be a Mapping, got {type(config).__name__}",
        )

    canary_tokens = config.get("canary_tokens", [])
    ctx = config.get("tenant_purpose_ctx") or config.get("context")
    lineage = config.get("cache_lineage") or config.get("lineage")

    items: list[Any]
    if isinstance(history, list | tuple):
        items = list(history)
    else:
        items = [history]

    results: list[ProbeResult] = []
    for item in items:
        res = probe_redisclosure(
            outbound_response=item,
            canary_tokens=canary_tokens,
            tenant_purpose_ctx=ctx,
            cache_lineage=lineage,
        )
        results.append(res)

    all_matched = sorted(list(set(t for r in results for t in r.matched_tokens)))
    any_detected = any(r.canary_detected for r in results)
    total_bytes = sum(r.byte_count for r in results)
    violations = sum(1 for r in results if r.canary_detected)

    rep_digest = hashlib.sha256(
        f"{len(results)}:{total_bytes}:{len(all_matched)}".encode()
    ).hexdigest()[:16]

    return DisclosureReport(
        report_id=f"rep-{rep_digest}",
        canary_detected=any_detected,
        results=tuple(results),
        total_byte_count=total_bytes,
        matched_tokens=all_matched,
        violation_count=violations,
    )
