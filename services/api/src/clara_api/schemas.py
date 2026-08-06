import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, EmailStr, Field, field_validator, model_validator

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
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    role: Role
    otp_required: bool = False
    otp_delivery_status: str | None = None
    otp_code_preview: str | None = None
    otp_expires_in_seconds: int | None = None


class LoginOtpVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(min_length=4, max_length=16)


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)
    role: Role = "normal"
    accepted_terms: bool = False
    accepted_privacy: bool = False
    accepted_medical_consent: bool = False

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
    ui_language: Literal["vi", "en"] = "vi"
    protocol: Literal["chat", "clinical_answer", "medication_review", "evidence_brief"] = (
        "clinical_answer"
    )
    clinical_context: dict[str, Any] | None = None


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
    # Compliance: AI model/version disclosure (Req 1.3, 1.4). Populated only when
    # COMPLIANCE_MODEL_DISCLOSURE_ENABLED; omitted otherwise (legacy envelope).
    ai_disclosure: dict[str, Any] | None = None


class MedicineCabinetItemCreate(BaseModel):
    drug_name: str = Field(min_length=1, max_length=255)
    brand_name: str = ""
    manufacturer: str = ""
    dosage: str = ""
    dosage_form: str = ""
    quantity: float = 0.0
    source: Literal["manual", "ocr", "barcode", "imported"] = "manual"
    rx_cui: str = ""
    ocr_confidence: float | None = None
    expires_on: datetime | None = None
    note: str = ""
    # Per-item expiry reminder state (Req 10.3). Persisted only when
    # ``SELFMED_EXPIRY_REMINDERS_ENABLED`` is on; ignored (no persistence) when
    # off so behavior is byte-equivalent to today (Req 10.4).
    expiry_reminder: dict[str, Any] | None = None


class MedicineCabinetItemUpdate(BaseModel):
    drug_name: str | None = Field(default=None, min_length=1, max_length=255)
    brand_name: str | None = None
    manufacturer: str | None = None
    dosage: str | None = None
    dosage_form: str | None = None
    quantity: float | None = None
    source: Literal["manual", "ocr", "barcode", "imported"] | None = None
    rx_cui: str | None = None
    ocr_confidence: float | None = None
    expires_on: datetime | None = None
    note: str | None = None
    # Per-item expiry reminder state (Req 10.3); persisted only behind
    # ``SELFMED_EXPIRY_REMINDERS_ENABLED`` (Req 10.4).
    expiry_reminder: dict[str, Any] | None = None


class MedicineCabinetItemResponse(BaseModel):
    id: int
    drug_name: str
    brand_name: str | None = None
    manufacturer: str | None = None
    normalized_name: str
    normalization_source: Literal["db", "candidate", "fallback"] | None = None
    normalization_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    # Derived normalization status surfaced to clients (Req 2.1, 2.5, 2.6).
    # ``matched`` (exact dictionary hit) / ``candidate`` (fuzzy dictionary
    # candidate) / ``fallback`` (alias-map hit) / ``needs_review`` (unmatched or
    # low-confidence — the user-entered name is retained, never dropped).
    # Additive + nullable so flags-off byte-equivalence is preserved for the
    # pre-existing fields (P12); ``needs_review`` is a convenience boolean
    # equal to ``normalization_status == "needs_review"``.
    normalization_status: (
        Literal["matched", "candidate", "fallback", "needs_review"] | None
    ) = None
    needs_review: bool = False
    dosage: str
    dosage_form: str
    quantity: float
    source: str
    rx_cui: str
    ocr_confidence: float | None
    expires_on: datetime | None
    # Derived expiry status from ``expires_on`` (Req 10.1). ``expired`` (in the
    # past), ``expiring_soon`` (within the configured window), ``ok`` (beyond the
    # window), or ``None`` when there is no expiry data (Req 10.5). Purely
    # derived — no persisted state — so the pre-existing fields stay
    # byte-equivalent (P12).
    expiry_status: Literal["expired", "expiring_soon", "ok"] | None = None
    # Persisted per-item reminder state, exposed only when
    # ``SELFMED_EXPIRY_REMINDERS_ENABLED`` is on (Req 10.3); ``None`` otherwise,
    # so flags-off behavior matches today (Req 10.4).
    expiry_reminder: dict[str, Any] | None = None
    note: str
    created_at: datetime
    updated_at: datetime


