"""Resource preservation and temporal-mapping comparators (H-005/H-006).

All metrics are computed offline from fixtures and the product's real gates.
Where a quantity cannot be measured without the live app (DB-backed endpoint
replay protection, Consent/Provenance candidate retention), the metric is
reported with ``na: true`` and an explicit note — never invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

try:  # pragma: no cover - import guard
    from clara_api.lifemap.fhir_r4 import (
        build_summary_bundle,  # type: ignore[import-not-found]
    )
except ImportError:  # pragma: no cover
    build_summary_bundle = None  # type: ignore[assignment]

from evaluation.commitloop.fhir_ingest import SUPPORTED_RESOURCE_TYPES_BY_VERSION
from evaluation.fhir_conformance.app_semantic import GateResult

NON_CANDIDATE_TYPES = frozenset({"Provenance", "Consent", "AuditEvent", "Composition"})

_SUBJECT_REJECTION_CATEGORIES = frozenset(
    {
        "missing_patient",
        "multiple_patient",
        "wrong_patient_reference",
        "cross_subject_reference",
    }
)


@dataclass
class Metric:
    name: str
    n: int | None
    d: int | None
    ratio: float | None
    na: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "n": self.n,
            "d": self.d,
            "numerator": self.d,
            "denominator": self.n,
            "ratio": self.ratio,
            "na": self.na,
            "note": self.note,
        }


def _normalize_instant(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().isoformat()


def _matchable(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def resource_preservation(bundle: dict[str, Any], result: GateResult, *, gate: str) -> Metric:
    """N/D: source resources that survive the gate as candidates/events."""
    expected: list[str] = []
    preserved: list[str] = []
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        rtype = resource.get("resourceType")
        rid = resource.get("id")
        if not isinstance(rtype, str) or not isinstance(rid, str):
            continue
        key = f"{rtype}/{rid}"
        if gate == "api_r4" and rtype in NON_CANDIDATE_TYPES:
            continue
        if gate.startswith("bench"):
            version = "STU3" if gate == "bench_stu3" else "R4"
            if rtype not in SUPPORTED_RESOURCE_TYPES_BY_VERSION[version]:
                continue
        if gate.startswith("bench") and rtype == "Patient":
            continue
        expected.append(key)
        if result.available and result.accepted:
            if gate == "api_r4":
                for candidate in _api_candidates(result):
                    if (
                        candidate.get("resource_type") == rtype
                        and candidate.get("resource_id") == rid
                    ):
                        preserved.append(key)
            else:
                for event in _bench_events(result):
                    if event.get("evidence_id") == key:
                        preserved.append(key)
    return Metric(
        name="resource_preservation_accuracy",
        n=len(expected),
        d=len(preserved),
        ratio=len(preserved) / len(expected) if expected else None,
        na=not result.available,
        note=(
            "gate_unavailable"
            if not result.available
            else f"gate={gate}; non-event types excluded per ingest policy"
        ),
    )


def _api_candidates(result: GateResult) -> list[dict[str, Any]]:
    return [c["value"] for c in result.candidates]


def _api_raw_candidates(result: GateResult) -> list[dict[str, Any]]:
    return result.candidates


def _bench_events(result: GateResult) -> list[dict[str, Any]]:
    return [e for e in result.events if isinstance(e, dict)]


def source_reference_reconstruction(
    bundle: dict[str, Any], result: GateResult, *, gate: str
) -> Metric:
    """N/D: candidates/events that retain their source identity (id/fullUrl)."""
    full_urls = {
        e.get("fullUrl")
        for e in bundle.get("entry") or []
        if isinstance(e, dict) and isinstance(e.get("fullUrl"), str)
    }
    expected: list[str] = []
    reconstructed: list[str] = []
    if gate == "api_r4" and result.available and result.accepted:
        for candidate in _api_raw_candidates(result):
            value = candidate["value"]
            identity = f"{value['resource_type']}/{value['resource_id']}"
            expected.append(identity)
            span = candidate.get("source_span") or {}
            if (
                isinstance(span.get("full_url"), str)
                and span["full_url"] in full_urls
                and _matchable(value.get("resource_id"))
            ):
                reconstructed.append(identity)
    elif gate.startswith("bench") and result.available and result.accepted:
        for event in _bench_events(result):
            expected.append(event["evidence_id"])
            rtype, rid = event["evidence_id"].split("/", 1)
            if any(
                isinstance(e, dict)
                and (e.get("resource") or {}).get("resourceType") == rtype
                and (e.get("resource") or {}).get("id") == rid
                for e in bundle.get("entry") or []
            ):
                reconstructed.append(event["evidence_id"])
    return Metric(
        name="source_reference_reconstruction",
        n=len(expected),
        d=len(reconstructed),
        ratio=len(reconstructed) / len(expected) if expected else None,
        na=not result.available or not result.accepted,
        note=(
            "gate_unavailable_or_rejected"
            if not result.available or not result.accepted
            else (
                f"gate={gate}; resource_type/resource_id traced to bundle entry; "
                "bench TimelineEvent does not retain Bundle.fullUrl"
            )
        ),
    )


def subject_rejection_accuracy(
    fixtures: list[dict[str, Any]],
    results: dict[str, dict[str, GateResult]],
    *,
    gate: str,
) -> Metric:
    """N/D: negative subject fixtures correctly rejected by the gate."""
    candidates_fixtures = [
        f
        for f in fixtures
        if f.get("category") in _SUBJECT_REJECTION_CATEGORIES and gate in f.get("gates", [])
    ]
    rejected = 0
    for fixture in candidates_fixtures:
        gate_result = (results.get(fixture["id"]) or {}).get(gate)
        if gate_result is not None and gate_result.available and gate_result.accepted is False:
            rejected += 1
    return Metric(
        name="subject_rejection_accuracy",
        n=len(candidates_fixtures),
        d=rejected,
        ratio=rejected / len(candidates_fixtures) if candidates_fixtures else None,
        note=f"gate={gate}; categories={sorted(_SUBJECT_REJECTION_CATEGORIES)}",
    )


def supported_resource_acceptance(
    fixtures: list[dict[str, Any]],
    results: dict[str, dict[str, GateResult]],
    *,
    gate: str,
) -> Metric:
    """N/D: fixtures the gate is expected to accept are accepted."""
    expected_accept = [
        f for f in fixtures if (f.get("expected") or {}).get(gate, {}).get("accepted") is True
    ]
    accepted = 0
    for fixture in expected_accept:
        gate_result = (results.get(fixture["id"]) or {}).get(gate)
        if gate_result is not None and gate_result.accepted is True:
            accepted += 1
    return Metric(
        name="supported_resource_acceptance",
        n=len(expected_accept),
        d=accepted,
        ratio=accepted / len(expected_accept) if expected_accept else None,
        note=f"gate={gate}; denominators from fixture manifest expected-accept set",
    )


def export_temporal_mapping(snapshot: dict[str, Any]) -> Metric:
    """N/D: canonical snapshot temporal fields round-trip into the R4 export.

    Uses the production mapper (``build_summary_bundle``) as a pure function.
    """
    if build_summary_bundle is None:
        return Metric(
            name="temporal_mapping_correctness_export",
            n=None,
            d=None,
            ratio=None,
            na=True,
            note="oracle_unavailable: clara_api.lifemap.fhir_r4 not importable",
        )
    bundle = build_summary_bundle(
        snapshot,
        export_id="temporal-probe-1",
        generated_at=datetime.fromisoformat("2026-07-29T08:00:00+00:00"),
        purpose="self_download",
        include={
            "demographics",
            "observations",
            "medications",
            "care_plan",
            "answers",
            "documents",
        },
    )
    by_id = {
        e.get("resource", {}).get("id"): e.get("resource", {}) for e in bundle.get("entry") or []
    }
    pairs: list[tuple[str, str]] = []
    for event in snapshot.get("events") or []:
        if isinstance(event, dict) and _matchable(event.get("occurred_at")):
            obs = by_id.get(event.get("public_id")) or {}
            if _matchable(obs.get("effectiveDateTime")):
                pairs.append((str(event["occurred_at"]), str(obs["effectiveDateTime"])))
    for item in snapshot.get("medications") or []:
        if not isinstance(item, dict):
            continue
        med = by_id.get(item.get("public_id")) or {}
        period = med.get("effectivePeriod") or {}
        for key, source in (("start", "started_at"), ("end", "ended_at")):
            if _matchable(item.get(source)) and _matchable(period.get(key)):
                pairs.append((str(item[source]), str(period[key])))
    for task in snapshot.get("tasks") or []:
        if isinstance(task, dict) and _matchable(task.get("created_at")):
            t = by_id.get(task.get("public_id")) or {}
            if _matchable(t.get("authoredOn")):
                pairs.append((str(task["created_at"]), str(t["authoredOn"])))
    for answer in snapshot.get("answers") or []:
        if isinstance(answer, dict) and _matchable(answer.get("occurred_at")):
            q = by_id.get(answer.get("public_id")) or {}
            if _matchable(q.get("authored")):
                pairs.append((str(answer["occurred_at"]), str(q["authored"])))
    for document in snapshot.get("documents") or []:
        if isinstance(document, dict) and _matchable(document.get("created_at")):
            d = by_id.get(document.get("public_id")) or {}
            if _matchable(d.get("date")):
                pairs.append((str(document["created_at"]), str(d["date"])))
    matches = 0
    for source, emitted in pairs:
        try:
            if _normalize_instant(source) == _normalize_instant(emitted):
                matches += 1
        except ValueError:
            continue
    return Metric(
        name="temporal_mapping_correctness_export",
        n=len(pairs),
        d=matches,
        ratio=matches / len(pairs) if pairs else None,
        note="snapshot -> R4 export via production mapper (pure function)",
    )


def bench_temporal_mapping(bundle: dict[str, Any], result: GateResult) -> Metric:
    """N/D: recognized source temporal fields reconstructed into event valid_at."""
    pairs: list[tuple[str, str]] = []
    for event in _bench_events(result):
        source = event.get("source") or {}
        valid_at = event.get("valid_at")
        recognized = (
            source.get("authoredOn")
            or source.get("issued")
            or source.get("effectiveDateTime")
            or source.get("performedDateTime")
            or source.get("recordedDate")
            or source.get("onsetDateTime")
        )
        if isinstance(recognized, str) and valid_at is not None:
            pairs.append((recognized, valid_at.isoformat()))
    matches = 0
    for source, emitted in pairs:
        try:
            if _normalize_instant(source) == _normalize_instant(emitted):
                matches += 1
        except ValueError:
            continue
    return Metric(
        name="temporal_mapping_correctness_bench",
        n=len(pairs),
        d=matches,
        ratio=matches / len(pairs) if pairs else None,
        note=(
            "recognized source fields -> TimelineEvent.valid_at; fields not in the "
            "bench candidate list (e.g. STU3 occurrenceDateTime) are counted as gaps"
        ),
    )


def unsupported_behavior(
    fixtures: list[dict[str, Any]],
    results: dict[str, dict[str, GateResult]],
) -> list[dict[str, Any]]:
    """Recorded behavior for unsupported-resource fixtures per gate."""
    behavior: list[dict[str, Any]] = []
    for fixture in fixtures:
        if fixture.get("category") != "resource_unsupported":
            continue
        row: dict[str, Any] = {
            "fixture_id": fixture["id"],
            "path": fixture["path"],
            "modes": sorted((results.get(fixture["id"]) or {}).keys()),
        }
        for gate, result in (results.get(fixture["id"]) or {}).items():
            row[gate] = {
                "accepted": result.accepted,
                "errors": result.errors,
                "dropped_types": result.dropped_types,
            }
        behavior.append(row)
    return behavior


def provenance_candidate_retention(
    fixtures: list[dict[str, Any]],
    bundles: dict[str, dict[str, Any]],
    results: dict[str, dict[str, GateResult]],
) -> Metric:
    """Report the product's explicit policy for imported Provenance resources."""
    expected = 0
    retained = 0
    for fixture in fixtures:
        if fixture.get("category") != "provenance_loss":
            continue
        bundle = bundles.get(fixture["id"], {})
        provenance_ids = {
            (entry.get("resource") or {}).get("id")
            for entry in bundle.get("entry") or []
            if (entry.get("resource") or {}).get("resourceType") == "Provenance"
        }
        provenance_ids.discard(None)
        expected += len(provenance_ids)
        api_result = (results.get(fixture["id"]) or {}).get("api_r4")
        if api_result is not None and api_result.available and api_result.accepted:
            retained += sum(
                1
                for candidate in _api_candidates(api_result)
                if candidate.get("resource_type") == "Provenance"
                and candidate.get("resource_id") in provenance_ids
            )
    return Metric(
        name="provenance_candidate_retention",
        n=expected,
        d=retained,
        ratio=retained / expected if expected else None,
        na=expected == 0,
        note=("Provenance is parsed but excluded from import candidates by product policy"),
    )


