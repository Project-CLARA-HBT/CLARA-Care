from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceCatalogEntry:
    source_id: str
    owner: str
    category: str
    entry_url: str
    direct_url_example: str
    update_cadence_observed: str
    usage_notes: str
    trust_tier: str
    confidence: str


@dataclass(frozen=True)
class DownloadedPdf:
    source_id: str
    owner: str
    category: str
    trust_tier: str
    confidence: str
    source_url: str
    download_url: str
    local_path: str
    sha256: str
    size_bytes: int
    extracted_text: str
