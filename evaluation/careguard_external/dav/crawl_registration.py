"""Fetch all discovered DAV publication detail pages, retaining provenance metadata."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .core import Store, decision_number, fetch, now


def crawl(root: Path, retrieval_date: str) -> int:
    store = Store(root, retrieval_date)
    queue = json.loads((store.manifests / "publication_queue.json").read_text(encoding="utf-8"))
    completed = set()
    inventory = store.manifests / "source_inventory.jsonl"
    if inventory.exists():
        completed = {
            json.loads(line).get("url")
            for line in inventory.read_text(encoding="utf-8").splitlines()
        }
    failed_path = store.manifests / "failed_or_unavailable.jsonl"
    if failed_path.exists():
        completed |= {
            json.loads(line).get("url")
            for line in failed_path.read_text(encoding="utf-8").splitlines()
        }

    to_fetch = [row for row in queue if row["url"] not in completed]
    if not to_fetch:
        return 0

    count = 0

    def _fetch_one(row: dict) -> tuple[dict, tuple | Exception]:
        try:
            return row, fetch(row["url"])
        except Exception as exc:
            return row, exc

    with ThreadPoolExecutor(max_workers=4) as executor:
        for row, res in executor.map(_fetch_one, to_fetch):
            if isinstance(res, Exception):
                store.append(
                    "failed_or_unavailable.jsonl",
                    {"url": row["url"], "retrieved_at_utc": now(), "reason": str(res)},
                )
            else:
                status, content_type, payload, final_url = res
                source = store.retain(
                    bucket=row["document_type"],
                    url=final_url,
                    payload=payload,
                    content_type=content_type,
                    status=status,
                )
                source.update(
                    {
                        "source_url": final_url,
                        "title": row["title"],
                        "document_type": row["document_type"],
                        "decision_number": decision_number(row["title"]),
                        "discovered_from": row["discovered_from"],
                    }
                )
                store.append("source_inventory.jsonl", source)
                count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/restricted/dav"))
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    print(crawl(args.root, args.date))