class CabinetExpirySummary(BaseModel):
    # Cabinet-level expiry rollup (Req 10.2) computed from each item's
    # ``expires_on``. Items with no expiry data are excluded from both counts
    # (Req 10.5).
    expired_count: int = 0
    expiring_soon_count: int = 0
    expiry_window_days: int = 0


class MedicineCabinetResponse(BaseModel):
    cabinet_id: int
    label: str
    items: list[MedicineCabinetItemResponse]
    # Expired / expiring-soon rollup surfaced in the cabinet summary (Req 10.2).
    # Additive + nullable so legacy clients ignore it and flags-off
    # byte-equivalence of the pre-existing fields is preserved (P12).
    expiry_summary: CabinetExpirySummary | None = None


class CabinetScanTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)


class OcrSourceCoordinate(BaseModel):
    """A reviewable source offset in the corrected OCR text.

    Providers that expose image polygons can be added later without changing the
    cabinet contract.  The current adapters reliably expose text only, so this
    coordinate system intentionally never pretends to be a bounding box.
    """

    coordinate_system: Literal["corrected_text_codepoint_offset"]
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered_offsets(self) -> "OcrSourceCoordinate":
        if self.end < self.start:
            raise ValueError("OCR source coordinate end must not precede start")
        return self


class OcrDataProcessingDisclosure(BaseModel):
    """Bounded disclosure returned with a review-only OCR result.

    It identifies a processing category only: never an upstream URL, account,
    raw upload, or OCR transcript. The client must acknowledge this disclosure
    before it sends a file to an OCR adapter.
    """

    processing_purpose: Literal["medication_candidate_extraction"]
    provider_category: Literal[
        "configured_ocr_service", "google_cloud_vision", "local_tesseract"
    ]
    upload_persisted_by_clara: bool = False
    raw_text_logged_by_clara: bool = False
    human_confirmation_required: bool = True
    schema_version: Literal["ocr-processing-disclosure.v1"] = (
        "ocr-processing-disclosure.v1"
    )


class CabinetScanDetection(BaseModel):
    drug_name: str
    normalized_name: str
    dosage: str | None = None
    brand_name: str | None = None
    manufacturer: str | None = None
    confidence: float
    evidence: str
    mapping_source: Literal["db", "candidate", "fallback"] | None = None
    mapping_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    # Derived normalization status (Req 2.1, 2.5, 2.6) — same vocabulary as the
    # cabinet item response so the UI can render a consistent badge before
    # import. Additive + nullable; legacy clients ignore it.
    normalization_status: (
        Literal["matched", "candidate", "fallback", "needs_review"] | None
    ) = None
    requires_manual_confirm: bool = False
    confirmed: bool = False
    capture_candidate_id: str | None = None
    source_coordinates: list[OcrSourceCoordinate] = Field(default_factory=list)


class CabinetPrioritizedField(BaseModel):
    drug_name: str
    brand_name: str = ""
    manufacturer: str = ""
    dosage: str = ""


class OcrConfirmGate(BaseModel):
    """Low-confidence OCR manual-confirm gate state (Req 2.2, 2.6).

    Surfaced on scan responses so clients can render the confirm gate
    explicitly: any detection below ``threshold`` (or otherwise flagged) must be
    manually confirmed before it can be imported. Additive + optional.
    """

    threshold: float
    total_detections: int = 0
    requires_confirmation: int = 0
    confirmed: int = 0
    needs_review: int = 0


class CabinetScanTextResponse(BaseModel):
    detections: list[CabinetScanDetection]
    extracted_text: str | None = None
    ocr_provider: str | None = None
    ocr_endpoint: str | None = None
    prioritized_fields: list[CabinetPrioritizedField] = Field(default_factory=list)
    confirm_gate: OcrConfirmGate | None = None
    capture_session_id: str | None = None


class CabinetImportRequest(BaseModel):
    # Bounded batch import (Req 4.5): oversized arrays are rejected with a PII-free 422.
    detections: list[CabinetScanDetection] = Field(max_length=200)


class CabinetImportResponse(BaseModel):
    inserted: int
    prioritized_fields: list[CabinetPrioritizedField] = Field(default_factory=list)


class CabinetDrugBankResolution(BaseModel):
    """An explicit, revalidated DrugBank identity for one owner-scoped item.

    This is only a request to re-run the check.  The API verifies cabinet
    ownership and raw-alias binding, and ML re-verifies the identifier against
    the current licensed DrugBank index; it never confirms or persists a drug.
    """

    cabinet_item_id: int = Field(gt=0)
    input_alias: str = Field(min_length=1, max_length=255)
    drugbank_id: str = Field(min_length=1, max_length=128)
    drugbank_version: str = Field(min_length=1, max_length=128)


