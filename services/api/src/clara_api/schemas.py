from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

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
    refresh_token: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)
    role: Role = "normal"


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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ConsentStatusResponse(BaseModel):
    consent_type: str = "medical_disclaimer"
    required_version: str
    accepted: bool
    accepted_version: str | None = None
    accepted_at: datetime | None = None


class ConsentAcceptRequest(BaseModel):
    consent_version: str = Field(min_length=1, max_length=32)
    accepted: bool = True


class ConsentAcceptResponse(BaseModel):
    consent_type: str = "medical_disclaimer"
    consent_version: str
    accepted_at: datetime


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
