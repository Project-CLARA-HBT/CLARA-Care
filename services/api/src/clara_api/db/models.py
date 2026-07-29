from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    event as sa_event,
)
from sqlalchemy import (
    inspect as sa_inspect,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clara_api.db.base import Base


def _public_id() -> str:
    """Return a non-enumerable API identifier without database-specific defaults."""

    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User")


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), index=True)
    user_input: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScribeSession(Base):
    __tablename__ = "scribe_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    # A visit-bound session is permitted to process PHI only while the linked,
    # affirmative VisitConsent remains active. Legacy standalone Scribe sessions
    # remain unbound rather than being silently assigned to a visit.
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    visit_consent_id: Mapped[int | None] = mapped_column(
        ForeignKey("visit_consents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    soap_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    insights_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    # Enterprise scribe additive columns (migration 20260410_0009, Req 5/8).
    encounter_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    asr_meta_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    consent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Wave-2 additive column (migration 20260411_0010, Req 15) — non-PII
    # quality / documentation-efficiency metrics; written only when the
    # RAG_SCRIBE_QUALITY_METRICS_ENABLED flag is on.
    metrics_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    last_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship("User")


class ScribeNoteVersion(Base):
    """Versioned clinical note for a scribe session (Requirement 8.2/8.5).

    A signed version is immutable; any later edit inserts a new row with an
    incremented ``version_no``. Append-only by convention (no UPDATE of signed rows).
    """

    __tablename__ = "scribe_note_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scribe_sessions.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    template_id: Mapped[str] = mapped_column(String(64), default="soap")
    sections_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    coding_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    # Wave-2 additive metadata columns (migration 20260411_0010). Each is
    # written only by its corresponding flag-gated pass and never mutates the
    # note's clinical text (Req 12.6, 13.5, 15, 16).
    grounding_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    extraction_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    wer_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    quality_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    signed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScribeConsent(Base):
    """Immutable patient-consent record for a scribe session (Requirement 4)."""

    __tablename__ = "scribe_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scribe_sessions.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[str] = mapped_column(String(32), default="verbal")
    scope: Mapped[str] = mapped_column(String(64), default="encounter")
    captured_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScribeAudit(Base):
    """Append-only audit trail for a scribe session (Requirement 8.3/8.4)."""

    __tablename__ = "scribe_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scribe_sessions.id", ondelete="CASCADE"), index=True
    )
    actor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    from_status: Mapped[str] = mapped_column(String(32), default="")
    to_status: Mapped[str] = mapped_column(String(32), default="")
    detail_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScribeAddendum(Base):
    """Append-only, time-stamped addendum attached to a signed note version.

    Distinct from amend (Requirement 18): attaching an addendum leaves the
    signed ``ScribeNoteVersion`` byte-for-byte unchanged and creates no new
    note version. Rows are append-only by convention.
    """

    __tablename__ = "scribe_addenda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scribe_sessions.id", ondelete="CASCADE"), index=True
    )
    note_version_id: Mapped[int] = mapped_column(
        ForeignKey("scribe_note_versions.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CouncilCase(Base):
    __tablename__ = "council_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), default="New Case")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    intake_mode: Mapped[str] = mapped_column(String(32), default="transcript")
    transcript: Mapped[str] = mapped_column(Text, default="")
    intake_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    request_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    raw_result_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    # Additive oversight-state column (migration 20260421_0017, clara-council-upgrade
    # Req 3). Nullable; defaults to ``none``. A ``pause`` oversight action flips
    # this to ``paused`` so the final recommendation renders as "not yet confirmed".
    # Written only when COUNCIL_OVERSIGHT_ENABLED is on; null/``none`` preserves
    # today's behavior.
    oversight_state: Mapped[str | None] = mapped_column(String(16), nullable=True, default="none")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship("User")


class CouncilRun(Base):
    """Append-only snapshot of a single ``run_council`` execution (Req 2).

    A new row is appended on each run when ``COUNCIL_RUN_HISTORY_ENABLED`` is on;
    rows are immutable by convention (no UPDATE / DELETE). The owning case's
    ``result_json`` / ``last_run_at`` continue to mirror the newest run so
    existing consumers are unaffected. Clinical payloads live within the same
    owner-isolated trust boundary as ``CouncilCase`` and are never telemetered
    (Req 2.7).
    """

    __tablename__ = "council_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("council_cases.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    request_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), default="")
    emergency_triggered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["CouncilCase"] = relationship("CouncilCase")
    user: Mapped[User] = relationship("User")


class CouncilOversightAction(Base):
    """Append-only human-oversight governance action on a run (Req 3, 4).

    Records ``handoff`` (invite an attending specialty), ``override`` (a human
    decision that differs from the AI; the AI recommendation is retained), or
    ``pause`` (suspend automated conclusion pending review). Rows are immutable
    by convention. ``reason`` and the override fields are owner-isolated case
    data and are never emitted to telemetry or analytics (Req 3.7).
    """

    __tablename__ = "council_oversight_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("council_cases.id", ondelete="CASCADE"),
        index=True,
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("council_runs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    actor_ref: Mapped[str] = mapped_column(String(64), default="")
    kind: Mapped[str] = mapped_column(String(16), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    handoff_specialty: Mapped[str | None] = mapped_column(String(64), nullable=True)
    override_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["CouncilCase"] = relationship("CouncilCase")
    run: Mapped["CouncilRun | None"] = relationship("CouncilRun")


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    query_text: Mapped[str] = mapped_column(Text, default="")
    request_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    progress_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    run_manifest_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    evidence_snapshot_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error_text: Mapped[str] = mapped_column(Text, default="")
    worker_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    lease_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    recovery_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship("User")


class ResearchUploadedFile(Base):
    """Durable, owner-isolated uploaded research file (R2)."""

    __tablename__ = "research_uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer, default=0)
    storage_kind: Mapped[str] = mapped_column(String(16), default="db")
    storage_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    preview: Mapped[str] = mapped_column(Text, default="")
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    ocr_bridge_kind: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship("User")


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_type: Mapped[str] = mapped_column(String(32), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User")


class UserConsent(Base):
    __tablename__ = "user_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(64), default="medical_disclaimer", index=True)
    consent_version: Mapped[str] = mapped_column(String(32), index=True)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    # Appended (never mutated in place) when a typed consent is withdrawn; the
    # ledger stays append-only. Null ⇒ the grant is still active.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User")


class MedicineCabinet(Base):
    __tablename__ = "medicine_cabinets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        unique=True,
    )
    label: Mapped[str] = mapped_column(String(255), default="Tủ thuốc cá nhân")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship("User")


class MedicineItem(Base):
    __tablename__ = "medicine_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cabinet_id: Mapped[int] = mapped_column(
        ForeignKey("medicine_cabinets.id", ondelete="CASCADE"),
        index=True,
    )
    drug_name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    dosage: Mapped[str] = mapped_column(String(255), default="")
    dosage_form: Mapped[str] = mapped_column(String(255), default="")
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(32), default="manual", index=True)
    rx_cui: Mapped[str] = mapped_column(String(64), default="")
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    # Structured first-class cabinet fields (migration 20260419_0015, Req 1.2,
    # 10.3). Additive + nullable: when SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED
    # is on these replace the legacy ``[meta]`` note encoding for brand /
    # manufacturer; when off they stay null and behavior is unchanged. The
    # ``expiry_reminder_json`` column persists per-item expiry reminder state
    # behind SELFMED_EXPIRY_REMINDERS_ENABLED.
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expiry_reminder_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    cabinet: Mapped[MedicineCabinet] = relationship("MedicineCabinet")