class CabinetAutoDdiRequest(BaseModel):
    # Bounded list inputs (Req 4.5): caps keep auto-DDI payloads from growing unbounded.
    symptoms: list[str] = Field(default_factory=list, max_length=100)
    labs: dict[str, float | str] = Field(default_factory=dict)
    allergies: list[str] = Field(default_factory=list, max_length=100)
    # Presentation-only locale for the independently verified wording layer.
    # It is not used by DrugBank lookup, severity, or safety policy.
    locale: Literal["vi", "en"] = "vi"
    # Additive/default-empty: source-backed choices returned by the preceding
    # clarification terminal state.  Absent values preserve legacy behavior.
    resolutions: list[CabinetDrugBankResolution] = Field(default_factory=list, max_length=100)


class VnDrugMappingCreateRequest(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    active_ingredients: str = Field(default="", max_length=2000)
    normalized_name: str = Field(min_length=1, max_length=255)
    rx_cui: str = Field(default="", max_length=64)
    mapping_source: Literal["manual", "seed", "import", "curated", "neural"] = "manual"
    notes: str = Field(default="", max_length=4000)
    is_active: bool = True


class VnDrugMappingUpdateRequest(BaseModel):
    brand_name: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: list[str] | None = Field(default=None, max_length=100)
    active_ingredients: str | None = Field(default=None, max_length=2000)
    normalized_name: str | None = Field(default=None, min_length=1, max_length=255)
    rx_cui: str | None = Field(default=None, max_length=64)
    mapping_source: Literal["manual", "seed", "import", "curated", "neural"] | None = None
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class VnDrugMappingCurationRequest(BaseModel):
    brand_name: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: list[str] | None = Field(default=None, max_length=100)
    active_ingredients: str | None = Field(default=None, max_length=2000)
    normalized_name: str | None = Field(default=None, min_length=1, max_length=255)
    rx_cui: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None
    reason: str = Field(default="", max_length=1000)


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


class VnDrugMappingAuditResponse(BaseModel):
    id: int
    mapping_id: int
    actor_user_id: int | None
    actor_email: str | None = None
    action: str
    reason: str
    before_json: dict | list | None = None
    after_json: dict | list | None = None
    metadata_json: dict | list | None = None
    created_at: datetime


class VnDrugMappingAuditListResponse(BaseModel):
    total: int
    items: list[VnDrugMappingAuditResponse] = Field(default_factory=list)


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
    rule_verification_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("rule_verification_enabled", "verification_enabled"),
    )
    nli_model_enabled: bool = True
    rag_reranker_enabled: bool = True
    rag_nli_enabled: bool = True
    rag_graphrag_enabled: bool = True
    deepseek_fallback_enabled: bool = True
    low_context_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    precision_at_k: int = Field(default=10, ge=1, le=50)
    recall_at_k: int = Field(default=10, ge=1, le=50)
    ndcg_at_k: int = Field(default=10, ge=1, le=50)
    scientific_retrieval_enabled: bool = True
    web_retrieval_enabled: bool = True
    file_retrieval_enabled: bool = True
    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_verification_enabled(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "rule_verification_enabled" in value:
            return value
        if "verification_enabled" not in value:
            return value
        normalized = dict(value)
        normalized["rule_verification_enabled"] = normalized.get("verification_enabled")
        return normalized


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
    # Bounded list inputs (Req 4.5): caps bound the council request payload size.
    symptoms: list[str] = Field(default_factory=list, max_length=100)
    labs: dict[str, float | str] = Field(default_factory=dict)
    medications: list[str] = Field(default_factory=list, max_length=100)
    history: str | list[str] | dict[str, Any] = ""
    specialist_count: int = Field(default=3, ge=2, le=5)
    specialists: list[str] = Field(default_factory=list, max_length=50)


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
ResearchOutputMode = Literal["plain_language", "professional"]


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
    personal_mode: bool = False
    retrieval_stack_mode: Literal["auto", "full"] = Field(
        default="auto",
        validation_alias=AliasChoices("retrieval_stack_mode", "stack_mode"),
    )
    ui_language: Literal["vi", "en"] = Field(
        default="vi",
        validation_alias=AliasChoices("ui_language", "answer_language"),
    )
    # The API resolves this closed, presentation-only selector after RBAC and
    # again after the evidence-release gate. It never changes retrieval,
    # claims, citations, policy, or model routing.
    output_mode: ResearchOutputMode = "plain_language"
    # deep_pass_count declared EXACTLY ONCE with one bound set 1..6 (clara-research R1.2/R1.3).
    deep_pass_count: int | None = Field(default=None, ge=1, le=6)
    answer_format: str = "markdown"
    response_format: str = "markdown"
    render_hints: dict[str, Any] = Field(default_factory=dict)
    source_mode: str | None = None
    # Bounded batch arrays (Req 4.5): cap research-job inputs so a single job cannot
    # reference an unbounded set of uploads/sources; violations yield a PII-free 422.
    # uploaded_file_ids mirrors the in-process _MAX_RESEARCH_UPLOADS=200 ceiling.
    uploaded_file_ids: list[str] = Field(default_factory=list, max_length=200)
    source_ids: list[int] = Field(default_factory=list, max_length=200)
    source_hub_sources: list[SourceHubSourceKey] = Field(default_factory=list, max_length=50)
    # Additive clarifying-answer carrier (clara-research R12.2); defaults empty for back-compat.
    clarifying_answers: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reject_fast_personal(self) -> "ResearchTier2JobCreateRequest":
        # clara-research R15.2: preserve the invariant "never (fast && personal)".
        # Personalization is valid only in tier2 (deep / deep_beta); a fast request that
        # sets personal_mode is rejected rather than silently downgraded.
        if self.personal_mode and self.research_mode == "fast":
            raise ValueError(
                "personal_mode is not allowed when research_mode is 'fast' "
                "(invariant: never (fast && personal))."
            )
        return self


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
    run_manifest: dict[str, object] | None = None
    evidence_snapshot: dict[str, object] | None = None
    attempt_count: int = 0
    recovery_count: int = 0


class ResearchClarifyRequest(BaseModel):
    """Request to evaluate whether a deep research query needs clarification (R12)."""

    query: str = Field(min_length=1, max_length=4000)
    message: str | None = None
    research_mode: Literal["fast", "deep", "deep_beta"] = "deep"
    ui_language: Literal["vi", "en"] = Field(
        default="vi",
        validation_alias=AliasChoices("ui_language", "answer_language"),
    )


class ResearchClarifyQuestion(BaseModel):
    """A single clarifying question; ``id`` is the key used in ``clarifying_answers`` (R12.2)."""

    id: str
    question: str
    rationale: str | None = None


class ResearchClarifyResponse(BaseModel):
    """Clarifying-question payload returned by ``POST /research/clarify`` (clara-research R12.1)."""

    ambiguous: bool = False
    research_mode: Literal["fast", "deep", "deep_beta"] = "deep"
    questions: list[ResearchClarifyQuestion] = Field(default_factory=list)


class WorkspaceFolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    color: str = Field(default="cyan", max_length=32)
    icon: str = Field(default="folder", max_length=64)
    sort_order: int = 0


class WorkspaceFolderUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    color: str | None = Field(default=None, max_length=32)
    icon: str | None = Field(default=None, max_length=64)
    sort_order: int | None = None
    is_archived: bool | None = None


class WorkspaceFolderResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    color: str
    icon: str
    sort_order: int
    is_archived: bool
    conversation_count: int = 0
    created_at: datetime
    updated_at: datetime


class WorkspaceChannelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    visibility: Literal["private", "team", "public"] = "private"
    color: str = Field(default="violet", max_length=32)
    icon: str = Field(default="hash", max_length=64)
    sort_order: int = 0


class WorkspaceChannelUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    visibility: Literal["private", "team", "public"] | None = None
    color: str | None = Field(default=None, max_length=32)
    icon: str | None = Field(default=None, max_length=64)
    sort_order: int | None = None
    is_archived: bool | None = None


class WorkspaceChannelResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    visibility: Literal["private", "team", "public"]
    color: str
    icon: str
    sort_order: int
    is_archived: bool
    conversation_count: int = 0
    created_at: datetime
    updated_at: datetime


class WorkspaceConversationMetaUpdateRequest(BaseModel):
    folder_id: int | None = None
    channel_id: int | None = None
    is_favorite: bool | None = None
    touched: bool = True


class WorkspaceConversationUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class WorkspaceBulkConversationMetaUpdateRequest(BaseModel):
    conversation_ids: list[int] = Field(default_factory=list, min_length=1, max_length=200)
    folder_id: int | None = None
    channel_id: int | None = None
    is_favorite: bool | None = None
    touched: bool = True


class WorkspaceBulkConversationMetaUpdateResponse(BaseModel):
    updated_count: int = 0
    updated_ids: list[int] = Field(default_factory=list)


class WorkspaceConversationMetaResponse(BaseModel):
    conversation_id: int
    folder_id: int | None = None
    channel_id: int | None = None
    is_favorite: bool = False
    last_opened_at: datetime | None = None
    updated_at: datetime


class WorkspaceConversationListItem(BaseModel):
    conversation_id: int
    title: str
    preview: str
    query_id: int | None = None
    message_count: int = 0
    created_at: datetime
    last_message_at: datetime | None = None
    folder_id: int | None = None
    channel_id: int | None = None
    is_favorite: bool = False


class WorkspaceConversationListResponse(BaseModel):
    items: list[WorkspaceConversationListItem] = Field(default_factory=list)


class WorkspaceConversationShareCreateRequest(BaseModel):
    expires_in_hours: int = Field(default=168, ge=1, le=720)
    rotate: bool = False


class WorkspaceConversationShareResponse(BaseModel):
    share_id: int
    conversation_id: int
    # Capability material is returned only while it is issued/rotated.  It is
    # deliberately absent on an owner metadata read because the DB stores only
    # a digest and cannot safely recover it.
    share_token: str | None = None
    public_url: str | None = None
    is_active: bool
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ResearchTier2ShareResponse(BaseModel):
    """Read-only share link for a research tier2 job (R16.3).

    Reuses the ``WorkspaceConversationShare`` mechanism: a ``share_token`` and a
    ``/share/{token}`` public URL.
    """

    job_id: str
    share_id: int
    share_token: str | None = None
    public_url: str | None = None
    is_active: bool
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkspaceConversationShareListItem(BaseModel):
    share_id: int
    conversation_id: int
    conversation_title: str
    message_count: int = 0
    last_message_at: datetime | None = None
    is_active: bool
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkspacePublicConversationMessageResponse(BaseModel):
    query_id: int
    role: str
    query: str
    answer: str
    created_at: datetime


class WorkspacePublicConversationResponse(BaseModel):
    conversation_id: int
    title: str
    expires_at: datetime | None = None
    messages: list[WorkspacePublicConversationMessageResponse] = Field(default_factory=list)


class WorkspaceNoteCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content_markdown: str = ""
    tags: list[str] = Field(default_factory=list, max_length=50)
    is_pinned: bool = False
    conversation_id: int | None = None


class WorkspaceNoteUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_markdown: str | None = None
    tags: list[str] | None = Field(default=None, max_length=50)
    is_pinned: bool | None = None
    conversation_id: int | None = None


class WorkspaceNoteResponse(BaseModel):
    id: int
    title: str
    content_markdown: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    is_pinned: bool
    conversation_id: int | None = None
    created_at: datetime
    updated_at: datetime


class WorkspaceSuggestionResponse(BaseModel):
    id: str
    text: str
    category: str
    score: float


class WorkspaceSuggestionsResponse(BaseModel):
    items: list[WorkspaceSuggestionResponse] = Field(default_factory=list)


class WorkspaceSearchResponse(BaseModel):
    query: str
    conversations: list[WorkspaceConversationListItem] = Field(default_factory=list)
    notes: list[WorkspaceNoteResponse] = Field(default_factory=list)
    folders: list[WorkspaceFolderResponse] = Field(default_factory=list)
    channels: list[WorkspaceChannelResponse] = Field(default_factory=list)
    suggestions: list[WorkspaceSuggestionResponse] = Field(default_factory=list)


class WorkspaceSummaryResponse(BaseModel):
    conversations: int = 0
    messages: int = 0
    folders: int = 0
    channels: int = 0
    notes: int = 0
    pinned_notes: int = 0


class WorkspaceExportFormatResponse(BaseModel):
    format: Literal["markdown", "docx"]
    filename: str


class ScribeGroundingResponse(BaseModel):
    """Read response for a note version's grounding report (Req 12.7).

    ``grounding`` is the additive :class:`GroundingReport` serialized by the ML pass
    (statements + per-statement grounded/unverified indicator + supporting span ids,
    grounded-claim rate, and critical-safety unverified candidates). It is metadata
    only — the note's clinical text is never altered by the grounding pass (Req 12.6).
    """

    session_id: int
    version_no: int
    grounding: dict[str, Any] = Field(default_factory=dict)


class ScribeExtractionResponse(BaseModel):
    """Read response for a note version's structured-extraction result (Req 13).

    ``extraction`` is the additive :class:`StructuredExtraction` serialized by the ML
    pass (problems/medications/allergies/vitals, each with transcript-span provenance
    and, for medications, ``rxcui`` when known). Metadata only — the note's clinical
    text is never altered by the extraction pass (Req 13.5).
    """

    session_id: int
    version_no: int
    extraction: dict[str, Any] = Field(default_factory=dict)


class ScribeCodingResponse(BaseModel):
    """Read response for a note version's E/M + CPT coding suggestions (Req 14.3/14.5).

    ``coding`` is the additive :class:`CodingResult` serialized by the ML pass
    (ICD-10 + medications + interactions per Req 7, plus an ``em_cpt`` list of
    advisory E/M visit-level and CPT/procedure suggestions per Req 14). Every
    suggestion carries justifying span(s) and is ``selected=False`` from the server
    — nothing is auto-selected; clinician confirmation happens in the web client.
    Metadata only — the note's clinical text is never altered by the coding pass
    (Req 14.7).
    """

    session_id: int
    version_no: int
    coding: dict[str, Any] = Field(default_factory=dict)


class ScribeAddendumResponse(BaseModel):
    """Response for an append-only addendum attached to a signed note (Req 18).

    An addendum is a time-stamped clinical note (``author``, ``created_at``,
    ``text``) attached to a ``signed`` :class:`ScribeNoteVersion`. Attaching it
    leaves the signed version byte-for-byte unchanged and creates no new note
    version (distinct from amend) — this response simply echoes the appended
    record so the client can render it without a re-fetch (Req 18.2/18.3/18.5).
    """

    session_id: int
    version_no: int
    addendum_id: int
    author: int | None = None
    text: str
    created_at: datetime | None = None


class ScribeAddendumListResponse(BaseModel):
    """Read response listing a signed note version's addenda in append order (Req 18.6)."""

    session_id: int
    version_no: int
    addenda: list[ScribeAddendumResponse] = Field(default_factory=list)


class PhrAllergyItemLegacy(BaseModel):
    """Legacy allergy item shape (kept for byte-for-byte flags-off /record)."""

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=140)
    reaction: str = Field(default="", max_length=200)
    severity: Literal["mild", "moderate", "severe", "unknown"] = "unknown"
    note: str = Field(default="", max_length=500)


