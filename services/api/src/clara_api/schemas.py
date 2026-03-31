import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Role = Literal["normal", "researcher", "doctor", "admin"]


class User(BaseModel):
    id: int | None = None
    email: EmailStr
    role: Role = "normal"
    created_at: datetime | None = None


class Session(BaseModel):
    id: int | None = None
    user_id: int
    title: str = ""
    created_at: datetime | None = None


class Query(BaseModel):
    id: int | None = None
    session_id: int
    role: Role
    user_input: str
    response_text: str = ""
    created_at: datetime | None = None


class MedicalRecord(BaseModel):
    patient_id: str
    diagnosis: str = ""
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)


class Prescription(BaseModel):
    patient_id: str
    drug_name: str
    dosage: str
    frequency: str
    duration_days: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: Role


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)
    role: Role = "normal"

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value):
            raise ValueError("Mật khẩu phải có ít nhất 1 chữ cái và 1 chữ số")
        return value


class RegisterResponse(BaseModel):
    user_id: int
    email: EmailStr
    role: Role
    is_email_verified: bool
    email_delivery_status: str | None = None
    verification_token_preview: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    accepted: bool = True
    email_delivery_status: str | None = None
    reset_token_preview: str | None = None


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ResendVerificationResponse(BaseModel):
    accepted: bool = True
    email_delivery_status: str | None = None
    verification_token_preview: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value):
            raise ValueError("Mật khẩu phải có ít nhất 1 chữ cái và 1 chữ số")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_change_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value):
            raise ValueError("Mật khẩu phải có ít nhất 1 chữ cái và 1 chữ số")
        return value


class ConsentStatusResponse(BaseModel):
    consent_type: str = "medical_disclaimer"
    required_version: str
    accepted: bool
    user_id: int
    consent_version: str | None = None
    accepted_version: str | None = None
    accepted_at: datetime | None = None


class ConsentAcceptRequest(BaseModel):
    consent_version: str = Field(min_length=1, max_length=32)
    accepted: bool = True


class ConsentAcceptResponse(BaseModel):
    consent_type: str = "medical_disclaimer"
    user_id: int
    consent_version: str
    accepted_at: datetime


PolicyAction = Literal["allow", "warn", "block", "escalate"]


class AttributionCitation(BaseModel):
    source: str
    url: str | None = None


class AttributionSource(BaseModel):
    id: str
    name: str
    category: str | None = None
    type: str | None = None


class AttributionEntry(BaseModel):
    channel: str
    mode: str | None = None
    source_count: int = 0
    citation_count: int = 0
    sources: list[AttributionSource] = Field(default_factory=list)
    citations: list[AttributionCitation] = Field(default_factory=list)


class UnifiedContractMetadata(BaseModel):
    policy_action: PolicyAction | None = None
    fallback_used: bool = False
    source_errors: dict[str, list[str]] = Field(default_factory=dict)
    attributions: list[AttributionEntry] = Field(default_factory=list)


class MedicineCabinetItemCreate(BaseModel):
    drug_name: str = Field(min_length=1, max_length=255)
    dosage: str = ""
    dosage_form: str = ""
    quantity: float = 0.0
    source: Literal["manual", "ocr", "barcode", "imported"] = "manual"
    rx_cui: str = ""
    ocr_confidence: float | None = None
    expires_on: datetime | None = None
    note: str = ""


class MedicineCabinetItemUpdate(BaseModel):
    drug_name: str | None = Field(default=None, min_length=1, max_length=255)
    dosage: str | None = None
    dosage_form: str | None = None
    quantity: float | None = None
    source: Literal["manual", "ocr", "barcode", "imported"] | None = None
    rx_cui: str | None = None
    ocr_confidence: float | None = None
    expires_on: datetime | None = None
    note: str | None = None


class MedicineCabinetItemResponse(BaseModel):
    id: int
    drug_name: str
    normalized_name: str
    dosage: str
    dosage_form: str
    quantity: float
    source: str
    rx_cui: str
    ocr_confidence: float | None
    expires_on: datetime | None
    note: str
    created_at: datetime
    updated_at: datetime


class MedicineCabinetResponse(BaseModel):
    cabinet_id: int
    label: str
    items: list[MedicineCabinetItemResponse]


class CabinetScanTextRequest(BaseModel):
    text: str = Field(min_length=1)


