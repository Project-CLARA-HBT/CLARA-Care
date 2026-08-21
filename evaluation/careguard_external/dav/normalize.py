"""Create provenance-preserving, non-destructive extracted registration/event rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import Store, registration_numbers

FIELDS = (
    "registration_number",
    "old_registration_number",
    "new_registration_number",
    "product_name_raw",
    "active_ingredients_raw",
    "strength_raw",
    "dosage_form_raw",
    "route_raw",
    "package_raw",
    "registrant_raw",
    "manufacturer_raw",
    "manufacturing_country_raw",
    "registration_issue_date_raw",
    "expiry_raw",
    "source_document_number",
    "source_document_date_raw",
    "source_url",
    "raw_artifact_sha256",
)


def norm(value: str | None) -> str | None:
    return " ".join(value.split()).casefold() if value else None


def write_parquet(rows: list[dict], destination: Path) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow_required_for_parquet_output") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), destination)


def normalize(root: Path, retrieval_date: str) -> tuple[list[dict], list[dict]]:
    store = Store(root, retrieval_date)
    parsed = [
        json.loads(line)
        for line in (store.manifests / "attachment_parse.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    products, events = [], []
    for artifact in parsed:
        if artifact["parse_status"] != "PARSED" or not artifact["text"]:
            continue
        numbers = registration_numbers(artifact["text"])
        for number in numbers:
            row = {field: None for field in FIELDS}
            row.update(
                {
                    "registration_number": number,
                    "source_url": artifact["source_url"],
                    "raw_artifact_sha256": artifact["raw_artifact_sha256"],
                    "product_name_normalized": None,
                    "active_ingredients_normalized": None,
                    "extraction_status": "REGISTRATION_NUMBER_ONLY",
                }
            )
            products.append(row)
            events.append(
                {
                    "event_type": {
                        "withdrawals": "WITHDRAWN",
                        "renewals": "RENEWED",
                        "continued_validity": "CONTINUED_VALIDITY",
                        "amendments": "AMENDED",
                        "corrections": "CORRECTED",
                    }.get(artifact.get("document_type"), "ISSUED"),
                    "registration_number": number,
                    "source_url": artifact["source_url"],
                    "raw_artifact_sha256": artifact["raw_artifact_sha256"],
                    "evidence_document_id": artifact["raw_artifact_sha256"],
                }
            )
    normalized = root / "normalized"
    write_parquet(products, normalized / "products.parquet")
    write_parquet(events, normalized / "product_events.parquet")
    return products, events


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/restricted/dav"))
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    print(tuple(map(len, normalize(args.root, args.date))))
