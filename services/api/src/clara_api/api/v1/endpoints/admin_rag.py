"""Admin RBAC endpoints for the RAG knowledge pipeline (Requirement 13).

This module exposes the ``/api/v1/admin/rag/*`` control surface used by the
Vietnamese admin web pages to manage the offline ingestion plane and the
evaluation harness. Every endpoint is gated by ``require_roles("admin")`` so a
non-admin token receives HTTP 403 and a missing token receives HTTP 401
(Requirement 13.1); no unauthenticated public endpoint is introduced
(Requirement 13.4).

The corpus, ``kb_source_registry``, and eval tables are owned by
``services/ml``. The API never touches them directly: each handler proxies to a
clearly-named ml path, reusing the established ``ml_proxy`` pattern (internal
api-key header, downstream timeout, single retry). The ml-side handlers may not
exist yet — these endpoints therefore degrade gracefully to a fail-soft payload
rather than blocking, so the admin surface stays available during rollout
(Requirement 13.2).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.compliance.redaction import hash_user_ref
from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.session import get_db
from clara_api.observability.admin_audit import (
    ACTION_EVAL_RUN,
    ACTION_INGESTION_RUN,
    ACTION_RAG_SOURCE_UPDATE,
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    record_admin_action,
)

router = APIRouter()

# Single admin RBAC dependency reused by every route (Requirement 13.1/13.2).
# Mirrors the ``DOCTOR_ROLE_DEP`` convention used by the council/scribe routers.
ADMIN_ROLE_DEP = Depends(require_roles("admin"))


# ---------------------------------------------------------------------------
# ML proxy helper (read / update verbs)
# ---------------------------------------------------------------------------


def _build_fail_soft(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    """Return a degraded payload flagged so the admin UI can surface the outage."""

    response = dict(payload)
    response["ml_available"] = False
    response["fallback"] = True
    response["fallback_reason"] = reason
    return response


def _require_ingestion_controls_enabled() -> None:
    """Gate the live ingestion/eval control path behind its feature flag.

    When ``admin_rag_ingestion_controls_enabled`` is off the control surface
    ships dark: each gated endpoint returns the project's standard
    "feature-disabled" HTTP 404 shape (matching ``system.py`` analytics and the
    flag-gated scribe/careguard surfaces) rather than a partial or misleading
    success (Requirements 3.1, 12.4). The check runs inside the handler body so
    the ``require_roles("admin")`` dependency still authorizes the caller first.
    """

    if not get_settings().admin_rag_ingestion_controls_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Điều khiển ingestion/eval đã bị tắt.",
        )


def _mark_degraded(result: dict[str, Any]) -> dict[str, Any]:
    """Stamp an explicit boolean ``degraded`` marker on a control response.

    The marker is derived purely from the existing fail-soft fields: a payload
    is degraded when CLARA_ML reported ``fallback`` or is not available. A
    successful CLARA_ML response (``ml_available`` truthy, no ``fallback``) is
    therefore never marked degraded, so the web surface can render an
    "unavailable, retry" state on real outages instead of presenting stale
    success (Requirements 3.3, 3.4).
    """

    result["degraded"] = bool(
        result.get("fallback") or not result.get("ml_available", True)
    )
    return result


def _audit_rag_mutation(
    db: Session,
    token: TokenPayload,
    action: str,
    *,
    target: str,
    result: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one admin-action audit row for a RAG control mutation (Req 9.1, 9.5).

    The outcome mirrors the fail-soft/degraded marker derived from the proxy
    response: a degraded result (CLARA_ML unavailable / ``fallback``) is recorded
    as a ``failure`` and a clean ML response as a ``success`` (Requirement 9.5).
    The actor reference is the opaque, salted hash of the caller's id — never the
    raw user id / email (Requirement 9.3) — and ``meta`` carries counts/flags
    only. The write is a no-op when ``admin_audit_log_enabled`` is off, so the
    flags-off baseline is preserved (Requirement 12.2).
    """

    degraded = bool(result.get("fallback") or not result.get("ml_available", True))
    audit_meta: dict[str, Any] = {"degraded": degraded}
    if meta:
        audit_meta.update(meta)
    record_admin_action(
        db,
        hash_user_ref(token.sub),
        action,
        target=target,
        outcome=OUTCOME_FAILURE if degraded else OUTCOME_SUCCESS,
        meta=audit_meta,
    )
    db.commit()


