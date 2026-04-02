import re
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, EmailStr, Field, field_validator

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
    fallback_reason: str | None = None
    source_attempts: list[dict[str, Any]] = Field(default_factory=list)
    source_errors: dict[str, list[str]] = Field(default_factory=dict)
    query_plan: dict[str, Any] = Field(default_factory=dict)
    attributions: list[AttributionEntry] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    reply: str
    role: str
    intent: str | None = None
    confidence: float | None = None
    emergency: bool | None = None
    model_used: str | None = None
    retrieved_ids: list[Any] = Field(default_factory=list)
    ml: dict[str, Any] = Field(default_factory=dict)
    fallback: bool = False
    fallback_reason: str | None = None
    attribution: dict[str, Any] = Field(default_factory=dict)
    attributions: list[dict[str, Any]] = Field(default_factory=list)


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
    normalization_source: Literal["db", "candidate", "fallback"] | None = None
    normalization_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
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
    mapping_source: Literal["db", "candidate", "fallback"] | None = None
    mapping_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
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


class VnDrugMappingCreateRequest(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    active_ingredients: str = Field(default="", max_length=2000)
    normalized_name: str = Field(min_length=1, max_length=255)
    rx_cui: str = Field(default="", max_length=64)
    mapping_source: Literal["manual", "seed", "import", "curated", "neural"] = "manual"
    notes: str = Field(default="", max_length=4000)
    is_active: bool = True


class VnDrugMappingUpdateRequest(BaseModel):
    brand_name: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: list[str] | None = None
    active_ingredients: str | None = Field(default=None, max_length=2000)
    normalized_name: str | None = Field(default=None, min_length=1, max_length=255)
    rx_cui: str | None = Field(default=None, max_length=64)
    mapping_source: Literal["manual", "seed", "import", "curated", "neural"] | None = None
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class VnDrugMappingResponse(BaseModel):
    id: int
    brand_name: str
    aliases: list[str] = Field(default_factory=list)
    active_ingredients: str
    normalized_name: str
    rx_cui: str
    mapping_source: str
    notes: str
    is_active: bool
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


class VnDrugMappingListResponse(BaseModel):
    total: int
    items: list[VnDrugMappingResponse] = Field(default_factory=list)


class VnDrugResolveRequest(BaseModel):
    drug_name: str = Field(min_length=1, max_length=255)


class VnDrugResolveResponse(BaseModel):
    input_name: str
    display_name: str
    normalized_name: str
    rx_cui: str
    mapping_source: Literal["db", "candidate", "fallback"]
    mapping_confidence: float = Field(ge=0.0, le=1.0)


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
    precision_at_k: int = Field(default=10, ge=1, le=50)
    recall_at_k: int = Field(default=10, ge=1, le=50)
    ndcg_at_k: int = Field(default=10, ge=1, le=50)
    scientific_retrieval_enabled: bool = True
    web_retrieval_enabled: bool = True
    file_retrieval_enabled: bool = True


class CareguardRuntimeConfig(BaseModel):
    external_ddi_enabled: bool = False


class SystemControlTowerConfig(BaseModel):
    rag_sources: list[RagSourceEntry] = Field(default_factory=list)
    rag_flow: RagFlowConfig = Field(default_factory=RagFlowConfig)
    careguard_runtime: CareguardRuntimeConfig = Field(default_factory=CareguardRuntimeConfig)


class SystemSourceRegistryItem(BaseModel):
    id: str
    name: str
    group: str
    phase: Literal["public_no_key", "key_required", "commercial"]
    key_required: bool
    status: str
    notes: str


class SystemSourcesRegistryResponse(BaseModel):
    public_no_key: list[SystemSourceRegistryItem] = Field(default_factory=list)
    key_required: list[SystemSourceRegistryItem] = Field(default_factory=list)
    commercial: list[SystemSourceRegistryItem] = Field(default_factory=list)


class MobileApiHealth(BaseModel):
    status: str
    endpoint: str


class MobileSummaryResponse(BaseModel):
    role: Role
    api_health: MobileApiHealth
    quick_links: dict[str, str] = Field(default_factory=dict)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    last_updated: datetime


class CouncilRunRequest(BaseModel):
    symptoms: list[str] = Field(default_factory=list)
    labs: dict[str, float | str] = Field(default_factory=dict)
    medications: list[str] = Field(default_factory=list)
    history: str | list[str] | dict[str, Any] = ""
    specialist_count: int = Field(default=3, ge=2, le=5)
    specialists: list[str] = Field(default_factory=list)


class CouncilRunResponse(BaseModel):
    requested_specialists: list[str] = Field(default_factory=list)
    per_specialist_reasoning_logs: list[dict[str, Any]] = Field(default_factory=list)
    conflict_list: list[dict[str, Any] | str] = Field(default_factory=list)
    consensus_summary: str = ""
    divergence_notes: list[str] = Field(default_factory=list)
    final_recommendation: str = ""
    estimated_duration_minutes: int = 0
    emergency_escalation: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    data_quality: dict[str, Any] = Field(default_factory=dict)
    uncertainty_notes: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    analysis_sections: dict[str, Any] = Field(default_factory=dict)


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
    "vn_moh",
    "vn_kcb",
    "vn_canhgiacduoc",
    "vn_vbpl_byt",
    "vn_dav",
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
    limit: int = Field(default=12, ge=1, le=500)


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


class ResearchConversationMessageResponse(BaseModel):
    query_id: int
    query: str
    tier: ResearchConversationTier
    result: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class ResearchConversationMessagesResponse(BaseModel):
    conversation_id: int
    items: list[ResearchConversationMessageResponse] = Field(default_factory=list)


class ResearchTier2JobCreateRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    message: str | None = None
    research_mode: Literal["fast", "deep", "deep_beta"] = "fast"
    retrieval_stack_mode: Literal["auto", "full"] = Field(
        default="auto",
        validation_alias=AliasChoices("retrieval_stack_mode", "stack_mode"),
    )
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
