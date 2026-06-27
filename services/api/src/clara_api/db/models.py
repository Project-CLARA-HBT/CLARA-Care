from datetime import date, datetime

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clara_api.db.base import Base


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
    oversight_state: Mapped[str | None] = mapped_column(
        String(16), nullable=True, default="none"
    )
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
    error_text: Mapped[str] = mapped_column(Text, default="")
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
        UniqueConstraint(
            "research_job_id", name="uq_workspace_conversation_shares_research_job"
        ),
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
    # New — monotonic per-profile version counter, bumped on each committed change.
    current_version_no: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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
