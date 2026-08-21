"""Discover official DAV registration sections and pagination without guessing routes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import Store, classify, fetch, links_from_html, now

SEEDS = (
    "https://dav.gov.vn/",
    "https://dav.gov.vn/dang-ki-thuoc---cong-bo-nguyen-lieu-c311.html",
    "https://dav.gov.vn/tra-cuu-thuoc.html",
    "https://dichvucong.dav.gov.vn/",
    "https://06dichvucong.dav.gov.vn/",
)


def discover(root: Path, retrieval_date: str) -> dict:
    store, sections = Store(root, retrieval_date), []
    for url in SEEDS:
        try:
            receipt = store.prior_receipt(url)
            if receipt is None:
                status, content_type, payload, final_url = fetch(url)
                receipt = store.retain(
                    bucket="registration_search",
                    url=final_url,
                    payload=payload,
                    content_type=content_type,
                    status=status,
                )
                store.append("source_inventory.jsonl", receipt)
            else:
                status, content_type, final_url = (
                    receipt["http_status"],
                    receipt["content_type"],
                    receipt["url"],
                )
                payload = Path(receipt["raw_path"]).read_bytes()
            receipt["seed_url"] = url
            receipt["maintenance_notice"] = (
                "tạm dừng để bảo trì" in payload.decode("utf-8", "replace").casefold()
            )
            if status == 200 and "html" in content_type:
                for linked_url, title in links_from_html(payload, final_url):
                    kind = classify(title, linked_url)
                    if kind:
                        sections.append(
                            {
                                "url": linked_url,
                                "title": title,
                                "document_type": kind,
                                "discovered_from": final_url,
                            }
                        )
        except Exception as exc:  # noqa: BLE001 - retain every public-source failure receipt
            store.append(
                "failed_or_unavailable.jsonl",
                {"url": url, "retrieved_at_utc": now(), "reason": str(exc)},
            )
    unique = {row["url"]: row for row in sections}
    result = {
        "schema_version": "dav.discovery.v1",
        "retrieved_at_utc": now(),
        "sections": [unique[key] for key in sorted(unique)],
    }
    (store.manifests / "discovery.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/restricted/dav"))
    parser.add_argument("--date", required=True)
    print(
        json.dumps(discover(parser.parse_args().root, parser.parse_args().date), ensure_ascii=False)
    )
