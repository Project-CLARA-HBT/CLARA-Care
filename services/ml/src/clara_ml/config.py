from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "clara-ml"
    environment: str = "development"
    default_embedder: str = "bge-m3"
    embedding_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "EMBEDDING_API_KEY",
            "RAG_EMBEDDING_API_KEY",
            "YESCALE_API_KEY",
        ),
    )
    embedding_base_url: str = Field(
        default="https://api.yescale.io/v1",
        validation_alias=AliasChoices("EMBEDDING_BASE_URL", "RAG_EMBEDDING_BASE_URL"),
    )
    embedding_model: str = Field(
        default="text-embedding-3-large",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "RAG_EMBEDDING_MODEL"),
    )
    embedding_timeout_seconds: float = Field(
        default=6.0,
        validation_alias=AliasChoices(
            "EMBEDDING_TIMEOUT_SECONDS",
            "RAG_EMBEDDING_TIMEOUT_SECONDS",
        ),
    )
    deepseek_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "DEEPSEEK_API_KEY",
            "YESCALE_API_KEY",
            "EMBEDDING_API_KEY",
        ),
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias="DEEPSEEK_BASE_URL",
    )
    deepseek_model: str = Field(default="deepseek-v3.2", validation_alias="DEEPSEEK_MODEL")
    deepseek_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("DEEPSEEK_TIMEOUT_SECONDS", "DEEPSEEK_TIMEOUT"),
    )
    external_ddi_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("EXTERNAL_DDI_ENABLED", "CAREGUARD_EXTERNAL_DDI_ENABLED"),
    )
    external_ddi_timeout_seconds: float = Field(
        default=1.5,
        validation_alias=AliasChoices(
            "EXTERNAL_DDI_TIMEOUT_SECONDS", "CAREGUARD_EXTERNAL_DDI_TIMEOUT_SECONDS"
        ),
    )
    pubmed_connector_timeout_seconds: float = Field(
        default=4.0,
        validation_alias=AliasChoices(
            "PUBMED_CONNECTOR_TIMEOUT_SECONDS", "RAG_EXTERNAL_TIMEOUT_SECONDS"
        ),
    )
    pubmed_esearch_max_results: int = Field(
        default=3,
        validation_alias="PUBMED_ESEARCH_MAX_RESULTS",
        ge=1,
        le=10,
    )
    europe_pmc_max_results: int = Field(
        default=3,
        validation_alias="EUROPE_PMC_MAX_RESULTS",
        ge=1,
        le=10,
    )
    rag_external_connectors_enabled: bool = Field(
        default=True,
        validation_alias="RAG_EXTERNAL_CONNECTORS_ENABLED",
    )
    rag_force_search_index: bool = Field(
        default=True,
        validation_alias="RAG_FORCE_SEARCH_INDEX",
    )
    searxng_base_url: str = Field(
        default="",
        validation_alias="SEARXNG_BASE_URL",
    )
    searxng_timeout_seconds: float = Field(
        default=3.0,
        validation_alias="SEARXNG_TIMEOUT_SECONDS",
    )
    searxng_crawl_enabled: bool = Field(
        default=True,
        validation_alias="SEARXNG_CRAWL_ENABLED",
    )
    searxng_crawl_top_k: int = Field(
        default=2,
        validation_alias="SEARXNG_CRAWL_TOP_K",
        ge=0,
        le=8,
    )
    searxng_crawl_timeout_seconds: float = Field(
        default=2.0,
        validation_alias="SEARXNG_CRAWL_TIMEOUT_SECONDS",
    )
    searxng_crawl_allowed_domains: str = Field(
        default="",
        validation_alias="SEARXNG_CRAWL_ALLOWED_DOMAINS",
    )
    semantic_scholar_timeout_seconds: float = Field(
        default=3.0,
        validation_alias="SEMANTIC_SCHOLAR_TIMEOUT_SECONDS",
    )
    semantic_scholar_max_results: int = Field(
        default=3,
        validation_alias="SEMANTIC_SCHOLAR_MAX_RESULTS",
        ge=1,
        le=20,
    )
    web_crawl_enabled: bool = Field(
        default=True,
        validation_alias="WEB_CRAWL_ENABLED",
    )
    web_crawl_timeout_seconds: float = Field(
        default=1.5,
        validation_alias="WEB_CRAWL_TIMEOUT_SECONDS",
    )
    web_crawl_max_pages: int = Field(
        default=3,
        validation_alias="WEB_CRAWL_MAX_PAGES",
        ge=1,
        le=10,
    )
    web_crawl_max_chars: int = Field(
        default=1200,
        validation_alias="WEB_CRAWL_MAX_CHARS",
        ge=300,
        le=8000,
    )
    web_crawl_allowed_domains: str = Field(
        default=(
            "who.int,nih.gov,ncbi.nlm.nih.gov,pubmed.ncbi.nlm.nih.gov,"
            "open.fda.gov,fda.gov,dailymed.nlm.nih.gov,"
            "clinicaltrials.gov,ema.europa.eu,bmj.com,thelancet.com"
        ),
        validation_alias="WEB_CRAWL_ALLOWED_DOMAINS",
    )
    evidence_search_enforced: bool = Field(
        default=True,
        validation_alias="EVIDENCE_SEARCH_ENFORCED",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
