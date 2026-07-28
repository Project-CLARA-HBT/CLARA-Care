"""LifeMap next-best-question engine (Phase 2, P2-WP5).

Objective (per spec §6.9): ask the *smallest* number of questions that could
materially change safety or the next step — ideally one, or none.

Design stance
-------------
This engine is **deterministic-core, LLM-enriched**:

* The deterministic core owns *what* to ask and *whether* asking is safe. It
  derives candidate questions from typed missing critical fields on the episode,
  scores each by its safety/action impact, removes anything already answered or
  previously dismissed, and returns the single highest-value question — or none.
  This path always works and is fully reproducible, so the safety invariants hold
  even when the model is unavailable.
* An optional LLM pass (flag-gated, default off) may only *rephrase* the chosen
  question into warmer consumer language. It can never introduce a new question,
  change the field being asked, or override a "ask nothing" decision. The
  rephrased text is re-validated before use; on any failure the deterministic
  wording stands. This is the "LLM first if possible" enrichment without letting
  the model weaken a guardrail.

Hard rules (spec §6.9)
----------------------
* never delay an emergency response to ask a question — an active emergency
  disposition on the episode short-circuits to "ask nothing";
* do not repeatedly ask a dismissed question without a new reason;
* do not ask sensitive questions without explaining why (every question carries
  a ``why`` rationale);
* generated questions pass consumer-language validation before they are surfaced.

The engine reads only confirmed/reported facts the user already owns and never
persists anything, so it is inert until called and has no schema footprint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    LifeMapCareTask,
    LifeMapDecisionLedger,
    LifeMapEpisode,
    LifeMapEvent,
    LifeMapQuestionDefinition,
    LifeMapQuestionInteraction,
)

POLICY_VERSION = "next-best-question-v1"

# A critical field is a typed piece of information whose absence could change the
# safety disposition or the next step for a class of episode. Each carries the
# question text, a plain-language rationale, and an impact weight (higher ⇒ more
# likely to change safety/action). Questions are consumer-first Vietnamese.
CriticalField = tuple[str, str, str, int]

# event_type that satisfies a field → the field is considered answered.
_SYMPTOM_FIELDS: list[CriticalField] = [
    (
        "symptom_onset",
        "Triệu chứng bắt đầu từ khi nào?",
        "Thời điểm khởi phát giúp phân biệt việc cần theo dõi thêm hay nên đi khám sớm.",
        3,
    ),
    (
        "symptom_severity",
        "Mức độ khó chịu hiện tại của bạn thế nào (nhẹ, vừa, nặng)?",
        "Mức độ nặng là yếu tố an toàn quan trọng nhất để biết có cần hỗ trợ khẩn cấp không.",
        4,
    ),
    (
        "symptom_trend",
        "Triệu chứng đang nặng hơn, nhẹ đi hay không đổi?",
        "Xu hướng thay đổi cho biết tình trạng có đang xấu đi hay không.",
        3,
    ),
]

_MEDICATION_FIELDS: list[CriticalField] = [
    (
        "medication_adherence",
        "Bạn có đang dùng thuốc đúng lịch không?",
        "Việc dùng thuốc đều đặn ảnh hưởng trực tiếp đến hiệu quả và an toàn.",
        3,
    ),
    (
        "medication_side_effect",
        "Bạn có gặp tác dụng không mong muốn nào sau khi dùng thuốc không?",
        "Tác dụng phụ mới có thể là tín hiệu an toàn cần được xem xét.",
        4,
    ),
]

# Coarse episode classification from the goal/title text so we only offer
# questions relevant to what the user is actually tracking.
_SYMPTOM_HINTS = ("triệu chứng", "đau", "ho", "sốt", "mệt", "symptom", "pain", "theo dõi")
_MEDICATION_HINTS = ("thuốc", "liều", "uống", "medication", "dose", "medicine")


@dataclass
class QuestionCandidate:
    question_id: str | None
    field_key: str
    text: str
    why: str
    impact: int


@dataclass
class NextBestQuestion:
    """The single highest-value question, or an explicit 'ask nothing' result."""

    ask: bool
    policy_version: str = POLICY_VERSION
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    field_key: str | None = None
    question_id: str | None = None
    question: str | None = None
    why: str | None = None
    reason_code: str = ""
    candidates_considered: int = 0

    def as_dict(self) -> dict:
        return {
            "ask": self.ask,
            "policy_version": self.policy_version,
            "generated_at": self.generated_at,
            "field_key": self.field_key,
            "question_id": self.question_id,
            "question": self.question,
            "why": self.why,
            "reason_code": self.reason_code,
            "candidates_considered": self.candidates_considered,
        }


def _classify(episode: LifeMapEpisode) -> list[CriticalField]:
    text = f"{episode.title} {episode.goal or ''}".lower()
    fields: list[CriticalField] = []
    if any(hint in text for hint in _SYMPTOM_HINTS):
        fields.extend(_SYMPTOM_FIELDS)
    if any(hint in text for hint in _MEDICATION_HINTS):
        fields.extend(_MEDICATION_FIELDS)
    # An unclassified episode still gets the most universal safety question.
    if not fields:
        fields.append(_SYMPTOM_FIELDS[1])  # severity
    return fields


def _episode_class(episode: LifeMapEpisode) -> str:
    text = f"{episode.title} {episode.goal or ''}".lower()
    if any(hint in text for hint in _MEDICATION_HINTS):
        return "medication"
    if any(hint in text for hint in _SYMPTOM_HINTS):
        return "symptom"
    return "general"


def _approved_catalogue(
    db: Session, episode: LifeMapEpisode, *, locale: str
) -> list[QuestionCandidate]:
    episode_class = _episode_class(episode)
    rows = list(
        db.execute(
            select(LifeMapQuestionDefinition)
            .where(
                LifeMapQuestionDefinition.status == "approved",
                LifeMapQuestionDefinition.approved_at.is_not(None),
                LifeMapQuestionDefinition.locale == locale,
                LifeMapQuestionDefinition.episode_class.in_(
                    (episode_class, "general")
                ),
            )
            .order_by(
                LifeMapQuestionDefinition.impact_weight.desc(),
                LifeMapQuestionDefinition.field_key,
            )
        ).scalars()
    )
    return [
        QuestionCandidate(
            question_id=row.public_id,
            field_key=row.field_key,
            text=row.question_text,
            why=row.rationale_text,
            impact=row.impact_weight,
        )
        for row in rows
    ]


def _answered_field_keys(db: Session, profile_id: int, episode_id: int) -> set[str]:
    """Field keys already supplied by a confirmed or explicitly reported fact."""

    rows = db.execute(
        select(LifeMapEvent.event_type, LifeMapEvent.payload_json).where(
            LifeMapEvent.profile_id == profile_id,
            LifeMapEvent.episode_id == episode_id,
            LifeMapEvent.truth_state.in_(("confirmed", "user_reported", "reported")),
        )
    ).all()
    answered: set[str] = set()
    for event_type, payload in rows:
        answered.add(event_type)
        if isinstance(payload, dict):
            for key in payload:
                answered.add(str(key))
    return answered


def _dismissed_field_keys(db: Session, profile_id: int, episode_id: int) -> set[str]:
    """Questions the user dismissed, so we do not re-ask without new reason.

    Recorded as decision-ledger rows of type ``next_best_question_dismissed`` with
    the field key in ``inputs_json['field_key']``.
    """

    rows = db.execute(
        select(LifeMapDecisionLedger.inputs_json).where(
            LifeMapDecisionLedger.profile_id == profile_id,
            LifeMapDecisionLedger.episode_id == episode_id,
            LifeMapDecisionLedger.decision_type == "next_best_question_dismissed",
        )
    ).scalars()
    dismissed: set[str] = set()
    for inputs in rows:
        if isinstance(inputs, dict) and (key := inputs.get("field_key")):
            dismissed.add(str(key))
    now = datetime.now(UTC)
    governed = db.execute(
        select(LifeMapQuestionDefinition.field_key)
        .join(
            LifeMapQuestionInteraction,
            LifeMapQuestionInteraction.question_definition_id
            == LifeMapQuestionDefinition.id,
        )
        .where(
            LifeMapQuestionInteraction.profile_id == profile_id,
            LifeMapQuestionInteraction.episode_id == episode_id,
            or_(
                LifeMapQuestionInteraction.action == "do_not_ask",
                (
                    (LifeMapQuestionInteraction.action == "dismissed")
                    & (LifeMapQuestionInteraction.cooldown_until.is_not(None))
                    & (LifeMapQuestionInteraction.cooldown_until > now)
                ),
            ),
        )
    ).scalars()
    dismissed.update(str(key) for key in governed)
    return dismissed


def _burden_budget_exhausted(
    db: Session, profile_id: int, episode_id: int, now: datetime
) -> bool:
    recent = db.execute(
        select(LifeMapQuestionInteraction.id).where(
            LifeMapQuestionInteraction.profile_id == profile_id,
            LifeMapQuestionInteraction.episode_id == episode_id,
            LifeMapQuestionInteraction.action.in_(
                ("presented", "answered_draft", "confirmed", "dismissed")
            ),
            LifeMapQuestionInteraction.created_at >= now - timedelta(hours=24),
        )
    ).first()
    return recent is not None


def _emergency_active(db: Session, profile_id: int, episode_id: int) -> bool:
    """True if an active emergency disposition exists on the episode.

    Hard rule: never delay an emergency response to ask a question.
    """

    row = db.execute(
        select(LifeMapDecisionLedger.id).where(
            LifeMapDecisionLedger.profile_id == profile_id,
            LifeMapDecisionLedger.episode_id == episode_id,
            LifeMapDecisionLedger.disposition == "emergency",
        )
    ).first()
    return row is not None


def _has_open_pending_task(db: Session, profile_id: int, episode_id: int) -> bool:
    """If the user already has an accepted next step, asking is lower value."""

    row = db.execute(
        select(LifeMapCareTask.id).where(
            LifeMapCareTask.profile_id == profile_id,
            LifeMapCareTask.episode_id == episode_id,
            LifeMapCareTask.status == "accepted",
        )
    ).first()
    return row is not None


def compute_next_best_question(
    db: Session,
    *,
    profile_id: int,
    episode: LifeMapEpisode,
    locale: str = "vi",
    governed_only: bool = False,
) -> NextBestQuestion:
    """Deterministic core: return the single highest-value question, or none."""

    # Hard rule 1: an active emergency short-circuits to "ask nothing".
    if _emergency_active(db, profile_id, episode.id):
        return NextBestQuestion(ask=False, reason_code="emergency_active")

    now = datetime.now(UTC)
    if _burden_budget_exhausted(db, profile_id, episode.id, now):
        return NextBestQuestion(ask=False, reason_code="burden_budget_exhausted")

    governed = (
        _approved_catalogue(db, episode, locale=locale)
        if governed_only
        else []
    )
    if governed_only and not governed:
        return NextBestQuestion(ask=False, reason_code="catalogue_not_approved")
    answered = _answered_field_keys(db, profile_id, episode.id)
    dismissed = _dismissed_field_keys(db, profile_id, episode.id)

    candidates = governed or [
        QuestionCandidate(
            question_id=None,
            field_key=key,
            text=text,
            why=why,
            impact=impact,
        )
        for (key, text, why, impact) in _classify(episode)
    ]
    candidates = [
        item
        for item in candidates
        if item.field_key not in answered and item.field_key not in dismissed
    ]
    considered = len(candidates)

    if not candidates:
        return NextBestQuestion(
            ask=False,
            reason_code="no_material_question",
            candidates_considered=considered,
        )

    # Rank by impact (desc), then stable by field key for reproducibility.
    candidates.sort(key=lambda c: (-c.impact, c.field_key))
    best = candidates[0]

    # If the user already committed to a next step and the top question is not a
    # high-impact safety question, defer — one next step beats another question.
    if best.impact < 4 and _has_open_pending_task(db, profile_id, episode.id):
        return NextBestQuestion(
            ask=False,
            reason_code="next_step_already_accepted",
            candidates_considered=considered,
        )

    return NextBestQuestion(
        ask=True,
        question_id=best.question_id,
        field_key=best.field_key,
        question=best.text,
        why=best.why,
        reason_code="highest_value_question",
        candidates_considered=considered,
    )
