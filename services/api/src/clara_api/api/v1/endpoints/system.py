from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.control_tower import get_control_tower_config_service
from clara_api.core.flow import FLOW_EVENTS_DEFAULT_LIMIT, get_flow_event_stream_service
from clara_api.core.metrics import get_api_metrics_store
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.session import get_db
from clara_api.schemas import (
    CareguardRuntimeConfig,
    SystemControlTowerConfig,
    SystemSourcesRegistryResponse,
)

router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _utc_ago_iso(*, minutes: int = 0, hours: int = 0) -> str:
    return (datetime.now(tz=UTC) - timedelta(minutes=minutes, hours=hours)).isoformat()


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _safe_iso_to_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def _status_from_ratio(value: float, *, warn: float, critical: float) -> str:
    if value >= critical:
        return "down"
    if value >= warn:
        return "degraded"
    return "ok"


def _minutes_since(now_utc: datetime, when_utc: datetime | None) -> float | None:
    if when_utc is None:
        return None
    delta = now_utc - when_utc
    return max(delta.total_seconds() / 60.0, 0.0)


@router.get("/metrics")
def get_metrics(
    _token: TokenPayload = Depends(require_roles("doctor")),
) -> dict[str, object]:
    return get_api_metrics_store().snapshot()


@router.get("/dependencies")
def get_dependencies(
    _token: TokenPayload = Depends(require_roles("doctor")),
) -> dict[str, object]:
    settings = get_settings()
    health_url = f"{settings.ml_service_url.rstrip('/')}/health"
    ml_status: dict[str, object] = {"url": health_url}
    headers: dict[str, str] = {}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()

    try:
        request_kwargs: dict[str, Any] = {"timeout": settings.ml_service_timeout_seconds}
        if headers:
            request_kwargs["headers"] = headers
        response = httpx.get(health_url, **request_kwargs)
        ml_status["reachable"] = response.status_code < 500
        ml_status["status"] = "ok" if response.status_code < 400 else "unhealthy"
        ml_status["upstream_status_code"] = response.status_code
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        ml_status["reachable"] = False
        ml_status["status"] = "unreachable"
        ml_status["detail"] = f"{exc.__class__.__name__}: {exc}"
    except httpx.HTTPError as exc:
        ml_status["reachable"] = False
        ml_status["status"] = "unreachable"
        ml_status["detail"] = str(exc)

    overall_status = "ok" if ml_status.get("status") == "ok" else "degraded"
    return {"status": overall_status, "dependencies": {"ml": ml_status}}


