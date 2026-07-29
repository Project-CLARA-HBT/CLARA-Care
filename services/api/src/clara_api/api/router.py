from fastapi import APIRouter

from clara_api.api.v1.endpoints import (
    admin_audit,
    admin_observability,
    admin_rag,
    auth,
    careguard,
    chat,
    clinical_workbench,
    connected_health,
    council,
    evidence_questions,
    family,
    health,
    lifemap,
    lifemap_capture,
    lifemap_insights,
    lifemap_review,
    medications,
    mobile,
    phr,
    profiles,
    research,
    scribe,
    search,
    social,
    system,
    visits,
    workspace,
)
from clara_api.compliance.api import router as compliance_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(profiles.router, tags=["profiles"])
api_router.include_router(lifemap.router, prefix="/lifemap", tags=["lifemap"])
api_router.include_router(
    lifemap_capture.router, prefix="/lifemap/capture", tags=["lifemap-capture"]
)
api_router.include_router(lifemap_insights.router, tags=["lifemap-insights"])
api_router.include_router(lifemap_review.router, tags=["lifemap-review"])
api_router.include_router(evidence_questions.router, tags=["evidence"])
api_router.include_router(visits.router, prefix="/visits", tags=["visits"])
api_router.include_router(visits.pack_router, prefix="/visit-packs", tags=["visit-packs"])
api_router.include_router(family.router, prefix="/family", tags=["family"])
api_router.include_router(family.task_router, prefix="/care-tasks", tags=["care-tasks"])
api_router.include_router(medications.router, prefix="/medication-courses", tags=["medications"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(mobile.router, prefix="/mobile", tags=["mobile"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(
    clinical_workbench.router, prefix="/clinical-workbench", tags=["clinical-workbench"]
)
api_router.include_router(phr.router, prefix="/phr", tags=["phr"])
api_router.include_router(connected_health.router, prefix="/connectors", tags=["connected-health"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(careguard.router, prefix="/careguard", tags=["careguard"])
api_router.include_router(council.router, prefix="/council", tags=["council"])
api_router.include_router(scribe.router, prefix="/scribe", tags=["scribe"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(workspace.router, prefix="/workspace", tags=["workspace"])
api_router.include_router(social.router, prefix="/social", tags=["social"])
api_router.include_router(admin_rag.router, prefix="/admin/rag", tags=["admin-rag"])
api_router.include_router(admin_audit.router, prefix="/admin/audit", tags=["admin-audit"])
api_router.include_router(
    admin_observability.router, prefix="/admin/observability", tags=["admin-observability"]
)
api_router.include_router(compliance_router, prefix="/compliance", tags=["compliance"])