class PhrConditionItemLegacy(BaseModel):
    """Legacy condition item shape (flags-off /record)."""

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    status: Literal["active", "resolved", "monitoring", "unknown"] = "unknown"
    diagnosed_on: date | None = None
    note: str = Field(default="", max_length=500)


class PhrMedicationItemLegacy(BaseModel):
    """Legacy medication item shape (flags-off /record)."""

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    dose: str = Field(default="", max_length=140)
    frequency: str = Field(default="", max_length=140)
    started_on: date | None = None
    is_current: bool = True
    note: str = Field(default="", max_length=500)


class PhrAllergyItem(BaseModel):
    # --- existing (unchanged) ---
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=140)
    reaction: str = Field(default="", max_length=200)
    severity: Literal["mild", "moderate", "severe", "unknown"] = "unknown"
    note: str = Field(default="", max_length=500)
    # --- new coded + provenance (additive, optional, safe defaults) ---
    substance: str = Field(default="", max_length=140)
    coded_substance_id: str = Field(default="", max_length=64)
    is_coded: bool = False
    information_source: Literal["self-declared", "ocr", "imported"] = "self-declared"
    verification_status: str = Field(default="unconfirmed", max_length=32)


class PhrConditionItem(BaseModel):
    # --- existing (unchanged) ---
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    status: Literal["active", "resolved", "monitoring", "unknown"] = "unknown"
    diagnosed_on: date | None = None
    note: str = Field(default="", max_length=500)
    # --- new coded + provenance (additive, optional, safe defaults) ---
    icd10_code: str = Field(default="", max_length=16)
    snomed_code: str = Field(default="", max_length=32)
    is_coded: bool = False
    information_source: Literal["self-declared", "ocr", "imported"] = "self-declared"
    verification_status: str = Field(default="unconfirmed", max_length=32)


