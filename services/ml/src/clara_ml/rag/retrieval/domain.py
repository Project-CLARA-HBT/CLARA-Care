from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


SOURCE_SCORE_BIAS: dict[str, float] = {
    "pubmed": 1.12,
    "europepmc": 1.1,
    "clinicaltrials": 1.08,
    "openfda": 1.35,
    "dailymed": 1.35,
    "searxng": 1.0,
    "web_crawl": 0.98,
    "searxng-crawl": 0.98,
    "openalex": 0.92,
    "semantic_scholar": 0.95,
    "crossref": 0.7,
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