def _proxy_ml_read(
    method: str,
    ml_path: str,
    *,
    json_body: dict[str, Any] | None = None,
    fail_soft_payload: dict[str, Any],
) -> dict[str, Any]:
    """Proxy a GET/PATCH admin request to ``services/ml``.

    Mirrors :func:`clara_api.api.v1.endpoints.ml_proxy.proxy_ml_post` (same
    internal-key header, downstream timeout, and single-retry semantics) but
    supports read/update verbs and always degrades to ``fail_soft_payload`` so
    an absent or unavailable ml handler never takes the admin surface down.
    """

    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/{ml_path.lstrip('/')}"
    headers: dict[str, str] = {}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()
    timeout = settings.ml_service_timeout_seconds

    response: httpx.Response | None = None
    for attempt in range(2):
        try:
            request_kwargs: dict[str, Any] = {"timeout": timeout}
            if headers:
                request_kwargs["headers"] = headers
            if json_body is not None:
                request_kwargs["json"] = json_body
            response = httpx.request(method.upper(), url, **request_kwargs)
            break
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            if attempt < 1:
                continue
            return _build_fail_soft(fail_soft_payload, exc.__class__.__name__)
        except httpx.HTTPError as exc:
            return _build_fail_soft(fail_soft_payload, exc.__class__.__name__)

    if response is None:
        return _build_fail_soft(fail_soft_payload, "NoResponse")
    if response.status_code >= 400:
        return _build_fail_soft(fail_soft_payload, f"status_{response.status_code}")

    try:
        data = response.json()
    except ValueError:
        return _build_fail_soft(fail_soft_payload, "InvalidJSON")
    if not isinstance(data, dict):
        return _build_fail_soft(fail_soft_payload, "UnexpectedPayloadFormat")
    return data


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class _ProxyAwareModel(BaseModel):
    """Base for proxied responses.

    ``extra="allow"`` lets richer ml payloads (and the fail-soft ``fallback`` /
    ``fallback_reason`` markers) pass through untouched while the declared
    fields document the stable contract.
    """

    model_config = ConfigDict(extra="allow")
    ml_available: bool = True


class IngestionRunRequest(BaseModel):
    """Trigger ingestion for one registered source."""

    source_key: str = Field(
        ..., min_length=1, description="kb_source_registry.source_key to ingest"
    )
    since: str | None = Field(
        default=None, description="Optional watermark/cursor override (resume point)"
    )
    force: bool = Field(
        default=False, description="Re-ingest even when content_hash is unchanged"
    )


class IngestionRunResponse(_ProxyAwareModel):
    job_id: str = ""
    source_key: str = ""
    status: str = "queued"
    accepted: bool = False
    # Explicit fail-soft marker (Req 3.3/3.4): true only when CLARA_ML is
    # unavailable or returned a fallback payload; never set on real success.
    degraded: bool = False


class IngestionStatusResponse(_ProxyAwareModel):
    job_id: str = ""
    source_key: str = ""
    status: str = "unknown"
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    degraded: int = 0
    errors: list[Any] = Field(default_factory=list)


class SourceInfo(_ProxyAwareModel):
    id: int | None = None
    source_key: str = ""
    display_name: str = ""
    trust_tier: int | None = None
    enabled: bool = True
    weight: float | None = None
    fetch_mode: str = ""
    license_code: str = ""
    attribution: str = ""
    last_watermark: str = ""
    last_run_at: str | None = None