class VnDrugMapping(Base):
    __tablename__ = "vn_drug_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_brand: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    active_ingredients: Mapped[str] = mapped_column(Text, default="")
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    rx_cui: Mapped[str] = mapped_column(String(64), default="")
    mapping_source: Mapped[str] = mapped_column(String(32), default="manual", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    created_by: Mapped[User | None] = relationship("User")
    aliases: Mapped[list["VnDrugMappingAlias"]] = relationship(
        "VnDrugMappingAlias",
        cascade="all, delete-orphan",
        back_populates="mapping",
    )
    audit_events: Mapped[list["VnDrugMappingAudit"]] = relationship(
        "VnDrugMappingAudit",
        cascade="all, delete-orphan",
        back_populates="mapping",
    )


class VnDrugMappingAlias(Base):
    __tablename__ = "vn_drug_mapping_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mapping_id: Mapped[int] = mapped_column(
        ForeignKey("vn_drug_mappings.id", ondelete="CASCADE"),
        index=True,
    )
    alias_name: Mapped[str] = mapped_column(String(255))
    normalized_alias: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mapping: Mapped[VnDrugMapping] = relationship("VnDrugMapping", back_populates="aliases")


class VnDrugMappingAudit(Base):
    __tablename__ = "vn_drug_mapping_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mapping_id: Mapped[int] = mapped_column(
        ForeignKey("vn_drug_mappings.id", ondelete="CASCADE"),
        index=True,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    before_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mapping: Mapped[VnDrugMapping] = relationship("VnDrugMapping", back_populates="audit_events")
    actor: Mapped[User | None] = relationship("User")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    value_text: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship("User")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        index=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    preview: Mapped[str] = mapped_column(Text, default="")
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    source: Mapped[KnowledgeSource] = relationship("KnowledgeSource")
    owner: Mapped[User] = relationship("User")


class FederatedSourceRecord(Base):
    __tablename__ = "federated_source_records"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "record_id",
            name="uq_federated_source_records_owner_record",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    record_id: Mapped[str] = mapped_column(String(128), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    external_id: Mapped[str] = mapped_column(String(255), default="")
    query: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[str] = mapped_column(String(64), default="")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        server_default=func.now(),
    )
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship("User")


class WorkspaceFolder(Base):
    __tablename__ = "workspace_folders"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_workspace_folders_user_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(32), default="cyan")
    icon: Mapped[str] = mapped_column(String(64), default="folder")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship("User")


class WorkspaceChannel(Base):
    __tablename__ = "workspace_channels"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_workspace_channels_user_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    visibility: Mapped[str] = mapped_column(String(24), default="private", index=True)
    color: Mapped[str] = mapped_column(String(32), default="violet")
    icon: Mapped[str] = mapped_column(String(64), default="hash")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship("User")


class WorkspaceConversationMeta(Base):
    __tablename__ = "workspace_conversation_meta"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_workspace_conversation_meta_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
    )
    folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_folders.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_channels.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship("User")
    session: Mapped[SessionModel] = relationship("SessionModel")
    folder: Mapped[WorkspaceFolder | None] = relationship("WorkspaceFolder")
    channel: Mapped[WorkspaceChannel | None] = relationship("WorkspaceChannel")


