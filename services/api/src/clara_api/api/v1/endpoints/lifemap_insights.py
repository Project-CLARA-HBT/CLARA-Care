"""Profile-scoped baseline, revision-aware replay, and decision-ledger reads."""

import hashlib
from datetime import UTC, datetime, timedelta
from statistics import median
from time import perf_counter
from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.config import get_settings
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    AIContextManifest,
    GlhsSnapshotManifest,
    LifeMapBaselineDefinition,
    LifeMapBaselineSnapshot,
    LifeMapCareTask,
    LifeMapDecisionInput,
    LifeMapDecisionLedger,
    LifeMapEpisode,
    LifeMapEpisodeEventLink,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapProjectionDependency,
    LifeMapQuestionDefinition,
    LifeMapQuestionInteraction,
    MLInferenceManifest,
    WearableDailyAggregate,
)
from clara_api.db.session import get_db
from clara_api.glhs.gateway import compile_thss, create_inference_context_binding
from clara_api.lifemap.baselines import recompute_baseline, serialize_snapshot
from clara_api.lifemap.commands import (
    add_outbox,
    replay_command,
    request_digest,
    store_command,
)
from clara_api.lifemap.intelligence import (
    AskIntent,
    SafetyRoute,
    deterministic_answer,
    hierarchical_summary,
    retrieve_revision_evidence,
    route_ask_query,
    verify_grounded_answer,
    visit_preparation_draft,
)
from clara_api.lifemap.next_best_question import compute_next_best_question
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from clara_api.ml_governance.registry import (
    GovernanceError,
    compile_private_context,
    safe_operational_manifest,
)
from clara_api.phr.audit import write_audit

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class DecisionDisputeRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


class QuestionInteractionRequest(BaseModel):
    action: str
    reason: str = Field(default="", max_length=255)


class AskLifeMapRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    locale: str = Field(default="vi", pattern=r"^(vi|en)(-[A-Za-z]{2})?$")
    episode_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    limit: int = Field(default=20, ge=1, le=50)


class VisitPreparationDraftRequest(BaseModel):
    """Read-only scope for a consumer-editable, provenance-bound draft."""

    query: str = Field(default="", max_length=500)
    locale: str = Field(default="vi", pattern=r"^(vi|en)(-[A-Za-z]{2})?$")
    episode_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    limit: int = Field(default=12, ge=1, le=20)


def _scope(
    db: Session,
    token: TokenPayload,
    requested_profile: str | None,
    *,
    action: str = "view",
) -> ProfileScope:
    return resolve_profile_scope(
        db,
        token,
        requested_profile=requested_profile,
        action=action,
        data_class="lifemap",
        purpose="self_care",
    )


def _episode_for_profile(
    db: Session, profile_id: int, episode_ref: str
) -> LifeMapEpisode:
    selector = LifeMapEpisode.public_id == episode_ref
    if episode_ref.isdigit():
        selector = selector | (LifeMapEpisode.id == int(episode_ref))
    episode = db.execute(
        select(LifeMapEpisode).where(
            selector,
            LifeMapEpisode.profile_id == profile_id,
        )
    ).scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


def _governed_lifemap_event_ids(
    db: Session,
    *,
    scope: ProfileScope,
    task: str,
) -> tuple[str, frozenset[str]]:
    """Compile LifeMap THSS then return only its event projection keys.

    The ledger holds canonical state while LifeMap revisions hold the exact
    wording/citation projection.  Keep the two layers joined by the opaque
    event ID; never perform retrieval first and use governance only as a
    presentation label afterwards.
    """

    snapshot = compile_thss(
        db,
        scope=scope,
        task=task,
        purpose=scope.purpose,
        allowed_data_classes=frozenset({"lifemap"}),
        selection_policy="strict",
    )
    prefix = "lifemap_event:"
    return (
        snapshot.snapshot_id,
        frozenset(
            semantic_key[len(prefix) :]
            for assertion in snapshot.assertions
            if assertion.get("type") == "lifemap"
            and isinstance((semantic_key := assertion.get("semantic_key")), str)
            and semantic_key.startswith(prefix)
            and semantic_key[len(prefix) :]
        ),
    )


_ASK_LIFEMAP_USE_CASE = {
    "use_case_id": "lifemap.ask.v1",
    "release_state": "champion",
    "allowed_purposes": ["self_care"],
    "allowed_data_classes": ["lifemap"],
    "requires_consent": True,
}

_LIFEMAP_ASK_INTENTS = frozenset(
    {
        "timeline_lookup",
        "comparison",
        "visit_preparation",
        "missingness",
        "explanation",
    }
)
_LIFEMAP_ASK_BLOCK_REASONS = frozenset(
    {"prescription_request", "dosage_request", "diagnosis_request"}
)


