"""Fail-closed, revision-grounded primitives for Ask My LifeMap.

This module deliberately performs authorization-independent intent/safety
routing before callers materialize any health context. Retrieval accepts an
already-authorized profile identifier and can never broaden that partition.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    LifeMapEpisodeEventLink,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapSourceRevocation,
)
from clara_api.lifemap.temporal_index import RetrievalDocument, TemporalRetrievalIndex

AskIntent = Literal[
    "timeline_lookup",
    "comparison",
    "visit_preparation",
    "missingness",
    "explanation",
]


def _consumer_copy(locale: str, *, vietnamese: str, english: str) -> str:
    """Select bounded consumer wording without changing the source facts.

    LifeMap's consumer language is intentionally assembled from fixed copy and
    exact revision text.  This keeps the draft useful in Vietnamese while
    ensuring that a wording layer cannot silently introduce a diagnosis,
    medication instruction, or a new truth-state.
    """

    return vietnamese if locale.startswith("vi") else english


_INTENT_HINTS: tuple[tuple[AskIntent, tuple[str, ...]], ...] = (
    ("comparison", ("compare", "change", "different", "so sanh", "thay doi")),
    ("visit_preparation", ("visit", "doctor", "appointment", "kham", "bac si")),
    ("missingness", ("missing", "unknown", "lack", "thieu", "chua co")),
    ("explanation", ("why", "explain", "meaning", "tai sao", "giai thich")),
)
_EMERGENCY_HINTS = (
    "khong tho duoc",
    "dau nguc du doi",
    "bat tinh",
    "co giat",
    "cannot breathe",
    "severe chest pain",
    "unconscious",
    "seizure",
)
_FORBIDDEN_HINTS = (
    "chan doan cho toi",
    "toi bi benh gi",
    "ke don",
    "lieu dung cho toi",
    "diagnose me",
    "what disease do i have",
    "prescribe",
    "my dosage",
)
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


@dataclass(frozen=True)
class SafetyRoute:
    intent: AskIntent
    emergency: bool = False
    blocked_reason: str = ""


@dataclass(frozen=True)
class EvidenceRow:
    evidence_id: str
    revision_id: str
    event_id: str
    event_type: str
    occurred_at: datetime
    recorded_at: datetime
    truth_state: str
    source_kind: str
    attribution: str
    text: str

    def public_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "revision_id": self.revision_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat(),
            "truth_state": self.truth_state,
            "source_kind": self.source_kind,
            "attribution": self.attribution,
            "text": self.text,
        }


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    return " ".join(
        "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        ).split()
    )


def route_ask_query(query: str) -> SafetyRoute:
    folded = _fold(query)
    if any(hint in folded for hint in _EMERGENCY_HINTS):
        return SafetyRoute(intent="timeline_lookup", emergency=True)
    if any(hint in folded for hint in _FORBIDDEN_HINTS):
        return SafetyRoute(intent="explanation", blocked_reason="legal_guard")
    for intent, hints in _INTENT_HINTS:
        if any(hint in folded for hint in hints):
            return SafetyRoute(intent=intent)
    return SafetyRoute(intent="timeline_lookup")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(_fold(value)))


def retrieve_revision_evidence(
    db: Session,
    *,
    profile_id: int,
    query: str,
    episode_id: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    event_types: frozenset[str] | None = None,
    limit: int = 20,
) -> list[EvidenceRow]:
    """Retrieve only current revisions from one pre-authorized profile."""

    statement = (
        select(LifeMapEvent, LifeMapEventRevision)
        .join(
            LifeMapEventRevision,
            (LifeMapEventRevision.event_id == LifeMapEvent.id)
            & (LifeMapEventRevision.revision_no == LifeMapEvent.current_revision_no),
        )
        .where(
            LifeMapEvent.profile_id == profile_id,
            LifeMapEventRevision.profile_id == profile_id,
            LifeMapEvent.lifecycle_status == "active",
            ~select(LifeMapSourceRevocation.id)
            .where(
                LifeMapSourceRevocation.profile_id == profile_id,
                LifeMapSourceRevocation.source_reference_id
                == LifeMapEventRevision.source_reference_id,
            )
            .exists(),
        )
    )
    if episode_id is not None:
        linked = select(LifeMapEpisodeEventLink.event_id).where(
            LifeMapEpisodeEventLink.profile_id == profile_id,
            LifeMapEpisodeEventLink.episode_id == episode_id,
            LifeMapEpisodeEventLink.status == "active",
        )
        statement = statement.where(
            or_(LifeMapEvent.episode_id == episode_id, LifeMapEvent.id.in_(linked))
        )
    if start_at is not None:
        statement = statement.where(LifeMapEvent.occurred_at >= start_at)
    if end_at is not None:
        statement = statement.where(LifeMapEvent.occurred_at <= end_at)
    if event_types is not None:
        if not event_types:
            return []
        statement = statement.where(LifeMapEvent.event_type.in_(event_types))

    rows: list[tuple[LifeMapEvent, LifeMapEventRevision]] = [
        (event, revision)
        for event, revision in db.execute(
            statement.order_by(LifeMapEvent.occurred_at.desc(), LifeMapEvent.id.desc()).limit(200)
        ).all()
    ]
    index = TemporalRetrievalIndex()
    by_document: dict[str, tuple[LifeMapEvent, LifeMapEventRevision]] = {}
    for event, revision in rows:
        document_id = f"event-revision:{revision.public_id}"
        by_document[document_id] = (event, revision)
        index.upsert(
            RetrievalDocument(
                document_id=document_id,
                profile_partition=str(profile_id),
                revision_id=revision.public_id,
                source_type=event.source_kind,
                effective_start=event.occurred_at,
                effective_end=None,
                recorded_at=revision.recorded_at,
                episode_ids=(
                    frozenset(
                        {
                            str(episode_id)
                            if episode_id is not None
                            else str(event.episode_id)
                        }
                    )
                    if episode_id is not None or event.episode_id is not None
                    else frozenset()
                ),
                truth_state=revision.truth_state,
                data_class="lifemap",
                language="vi",
                terms=frozenset(_tokens(f"{event.event_type} {revision.display_summary}")),
                embedding=None,
                graph_entities=frozenset({event.event_type}),
            )
        )
    hits = index.search(
        profile_partition=str(profile_id),
        allowed_data_classes=frozenset({"lifemap"}),
        query_terms=frozenset(_tokens(query)),
        episode_id=str(episode_id) if episode_id is not None else None,
        start_at=start_at,
        end_at=end_at,
        graph_entities=frozenset(_tokens(query)),
        limit=limit,
    )
    selected = [by_document[hit.document.document_id] for hit in hits]
    return [
        EvidenceRow(
            evidence_id=f"ev:{revision.public_id}",
            revision_id=revision.public_id,
            event_id=event.public_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at.astimezone(UTC),
            recorded_at=revision.recorded_at.astimezone(UTC),
            truth_state=revision.truth_state,
            source_kind=event.source_kind,
            attribution={
                "reported": "user_report",
                "device": "device_measurement",
                "document": "source_document",
                "derived": "clara_derived",
            }.get(event.source_kind, "source_record"),
            text=revision.display_summary.strip() or f"{event.event_type} event",
        )
        for event, revision in selected
    ]


def deterministic_answer(
    *,
    intent: AskIntent,
    evidence: list[EvidenceRow],
    locale: str,
) -> dict[str, object]:
    ordered = sorted(evidence, key=lambda row: (row.occurred_at, row.revision_id))
    disputed = [row.evidence_id for row in ordered if row.truth_state == "disputed"]
    conflicting = [row.evidence_id for row in ordered if row.truth_state == "conflicting"]
    stale = [row.evidence_id for row in ordered if row.truth_state == "stale"]
    if not evidence:
        return {
            "status": "abstained",
            "answer": (
                "Tôi chưa tìm thấy dữ liệu LifeMap được xác nhận trong phạm vi này."
                if locale.startswith("vi")
                else "I could not find confirmed LifeMap data in this scope."
            ),
            "claims": [],
            "unknown": ["no_matching_evidence"],
            "conflicting": [],
            "stale": [],
            "disputed": [],
            "abstention_code": "insufficient_information",
        }
    claims = [
        {
            "claim_id": f"claim-{index + 1}",
            "text": row.text,
            "citation_ids": [row.evidence_id],
            "truth_state": row.truth_state,
            "attribution": row.attribution,
        }
        for index, row in enumerate(ordered[:8])
    ]
    prefix = (
        f"LifeMap có {len(claims)} mục liên quan theo thứ tự thời gian."
        if locale.startswith("vi")
        else f"LifeMap contains {len(claims)} relevant items in temporal order."
    )
    return {
        "status": "grounded",
        "answer": prefix,
        "claims": claims,
        "unknown": [],
        "conflicting": conflicting,
        "stale": stale,
        "disputed": disputed,
        "abstention_code": "",
        "intent": intent,
    }


def verify_grounded_answer(
    answer: dict[str, object],
    evidence: list[EvidenceRow],
    *,
    fides_verdict: str | None = None,
) -> dict[str, object]:
    available = {row.evidence_id: row for row in evidence}
    temporal = sorted(evidence, key=lambda row: (row.occurred_at, row.revision_id))
    positions = {row.evidence_id: index for index, row in enumerate(temporal)}
    claims = answer.get("claims")
    if not isinstance(claims, list):
        raise ValueError("claims_schema_invalid")
    last_position = -1
    generated_medication_claim = False
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("text"), str):
            raise ValueError("claim_schema_invalid")
        citations = claim.get("citation_ids")
        if not isinstance(citations, list) or not citations:
            raise ValueError("citation_required")
        if any(citation not in available for citation in citations):
            raise ValueError("citation_outside_evidence_table")
        claim_text = " ".join(str(claim["text"]).casefold().split())
        source_texts = [
            " ".join(available[str(citation)].text.casefold().split())
            for citation in citations
        ]
        if not any(claim_text == source or claim_text in source for source in source_texts):
            raise ValueError("claim_not_entailed_by_cited_revision")
        current_position = min(positions[str(citation)] for citation in citations)
        if current_position < last_position:
            raise ValueError("claim_temporal_order_invalid")
        last_position = current_position
        folded = _fold(claim_text)
        if any(hint in folded for hint in _FORBIDDEN_HINTS):
            raise ValueError("released_claim_violates_legal_guard")
        medication_markers = (
            " mg",
            " mcg",
            " ml",
            "dose",
            "dosage",
            "lieu",
            "tablet",
            "vien",
        )
        exact_source_copy = any(claim_text == source for source in source_texts)
        if any(marker in f" {folded}" for marker in medication_markers) and not exact_source_copy:
            generated_medication_claim = True
    disputed = answer.get("disputed")
    conflicting = answer.get("conflicting")
    if not isinstance(disputed, list) or not isinstance(conflicting, list):
        raise ValueError("ambiguity_fields_required")
    expected_disputed = {
        row.evidence_id for row in evidence if row.truth_state == "disputed"
    }
    expected_conflicting = {
        row.evidence_id for row in evidence if row.truth_state == "conflicting"
    }
    if not expected_disputed <= set(disputed) or not expected_conflicting <= set(conflicting):
        raise ValueError("contradiction_or_dispute_not_surfaced")
    if generated_medication_claim and fides_verdict != "pass":
        raise ValueError("fides_required_for_generated_medication_claim")
    return {
        "citation_existence": "pass",
        "entailment": "pass",
        "profile_scope": "pass",
        "temporal_order": "pass",
        "contradiction": "pass",
        "legal_guard": "pass",
        "fides": (
            "pass"
            if generated_medication_claim
            else "not_applicable_exact_revision_reporting"
        ),
        "unsupported_claims": 0,
    }


def consumer_summary(
    evidence: list[EvidenceRow], *, locale: str
) -> dict[str, object]:
    """Return a plain-language, revision-bound summary for a consumer.

    This is presentation-only output: each factual item is an exact revision
    copy with an evidence id, and the non-factual guidance is fixed safety
    wording.  It must never be persisted as a LifeMap event or treated as a
    clinical recommendation.
    """

    ordered = sorted(evidence, key=lambda row: (row.occurred_at, row.revision_id))
    uncertain = [
        row.evidence_id
        for row in ordered
        if row.truth_state in {"disputed", "conflicting", "stale"}
    ]
    if not ordered:
        return {
            "status": "abstained",
            "important_now": _consumer_copy(
                locale,
                vietnamese="Chưa có ghi nhận phù hợp trong phạm vi bạn đã chọn.",
                english="There are no matching records in the selected scope.",
            ),
            "based_on": [],
            "uncertainty": ["no_matching_evidence"],
            "next_step": _consumer_copy(
                locale,
                vietnamese=(
                    "Bạn có thể bổ sung thông tin hoặc kiểm tra lại phạm vi "
                    "thời gian."
                ),
                english="You can add information or review the selected time range.",
            ),
            "urgent_help": _consumer_copy(
                locale,
                vietnamese=(
                    "Nếu có dấu hiệu khẩn cấp, hãy gọi cấp cứu địa phương "
                    "hoặc đến khoa cấp cứu gần nhất."
                ),
                english=(
                    "For emergency symptoms, call local emergency services "
                    "or go to the nearest emergency department."
                ),
            ),
            "input_revision_ids": [],
            "draft_only": True,
        }
    return {
        "status": "ready",
        "important_now": _consumer_copy(
            locale,
            vietnamese=f"Có {len(ordered)} ghi nhận trong phạm vi bạn đã chọn.",
            english=f"There are {len(ordered)} records in the selected scope.",
        ),
        "based_on": [
            {
                "text": row.text,
                "citation_ids": [row.evidence_id],
                "occurred_at": row.occurred_at.isoformat(),
                "truth_state": row.truth_state,
            }
            for row in ordered[:8]
        ],
        "uncertainty": uncertain,
        "next_step": _consumer_copy(
            locale,
            vietnamese=(
                "Hãy kiểm tra lại các ghi nhận trước khi dùng chúng để trao "
                "đổi với nhân viên y tế."
            ),
            english=(
                "Review these records before using them in a conversation "
                "with a health professional."
            ),
        ),
        "urgent_help": _consumer_copy(
            locale,
            vietnamese=(
                "Nếu có dấu hiệu khẩn cấp, hãy gọi cấp cứu địa phương hoặc "
                "đến khoa cấp cứu gần nhất."
            ),
            english=(
                "For emergency symptoms, call local emergency services or "
                "go to the nearest emergency department."
            ),
        ),
        "input_revision_ids": [row.revision_id for row in ordered],
        "draft_only": True,
    }


def visit_preparation_draft(
    evidence: list[EvidenceRow], *, locale: str
) -> dict[str, object]:
    """Create a consumer-editable visit-preparation draft from exact facts.

    The questions deliberately avoid interpretation.  They are prompts a
    person may edit before a visit, not clinical instructions and not a
    mutation of the LifeMap truth state.
    """

    summary = consumer_summary(evidence, locale=locale)
    source_rows = summary["based_on"]
    if not isinstance(source_rows, list) or not source_rows:
        return {
            "status": "abstained",
            "title": _consumer_copy(
                locale,
                vietnamese="Bản nháp chuẩn bị buổi khám",
                english="Visit preparation draft",
            ),
            "plain_language_summary": summary,
            "questions_to_consider": [],
            "source_revision_ids": [],
            "draft_only": True,
            "requires_user_review": True,
        }
    questions: list[dict[str, object]] = []
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        text = row.get("text")
        citations = row.get("citation_ids")
        if not isinstance(text, str) or not isinstance(citations, list):
            continue
        questions.append(
            {
                "text": _consumer_copy(
                    locale,
                    vietnamese=(
                        f"Tôi muốn trao đổi về ghi nhận này: “{text}”. "
                        "Điều gì là quan trọng để tôi theo dõi hoặc hỏi thêm?"
                    ),
                    english=(
                        f"I would like to discuss this record: “{text}”. "
                        "What is important for me to monitor or ask about?"
                    ),
                ),
                "citation_ids": citations,
            }
        )
    return {
        "status": "ready",
        "title": _consumer_copy(
            locale,
            vietnamese="Bản nháp chuẩn bị buổi khám",
            english="Visit preparation draft",
        ),
        "plain_language_summary": summary,
        "questions_to_consider": questions,
        "source_revision_ids": summary["input_revision_ids"],
        "draft_only": True,
        "requires_user_review": True,
    }


def hierarchical_summary(
    evidence: list[EvidenceRow],
    *,
    level: Literal["event", "day", "episode", "week", "visit"],
    locale: str,
) -> dict[str, object]:
    """Build a deterministic structured summary from exact child claims."""

    ordered = sorted(evidence, key=lambda row: (row.occurred_at, row.revision_id))
    groups: dict[str, list[EvidenceRow]] = {}
    for row in ordered:
        if level == "event":
            key = row.evidence_id
        elif level == "day":
            key = row.occurred_at.date().isoformat()
        elif level == "week":
            year, week, _ = row.occurred_at.isocalendar()
            key = f"{year}-W{week:02d}"
        else:
            key = level
        groups.setdefault(key, []).append(row)
    children = [
        {
            "group": key,
            "claims": [
                {
                    "text": row.text,
                    "citation_ids": [row.evidence_id],
                    "truth_state": row.truth_state,
                    "attribution": row.attribution,
                    "occurred_at": row.occurred_at.isoformat(),
                }
                for row in rows
            ],
        }
        for key, rows in groups.items()
    ]
    digest = hashlib.sha256(
        json.dumps(
            {
                "level": level,
                "revision_ids": [row.revision_id for row in ordered],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return {
        "id": digest,
        "level": level,
        "status": "ready" if ordered else "abstained",
        "summary": (
            f"Tóm tắt gồm {len(ordered)} bản ghi có dẫn nguồn."
            if locale.startswith("vi")
            else f"Summary of {len(ordered)} source-cited records."
        ),
        "consumer_summary": consumer_summary(ordered, locale=locale),
        "children": children,
        "input_revision_ids": [row.revision_id for row in ordered],
        "conflicting": [
            row.evidence_id for row in ordered if row.truth_state == "conflicting"
        ],
        "disputed": [
            row.evidence_id for row in ordered if row.truth_state == "disputed"
        ],
        "fallback_used": True,
        "rule_version": "lifemap-hierarchical-summary-v1",
    }
