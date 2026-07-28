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

    # --- Database connection-pool sizing (additive; defaults preserve behavior) ---
    # These map to the SQLAlchemy QueuePool knobs applied during engine creation
    # for non-SQLite backends. The defaults equal SQLAlchemy's own defaults so an
    # unconfigured deployment behaves exactly as before (only ``pool_pre_ping`` was
    # set previously). Production deploys size ``DB_POOL_SIZE`` / ``DB_MAX_OVERFLOW``
    # relative to the API/ML worker count (Requirement 10.2). ``pool_pre_ping`` is
    # always preserved as the liveness check; ``DB_POOL_PRE_PING`` exists only as an
    # explicit override and defaults on.
    db_pool_size: int = Field(
        default=5,
        validation_alias="DB_POOL_SIZE",
        ge=1,
    )
    db_max_overflow: int = Field(
        default=10,
        validation_alias="DB_MAX_OVERFLOW",
        ge=0,
    )
    # Recycle connections after this many seconds. ``-1`` (the default) disables
    # recycling, matching SQLAlchemy's default and the prior behavior.
    db_pool_recycle: int = Field(
        default=-1,
        validation_alias="DB_POOL_RECYCLE",
        ge=-1,
    )
    # Seconds to wait for a connection from the pool before raising. ``30`` is the
    # SQLAlchemy default, preserving current behavior.
    db_pool_timeout: int = Field(
        default=30,
        validation_alias="DB_POOL_TIMEOUT",
        ge=1,
    )
    db_pool_pre_ping: bool = Field(
        default=True,
        validation_alias="DB_POOL_PRE_PING",
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
    # Previous JWT signing key, used for verification only during a key-overlap
    # rotation window (Requirement 1.7). Default empty ⇒ no overlap window and
    # behavior is identical to the pre-hardening baseline: only the current
    # ``jwt_secret_key`` signs and verifies tokens. When set, newly minted tokens
    # are still signed with ``jwt_secret_key``, but tokens that fail verification
    # against the current key are additionally checked against this previous key
    # so rotating the signing key does not force a mass logout. Operators clear
    # this value once all tokens signed with the prior key have naturally expired.
    jwt_secret_key_previous: str = Field(
        default="", validation_alias="JWT_SECRET_KEY_PREVIOUS"
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
    scribe_asr_primary: str = Field(default="whisper", validation_alias="SCRIBE_ASR_PRIMARY")
    scribe_asr_fallback: str = Field(default="whisper", validation_alias="SCRIBE_ASR_FALLBACK")
    scribe_asr_language: str = Field(default="vi", validation_alias="SCRIBE_ASR_LANGUAGE")
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
    ml_scribe_timeout_seconds: float = Field(
        default=180.0,
        validation_alias="ML_SCRIBE_TIMEOUT_SECONDS",
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
    # Simple API-key auth for the Vision REST API (`?key=...`). When set, this is
    # tried before service-account JWT auth: it needs no signed token and works
    # for any project whose Vision API + billing are enabled for the key.
    google_vision_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GCP_VISION_API_KEY", "GOOGLE_VISION_API_KEY"),
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

    # CLARA Health Social platform (spec: .kiro/specs/clara-health-social).
    # Master flag defaults OFF: when off the /api/v1/social router returns 404
    # for every route and no social table is read/written, so baseline behavior
    # is byte-identical. Sub-flags gate feed personalization and AI assistance
    # independently; both are inert while the master flag is off.
    social_platform_enabled: bool = Field(
        default=False,
        validation_alias="SOCIAL_PLATFORM_ENABLED",
    )
    social_feed_personalization_enabled: bool = Field(
        default=False,
        validation_alias="SOCIAL_FEED_PERSONALIZATION_ENABLED",
    )
    social_ai_assist_enabled: bool = Field(
        default=False,
        validation_alias="SOCIAL_AI_ASSIST_ENABLED",
    )
    # Per-user write rate limit (posts+comments) per rolling minute.
    social_write_rate_per_minute: int = Field(
        default=8,
        validation_alias="SOCIAL_WRITE_RATE_PER_MINUTE",
        gt=0,
        le=120,
    )

    # --- Regulatory compliance (AI Law 134/2025 + PDPD 13/2023) feature flags ---
    # All additive + default OFF ⇒ byte-for-byte current behavior. When every
    # flag is off the compliance layer is inert (Requirement 8.1, 8.2).
    compliance_transparency_notice_enabled: bool = Field(
        default=False, validation_alias="COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED"
    )
    compliance_granular_consent_enabled: bool = Field(
        default=False, validation_alias="COMPLIANCE_GRANULAR_CONSENT_ENABLED"
    )
    compliance_dsar_enabled: bool = Field(default=False, validation_alias="COMPLIANCE_DSAR_ENABLED")
    compliance_cross_border_gating_enabled: bool = Field(
        default=False, validation_alias="COMPLIANCE_CROSS_BORDER_GATING_ENABLED"
    )
    compliance_retention_job_enabled: bool = Field(
        default=False, validation_alias="COMPLIANCE_RETENTION_JOB_ENABLED"
    )
    compliance_model_disclosure_enabled: bool = Field(
        default=False, validation_alias="COMPLIANCE_MODEL_DISCLOSURE_ENABLED"
    )
    compliance_records_admin_enabled: bool = Field(
        default=False, validation_alias="COMPLIANCE_RECORDS_ADMIN_ENABLED"
    )
    # Current AI transparency-notice version; bumping it forces re-acknowledgement
    # on next access (Requirement 1.6).
    compliance_transparency_notice_version: str = Field(
        default="2026-03-v1",
        validation_alias="COMPLIANCE_TRANSPARENCY_NOTICE_VERSION",
    )

    # --- Personal Health Record (enhanced) feature flags ------------------------
    # ``phr_enhanced_enabled`` is the master switch; every sub-flag is effective
    # only as ``master AND sub`` (see ``phr_features``). All default OFF ⇒ the
    # legacy PHR upsert/read path is untouched (Requirement 18.1).
    phr_enhanced_enabled: bool = Field(default=False, validation_alias="PHR_ENHANCED_ENABLED")
    phr_consent_enforcement_enabled: bool = Field(
        default=False, validation_alias="PHR_CONSENT_ENFORCEMENT_ENABLED"
    )
    phr_reconciliation_enabled: bool = Field(
        default=False, validation_alias="PHR_RECONCILIATION_ENABLED"
    )
    phr_allergy_aware_ddi_enabled: bool = Field(
        default=False, validation_alias="PHR_ALLERGY_AWARE_DDI_ENABLED"
    )
    phr_ocr_import_enabled: bool = Field(default=False, validation_alias="PHR_OCR_IMPORT_ENABLED")
    phr_observations_enabled: bool = Field(
        default=False, validation_alias="PHR_OBSERVATIONS_ENABLED"
    )
    phr_export_enabled: bool = Field(default=False, validation_alias="PHR_EXPORT_ENABLED")
    phr_sharing_enabled: bool = Field(default=False, validation_alias="PHR_SHARING_ENABLED")
    phr_reminders_enabled: bool = Field(default=False, validation_alias="PHR_REMINDERS_ENABLED")
    phr_completeness_meter_enabled: bool = Field(
        default=False, validation_alias="PHR_COMPLETENESS_METER_ENABLED"
    )

    # --- CLARA Research enhancement feature flags (additive; default off) --------
    # All flags default to the value that preserves current (legacy) behavior.
    # When every flag below is False/off, the research endpoints behave
    # identically to the pre-enhancement baseline (Requirement 20.2).
    research_api_gap_fill_hard_max: int = Field(
        default=3,
        validation_alias="RESEARCH_API_GAP_FILL_HARD_MAX",
        ge=1,
        le=10,
    )
    research_clarifying_questions_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_CLARIFYING_QUESTIONS_ENABLED",
    )
    research_role_gated_telemetry_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_ROLE_GATED_TELEMETRY_ENABLED",
    )
    research_personalization_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_PERSONALIZATION_ENABLED",
    )
    research_export_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_EXPORT_ENABLED",
    )
    research_share_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_SHARE_ENABLED",
    )
    research_quality_gate_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_QUALITY_GATE_ENABLED",
    )
    research_durable_uploads_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_DURABLE_UPLOADS_ENABLED",
    )
    research_upload_object_store_url: str = Field(
        default="",
        validation_alias="RESEARCH_UPLOAD_OBJECT_STORE_URL",
    )

    # --- Platform hardening feature flags (additive; default off/behavior-preserving) ---
    # Every flag below gates a new runtime behavior and defaults to the value that
    # preserves current behavior. With all HARDENING_* flags off the system is
    # equivalent to the pre-hardening baseline (Requirements 11.1, 11.2).
    hardening_refresh_rotation_enabled: bool = Field(
        default=False,
        validation_alias="HARDENING_REFRESH_ROTATION_ENABLED",
    )
    hardening_token_denylist_enabled: bool = Field(
        default=False,
        validation_alias="HARDENING_TOKEN_DENYLIST_ENABLED",
    )
    hardening_login_fail_closed: bool = Field(
        default=False,
        validation_alias="HARDENING_LOGIN_FAIL_CLOSED",
    )
    hardening_rate_limit_fail_closed: bool = Field(
        default=False,
        validation_alias="HARDENING_RATE_LIMIT_FAIL_CLOSED",
    )
    hardening_request_body_limit_enabled: bool = Field(
        default=False,
        validation_alias="HARDENING_REQUEST_BODY_LIMIT_ENABLED",
    )
    # Maximum request body size enforced only when the body-size limit is enabled.
    # The default (10 MiB) is inert while ``hardening_request_body_limit_enabled``
    # is off, preserving current behavior.
    hardening_request_body_max_bytes: int = Field(
        default=10_485_760,
        validation_alias="HARDENING_REQUEST_BODY_MAX_BYTES",
        gt=0,
    )
    hardening_readiness_probe_enabled: bool = Field(
        default=False,
        validation_alias="HARDENING_READINESS_PROBE_ENABLED",
    )
    hardening_circuit_breaker_enabled: bool = Field(
        default=False,
        validation_alias="HARDENING_CIRCUIT_BREAKER_ENABLED",
    )
    hardening_structured_logging_enabled: bool = Field(
        default=False,
        validation_alias="HARDENING_STRUCTURED_LOGGING_ENABLED",
    )
    hardening_csp_enabled: bool = Field(
        default=False,
        validation_alias="HARDENING_CSP_ENABLED",
    )

    # --- Self-Med + DDI + CareGuard upgrade feature flags ----------------------
    # All additive + default OFF ⇒ byte-for-byte current behavior. With every
    # flag below off, the cabinet API, the ML analysis payload, and the response
    # envelope are equivalent to the pre-upgrade baseline (Requirements 12.1,
    # 12.2). Existing flags (``CAREGUARD_DRUGBANK_ENABLED`` /
    # ``EXTERNAL_DDI_ENABLED`` in the ML config) remain the source of truth for
    # their respective behaviors and are intentionally not redefined here.
    selfmed_cabinet_structured_fields_enabled: bool = Field(
        default=False,
        validation_alias="SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED",
    )
    selfmed_expiry_reminders_enabled: bool = Field(
        default=False,
        validation_alias="SELFMED_EXPIRY_REMINDERS_ENABLED",
    )
    careguard_ddi_index_enabled: bool = Field(
        default=False,
        validation_alias="CAREGUARD_DDI_INDEX_ENABLED",
    )
    careguard_offline_fallback_enabled: bool = Field(
        default=False,
        validation_alias="CAREGUARD_OFFLINE_FALLBACK_ENABLED",
    )
    careguard_mobile_cabinet_enabled: bool = Field(
        default=False,
        validation_alias="CAREGUARD_MOBILE_CABINET_ENABLED",
    )
    careguard_observability_enabled: bool = Field(
        default=False,
        validation_alias="CAREGUARD_OBSERVABILITY_ENABLED",
    )

    # --- Admin & Observability upgrade feature flags ----------------------------
    # All additive + default OFF/empty ⇒ byte-for-byte current behavior. With
    # every flag below off, request/response shapes and side effects equal the
    # pre-feature baseline (Requirements 12.1, 12.2). Each flag gates one new
    # capability so the upgrade ships dark and can be enabled per environment.
    admin_rag_ingestion_controls_enabled: bool = Field(
        default=False,
        validation_alias="ADMIN_RAG_INGESTION_CONTROLS_ENABLED",
    )
    admin_observability_percentiles_enabled: bool = Field(
        default=False,
        validation_alias="ADMIN_OBSERVABILITY_PERCENTILES_ENABLED",
    )
    admin_observability_persistent_store_enabled: bool = Field(
        default=False,
        validation_alias="ADMIN_OBSERVABILITY_PERSISTENT_STORE_ENABLED",
    )
    admin_observability_alerting_enabled: bool = Field(
        default=False,
        validation_alias="ADMIN_OBSERVABILITY_ALERTING_ENABLED",
    )
    admin_observability_alert_webhook_url: str = Field(
        default="",
        validation_alias="ADMIN_OBSERVABILITY_ALERT_WEBHOOK_URL",
    )
    admin_audit_log_enabled: bool = Field(
        default=False,
        validation_alias="ADMIN_AUDIT_LOG_ENABLED",
    )

    # --- Council upgrade feature flags (additive; default OFF) ------------------
    # All additive + default OFF ⇒ byte-for-byte current behavior. With every
    # flag below off, the Council endpoints, the proxied ML run/intake output
    # shapes, the web wizard, and the response envelopes equal the pre-feature
    # baseline (Requirements 9.1, 9.2). Each flag gates exactly one new
    # capability so the upgrade ships dark and is enabled per environment in the
    # staged order documented in tasks.md.
    council_streaming_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_STREAMING_ENABLED",
    )
    council_run_history_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_RUN_HISTORY_ENABLED",
    )
    council_oversight_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_OVERSIGHT_ENABLED",
    )
    council_resilience_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_RESILIENCE_ENABLED",
    )
    council_model_disclosure_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_MODEL_DISCLOSURE_ENABLED",
    )
    council_observability_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_OBSERVABILITY_ENABLED",
    )
    council_mobile_parity_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_MOBILE_PARITY_ENABLED",
    )

    # Bounded retry/timeout policy knobs for the Council resilience wrapper
    # (task 5.1, Requirement 5.1, 5.2). These are inert while
    # ``council_resilience_enabled`` is off — the wrapper performs a single
    # attempt and preserves today's error mapping byte-for-byte (Requirement
    # 5.5). When the flag is on, the wrapper makes at most
    # ``council_resilience_max_attempts`` bounded attempts, sleeping an
    # exponential backoff (capped) between attempts, with each attempt carrying
    # ``council_resilience_timeout_seconds`` as its outbound timeout (``0`` ⇒
    # use the existing ``ml_service_timeout_seconds`` default, so the per-attempt
    # timeout is never weakened). The attempt count is hard-capped so a slow or
    # unavailable ML service can never retry without bound.
    council_resilience_max_attempts: int = Field(
        default=3,
        validation_alias="COUNCIL_RESILIENCE_MAX_ATTEMPTS",
        ge=1,
        le=10,
    )
    council_resilience_backoff_base_seconds: float = Field(
        default=0.25,
        validation_alias="COUNCIL_RESILIENCE_BACKOFF_BASE_SECONDS",
        ge=0,
    )
    council_resilience_backoff_max_seconds: float = Field(
        default=2.0,
        validation_alias="COUNCIL_RESILIENCE_BACKOFF_MAX_SECONDS",
        ge=0,
    )
    council_resilience_timeout_seconds: float = Field(
        default=0.0,
        validation_alias="COUNCIL_RESILIENCE_TIMEOUT_SECONDS",
        ge=0,
    )

    # --- LifeMap transactional-outbox relay (Phase 0, P0-WP5) -----------------
    # LifeMap command handlers durably write integration events into
    # ``lifemap_outbox_events`` alongside each mutation, but nothing drained the
    # ``pending`` rows. The relay now runs only as the dedicated
    # ``python -m clara_api.lifemap.worker`` process; the legacy flag remains as
    # a compatibility setting but never starts a thread inside an API replica.
    lifemap_outbox_relay_enabled: bool = Field(
        default=False,
        validation_alias="LIFEMAP_OUTBOX_RELAY_ENABLED",
    )
    lifemap_outbox_relay_interval_seconds: float = Field(
        default=5.0,
        validation_alias="LIFEMAP_OUTBOX_RELAY_INTERVAL_SECONDS",
        gt=0,
    )
    lifemap_outbox_relay_batch_size: int = Field(
        default=100,
        validation_alias="LIFEMAP_OUTBOX_RELAY_BATCH_SIZE",
        gt=0,
        le=1000,
    )
    lifemap_outbox_lease_seconds: float = Field(
        default=60.0,
        validation_alias="LIFEMAP_OUTBOX_LEASE_SECONDS",
        ge=5.0,
        le=3600.0,
    )
    lifemap_outbox_backoff_seconds: float = Field(
        default=1.0,
        validation_alias="LIFEMAP_OUTBOX_BACKOFF_SECONDS",
        ge=0.0,
        le=300.0,
    )
    lifemap_worker_health_port: int = Field(
        default=8020,
        validation_alias="LIFEMAP_WORKER_HEALTH_PORT",
        ge=1,
        le=65535,
    )

    # --- LifeMap V2 staged rollout -----------------------------------------
    # Server-authoritative and fail-closed. Clients may hide unavailable
    # surfaces from capability responses but cannot enable any behavior.
    lifemap_v2_enabled: bool = Field(default=False, validation_alias="LIFEMAP_V2_ENABLED")
    lifemap_capture_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_CAPTURE_ENABLED"
    )
    lifemap_baselines_v2_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_BASELINES_V2_ENABLED"
    )
    lifemap_next_question_v2_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_NEXT_QUESTION_V2_ENABLED"
    )
    lifemap_replay_v2_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_REPLAY_V2_ENABLED"
    )
    lifemap_visit_extraction_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_VISIT_EXTRACTION_ENABLED"
    )
    lifemap_evidence_monitor_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_EVIDENCE_MONITOR_ENABLED"
    )
    lifemap_fhir_export_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_FHIR_EXPORT_ENABLED"
    )
    lifemap_ask_ai_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_ASK_AI_ENABLED"
    )
    lifemap_ai_summaries_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_AI_SUMMARIES_ENABLED"
    )
    lifemap_ai_entity_resolution_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_AI_ENTITY_RESOLUTION_ENABLED"
    )
    lifemap_ai_review_findings_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_AI_REVIEW_FINDINGS_ENABLED"
    )
    lifemap_ai_pattern_shadow_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_AI_PATTERN_SHADOW_ENABLED"
    )
    lifemap_ai_forecast_shadow_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_AI_FORECAST_SHADOW_ENABLED"
    )
    lifemap_ai_question_ranker_shadow_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_AI_QUESTION_RANKER_SHADOW_ENABLED"
    )
    lifemap_ai_evidence_matching_enabled: bool = Field(
        default=False, validation_alias="LIFEMAP_AI_EVIDENCE_MATCHING_ENABLED"
    )

    # --- LifeMap next-best-question engine (Phase 2, P2-WP5) --------------------
    # Additive + default OFF ⇒ the endpoint returns the feature-disabled (404)
    # shape and no question is ever generated, preserving prior behavior. When
    # on, the engine deterministically proposes at most one highest-value
    # question (or none) from an episode's typed missing critical fields, subject
    # to a per-episode burden budget. Flipping it off at runtime cleanly stops
    # question generation with no data change.
    lifemap_next_question_enabled: bool = Field(
        default=False,
        validation_alias="LIFEMAP_NEXT_QUESTION_ENABLED",
    )
    lifemap_next_question_burden_budget: int = Field(
        default=3,
        validation_alias="LIFEMAP_NEXT_QUESTION_BURDEN_BUDGET",
        gt=0,
        le=20,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
