from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import DownloadedPdf, SourceCatalogEntry


def load_catalog_csv(catalog_csv_path: Path) -> list[SourceCatalogEntry]:
    if not catalog_csv_path.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_csv_path}")

    entries: list[SourceCatalogEntry] = []
    with catalog_csv_path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            source_id = str(row.get("source_id") or "").strip()
            if not source_id:
                continue
            entries.append(
                SourceCatalogEntry(
                    source_id=source_id,
                    owner=str(row.get("owner") or "").strip(),
                    category=str(row.get("category") or "").strip(),
                    entry_url=str(row.get("entry_url") or "").strip(),
                    direct_url_example=str(row.get("direct_url_example") or "").strip(),
                    update_cadence_observed=str(
                        row.get("update_cadence_observed") or ""
                    ).strip(),
                    usage_notes=str(row.get("usage_notes") or "").strip(),
                    trust_tier=str(row.get("trust_tier") or "").strip(),
                    confidence=str(row.get("confidence") or "").strip(),
                )
            )
    return entries


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)


def write_manifest_jsonl(path: Path, items: Iterable[DownloadedPdf]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file_obj:
        for item in items:
            record = {
                "source_id": item.source_id,
                "owner": item.owner,
                "category": item.category,
                "trust_tier": item.trust_tier,
                "confidence": item.confidence,
                "source_url": item.source_url,
                "download_url": item.download_url,
                "local_path": item.local_path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
            }
            file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")


def trust_tier_weight(trust_tier: str) -> float:
    normalized = trust_tier.strip().upper()
    if normalized == "A1":
        return 1.0
    if normalized == "A2":
        return 0.95
    if normalized == "B1":
        return 0.8
    if normalized == "C1":
        return 0.6
    return 0.75
