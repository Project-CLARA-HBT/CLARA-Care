"""CLARA application-semantic gates for FHIR fixtures (H-002/H-004).

These re-run the product's real acceptance logic — not a reimplementation —
against each fixture:

- ``api_r4_gate`` replays the production LifeMap FHIR R4 import gate
  (``clara_api.lifemap.fhir_r4.validate_bundle`` + ``import_candidates``).
- ``bench_gate`` replays the GLHS CommitLoop bench ingestion
  (``evaluation.commitloop.fhir_ingest.ingest_bundle``) for R4 or STU3.

If a gate's dependencies are unavailable (wrong interpreter/`PYTHONPATH`), the
result is recorded with ``available: false`` and ``accepted: None`` rather than
guessing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from evaluation.commitloop.fhir_ingest import (
    SUPPORTED_RESOURCE_TYPES_BY_VERSION,
    FhirIngestError,
    ingest_bundle,
)

try:  # pragma: no cover - import guard
    from clara_api.lifemap.fhir_r4 import (  # type: ignore[import-not-found]
        FhirValidationError,
        import_candidates,
        validate_bundle,
    )
except ImportError:  # pragma: no cover
    FhirValidationError = None  # type: ignore[assignment]
    import_candidates = None  # type: ignore[assignment]
    validate_bundle = None  # type: ignore[assignment]


@dataclass
class GateResult:
    gate: str
    version: str
    available: bool
    accepted: bool | None
    errors: list[str] = field(default_factory=list)
    candidate_count: int = 0
    event_count: int = 0
    candidates: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    dropped_types: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


def api_r4_gate(bundle: dict[str, Any]) -> GateResult:
    """Replay the production LifeMap R4 import gate."""
    if validate_bundle is None or import_candidates is None:
        return GateResult(
            gate="api_r4",
            version="4.0.1",
            available=False,
            accepted=None,
            notes=["oracle_unavailable: clara_api.lifemap.fhir_r4 not importable"],
        )
    try:
        validate_bundle(bundle)
    except FhirValidationError as error:
        return GateResult(
            gate="api_r4",
            version="4.0.1",
            available=True,
            accepted=False,
            errors=list(error.errors),
        )
    candidates = import_candidates(bundle)
    return GateResult(
        gate="api_r4",
        version="4.0.1",
        available=True,
        accepted=True,
        candidate_count=len(candidates),
        candidates=candidates,
    )


def bench_gate(bundle: dict[str, Any], version: str) -> GateResult:
    """Replay the GLHS CommitLoop bench ingestion for R4 or STU3."""
    version = version.upper()
    try:
        _token, events = ingest_bundle(bundle, fhir_version=version, ingested_at=_now())
    except FhirIngestError as error:
        return GateResult(
            gate=f"bench_{version.lower()}",
            version=version,
            available=True,
            accepted=False,
            errors=[str(error)],
        )
    supported = SUPPORTED_RESOURCE_TYPES_BY_VERSION.get(version, frozenset())
    dropped: list[str] = []
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        if resource.get("resourceType") not in supported:
            dropped.append(f"{resource.get('resourceType')}/{resource.get('id') or '?'}")
    return GateResult(
        gate=f"bench_{version.lower()}",
        version=version,
        available=True,
        accepted=True,
        event_count=len(events),
        events=[asdict(event) for event in events],
        dropped_types=sorted(dropped),
        notes=["unsupported_resources_silently_dropped"] if dropped else [],
    )