def _semantic_ask_route(
    *,
    query: str,
    locale: str,
    fallback: SafetyRoute,
) -> tuple[SafetyRoute, dict[str, object]]:
    """Ask ML only for a closed semantic route, never LifeMap facts.

    The deterministic emergency/legal route has already run before this helper.
    The downstream request contains only the user's bounded question and locale;
    no profile, consent, episode, event, revision or retrieved evidence crosses
    the API-to-ML boundary.  A provider failure, malformed payload, or low
    confidence restores the pre-existing deterministic route immediately.
    """

    settings = get_settings()
    if not settings.lifemap_ask_semantic_routing_enabled:
        return fallback, {
            "enabled": False,
            "used": False,
            "degraded": False,
            "model_ref": "deterministic-grounded-fallback@1",
        }
    fallback_payload = {
        "action": "allow",
        "reason": "none",
        "emergency": False,
        "intent": fallback.intent,
        "confidence": 0.0,
        "model_used": "deterministic-grounded-fallback@1",
        "degraded": True,
    }
    result = proxy_ml_post(
        "/v1/lifemap/ask/route",
        {"query": query, "locale": locale},
        fail_soft_payload=fallback_payload,
    )
    if result.get("fallback") or result.get("degraded") is True:
        return fallback, {
            "enabled": True,
            "used": False,
            "degraded": True,
            "model_ref": "deterministic-grounded-fallback@1",
        }

    action = result.get("action")
    reason = result.get("reason")
    emergency = result.get("emergency")
    intent = result.get("intent")
    confidence = result.get("confidence")
    model_ref = result.get("model_used")
    if (
        action not in {"allow", "block"}
        or not isinstance(reason, str)
        or not isinstance(emergency, bool)
        or not isinstance(intent, str)
        or intent not in _LIFEMAP_ASK_INTENTS
        or not isinstance(confidence, int | float)
        or isinstance(confidence, bool)
        or not 0.0 <= float(confidence) <= 1.0
        or not isinstance(model_ref, str)
        or not model_ref.strip()
    ):
        return fallback, {
            "enabled": True,
            "used": False,
            "degraded": True,
            "model_ref": "deterministic-grounded-fallback@1",
        }
    if emergency:
        return SafetyRoute(intent="timeline_lookup", emergency=True), {
            "enabled": True,
            "used": True,
            "degraded": False,
            "model_ref": model_ref.strip()[:128],
        }
    if action == "block" and reason in _LIFEMAP_ASK_BLOCK_REASONS:
        return SafetyRoute(intent="explanation", blocked_reason="legal_guard"), {
            "enabled": True,
            "used": True,
            "degraded": False,
            "model_ref": model_ref.strip()[:128],
        }
    if action == "allow" and reason == "none" and float(confidence) >= 0.7:
        return SafetyRoute(intent=cast(AskIntent, intent)), {
            "enabled": True,
            "used": True,
            "degraded": False,
            "model_ref": model_ref.strip()[:128],
        }
    return fallback, {
        "enabled": True,
        "used": False,
        "degraded": False,
        "model_ref": "deterministic-grounded-fallback@1",
    }


def _emergency_visit_draft(locale: str) -> dict:
    return {
        "status": "emergency_escalation",
        "title": (
            "Hãy tìm hỗ trợ khẩn cấp ngay"
            if locale.startswith("vi")
            else "Get emergency help now"
        ),
        "answer": (
            "Hãy gọi cấp cứu địa phương ngay hoặc đến khoa cấp cứu gần nhất."
            if locale.startswith("vi")
            else (
                "Call local emergency services now or go to the nearest "
                "emergency department."
            )
        ),
        "questions_to_consider": [],
        "source_revision_ids": [],
        "disclosure": {
            "mutates_lifemap": False,
            "draft_only": True,
            "retrieval_bypassed": True,
        },
    }


