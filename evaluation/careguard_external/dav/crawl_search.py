"""Acquire the DAV public ``Tra cứu thông tin thuốc`` result archive.

This is a public information-material index, not affirmative marketing status.
Its product identity fields are retained separately from registration decisions.
"""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from .core import Store, fetch, now

ROOT = "https://dav.gov.vn/tra-cuu-thuoc.html"


class TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if len(self.row) >= 7:
                self.rows.append(self.row)
            self.row = None


def extract_index(root: Path, retrieval_date: str) -> int:
    store = Store(root, retrieval_date)
    inventory = [
        json.loads(line)
        for line in (store.manifests / "source_inventory.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    records = []
    for source in inventory:
        if source.get("document_type") != "drug_information_search":
            continue
        parser = TableRows()
        parser.feed(Path(source["raw_path"]).read_text(encoding="utf-8", errors="replace"))
        for ordinal, row in enumerate(parser.rows, start=1):
            records.append(
                {
                    "source_record_id": f"{source['sha256']}:{ordinal}",
                    "receipt_number_raw": row[1],
                    "receipt_year_raw": row[2],
                    "product_name_raw": row[3],
                    "registrant_raw": row[4],
                    "information_material_type_raw": row[5],
                    "registration_number_raw": row[6],
                    "source_url": source["url"],
                    "raw_artifact_sha256": source["sha256"],
                }
            )
    output = store.manifests / "drug_information_index.jsonl"
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    return len(records)


def crawl(root: Path, retrieval_date: str) -> int:
    store = Store(root, retrieval_date)
    status, content_type, payload, final_url = fetch(ROOT)
    receipt = store.retain(
        bucket="registration_search",
        url=final_url,
        payload=payload,
        content_type=content_type,
        status=status,
    )
    receipt.update({"source_url": final_url, "document_type": "drug_information_search"})
    store.append("source_inventory.jsonl", receipt)
    text = payload.decode("utf-8", "replace")
    # DAV server-side pagination exposes a finite last-page link. Do not invent
    # a page upper bound if that control is absent.
    pages = [int(value) for value in re.findall(r"tra-cuu-thuoc(?:-page|\.html\?page=)(\d+)", text)]
    if not pages:
        return 1
    count = 1
    for page in range(2, max(pages) + 1):
        url = f"https://dav.gov.vn/tra-cuu-thuoc-page{page}.html"
        try:
            status, content_type, body, final_url = fetch(url)
            record = store.retain(
                bucket="registration_search",
                url=final_url,
                payload=body,
                content_type=content_type,
                status=status,
            )
            record.update(
                {
                    "source_url": final_url,
                    "document_type": "drug_information_search",
                    "archive_page": page,
                }
            )
            store.append("source_inventory.jsonl", record)
            count += 1
        except Exception as exc:
            store.append(
                "failed_or_unavailable.jsonl",
                {"url": url, "retrieved_at_utc": now(), "reason": str(exc)},
            )
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/restricted/dav"))
    parser.add_argument("--date", required=True)
    parser.add_argument("--extract-only", action="store_true")
    args = parser.parse_args()
    print(extract_index(args.root, args.date) if args.extract_only else crawl(args.root, args.date))