class WorkspaceConversationShare(Base):
    __tablename__ = "workspace_conversation_shares"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_workspace_conversation_shares_session"),
        UniqueConstraint("research_job_id", name="uq_workspace_conversation_shares_research_job"),
        UniqueConstraint("share_token", name="uq_workspace_conversation_shares_token"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    # A share targets either a workspace conversation (``session_id``) or a
    # research tier2 job (``research_job_id``); exactly one is set. Both are
    # nullable so the same share mechanism can back research report shares
    # (R16.3) without requiring an associated chat session.
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    research_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    share_token: Mapped[str] = mapped_column(String(160), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship("User")
    session: Mapped[SessionModel | None] = relationship("SessionModel")
    research_job: Mapped[ResearchJob | None] = relationship("ResearchJob")


class WorkspaceNote(Base):
    __tablename__ = "workspace_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), index=True)
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[list[str] | dict | None] = mapped_column(JSON, nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship("User")
    conversation: Mapped[SessionModel | None] = relationship("SessionModel")


class PhrProfile(Base):
    __tablename__ = "phr_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        unique=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str] = mapped_column(String(32), default="")
    blood_type: Mapped[str] = mapped_column(String(16), default="")
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    phone: Mapped[str] = mapped_column(String(64), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    emergency_contact_name: Mapped[str] = mapped_column(String(255), default="")
    emergency_contact_phone: Mapped[str] = mapped_column(String(64), default="")
    insurance_id: Mapped[str] = mapped_column(String(128), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    allergies_json: Mapped[list[dict] | dict | None] = mapped_column(JSON, nullable=True)
    conditions_json: Mapped[list[dict] | dict | None] = mapped_column(JSON, nullable=True)
    medications_json: Mapped[list[dict] | dict | None] = mapped_column(JSON, nullable=True)
    # New (additive, nullable) — owner-controlled emergency-card field inclusion.
    emergency_card_prefs_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # First-run setup is an explicit user decision.  A newly provisioned
    # profile starts pending; existing accounts are classified by migration so
    # they are not unexpectedly trapped in onboarding.
    onboarding_status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", index=True
    )
    onboarding_version: Mapped[str] = mapped_column(
        String(32), default="", server_default=""
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # New — monotonic per-profile version counter, bumped on each committed change.
    current_version_no: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(24), default="active", server_default="active", index=True
    )
    locale: Mapped[str] = mapped_column(String(16), default="vi", server_default="vi")
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Ho_Chi_Minh", server_default="Asia/Ho_Chi_Minh"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship("User")


class PhrAudit(Base):
    """Append-only audit trail for PHR create/update/delete/read events."""

    __tablename__ = "phr_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    entity: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    before_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PhrVersion(Base):
    """Monotonic per-profile snapshot history (append-only)."""

    __tablename__ = "phr_versions"
    __table_args__ = (
        UniqueConstraint("profile_id", "version_no", name="uq_phr_versions_profile_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, index=True)
    snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PhrObservation(Base):
    """Structured lab/vital observations linked to a PHR profile."""

    __tablename__ = "phr_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    entry_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    value: Mapped[str] = mapped_column(String(120), default="")
    unit: Mapped[str] = mapped_column(String(64), default="")
    observed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    information_source: Mapped[str] = mapped_column(String(32), default="self-declared")
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LifeMapEvent(Base):
    """Versioned personal health fact; a draft is never silently promoted."""

    __tablename__ = "lifemap_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_episodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    truth_state: Mapped[str] = mapped_column(String(24), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    provenance_json: Mapped[dict] = mapped_column(JSON)
    source_kind: Mapped[str] = mapped_column(String(32), default="reported", index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(24), default="active", server_default="active", index=True
    )
    current_revision_no: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LifeMapEpisode(Base):
    """A user-owned care loop, deliberately separate from a diagnosis."""

    __tablename__ = "lifemap_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(16), default="routine", index=True)
    outcome_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    handoff_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LifeMapEpisodeGoalRevision(Base):
    """Append-only episode goal history."""

    __tablename__ = "lifemap_episode_goal_revisions"
    __table_args__ = (
        UniqueConstraint(
            "episode_id",
            "revision_no",
            name="uq_lifemap_episode_goal_revision",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_episodes.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer)
    goal: Mapped[str] = mapped_column(Text, default="")
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapCareTask(Base):
    """An explicit, trackable next action in a care loop."""

    __tablename__ = "lifemap_care_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_episodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="proposed", index=True)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provenance_json: Mapped[dict] = mapped_column(JSON)
    version_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LifeMapDecisionLedger(Base):
    """Structured decision rationale, never private model chain-of-thought."""

    __tablename__ = "lifemap_decision_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_episodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    decision_type: Mapped[str] = mapped_column(String(64), index=True)
    disposition: Mapped[str] = mapped_column(String(24), index=True)
    inputs_json: Mapped[dict] = mapped_column(JSON)
    rationale_json: Mapped[dict] = mapped_column(JSON)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LifeMapEpisodeEventLink(Base):
    """Revision-aware membership of one fact in an episode replay."""

    __tablename__ = "lifemap_episode_event_links"
    __table_args__ = (
        UniqueConstraint(
            "episode_id",
            "event_revision_id",
            name="uq_lifemap_episode_event_revision_link",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_episodes.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_events.id", ondelete="CASCADE"), index=True
    )
    event_revision_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_event_revisions.id", ondelete="RESTRICT"), index=True
    )
    linked_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(24), default="active", server_default="active", index=True
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    unlinked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LifeMapDecisionInput(Base):
    """Relational link from a decision to the exact fact revision it consumed."""

    __tablename__ = "lifemap_decision_inputs"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "event_revision_id",
            name="uq_lifemap_decision_input_revision",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_decision_ledger.id", ondelete="CASCADE"), index=True
    )
    event_revision_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_event_revisions.id", ondelete="RESTRICT"), index=True
    )
    input_role: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapBaselineDefinition(Base):
    """Versioned, governed registry entry for one personal baseline signal."""

    __tablename__ = "lifemap_baseline_definitions"
    __table_args__ = (
        UniqueConstraint(
            "signal_key",
            "version",
            name="uq_lifemap_baseline_definition_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    signal_key: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(64), index=True)
    canonical_unit: Mapped[str] = mapped_column(String(32))
    valid_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    minimum_samples: Mapped[int] = mapped_column(Integer, default=7)
    minimum_span_days: Mapped[int] = mapped_column(Integer, default=7)
    window_days: Mapped[int] = mapped_column(Integer, default=28)
    source_eligibility_json: Mapped[dict] = mapped_column(JSON, default=dict)
    exclusions_json: Mapped[list] = mapped_column(JSON, default=list)
    change_rules_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default="draft", index=True
    )
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapBaselineSnapshot(Base):
    """Immutable reproducible result for a definition and input watermark."""

    __tablename__ = "lifemap_baseline_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "definition_id",
            "input_watermark",
            name="uq_lifemap_baseline_snapshot_watermark",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    definition_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_baseline_definitions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), index=True)
    median_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    mad_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer)
    span_days: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    input_watermark: Mapped[str] = mapped_column(String(64), index=True)
    rule_version: Mapped[str] = mapped_column(String(64))
    stale_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    stale_reason: Mapped[str] = mapped_column(String(96), default="")
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapBaselineInput(Base):
    """Exact daily aggregates consumed by a baseline snapshot."""

    __tablename__ = "lifemap_baseline_inputs"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "aggregate_id",
            name="uq_lifemap_baseline_snapshot_input",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_baseline_snapshots.id", ondelete="CASCADE"), index=True
    )
    aggregate_id: Mapped[int] = mapped_column(
        ForeignKey("wearable_daily_aggregates.id", ondelete="RESTRICT"), index=True
    )
    aggregate_policy_version: Mapped[str] = mapped_column(String(64))


class LifeMapBaselineChange(Base):
    """Explainable comparison between consecutive baseline snapshots."""

    __tablename__ = "lifemap_baseline_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    previous_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_baseline_snapshots.id", ondelete="CASCADE"), index=True
    )
    current_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_baseline_snapshots.id", ondelete="CASCADE"), index=True
    )
    change_kind: Mapped[str] = mapped_column(String(32), index=True)
    absolute_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    rule_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapQuestionDefinition(Base):
    """Versioned question catalogue; only approved rows are eligible."""

    __tablename__ = "lifemap_question_definitions"
    __table_args__ = (
        UniqueConstraint(
            "field_key",
            "version",
            "locale",
            name="uq_lifemap_question_definition_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    field_key: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(64), index=True)
    locale: Mapped[str] = mapped_column(String(16), index=True)
    episode_class: Mapped[str] = mapped_column(String(32), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    rationale_text: Mapped[str] = mapped_column(Text)
    sensitivity: Mapped[str] = mapped_column(String(24), default="standard")
    answer_schema_json: Mapped[dict] = mapped_column(JSON)
    impact_weight: Mapped[int] = mapped_column(Integer)
    impact_mapping_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default="draft", index=True
    )
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LifeMapQuestionInteraction(Base):
    """Append-only burden, dismissal, and answer history."""

    __tablename__ = "lifemap_question_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_episodes.id", ondelete="CASCADE"), index=True
    )
    question_definition_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_question_definitions.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(24), index=True)
    reason_code: Mapped[str] = mapped_column(String(64), default="")
    answer_event_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_event_revisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AIUseCaseDefinition(Base):
    """Governed authority boundary for one AI/ML use case and version."""

    __tablename__ = "ai_use_case_definitions"
    __table_args__ = (UniqueConstraint("use_case_id", "version", name="uq_ai_use_case_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_public_id)
    use_case_id: Mapped[str] = mapped_column(String(96), index=True)
    version: Mapped[str] = mapped_column(String(64))
    risk_class: Mapped[str] = mapped_column(String(32), index=True)
    owner: Mapped[str] = mapped_column(String(96))
    intended_users_json: Mapped[dict | list] = mapped_column(JSON)
    allowed_inputs_json: Mapped[dict | list] = mapped_column(JSON)
    allowed_outputs_json: Mapped[dict | list] = mapped_column(JSON)
    forbidden_uses_json: Mapped[dict | list] = mapped_column(JSON)
    champion_ref: Mapped[str] = mapped_column(String(160), default="")
    fallback_ref: Mapped[str] = mapped_column(String(160), default="")
    metrics_json: Mapped[dict | list] = mapped_column(JSON)
    release_state: Mapped[str] = mapped_column(
        String(32), default="research", server_default="research", index=True
    )
    requires_consent: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MLRegistryObject(Base):
    """Immutable manifest for datasets, models, evaluations and deployments."""

    __tablename__ = "ml_registry_objects"
    __table_args__ = (
        UniqueConstraint("object_kind", "stable_id", "version", name="uq_ml_registry_object"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_public_id)
    object_kind: Mapped[str] = mapped_column(String(40), index=True)
    stable_id: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(
        String(32), default="draft", server_default="draft", index=True
    )
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="")
    manifest_json: Mapped[dict | list] = mapped_column(JSON)
    parent_refs_json: Mapped[dict | list] = mapped_column(JSON)
    signature_key_id: Mapped[str] = mapped_column(String(96), default="")
    signature_base64: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIContextManifest(Base):
    """Private, content-free exact revision lineage compiled before inference."""

    __tablename__ = "ai_context_manifests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_public_id)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    use_case_id: Mapped[str] = mapped_column(String(96), index=True)
    purpose: Mapped[str] = mapped_column(String(64), index=True)
    actor_category: Mapped[str] = mapped_column(String(32))
    data_classes_json: Mapped[dict | list] = mapped_column(JSON)
    revision_refs_json: Mapped[dict | list] = mapped_column(JSON)
    context_digest: Mapped[str] = mapped_column(String(64), index=True)
    consent_version: Mapped[str] = mapped_column(String(64))
    grant_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MLInferenceManifest(Base):
    """No-content operational record linked to a private context manifest."""

    __tablename__ = "ml_inference_manifests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_public_id)
    context_manifest_id: Mapped[int] = mapped_column(
        ForeignKey("ai_context_manifests.id", ondelete="CASCADE"), index=True
    )
    use_case_id: Mapped[str] = mapped_column(String(96), index=True)
    model_ref: Mapped[str] = mapped_column(String(160), index=True)
    release_state: Mapped[str] = mapped_column(String(32), index=True)
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    abstention_code: Mapped[str] = mapped_column(String(64), default="")
    operational_json: Mapped[dict | list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


def _reject_governance_manifest_mutation(*_args: object, **_kwargs: object) -> None:
    raise ValueError("AI/ML governance manifests are immutable; append a new version")


for _immutable_governance_model in (
    AIUseCaseDefinition,
    MLRegistryObject,
    AIContextManifest,
    MLInferenceManifest,
):
    sa_event.listen(
        _immutable_governance_model,
        "before_update",
        _reject_governance_manifest_mutation,
    )
    sa_event.listen(
        _immutable_governance_model,
        "before_delete",
        _reject_governance_manifest_mutation,
    )


class LifeMapCaptureSession(Base):
    """A resumable, expiring Universal Capture review boundary."""

    __tablename__ = "lifemap_capture_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    input_kind: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default="draft", index=True
    )
    schema_version: Mapped[str] = mapped_column(String(64))
    locale: Mapped[str] = mapped_column(String(16), default="vi")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    abandoned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LifeMapCaptureArtifact(Base):
    """Encrypted capture artifact metadata; raw bytes live outside the database."""

    __tablename__ = "lifemap_capture_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_capture_sessions.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    media_type: Mapped[str] = mapped_column(String(128))
    byte_size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(128), index=True)
    encryption_version: Mapped[str] = mapped_column(String(32), default="aesgcm-v1")
    malware_status: Mapped[str] = mapped_column(
        String(24), default="pending", server_default="pending", index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapCaptureJob(Base):
    """Durable OCR/ML extraction job; output is always review-only candidates."""

    __tablename__ = "lifemap_capture_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_capture_sessions.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_capture_artifacts.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(48), index=True)
    status: Mapped[str] = mapped_column(
        String(24), default="queued", server_default="queued", index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    lease_owner: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    error_code: Mapped[str] = mapped_column(String(64), default="")
    extractor_version: Mapped[str] = mapped_column(String(96), default="")
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapCaptureCandidate(Base):
    """Untrusted extracted value awaiting an explicit review action."""

    __tablename__ = "lifemap_capture_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_capture_sessions.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_capture_artifacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    candidate_type: Mapped[str] = mapped_column(String(64), index=True)
    field_path: Mapped[str] = mapped_column(String(160))
    value_json: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_span_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    missing_critical_fields_json: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    extraction_schema_version: Mapped[str] = mapped_column(String(64))
    extractor_version: Mapped[str] = mapped_column(String(96), default="")
    security_findings_json: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default="draft", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapCaptureReviewAction(Base):
    """Append-only edit/reject/confirm history for one capture candidate."""

    __tablename__ = "lifemap_capture_review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_capture_candidates.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(24), index=True)
    patch_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapOutboxEvent(Base):
    """Transactional integration event emitted alongside LifeMap mutations."""

    __tablename__ = "lifemap_outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    aggregate_type: Mapped[str] = mapped_column(String(64), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(96), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_error_code: Mapped[str] = mapped_column(String(96), default="", server_default="")
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HealthSourceReference(Base):
    """Immutable origin metadata for a canonical or candidate LifeMap fact."""

    __tablename__ = "health_source_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    source_kind: Mapped[str] = mapped_column(String(32), index=True)
    source_identity: Mapped[str] = mapped_column(String(255), default="")
    author_type: Mapped[str] = mapped_column(String(32), default="")
    author_public_id: Mapped[str] = mapped_column(String(64), default="")
    device_identity: Mapped[str] = mapped_column(String(128), default="")
    checksum: Mapped[str] = mapped_column(String(128), default="", index=True)
    original_language: Mapped[str] = mapped_column(String(16), default="")
    source_span_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapEventRevision(Base):
    """Append-only truth and provenance revision for a LifeMap event."""

    __tablename__ = "lifemap_event_revisions"
    __table_args__ = (
        UniqueConstraint("event_id", "revision_no", name="uq_lifemap_event_revision_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_events.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer)
    truth_state: Mapped[str] = mapped_column(String(24), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    display_summary: Mapped[str] = mapped_column(Text, default="")
    provenance_json: Mapped[dict] = mapped_column(JSON)
    source_reference_id: Mapped[int | None] = mapped_column(
        ForeignKey("health_source_references.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asserted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64), default="")
    supersedes_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_event_revisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    policy_version: Mapped[str] = mapped_column(String(64), default="")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


@sa_event.listens_for(LifeMapEventRevision, "before_update")
def _prevent_lifemap_revision_update(_mapper, _connection, _target) -> None:
    """Canonical revisions are append-only; corrections insert a successor."""

    raise ValueError("LifeMap event revisions are immutable")


@sa_event.listens_for(HealthSourceReference, "before_update")
def _prevent_source_checksum_change(_mapper, _connection, target) -> None:
    """A source checksum is an immutable provenance identity."""

    if sa_inspect(target).attrs.checksum.history.has_changes():
        raise ValueError("Health source checksums are immutable")


class LifeMapTaskAction(Base):
    """Append-only task state transition ledger."""

    __tablename__ = "lifemap_task_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_care_tasks.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(32), index=True)
    from_state: Mapped[str] = mapped_column(String(24))
    to_state: Mapped[str] = mapped_column(String(24))
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reason: Mapped[str] = mapped_column(String(255), default="")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class LifeMapCommandRecord(Base):
    """Idempotency result keyed by actor, profile, operation, key, and digest."""

    __tablename__ = "lifemap_command_records"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "actor_user_id",
            "operation",
            "idempotency_key_hash",
            name="uq_lifemap_command_scope_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    operation: Mapped[str] = mapped_column(String(96), index=True)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64))
    request_digest: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapProjectionDependency(Base):
    """Input lineage and invalidation state for a derived LifeMap projection."""

    __tablename__ = "lifemap_projection_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    projection_type: Mapped[str] = mapped_column(String(64), index=True)
    projection_public_id: Mapped[str] = mapped_column(String(64), index=True)
    input_type: Mapped[str] = mapped_column(String(64))
    input_revision_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_event_revisions.id", ondelete="CASCADE"), index=True
    )
    rule_version: Mapped[str] = mapped_column(String(64))
    produced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    invalidation_reason: Mapped[str] = mapped_column(String(96), default="")


class MedicationCourse(Base):
    """Confirmed medication use, not an OCR or model assertion."""

    __tablename__ = "medication_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    medication_name: Mapped[str] = mapped_column(String(255), index=True)
    original_text: Mapped[str] = mapped_column(Text, default="")
    normalized_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    normalization_system: Mapped[str] = mapped_column(String(64), default="")
    normalization_code: Mapped[str] = mapped_column(String(128), default="", index=True)
    reconciliation_status: Mapped[str] = mapped_column(
        String(24), default="unknown", server_default="unknown", index=True
    )
    drugbank_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    dose_text: Mapped[str] = mapped_column(String(255), default="")
    schedule_text: Mapped[str] = mapped_column(String(255), default="")
    route_text: Mapped[str] = mapped_column(String(128), default="")
    form_text: Mapped[str] = mapped_column(String(128), default="")
    indication_text: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    truth_state: Mapped[str] = mapped_column(String(24), default="confirmed", index=True)
    provenance_json: Mapped[dict] = mapped_column(JSON)
    source_reference_id: Mapped[int | None] = mapped_column(
        ForeignKey("health_source_references.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MedicationCourseChange(Base):
    """Append-only medication reconciliation and lifecycle history."""

    __tablename__ = "medication_course_changes"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "version_no",
            name="uq_medication_course_change_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("medication_courses.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32), index=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    reason_code: Mapped[str] = mapped_column(String(96), default="")
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LifeMapVisit(Base):
    """A profile-owned appointment workflow, never a clinical encounter claim."""

    __tablename__ = "lifemap_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    visit_type: Mapped[str] = mapped_column(String(64), default="other", index=True)
    title: Mapped[str] = mapped_column(String(255))
    goal: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planning", index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VisitConcern(Base):
    """A user-authored concern for a visit; it does not establish a diagnosis."""

    __tablename__ = "visit_concerns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_visits.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(24), default="routine", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VisitEpisodeLink(Base):
    """Explicit link between a visit and a profile-owned LifeMap episode."""

    __tablename__ = "visit_episode_links"
    __table_args__ = (
        UniqueConstraint("visit_id", "episode_id", name="uq_visit_episode_links_visit_episode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_visits.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_episodes.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VisitPackVersion(Base):
    """Immutable, explicitly selected Visit Pack snapshot once approved."""

    __tablename__ = "visit_pack_versions"
    __table_args__ = (
        UniqueConstraint("visit_id", "version_no", name="uq_visit_pack_versions_visit_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_visits.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    selection_json: Mapped[dict] = mapped_column(JSON)
    contents_json: Mapped[dict] = mapped_column(JSON)
    source_versions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    policy_version: Mapped[str] = mapped_column(
        String(64), default="visit-pack-v2", server_default="visit-pack-v2"
    )
    purpose: Mapped[str] = mapped_column(
        String(64), default="visit_preparation", server_default="visit_preparation"
    )
    stale_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    stale_reason: Mapped[str] = mapped_column(String(96), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VisitConsent(Base):
    """Affirmative, visit-specific consent. Withdrawal invalidates processing."""

    __tablename__ = "visit_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_visits.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(64), index=True)
    policy_version: Mapped[str] = mapped_column(String(64))
    granted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str] = mapped_column(String(255), default="")


class VisitShare(Base):
    """Revocable, time-bounded capability to one immutable approved pack version."""

    __tablename__ = "visit_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    pack_version_id: Mapped[int] = mapped_column(
        ForeignKey("visit_pack_versions.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VisitIntakeAnswer(Base):
    """A user-controlled answer in the short, adaptive pre-visit intake.

    The question text, reason and skip/unknown decision are persisted together so
    later pack creation can explain what was asked without inventing a clinical
    assessment from the answer.
    """

    __tablename__ = "visit_intake_answers"
    __table_args__ = (
        UniqueConstraint("visit_id", "question_key", name="uq_visit_intake_answer_question"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_visits.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    question_key: Mapped[str] = mapped_column(String(96))
    question_text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(500), default="")
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_state: Mapped[str] = mapped_column(String(24), default="answered", index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VisitDocument(Base):
    """Bounded visit document text/metadata with explicit provenance and lifecycle.

    This deliberately stores no claimed OCR/extraction result. Binary-object
    storage can be added behind this record later; a document remains an external
    or unsigned draft until an authorized workflow records otherwise.
    """

    __tablename__ = "visit_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_visits.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    document_kind: Mapped[str] = mapped_column(
        String(48), default="external_user_uploaded", index=True
    )
    media_type: Mapped[str] = mapped_column(String(128), default="text/plain")
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    provenance_json: Mapped[dict] = mapped_column(JSON)
    content_digest: Mapped[str] = mapped_column(String(128), index=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(32), default="external_unverified", index=True)
    scribe_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("scribe_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdraw_reason: Mapped[str] = mapped_column(String(255), default="")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VisitPlanDraft(Base):
    """Candidate post-visit plan, never an instruction until explicit confirmation."""

    __tablename__ = "visit_plan_drafts"
    __table_args__ = (
        UniqueConstraint(
            "visit_id",
            "confirmation_key",
            name="uq_visit_plan_drafts_visit_confirmation_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("lifemap_visits.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("visit_documents.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="extraction_unavailable", index=True)
    extraction_provider: Mapped[str] = mapped_column(String(64), default="unavailable")
    candidates_json: Mapped[list | dict] = mapped_column(JSON)
    provenance_json: Mapped[dict] = mapped_column(JSON)
    confirmed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmation_request_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmation_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdraw_reason: Mapped[str] = mapped_column(String(255), default="")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VisitInstructionCandidate(Base):
    """Typed, source-grounded instruction awaiting an explicit review action."""

    __tablename__ = "visit_instruction_candidates"
    __table_args__ = (
        UniqueConstraint(
            "draft_id",
            "candidate_key",
            name="uq_visit_instruction_candidate_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("visit_plan_drafts.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("visit_documents.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    candidate_key: Mapped[str] = mapped_column(String(96))
    instruction_kind: Mapped[str] = mapped_column(String(48), index=True)
    classification: Mapped[str] = mapped_column(String(48), index=True)
    instruction_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    source_span_json: Mapped[dict] = mapped_column(JSON)
    source_document_digest: Mapped[str] = mapped_column(String(128), index=True)
    extraction_schema_version: Mapped[str] = mapped_column(String(64))
    extractor_version: Mapped[str] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default="draft", index=True
    )
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FamilyInvitation(Base):
    """One-time, recipient-bound invitation. The plaintext capability is never stored."""

    __tablename__ = "family_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    inviter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    recipient_email: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    proposed_scope_json: Mapped[dict] = mapped_column(JSON)
    purpose: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FamilyAccessGrant(Base):
    """Object/action/purpose scoped relationship grant with authoritative revocation."""

    __tablename__ = "family_access_grants"
    __table_args__ = (
        # A one-time invitation may materialize exactly one grant. NULL remains
        # valid for future grants created without an invitation.
        UniqueConstraint("invitation_id", name="uq_family_access_grants_invitation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    grantor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    grantee_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    object_type: Mapped[str] = mapped_column(String(32), index=True)
    object_id: Mapped[str] = mapped_column(String(64), index=True)
    data_classes_json: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    allowed_actions_json: Mapped[list[str]] = mapped_column(JSON)
    purpose: Mapped[str] = mapped_column(String(64), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    grant_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str] = mapped_column(String(255), default="")
    invitation_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_invitations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FamilyAccessLog(Base):
    """Append-only access decision ledger; denial is as important as success."""

    __tablename__ = "family_access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    grant_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_access_grants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    object_type: Mapped[str] = mapped_column(String(32), index=True)
    object_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    outcome: Mapped[str] = mapped_column(String(16), index=True)
    purpose: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConnectorAccount(Base):
    """A user-authorized, profile-scoped external health data source."""

    __tablename__ = "connector_accounts"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "provider",
            "external_subject_ref",
            name="uq_connector_account_profile_provider_subject",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32), index=True)
    external_subject_ref: Mapped[str] = mapped_column(String(255), default="")
    display_label: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="available", index=True)
    scopes_json: Mapped[list[str] | dict | None] = mapped_column(JSON, nullable=True)
    data_types_json: Mapped[list[str] | dict | None] = mapped_column(JSON, nullable=True)
    token_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    token_key_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConnectorConsent(Base):
    """Append-only connector data-type and purpose grant."""

    __tablename__ = "connector_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector_accounts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_version: Mapped[str] = mapped_column(String(32))
    purposes_json: Mapped[list[str] | dict] = mapped_column(JSON)
    data_types_json: Mapped[list[str] | dict] = mapped_column(JSON)
    access_direction: Mapped[str] = mapped_column(String(16), default="read")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConnectorSyncCursor(Base):
    __tablename__ = "connector_sync_cursors"
    __table_args__ = (
        UniqueConstraint("connector_id", "data_type", name="uq_connector_sync_cursor_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector_accounts.id", ondelete="CASCADE"), index=True
    )
    data_type: Mapped[str] = mapped_column(String(64))
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConnectorImportBatch(Base):
    __tablename__ = "connector_import_batches"
    __table_args__ = (
        UniqueConstraint("connector_id", "idempotency_key", name="uq_connector_import_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector_accounts.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(72))
    status: Mapped[str] = mapped_column(String(24), default="received", index=True)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    upserted_count: Mapped[int] = mapped_column(Integer, default=0)
    tombstoned_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WearableObservation(Base):
    __tablename__ = "wearable_observations"
    __table_args__ = (
        UniqueConstraint(
            "connector_id",
            "data_origin",
            "provider_record_id",
            name="uq_wearable_observation_provider_record",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector_accounts.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_record_id: Mapped[str] = mapped_column(String(512))
    data_origin: Mapped[str] = mapped_column(String(255))
    record_type: Mapped[str] = mapped_column(String(64), index=True)
    value_json: Mapped[dict] = mapped_column(JSON)
    observed_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    observed_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    zone_offset_start: Mapped[str | None] = mapped_column(String(6), nullable=True)
    zone_offset_end: Mapped[str | None] = mapped_column(String(6), nullable=True)
    device_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recording_method: Mapped[str] = mapped_column(String(24), default="unknown")
    quality_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provenance_json: Mapped[dict] = mapped_column(JSON)
    provider_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw_hash: Mapped[str] = mapped_column(String(72))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WearableObservationVersion(Base):
    """Append-only prior canonical observation value."""

    __tablename__ = "wearable_observation_versions"
    __table_args__ = (
        UniqueConstraint("observation_id", "version_no", name="uq_wearable_observation_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("wearable_observations.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WearableDailyAggregate(Base):
    __tablename__ = "wearable_daily_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "record_type",
            "local_date",
            name="uq_wearable_daily_aggregate",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    record_type: Mapped[str] = mapped_column(String(64), index=True)
    local_date: Mapped[date] = mapped_column(Date, index=True)
    value_json: Mapped[dict] = mapped_column(JSON)
    primary_origin: Mapped[str] = mapped_column(String(255))
    coverage_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WearableAggregateContribution(Base):
    __tablename__ = "wearable_aggregate_contributions"
    __table_args__ = (
        UniqueConstraint(
            "aggregate_id",
            "observation_id",
            name="uq_wearable_aggregate_contribution",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aggregate_id: Mapped[int] = mapped_column(
        ForeignKey("wearable_daily_aggregates.id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("wearable_observations.id", ondelete="CASCADE"), index=True
    )


class ConnectorAuditEvent(Base):
    """PII-minimized connector control and purpose-use audit."""

    __tablename__ = "connector_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int | None] = mapped_column(
        ForeignKey("connector_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConnectorOAuthTransaction(Base):
    __tablename__ = "connector_oauth_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32), index=True)
    state_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    pkce_verifier_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    redirect_uri: Mapped[str] = mapped_column(String(1024))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PhrReminder(Base):
    """Medication reminder / refill / caregiver-nudge configuration."""

    __tablename__ = "phr_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    medication_entry_id: Mapped[str] = mapped_column(String(64), index=True)
    schedule_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    remaining_supply: Mapped[float | None] = mapped_column(Float, nullable=True)
    refill_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    caregiver_nudge_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PhrShare(Base):
    """Read-only revocable share link to a PHR projection."""

    __tablename__ = "phr_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    share_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scope: Mapped[str] = mapped_column(String(32), default="full")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DsarRequest(Base):
    """Append-only Data Subject Access Request log (no free-text PII)."""

    __tablename__ = "dsar_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Opaque hashed user reference — never the email/name itself.
    user_ref: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="received", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComplianceEvent(Base):
    """Append-only compliance event log. ``meta_json`` is a PII-free projection."""

    __tablename__ = "compliance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    subject_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    processor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransferAssessment(Base):
    """Registry of cross-border processors + their Transfer Impact Assessment."""

    __tablename__ = "transfer_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processor: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(64), default="")
    purpose: Mapped[str] = mapped_column(String(64), default="")
    tia_doc_ref: Mapped[str] = mapped_column(String(128), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# CLARA Health Social Platform (clara-health-social).
#
# All tables are flag-gated at the router level (``social_platform_enabled``);
# when the flag is off none of these are ever read/written and the routes 404.
# The social identity is deliberately ISOLATED from the PHR: a social profile
# carries only a public handle/display name/bio and never references any
# clinical record. Moderation/report tables store opaque state only.
# ---------------------------------------------------------------------------


class SocialProfile(Base):
    """Public social identity for a user. Isolated from PHR (Req 2, 3, 10).

    Carries only self-declared public presentation fields (handle, display
    name, bio, avatar seed). NEVER references clinical data.
    """

    __tablename__ = "social_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    handle: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80), default="")
    bio: Mapped[str] = mapped_column(String(280), default="")
    avatar_seed: Mapped[str] = mapped_column(String(32), default="")
    is_verified_clinician: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SocialCommunity(Base):
    """A curated topic community (e.g. đái tháo đường, tim mạch)."""

    __tablename__ = "social_communities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(String(500), default="")
    is_curated: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialMembership(Base):
    """Join edge between a user and a community."""

    __tablename__ = "social_memberships"
    __table_args__ = (UniqueConstraint("user_id", "community_id", name="uq_social_membership"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    community_id: Mapped[int] = mapped_column(
        ForeignKey("social_communities.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialPost(Base):
    """A post authored by a user, optionally within a community.

    ``moderation_status`` gates visibility: only ``approved`` posts appear in
    feeds. Pre-publish moderation (ML legal guard + emergency + PII filter)
    sets this before the post is ever visible (Req 4, 6, 7, 8).
    """

    __tablename__ = "social_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    community_id: Mapped[int | None] = mapped_column(
        ForeignKey("social_communities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(160), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    moderation_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    moderation_reason: Mapped[str] = mapped_column(String(64), default="")
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SocialComment(Base):
    """A comment on a post; same pre-publish moderation contract as posts."""

    __tablename__ = "social_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("social_posts.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    moderation_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    moderation_reason: Mapped[str] = mapped_column(String(64), default="")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SocialReaction(Base):
    """A supportive reaction (helpful/relate/thanks). No public vanity counts."""

    __tablename__ = "social_reactions"
    __table_args__ = (UniqueConstraint("user_id", "post_id", "kind", name="uq_social_reaction"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("social_posts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="helpful")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialFollow(Base):
    """Directed follow edge between two users."""

    __tablename__ = "social_follows"
    __table_args__ = (UniqueConstraint("follower_id", "followee_id", name="uq_social_follow"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    followee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialReport(Base):
    """A user report against a post/comment, feeding the moderation queue."""

    __tablename__ = "social_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(16), index=True)  # post | comment
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    reason: Mapped[str] = mapped_column(String(32), default="other")
    detail: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SocialModerationAudit(Base):
    """Append-only, PII-free moderation audit (Req 12, 13).

    ``actor_ref`` is an opaque hashed reference, never the email/name.
    """

    __tablename__ = "social_moderation_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_ref: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    target_type: Mapped[str] = mapped_column(String(16), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    reason: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicalCase(Base):
    """Owner-scoped longitudinal container shared by CLARA clinical workflows."""

    __tablename__ = "clinical_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    case_type: Mapped[str] = mapped_column(String(32), default="general", index=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClinicalContextSnapshot(Base):
    """Immutable, provenance-bearing clinical context supplied to a workflow."""

    __tablename__ = "clinical_context_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    schema_version: Mapped[str] = mapped_column(String(32), default="1.0")
    context_json: Mapped[dict | list] = mapped_column(JSON)
    provenance_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ClinicalWorkflowRun(Base):
    """Durable execution record; never represents work that was not performed."""

    __tablename__ = "clinical_workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "idempotency_key", name="uq_clinical_workflow_owner_idempotency"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("clinical_context_snapshots.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    protocol: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_json: Mapped[dict | list] = mapped_column(JSON)
    result_summary_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClinicalStageRun(Base):
    __tablename__ = "clinical_stage_runs"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "stage_key", name="uq_clinical_stage_run_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), index=True
    )
    stage_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metrics_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvidenceRecord(Base):
    """Normalized evidence ledger entry with retrieval and citation provenance."""

    __tablename__ = "clinical_evidence_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    workflow_run_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(512), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    citation_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    evidence_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class EvidenceRunSubscription(Base):
    """Revocable opt-in for material updates to one evidence run."""

    __tablename__ = "evidence_run_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "workflow_run_id", name="uq_evidence_run_subscription_user_run"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    workflow_run_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    delivery_channel: Mapped[str] = mapped_column(String(32), default="in_app")
    interval_hours: Mapped[int] = mapped_column(
        Integer, default=168, server_default="168"
    )
    next_check_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvidenceApplicabilityRule(Base):
    """Governed executable rule; drafts cannot influence consumer output."""

    __tablename__ = "evidence_applicability_rules"
    __table_args__ = (
        UniqueConstraint(
            "question_class",
            "version",
            name="uq_evidence_applicability_rule_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    question_class: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(64))
    required_fact_types_json: Mapped[list[str]] = mapped_column(JSON)
    rule_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default="draft", index=True
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvidenceSourceCheckpoint(Base):
    """Stable per-source cursor for one subscription."""

    __tablename__ = "evidence_source_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "source_class",
            "provider",
            name="uq_evidence_checkpoint_subscription_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_run_subscriptions.id", ondelete="CASCADE"),
        index=True,
    )
    source_class: Mapped[str] = mapped_column(String(48), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    cursor: Mapped[str] = mapped_column(String(512), default="")
    watermark_digest: Mapped[str] = mapped_column(String(128), default="")
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvidenceMonitorJob(Base):
    """Leased, retryable execution intent containing references but no PHI."""

    __tablename__ = "evidence_monitor_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_run_subscriptions.id", ondelete="CASCADE"),
        index=True,
    )
    dedupe_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(24), default="pending", server_default="pending", index=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    lease_owner: Mapped[str] = mapped_column(String(96), default="")
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failure_code: Mapped[str] = mapped_column(String(64), default="")
    result_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("clinical_workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EvidenceChangeAssessment(Base):
    """Versioned material-change/contradiction result awaiting human review."""

    __tablename__ = "evidence_change_assessments"
    __table_args__ = (
        UniqueConstraint(
            "monitor_job_id", name="uq_evidence_change_assessment_job"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    monitor_job_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_monitor_jobs.id", ondelete="CASCADE"),
        index=True,
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_run_subscriptions.id", ondelete="CASCADE"),
        index=True,
    )
    previous_run_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_workflow_runs.id", ondelete="RESTRICT"),
        index=True,
    )
    current_run_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_workflow_runs.id", ondelete="RESTRICT"),
        index=True,
    )
    classification: Mapped[str] = mapped_column(String(40), index=True)
    contradiction_status: Mapped[str] = mapped_column(String(40), index=True)
    rule_version: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(96), default="none")
    review_status: Mapped[str] = mapped_column(
        String(24), default="pending", server_default="pending", index=True
    )
    safe_projection_json: Mapped[dict] = mapped_column(JSON)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvidenceChangeNotification(Base):
    """Minimum-data in-app card created only from an accepted assessment."""

    __tablename__ = "evidence_change_notifications"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id", name="uq_evidence_change_notification_assessment"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_change_assessments.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(24), default="unread", server_default="unread", index=True
    )
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class GuidelineArtifact(Base):
    """Curated, versioned guideline registry; drafts never reach consumer reads."""

    __tablename__ = "guideline_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=_public_id
    )
    title: Mapped[str] = mapped_column(String(500))
    source_provider: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str] = mapped_column(String(2_000))
    source_section: Mapped[str] = mapped_column(String(500), default="")
    jurisdiction: Mapped[str] = mapped_column(String(120), default="", index=True)
    version: Mapped[str] = mapped_column(String(128), default="")
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    intended_population_json: Mapped[dict | list] = mapped_column(JSON)
    eligibility_logic_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    action_options_json: Mapped[dict | list] = mapped_column(JSON)
    certainty: Mapped[str] = mapped_column(String(32), default="")
    content_json: Mapped[dict | list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClinicalClaim(Base):
    __tablename__ = "clinical_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    workflow_run_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), index=True
    )
    claim_type: Mapped[str] = mapped_column(String(32), index=True)
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="unverified", index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_ids_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    rationale_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicalArtifact(Base):
    __tablename__ = "clinical_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    workflow_run_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(48), index=True)
    schema_version: Mapped[str] = mapped_column(String(32), default="1.0")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    content_json: Mapped[dict | list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ClinicalReviewAction(Base):
    """Append-only human review, correction, sign-off, or override record."""

    __tablename__ = "clinical_review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_artifacts.id", ondelete="CASCADE"), index=True
    )
    reviewer_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(24), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    patch_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