class PhrMedicationItem(BaseModel):
    # --- existing (unchanged) ---
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    dose: str = Field(default="", max_length=140)
    frequency: str = Field(default="", max_length=140)
    started_on: date | None = None
    is_current: bool = True
    note: str = Field(default="", max_length=500)
    # --- new structured (additive, optional, safe defaults) ---
    dose_amount: float | None = Field(default=None, ge=0)
    dose_unit: str = Field(default="", max_length=32)
    route: str = Field(default="", max_length=64)
    # --- new coded ---
    normalized_name: str = Field(default="", max_length=160)
    rx_cui: str = Field(default="", max_length=64)
    normalization_source: str = Field(default="", max_length=32)
    is_normalized: bool = False
    duplicate_of: str | None = Field(default=None, max_length=64)
    # --- new provenance ---
    information_source: Literal["self-declared", "ocr", "imported"] = "self-declared"
    verification_status: str = Field(default="unconfirmed", max_length=32)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)


class PhrRecordUpdateRequest(BaseModel):
    full_name: str = Field(default="", max_length=255)
    date_of_birth: date | None = None
    gender: str = Field(default="", max_length=32)
    blood_type: str = Field(default="", max_length=16)
    height_cm: float | None = Field(default=None, ge=0, le=300)
    weight_kg: float | None = Field(default=None, ge=0, le=800)
    phone: str = Field(default="", max_length=64)
    contact_email: str = Field(default="", max_length=254)
    address: str = Field(default="", max_length=2000)
    emergency_contact_name: str = Field(default="", max_length=255)
    emergency_contact_phone: str = Field(default="", max_length=64)
    emergency_contact_relationship: str = Field(default="", max_length=80)
    emergency_contact_note: str = Field(default="", max_length=2000)
    insurance_provider: str = Field(default="", max_length=255)
    insurance_id: str = Field(default="", max_length=128)
    insurance_expiry: date | None = None
    allergy_status: Literal["unknown", "none_known", "recorded"] = "unknown"
    notes: str = Field(default="", max_length=4000)
    allergies: list[PhrAllergyItemLegacy] = Field(default_factory=list, max_length=80)
    conditions: list[PhrConditionItemLegacy] = Field(default_factory=list, max_length=80)
    medications: list[PhrMedicationItemLegacy] = Field(default_factory=list, max_length=120)


