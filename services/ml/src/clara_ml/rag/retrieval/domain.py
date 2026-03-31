from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


SOURCE_SCORE_BIAS: dict[str, float] = {
    "pubmed": 1.05,
    "europepmc": 1.04,
    "clinicaltrials": 1.08,
    "openfda": 1.35,
    "dailymed": 1.35,
    "rxnorm": 1.2,
    "who": 1.16,
    "cdc": 1.12,
    "nice": 1.12,
    "ema": 1.13,
    "mhra": 1.1,
    "medlineplus": 1.06,
    "searxng": 1.0,
    "web_crawl": 0.98,
    "searxng-crawl": 0.98,
    "openalex": 1.0,
    "semantic_scholar": 1.0,
    "crossref": 0.95,
    "byt": 1.2,
    "dav": 1.18,
    "vn_source_registry": 1.15,
    "vn_pdf": 1.17,
}

TRUST_TIER_FACTOR: dict[str, float] = {
    "tier_1": 1.25,
    "tier_2": 1.12,
    "tier_3": 1.0,
    "tier_4": 0.88,
}
