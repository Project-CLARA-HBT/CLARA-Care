from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.metrics import get_api_metrics_store
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import SystemSetting
from clara_api.db.session import get_db
from clara_api.schemas import RagFlowConfig, RagSourceEntry, SystemControlTowerConfig

router = APIRouter()

CONTROL_TOWER_KEY = "control_tower_config_v1"

DEFAULT_CONTROL_TOWER_CONFIG = SystemControlTowerConfig(
    rag_sources=[
        RagSourceEntry(
            id="pubmed",
            name="PubMed",
            enabled=True,
            priority=1,
            category="literature",
        ),
        RagSourceEntry(
            id="rxnorm",
            name="RxNorm",
            enabled=True,
            priority=2,
            category="drug_normalization",
        ),
        RagSourceEntry(
            id="openfda",
            name="openFDA",
            enabled=True,
            priority=3,
            category="drug_safety",
        ),
        RagSourceEntry(
            id="davidrug",
            name="Cục Quản lý Dược (VN)",
            enabled=True,
            priority=4,
            category="vn_regulatory",
        ),
    ],
    rag_flow=RagFlowConfig(
        role_router_enabled=True,
        intent_router_enabled=True,
        verification_enabled=True,
        deepseek_fallback_enabled=True,
        low_context_threshold=0.2,
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _utc_ago_iso(*, minutes: int = 0, hours: int = 0) -> str:
    return (datetime.now(tz=UTC) - timedelta(minutes=minutes, hours=hours)).isoformat()


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

    try:
        response = httpx.get(health_url, timeout=settings.ml_service_timeout_seconds)
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
) -> dict[str, object]:
    generated_at = _utc_now_iso()
    partner_health: list[dict[str, object]] = [
        {
            "partner": "ehr_core",
            "status": "ok",
            "latency_ms": 118,
            "error_rate_pct": 0.2,
            "last_check": _utc_ago_iso(minutes=2),
        },
        {
            "partner": "claims_exchange",
            "status": "degraded",
            "latency_ms": 426,
            "error_rate_pct": 3.7,
            "last_check": _utc_ago_iso(minutes=3),
        },
        {
            "partner": "labs_federation",
            "status": "down",
            "latency_ms": 0,
            "error_rate_pct": 100.0,
            "last_check": _utc_ago_iso(minutes=1),
        },
    ]
    data_trust_scores: list[dict[str, object]] = [
        {
            "source": "national_hospital_feed",
            "trust_score": 92,
            "freshness_hours": 2.0,
            "drift_risk": "low",
            "last_refresh": _utc_ago_iso(hours=2),
        },
        {
            "source": "regional_outpatient_registry",
            "trust_score": 74,
            "freshness_hours": 6.5,
            "drift_risk": "medium",
            "last_refresh": _utc_ago_iso(hours=6),
        },
        {
            "source": "community_lab_batch",
            "trust_score": 48,
            "freshness_hours": 18.0,
            "drift_risk": "high",
            "last_refresh": _utc_ago_iso(hours=18),
        },
    ]
    federation_alerts: list[dict[str, object]] = [
        {
            "id": "fa-1001",
            "severity": "warning",
            "message": "Claims partner latency elevated above SLO for 15 minutes.",
            "source": "claims_exchange",
            "created_at": _utc_ago_iso(minutes=17),
            "acknowledged": True,
        },
        {
            "id": "fa-1002",
            "severity": "critical",
            "message": "Lab federation endpoint unreachable from two regions.",
            "source": "labs_federation",
            "created_at": _utc_ago_iso(minutes=7),
            "acknowledged": False,
        },
        {
            "id": "fa-1003",
            "severity": "info",
            "message": "Nightly trust model refresh completed successfully.",
            "source": "trust_scoring_pipeline",
            "created_at": _utc_ago_iso(minutes=4),
            "acknowledged": True,
        },
    ]

    summary = {
        "partners_total": len(partner_health),
        "partners_down": sum(1 for partner in partner_health if partner["status"] == "down"),
        "trust_low_count": sum(1 for score in data_trust_scores if int(score["trust_score"]) < 60),
        "critical_alert_count": sum(
            1 for alert in federation_alerts if alert["severity"] == "critical"
        ),
    }

    return {
        "generated_at": generated_at,
        "partner_health": partner_health,
        "data_trust_scores": data_trust_scores,
        "federation_alerts": federation_alerts,
        "summary": summary,
    }


@router.get("/sources")
def get_sources_registry(
    _token: TokenPayload = Depends(require_roles("doctor")),
) -> dict[str, list[dict[str, object]]]:
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


def _load_control_tower_config(db: Session) -> SystemControlTowerConfig:
    row = db.execute(
        select(SystemSetting).where(SystemSetting.key == CONTROL_TOWER_KEY)
    ).scalar_one_or_none()
    if row and isinstance(row.value_json, dict):
        try:
            return SystemControlTowerConfig.model_validate(row.value_json)
        except Exception:
            pass
    return SystemControlTowerConfig.model_validate(
        DEFAULT_CONTROL_TOWER_CONFIG.model_dump(mode="json")
    )


@router.get("/control-tower/config", response_model=SystemControlTowerConfig)
def get_control_tower_config(
    _token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> SystemControlTowerConfig:
    return _load_control_tower_config(db)


@router.put("/control-tower/config", response_model=SystemControlTowerConfig)
def update_control_tower_config(
    payload: SystemControlTowerConfig,
    _token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> SystemControlTowerConfig:
    row = db.execute(
        select(SystemSetting).where(SystemSetting.key == CONTROL_TOWER_KEY)
    ).scalar_one_or_none()
    if not row:
        row = SystemSetting(key=CONTROL_TOWER_KEY)
    row.value_json = payload.model_dump(mode="json")
    row.value_text = ""
    db.add(row)
    db.commit()
    db.refresh(row)
    return SystemControlTowerConfig.model_validate(row.value_json or {})
