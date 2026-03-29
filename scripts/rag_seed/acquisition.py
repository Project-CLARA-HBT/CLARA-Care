from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .html_discovery import discover_pdf_links
from .http_client import (
    HttpClient,
    is_likely_pdf_url,
    normalize_url_candidates,
    within_domain,
    write_pdf_file,
)
from .io_utils import trust_tier_weight
from .models import DownloadedPdf, SourceCatalogEntry
from .pdf_extract import extract_pdf_text


def _allowed_hosts(entry: SourceCatalogEntry) -> list[str]:
    hosts: list[str] = []
    for value in [entry.entry_url, entry.direct_url_example]:
        parsed = urlparse(value)
        host = (parsed.hostname or "").strip().lower()
        if host:
            hosts.append(host)
    # keep stable order, remove duplicates
    deduped: list[str] = []
    seen: set[str] = set()
    for host in hosts:
        if host in seen:
            continue
        seen.add(host)
        deduped.append(host)
    return deduped


def _candidate_urls(entry: SourceCatalogEntry) -> list[str]:
    raw = "\n".join([entry.entry_url, entry.direct_url_example])
    return normalize_url_candidates(raw)


def _discover_urls_from_entry_page(
    client: HttpClient,
    entry: SourceCatalogEntry,
    *,
    max_links: int,
) -> list[str]:
    try:
        html = client.get_text(entry.entry_url)
    except Exception:
        return []
    return discover_pdf_links(html, entry.entry_url, max_links=max_links)


def _download_pdf(
    client: HttpClient,
    dest_dir: Path,
    *,
    source_id: str,
    source_url: str,
    download_url: str,
) -> tuple[Path, str, int] | None:
    try:
        payload, content_type = client.get_bytes(download_url)
    except Exception:
        return None
    if not payload:
        return None

    pdf_signature = payload[:4] == b"%PDF"
    content_is_pdf = "application/pdf" in content_type
    if not pdf_signature and not content_is_pdf:
        return None

    local_path, sha256_hex = write_pdf_file(
        dest_dir,
        source_id=source_id,
        download_url=download_url,
        payload=payload,
    )
    return local_path, sha256_hex, len(payload)


def acquire_seed_pdfs(
    entries: Iterable[SourceCatalogEntry],
    *,
    output_dir: Path,
    max_sources: int,
    max_docs_per_source: int,
    max_candidate_urls_per_source: int,
    timeout_seconds: float,
    sleep_seconds: float,
) -> list[DownloadedPdf]:
    client = HttpClient(timeout_seconds=timeout_seconds, sleep_seconds=sleep_seconds)
    acquired: list[DownloadedPdf] = []
    selected_entries = list(entries)
    if max_sources > 0:
        selected_entries = selected_entries[:max_sources]

    for entry in selected_entries:
        allowed_hosts = _allowed_hosts(entry)
        candidates = _candidate_urls(entry)
        discovered = _discover_urls_from_entry_page(
            client,
            entry,
            max_links=max(8, max_docs_per_source * 4),
        )
        candidates.extend(discovered)

        unique_candidates: list[str] = []
        seen_urls: set[str] = set()
        for url in candidates:
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if allowed_hosts and not within_domain(url, allowed_hosts):
                continue
            unique_candidates.append(url)
            if len(unique_candidates) >= max_candidate_urls_per_source:
                break

        downloaded_count = 0
        for url in unique_candidates:
            if downloaded_count >= max_docs_per_source:
                break

            if not is_likely_pdf_url(url):
                continue
            result = _download_pdf(
                client,
                output_dir,
                source_id=entry.source_id,
                source_url=entry.entry_url,
                download_url=url,
            )
            if result is None:
                continue

            local_path, sha256_hex, size_bytes = result
            extracted_text = extract_pdf_text(local_path, max_chars=12000)
            acquired.append(
                DownloadedPdf(
                    source_id=entry.source_id,
                    owner=entry.owner,
                    category=entry.category,
                    trust_tier=entry.trust_tier,
                    confidence=entry.confidence,
                    source_url=entry.entry_url,
                    download_url=url,
                    local_path=str(local_path),
                    sha256=sha256_hex,
                    size_bytes=size_bytes,
                    extracted_text=extracted_text,
                )
            )
            downloaded_count += 1
    return acquired


