from clara_api.schemas import (
    CareguardRuntimeConfig,
    RagFlowConfig,
    RagSourceEntry,
    SystemControlTowerConfig,
)

CONTROL_TOWER_KEY = "control_tower_config_v1"

_DEFAULT_CONTROL_TOWER_CONFIG = SystemControlTowerConfig(
    rag_sources=[
        RagSourceEntry(
            id="pubmed",
            name="PubMed",
            enabled=True,
            priority=1,
            weight=1.0,
            category="literature",
        ),
        RagSourceEntry(
            id="europepmc",
            name="Europe PMC",
            enabled=True,
            priority=2,
            weight=1.0,
            category="literature",
        ),
        RagSourceEntry(
            id="openalex",
            name="OpenAlex",
            enabled=True,
            priority=3,
            weight=1.0,
            category="literature",
        ),
        RagSourceEntry(
            id="crossref",
            name="Crossref",
            enabled=True,
            priority=4,
            weight=1.0,
            category="literature",
        ),
        RagSourceEntry(
            id="clinicaltrials",
            name="ClinicalTrials.gov",
            enabled=True,
            priority=5,
            weight=1.0,
            category="clinical_trials",
        ),
        RagSourceEntry(
            id="openfda",
            name="openFDA",
            enabled=True,
            priority=6,
            weight=1.0,
            category="drug_safety",
        ),
        RagSourceEntry(
            id="dailymed",
            name="DailyMed",
            enabled=True,
            priority=7,
            weight=1.0,
            category="drug_label",
        ),
        RagSourceEntry(
            id="searxng",
            name="SearXNG (self-host)",
            enabled=True,
            priority=8,
            weight=1.0,
            category="web_search",
        ),
        RagSourceEntry(
            id="rxnorm",
            name="RxNorm",
            enabled=True,
            priority=9,
            weight=1.0,
            category="drug_normalization",
        ),
        RagSourceEntry(
            id="davidrug",
            name="Cục Quản lý Dược (VN)",
            enabled=True,
            priority=10,
            weight=1.0,
            category="vn_regulatory",
        ),
    ],
    rag_flow=RagFlowConfig(
        role_router_enabled=True,
        intent_router_enabled=True,
        verification_enabled=True,
        deepseek_fallback_enabled=True,
        low_context_threshold=0.2,
        precision_at_k=10,
        recall_at_k=10,
        ndcg_at_k=10,
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=True,
        file_retrieval_enabled=True,
    ),
    careguard_runtime=CareguardRuntimeConfig(external_ddi_enabled=False),
)


def get_default_control_tower_config() -> SystemControlTowerConfig:
    return SystemControlTowerConfig.model_validate(
        _DEFAULT_CONTROL_TOWER_CONFIG.model_dump(mode="json")
    )