class SourcesListResponse(_ProxyAwareModel):
    sources: list[SourceInfo] = Field(default_factory=list)


class SourceUpdateRequest(BaseModel):
    """Enable/disable a source or adjust its ranking tier/weight.

    All fields are optional; only the provided ones are applied. ``trust_tier``
    is constrained to the ``{1,2,3,4}`` authority band used across the pipeline.
    """

    enabled: bool | None = Field(default=None, description="Toggle source ingestion")
    trust_tier: int | None = Field(
        default=None, ge=1, le=4, description="Authority tier (1 = regulator/label)"
    )
    weight: float | None = Field(
        default=None, ge=0.0, description="Relative ranking weight (>= 0)"
    )


class EvalRunRequest(BaseModel):
    """Run the golden VN Q&A evaluation harness."""

    run_label: str | None = Field(
        default=None, description="Optional human-readable label for the run"
    )
    k: int = Field(default=10, ge=1, le=100, description="recall@k / nDCG@k cutoff")
    categories: list[str] = Field(
        default_factory=list, description="Optional eval_set category filter"
    )


class EvalRunResponse(_ProxyAwareModel):
    run_id: str = ""
    status: str = "queued"
    accepted: bool = False
    # Explicit fail-soft marker (Req 3.3/3.4); see ``IngestionRunResponse``.
    degraded: bool = False


class EvalResultItem(_ProxyAwareModel):
    qid: str = ""
    recall_at_k: float = 0.0
    ndcg_at_k: float = 0.0
    faithfulness: float = 0.0
    citation_acc: float = 0.0
    latency_ms: float = 0.0


class EvalResultsResponse(_ProxyAwareModel):
    run_id: str = ""
    results: list[EvalResultItem] = Field(default_factory=list)
    # Aggregate means across the run (mirrors eval_run_result columns).
    recall_at_k: float = 0.0
    ndcg_at_k: float = 0.0
    faithfulness: float = 0.0
    citation_acc: float = 0.0
    # Explicit fail-soft marker (Req 3.3/3.4); see ``IngestionRunResponse``.
    degraded: bool = False


class CorpusStatsResponse(_ProxyAwareModel):
    documents: int = 0
    chunks: int = 0
    degraded_chunks: int = 0
    coverage_pct: float = 0.0
    sources_total: int = 0
    sources_enabled: int = 0


# ---------------------------------------------------------------------------
# Ingestion control (P1)
# ---------------------------------------------------------------------------