class PhrRecordResponse(BaseModel):
    """Legacy /record response shape — unchanged so flags-off equivalence holds."""

    full_name: str = ""
    date_of_birth: date | None = None
    gender: str = ""
    blood_type: str = ""
    height_cm: float | None = None
    weight_kg: float | None = None
    phone: str = ""
    address: str = ""
    emergency_contact_name: str = ""
    emergency_contact_phone: str = ""
    insurance_id: str = ""
    notes: str = ""
    allergies: list[PhrAllergyItemLegacy] = Field(default_factory=list)
    conditions: list[PhrConditionItemLegacy] = Field(default_factory=list)
    medications: list[PhrMedicationItemLegacy] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PhrOnboardingUpdateRequest(BaseModel):
    """Partial, owner-declared first-run profile setup.

    Every health field is optional. Omitted fields are preserved, while an
    explicitly supplied empty value clears that field. No answer is inferred.
    """

    action: Literal["save", "complete", "skip"] = "save"
    confirm_self_declared: bool = False
    personalization_consent: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    blood_type: str | None = Field(default=None, max_length=16)
    height_cm: float | None = Field(default=None, ge=0, le=300)
    weight_kg: float | None = Field(default=None, ge=0, le=800)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=64)
    allergies: list[PhrAllergyItemLegacy] | None = Field(default=None, max_length=80)
    conditions: list[PhrConditionItemLegacy] | None = Field(default=None, max_length=80)
    medications: list[PhrMedicationItemLegacy] | None = Field(default=None, max_length=120)