@router.post("/lifemap/v2/ask")
def ask_lifemap_v2(
    payload: AskLifeMapRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Return a read-only, exact-revision-cited LifeMap answer.

    The first release is deliberately the deterministic governed fallback. It
    proves the authorization, context-lineage, citation, abstention and safety
    boundary before a separately evaluated LLM synthesizer may be promoted.
    """

    if not get_settings().lifemap_ask_ai_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_not_enabled"})
    route = route_ask_query(payload.query)
    disclosure = {
        "ai_assisted": True,
        "mode": "deterministic_grounded_fallback",
        "medical_advice": False,
        "mutates_lifemap": False,
    }
    if route.emergency:
        return {
            "status": "emergency_escalation",
            "intent": route.intent,
            "answer": (
                "Hãy gọi cấp cứu địa phương ngay hoặc đến khoa cấp cứu gần nhất."
                if payload.locale.startswith("vi")
                else "Call local emergency services now or go to the nearest emergency department."
            ),
            "claims": [],
            "evidence": [],
            "unknown": [],
            "conflicting": [],
            "stale": [],
            "disputed": [],
            "abstention_code": "emergency_fast_path",
            "verification": {"retrieval_bypassed": True},
            "disclosure": disclosure,
        }
    if route.blocked_reason:
        raise HTTPException(
            status_code=422,
            detail={
                "code": route.blocked_reason,
                "message": (
                    "LifeMap chỉ có thể hỗ trợ tra cứu và chuẩn bị câu hỏi; "
                    "không chẩn đoán, kê đơn hoặc đưa liều cá nhân."
                ),
            },
        )

    started = perf_counter()
    scope = _scope(db, token, x_profile)
    consent = ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    route, semantic_route = _semantic_ask_route(
        query=payload.query,
        locale=payload.locale,
        fallback=route,
    )
    if route.emergency:
        return {
            "status": "emergency_escalation",
            "intent": route.intent,
            "answer": (
                "Hãy gọi cấp cứu địa phương ngay hoặc đến khoa cấp cứu gần nhất."
                if payload.locale.startswith("vi")
                else "Call local emergency services now or go to the nearest emergency department."
            ),
            "claims": [],
            "evidence": [],
            "unknown": [],
            "conflicting": [],
            "stale": [],
            "disputed": [],
            "abstention_code": "emergency_fast_path",
            "verification": {"retrieval_bypassed": True},
            "disclosure": {
                **disclosure,
                "mode": (
                    "semantic_route_deterministic_grounded_answer"
                    if semantic_route["used"]
                    else "deterministic_grounded_fallback"
                ),
                "semantic_routing": {
                    "enabled": semantic_route["enabled"],
                    "used": semantic_route["used"],
                    "degraded": semantic_route["degraded"],
                },
            },
        }
    if route.blocked_reason:
        raise HTTPException(
            status_code=422,
            detail={
                "code": route.blocked_reason,
                "message": (
                    "LifeMap chỉ có thể hỗ trợ tra cứu và chuẩn bị câu hỏi; "
                    "không chẩn đoán, kê đơn hoặc đưa liều cá nhân."
                ),
            },
        )
    episode = (
        _episode_for_profile(db, scope.profile.id, payload.episode_id)
        if payload.episode_id
        else None
    )
    glhs_snapshot_id, allowed_event_ids = _governed_lifemap_event_ids(
        db,
        scope=scope,
        task="lifemap_ask",
    )
    evidence = retrieve_revision_evidence(
        db,
        profile_id=scope.profile.id,
        query=payload.query,
        episode_id=episode.id if episode else None,
        start_at=payload.start_at,
        end_at=payload.end_at,
        allowed_event_ids=allowed_event_ids,
        limit=payload.limit,
    )
    answer = deterministic_answer(
        intent=route.intent,
        evidence=evidence,
        locale=payload.locale,
    )
    verification = verify_grounded_answer(answer, evidence)
    revision_refs = [row.revision_id for row in evidence]
    context_id: str | None = None
    inference_id: str | None = None
    if revision_refs:
        try:
            context = compile_private_context(
                use_case=_ASK_LIFEMAP_USE_CASE,
                profile_id=scope.profile.id,
                purpose=scope.purpose,
                actor_category=scope.actor_role,
                requested_data_classes={"lifemap"},
                revision_refs=revision_refs,
                consent_version=consent.consent_version,
                grant_version=scope.grant_id,
            )
        except GovernanceError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "ai_context_rejected"}
            ) from exc
        context_manifest = AIContextManifest(
            profile_id=scope.profile.id,
            use_case_id=str(context["use_case_id"]),
            purpose=scope.purpose,
            actor_category=scope.actor_role,
            data_classes_json=context["data_classes"],
            revision_refs_json=context["revision_refs"],
            context_digest=str(context["context_digest"]),
            consent_version=consent.consent_version,
            grant_version=scope.grant_id,
            expires_at=context["expires_at"],
        )
        db.add(context_manifest)
        db.flush()
        claims = answer.get("claims")
        citation_count = 0
        if isinstance(claims, list):
            for claim in claims:
                if isinstance(claim, dict) and isinstance(
                    claim.get("citation_ids"), list
                ):
                    citation_count += len(claim["citation_ids"])
        operational = safe_operational_manifest(
            {
                "latency_ms": round((perf_counter() - started) * 1000),
                "input_revision_count": len(evidence),
                "citation_count": citation_count,
                "abstained": answer["status"] == "abstained",
                "ood": False,
                "fallback_used": True,
                "locale": payload.locale,
                "semantic_route_used": semantic_route["used"],
                "semantic_route_degraded": semantic_route["degraded"],
            }
        )
        inference = MLInferenceManifest(
            context_manifest_id=context_manifest.id,
            use_case_id="lifemap.ask.v1",
            model_ref=str(semantic_route["model_ref"]),
            release_state=("champion" if semantic_route["used"] else "fallback"),
            outcome=str(answer["status"]),
            abstention_code=str(answer["abstention_code"]),
            operational_json=operational,
        )
        db.add(inference)
        db.flush()
        context_id = context_manifest.public_id
        inference_id = inference.public_id
        snapshot_manifest = (
            db.execute(
                select(GlhsSnapshotManifest).where(
                    GlhsSnapshotManifest.profile_id == scope.profile.id,
                    GlhsSnapshotManifest.public_id == glhs_snapshot_id,
                )
            ).scalar_one_or_none()
            if glhs_snapshot_id
            else None
        )
        if snapshot_manifest is not None:
            # GLHS-B01/B-004: bind at the API-owned point where the model
            # inference manifest is constructed from the THSS snapshot.  The
            # server decides ``consumed_thss``; the client never declares it.
            create_inference_context_binding(
                db,
                profile_id=scope.profile.id,
                inference_manifest_id=inference.public_id,
                snapshot=snapshot_manifest,
                actor_user_id=scope.actor.id,
                actor_role=scope.actor_role,
                purpose=scope.purpose,
                task="lifemap_ask",
                disclosed_evidence_ids=snapshot_manifest.provenance_ids_json or (),
            )
        db.commit()
    else:
        # The THSS manifest is audit evidence even when governed selection
        # produces no retrievable revision and the answer abstains.
        db.commit()

    return {
        **answer,
        "intent": route.intent,
        "evidence": [row.public_dict() for row in evidence],
        "verification": verification,
        "disclosure": {
            **disclosure,
            "mode": (
                "semantic_route_deterministic_grounded_answer"
                if semantic_route["used"]
                else "deterministic_grounded_fallback"
            ),
            "semantic_routing": {
                "enabled": semantic_route["enabled"],
                "used": semantic_route["used"],
                "degraded": semantic_route["degraded"],
            },
        },
        "context_manifest_id": context_id,
        "glhs_snapshot_id": glhs_snapshot_id,
        "inference_manifest_id": inference_id,
        "model": str(semantic_route["model_ref"]),
        "template": "ask-lifemap-v1",
        "retrieval_index": "profile-temporal-hybrid-current-revisions-v1",
        "policy": "lifemap-ai-safe-read-v1",
    }


@router.post("/lifemap/v2/visit-preparation-drafts")
def create_visit_preparation_draft_v2(
    payload: VisitPreparationDraftRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Build a Vietnamese-first, read-only visit-preparation draft.

    The endpoint only exposes current revisions from the authorised profile.
    It returns fixed wording plus exact cited source text and intentionally has
    no command, event, revision, or confirmation path.
    """

    if not get_settings().lifemap_vietnamese_drafts_enabled:
        raise HTTPException(
            status_code=404, detail={"code": "feature_not_enabled"}
        )
    route = route_ask_query(payload.query)
    if route.emergency:
        return _emergency_visit_draft(payload.locale)
    if route.blocked_reason:
        raise HTTPException(
            status_code=422,
            detail={
                "code": route.blocked_reason,
                "message": (
                    "Bản nháp này chỉ giúp chuẩn bị trao đổi khi đi khám; "
                    "không chẩn đoán, kê đơn hoặc đưa liều cá nhân."
                ),
            },
        )
    scope = _scope(db, token, x_profile)
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    episode = (
        _episode_for_profile(db, scope.profile.id, payload.episode_id)
        if payload.episode_id
        else None
    )
    glhs_snapshot_id, allowed_event_ids = _governed_lifemap_event_ids(
        db,
        scope=scope,
        task="lifemap_visit_preparation",
    )
    evidence = retrieve_revision_evidence(
        db,
        profile_id=scope.profile.id,
        query=payload.query,
        episode_id=episode.id if episode else None,
        start_at=payload.start_at,
        end_at=payload.end_at,
        allowed_event_ids=allowed_event_ids,
        limit=payload.limit,
    )
    draft = visit_preparation_draft(evidence, locale=payload.locale)
    db.commit()
    return {
        **draft,
        "evidence": [row.public_dict() for row in evidence],
        "glhs_snapshot_id": glhs_snapshot_id,
        "disclosure": {
            "mode": "deterministic_provenance_bound_draft_v1",
            "medical_advice": False,
            "mutates_lifemap": False,
            "draft_only": True,
            "requires_user_review": True,
            "preserves_truth_state": True,
        },
        "policy": "lifemap-visit-preparation-draft-safe-read-v1",
    }


@router.get("/lifemap/v2/summaries/{level}")
def lifemap_summary_v2(
    level: str,
    episode_id: str | None = Query(default=None),
    locale: str = Query(default="vi", pattern=r"^(vi|en)(-[A-Za-z]{2})?$"),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    if not get_settings().lifemap_ai_summaries_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_not_enabled"})
    if level not in {"event", "day", "episode", "week", "visit"}:
        raise HTTPException(status_code=422, detail={"code": "summary_level_invalid"})
    scope = _scope(db, token, x_profile)
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    episode = (
        _episode_for_profile(db, scope.profile.id, episode_id) if episode_id else None
    )
    glhs_snapshot_id, allowed_event_ids = _governed_lifemap_event_ids(
        db,
        scope=scope,
        task=f"lifemap_summary:{level}",
    )
    evidence = retrieve_revision_evidence(
        db,
        profile_id=scope.profile.id,
        query="",
        episode_id=episode.id if episode else None,
        start_at=start_at,
        end_at=end_at,
        allowed_event_ids=allowed_event_ids,
        limit=50,
    )
    summary = hierarchical_summary(
        evidence,
        level=level,  # type: ignore[arg-type]
        locale=locale,
    )
    revision_ids = [row.revision_id for row in evidence]
    if revision_ids:
        revisions = list(
            db.execute(
                select(LifeMapEventRevision).where(
                    LifeMapEventRevision.profile_id == scope.profile.id,
                    LifeMapEventRevision.public_id.in_(revision_ids),
                )
            ).scalars()
        )
        for revision in revisions:
            exists = db.execute(
                select(LifeMapProjectionDependency.id).where(
                    LifeMapProjectionDependency.profile_id == scope.profile.id,
                    LifeMapProjectionDependency.projection_type == f"summary:{level}",
                    LifeMapProjectionDependency.projection_public_id == summary["id"],
                    LifeMapProjectionDependency.input_revision_id == revision.id,
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(
                    LifeMapProjectionDependency(
                        profile_id=scope.profile.id,
                        projection_type=f"summary:{level}",
                        projection_public_id=str(summary["id"]),
                        input_type="event_revision",
                        input_revision_id=revision.id,
                        rule_version=str(summary["rule_version"]),
                    )
                )
    # Persist the THSS manifest even for an empty/abstained summary.
    db.commit()
    return {
        **summary,
        "glhs_snapshot_id": glhs_snapshot_id,
        "disclosure": {
            "deterministic_fallback": True,
            "medical_advice": False,
            "preserves_truth_state": True,
        },
    }


@router.get("/lifemap/v2/digests/{level}")
def delegated_lifemap_digest_v2(
    level: str,
    purpose: str = Query(default="care_coordination"),
    event_types: list[str] = Query(default=[]),
    locale: str = Query(default="vi", pattern=r"^(vi|en)(-[A-Za-z]{2})?$"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    if not get_settings().lifemap_ai_summaries_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_not_enabled"})
    if level not in {"day", "episode", "week", "visit"}:
        raise HTTPException(status_code=422, detail={"code": "digest_level_invalid"})
    if purpose not in {"care_coordination", "visit_support"}:
        raise HTTPException(status_code=422, detail={"code": "purpose_invalid"})
    requested_types = frozenset(item.strip() for item in event_types if item.strip())
    if len(requested_types) > 20 or any(len(item) > 64 for item in requested_types):
        raise HTTPException(status_code=422, detail={"code": "event_types_invalid"})
    scope = resolve_profile_scope(
        db,
        token,
        requested_profile=x_profile,
        action="view",
        data_class="lifemap",
        purpose=purpose,
    )
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    glhs_snapshot_id, allowed_event_ids = _governed_lifemap_event_ids(
        db,
        scope=scope,
        task=f"lifemap_delegated_digest:{level}",
    )
    evidence = retrieve_revision_evidence(
        db,
        profile_id=scope.profile.id,
        query="",
        event_types=requested_types or None,
        allowed_event_ids=allowed_event_ids,
        limit=50,
    )
    digest = hierarchical_summary(
        evidence,
        level=level,  # type: ignore[arg-type]
        locale=locale,
    )
    db.commit()
    return {
        **digest,
        "audience": scope.actor_role,
        "purpose": scope.purpose,
        "grant_id": scope.grant_id,
        "glhs_snapshot_id": glhs_snapshot_id,
        "visible_data_classes": sorted(scope.allowed_data_classes & {"lifemap"}),
        "withheld_event_types": sorted(
            set(event_types) - {row.event_type for row in evidence}
        ),
        "authorization_rechecked": True,
    }


def _aggregate_value(row: WearableDailyAggregate) -> float | None:
    value = row.value_json if isinstance(row.value_json, dict) else {}
    scalar = value.get("scalar")
    if isinstance(scalar, int | float) and not isinstance(scalar, bool):
        return float(scalar)
    return None


def _approved_baseline_definition(
    db: Session, signal_key: str
) -> LifeMapBaselineDefinition:
    definition = db.execute(
        select(LifeMapBaselineDefinition)
        .where(
            LifeMapBaselineDefinition.signal_key == signal_key,
            LifeMapBaselineDefinition.status == "approved",
            LifeMapBaselineDefinition.approved_at.is_not(None),
        )
        .order_by(LifeMapBaselineDefinition.created_at.desc())
    ).scalars().first()
    if definition is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "baseline_definition_not_approved"},
        )
    return definition


def _require_baseline_v2() -> None:
    if not get_settings().lifemap_baselines_v2_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_not_enabled"})


@router.get("/lifemap/v2/baselines")
def baseline_snapshots_v2(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict]:
    _require_baseline_v2()
    scope = _scope(db, token, x_profile)
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    rows = db.execute(
        select(LifeMapBaselineSnapshot, LifeMapBaselineDefinition)
        .join(
            LifeMapBaselineDefinition,
            LifeMapBaselineDefinition.id == LifeMapBaselineSnapshot.definition_id,
        )
        .where(
            LifeMapBaselineSnapshot.profile_id == scope.profile.id,
            LifeMapBaselineSnapshot.stale_at.is_(None),
        )
        .order_by(LifeMapBaselineDefinition.signal_key)
    ).all()
    return [serialize_snapshot(snapshot, definition) for snapshot, definition in rows]


@router.post("/lifemap/v2/baselines/{signal_key}/recompute")
def recompute_baseline_v2(
    signal_key: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _require_baseline_v2()
    scope = _scope(db, token, x_profile, action="update")
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    definition = _approved_baseline_definition(db, signal_key)
    operation = f"baseline.recompute:{definition.public_id}"
    digest = request_digest({"signal_key": signal_key, "version": definition.version})
    prior = replay_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
    )
    if prior is not None:
        return {**prior.response, "idempotent_replay": True}
    snapshot = recompute_baseline(
        db,
        profile_id=scope.profile.id,
        definition=definition,
    )
    response = {
        **serialize_snapshot(snapshot, definition),
        "idempotent_replay": False,
    }
    command = store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        status_code=200,
        response=response,
    )
    add_outbox(
        db,
        event_id=hashlib.sha256(
            (
                f"{scope.profile.id}:{scope.actor.id}:{operation}:"
                f"{idempotency_key}"
            ).encode()
        ).hexdigest(),
        profile_id=scope.profile.id,
        aggregate_type="baseline_snapshot",
        aggregate_public_id=snapshot.public_id,
        event_type="lifemap.baseline.recomputed",
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity="baseline_snapshot",
        entity_id=snapshot.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    response["command_id"] = command.public_id
    command.response_json = {**response}
    db.commit()
    return response


@router.get("/baselines")
def baselines(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict]:
    scope = _scope(db, token, x_profile)
    record_types = db.execute(
        select(WearableDailyAggregate.record_type)
        .where(WearableDailyAggregate.profile_id == scope.profile.id)
        .distinct()
    ).scalars()
    return [_baseline(db, scope.profile.id, signal) for signal in record_types]


def _baseline(db: Session, profile_id: int, signal_key: str) -> dict:
    rows = list(
        db.execute(
            select(WearableDailyAggregate)
            .where(
                WearableDailyAggregate.profile_id == profile_id,
                WearableDailyAggregate.record_type == signal_key,
            )
            .order_by(WearableDailyAggregate.local_date.desc())
            .limit(28)
        ).scalars()
    )
    values = [value for row in rows if (value := _aggregate_value(row)) is not None]
    if len(values) < 7:
        return {
            "signal_key": signal_key,
            "status": "insufficient_data",
            "sample_days": len(values),
            "minimum_days": 7,
        }
    return {
        "signal_key": signal_key,
        "status": "ready",
        "median": median(values),
        "sample_days": len(values),
        "window_days": 28,
        "policy_version": "rolling-median-v1",
        "latest_date": rows[0].local_date,
    }


@router.get("/baselines/{signal_key}")
def baseline(
    signal_key: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile)
    return _baseline(db, scope.profile.id, signal_key)


@router.get("/episodes/{episode_id}/next-question")
def episode_next_question(
    episode_id: str,
    locale: str = "vi",
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Next-best-question for an episode (Phase 2, P2-WP5).

    Default-off: when ``LIFEMAP_NEXT_QUESTION_ENABLED`` is unset the feature is
    disabled and returns a 404, preserving prior behavior. When enabled the
    engine returns at most one highest-value question, or an explicit
    'ask nothing' result with a reason code.
    """

    settings = get_settings()
    if not (
        settings.lifemap_next_question_enabled
        or settings.lifemap_next_question_v2_enabled
    ):
        raise HTTPException(status_code=404, detail="Feature not enabled")
    scope = _scope(db, token, x_profile)
    if settings.lifemap_next_question_v2_enabled:
        ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
        if not settings.lifemap_capture_enabled:
            return {
                "episode_id": episode_id,
                "ask": False,
                "policy_version": "next-best-question-v2",
                "reason_code": "capture_unavailable",
            }
    episode = _episode_for_profile(db, scope.profile.id, episode_id)
    result = compute_next_best_question(
        db,
        profile_id=scope.profile.id,
        episode=episode,
        locale=locale,
        governed_only=settings.lifemap_next_question_v2_enabled,
    )
    return {"episode_id": episode.public_id, **result.as_dict()}


@router.post("/episodes/{episode_id}/questions/{question_id}/interaction")
def record_question_interaction(
    episode_id: str,
    question_id: str,
    payload: QuestionInteractionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    settings = get_settings()
    if not settings.lifemap_next_question_v2_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_not_enabled"})
    if payload.action not in {"presented", "dismissed", "do_not_ask"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_action"})
    scope = _scope(db, token, x_profile, action="update")
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    episode = _episode_for_profile(db, scope.profile.id, episode_id)
    question = db.execute(
        select(LifeMapQuestionDefinition).where(
            LifeMapQuestionDefinition.public_id == question_id,
            LifeMapQuestionDefinition.status == "approved",
            LifeMapQuestionDefinition.approved_at.is_not(None),
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail={"code": "question_not_found"})
    operation = f"question.{payload.action}:{episode.public_id}:{question.public_id}"
    digest = request_digest(payload.model_dump(mode="json"))
    prior = replay_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
    )
    if prior is not None:
        return {**prior.response, "idempotent_replay": True}
    cooldown = (
        datetime.now(UTC) + timedelta(days=30)
        if payload.action == "dismissed"
        else None
    )
    interaction = LifeMapQuestionInteraction(
        profile_id=scope.profile.id,
        episode_id=episode.id,
        question_definition_id=question.id,
        action=payload.action,
        reason_code=payload.reason.strip(),
        cooldown_until=cooldown,
    )
    db.add(interaction)
    db.flush()
    response = {
        "id": interaction.public_id,
        "action": interaction.action,
        "cooldown_until": (
            interaction.cooldown_until.isoformat()
            if interaction.cooldown_until is not None
            else None
        ),
        "idempotent_replay": False,
    }
    command = store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        status_code=200,
        response=response,
    )
    response["command_id"] = command.public_id
    command.response_json = {**response}
    add_outbox(
        db,
        event_id=hashlib.sha256(
            (
                f"{scope.profile.id}:{scope.actor.id}:{operation}:"
                f"{idempotency_key}"
            ).encode()
        ).hexdigest(),
        profile_id=scope.profile.id,
        aggregate_type="question_interaction",
        aggregate_public_id=interaction.public_id,
        event_type=f"lifemap.question.{payload.action}",
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity="question_interaction",
        entity_id=interaction.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return response


@router.get("/episodes/{episode_id}/replay")
def episode_replay(
    episode_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile)
    episode = _episode_for_profile(db, scope.profile.id, episode_id)
    linked_revisions = list(
        db.execute(
            select(LifeMapEpisodeEventLink, LifeMapEvent, LifeMapEventRevision)
            .join(LifeMapEvent, LifeMapEvent.id == LifeMapEpisodeEventLink.event_id)
            .join(
                LifeMapEventRevision,
                LifeMapEventRevision.id
                == LifeMapEpisodeEventLink.event_revision_id,
            )
            .where(
                LifeMapEpisodeEventLink.profile_id == scope.profile.id,
                LifeMapEpisodeEventLink.episode_id == episode.id,
                LifeMapEpisodeEventLink.status == "active",
            )
            .order_by(LifeMapEvent.occurred_at, LifeMapEvent.id)
        ).all()
    )
    event_revisions: list[tuple[LifeMapEvent, LifeMapEventRevision]] = [
        (event, revision) for _link, event, revision in linked_revisions
    ]
    # Compatibility for pre-migration fixtures/databases. Production migration
    # 0034 materializes these links; new commands always create them.
    if not event_revisions:
        event_revisions = [
            (event, revision)
            for event, revision in db.execute(
                select(LifeMapEvent, LifeMapEventRevision)
                .join(
                    LifeMapEventRevision,
                    (LifeMapEventRevision.event_id == LifeMapEvent.id)
                    & (
                        LifeMapEventRevision.revision_no
                        == LifeMapEvent.current_revision_no
                    ),
                )
                .where(
                    LifeMapEvent.profile_id == scope.profile.id,
                    LifeMapEvent.episode_id == episode.id,
                )
                .order_by(LifeMapEvent.occurred_at, LifeMapEvent.id)
            ).all()
        ]
    tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(
                LifeMapCareTask.profile_id == scope.profile.id,
                LifeMapCareTask.episode_id == episode.id,
            )
            .order_by(LifeMapCareTask.id)
        ).scalars()
    )
    decisions = list(
        db.execute(
            select(LifeMapDecisionLedger)
            .where(
                LifeMapDecisionLedger.profile_id == scope.profile.id,
                LifeMapDecisionLedger.episode_id == episode.id,
            )
            .order_by(LifeMapDecisionLedger.id)
        ).scalars()
    )
    return {
        "episode": {
            "id": episode.public_id,
            "title": episode.title,
            "status": episode.status,
        },
        "events": [
            {
                "id": event.public_id,
                "revision_id": revision.public_id,
                "revision": revision.revision_no,
                "type": event.event_type,
                "truth_state": revision.truth_state,
                "occurred_at": event.occurred_at,
                "provenance": revision.provenance_json,
                "source_reference": (
                    str(revision.source_reference_id)
                    if revision.source_reference_id is not None
                    else None
                ),
                "policy_version": revision.policy_version,
                "why": {
                    "code": revision.reason_code or "recorded",
                    "text": "Included from your confirmed or reported LifeMap history.",
                },
            }
            for event, revision in event_revisions
        ],
        "tasks": [
            {"id": row.public_id, "title": row.title, "status": row.status}
            for row in tasks
        ],
        "decisions": [
            {
                "id": row.public_id,
                "type": row.decision_type,
                "disposition": row.disposition,
                "policy_version": row.policy_version,
                "stale": _decision_is_stale(db, scope.profile.id, row),
                "why": _consumer_why(row),
            }
            for row in decisions
        ],
    }


def _consumer_why(row: LifeMapDecisionLedger) -> dict:
    rationale = row.rationale_json if isinstance(row.rationale_json, dict) else {}
    code = str(rationale.get("reason_code") or row.decision_type)
    summary = rationale.get("summary")
    return {
        "code": code,
        "text": (
            str(summary)
            if isinstance(summary, str) and summary.strip()
            else "This result was produced from the listed LifeMap facts and policy version."
        ),
    }


def _decision_is_stale(
    db: Session, profile_id: int, row: LifeMapDecisionLedger
) -> bool:
    revision_ids = list(
        db.execute(
            select(LifeMapDecisionInput.event_revision_id).where(
                LifeMapDecisionInput.profile_id == profile_id,
                LifeMapDecisionInput.decision_id == row.id,
            )
        ).scalars()
    )
    if not revision_ids:
        return False
    return (
        db.execute(
            select(LifeMapProjectionDependency.id).where(
                LifeMapProjectionDependency.profile_id == profile_id,
                LifeMapProjectionDependency.input_revision_id.in_(revision_ids),
                LifeMapProjectionDependency.invalidated_at.is_not(None),
            )
        ).first()
        is not None
    )


def _owned_decision(
    db: Session, profile_id: int, decision_id: str
) -> LifeMapDecisionLedger:
    selector = LifeMapDecisionLedger.public_id == decision_id
    if decision_id.isdecimal():
        selector = selector | (LifeMapDecisionLedger.id == int(decision_id))
    row = db.execute(
        select(LifeMapDecisionLedger).where(
            selector,
            LifeMapDecisionLedger.profile_id == profile_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


@router.get("/decisions/{decision_id}")
def decision(
    decision_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile)
    row = _owned_decision(db, scope.profile.id, decision_id)
    return {
        "id": row.public_id,
        "decision_type": row.decision_type,
        "disposition": row.disposition,
        "inputs": row.inputs_json,
        "rationale": row.rationale_json,
        "evidence": row.evidence_json,
        "policy_version": row.policy_version,
        "stale": _decision_is_stale(db, scope.profile.id, row),
        "why": _consumer_why(row),
        "created_at": row.created_at,
    }


@router.post("/decisions/{decision_id}/dispute", status_code=201)
def dispute_decision(
    decision_id: str,
    payload: DecisionDisputeRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile, action="dispute")
    original = _owned_decision(db, scope.profile.id, decision_id)
    dispute = LifeMapDecisionLedger(
        profile_id=scope.profile.id,
        episode_id=original.episode_id,
        decision_type="decision_dispute",
        disposition="deferred",
        inputs_json={"disputed_decision_id": original.public_id},
        rationale_json={"actor": "user", "reason": payload.reason.strip()},
        evidence_json=None,
        policy_version="user-dispute-v1",
        expires_at=None,
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return {
        "id": dispute.public_id,
        "disputed_decision_id": original.public_id,
        "status": "recorded",
        "recorded_at": datetime.now(UTC),
    }
