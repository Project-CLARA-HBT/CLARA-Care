"""Phase-5, evidence-first APIs built on the existing clinical ledger.

This module deliberately does *not* turn a question into medical advice.  It
uses ``ClinicalCase`` as the durable evidence-question container and
``ClinicalWorkflowRun`` / ``EvidenceRecord`` as the run and provenance ledger.
That keeps the Phase-5 vertical slice migration-safe while a dedicated evidence
schema is introduced later.

Only a successful, non-fallback Research run with explicitly supplied source
class and stable provenance can become an evidence matrix row.  Everything
else is an ``evidence_unavailable`` outcome: a useful, safe state rather than
a made-up clinical synthesis.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.config import get_settings
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    ClinicalCase,
    ClinicalStageRun,
    ClinicalWorkflowRun,
    EvidenceApplicabilityRule,
    EvidenceChangeAssessment,
    EvidenceChangeNotification,
    EvidenceMonitorJob,
    EvidenceRecord,
    EvidenceRunSubscription,
    GuidelineArtifact,
    LifeMapEpisode,
    LifeMapEvent,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal, get_db
from clara_api.lifemap.evidence_monitor import (
    EvidenceMonitorError,
    evaluate_applicability,
    review_change_assessment,
    validate_applicability_rule,
)

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))
REVIEWER = Depends(require_roles("doctor", "admin"))

_QUESTION_CASE_TYPE = "lifemap_evidence_question"
_PROTOCOL = "evidence_brief"
_SCHEMA_VERSION = "2026-07-25.5"
_SOURCE_CLASS_ALIASES = {
    "guideline": "guideline",
    "clinical_guideline": "guideline",
    "consensus": "guideline",
    "consensus_statement": "guideline",
    "rct": "primary_randomized_trial",
    "randomized_trial": "primary_randomized_trial",
    "randomized_controlled_trial": "primary_randomized_trial",
    "primary_randomized_trial": "primary_randomized_trial",
    "observational": "primary_observational",
    "cohort": "primary_observational",
    "case_control": "primary_observational",
    "diagnostic_study": "primary_diagnostic",
    "prognostic_study": "primary_prognostic",
    "systematic_review": "systematic_review",
    "meta_analysis": "systematic_review",
    "review": "review",
    "editorial": "editorial_commentary",
    "commentary": "editorial_commentary",
    "letter": "editorial_commentary",
}
_NON_EDITORIAL_CLASSES = frozenset(
    {
        "guideline",
        "primary_randomized_trial",
        "primary_observational",
        "primary_diagnostic",
        "primary_prognostic",
        "systematic_review",
        "review",
    }
)
_TRUSTED_RESEARCH_PROVIDERS = frozenset(
    {
        "pubmed",
        "europepmc",
        "clinicaltrials",
        "clinicaltrials.gov",
        "cochrane",
        "who",
        "nice",
        "cdc",
        "moh",
        "vn_moh",
    }
)


class EvidenceQuestionCreate(BaseModel):
    question: str = Field(min_length=8, max_length=4_000)
    population_context: str = Field(default="", max_length=2_000)
    intervention_or_exposure: str = Field(default="", max_length=1_000)
    comparator: str = Field(default="", max_length=1_000)
    outcomes: list[str] = Field(default_factory=list, max_length=12)
    time_horizon: str = Field(default="", max_length=500)
    guideline_jurisdiction: str = Field(default="", max_length=120)
    exclusions: list[str] = Field(default_factory=list, max_length=20)
    confirmed: bool = False
    question_class: str = Field(default="general", min_length=1, max_length=64)


class EvidenceQuestionUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=8, max_length=4_000)
    population_context: str | None = Field(default=None, max_length=2_000)
    intervention_or_exposure: str | None = Field(default=None, max_length=1_000)
    comparator: str | None = Field(default=None, max_length=1_000)
    outcomes: list[str] | None = Field(default=None, max_length=12)
    time_horizon: str | None = Field(default=None, max_length=500)
    guideline_jurisdiction: str | None = Field(default=None, max_length=120)
    exclusions: list[str] | None = Field(default=None, max_length=20)
    confirmed: bool | None = None


class EvidenceSubscriptionCreate(BaseModel):
    delivery_channel: Literal["in_app"] = "in_app"
    interval_hours: int = Field(default=168, ge=24, le=720)


class EvidenceSubscriptionUpdate(BaseModel):
    interval_hours: int = Field(ge=24, le=720)


class EvidenceAssessmentReview(BaseModel):
    action: Literal["accept", "reject"]
    reason: str = Field(default="", max_length=255)


class EvidenceApplicabilityRuleCreate(BaseModel):
    question_class: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=64)
    required_fact_types: list[str] = Field(min_length=1, max_length=32)
    rule: dict[str, Any]


class EvidenceApplicabilityRuleReview(BaseModel):
    action: Literal["approve", "retire"]


def _user_profile(db: Session, token: TokenPayload) -> tuple[User, PhrProfile]:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    return user, profile


def _episode(db: Session, profile_id: int, episode_id: str | int) -> LifeMapEpisode:
    episode_ref = str(episode_id)
    selector = LifeMapEpisode.public_id == episode_ref
    if episode_ref.isdigit():
        selector = selector | (LifeMapEpisode.id == int(episode_ref))
    episode = db.execute(
        select(LifeMapEpisode).where(
            selector, LifeMapEpisode.profile_id == profile_id
        )
    ).scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


def _question_case(db: Session, user_id: int, question_id: str | int) -> ClinicalCase:
    reference = str(question_id)
    selector = ClinicalCase.public_id == reference
    if reference.isdecimal():
        selector = selector | (ClinicalCase.id == int(reference))
    item = db.execute(
        select(ClinicalCase).where(
            selector,
            ClinicalCase.owner_user_id == user_id,
            ClinicalCase.case_type == _QUESTION_CASE_TYPE,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Evidence question not found")
    return item


def _question_data(item: ClinicalCase) -> dict[str, Any]:
    metadata = item.metadata_json if isinstance(item.metadata_json, dict) else {}
    question = metadata.get("evidence_question")
    if not isinstance(question, dict):
        # A malformed legacy row must never be silently treated as a usable question.
        raise HTTPException(status_code=409, detail="Evidence question record is invalid")
    return question


def _clean_terms(values: list[str]) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _compile_question(
    payload: EvidenceQuestionCreate | EvidenceQuestionUpdate,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile only user-confirmed fields; this is intentionally not LLM inference."""

    previous = dict(base or {})
    supplied = payload.model_dump(exclude_unset=True)
    for key, value in supplied.items():
        if isinstance(value, str):
            previous[key] = value.strip()
        elif isinstance(value, list):
            previous[key] = _clean_terms(value)
        else:
            previous[key] = value

    required_dimensions = ("population_context", "outcomes", "time_horizon")
    missing = [key for key in required_dimensions if not previous.get(key)]
    previous["schema_version"] = _SCHEMA_VERSION
    previous["study_design_needs"] = [
        "guideline",
        "primary_randomized_trial",
        "primary_observational",
        "systematic_review",
        "editorial_commentary",
    ]
    previous["missing_dimensions"] = missing
    previous["requires_confirmation"] = not bool(previous.get("confirmed"))
    previous["compiler_provenance"] = "user_confirmed_fields_only"
    return previous


