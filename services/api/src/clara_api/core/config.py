from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CLARA API"
    environment: str = "development"
    debug: bool = True

    database_url: str = Field(
        default="sqlite+pysqlite:///./clara.db",
        validation_alias="DATABASE_URL",
    )

    jwt_secret_key: str = Field(default="change-me", min_length=8, validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = Field(default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_minutes: int = Field(default=43200, validation_alias="REFRESH_TOKEN_EXPIRE_MINUTES")
    auth_auto_provision_users: bool = Field(default=True, validation_alias="AUTH_AUTO_PROVISION_USERS")
    auth_require_email_verification: bool = Field(
        default=False,
        validation_alias="AUTH_REQUIRE_EMAIL_VERIFICATION",
    )
    auth_action_token_ttl_minutes: int = Field(
        default=30,
        validation_alias="AUTH_ACTION_TOKEN_TTL_MINUTES",
        gt=0,
    )

    rate_limit_requests: int = Field(default=120, validation_alias="GLOBAL_RATE_LIMIT_PER_MIN")
    rate_limit_window_seconds: int = Field(default=60, validation_alias="RATE_LIMIT_WINDOW_SECONDS")
    pubmed_rate_limit_per_sec: int = Field(default=10, validation_alias="PUBMED_RATE_LIMIT_PER_SEC")
    ml_service_url: str = Field(default="http://localhost:8110", validation_alias="ML_SERVICE_URL")
    ml_service_timeout_seconds: float = Field(
        default=20.0,
        validation_alias="ML_SERVICE_TIMEOUT_SECONDS",
        gt=0,
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