class PhrOnboardingResponse(BaseModel):
    status: Literal["pending", "completed", "skipped"]
    needs_onboarding: bool
    version: str
    completed_at: datetime | None = None
    personalization_consent: bool
    optional_fields: list[str] = Field(default_factory=list)
    record: PhrRecordResponse


class PhrEnhancedRecordResponse(BaseModel):
    """Enhanced /record/enhanced response — surfaces coded/provenance fields."""

    full_name: str = ""
    date_of_birth: date | None = None
    gender: str = ""
    blood_type: str = ""
    height_cm: float | None = None
    weight_kg: float | None = None
    phone: str = ""
    contact_email: str = ""
    address: str = ""
    emergency_contact_name: str = ""
    emergency_contact_phone: str = ""
    emergency_contact_relationship: str = ""
    emergency_contact_note: str = ""
    insurance_provider: str = ""
    insurance_id: str = ""
    insurance_expiry: date | None = None
    allergy_status: Literal["unknown", "none_known", "recorded"] = "unknown"
    notes: str = ""
    allergies: list[PhrAllergyItem] = Field(default_factory=list)
    conditions: list[PhrConditionItem] = Field(default_factory=list)
    medications: list[PhrMedicationItem] = Field(default_factory=list)
    current_version_no: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PhrEntryPatchRequest(BaseModel):
    """Entry/field-level patch payload for PATCH /phr/entries/{kind}/{id}."""

    fields: dict[str, Any] = Field(default_factory=dict)