def _serialize_question(item: ClinicalCase) -> dict[str, Any]:
    data = _question_data(item)
    return {
        "id": item.public_id,
        "episode_id": str(data.get("episode_id")),
        "question": data.get("question", ""),
        "compiled": data,
        "confirmed": bool(data.get("confirmed")),
        "requires_confirmation": bool(data.get("requires_confirmation")),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _source_class(raw: Any) -> str | None:
    normalized = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _SOURCE_CLASS_ALIASES.get(normalized)


def _stable_identifiers(raw: dict[str, Any]) -> dict[str, str]:
    identifiers: dict[str, str] = {}
    for key in ("source_id", "study_id", "pmid", "doi", "nct"):
        value = raw.get(key)
        if value is not None and str(value).strip():
            identifiers[key] = str(value).strip()[:512]
    return identifiers


def _accepted_evidence(
    raw_citations: Any, *, research_result: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Accept only source records with explicit, inspectable provenance.

    We deliberately reject a citation that merely says "a study".  The user can
    see an unavailable state and retry later rather than receive a synthesized
    claim whose source cannot be audited.
    """

    reasons: list[str] = []
    if bool(research_result.get("fallback")) or bool(research_result.get("fallback_used")):
        return [], ["research_fallback_not_evidence"]
    gate = research_result.get("quality_gate")
    if not isinstance(gate, dict) or gate.get("passed") is not True:
        return [], ["research_quality_gate_not_passed"]
    if not isinstance(raw_citations, list):
        return [], ["no_citation_records"]

    accepted: list[dict[str, Any]] = []
    for raw in raw_citations:
        if not isinstance(raw, dict):
            continue
        provider = str(raw.get("source") or "").strip().lower()
        source_class = _source_class(raw.get("source_type") or raw.get("study_design"))
        identifiers = _stable_identifiers(raw)
        if provider not in _TRUSTED_RESEARCH_PROVIDERS:
            continue
        if source_class is None or not identifiers:
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        url = str(raw.get("url") or raw.get("link") or "").strip()
        accepted.append(
            {
                "provider": provider,
                "source_class": source_class,
                "study_design": str(raw.get("study_design") or raw.get("source_type")).strip(),
                "identifiers": identifiers,
                "title": title[:500],
                "url": url[:2_000] or None,
                "excerpt": str(raw.get("excerpt") or raw.get("snippet") or "")[:4_000],
                "published_at": raw.get("published_at"),
                "trust_tier": raw.get("trust_tier"),
                "citation_id": str(
                    raw.get("citation_id") or raw.get("source_id") or raw.get("study_id") or ""
                ).strip(),
            }
        )

    if not accepted:
        reasons.append("no_verified_provenance_records")
    if accepted and not any(item["source_class"] in _NON_EDITORIAL_CLASSES for item in accepted):
        # Editorials are visible in a matrix, but cannot release an evidence conclusion.
        reasons.append("editorial_only_evidence")
    return accepted, reasons


def _uncertainty(
    question: dict[str, Any], *, release_status: str, structured_contradictions: bool
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = [
        {
            "dimension": "applicability",
            "status": "not_assessed",
            "reason": "No validated executable eligibility rule was available for this run.",
        }
    ]
    for dimension in question.get("missing_dimensions", []):
        notes.append(
            {
                "dimension": "personal_context",
                "status": "unknown",
                "reason": f"Required context is missing: {dimension}.",
            }
        )
    if not structured_contradictions:
        notes.append(
            {
                "dimension": "contradictions",
                "status": "limited",
                "reason": (
                    "No structured contradiction result was supplied by the verified "
                    "research run."
                ),
            }
        )
    if release_status == "evidence_unavailable":
        notes.append(
            {
                "dimension": "evidence",
                "status": "unavailable",
                "reason": (
                    "CLARA did not release a clinical conclusion without verified evidence "
                    "provenance."
                ),
            }
        )
    return notes


def _run_summary(
    run: ClinicalWorkflowRun,
    evidence: list[EvidenceRecord] | None = None,
    *,
    case_public_id: str = "",
) -> dict[str, Any]:
    summary = run.result_summary_json if isinstance(run.result_summary_json, dict) else {}
    rows = evidence or []
    pending = run.status in {"queued", "running"}
    return {
        "id": run.public_id,
        "evidence_question_id": case_public_id,
        "status": run.status,
        "release_status": summary.get(
            "release_status", "pending" if pending else "evidence_unavailable"
        ),
        "evidence_count": (
            len(rows) if evidence is not None else int(summary.get("evidence_count", 0))
        ),
        "source_class_counts": summary.get("source_class_counts", {}),
        "uncertainty": summary.get("uncertainty", []),
        "safe_message": summary.get(
            "safe_message",
            (
                "Verified evidence retrieval is still running."
                if pending
                else "No clinical conclusion is released."
            ),
        ),
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }


def _owned_run(
    db: Session, user_id: int, run_id: str | int
) -> ClinicalWorkflowRun:
    reference = str(run_id)
    selector = ClinicalWorkflowRun.public_id == reference
    if reference.isdecimal():
        selector = selector | (ClinicalWorkflowRun.id == int(reference))
    run = db.execute(
        select(ClinicalWorkflowRun)
        .join(ClinicalCase, ClinicalCase.id == ClinicalWorkflowRun.case_id)
        .where(
            selector,
            ClinicalWorkflowRun.owner_user_id == user_id,
            ClinicalWorkflowRun.protocol == _PROTOCOL,
            ClinicalCase.case_type == _QUESTION_CASE_TYPE,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Evidence run not found")
    return run


def _subscription_view(
    item: EvidenceRunSubscription, *, run_public_id: str
) -> dict[str, Any]:
    return {
        "id": item.public_id,
        "evidence_run_id": run_public_id,
        "status": item.status,
        "delivery_channel": item.delivery_channel,
        "interval_hours": item.interval_hours,
        "next_check_at": item.next_check_at,
        "last_checked_at": item.last_checked_at,
        "created_at": item.created_at,
        "revoked_at": item.revoked_at,
    }


def _owned_subscription(
    db: Session, *, user_id: int, reference: str
) -> EvidenceRunSubscription:
    selector = EvidenceRunSubscription.public_id == reference
    if reference.isdecimal():
        selector = selector | (EvidenceRunSubscription.id == int(reference))
    item = db.execute(
        select(EvidenceRunSubscription).where(
            selector,
            EvidenceRunSubscription.user_id == user_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Evidence subscription not found")
    return item


def _structured_contradictions(
    result: dict[str, Any], accepted_ids: set[str]
) -> list[dict[str, Any]]:
    raw_items = result.get("conflicting_evidence")
    if not isinstance(raw_items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        ids = item.get("citation_ids") or item.get("contrasting_citation_ids")
        if not isinstance(ids, list):
            continue
        cited = [str(value).strip() for value in ids if str(value).strip()]
        if cited and all(value in accepted_ids for value in cited):
            normalized.append(
                {
                    "claim": str(item.get("claim") or "").strip(),
                    "citation_ids": cited,
                    "classification": "pipeline_reported_conflict",
                }
            )
    return normalized


def _execute_evidence_run(run_id: int, token_data: dict[str, Any]) -> None:
    """Execute one persisted evidence run outside the request DB session.

    FastAPI invokes this through ``BackgroundTasks`` after the 202 response is
    sent.  A fresh session is essential: request-scoped sessions are closed as
    soon as the response lifecycle finishes.
    """

    with SessionLocal() as db:
        try:
            run = db.execute(
                select(ClinicalWorkflowRun)
                .where(ClinicalWorkflowRun.id == run_id)
                .with_for_update()
            ).scalar_one_or_none()
            if run is None or run.protocol != _PROTOCOL or run.status != "running":
                # Missing, completed, failed, or duplicate worker delivery: no-op.
                return
            stage = db.execute(
                select(ClinicalStageRun).where(
                    ClinicalStageRun.workflow_run_id == run.id,
                    ClinicalStageRun.stage_key == "research_retrieval",
                )
            ).scalar_one()
            question_case = db.get(ClinicalCase, run.case_id)
            if question_case is None:
                raise RuntimeError("Evidence question was removed before retrieval")
            question = _question_data(question_case)

            # Import lazily so the existing Research endpoint remains the single
            # retrieval/harness owner. Its answer prose is intentionally discarded.
            from clara_api.api.v1.endpoints.research import research_tier2

            research_result = research_tier2(
                {
                    "query": str(question.get("question") or ""),
                    "research_mode": "deep",
                    "retrieval_stack_mode": "full",
                    "ui_language": "vi",
                    "source_mode": "scientific",
                    "output_profile": "researcher",
                },
                token=TokenPayload(token_data),
                db=db,
            )
            accepted, rejection_reasons = _accepted_evidence(
                research_result.get("citations"), research_result=research_result
            )
            release_status = (
                "evidence_available"
                if accepted and not rejection_reasons
                else "evidence_unavailable"
            )
            accepted_ids = {item["citation_id"] for item in accepted if item["citation_id"]}
            contradictions = _structured_contradictions(research_result, accepted_ids)
            source_counts: dict[str, int] = defaultdict(int)
            retrieved_at = datetime.now(UTC)
            if release_status == "evidence_available":
                for item in accepted:
                    source_counts[item["source_class"]] += 1
                    db.add(
                        EvidenceRecord(
                            case_id=question_case.id,
                            workflow_run_id=run.id,
                            source_type=item["source_class"],
                            source_id=(
                                item["identifiers"].get("study_id")
                                or item["identifiers"].get("source_id")
                                or item["identifiers"].get("pmid")
                                or item["identifiers"].get("doi")
                                or item["identifiers"].get("nct")
                                or ""
                            ),
                            title=item["title"],
                            citation_json={
                                "provider": item["provider"],
                                "source_class": item["source_class"],
                                "study_design": item["study_design"],
                                "identifiers": item["identifiers"],
                                "url": item["url"],
                                "published_at": item["published_at"],
                                "trust_tier": item["trust_tier"],
                                "retrieval_query": question.get("question"),
                                "retrieval_at": retrieved_at.isoformat(),
                            },
                            excerpt=item["excerpt"],
                            evidence_level=item["source_class"],
                        )
                    )
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.result_summary_json = {
                "release_status": release_status,
                "evidence_count": (
                    len(accepted) if release_status == "evidence_available" else 0
                ),
                "source_class_counts": dict(source_counts),
                "rejection_reasons": rejection_reasons,
                "contradictions": contradictions,
                "uncertainty": _uncertainty(
                    question,
                    release_status=release_status,
                    structured_contradictions=bool(contradictions),
                ),
                "safe_message": (
                    "Evidence records are available for inspection. CLARA has not generated "
                    "individual treatment advice."
                    if release_status == "evidence_available"
                    else (
                        "No clinical conclusion is released because verified evidence "
                        "provenance was unavailable or incomplete."
                    )
                ),
            }
            stage.status = "completed"
            stage.completed_at = run.completed_at
            db.commit()
        except Exception:
            db.rollback()
            run = db.get(ClinicalWorkflowRun, run_id)
            if run is None or run.status != "running":
                return
            failed_stage = db.execute(
                select(ClinicalStageRun).where(
                    ClinicalStageRun.workflow_run_id == run.id,
                    ClinicalStageRun.stage_key == "research_retrieval",
                )
            ).scalar_one_or_none()
            run.status = "failed"
            run.failure_code = "research_unavailable"
            run.completed_at = datetime.now(UTC)
            run.result_summary_json = {
                "release_status": "evidence_unavailable",
                "evidence_count": 0,
                "source_class_counts": {},
                "uncertainty": [],
                "safe_message": (
                    "No clinical conclusion is released because verified evidence retrieval "
                    "failed."
                ),
            }
            if failed_stage is not None:
                failed_stage.status = "failed"
                failed_stage.error_code = "research_unavailable"
                failed_stage.completed_at = run.completed_at
            db.commit()


@router.post("/episodes/{episode_id}/evidence-questions", status_code=status.HTTP_201_CREATED)
def create_evidence_question(
    episode_id: str,
    payload: EvidenceQuestionCreate,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _user_profile(db, token)
    episode = _episode(db, profile.id, episode_id)
    compiled = _compile_question(payload)
    compiled["episode_id"] = episode.public_id
    item = ClinicalCase(
        owner_user_id=user.id,
        title=payload.question.strip()[:255],
        case_type=_QUESTION_CASE_TYPE,
        metadata_json={"evidence_question": compiled},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_question(item)


@router.get("/evidence-questions/{question_id}")
def get_evidence_question(
    question_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _user_profile(db, token)
    item = _question_case(db, user.id, question_id)
    _episode(db, profile.id, str(_question_data(item).get("episode_id") or ""))
    return _serialize_question(item)


@router.patch("/evidence-questions/{question_id}")
def update_evidence_question(
    question_id: str,
    payload: EvidenceQuestionUpdate,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _user_profile(db, token)
    item = _question_case(db, user.id, question_id)
    existing = _question_data(item)
    _episode(db, profile.id, str(existing.get("episode_id") or ""))
    updated = _compile_question(payload, existing)
    updated["episode_id"] = existing["episode_id"]
    item.metadata_json = {"evidence_question": updated}
    if payload.question is not None:
        item.title = payload.question.strip()[:255]
    db.commit()
    db.refresh(item)
    return _serialize_question(item)


@router.post("/evidence-questions/{question_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_evidence_question(
    question_id: str,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Persist and enqueue deep Research, returning before retrieval starts."""

    user, profile = _user_profile(db, token)
    question_case = _question_case(db, user.id, question_id)
    question = _question_data(question_case)
    _episode(db, profile.id, str(question.get("episode_id") or ""))
    if not question.get("confirmed"):
        raise HTTPException(
            status_code=409,
            detail="Review and confirm the compiled question before running deep research",
        )
    existing = db.execute(
        select(ClinicalWorkflowRun).where(
            ClinicalWorkflowRun.owner_user_id == user.id,
            ClinicalWorkflowRun.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.case_id != question_case.id or existing.protocol != _PROTOCOL:
            raise HTTPException(
                status_code=409, detail="Idempotency-Key was used for another request"
            )
        return {
            **_run_summary(
                existing, case_public_id=question_case.public_id
            ),
            "idempotent_replay": True,
        }

    now = datetime.now(UTC)
    run = ClinicalWorkflowRun(
        case_id=question_case.id,
        owner_user_id=user.id,
        protocol=_PROTOCOL,
        status="running",
        idempotency_key=idempotency_key,
        request_json={
            "schema_version": _SCHEMA_VERSION,
            "question": question,
            "retrieval_contract": {
                "mode": "deep",
                "source_classes": question["study_design_needs"],
                "no_fallback_evidence": True,
            },
        },
        started_at=now,
    )
    stage = ClinicalStageRun(
        workflow_run_id=0,  # replaced after the run is flushed
        stage_key="research_retrieval",
        status="running",
        started_at=now,
    )
    try:
        db.add(run)
        db.flush()
        stage.workflow_run_id = run.id
        db.add(stage)
        db.commit()
    except IntegrityError:
        # A concurrent request may pass the read check before the unique
        # (owner, idempotency key) constraint commits. Resolve it as the same
        # idempotent replay instead of leaking a database error.
        db.rollback()
        existing = db.execute(
            select(ClinicalWorkflowRun).where(
                ClinicalWorkflowRun.owner_user_id == user.id,
                ClinicalWorkflowRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if (
            existing is not None
            and existing.case_id == question_case.id
            and existing.protocol == _PROTOCOL
        ):
            return {
                **_run_summary(
                    existing, case_public_id=question_case.public_id
                ),
                "idempotent_replay": True,
            }
        raise HTTPException(
            status_code=409, detail="Idempotency-Key was used for another request"
        ) from None
    db.refresh(run)
    # The worker needs only the stable subject and role, not the complete JWT
    # claims (expiry, token ID, issuer).
    background_tasks.add_task(
        _execute_evidence_run,
        run.id,
        {"sub": token.sub, "role": token.role},
    )
    return {
        **_run_summary(run, case_public_id=question_case.public_id),
        "idempotent_replay": False,
    }


@router.get("/evidence-runs/{run_id}")
def get_evidence_run(
    run_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user = current_user(db, token)
    run = _owned_run(db, user.id, run_id)
    evidence = list(
        db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.workflow_run_id == run.id)
            .order_by(EvidenceRecord.id)
        ).scalars()
    )
    question_case = _question_case(db, user.id, run.case_id)
    return _run_summary(
        run, evidence, case_public_id=question_case.public_id
    )


@router.get("/evidence-runs/{run_id}/matrix")
def get_evidence_matrix(
    run_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user = current_user(db, token)
    run = _owned_run(db, user.id, run_id)
    rows = list(
        db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.workflow_run_id == run.id)
            .order_by(EvidenceRecord.id)
        ).scalars()
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        citation = row.citation_json if isinstance(row.citation_json, dict) else {}
        grouped[row.source_type].append(
            {
                "evidence_id": row.public_id,
                "title": row.title,
                "source_class": row.source_type,
                "study_design": citation.get("study_design"),
                "identifiers": citation.get("identifiers", {}),
                "provider": citation.get("provider"),
                "url": citation.get("url"),
                "published_at": citation.get("published_at"),
                "excerpt": row.excerpt,
                "retrieved_at": row.retrieved_at,
            }
        )
    return {
        "run_id": run.public_id,
        "release_status": _run_summary(run, rows)["release_status"],
        "source_classes": {key: value for key, value in sorted(grouped.items())},
        "unavailable_reason": (
            None
            if rows
            else "No verified, source-classed evidence records were released for this run."
        ),
    }


@router.get("/evidence-runs/{run_id}/applicability")
def get_applicability(
    run_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user = current_user(db, token)
    run = _owned_run(db, user.id, run_id)
    question = _question_data(_question_case(db, user.id, run.case_id))
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    episode = _episode(
        db, profile.id, str(question.get("episode_id") or "")
    )
    question_class = str(question.get("question_class") or "general")
    rule = (
        db.execute(
            select(EvidenceApplicabilityRule)
            .where(
                EvidenceApplicabilityRule.question_class == question_class,
                EvidenceApplicabilityRule.status == "approved",
                EvidenceApplicabilityRule.approved_at.is_not(None),
                EvidenceApplicabilityRule.approved_by_user_id.is_not(None),
            )
            .order_by(EvidenceApplicabilityRule.id.desc())
        )
        .scalars()
        .first()
    )
    facts: dict[str, Any] = {}
    for event in db.execute(
        select(LifeMapEvent).where(
            LifeMapEvent.profile_id == profile.id,
            LifeMapEvent.episode_id == episode.id,
            LifeMapEvent.truth_state == "confirmed",
        )
    ).scalars():
        payload = event.payload_json if isinstance(event.payload_json, dict) else {}
        if "value" in payload:
            facts[event.event_type] = payload["value"]
    result = evaluate_applicability(rule=rule, confirmed_facts=facts)
    return {
        "run_id": run.public_id,
        **result,
        "critical_exclusions": [],
        "safe_message": (
            "Applicability was compared only with confirmed facts; this is not "
            "diagnosis, eligibility confirmation, or treatment advice."
            if result["status"] in {"match", "mismatch"}
            else (
                "Applicability was not assessed because an approved rule or "
                "required confirmed facts were unavailable."
            )
        ),
    }


@router.get("/evidence-runs/{run_id}/contradictions")
def get_contradictions(
    run_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user = current_user(db, token)
    run = _owned_run(db, user.id, run_id)
    summary = run.result_summary_json if isinstance(run.result_summary_json, dict) else {}
    items = summary.get("contradictions") if isinstance(summary.get("contradictions"), list) else []
    return {
        "run_id": run.public_id,
        "status": "reported" if items else "not_assessed",
        "items": items,
        "safe_message": (
            "No structured contradiction result was available; this is not a claim that "
            "evidence agrees."
            if not items
            else (
                "Contradictions were reported by the research pipeline and are linked only "
                "to released evidence identifiers."
            )
        ),
    }


@router.post("/evidence-runs/{run_id}/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe_to_evidence_run(
    run_id: str,
    payload: EvidenceSubscriptionCreate,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Persist an opt-in only; a scheduler still needs material-change adjudication."""

    user, profile = _user_profile(db, token)
    ensure_medical_disclaimer_consent(db, user_id=user.id)
    run = _owned_run(db, user.id, run_id)
    question = _question_data(_question_case(db, user.id, run.case_id))
    _episode(db, profile.id, str(question.get("episode_id") or ""))
    existing = db.execute(
        select(EvidenceRunSubscription).where(
            EvidenceRunSubscription.user_id == user.id,
            EvidenceRunSubscription.workflow_run_id == run.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status == "revoked":
            existing.status = "active"
            existing.revoked_at = None
            existing.delivery_channel = payload.delivery_channel
            existing.interval_hours = payload.interval_hours
            existing.next_check_at = datetime.now(UTC)
            db.commit()
            db.refresh(existing)
            return {
                **_subscription_view(
                    existing, run_public_id=run.public_id
                ),
                "reactivated": True,
            }
        return {
            **_subscription_view(existing, run_public_id=run.public_id),
            "idempotent_replay": True,
        }

    item = EvidenceRunSubscription(
        user_id=user.id,
        profile_id=profile.id,
        workflow_run_id=run.id,
        delivery_channel=payload.delivery_channel,
        interval_hours=payload.interval_hours,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        item = db.execute(
            select(EvidenceRunSubscription).where(
                EvidenceRunSubscription.user_id == user.id,
                EvidenceRunSubscription.workflow_run_id == run.id,
            )
        ).scalar_one()
        return {
            **_subscription_view(item, run_public_id=run.public_id),
            "idempotent_replay": True,
        }
    db.refresh(item)
    return {
        **_subscription_view(item, run_public_id=run.public_id),
        "idempotent_replay": False,
        "monitor_enabled": get_settings().lifemap_evidence_monitor_enabled,
    }


@router.get("/evidence-subscriptions")
def list_evidence_subscriptions(
    db: Session = Depends(get_db), token: TokenPayload = USER
) -> list[dict[str, Any]]:
    user, _ = _user_profile(db, token)
    rows = list(
        db.execute(
            select(EvidenceRunSubscription)
            .where(EvidenceRunSubscription.user_id == user.id)
            .order_by(EvidenceRunSubscription.id.desc())
        ).scalars()
    )
    runs = {
        run.id: run.public_id
        for run in db.execute(
            select(ClinicalWorkflowRun).where(
                ClinicalWorkflowRun.id.in_(
                    {row.workflow_run_id for row in rows} or {-1}
                )
            )
        ).scalars()
    }
    return [
        {
            **_subscription_view(
                row, run_public_id=runs.get(row.workflow_run_id, "")
            ),
            "monitor_enabled": get_settings().lifemap_evidence_monitor_enabled,
        }
        for row in rows
    ]


@router.patch("/evidence-subscriptions/{subscription_id}")
def update_evidence_subscription(
    subscription_id: str,
    payload: EvidenceSubscriptionUpdate,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user = current_user(db, token)
    item = _owned_subscription(
        db, user_id=user.id, reference=subscription_id
    )
    if item.status != "active" or item.revoked_at is not None:
        raise HTTPException(status_code=409, detail="Subscription is not active")
    item.interval_hours = payload.interval_hours
    item.next_check_at = datetime.now(UTC)
    db.commit()
    run = db.get(ClinicalWorkflowRun, item.workflow_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evidence run not found")
    return _subscription_view(item, run_public_id=run.public_id)


@router.delete("/evidence-subscriptions/{subscription_id}")
def delete_evidence_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user = current_user(db, token)
    item = _owned_subscription(db, user_id=user.id, reference=subscription_id)
    if item.status != "revoked":
        item.status = "revoked"
        item.revoked_at = datetime.now(UTC)
        for job in db.execute(
            select(EvidenceMonitorJob).where(
                EvidenceMonitorJob.subscription_id == item.id,
                EvidenceMonitorJob.status.in_(
                    {"pending", "retry", "processing"}
                ),
            )
        ).scalars():
            job.status = "cancelled"
            job.failure_code = "subscription_revoked"
            job.completed_at = item.revoked_at
            job.lease_until = None
        db.commit()
        db.refresh(item)
    run = db.get(ClinicalWorkflowRun, item.workflow_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evidence run not found")
    return _subscription_view(item, run_public_id=run.public_id)


@router.get("/evidence-change-notifications")
def list_evidence_change_notifications(
    db: Session = Depends(get_db), token: TokenPayload = USER
) -> list[dict[str, Any]]:
    user, profile = _user_profile(db, token)
    return [
        {
            "id": row.public_id,
            "status": row.status,
            "payload": row.payload_json,
            "created_at": row.created_at,
            "read_at": row.read_at,
        }
        for row in db.execute(
            select(EvidenceChangeNotification)
            .where(
                EvidenceChangeNotification.user_id == user.id,
                EvidenceChangeNotification.profile_id == profile.id,
            )
            .order_by(EvidenceChangeNotification.id.desc())
        ).scalars()
    ]


@router.post("/evidence-change-notifications/{notification_id}/read")
def read_evidence_change_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _user_profile(db, token)
    selector = EvidenceChangeNotification.public_id == notification_id
    if notification_id.isdecimal():
        selector = selector | (
            EvidenceChangeNotification.id == int(notification_id)
        )
    row = db.execute(
        select(EvidenceChangeNotification).where(
            selector,
            EvidenceChangeNotification.user_id == user.id,
            EvidenceChangeNotification.profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence notification not found")
    if row.status == "unread":
        row.status = "read"
        row.read_at = datetime.now(UTC)
        db.commit()
    return {"id": row.public_id, "status": row.status, "read_at": row.read_at}


@router.get("/admin/evidence-change-assessments")
def list_evidence_change_assessments(
    db: Session = Depends(get_db), _token: TokenPayload = REVIEWER
) -> list[dict[str, Any]]:
    return [
        {
            "id": row.public_id,
            "classification": row.classification,
            "contradiction_status": row.contradiction_status,
            "rule_version": row.rule_version,
            "model_version": row.model_version,
            "review_status": row.review_status,
            "safe_projection": row.safe_projection_json,
            "created_at": row.created_at,
        }
        for row in db.execute(
            select(EvidenceChangeAssessment)
            .where(EvidenceChangeAssessment.review_status == "pending")
            .order_by(EvidenceChangeAssessment.id)
        ).scalars()
    ]


@router.post("/admin/evidence-change-assessments/{assessment_id}/review")
def review_evidence_change(
    assessment_id: str,
    payload: EvidenceAssessmentReview,
    db: Session = Depends(get_db),
    token: TokenPayload = REVIEWER,
) -> dict[str, Any]:
    reviewer = current_user(db, token)
    selector = EvidenceChangeAssessment.public_id == assessment_id
    if assessment_id.isdecimal():
        selector = selector | (EvidenceChangeAssessment.id == int(assessment_id))
    row = db.execute(
        select(EvidenceChangeAssessment).where(selector)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence assessment not found")
    try:
        review_change_assessment(
            db,
            assessment=row,
            reviewer_user_id=reviewer.id,
            action=payload.action,
            reason=payload.reason,
        )
        db.commit()
    except EvidenceMonitorError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": row.public_id, "review_status": row.review_status}


@router.post(
    "/admin/evidence-applicability-rules",
    status_code=status.HTTP_201_CREATED,
)
def create_evidence_applicability_rule(
    payload: EvidenceApplicabilityRuleCreate,
    db: Session = Depends(get_db),
    _token: TokenPayload = REVIEWER,
) -> dict[str, Any]:
    try:
        required, definition = validate_applicability_rule(
            required_fact_types=payload.required_fact_types,
            rule=payload.rule,
        )
    except EvidenceMonitorError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    question_class = payload.question_class.strip()
    version = payload.version.strip()
    if (
        not question_class.replace("_", "").isalnum()
        or not version.replace(".", "").replace("-", "").isalnum()
    ):
        raise HTTPException(status_code=422, detail="Rule identity is invalid")
    row = EvidenceApplicabilityRule(
        question_class=question_class,
        version=version,
        required_fact_types_json=required,
        rule_json=definition,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Rule version already exists"
        ) from error
    db.refresh(row)
    return {
        "id": row.public_id,
        "question_class": row.question_class,
        "version": row.version,
        "required_fact_types": row.required_fact_types_json,
        "rule": row.rule_json,
        "status": row.status,
    }


@router.get("/admin/evidence-applicability-rules")
def list_evidence_applicability_rules(
    db: Session = Depends(get_db),
    _token: TokenPayload = REVIEWER,
) -> list[dict[str, Any]]:
    return [
        {
            "id": row.public_id,
            "question_class": row.question_class,
            "version": row.version,
            "required_fact_types": row.required_fact_types_json,
            "rule": row.rule_json,
            "status": row.status,
            "approved_at": row.approved_at,
        }
        for row in db.execute(
            select(EvidenceApplicabilityRule).order_by(
                EvidenceApplicabilityRule.id.desc()
            )
        ).scalars()
    ]


@router.post("/admin/evidence-applicability-rules/{rule_id}/review")
def review_evidence_applicability_rule(
    rule_id: str,
    payload: EvidenceApplicabilityRuleReview,
    db: Session = Depends(get_db),
    token: TokenPayload = REVIEWER,
) -> dict[str, Any]:
    reviewer = current_user(db, token)
    selector = EvidenceApplicabilityRule.public_id == rule_id
    if rule_id.isdecimal():
        selector = selector | (EvidenceApplicabilityRule.id == int(rule_id))
    row = db.execute(
        select(EvidenceApplicabilityRule).where(selector)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Applicability rule not found")
    if payload.action == "approve":
        validate_applicability_rule(
            required_fact_types=row.required_fact_types_json,
            rule=row.rule_json,
        )
        for active in db.execute(
            select(EvidenceApplicabilityRule).where(
                EvidenceApplicabilityRule.question_class == row.question_class,
                EvidenceApplicabilityRule.status == "approved",
                EvidenceApplicabilityRule.id != row.id,
            )
        ).scalars():
            active.status = "retired"
        row.status = "approved"
        row.approved_by_user_id = reviewer.id
        row.approved_at = datetime.now(UTC)
    else:
        row.status = "retired"
        row.approved_by_user_id = None
        row.approved_at = None
    db.commit()
    return {
        "id": row.public_id,
        "question_class": row.question_class,
        "version": row.version,
        "status": row.status,
        "approved_at": row.approved_at,
    }


@router.get("/guideline-artifacts/{artifact_id}")
def get_guideline_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Read a curator-published artifact. Drafts are deliberately invisible."""

    current_user(db, token)
    selector = GuidelineArtifact.public_id == artifact_id
    if artifact_id.isdecimal():
        selector = selector | (GuidelineArtifact.id == int(artifact_id))
    item = db.execute(
        select(GuidelineArtifact).where(
            selector,
            GuidelineArtifact.status == "published",
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Published guideline artifact not found")
    return {
        "id": item.public_id,
        "title": item.title,
        "version": item.version,
        "status": item.status,
        "provenance": {
            "source_provider": item.source_provider,
            "source_url": item.source_url,
            "source_section": item.source_section,
            "jurisdiction": item.jurisdiction,
            "publication_date": item.publication_date,
            "review_date": item.review_date,
            "approval_status": "approved",
        },
        "intended_population": item.intended_population_json,
        "eligibility_logic": item.eligibility_logic_json,
        "action_options": item.action_options_json,
        "certainty": item.certainty,
        "content": item.content_json,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