@router.post("/ingestion/run", response_model=IngestionRunResponse)
def run_ingestion(
    payload: IngestionRunRequest,
    token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> IngestionRunResponse:
    """Trigger an async ingestion job for a source (Requirement 13.2)."""

    _require_ingestion_controls_enabled()
    result = proxy_ml_post(
        "/v1/admin/rag/ingestion/run",
        payload.model_dump(),
        fail_soft_payload={
            "job_id": "",
            "source_key": payload.source_key,
            "status": "unavailable",
            "accepted": False,
            "ml_available": False,
        },
    )
    _mark_degraded(result)
    _audit_rag_mutation(
        db,
        token,
        ACTION_INGESTION_RUN,
        target=str(result.get("source_key") or payload.source_key),
        result=result,
        meta={"force": payload.force},
    )
    return IngestionRunResponse.model_validate(result)


@router.get("/ingestion/status/{job_id}", response_model=IngestionStatusResponse)
def get_ingestion_status(
    job_id: str = Path(..., min_length=1, description="Ingestion job identifier"),
    _token: TokenPayload = ADMIN_ROLE_DEP,
) -> IngestionStatusResponse:
    """Poll the status / report of a previously triggered ingestion job."""

    _require_ingestion_controls_enabled()
    result = _proxy_ml_read(
        "GET",
        f"/v1/admin/rag/ingestion/status/{quote(job_id, safe='')}",
        fail_soft_payload={"job_id": job_id, "status": "unavailable"},
    )
    return IngestionStatusResponse.model_validate(result)


# ---------------------------------------------------------------------------
# Source registry (P1)
# ---------------------------------------------------------------------------


@router.get("/sources", response_model=SourcesListResponse)
def list_sources(
    _token: TokenPayload = ADMIN_ROLE_DEP,
) -> SourcesListResponse:
    """List ``kb_source_registry`` entries with their ingestion watermarks."""

    result = _proxy_ml_read(
        "GET",
        "/v1/admin/rag/sources",
        fail_soft_payload={"sources": []},
    )
    return SourcesListResponse.model_validate(result)


@router.patch("/sources/{source_id}", response_model=SourceInfo)
def update_source(
    payload: SourceUpdateRequest,
    source_id: int = Path(..., ge=1, description="kb_source_registry.id"),
    token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> SourceInfo:
    """Enable/disable a source or set its trust tier / ranking weight."""

    # Forward only the explicitly-set fields so unspecified knobs are untouched.
    body = payload.model_dump(exclude_none=True)
    result = _proxy_ml_read(
        "PATCH",
        f"/v1/admin/rag/sources/{source_id}",
        json_body=body,
        fail_soft_payload={"id": source_id},
    )
    _audit_rag_mutation(
        db,
        token,
        ACTION_RAG_SOURCE_UPDATE,
        target=str(source_id),
        result=result,
        meta={"fields": sorted(body.keys())},
    )
    return SourceInfo.model_validate(result)


# ---------------------------------------------------------------------------
# Evaluation harness (P5)
# ---------------------------------------------------------------------------


@router.post("/eval/run", response_model=EvalRunResponse)
def run_eval(
    payload: EvalRunRequest,
    token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> EvalRunResponse:
    """Run the eval harness over the golden VN Q&A set; returns a ``run_id``."""

    _require_ingestion_controls_enabled()
    result = proxy_ml_post(
        "/v1/admin/rag/eval/run",
        payload.model_dump(),
        fail_soft_payload={
            "run_id": "",
            "status": "unavailable",
            "accepted": False,
            "ml_available": False,
        },
    )
    _mark_degraded(result)
    _audit_rag_mutation(
        db,
        token,
        ACTION_EVAL_RUN,
        target=str(result.get("run_id") or ""),
        result=result,
        meta={"k": payload.k, "categories_count": len(payload.categories)},
    )
    return EvalRunResponse.model_validate(result)


@router.get("/eval/results/{run_id}", response_model=EvalResultsResponse)
def get_eval_results(
    run_id: str = Path(..., min_length=1, description="Eval run identifier"),
    _token: TokenPayload = ADMIN_ROLE_DEP,
) -> EvalResultsResponse:
    """Fetch eval metrics (recall@k / nDCG / faithfulness / citation accuracy)."""

    _require_ingestion_controls_enabled()
    result = _proxy_ml_read(
        "GET",
        f"/v1/admin/rag/eval/results/{quote(run_id, safe='')}",
        fail_soft_payload={"run_id": run_id, "results": []},
    )
    return EvalResultsResponse.model_validate(_mark_degraded(result))


# ---------------------------------------------------------------------------
# Corpus statistics (P0/P5 observability)
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=CorpusStatsResponse)
def get_corpus_stats(
    _token: TokenPayload = ADMIN_ROLE_DEP,
) -> CorpusStatsResponse:
    """Corpus stats: document/chunk counts, degraded count, and coverage."""

    result = _proxy_ml_read(
        "GET",
        "/v1/admin/rag/stats",
        fail_soft_payload={
            "documents": 0,
            "chunks": 0,
            "degraded_chunks": 0,
            "coverage_pct": 0.0,
        },
    )
    return CorpusStatsResponse.model_validate(result)
