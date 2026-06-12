from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CLARA API"
    environment: str = Field(
        default="development", validation_alias=AliasChoices("ENVIRONMENT", "ENV")
    )
    debug: bool = Field(default=False, validation_alias="DEBUG")
    secure_error_messages: bool = Field(default=True, validation_alias="SECURE_ERROR_MESSAGES")

    database_url: str = Field(
        default="sqlite+pysqlite:///./clara.db",
        validation_alias="DATABASE_URL",
    )

    cors_allowed_origins: str = Field(
        default="*",
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    cors_allowed_methods: str = Field(
        default="GET,POST,PUT,PATCH,DELETE,OPTIONS",
        validation_alias="CORS_ALLOWED_METHODS",
    )
    cors_allowed_headers: str = Field(
        default="Authorization,Content-Type",
        validation_alias="CORS_ALLOWED_HEADERS",
    )
    cors_allow_credentials: bool = Field(
        default=False,
        validation_alias="CORS_ALLOW_CREDENTIALS",
    )

    jwt_secret_key: str = Field(
        default="change-me", min_length=8, validation_alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = Field(default="clara-api", validation_alias="JWT_ISSUER")
    jwt_access_minutes: int = Field(default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_minutes: int = Field(default=43200, validation_alias="REFRESH_TOKEN_EXPIRE_MINUTES")
    auth_cookie_access_name: str = Field(
        default="clara_access_token",
        validation_alias="AUTH_COOKIE_ACCESS_NAME",
    )
    auth_cookie_refresh_name: str = Field(
        default="clara_refresh_token",
        validation_alias="AUTH_COOKIE_REFRESH_NAME",
    )
    auth_cookie_secure: bool = Field(default=False, validation_alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: str = Field(default="lax", validation_alias="AUTH_COOKIE_SAMESITE")
    auth_cookie_domain: str = Field(default="", validation_alias="AUTH_COOKIE_DOMAIN")
    auth_cookie_path: str = Field(default="/", validation_alias="AUTH_COOKIE_PATH")
    auth_csrf_enabled: bool = Field(default=True, validation_alias="AUTH_CSRF_ENABLED")
    auth_csrf_cookie_name: str = Field(
        default="clara_csrf_token",
        validation_alias="AUTH_CSRF_COOKIE_NAME",
    )
    auth_csrf_header_name: str = Field(
        default="X-CSRF-Token",
        validation_alias="AUTH_CSRF_HEADER_NAME",
    )
    auth_refresh_reject_conflict: bool = Field(
        default=False,
        validation_alias="AUTH_REFRESH_REJECT_CONFLICT",
    )
    auth_auto_provision_users: bool = Field(
        default=True, validation_alias="AUTH_AUTO_PROVISION_USERS"
    )
    redis_url: str = Field(default="", validation_alias="REDIS_URL")
    security_redis_key_prefix: str = Field(
        default="clara:sec",
        validation_alias="SECURITY_REDIS_KEY_PREFIX",
    )
    rate_limit_distributed_enabled: bool = Field(
        default=False,
        validation_alias="RATE_LIMIT_DISTRIBUTED_ENABLED",
    )
    auth_login_distributed_enabled: bool = Field(
        default=False,
        validation_alias="AUTH_LOGIN_DISTRIBUTED_ENABLED",
    )
    auth_login_attempt_limit: int = Field(
        default=8,
        validation_alias="AUTH_LOGIN_ATTEMPT_LIMIT",
        gt=0,
    )
    auth_login_window_seconds: int = Field(
        default=300,
        validation_alias="AUTH_LOGIN_WINDOW_SECONDS",
        gt=0,
    )
    auth_login_lock_seconds: int = Field(
        default=600,
        validation_alias="AUTH_LOGIN_LOCK_SECONDS",
        gt=0,
    )
    auth_bootstrap_admin_enabled: bool = Field(
        default=False,
        validation_alias="AUTH_BOOTSTRAP_ADMIN_ENABLED",
    )
    auth_bootstrap_admin_email: str = Field(
        default="",
        validation_alias="AUTH_BOOTSTRAP_ADMIN_EMAIL",
    )
    auth_bootstrap_admin_password: str = Field(
        default="",
        validation_alias="AUTH_BOOTSTRAP_ADMIN_PASSWORD",
    )
    auth_bootstrap_admin_force_reset_password: bool = Field(
        default=False,
        validation_alias="AUTH_BOOTSTRAP_ADMIN_FORCE_RESET_PASSWORD",
    )
    auth_require_email_verification: bool = Field(
        default=False,
        validation_alias="AUTH_REQUIRE_EMAIL_VERIFICATION",
    )
    auth_action_token_ttl_minutes: int = Field(
        default=30,
        validation_alias="AUTH_ACTION_TOKEN_TTL_MINUTES",
        gt=0,
    )
    auth_login_otp_enabled: bool = Field(
        default=False,
        validation_alias="AUTH_LOGIN_OTP_ENABLED",
    )
    auth_login_otp_roles: str = Field(
        default="doctor,admin",
        validation_alias="AUTH_LOGIN_OTP_ROLES",
    )
    auth_login_otp_ttl_minutes: int = Field(
        default=5,
        validation_alias="AUTH_LOGIN_OTP_TTL_MINUTES",
        gt=0,
        le=30,
    )
    auth_action_rate_limit_attempts: int = Field(
        default=30,
        validation_alias="AUTH_ACTION_RATE_LIMIT_ATTEMPTS",
        gt=1,
    )
    auth_action_rate_limit_window_seconds: int = Field(
        default=300,
        validation_alias="AUTH_ACTION_RATE_LIMIT_WINDOW_SECONDS",
        gt=0,
    )
    auth_email_delivery_mode: str = Field(
        default="preview",
        validation_alias="AUTH_EMAIL_DELIVERY_MODE",
    )
    auth_expose_action_token_preview: bool = Field(
        default=True,
        validation_alias="AUTH_EXPOSE_ACTION_TOKEN_PREVIEW",
    )
    auth_public_web_base_url: str = Field(
        default="https://theclaracare.com",
        validation_alias="AUTH_PUBLIC_WEB_BASE_URL",
    )
    auth_verify_email_path: str = Field(
        default="/verify-email",
        validation_alias="AUTH_VERIFY_EMAIL_PATH",
    )
    auth_reset_password_path: str = Field(
        default="/reset-password",
        validation_alias="AUTH_RESET_PASSWORD_PATH",
    )
    medical_disclaimer_version: str = Field(
        default="2026-04-v1",
        validation_alias="MEDICAL_DISCLAIMER_VERSION",
    )
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT", gt=0)
    smtp_username: str = Field(default="", validation_alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", validation_alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, validation_alias="SMTP_USE_SSL")
    smtp_timeout_seconds: float = Field(default=10.0, validation_alias="SMTP_TIMEOUT_SECONDS", gt=0)

    rate_limit_requests: int = Field(default=120, validation_alias="GLOBAL_RATE_LIMIT_PER_MIN")
    rate_limit_window_seconds: int = Field(default=60, validation_alias="RATE_LIMIT_WINDOW_SECONDS")
    pubmed_rate_limit_per_sec: int = Field(default=10, validation_alias="PUBMED_RATE_LIMIT_PER_SEC")
    # NCBI E-utilities API key. When set, PubMed esearch/esummary/efetch requests
    # include it, raising the per-IP rate limit from 3 to 10 req/s. Optional; the
    # source hub works without it (just at the lower anonymous rate limit).
    ncbi_api_key: str = Field(default="", validation_alias="NCBI_API_KEY")
    # UMLS UTS API key (NLM licensed). Reserved for UMLS/RxNorm-authenticated
    # endpoints (e.g. RxClass, value sets). RxNorm normalization via the public
    # RxNav API does not require this key.
    umls_api_key: str = Field(default="", validation_alias="UMLS_API_KEY")
    ml_service_url: str = Field(default="http://localhost:8110", validation_alias="ML_SERVICE_URL")
    ml_internal_api_key: str = Field(default="", validation_alias="ML_INTERNAL_API_KEY")
    # --- Clara Scribe (enterprise) feature flags (additive; default off/legacy) ---
    # Wave 1 (R1–R11). All default off ⇒ legacy batch transcribe + SOAP flow.
    rag_scribe_streaming_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_STREAMING_ENABLED"
    )
    rag_scribe_diarization_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_DIARIZATION_ENABLED"
    )
    rag_scribe_consent_required: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_CONSENT_REQUIRED"
    )
    rag_scribe_templates_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_TEMPLATES_ENABLED"
    )
    rag_scribe_coding_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_CODING_ENABLED"
    )
    rag_scribe_sign_workflow_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_SIGN_WORKFLOW_ENABLED"
    )
    rag_scribe_export_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_EXPORT_ENABLED"
    )
    rag_scribe_fhir_export_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_FHIR_EXPORT_ENABLED"
    )
    # ASR provider selection seam (mirrors CLARA_ML config). "whisper" = the
    # existing DeepSeek/Whisper audio client; other names degrade to it.
    scribe_asr_primary: str = Field(
        default="whisper", validation_alias="SCRIBE_ASR_PRIMARY"
    )
    scribe_asr_fallback: str = Field(
        default="whisper", validation_alias="SCRIBE_ASR_FALLBACK"
    )
    scribe_asr_language: str = Field(
        default="vi", validation_alias="SCRIBE_ASR_LANGUAGE"
    )
    # --- Clara Scribe (enterprise) wave-2 feature flags -------------------------
    # R12–R20. All additive + default off ⇒ byte-for-byte current behavior.
    rag_scribe_grounding_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_GROUNDING_ENABLED"
    )
    rag_scribe_structured_extraction_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED"
    )
    rag_scribe_em_cpt_coding_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_EM_CPT_CODING_ENABLED"
    )
    rag_scribe_quality_metrics_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_QUALITY_METRICS_ENABLED"
    )
    rag_scribe_wer_reporting_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_WER_REPORTING_ENABLED"
    )
    rag_scribe_fhir_composition_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_FHIR_COMPOSITION_ENABLED"
    )
    rag_scribe_addendum_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_ADDENDUM_ENABLED"
    )
    rag_scribe_specialty_templates_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED"
    )
    rag_scribe_eval_gate_enabled: bool = Field(
        default=False, validation_alias="RAG_SCRIBE_EVAL_GATE_ENABLED"
    )
    ml_service_timeout_seconds: float = Field(
        default=60.0,
        validation_alias="ML_SERVICE_TIMEOUT_SECONDS",
        gt=0,
    )
    ml_research_timeout_seconds: float = Field(
        default=300.0,
        validation_alias="ML_RESEARCH_TIMEOUT_SECONDS",
        gt=0,
    )
    # Mirrors the CLARA_ML DeepSeek synthesis timeout so the API can guarantee its
    # ML request timeout never drops below the downstream synthesis floor (2.4).
    deepseek_timeout_seconds: float = Field(
        default=45.0,
        validation_alias=AliasChoices("DEEPSEEK_TIMEOUT_SECONDS", "DEEPSEEK_TIMEOUT"),
        gt=0,
    )
    research_job_max_workers: int = Field(
        default=8,
        validation_alias="RESEARCH_JOB_MAX_WORKERS",
        ge=1,
        le=32,
    )
    research_job_max_pending: int = Field(
        default=200,
        validation_alias="RESEARCH_JOB_MAX_PENDING",
        ge=1,
        le=2000,
    )
    research_job_max_active_per_user: int = Field(
        default=5,
        validation_alias="RESEARCH_JOB_MAX_ACTIVE_PER_USER",
        ge=1,
        le=100,
    )
    metrics_access_token: str = Field(default="", validation_alias="METRICS_ACCESS_TOKEN")
    deepseek_strict_mode: bool = Field(
        default=False,
        validation_alias="DEEPSEEK_STRICT_MODE",
    )
    tgc_ocr_base_url: str = Field(
        default="http://host.docker.internal:8080",
        validation_alias="TGC_OCR_BASE_URL",
    )
    tgc_ocr_endpoints: str = Field(
        default="/api/ocr,/api/extract,/ocr",
        validation_alias="TGC_OCR_ENDPOINTS",
    )
    tgc_ocr_timeout_seconds: float = Field(
        default=45.0,
        validation_alias="TGC_OCR_TIMEOUT_SECONDS",
        gt=0,
    )
    tgc_ocr_api_key: str = Field(default="", validation_alias="TGC_OCR_API_KEY")

    # Google Cloud Vision OCR
    google_vision_enabled: bool = Field(
        default=False,
        validation_alias="GOOGLE_VISION_ENABLED",
    )
    google_vision_service_account_json: str = Field(
        default="",
        validation_alias="GOOGLE_VISION_SERVICE_ACCOUNT_JSON",
    )
    google_vision_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="GOOGLE_VISION_TIMEOUT_SECONDS",
        gt=0,
    )
    google_vision_language_hints: str = Field(
        default="vi,en",
        validation_alias="GOOGLE_VISION_LANGUAGE_HINTS",
    )

    # Local Tesseract OCR (fallback)
    tesseract_ocr_enabled: bool = Field(
        default=True,
        validation_alias="TESSERACT_OCR_ENABLED",
    )
    tesseract_ocr_languages: str = Field(
        default="vie+eng",
        validation_alias="TESSERACT_OCR_LANGUAGES",
    )
    tesseract_ocr_psm: int = Field(
        default=6,
        validation_alias="TESSERACT_OCR_PSM",
        ge=0,
        le=13,
    )

    # Internal analytics dashboards (Requirement 12.4).
    # The Product_Analytics and Clinical_Analytics admin surfaces honor these
    # flags so a disabled surface returns 404, and an omitted date range
    # defaults to the trailing ``analytics_default_range_days`` window.
    product_analytics_enabled: bool = Field(
        default=True,
        validation_alias="PRODUCT_ANALYTICS_ENABLED",
    )
    clinical_analytics_enabled: bool = Field(
        default=True,
        validation_alias="CLINICAL_ANALYTICS_ENABLED",
    )
    analytics_default_range_days: int = Field(
        default=30,
        validation_alias="ANALYTICS_DEFAULT_RANGE_DAYS",
        gt=0,
        le=365,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
