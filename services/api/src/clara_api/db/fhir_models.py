"""FHIR R4 data models for Patient and Observation ingestion and storage.

Provides persistence models for FHIR R4 Patient and Observation resources,
along with import batch tracking for multi-tenant and profile-scoped ingestion.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clara_api.db.base import Base


def _public_id() -> str:
    """Return a non-enumerable API identifier."""
    return str(uuid4())


class FhirImportBatch(Base):
    """Batch manifest recording the provenance and status of an imported FHIR bundle."""

    __tablename__ = "fhir_import_batches"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "idempotency_key",
            name="uq_fhir_import_batch_idempotency",
        ),
        Index("ix_fhir_import_batches_profile_status", "profile_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), default=_public_id, unique=True, index=True
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    raw_bundle_hash: Mapped[str | None] = mapped_column(
        String(72), nullable=True, index=True
    )
    source_system: Mapped[str] = mapped_column(
        String(128), default="external_fhir_r4", server_default="external_fhir_r4"
    )
    bundle_type: Mapped[str] = mapped_column(
        String(32), default="collection", server_default="collection"
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", index=True
    )
    total_resources: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    patient_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    observation_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    rejected_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    import_trust: Mapped[str] = mapped_column(
        String(32),
        default="untrusted_external_draft",
        server_default="untrusted_external_draft",
    )
    error_summary_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    resource_version: Mapped[str] = mapped_column(
        String(32), default="1", server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    patients: Mapped[list[FhirPatient]] = relationship(
        "FhirPatient", back_populates="import_batch", cascade="all, delete-orphan"
    )
    observations: Mapped[list[FhirObservation]] = relationship(
        "FhirObservation", back_populates="import_batch", cascade="all, delete-orphan"
    )


class FhirPatient(Base):
    """Imported FHIR R4 Patient resource projection and provenance anchor."""

    __tablename__ = "fhir_patients"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "fhir_id",
            name="uq_fhir_patient_profile_fhir_id",
        ),
        Index("ix_fhir_patients_profile_active", "profile_id", "active"),
        Index("ix_fhir_patients_identifier", "identifier_system", "identifier_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), default=_public_id, unique=True, index=True
    )
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("fhir_import_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    fhir_id: Mapped[str] = mapped_column(String(128), index=True)
    identifier_system: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    identifier_value: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    family_name: Mapped[str] = mapped_column(
        String(128), default="", server_default=""
    )
    given_name: Mapped[str] = mapped_column(
        String(128), default="", server_default=""
    )
    full_name: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    gender: Mapped[str] = mapped_column(
        String(32), default="unknown", server_default="unknown"
    )
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str] = mapped_column(String(64), default="", server_default="")
    email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    address_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    contacts_json: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    marital_status: Mapped[str] = mapped_column(
        String(64), default="", server_default=""
    )
    language: Mapped[str] = mapped_column(String(16), default="vi", server_default="vi")
    raw_resource_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    import_trust: Mapped[str] = mapped_column(
        String(32),
        default="untrusted_external_draft",
        server_default="untrusted_external_draft",
        index=True,
    )
    resource_version: Mapped[str] = mapped_column(
        String(32), default="1", server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    import_batch: Mapped[FhirImportBatch | None] = relationship(
        "FhirImportBatch", back_populates="patients"
    )


class FhirObservation(Base):
    """Imported FHIR R4 Observation resource (vitals, laboratory, clinical measurements)."""

    __tablename__ = "fhir_observations"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "fhir_id",
            name="uq_fhir_observation_profile_fhir_id",
        ),
        Index("ix_fhir_obs_profile_code", "profile_id", "code"),
        Index("ix_fhir_obs_profile_category", "profile_id", "category_code"),
        Index("ix_fhir_obs_profile_effective", "profile_id", "effective_datetime"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), default=_public_id, unique=True, index=True
    )
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("fhir_import_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    patient_fhir_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    fhir_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default="final", server_default="final", index=True
    )
    category_code: Mapped[str] = mapped_column(
        String(64), default="vital-signs", server_default="vital-signs", index=True
    )
    category_display: Mapped[str] = mapped_column(
        String(128), default="", server_default=""
    )
    code_system: Mapped[str] = mapped_column(
        String(128),
        default="http://loinc.org",
        server_default="http://loinc.org",
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), index=True)
    code_display: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    effective_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    value_type: Mapped[str] = mapped_column(
        String(32), default="Quantity", server_default="Quantity"
    )
    value_quantity_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_quantity_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_quantity_system: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    value_quantity_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_concept_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_absent_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interpretation_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interpretation_display: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    body_site: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_range_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_range_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_range_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_range_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    components_json: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    raw_resource_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    import_trust: Mapped[str] = mapped_column(
        String(32),
        default="untrusted_external_draft",
        server_default="untrusted_external_draft",
        index=True,
    )
    resource_version: Mapped[str] = mapped_column(
        String(32), default="1", server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    import_batch: Mapped[FhirImportBatch | None] = relationship(
        "FhirImportBatch", back_populates="observations"
    )