def to_seed_documents(
    acquired: Iterable[DownloadedPdf],
    *,
    catalog_entries: Iterable[SourceCatalogEntry] | None = None,
) -> list[dict[str, object]]:
    seed_docs: list[dict[str, object]] = []
    covered_source_ids: set[str] = set()
    for item in acquired:
        excerpt = _clean_extracted_text(item.extracted_text, max_chars=6000)
        fallback_text = (
            f"Nguon: {item.owner}. Nhom: {item.category}. "
            f"Tai lieu tham chieu y khoa Viet Nam tu {item.source_id}. "
            f"URL: {item.download_url}"
        )
        text = excerpt if excerpt else fallback_text
        source_code = item.source_id.lower().replace("_", "-")
        doc_id = f"{source_code}-{item.sha256[:12]}"
        seed_docs.append(
            {
                "id": doc_id,
                "text": text,
                "metadata": {
                    "source": "vn_pdf",
                    "url": item.download_url,
                    "score": 0.0,
                    "weight": trust_tier_weight(item.trust_tier),
                    "tags": [
                        "vn-medical",
                        item.category.lower().replace(" ", "-"),
                        source_code,
                    ],
                    "trust_tier": _normalize_trust_tier(item.trust_tier),
                    "file_type": "pdf",
                    "source_id": item.source_id,
                    "owner": item.owner,
                },
            }
        )
        covered_source_ids.add(item.source_id)

    if catalog_entries is None:
        return seed_docs

    for entry in catalog_entries:
        if entry.source_id in covered_source_ids:
            continue
        source_code = entry.source_id.lower().replace("_", "-")
        catalog_text = (
            f"Registry source for VN medical RAG. Source ID: {entry.source_id}. "
            f"Owner: {entry.owner}. Category: {entry.category}. "
            f"Entry URL: {entry.entry_url}. "
            f"Direct example: {entry.direct_url_example}. "
            f"Cadence: {entry.update_cadence_observed}. "
            f"Notes: {entry.usage_notes}"
        )
        seed_docs.append(
            {
                "id": f"{source_code}-catalog",
                "text": catalog_text,
                "metadata": {
                    "source": "vn_source_registry",
                    "url": entry.entry_url,
                    "score": 0.0,
                    "weight": trust_tier_weight(entry.trust_tier),
                    "tags": ["vn-medical", "catalog", source_code],
                    "trust_tier": _normalize_trust_tier(entry.trust_tier),
                    "file_type": "catalog",
                    "source_id": entry.source_id,
                    "owner": entry.owner,
                    "confidence": entry.confidence,
                },
            }
        )
    return seed_docs


def _normalize_trust_tier(trust_tier: str) -> str:
    normalized = trust_tier.strip().upper()
    if normalized == "A1":
        return "tier_1"
    if normalized == "A2":
        return "tier_2"
    if normalized == "B1":
        return "tier_3"
    if normalized == "C1":
        return "tier_4"
    return "tier_3"


def to_acquisition_report(acquired: Iterable[DownloadedPdf]) -> dict[str, object]:
    items = list(acquired)
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item.source_id] = by_source.get(item.source_id, 0) + 1
    return {
        "total_documents": len(items),
        "source_count": len(by_source),
        "documents_per_source": by_source,
        "documents": [asdict(item) for item in items],
    }


def _clean_extracted_text(raw_text: str, *, max_chars: int) -> str:
    text = " ".join((raw_text or "").split()).strip()
    if not text:
        return ""
    lowered = text.lower()
    bad_markers = [
        "%pdf",
        "endobj",
        "xref",
        "stream",
        "/type /page",
        "/filter /flatedecode",
    ]
    bad_hits = sum(1 for marker in bad_markers if marker in lowered)
    if bad_hits >= 2:
        return ""
    alpha_chars = sum(1 for ch in text if ch.isalpha())
    ratio = alpha_chars / max(len(text), 1)
    if ratio < 0.35:
        return ""
    if len(text) < 80:
        return ""
    return text[:max_chars]
