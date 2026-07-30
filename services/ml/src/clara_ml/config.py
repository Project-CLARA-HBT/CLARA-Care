import logging

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

#: Hard ceiling for the deep_beta report word budget. The scope-aware band
#: (task 3.1) resolves ``target`` inside ``[min_words, max_words]``; this is the
#: absolute upper bound that ``max_words`` — and therefore ``target`` — can
#: never exceed (Requirement 1.4, 6.5; design Correctness Property P1).
DEEP_BETA_REPORT_HARD_MAX_WORDS = 15000


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
    # Bounded retries for a single embedding HTTP request. The upstream provider
    # (yescale) exhibits bimodal latency: a request either returns in ~1-2s or
    # hangs until the read timeout. Retrying a hung/failed request with a short
    # per-attempt timeout recovers the vast majority of these without persisting
    # a degraded vector. 0 disables retries (single attempt).
    # Hard upper bound on records the admin-triggered ingestion may process in a
    # single run, so the manual control surface can never run away and exhaust
    # disk on the shared host (the scheduler/orchestrator loop is otherwise
    # unbounded). Applies per source per admin trigger.
    rag_admin_ingest_max_records: int = Field(
        default=200,
        validation_alias=AliasChoices(
            "RAG_ADMIN_INGEST_MAX_RECORDS",
            "RAG_ADMIN_INGEST_CAP",
        ),
    )
    embedding_max_retries: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "EMBEDDING_MAX_RETRIES",
            "RAG_EMBEDDING_MAX_RETRIES",
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
    llm_deepseek_only: bool = Field(
        default=True,
        validation_alias="LLM_DEEPSEEK_ONLY",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias="DEEPSEEK_BASE_URL",
    )
    # Legacy/global DeepSeek model used when task routing is explicitly disabled.
    # New deployments route registered tasks between the two governed V4 models
    # below; neither value is ever sourced from an end-user request.
    deepseek_model: str = Field(default="deepseek-v4-pro", validation_alias="DEEPSEEK_MODEL")
    deepseek_pro_model: str = Field(
        default="deepseek-v4-pro",
        validation_alias="DEEPSEEK_PRO_MODEL",
    )
    deepseek_flash_model: str = Field(
        default="deepseek-v4-flash",
        validation_alias="DEEPSEEK_FLASH_MODEL",
    )
    deepseek_fallback_model: str = Field(
        # Secondary model tried when the primary model fails across all bases
        # (e.g. upstream 5xx / "temporarily unavailable"). Empty disables the
        # fallback so behavior is byte-for-byte the single-model path.
        default="",
        validation_alias="DEEPSEEK_FALLBACK_MODEL",
    )
    deepseek_required: bool = Field(
        default=False,
        validation_alias="DEEPSEEK_REQUIRED",
    )
    # Registry is a typed selection layer around the existing DeepSeek client,
    # not a user-selectable provider switch.  Defaults preserve the deployed
    # model; the rollback switch can only select an explicitly configured prior
    # DeepSeek model and is safe to turn off immediately during an incident.
    model_registry_enabled: bool = Field(
        default=True,
        validation_alias="MODEL_REGISTRY_ENABLED",
    )
    model_registry_task_model_routing_enabled: bool = Field(
        default=True,
        validation_alias="MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED",
    )
    # The semantic intent proposal is generated through the governed
    # MEDICAL_SAFETY_ROUTER contract. Emergency/legal deterministic guards stay
    # authoritative; this switch restores the legacy keyword intent path
    # immediately if a semantic routing incident is observed.
    semantic_intent_routing_enabled: bool = Field(
        default=True,
        validation_alias="SEMANTIC_INTENT_ROUTING_ENABLED",
    )
    model_registry_force_rollback: bool = Field(
        default=False,
        validation_alias="MODEL_REGISTRY_FORCE_ROLLBACK",
    )
    model_registry_rollback_model: str = Field(
        default="",
        validation_alias="MODEL_REGISTRY_ROLLBACK_MODEL",
    )
    # Optional external Encoder-SLM router.  This is strictly a shadow signal:
    # it is disabled by default and must never replace deterministic emergency,
    # legal, authorization, DrugBank, or state-transition decisions.
    encoder_slm_shadow_enabled: bool = Field(
        default=False,
        validation_alias="ENCODER_SLM_SHADOW_ENABLED",
    )
    encoder_slm_shadow_url: str = Field(
        default="",
        validation_alias="ENCODER_SLM_SHADOW_URL",
    )
    encoder_slm_shadow_api_key: str = Field(
        default="",
        validation_alias="ENCODER_SLM_SHADOW_API_KEY",
    )
    encoder_slm_shadow_model_id: str = Field(
        default="",
        validation_alias="ENCODER_SLM_SHADOW_MODEL_ID",
    )
    encoder_slm_shadow_timeout_ms: int = Field(
        default=750,
        validation_alias="ENCODER_SLM_SHADOW_TIMEOUT_MS",
        ge=100,
        le=5000,
    )
    encoder_slm_shadow_max_input_chars: int = Field(
        default=1200,
        validation_alias="ENCODER_SLM_SHADOW_MAX_INPUT_CHARS",
        ge=64,
        le=4000,
    )
    chat_llm_query_planner_enabled: bool = Field(
        # When true, plain chat (routed_chat_infer) runs the same LLM query
        # planner used by research tier2 to refine the raw query into a smaller
        # keyword set and concise per-source / per-provider queries before
        # retrieval. Fail-soft: any planner error falls back to the heuristic
        # base plan, so retrieval behavior is never worse than before. Kill
        # switch defaults on; set to false to restore the pure-heuristic path.
        default=True,
        validation_alias="CHAT_LLM_QUERY_PLANNER_ENABLED",
    )
    deepseek_timeout_seconds: float = Field(
        default=45.0,
        validation_alias=AliasChoices("DEEPSEEK_TIMEOUT_SECONDS", "DEEPSEEK_TIMEOUT"),
    )
    llm_global_max_concurrency: int = Field(
        default=2,
        validation_alias=AliasChoices(
            "LLM_GLOBAL_MAX_CONCURRENCY",
            "DEEPSEEK_MAX_CONCURRENCY",
        ),
        ge=1,
        le=16,
    )
    llm_global_min_interval_seconds: float = Field(
        default=0.4,
        validation_alias=AliasChoices(
            "LLM_GLOBAL_MIN_INTERVAL_SECONDS",
            "DEEPSEEK_MIN_INTERVAL_SECONDS",
        ),
        ge=0.0,
        le=10.0,
    )
    llm_global_jitter_seconds: float = Field(
        default=0.15,
        validation_alias=AliasChoices(
            "LLM_GLOBAL_JITTER_SECONDS",
            "DEEPSEEK_JITTER_SECONDS",
        ),
        ge=0.0,
        le=5.0,
    )
    deep_beta_pass_cap: int = Field(
        default=24,
        validation_alias="DEEP_BETA_PASS_CAP",
        ge=6,
        le=64,
    )
    deep_beta_reasoning_llm_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "DEEP_BETA_REASONING_LLM_ENABLED",
            "DEEP_BETA_LLM_REASONING_ENABLED",
        ),
    )
    deep_beta_reasoning_llm_nodes: int = Field(
        default=4,
        validation_alias="DEEP_BETA_REASONING_LLM_NODES",
        ge=1,
        le=16,
    )
    deep_beta_reasoning_llm_timeout_seconds: float = Field(
        default=12.0,
        validation_alias=AliasChoices(
            "DEEP_BETA_REASONING_LLM_TIMEOUT_SECONDS",
            "DEEP_BETA_LLM_REASONING_TIMEOUT_SECONDS",
        ),
        ge=2.0,
        le=120.0,
    )
    deep_beta_reasoning_parallel_workers: int = Field(
        default=3,
        validation_alias="DEEP_BETA_REASONING_PARALLEL_WORKERS",
        ge=1,
        le=8,
    )
    deep_beta_reasoning_rounds: int = Field(
        default=1,
        validation_alias="DEEP_BETA_REASONING_ROUNDS",
        ge=1,
        le=4,
    )
    deep_beta_gap_fill_max_passes: int = Field(
        default=2,
        validation_alias="DEEP_BETA_GAP_FILL_MAX_PASSES",
        ge=0,
        le=8,
    )
    deep_beta_gap_fill_max_queries: int = Field(
        default=6,
        validation_alias="DEEP_BETA_GAP_FILL_MAX_QUERIES",
        ge=1,
        le=24,
    )
    # Master flag for CLARA Pro answer-synthesis v2 (scope-aware budget,
    # de-templating, robust convergence). Default OFF preserves pre-feature
    # behavior so the work ships dark and is enabled per environment.
    synthesis_v2_enabled: bool = Field(
        default=False,
        validation_alias="SYNTHESIS_V2_ENABLED",
    )
    deep_beta_report_llm_enabled: bool = Field(
        default=True,
        validation_alias="DEEP_BETA_REPORT_LLM_ENABLED",
    )
    # When true (default), CLARA Pro (deep_beta) writes a natural, reader-first
    # explanatory answer in a single language at whatever length the content
    # warrants, and NEVER pads the answer body with telemetry (multi-pass logs,
    # reasoning-node matrices, claim-status/confusion matrices, source-profile
    # tables). That technical material still flows in the response envelope
    # (verification_matrix / citations / reasoning_steps / parallel_reasoning_
    # nodes) so web + mobile can render it in a hidden-by-default telemetry
    # panel. Set to false to restore the legacy dossier-with-appendix body.
    deep_beta_clean_body_enabled: bool = Field(
        default=True,
        validation_alias="DEEP_BETA_CLEAN_BODY_ENABLED",
    )
    # Natural (non-padded) length band for the clean-body Pro answer. Used only
    # when ``deep_beta_clean_body_enabled`` is true; the answer is guided to a
    # readable long-form length instead of the 8,000-15,000 word dossier target,
    # so it explains thoroughly without "padding to be long".
    deep_beta_clean_body_min_words: int = Field(
        default=500,
        validation_alias="DEEP_BETA_CLEAN_BODY_MIN_WORDS",
        ge=200,
        le=4000,
    )
    deep_beta_clean_body_target_words: int = Field(
        default=1100,
        validation_alias="DEEP_BETA_CLEAN_BODY_TARGET_WORDS",
        ge=300,
        le=6000,
    )
    deep_beta_clean_body_max_words: int = Field(
        default=2200,
        validation_alias="DEEP_BETA_CLEAN_BODY_MAX_WORDS",
        ge=500,
        le=8000,
    )
    # deep_beta report length floor for the LEGACY dossier/synthesis-v2 band.
    # Under the clean-body Pro default this floor is no longer used for the answer
    # length (clean-body uses its own natural band), and the legacy scope-aware
    # The synthesis-v2 budget contract is 4000..12000 words.  The legacy
    # resolver may use a lower internal fallback for historical requests, but a
    # configured synthesis report floor below 4000 is invalid rather than an
    # implicit latency tuning knob.
    deep_beta_report_min_words: int = Field(
        default=8000,
        validation_alias=AliasChoices(
            "DEEP_BETA_REPORT_MIN_WORDS",
            "DEEP_BETA_REPORT_MIN_CHARS",
        ),
        ge=4000,
        le=12000,
    )
    # Hard ceiling for the scope-aware budget band. Never exceeds 15000 words.
    # The lower static bound (6000) covers the smallest floor+2000 case; the
    # cross-field ``min <= target <= max <= 15000`` invariant is enforced
    # separately by config-bounds validation (task 1.2 / Requirement 6.5).
    deep_beta_report_max_words_cap: int = Field(
        default=15000,
        validation_alias=AliasChoices(
            "DEEP_BETA_REPORT_MAX_WORDS_CAP",
            "DEEP_BETA_REPORT_MAX_WORDS",
        ),
        ge=6000,
        le=15000,
    )
    deep_beta_report_target_pages: int = Field(
        default=28,
        validation_alias="DEEP_BETA_REPORT_TARGET_PAGES",
        ge=1,
        le=120,
    )
    deep_beta_report_words_per_page: int = Field(
        default=340,
        validation_alias="DEEP_BETA_REPORT_WORDS_PER_PAGE",
        ge=200,
        le=1000,
    )
    deep_beta_report_expansion_rounds: int = Field(
        default=4,
        validation_alias="DEEP_BETA_REPORT_EXPANSION_ROUNDS",
        ge=0,
        le=10,
    )
    deep_beta_report_timeout_seconds: float = Field(
        default=90.0,
        validation_alias="DEEP_BETA_REPORT_TIMEOUT_SECONDS",
        ge=10.0,
        le=600.0,
    )
    deep_beta_report_max_tokens: int = Field(
        default=8192,
        validation_alias="DEEP_BETA_REPORT_MAX_TOKENS",
        ge=1024,
        le=32768,
    )
    deep_beta_quality_gate_enabled: bool = Field(
        default=True,
        validation_alias="DEEP_BETA_QUALITY_GATE_ENABLED",
    )
    deep_beta_quality_gate_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="DEEP_BETA_QUALITY_GATE_TIMEOUT_SECONDS",
        ge=2.0,
        le=120.0,
    )
    deep_beta_evidence_verification_enabled: bool = Field(
        default=True,
        validation_alias="DEEP_BETA_EVIDENCE_VERIFICATION_ENABLED",
    )
    deep_beta_evidence_verification_timeout_seconds: float = Field(
        default=12.0,
        validation_alias="DEEP_BETA_EVIDENCE_VERIFICATION_TIMEOUT_SECONDS",
        ge=2.0,
        le=120.0,
    )
    deepseek_retries_per_base: int = Field(
        default=2,
        validation_alias="DEEPSEEK_RETRIES_PER_BASE",
        ge=0,
        le=5,
    )
    deepseek_retry_backoff_seconds: float = Field(
        default=0.9,
        validation_alias="DEEPSEEK_RETRY_BACKOFF_SECONDS",
        ge=0.0,
        le=5.0,
    )
    deepseek_audio_model: str = Field(
        default="whisper-1",
        validation_alias=AliasChoices(
            "DEEPSEEK_AUDIO_MODEL",
            "DEEPSEEK_TRANSCRIBE_MODEL",
            "DEEPSEEK_AUDIO_TRANSCRIPTION_MODEL",
        ),
    )
    deepseek_audio_language: str = Field(
        default="vi",
        validation_alias=AliasChoices("DEEPSEEK_AUDIO_LANGUAGE", "DEEPSEEK_TRANSCRIBE_LANGUAGE"),
    )
    deepseek_audio_base_url: str = Field(
        # Base URL riêng cho audio/transcriptions (vd Whisper local adapter);
        # rỗng → dùng chung DEEPSEEK_BASE_URL như trước.
        default="",
        validation_alias=AliasChoices("DEEPSEEK_AUDIO_BASE_URL", "WHISPER_BASE_URL"),
    )
    ml_internal_api_key: str = Field(
        default="",
        validation_alias="ML_INTERNAL_API_KEY",
    )
    external_ddi_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("EXTERNAL_DDI_ENABLED", "CAREGUARD_EXTERNAL_DDI_ENABLED"),
    )
    # CareGuard optional DrugBank shard layer. Default OFF.
    #
    # WARNING (memory): the current loader (``agents/careguard._resolve_ddi_rules``)
    # merges the DrugBank shards fully IN MEMORY. The full shard set is ~1.4M
    # interaction pairs and needs ~1.26 GB RSS once indexed. On a small host
    # (e.g. the current deploy has <1 GB free) enabling this OOMs the ML
    # container. Keep OFF until the loader is migrated to the on-disk SQLite
    # pair-index (see ``scripts/data/drugbank_ingest.py`` follow-up: ~260 MB on
    # disk, ~33 ms/lookup, constant memory), then this can default ON safely.
    # Self-degrading: when the shards are absent/unparseable the resolver falls
    # back to curated-only.
    careguard_drugbank_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("CAREGUARD_DRUGBANK_ENABLED"),
    )
    # Pair-indexed DDI matcher (Self-Med + CareGuard upgrade). Default OFF keeps
    # the existing linear ``issubset`` scan in ``agents/careguard`` so output is
    # byte-identical to the pre-upgrade baseline; when on, the matcher uses a
    # ``dict[frozenset[str], list[InteractionRule]]`` index cached by rule-set
    # version/mtime (Requirement 5.4, 12.1, 12.2).
    careguard_ddi_index_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("CAREGUARD_DDI_INDEX_ENABLED"),
    )
    # Memory-safe DrugBank DDI layer via an on-disk SQLite pair index. Default ON.
    #
    # This is the production-safe alternative to the in-memory
    # ``careguard_drugbank_enabled`` merge: instead of loading ~1.4M interaction
    # pairs into RAM (~1.26 GB RSS), the DrugBank shards are compiled ONCE into a
    # SQLite database (~260 MB on disk) and each analysis does an indexed lookup
    # for only the handful of medication pairs it actually needs (~30 ms,
    # constant memory). Curated Vietnamese rules still win on any conflicting
    # pair. Fully self-degrading: when the shards/DB are absent or unbuildable,
    # CareGuard transparently falls back to the curated-only in-memory path, so
    # enabling by default is safe even in builds that ship without the shards.
    # When both this and ``careguard_drugbank_enabled`` are on, the SQLite path
    # takes precedence (the in-memory merge is skipped) to avoid the OOM risk.
    careguard_drugbank_sqlite_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("CAREGUARD_DRUGBANK_SQLITE_ENABLED"),
    )
    # Clinical deployments may require the licensed DrugBank SQLite index as
    # the only source of drug-drug interaction conclusions. When enabled, an
    # unavailable/degraded/disabled index fails closed: local curated rules and
    # external DDI services are not used as substitutes. Non-DDI checks such as
    # declared-allergy conflicts, emergency symptoms, and lab-risk flags still
    # run and remain visible.
    careguard_drugbank_required: bool = Field(
        default=False,
        validation_alias=AliasChoices("CAREGUARD_DRUGBANK_REQUIRED"),
    )
    # Integrity is deliberately independent from ``careguard_drugbank_required``:
    # a deployment may use curated rules while staging a licensed DrugBank
    # artifact, but it must never silently trust a changed/incomplete artifact.
    # Set this to false only as a short-lived, audited rollback for a verified
    # legacy artifact; strict clinical deployments should pair it with
    # ``CAREGUARD_DRUGBANK_REQUIRED=true``.
    careguard_drugbank_manifest_integrity_required: bool = Field(
        default=True,
        validation_alias=AliasChoices("CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED"),
    )
    # Container-visible paths for a licensed DrugBank artifact bundle. Empty
    # values retain the small development bundle location in the ML package.
    # Production mounts the licensed manifest/shards and its prebuilt SQLite
    # index outside the image; the CareGuard store resolves these paths once at
    # startup and never exposes them in health responses or telemetry.
    careguard_drugbank_manifest_path: str = Field(
        default="",
        validation_alias=AliasChoices("CAREGUARD_DRUGBANK_MANIFEST_PATH"),
    )
    careguard_drugbank_sqlite_path: str = Field(
        default="",
        validation_alias=AliasChoices("CAREGUARD_DRUGBANK_SQLITE_PATH"),
    )
    # Additive consumer wording projection of an already-final CareGuard result.
    # It is intentionally OFF by default: the renderer never queries, changes,
    # or substitutes for the authoritative DrugBank decision path.
    careguard_wording_renderer_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("CAREGUARD_WORDING_RENDERER_ENABLED"),
    )
    external_ddi_timeout_seconds: float = Field(
        default=1.5,
        validation_alias=AliasChoices(
            "EXTERNAL_DDI_TIMEOUT_SECONDS", "CAREGUARD_EXTERNAL_DDI_TIMEOUT_SECONDS"
        ),
    )
    openfda_label_alerts_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "OPENFDA_LABEL_ALERTS_ENABLED", "CAREGUARD_OPENFDA_LABEL_ALERTS_ENABLED"
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
    rag_external_parallel_workers: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "RAG_EXTERNAL_PARALLEL_WORKERS",
            "RAG_EXTERNAL_MAX_PARALLEL",
        ),
        ge=1,
        le=16,
    )
    rag_external_min_interval_seconds: float = Field(
        default=0.2,
        validation_alias=AliasChoices(
            "RAG_EXTERNAL_MIN_INTERVAL_SECONDS",
            "RAG_EXTERNAL_THROTTLE_SECONDS",
        ),
        ge=0.0,
        le=5.0,
    )
    rag_external_jitter_seconds: float = Field(
        default=0.1,
        validation_alias=AliasChoices(
            "RAG_EXTERNAL_JITTER_SECONDS",
            "RAG_EXTERNAL_THROTTLE_JITTER_SECONDS",
        ),
        ge=0.0,
        le=2.0,
    )
    research_inter_step_pause_seconds: float = Field(
        default=0.35,
        validation_alias=AliasChoices(
            "RESEARCH_INTER_STEP_PAUSE_SECONDS",
            "RESEARCH_STAGE_PAUSE_SECONDS",
        ),
        ge=0.0,
        le=10.0,
    )
    research_inter_step_jitter_seconds: float = Field(
        default=0.15,
        validation_alias=AliasChoices(
            "RESEARCH_INTER_STEP_JITTER_SECONDS",
            "RESEARCH_STAGE_PAUSE_JITTER_SECONDS",
        ),
        ge=0.0,
        le=3.0,
    )
    rag_graphrag_enabled: bool = Field(
        default=False,
        validation_alias="RAG_GRAPHRAG_ENABLED",
    )
    rag_graphrag_max_neighbors: int = Field(
        default=8,
        validation_alias="RAG_GRAPHRAG_MAX_NEIGHBORS",
        ge=1,
        le=32,
    )
    rag_graphrag_expansion_docs: int = Field(
        default=4,
        validation_alias="RAG_GRAPHRAG_EXPANSION_DOCS",
        ge=1,
        le=16,
    )
    rag_biomed_graph_enabled: bool = Field(
        default=True,
        validation_alias="RAG_BIOMED_GRAPH_ENABLED",
    )
    rag_biomed_graph_path: str = Field(
        default="",
        validation_alias="RAG_BIOMED_GRAPH_PATH",
    )
    rag_biomed_graph_max_edges: int = Field(
        default=12,
        validation_alias="RAG_BIOMED_GRAPH_MAX_EDGES",
        ge=1,
        le=64,
    )
    rag_force_search_index: bool = Field(
        default=True,
        validation_alias="RAG_FORCE_SEARCH_INDEX",
    )
    searxng_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("SEARXNG_BASE_URL", "SEARXNG_PUBLIC_BASE_URL"),
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
        default=(
            "who.int,nih.gov,ncbi.nlm.nih.gov,pubmed.ncbi.nlm.nih.gov,"
            "open.fda.gov,fda.gov,dailymed.nlm.nih.gov,"
            "clinicaltrials.gov,ema.europa.eu,bmj.com,thelancet.com"
        ),
        validation_alias="SEARXNG_CRAWL_ALLOWED_DOMAINS",
    )
    semantic_scholar_timeout_seconds: float = Field(
        default=3.0,
        validation_alias="SEMANTIC_SCHOLAR_TIMEOUT_SECONDS",
    )
    semantic_scholar_api_key: str = Field(
        default="",
        validation_alias="SEMANTIC_SCHOLAR_API_KEY",
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
    otel_export_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("OTEL_EXPORT_ENABLED", "CLARA_OTEL_EXPORT_ENABLED"),
    )
    otel_export_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OTEL_EXPORT_ENDPOINT",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "CLARA_OTEL_EXPORT_ENDPOINT",
        ),
    )
    otel_export_timeout_seconds: float = Field(
        default=1.5,
        validation_alias=AliasChoices(
            "OTEL_EXPORT_TIMEOUT_SECONDS",
            "CLARA_OTEL_EXPORT_TIMEOUT_SECONDS",
        ),
        ge=0.1,
        le=10.0,
    )
    rag_biomedical_rerank_enabled: bool = Field(
        default=False,
        validation_alias="RAG_BIOMEDICAL_RERANK_ENABLED",
    )
    rag_reranker_enabled: bool = Field(
        default=False,
        validation_alias="RAG_RERANKER_ENABLED",
    )
    rag_reranker_strategy: str = Field(
        default="embedding",
        validation_alias="RAG_RERANKER_STRATEGY",
    )
    rag_reranker_model: str = Field(
        default="embedding-cosine-reranker-v1",
        validation_alias="RAG_RERANKER_MODEL",
    )
    rag_reranker_top_n: int = Field(
        default=12,
        validation_alias="RAG_RERANKER_TOP_N",
        ge=1,
        le=128,
    )
    rag_reranker_timeout_ms: int = Field(
        default=250,
        validation_alias="RAG_RERANKER_TIMEOUT_MS",
        ge=50,
        le=30000,
    )
    rag_reranker_llm_enabled: bool = Field(
        default=False,
        validation_alias="RAG_RERANKER_LLM_ENABLED",
    )
    rag_reranker_llm_top_n: int = Field(
        default=6,
        validation_alias="RAG_RERANKER_LLM_TOP_N",
        ge=1,
        le=24,
    )
    rag_reranker_llm_min_score: float = Field(
        default=0.55,
        validation_alias="RAG_RERANKER_LLM_MIN_SCORE",
        ge=0.0,
        le=1.0,
    )
    rag_reranker_llm_timeout_ms: int = Field(
        default=900,
        validation_alias="RAG_RERANKER_LLM_TIMEOUT_MS",
        ge=100,
        le=30000,
    )
    rag_reranker_cache_enabled: bool = Field(
        default=False,
        validation_alias="RAG_RERANKER_CACHE_ENABLED",
    )
    rag_reranker_cache_ttl_seconds: int = Field(
        default=180,
        validation_alias="RAG_RERANKER_CACHE_TTL_SECONDS",
        ge=1,
        le=3600,
    )
    rag_reranker_cache_max_entries: int = Field(
        default=512,
        validation_alias="RAG_RERANKER_CACHE_MAX_ENTRIES",
        ge=32,
        le=10000,
    )
    rule_verification_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "RULE_VERIFICATION_ENABLED",
            "RAG_RULE_VERIFICATION_ENABLED",
            "VERIFICATION_ENABLED",
        ),
    )
    rag_nli_enabled: bool = Field(
        default=True,
        validation_alias="RAG_NLI_ENABLED",
    )
    rag_nli_strategy: str = Field(
        default="heuristic",
        validation_alias="RAG_NLI_STRATEGY",
    )
    rag_nli_timeout_ms: int = Field(
        default=180,
        validation_alias="RAG_NLI_TIMEOUT_MS",
        ge=50,
        le=30000,
    )
    rag_nli_llm_enabled: bool = Field(
        default=False,
        validation_alias="RAG_NLI_LLM_ENABLED",
    )
    rag_nli_llm_timeout_ms: int = Field(
        default=900,
        validation_alias="RAG_NLI_LLM_TIMEOUT_MS",
        ge=100,
        le=30000,
    )
    rag_nli_min_confidence: float = Field(
        default=0.35,
        validation_alias="RAG_NLI_MIN_CONFIDENCE",
        ge=0.0,
        le=1.0,
    )
    rag_biomedical_rerank_alpha: float = Field(
        default=0.28,
        validation_alias="RAG_BIOMEDICAL_RERANK_ALPHA",
        ge=0.0,
        le=1.0,
    )
    rag_biomedical_rerank_top_n: int = Field(
        default=8,
        validation_alias="RAG_BIOMEDICAL_RERANK_TOP_N",
        ge=0,
        le=64,
    )
    # Canonical name explicitly identifies this as a deterministic fixed-weight
    # heuristic shadow. COUNCIL_NEURAL_* remains environment-only compatibility
    # for old deployments; it is never emitted as a model name or API field.
    council_rule_shadow_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "COUNCIL_RULE_SHADOW_ENABLED",
            "COUNCIL_NEURAL_ENABLED",
        ),
    )
    council_rule_shadow_mode: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "COUNCIL_RULE_SHADOW_MODE",
            "COUNCIL_NEURAL_SHADOW_MODE",
        ),
    )
    council_rule_shadow_medium_threshold: float = Field(
        default=0.45,
        validation_alias=AliasChoices(
            "COUNCIL_RULE_SHADOW_MEDIUM_THRESHOLD",
            "COUNCIL_NEURAL_MEDIUM_THRESHOLD",
        ),
        ge=0.0,
        le=1.0,
    )
    council_rule_shadow_high_threshold: float = Field(
        default=0.72,
        validation_alias=AliasChoices(
            "COUNCIL_RULE_SHADOW_HIGH_THRESHOLD",
            "COUNCIL_NEURAL_HIGH_THRESHOLD",
        ),
        ge=0.0,
        le=1.0,
    )
    council_llm_shadow_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_LLM_SHADOW_ENABLED",
    )
    council_llm_max_tokens: int = Field(
        default=1200,
        validation_alias="COUNCIL_LLM_MAX_TOKENS",
        ge=400,
        le=4000,
    )

    # --- Council upgrade feature flags (additive; default OFF) ---------------
    # ML-side gates for the Council upgrade, mirroring the COUNCIL_RULE_SHADOW_*
    # pattern above. All additive + default OFF ⇒ byte-for-byte current
    # behavior: with these off, run_council / run_council_intake emit their
    # existing shapes, no SSE stage stream is produced, no ai_disclosure block
    # is attached, and no per-stage flow events are emitted (Requirements 9.1,
    # 9.2). Each flag is the ML peer of the same-named API flag in
    # services/api/.../core/config.py.
    council_streaming_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_STREAMING_ENABLED",
    )
    council_model_disclosure_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_MODEL_DISCLOSURE_ENABLED",
    )
    council_observability_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_OBSERVABILITY_ENABLED",
    )

    # --- RAG Knowledge Pipeline (P0 foundations) -----------------------------
    # Additive feature flags. Every flag defaults to legacy behavior so the
    # existing in-memory pipeline keeps serving traffic until cutover.
    # NOTE: RAG_BIOMED_GRAPH_ENABLED and RAG_RERANKER_TIMEOUT_MS already exist
    # above (rag_biomed_graph_enabled / rag_reranker_timeout_ms) and are reused
    # as-is rather than redefined here.
    rag_persistent_store_enabled: bool = Field(
        default=False,
        validation_alias="RAG_PERSISTENT_STORE_ENABLED",
    )
    rag_persistent_retrieval_enabled: bool = Field(
        default=False,
        validation_alias="RAG_PERSISTENT_RETRIEVAL_ENABLED",
    )
    rag_ingestion_enabled: bool = Field(
        default=False,
        validation_alias="RAG_INGESTION_ENABLED",
    )
    rag_entity_normalization_enabled: bool = Field(
        default=False,
        validation_alias="RAG_ENTITY_NORMALIZATION_ENABLED",
    )
    rag_trust_tier_ranking_enabled: bool = Field(
        default=False,
        validation_alias="RAG_TRUST_TIER_RANKING_ENABLED",
    )
    rag_semantic_cache_enabled: bool = Field(
        default=False,
        validation_alias="RAG_SEMANTIC_CACHE_ENABLED",
    )
    rag_eval_ci_enabled: bool = Field(
        default=False,
        validation_alias="RAG_EVAL_CI_ENABLED",
    )
    # --- Clara Scribe (enterprise) feature flags + ASR config ---------------
    # All additive + default off/legacy: with these off, Scribe behaves exactly
    # as the current batch transcribe + SOAP flow.
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
    # ASR provider selection seam. "whisper" = existing DeepSeek/Whisper audio
    # client (the only fully-wired provider today); other names degrade to it.
    scribe_asr_primary: str = Field(default="whisper", validation_alias="SCRIBE_ASR_PRIMARY")
    scribe_asr_fallback: str = Field(default="whisper", validation_alias="SCRIBE_ASR_FALLBACK")
    scribe_asr_language: str = Field(default="vi", validation_alias="SCRIBE_ASR_LANGUAGE")
    scribe_asr_timeout_seconds: float = Field(
        default=150.0, validation_alias="SCRIBE_ASR_TIMEOUT_SECONDS"
    )
    scribe_google_project_id: str = Field(default="", validation_alias="SCRIBE_GOOGLE_PROJECT_ID")
    scribe_google_location: str = Field(default="us", validation_alias="SCRIBE_GOOGLE_LOCATION")
    scribe_google_recognizer: str = Field(default="_", validation_alias="SCRIBE_GOOGLE_RECOGNIZER")
    # Code-switching: when true (default) the Vietnamese ASR provider is asked to keep
    # embedded English drug/procedure tokens verbatim rather than transliterating them
    # (Requirement 2.2).
    scribe_asr_code_switching: bool = Field(
        default=True, validation_alias="SCRIBE_ASR_CODE_SWITCHING"
    )
    # Medical-ASR correction only proposes source-spanned edits. It never
    # rewrites a transcript automatically and stays off until explicit rollout.
    scribe_medical_correction_enabled: bool = Field(
        default=False, validation_alias="SCRIBE_MEDICAL_CORRECTION_ENABLED"
    )
    # PhoWhisper (self-hosted, Vietnamese-capable) HTTP provider config. Defaults keep it
    # DISABLED/degrading: with no base URL set the provider returns an empty result so the
    # composite falls back to Whisper. Selected via SCRIBE_ASR_PRIMARY/FALLBACK="phowhisper".
    scribe_phowhisper_base_url: str = Field(
        default="", validation_alias="SCRIBE_PHOWHISPER_BASE_URL"
    )
    scribe_phowhisper_api_key: str = Field(default="", validation_alias="SCRIBE_PHOWHISPER_API_KEY")
    scribe_phowhisper_model: str = Field(
        default="phowhisper-large", validation_alias="SCRIBE_PHOWHISPER_MODEL"
    )
    scribe_phowhisper_timeout_seconds: float = Field(
        default=30.0, validation_alias="SCRIBE_PHOWHISPER_TIMEOUT_SECONDS"
    )
    scribe_phowhisper_retries: int = Field(default=1, validation_alias="SCRIBE_PHOWHISPER_RETRIES")
    scribe_phowhisper_retry_backoff_seconds: float = Field(
        default=0.25, validation_alias="SCRIBE_PHOWHISPER_RETRY_BACKOFF_SECONDS"
    )
    # --- Clara Scribe (enterprise) wave-2 feature flags ---------------------
    # R12–R20. All additive + default off ⇒ byte-for-byte current behavior:
    # with these off, grounding/extraction/coding/metrics/FHIR-composition/
    # addendum/specialty-templates/eval-gate passes never run and emit no
    # metadata.
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
    # Embedding fail-loud / degraded-mode tuning (replaces silent hash fallback).
    rag_embedding_fail_loud: bool = Field(
        default=True,
        validation_alias="RAG_EMBEDDING_FAIL_LOUD",
    )
    rag_embedding_allow_degraded: bool = Field(
        default=False,
        validation_alias="RAG_EMBEDDING_ALLOW_DEGRADED",
    )
    # Dense embedding dimension; default matches text-embedding-3-large (3072),
    # labeled "bge-m3" in product copy. Asserted at write time by the store.
    rag_embedding_dim: int = Field(
        default=3072,
        validation_alias="RAG_EMBEDDING_DIM",
        ge=1,
        le=8192,
    )
    # ANN index kind for pgvector (hnsw | ivfflat); HNSW preferred for recall.
    rag_ann_index_kind: str = Field(
        default="hnsw",
        validation_alias="RAG_ANN_INDEX_KIND",
    )
    # Persistent-retrieval gap-fill knobs (unused on the legacy in-memory path).
    rag_min_results: int = Field(
        default=3,
        validation_alias=AliasChoices("RAG_MIN_RESULTS", "MIN_RESULTS"),
        ge=1,
        le=100,
    )
    # Trust floor: lowest acceptable authority tier number (1 = highest
    # authority, 4 = lowest). Default 4 accepts all tiers (no filtering today).
    rag_trust_floor: int = Field(
        default=4,
        validation_alias="RAG_TRUST_FLOOR",
        ge=1,
        le=4,
    )

    # --- CLARA Research enhancement feature flags (additive; default off) --------
    # All flags default to the value that preserves current (legacy) behavior.
    # When every flag below is False/off, the research pipeline produces
    # byte-for-byte identical output to the pre-enhancement baseline (R20.2).
    research_query_decomposition_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_QUERY_DECOMPOSITION_ENABLED",
    )
    research_gap_fill_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_GAP_FILL_ENABLED",
    )
    research_gap_fill_max_passes: int = Field(
        default=2,
        validation_alias="RESEARCH_GAP_FILL_MAX_PASSES",
        ge=0,
        le=8,
    )
    research_recency_trust_ranking_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_RECENCY_TRUST_RANKING_ENABLED",
    )
    research_pico_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_PICO_ENABLED",
    )
    research_grade_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_GRADE_ENABLED",
    )
    # Deprecated compatibility switch.  This value is intentionally no longer
    # used to emit GRADE labels or recommendation strength: source type and an
    # internal authority tier alone cannot perform a formal GRADE assessment.
    # Retain it only so existing deployments do not fail configuration parsing.
    # Use RESEARCH_EVIDENCE_SIGNALS_ENABLED for the provenance-only replacement.
    research_evidence_signals_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_EVIDENCE_SIGNALS_ENABLED",
    )
    research_consensus_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_CONSENSUS_ENABLED",
    )
    research_claim_trace_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_CLAIM_TRACE_ENABLED",
    )
    research_role_adaptive_output_enabled: bool = Field(
        default=False,
        validation_alias="RESEARCH_ROLE_ADAPTIVE_OUTPUT_ENABLED",
    )

    # --- Platform hardening: circuit breaker (additive; default OFF) ---------
    # Mirrors the API-side HARDENING_CIRCUIT_BREAKER_ENABLED flag so the ML
    # service can wrap the DeepSeek/embedding client retry loop with a breaker
    # that opens after a threshold of consecutive failures and short-circuits to
    # the existing labeled local fallback for a cool-down window before a
    # half-open probe. Default OFF preserves byte-for-byte current behavior: the
    # breaker is never consulted and calls flow through the existing bounded
    # retry path unchanged (Requirement 6.5, 11.1; design Property 16).
    hardening_circuit_breaker_enabled: bool = Field(
        default=False,
        validation_alias="HARDENING_CIRCUIT_BREAKER_ENABLED",
    )
    # Consecutive-failure count at which the breaker opens. Inert while the flag
    # is off.
    hardening_circuit_breaker_failure_threshold: int = Field(
        default=5,
        validation_alias="HARDENING_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        ge=1,
        le=100,
    )
    # Cool-down window (seconds) the breaker stays open before allowing a
    # half-open recovery probe. Inert while the flag is off.
    hardening_circuit_breaker_cooldown_seconds: float = Field(
        default=30.0,
        validation_alias="HARDENING_CIRCUIT_BREAKER_COOLDOWN_SECONDS",
        ge=0.0,
        le=3600.0,
    )

    @model_validator(mode="after")
    def _enforce_deep_beta_word_budget_bounds(self) -> "Settings":
        """Guarantee the deep_beta config band can never violate the
        ``min_words <= max_words_cap <= 15000`` invariant (Requirement 6.5;
        design Correctness Property P1).

        The per-field bounds already constrain each value to its documented
        range (``min_words`` 4000-12000, ``max_words_cap`` 6000-15000), but they
        cannot catch a *cross-field* misconfiguration such as
        ``DEEP_BETA_REPORT_MIN_WORDS=12000`` together with
        ``DEEP_BETA_REPORT_MAX_WORDS_CAP=6000`` (each individually valid, yet
        ``min > max``). Per the design's error-handling strategy we **clamp and
        log** rather than raise so a misconfiguration degrades gracefully while
        the invariant still holds: the ceiling (the hard 15000 guarantee) stays
        authoritative and the floor is lowered to meet it.
        """

        hard_max = DEEP_BETA_REPORT_HARD_MAX_WORDS

        # Defensive: the ceiling can never exceed the hard cap. The field bound
        # (le=15000) already enforces this for env input, but clamp anyway so
        # the invariant holds even if the bound is later relaxed.
        if self.deep_beta_report_max_words_cap > hard_max:
            logger.warning(
                "deep_beta_report_max_words_cap=%d exceeds hard ceiling %d; clamping to %d",
                self.deep_beta_report_max_words_cap,
                hard_max,
                hard_max,
            )
            self.deep_beta_report_max_words_cap = hard_max

        # The floor must never exceed the ceiling. Clamp the floor down so the
        # ceiling stays authoritative and ``min <= max`` holds.
        if self.deep_beta_report_min_words > self.deep_beta_report_max_words_cap:
            logger.warning(
                "deep_beta_report_min_words=%d exceeds "
                "deep_beta_report_max_words_cap=%d; clamping floor to %d so "
                "min <= max <= %d holds",
                self.deep_beta_report_min_words,
                self.deep_beta_report_max_words_cap,
                self.deep_beta_report_max_words_cap,
                hard_max,
            )
            self.deep_beta_report_min_words = self.deep_beta_report_max_words_cap

        # A clinical DrugBank-only deployment may not silently turn off either
        # the on-disk index or artifact-integrity verification. Refuse this
        # contradiction during configuration parsing so the service cannot make
        # a DDI conclusion from a legacy/curated fallback while claiming the
        # licensed source is mandatory.
        if self.careguard_drugbank_required and not self.careguard_drugbank_sqlite_enabled:
            raise ValueError(
                "CAREGUARD_DRUGBANK_REQUIRED requires CAREGUARD_DRUGBANK_SQLITE_ENABLED=true"
            )
        if (
            self.careguard_drugbank_required
            and not self.careguard_drugbank_manifest_integrity_required
        ):
            raise ValueError(
                "CAREGUARD_DRUGBANK_REQUIRED requires "
                "CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED=true"
            )

        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