class PhrConsentMutationRequest(BaseModel):
    purpose: Literal["personalization", "research", "sharing"]
    granted: bool = True


class PhrObservationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    value: str = Field(default="", max_length=120)
    unit: str = Field(default="", max_length=64)
    observed_on: date | None = None


class PhrBodyMeasurementCreateRequest(BaseModel):
    """One user-entered height/weight measurement at a single point in time.

    Keeping the pair in one request prevents the UI from accidentally deriving
    BMI from values recorded on unrelated dates.  The values are persisted as
    standard PHR observations so they remain included in export and DSAR flows.
    """

    height_cm: float = Field(gt=0, le=300)
    weight_kg: float = Field(gt=0, le=800)
    observed_on: date | None = None


class PhrShareCreateRequest(BaseModel):
    scope: Literal["full", "emergency_card"] = "full"
    expires_in_days: int = Field(default=30, ge=1, le=365)


class PhrOcrCandidate(BaseModel):
    """A single OCR-extracted candidate medication awaiting confirmation."""

    candidate_id: str = Field(min_length=8, max_length=96)
    name: str = Field(min_length=1, max_length=160)
    dose: str = Field(default="", max_length=140)
    frequency: str = Field(default="", max_length=140)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    # OCR values are proposals. Every row needs an explicit user acceptance;
    # numerical OCR confidence is not a confirmation surrogate.
    requires_manual_confirm: bool = True
    confirmed: bool = False
    source_coordinates: list[OcrSourceCoordinate] = Field(default_factory=list)


class PhrOcrScanResponse(BaseModel):
    """Owner-bound review-only candidates; no PHR state is committed."""

    committed: Literal[False] = False
    candidates: list[PhrOcrCandidate] = Field(default_factory=list)
    review_token: str = Field(min_length=20, max_length=4096)
    processing_disclosure: OcrDataProcessingDisclosure


class PhrOcrConfirmRequest(BaseModel):
    """User-edited candidate list to commit as ``ocr``-sourced entries."""

    review_token: str = Field(min_length=20, max_length=4096)
    # Includes every opaque ID returned by scan, including rows the person
    # discards. This lets the API verify the owner-bound review capability
    # without treating a discarded OCR proposal as confirmed data.
    review_candidate_ids: list[str] = Field(min_length=1, max_length=120)
    medications: list[PhrOcrCandidate] = Field(default_factory=list, max_length=120)


class PhrReminderCreateRequest(BaseModel):
    medication_entry_id: str = Field(min_length=1, max_length=64)
    schedule: dict[str, Any] = Field(default_factory=dict)
    remaining_supply: float | None = Field(default=None, ge=0)
    refill_threshold: float | None = Field(default=None, ge=0)
    caregiver_nudge_enabled: bool = False


class PhrReminderDoseState(BaseModel):
    """Per-medication dose acknowledgement state supplied at dispatch time."""

    dose_marked_taken: bool = False
    within_window: bool = True


class PhrReminderDispatchRequest(BaseModel):
    """Trigger evaluation + notification dispatch for the owner's reminders.

    ``now`` allows callers (e.g. the scheduler) to pin the evaluation instant;
    ``dose_states`` carries per-medication-entry acknowledgement state used by
    the caregiver missed-dose nudge decision (Req 14.5).
    """

    now: datetime | None = None
    dose_states: dict[str, PhrReminderDoseState] = Field(default_factory=dict)
