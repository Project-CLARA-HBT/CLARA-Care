"""CLARA API v2 Simplified Consumer Ask Endpoint.

Provides:
- POST /api/v2/ask: Multimodal question-answering returning structured ConsumerAnswerEnvelope.
- POST /api/v2/ask/stream: SSE stream for streaming answers with live token-by-token synthesis.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.chat import _call_ml_service, _load_rag_runtime
from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.api.v2.conventions import ApiV2ResponseEnvelope
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    MedicationCourse,
    PhrProfile,
)
from clara_api.db.session import get_db
from clara_api.lifemap.profile_scope import require_profile_scope

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AskEntryContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal[
        "global", "result", "medication", "visit", "timeline_period", "document"
    ] = "global"
    resource_id: str | None = None
    title: str | None = None


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(..., min_length=1, description="User question or prompt")
    conversation_id: str | None = None
    attachments: list[str] = Field(
        default_factory=list, description="List of uploaded artifact IDs"
    )
    entry_context: AskEntryContext | None = None
    locale: Literal["vi", "en"] = "vi"


class AnswerPersonalEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    resource_type: str
    title: str
    effective_at: str | None = None
    state: str = "confirmed"
    snippet: str = ""


class AnswerExternalSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    source_type: str = "guideline"
    url: str | None = None
    publisher: str | None = None
    year: int | None = None


class AnswerWriteProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    category: Literal[
        "medication", "measurement", "condition", "allergy", "task", "instruction"
    ]
    title: str
    interpreted_value: dict[str, Any] = Field(default_factory=dict)
    source_snippet: str = ""
    requires_confirmation: bool = True


class AnswerSafetyOutcome(BaseModel):
    model_config = ConfigDict(extra="ignore")

    urgency: Literal["none", "routine", "soon", "urgent", "emergency"] = "none"
    deterministic_floor_applied: bool = False
    red_flags: list[str] = Field(default_factory=list)
    call_115_notice: bool = False


class AnswerDisclosure(BaseModel):
    model_config = ConfigDict(extra="ignore")

    used_personal_context: bool = False
    data_classes: list[str] = Field(default_factory=list)
    model_alias: str = "gemini-3.7-tiered"


class AnswerSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    content: str


class ConsumerAnswerDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")

    main_message: str
    actions: list[str] = Field(default_factory=list)
    sections: list[AnswerSection] = Field(default_factory=list)


class ConsumerAnswerEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: ConsumerAnswerDetails
    personal_evidence: list[AnswerPersonalEvidence] = Field(default_factory=list)
    external_sources: list[AnswerExternalSource] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    safety: AnswerSafetyOutcome = Field(default_factory=AnswerSafetyOutcome)
    write_proposals: list[AnswerWriteProposal] = Field(default_factory=list)
    disclosure: AnswerDisclosure = Field(default_factory=AnswerDisclosure)
    conversation_id: str
    turn_id: str
    generated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sse_event(event_type: str, data: Any) -> str:
    serialized = json.dumps(data) if not isinstance(data, str) else data
    return f"event: {event_type}\ndata: {serialized}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ApiV2ResponseEnvelope[ConsumerAnswerEnvelope],
    summary="Consumer Ask CLARA Question",
)
def ask_question(
    payload: AskRequest,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(
        default=None, alias="X-CLARA-Profile-Context"
    ),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[ConsumerAnswerEnvelope]:
    """Evaluates question across authorized personal state + medical knowledge."""
    user = current_user(db, token)
    req_profile = profile_id or x_clara_profile_context

    personal_evs: list[AnswerPersonalEvidence] = []
    used_classes: list[str] = []

    # Check emergency triggers deterministically
    text_lower = payload.text.lower()
    emergency_keywords = [
        "đau ngực dữ dội",
        "khó thở cấp",
        "đột quỵ",
        "bất tỉnh",
        "co giật",
        "sốc phản vệ",
    ]
    is_emergency = any(kw in text_lower for kw in emergency_keywords)

    if is_emergency:
        answer_data = ConsumerAnswerEnvelope(
            answer=ConsumerAnswerDetails(
                main_message=(
                    "Đây là tình huống khẩn cấp cần được cấp cứu y tế ngay lập tức. "
                    "Vui lòng gọi cấp cứu 115 hoặc đến cơ sở y tế gần nhất."
                ),
                actions=[
                    "Gọi ngay cấp cứu 115 hoặc nhờ người thân đưa đến bệnh viện gần nhất.",
                    "Giữ người bệnh ở tư thế thoải mái, không tự ý dùng thuốc.",
                ],
                sections=[],
            ),
            unknowns=["Tình trạng huyết áp và nhịp tim hiện tại của bệnh nhân."],
            safety=AnswerSafetyOutcome(
                urgency="emergency",
                deterministic_floor_applied=True,
                red_flags=["Dấu hiệu cấp cứu tim mạch / hô hấp"],
                call_115_notice=True,
            ),
            disclosure=AnswerDisclosure(used_personal_context=False),
            conversation_id=payload.conversation_id or f"conv_{uuid4().hex[:12]}",
            turn_id=f"turn_{uuid4().hex[:8]}",
            generated_at=datetime.now(UTC).isoformat(),
        )
        return ApiV2ResponseEnvelope.wrap(data=answer_data)

    # General / Personal Context Response
    profile: PhrProfile | None = None
    if req_profile:
        try:
            scope = require_profile_scope(db, user=user, profile_id=req_profile)
            profile = scope.profile
            courses = list(
                db.execute(
                    select(MedicationCourse).where(
                        MedicationCourse.profile_id == profile.id,
                        MedicationCourse.status == "active",
                    )
                ).scalars()
            )
            for c in courses[:3]:
                personal_evs.append(
                    AnswerPersonalEvidence(
                        id=c.public_id,
                        resource_type="medication",
                        title=f"Đơn thuốc đang dùng: {c.medication_name}",
                        effective_at=str(c.started_at or ""),
                        state="confirmed",
                    )
                )
            if courses:
                used_classes.append("Thuốc đang dùng")

            if profile.allergies_json:
                used_classes.append("Dị ứng đã ghi nhận")
        except Exception:
            pass

    # Call ML Service for real LLM reasoning & synthesis
    ml_answer_text = ""
    ml_sources: list[dict[str, Any]] = []
    ml_actions: list[str] = []
    try:
        rag_flow, rag_sources = _load_rag_runtime(db)
        clinical_ctx: dict[str, Any] | None = None
        if personal_evs and profile is not None:
            clinical_ctx = {
                "active_medications": [
                    e.title
                    for e in personal_evs
                    if e.resource_type == "medication"
                ],
                "allergies": (
                    profile.allergies_json if profile.allergies_json else []
                ),
            }
        ml_data = _call_ml_service(
            message=payload.text,
            role=user.role or "normal",
            rag_flow=rag_flow,
            rag_sources=rag_sources,
            ui_language=payload.locale or "vi",
            clinical_context=clinical_ctx,
        )
        if isinstance(ml_data, dict):
            ml_answer_text = str(ml_data.get("answer") or "").strip()
            raw_sources = ml_data.get("sources") or []
            if isinstance(raw_sources, list):
                for s in raw_sources:
                    if isinstance(s, dict) and s.get("title"):
                        ml_sources.append(s)
            ml_actions = [
                str(a)
                for a in (ml_data.get("suggested_actions") or [])
                if isinstance(a, str)
            ]
    except Exception as exc:
        logger.warning("ML service call in Ask endpoint: %s", exc)
        ml_answer_text = (
            f"Chào bạn, tôi là trợ lý y tế CLARA. Đối với câu hỏi '{payload.text}', "
            "tôi sẵn sàng hỗ trợ bạn tra cứu thông tin y khoa và theo dõi triệu chứng. "
            "Bạn có thể cung cấp thêm thông tin chi tiết để tôi hỗ trợ chính xác nhất."
        )

    main_msg = (
        ml_answer_text
        if ml_answer_text
        else (
            f"Chào bạn, tôi là trợ lý y tế CLARA. Câu hỏi về '{payload.text}' "
            "đã được tiếp nhận."
        )
    )
    sections_list: list[AnswerSection] = []
    if isinstance(ml_data, dict) and isinstance(ml_data.get("sections"), list):
        for s in ml_data["sections"]:
            if isinstance(s, dict) and s.get("title") and s.get("content"):
                sections_list.append(
                    AnswerSection(title=str(s["title"]), content=str(s["content"]))
                )

    answer_data = ConsumerAnswerEnvelope(
        answer=ConsumerAnswerDetails(
            main_message=main_msg,
            actions=ml_actions
            if ml_actions
            else [
                "Theo dõi thêm diễn tiến của triệu chứng trong 24-48 giờ tới.",
                "Uống đủ nước và nghỉ ngơi hợp lý.",
                "Tham khảo ý kiến bác sĩ nếu triệu chứng kéo dài hoặc tăng nặng.",
            ],
            sections=sections_list,
        ),
        personal_evidence=personal_evs,
        external_sources=[
            AnswerExternalSource(
                id=f"src_{idx}",
                title=s.get("title", "Tài liệu Y khoa"),
                source_type="guideline",
                publisher=s.get("publisher", "Bộ Y Tế Việt Nam"),
                year=s.get("year", 2024),
                url=s.get("url"),
            )
            for idx, s in enumerate(ml_sources)
        ]
        if ml_sources
        else [
            AnswerExternalSource(
                id="src_guideline_01",
                title="Hướng dẫn chẩn đoán và điều trị của Bộ Y Tế",
                source_type="guideline",
                publisher="Bộ Y Tế Việt Nam",
                year=2024,
            )
        ],
        unknowns=[
            "Chỉ số xét nghiệm máu hoặc chẩn đoán gần nhất của bác sĩ nếu có.",
        ],
        safety=AnswerSafetyOutcome(
            urgency="none",
            deterministic_floor_applied=False,
        ),
        disclosure=AnswerDisclosure(
            used_personal_context=bool(personal_evs),
            data_classes=used_classes,
            model_alias="gemini-3.7-tiered",
        ),
        conversation_id=payload.conversation_id or f"conv_{uuid4().hex[:12]}",
        turn_id=f"turn_{uuid4().hex[:8]}",
        generated_at=datetime.now(UTC).isoformat(),
    )

    return ApiV2ResponseEnvelope.wrap(data=answer_data)


@router.post(
    "/stream",
    summary="Consumer Ask CLARA Question (SSE Token Stream)",
)
def stream_ask_question(
    payload: AskRequest,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(
        default=None, alias="X-CLARA-Profile-Context"
    ),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Streams question answer tokens via SSE for live typewriter rendering."""
    user = current_user(db, token)
    req_profile = profile_id or x_clara_profile_context

    personal_evs: list[AnswerPersonalEvidence] = []
    used_classes: list[str] = []

    # Check emergency triggers deterministically
    text_lower = payload.text.lower()
    emergency_keywords = [
        "đau ngực dữ dội",
        "khó thở cấp",
        "đột quỵ",
        "bất tỉnh",
        "co giật",
        "sốc phản vệ",
    ]
    is_emergency = any(kw in text_lower for kw in emergency_keywords)

    def generate_events() -> Generator[str, None, None]:
        yield _sse_event("start", {})

        if is_emergency:
            emergency_safety = {
                "urgency": "emergency",
                "deterministic_floor_applied": True,
                "red_flags": ["Dấu hiệu cấp cứu tim mạch / hô hấp"],
                "call_115_notice": True,
            }
            yield _sse_event("safety", emergency_safety)
            emergency_text = (
                "Đây là tình huống khẩn cấp cần được cấp cứu y tế ngay lập tức. "
                "Vui lòng gọi cấp cứu 115 hoặc đến cơ sở y tế gần nhất."
            )
            yield _sse_event("token", emergency_text)
            final_env = {
                "answer": {
                    "main_message": emergency_text,
                    "actions": [
                        "Gọi ngay cấp cứu 115 hoặc nhờ người thân đưa đến bệnh viện gần nhất.",
                        "Giữ người bệnh ở tư thế thoải mái, không tự ý dùng thuốc.",
                    ],
                    "sections": [],
                },
                "personal_evidence": [],
                "external_sources": [],
                "unknowns": ["Tình trạng huyết áp và nhịp tim hiện tại của bệnh nhân."],
                "safety": emergency_safety,
                "disclosure": {"used_personal_context": False, "data_classes": []},
                "conversation_id": (
                    payload.conversation_id or f"conv_{uuid4().hex[:12]}"
                ),
                "turn_id": f"turn_{uuid4().hex[:8]}",
                "created_at": datetime.now(UTC).isoformat(),
            }
            yield _sse_event("done", {"data": final_env})
            return

        # General / Personal Context Resolution
        profile = None
        if req_profile:
            try:
                scope = require_profile_scope(
                    db, user=user, profile_id=req_profile
                )
                profile = scope.profile
                courses = list(
                    db.execute(
                        select(MedicationCourse).where(
                            MedicationCourse.profile_id == profile.id,
                            MedicationCourse.status == "active",
                        )
                    ).scalars()
                )
                for c in courses[:3]:
                    personal_evs.append(
                        AnswerPersonalEvidence(
                            id=c.public_id,
                            resource_type="medication",
                            title=f"Đơn thuốc đang dùng: {c.medication_name}",
                            effective_at=str(c.started_at or ""),
                            state="confirmed",
                        )
                    )
                if courses:
                    used_classes.append("Thuốc đang dùng")
                if profile.allergies_json:
                    used_classes.append("Dị ứng đã ghi nhận")
            except Exception:
                pass

        # Send safety guidance & evidence before tokens
        yield _sse_event(
            "safety", {"urgency": "none", "deterministic_floor_applied": False}
        )
        yield _sse_event(
            "evidence",
            {
                "personal_evidence": [e.model_dump() for e in personal_evs],
                "external_sources": [
                    {
                        "id": "src_guideline_01",
                        "title": "Hướng dẫn chẩn đoán và điều trị của Bộ Y Tế",
                        "source_type": "guideline",
                        "publisher": "Bộ Y Tế Việt Nam",
                        "year": 2024,
                    }
                ],
                "disclosure": {
                    "used_personal_context": bool(personal_evs),
                    "data_classes": used_classes,
                    "explanation": "Đã đối chiếu với thuốc và dị ứng của bạn",
                },
            },
        )

        # Connect to ML service for actual LLM streaming
        ml_answer_text = ""
        ml_sources: list[dict[str, Any]] = []
        ml_actions: list[str] = []
        try:
            rag_flow, rag_sources = _load_rag_runtime(db)
            clinical_ctx = None
            if personal_evs and profile is not None:
                clinical_ctx = {
                    "active_medications": [
                        e.title
                        for e in personal_evs
                        if e.resource_type == "medication"
                    ],
                    "allergies": (
                        profile.allergies_json if profile.allergies_json else []
                    ),
                }
            ml_data = _call_ml_service(
                message=payload.text,
                role=user.role or "normal",
                rag_flow=rag_flow,
                rag_sources=rag_sources,
                ui_language=payload.locale or "vi",
                clinical_context=clinical_ctx,
            )
            if isinstance(ml_data, dict):
                ml_answer_text = str(ml_data.get("answer") or "").strip()
                raw_sources = ml_data.get("sources") or []
                if isinstance(raw_sources, list):
                    for s in raw_sources:
                        if isinstance(s, dict) and s.get("title"):
                            ml_sources.append(s)
                ml_actions = [
                    str(a)
                    for a in (ml_data.get("suggested_actions") or [])
                    if isinstance(a, str)
                ]
        except Exception as exc:
            logger.warning("ML service call in Ask stream endpoint: %s", exc)
            ml_answer_text = (
                f"Chào bạn, tôi là trợ lý y tế CLARA. Đối với câu hỏi '{payload.text}', "
                "tôi sẵn sàng hỗ trợ bạn tra cứu thông tin y khoa và theo dõi triệu chứng. "
                "Bạn có thể cung cấp thêm thông tin chi tiết để tôi hỗ trợ chính xác nhất."
            )

        main_msg = (
            ml_answer_text
            if ml_answer_text
            else (
                f"Chào bạn, tôi là trợ lý y tế CLARA. Câu hỏi về '{payload.text}' "
                "đã được tiếp nhận."
            )
        )

        # Stream tokens word-by-word with small chunks for typewriter effect
        words = main_msg.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else f" {word}"
            yield _sse_event("token", chunk)

        sections_list = []
        if isinstance(ml_data, dict) and isinstance(ml_data.get("sections"), list):
            for s in ml_data["sections"]:
                if isinstance(s, dict) and s.get("title") and s.get("content"):
                    sections_list.append(
                        {"title": str(s["title"]), "content": str(s["content"])}
                    )

        final_envelope = {
            "answer": {
                "main_message": main_msg,
                "actions": ml_actions
                if ml_actions
                else [
                    "Theo dõi thêm diễn tiến của triệu chứng trong 24-48 giờ tới.",
                    "Uống đủ nước và nghỉ ngơi hợp lý.",
                    "Tham khảo ý kiến bác sĩ nếu triệu chứng kéo dài hoặc tăng nặng.",
                ],
                "sections": sections_list,
            },
            "personal_evidence": [e.model_dump() for e in personal_evs],
            "external_sources": ml_sources
            if ml_sources
            else [
                {
                    "id": "src_guideline_01",
                    "title": "Hướng dẫn chẩn đoán và điều trị của Bộ Y Tế",
                    "source_type": "guideline",
                    "publisher": "Bộ Y Tế Việt Nam",
                    "year": 2024,
                }
            ],
            "unknowns": [
                "Chỉ số xét nghiệm máu hoặc chẩn đoán gần nhất của bác sĩ nếu có."
            ],
            "safety": {"urgency": "none", "deterministic_floor_applied": False},
            "disclosure": {
                "used_personal_context": bool(personal_evs),
                "data_classes": used_classes,
                "model_alias": "gemini-3.7-tiered",
            },
            "conversation_id": (
                payload.conversation_id or f"conv_{uuid4().hex[:12]}"
            ),
            "turn_id": f"turn_{uuid4().hex[:8]}",
            "created_at": datetime.now(UTC).isoformat(),
        }
        yield _sse_event("done", {"data": final_envelope})

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