def compute_metrics(
    manifest: dict[str, Any],
    bundles: dict[str, dict[str, Any]],
    results: dict[str, dict[str, GateResult]],
) -> dict[str, Any]:
    fixtures = manifest["fixtures"]
    gate_names = {gate for fixture in fixtures for gate in (fixture.get("expected") or {})}
    metrics: dict[str, Any] = {}
    for gate in sorted(gate_names):
        if not gate.startswith(("api_", "bench_")):
            continue
        accepted_fixtures = [
            f for f in fixtures if (f.get("expected") or {}).get(gate, {}).get("accepted") is True
        ]
        if not accepted_fixtures:
            continue
        preservation: list[Metric] = []
        reconstruction: list[Metric] = []
        for fixture in accepted_fixtures:
            bundle = bundles.get(fixture["id"])
            result = (results.get(fixture["id"]) or {}).get(gate)
            if bundle is None or result is None:
                continue
            preservation.append(resource_preservation(bundle, result, gate=gate))
            reconstruction.append(source_reference_reconstruction(bundle, result, gate=gate))
        metrics[f"{gate}_resource_preservation"] = _combine(
            f"resource_preservation_accuracy:{gate}", preservation
        )
        metrics[f"{gate}_source_reference"] = _combine(
            f"source_reference_reconstruction:{gate}", reconstruction
        )
        metrics[f"{gate}_acceptance"] = supported_resource_acceptance(
            fixtures, results, gate=gate
        ).to_dict()
        metrics[f"{gate}_subject_rejection"] = subject_rejection_accuracy(
            fixtures, results, gate=gate
        ).to_dict()
    metrics["temporal_mapping_export"] = (
        export_temporal_mapping(bundles.get("snapshot_input") or {}).to_dict()
        if "snapshot_input" in bundles
        else {
            "name": "temporal_mapping_correctness_export",
            "n": None,
            "d": None,
            "ratio": None,
            "na": True,
            "note": "no snapshot input fixture",
        }
    )
    for gate in ("bench_r4", "bench_stu3"):
        bench_metrics = []
        for fixture in fixtures:
            result = (results.get(fixture["id"]) or {}).get(gate)
            bundle = bundles.get(fixture["id"])
            if result is not None and result.accepted and bundle is not None:
                bench_metrics.append(bench_temporal_mapping(bundle, result))
        metrics[f"{gate}_temporal_mapping"] = _combine(
            f"temporal_mapping_correctness:{gate}", bench_metrics
        )
    metrics["unsupported_behavior"] = unsupported_behavior(fixtures, results)
    metrics["provenance_candidate_retention"] = provenance_candidate_retention(
        fixtures, bundles, results
    ).to_dict()
    return metrics


def _combine(name: str, metrics: list[Metric]) -> dict[str, Any]:
    if not metrics:
        return Metric(
            name=name,
            n=0,
            d=0,
            ratio=None,
            na=True,
            note="no applicable fixtures",
        ).to_dict()
    n = sum(m.n or 0 for m in metrics)
    d = sum(m.d or 0 for m in metrics)
    na = all(m.na for m in metrics)
    notes = sorted({m.note for m in metrics if m.note})
    return {
        "name": name,
        "n": n,
        "d": d,
        "numerator": d,
        "denominator": n,
        "ratio": (d / n) if n and not na else None,
        "na": na,
        "note": "; ".join(notes) if notes else "",
    }