class CabinetScanDetection(BaseModel):
    drug_name: str
    normalized_name: str
    confidence: float
    evidence: str
    requires_manual_confirm: bool = False
    confirmed: bool = False


class CabinetScanTextResponse(BaseModel):
    detections: list[CabinetScanDetection]
    extracted_text: str | None = None
    ocr_provider: str | None = None
    ocr_endpoint: str | None = None


class CabinetImportRequest(BaseModel):
    detections: list[CabinetScanDetection]


class CabinetAutoDdiRequest(BaseModel):
    symptoms: list[str] = Field(default_factory=list)
    labs: dict[str, float | str] = Field(default_factory=dict)
    allergies: list[str] = Field(default_factory=list)


class RagSourceEntry(BaseModel):
    id: str
    name: str
    enabled: bool
    priority: int = Field(ge=1, le=100)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    category: str


class RagFlowConfig(BaseModel):
    role_router_enabled: bool = True
    intent_router_enabled: bool = True
    verification_enabled: bool = True
    deepseek_fallback_enabled: bool = True
    low_context_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    scientific_retrieval_enabled: bool = True
    web_retrieval_enabled: bool = True
    file_retrieval_enabled: bool = True


class CareguardRuntimeConfig(BaseModel):
    external_ddi_enabled: bool = False


class SystemControlTowerConfig(BaseModel):
    rag_sources: list[RagSourceEntry] = Field(default_factory=list)
    rag_flow: RagFlowConfig = Field(default_factory=RagFlowConfig)
    careguard_runtime: CareguardRuntimeConfig = Field(default_factory=CareguardRuntimeConfig)


class KnowledgeSourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class KnowledgeSourceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class KnowledgeSourceResponse(BaseModel):
    id: int
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    documents_count: int = 0


class KnowledgeDocumentUpdateRequest(BaseModel):
    is_active: bool


class KnowledgeDocumentResponse(BaseModel):
    id: int
    source_id: int
    filename: str
    content_type: str
    size: int
    preview: str
    token_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


SourceHubSourceKey = Literal[
    "pubmed",
    "rxnorm",
    "openfda",
    "dailymed",
    "europepmc",
    "semantic_scholar",
    "clinicaltrials",
    "davidrug",
]


class SourceHubCatalogEntry(BaseModel):
    key: SourceHubSourceKey
    label: str
    description: str
    docs_url: str | None = None
    default_query: str | None = None
    supports_live_sync: bool = True


class SourceHubRecord(BaseModel):
    id: str
    source: SourceHubSourceKey
    title: str
    url: str | None = None
    snippet: str | None = None
    external_id: str | None = None
    query: str | None = None
    published_at: str | None = None
    synced_at: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class SourceHubRecordsResponse(BaseModel):
    records: list[SourceHubRecord] = Field(default_factory=list)


class SourceHubSyncRequest(BaseModel):
    source: SourceHubSourceKey
    query: str = Field(min_length=1, max_length=512)
    limit: int = Field(default=12, ge=1, le=100)


class SourceHubSyncResponse(BaseModel):
    source: SourceHubSourceKey
    query: str
    fetched: int = 0
    stored: int = 0
    records: list[SourceHubRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


ResearchConversationTier = Literal["tier1", "tier2"]
ResearchJobStatus = Literal["queued", "running", "completed", "failed"]


class ResearchConversationCreateRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    result: dict[str, object] = Field(default_factory=dict)


class ResearchConversationResponse(BaseModel):
    id: int
    query_id: int
    query: str
    tier: ResearchConversationTier
    result: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class ResearchConversationListResponse(BaseModel):
    items: list[ResearchConversationResponse] = Field(default_factory=list)


class ResearchTier2JobCreateRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    message: str | None = None
    research_mode: Literal["fast", "deep"] = "fast"
    answer_format: str = "markdown"
    response_format: str = "markdown"
    render_hints: dict[str, object] = Field(default_factory=dict)
    source_mode: str | None = None
    uploaded_file_ids: list[str] = Field(default_factory=list)
    source_ids: list[int] = Field(default_factory=list)
    source_hub_sources: list[SourceHubSourceKey] = Field(default_factory=list)


class ResearchTier2JobResponse(BaseModel):
    job_id: str
    status: ResearchJobStatus
    query: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    progress: dict[str, object] = Field(default_factory=dict)
    result: dict[str, object] | None = None
    error: str | None = None