@router.get("/ecosystem")
def get_ecosystem(
    _token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    now_utc = datetime.now(tz=UTC)
    generated_at = now_utc.isoformat()

    metrics_snapshot = get_api_metrics_store().snapshot()
    requests_total = _to_int(metrics_snapshot.get("requests_total"), 0)
    avg_latency_ms = _to_float(metrics_snapshot.get("avg_latency_ms"), 0.0)
    by_status_raw = metrics_snapshot.get("by_status")
    by_status = by_status_raw if isinstance(by_status_raw, dict) else {}
    status_total = sum(max(_to_int(value, 0), 0) for value in by_status.values())
    effective_total = max(requests_total, status_total, 1)
    status_5xx = sum(
        max(_to_int(value, 0), 0)
        for key, value in by_status.items()
        if str(key).startswith("5")
    )
    error_rate_pct = round((status_5xx / effective_total) * 100.0, 3)
    api_status = _status_from_ratio(error_rate_pct, warn=2.0, critical=8.0)

    probe_started = datetime.now(tz=UTC)
    dependency_snapshot = get_dependencies(_token=_token)
    probe_finished = datetime.now(tz=UTC)
    probe_latency_ms = max((probe_finished - probe_started).total_seconds() * 1000.0, 0.0)
    deps_obj = dependency_snapshot.get("dependencies")
    deps = deps_obj if isinstance(deps_obj, dict) else {}
    ml_dep_obj = deps.get("ml")
    ml_dep = ml_dep_obj if isinstance(ml_dep_obj, dict) else {}
    ml_status_text = str(ml_dep.get("status") or "unknown").strip().lower()
    ml_reachable = bool(ml_dep.get("reachable", False))
    ml_error_rate_pct = 0.0 if ml_reachable and ml_status_text == "ok" else 100.0
    if ml_status_text == "ok":
        ml_status = "ok"
    elif ml_status_text in {"unhealthy", "degraded"}:
        ml_status = "degraded"
    else:
        ml_status = "down"

    stream_service = get_flow_event_stream_service()
    flow_snapshot = stream_service.list_events(limit=FLOW_EVENTS_DEFAULT_LIMIT)
    items_obj = flow_snapshot.get("items")
    flow_items = items_obj if isinstance(items_obj, list) else []

    latest_event_time: datetime | None = None
    flow_missing_count = 0
    flow_error_like_count = 0
    source_last_seen: dict[str, datetime] = {}

    for item in flow_items:
        if not isinstance(item, dict):
            continue
        item_time = _safe_iso_to_utc(item.get("timestamp"))
        if item_time and (latest_event_time is None or item_time > latest_event_time):
            latest_event_time = item_time
        if bool(item.get("flow_events_missing")):
            flow_missing_count += 1

        source_text = str(item.get("source") or "").strip().lower()
        if source_text and item_time is not None:
            prev = source_last_seen.get(source_text)
            if prev is None or item_time > prev:
                source_last_seen[source_text] = item_time

        event_obj = item.get("event")
        event = event_obj if isinstance(event_obj, dict) else {}
        event_status = str(event.get("status") or "").strip().lower()
        if event_status in {"error", "failed"}:
            flow_error_like_count += 1

        payload_obj = event.get("payload")
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        for source_key in ("source", "provider", "connector"):
            source_value = str(payload.get(source_key) or "").strip().lower()
            if source_value and item_time is not None:
                prev = source_last_seen.get(source_value)
                if prev is None or item_time > prev:
                    source_last_seen[source_value] = item_time

    latest_event_iso = latest_event_time.isoformat() if latest_event_time else ""
    minutes_since_last_event = _minutes_since(now_utc, latest_event_time)
    flow_stale = minutes_since_last_event is None or minutes_since_last_event > 30.0
    flow_error_ratio = (
        flow_error_like_count / max(len(flow_items), 1) if flow_items else 1.0
    )
    if flow_stale:
        flow_status = "down" if not flow_items else "degraded"
    elif flow_error_ratio >= 0.2:
        flow_status = "degraded"
    else:
        flow_status = "ok"

    partner_health: list[dict[str, object]] = [
        {
            "partner": "api_runtime",
            "status": api_status,
            "latency_ms": round(avg_latency_ms, 3),
            "error_rate_pct": error_rate_pct,
            "last_check": generated_at,
            "requests_total": requests_total,
            "status_5xx": status_5xx,
        },
        {
            "partner": "ml_dependency",
            "status": ml_status,
            "latency_ms": round(probe_latency_ms, 3),
            "error_rate_pct": round(ml_error_rate_pct, 3),
            "last_check": generated_at,
            "reachable": ml_reachable,
            "upstream_status_code": ml_dep.get("upstream_status_code"),
            "detail": ml_dep.get("detail"),
        },
        {
            "partner": "flow_event_stream",
            "status": flow_status,
            "latency_ms": 0.0,
            "error_rate_pct": round(flow_error_ratio * 100.0, 3),
            "last_check": latest_event_iso or generated_at,
            "events_sampled": len(flow_items),
            "flow_events_missing": flow_missing_count,
        },
    ]

    control_tower_config = get_control_tower_config_service().load(db)
    rag_sources = list(control_tower_config.rag_sources)
    max_priority = max((max(source.priority, 1) for source in rag_sources), default=1)

    data_trust_scores: list[dict[str, object]] = []
    for source in rag_sources:
        normalized_source = source.id.strip().lower()
        source_last_refresh = source_last_seen.get(normalized_source, latest_event_time)
        freshness_hours = (
            round(max((now_utc - source_last_refresh).total_seconds(), 0.0) / 3600.0, 3)
            if source_last_refresh is not None
            else None
        )
        freshness_penalty = min((freshness_hours or 24.0) * 2.5, 35.0)
        enabled_bonus = 15.0 if source.enabled else -25.0
        weight_score = max(min(float(source.weight), 2.0), 0.0) * 15.0
        priority_score = ((max_priority - max(source.priority, 1) + 1) / max_priority) * 20.0
        trust_score = max(
            0.0,
            min(100.0, 45.0 + enabled_bonus + weight_score + priority_score - freshness_penalty),
        )
        drift_risk = "high" if trust_score < 50.0 else "medium" if trust_score < 75.0 else "low"
        data_trust_scores.append(
            {
                "source": normalized_source,
                "trust_score": round(trust_score, 2),
                "freshness_hours": freshness_hours,
                "drift_risk": drift_risk,
                "last_refresh": source_last_refresh.isoformat() if source_last_refresh else None,
                "enabled": source.enabled,
                "weight": source.weight,
                "priority": source.priority,
                "category": source.category,
            }
        )

    federation_alerts: list[dict[str, object]] = []
    if ml_status == "down":
        federation_alerts.append(
            {
                "id": "runtime-ml-unreachable",
                "severity": "critical",
                "message": "ML dependency is unreachable from API runtime.",
                "source": "ml_dependency",
                "created_at": generated_at,
                "acknowledged": False,
            }
        )
    elif ml_status == "degraded":
        federation_alerts.append(
            {
                "id": "runtime-ml-degraded",
                "severity": "warning",
                "message": "ML dependency is reachable but unhealthy/degraded.",
                "source": "ml_dependency",
                "created_at": generated_at,
                "acknowledged": False,
            }
        )

    if error_rate_pct >= 8.0:
        federation_alerts.append(
            {
                "id": "runtime-api-5xx-critical",
                "severity": "critical",
                "message": f"API 5xx ratio is high at {error_rate_pct}%.",
                "source": "api_runtime",
                "created_at": generated_at,
                "acknowledged": False,
            }
        )
    elif error_rate_pct >= 2.0:
        federation_alerts.append(
            {
                "id": "runtime-api-5xx-warning",
                "severity": "warning",
                "message": f"API 5xx ratio exceeded warning threshold ({error_rate_pct}%).",
                "source": "api_runtime",
                "created_at": generated_at,
                "acknowledged": False,
            }
        )

    if not flow_items:
        federation_alerts.append(
            {
                "id": "runtime-flow-events-missing",
                "severity": "warning",
                "message": "No flow events are available in recent runtime window.",
                "source": "flow_event_stream",
                "created_at": generated_at,
                "acknowledged": False,
            }
        )
    elif flow_stale:
        stale_minutes = round(minutes_since_last_event or 0.0, 3)
        federation_alerts.append(
            {
                "id": "runtime-flow-events-stale",
                "severity": "warning",
                "message": f"Latest flow event is stale ({stale_minutes} minutes ago).",
                "source": "flow_event_stream",
                "created_at": generated_at,
                "acknowledged": False,
            }
        )
    if flow_missing_count > 0:
        federation_alerts.append(
            {
                "id": "runtime-flow-events-partial",
                "severity": "warning",
                "message": (
                    f"{flow_missing_count} flow event record(s) were persisted "
                    "without detailed flow events."
                ),
                "source": "flow_event_stream",
                "created_at": generated_at,
                "acknowledged": False,
            }
        )

    summary: dict[str, Any] = {
        "partners_total": len(partner_health),
        "partners_down": sum(
            1 for partner in partner_health if str(partner.get("status")) == "down"
        ),
        "trust_low_count": sum(
            1 for score in data_trust_scores if _to_float(score.get("trust_score")) < 60.0
        ),
        "critical_alert_count": sum(
            1 for alert in federation_alerts if str(alert.get("severity")) == "critical"
        ),
        "simulated": False,
    }

    return {
        "generated_at": generated_at,
        "partner_health": partner_health,
        "data_trust_scores": data_trust_scores,
        "federation_alerts": federation_alerts,
        "summary": summary,
    }


@router.get("/sources", response_model=SystemSourcesRegistryResponse)
def get_sources_registry(
    _token: TokenPayload = Depends(require_roles("doctor")),
) -> SystemSourcesRegistryResponse:
    public_no_key: list[dict[str, object]] = [
        {
            "id": "moh_vn",
            "name": "Bộ Y tế Việt Nam (MOH)",
            "group": "guideline",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Nguồn hướng dẫn/chính sách y tế nội địa.",
        },
        {
            "id": "dav_vn",
            "name": "Cục Quản lý Dược (DAV)",
            "group": "drug_registry",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Dùng cho tra cứu thuốc hợp pháp và cảnh báo nội địa.",
        },
        {
            "id": "di_adr_vn",
            "name": "Trung tâm DI & ADR Quốc gia",
            "group": "pharmacovigilance",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Nguồn cảnh giác dược và cảnh báo ADR tại Việt Nam.",
        },
        {
            "id": "pubmed_no_key",
            "name": "PubMed E-utilities (no-key mode)",
            "group": "literature",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Nguồn bài báo y khoa cho RAG và trích dẫn.",
        },
        {
            "id": "europepmc_no_key",
            "name": "Europe PMC",
            "group": "literature",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Nguồn bài báo open-access và biomedical literature.",
        },
        {
            "id": "openalex_no_key",
            "name": "OpenAlex",
            "group": "literature",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Metadata học thuật mở cho truy xuất citation.",
        },
        {
            "id": "crossref_no_key",
            "name": "Crossref Works API",
            "group": "literature",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Truy xuất DOI và metadata bài báo khoa học.",
        },
        {
            "id": "clinicaltrials_v2",
            "name": "ClinicalTrials.gov API v2",
            "group": "clinical_trials",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Nguồn thử nghiệm lâm sàng công khai.",
        },
        {
            "id": "openfda_no_key",
            "name": "openFDA (no-key mode)",
            "group": "drug_safety",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Nguồn nhãn thuốc và cảnh báo an toàn cơ bản.",
        },
        {
            "id": "dailymed",
            "name": "DailyMed Web Services",
            "group": "drug_label",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Nguồn nhãn thuốc SPL của NLM/FDA.",
        },
        {
            "id": "searxng_self_host",
            "name": "SearXNG (self-host)",
            "group": "web_search",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Web search meta-engine tự host, không cần API key.",
        },
        {
            "id": "rxnav_public",
            "name": "RxNav/RxNorm public APIs",
            "group": "medication_normalization",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Chuẩn hóa hoạt chất và mã thuốc.",
        },
        {
            "id": "who_outbreak",
            "name": "WHO Public Health Feeds",
            "group": "public_health",
            "phase": "public_no_key",
            "key_required": False,
            "status": "active",
            "notes": "Cập nhật dịch tễ và thông báo y tế công cộng.",
        },
    ]
    key_required: list[dict[str, object]] = [
        {
            "id": "nhic_csdl_duoc",
            "name": "NHIC/CSDL Dược API",
            "group": "drug_registry",
            "phase": "key_required",
            "key_required": True,
            "status": "pending_credentials",
            "notes": "Yêu cầu OAuth2 và kết nối chính thức.",
        },
        {
            "id": "who_icd_api",
            "name": "WHO ICD API",
            "group": "terminology",
            "phase": "key_required",
            "key_required": True,
            "status": "pending_credentials",
            "notes": "Yêu cầu client credentials.",
        },
        {
            "id": "pubmed_key_mode",
            "name": "PubMed E-utilities (key mode)",
            "group": "literature",
            "phase": "key_required",
            "key_required": True,
            "status": "pending_credentials",
            "notes": "Mở rộng throughput khi có NCBI API key.",
        },
        {
            "id": "openfda_key_mode",
            "name": "openFDA (key mode)",
            "group": "drug_safety",
            "phase": "key_required",
            "key_required": True,
            "status": "pending_credentials",
            "notes": "Mở rộng quota truy vấn khi có key.",
        },
        {
            "id": "fhir_partner",
            "name": "FHIR API đối tác bệnh viện",
            "group": "clinical_data",
            "phase": "key_required",
            "key_required": True,
            "status": "pending_partner",
            "notes": "Tích hợp dữ liệu hồ sơ y khoa có kiểm soát quyền.",
        },
        {
            "id": "gcp_vision",
            "name": "Google Cloud Vision OCR",
            "group": "ocr",
            "phase": "key_required",
            "key_required": True,
            "status": "pending_credentials",
            "notes": "OCR chính cho scan hóa đơn/đơn thuốc.",
        },
        {
            "id": "aws_textract",
            "name": "AWS Textract OCR",
            "group": "ocr",
            "phase": "key_required",
            "key_required": True,
            "status": "pending_credentials",
            "notes": "OCR dự phòng hoặc song song theo chiến lược đa nhà cung cấp.",
        },
        {
            "id": "azure_doc_intel",
            "name": "Azure Document Intelligence OCR",
            "group": "ocr",
            "phase": "key_required",
            "key_required": True,
            "status": "pending_credentials",
            "notes": "OCR thay thế cho khu vực/hạ tầng Azure.",
        },
    ]
    commercial: list[dict[str, object]] = [
        {
            "id": "drugbank_api",
            "name": "DrugBank API",
            "group": "drug_knowledge",
            "phase": "commercial",
            "key_required": True,
            "status": "license_required",
            "notes": "Nguồn DDI/tri thức dược chuyên sâu theo license thương mại.",
        },
        {
            "id": "nice_syndication",
            "name": "NICE Syndication API",
            "group": "guideline",
            "phase": "commercial",
            "key_required": True,
            "status": "license_required",
            "notes": "Nguồn guideline nâng cao theo thỏa thuận.",
        },
        {
            "id": "vigibase_access",
            "name": "UMC VigiBase access",
            "group": "pharmacovigilance",
            "phase": "commercial",
            "key_required": True,
            "status": "license_required",
            "notes": "Nguồn cảnh giác dược toàn cầu theo data agreement.",
        },
        {
            "id": "scopus_api",
            "name": "Scopus API",
            "group": "literature",
            "phase": "commercial",
            "key_required": True,
            "status": "license_required",
            "notes": "Mở rộng dữ liệu nghiên cứu khoa học theo license.",
        },
        {
            "id": "wos_api",
            "name": "Web of Science API",
            "group": "literature",
            "phase": "commercial",
            "key_required": True,
            "status": "license_required",
            "notes": "Nguồn bài báo/bibliometrics chuyên sâu theo license.",
        },
    ]
    return {
        "public_no_key": public_no_key,
        "key_required": key_required,
        "commercial": commercial,
    }


@router.get("/control-tower/config", response_model=SystemControlTowerConfig)
def get_control_tower_config(
    _token: TokenPayload = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
) -> SystemControlTowerConfig:
    return get_control_tower_config_service().load(db)


@router.put("/control-tower/config", response_model=SystemControlTowerConfig)
def update_control_tower_config(
    payload: SystemControlTowerConfig,
    _token: TokenPayload = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
) -> SystemControlTowerConfig:
    return get_control_tower_config_service().save(db, payload)


@router.get("/careguard/runtime", response_model=CareguardRuntimeConfig)
def get_careguard_runtime(
    _token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> CareguardRuntimeConfig:
    return get_control_tower_config_service().load(db).careguard_runtime


@router.put("/careguard/runtime", response_model=CareguardRuntimeConfig)
def update_careguard_runtime(
    payload: CareguardRuntimeConfig,
    _token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> CareguardRuntimeConfig:
    service = get_control_tower_config_service()
    config = service.load(db)
    config.careguard_runtime = payload
    updated = service.save(db, config)
    return updated.careguard_runtime


@router.get("/flow-events")
def get_flow_events(
    limit: int = FLOW_EVENTS_DEFAULT_LIMIT,
    after_sequence: int | None = None,
    source: str | None = None,
    _token: TokenPayload = Depends(require_roles("doctor", "admin")),
) -> dict[str, object]:
    return get_flow_event_stream_service().list_events(
        limit=limit,
        after_sequence=after_sequence,
        source=source,
    )


@router.get("/flow-events/stream")
async def stream_flow_events(
    request: Request,
    limit: int = FLOW_EVENTS_DEFAULT_LIMIT,
    after_sequence: int | None = None,
    source: str | None = None,
    heartbeat_seconds: int = 15,
    poll_interval_seconds: float = 1.0,
    _token: TokenPayload = Depends(require_roles("doctor", "admin")),
):
    return get_flow_event_stream_service().stream_response(
        request=request,
        limit=limit,
        after_sequence=after_sequence,
        source=source,
        heartbeat_seconds=heartbeat_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
