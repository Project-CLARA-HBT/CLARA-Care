"""Download every publicly linked, product-relevant DAV attachment once."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .core import ATTACHMENT_EXTENSIONS, Store, fetch, links_from_html, now


def download(root: Path, retrieval_date: str, max_workers: int = 8) -> int:
    store = Store(root, retrieval_date)
    inventory_path = store.manifests / "source_inventory.jsonl"
    rows = [json.loads(line) for line in inventory_path.read_text(encoding="utf-8").splitlines()]
    known = {row["url"] for row in rows}
    failed_path = store.manifests / "failed_or_unavailable.jsonl"
    if failed_path.exists():
        known |= {
            json.loads(line).get("url")
            for line in failed_path.read_text(encoding="utf-8").splitlines()
        }

    count = 0
    seen_in_batch = set()
    candidates: list[tuple[dict, str, str]] = []
    for source in rows:
        if "html" not in source.get("content_type", "") or not source.get("document_type"):
            continue
        raw_path = Path(source["raw_path"])
        if not raw_path.exists():
            continue
        payload = raw_path.read_bytes()
        for url, label in links_from_html(payload, source["url"]):
            if url in known or url in seen_in_batch:
                continue
            suffix = Path(url.split("?", 1)[0]).suffix.lower()
            if suffix not in ATTACHMENT_EXTENSIONS:
                continue
            candidates.append((source, url, label))
            seen_in_batch.add(url)

    print(f"Total new attachment candidates to download: {len(candidates)}")
    if not candidates:
        return 0

    def retrieve(candidate: tuple[dict, str, str]) -> tuple[dict, str, str, tuple | Exception]:
        source, url, label = candidate
        try:
            return source, url, label, fetch(url)
        except Exception as exc:  # noqa: BLE001 - persisted below as a receipt
            return source, url, label, exc

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, (source, url, label, response) in enumerate(
            executor.map(retrieve, candidates), start=1
        ):
            try:
                if isinstance(response, Exception):
                    raise response
                status, content_type, body, final_url = response
                if status != 200 or "html" in content_type:
                    raise RuntimeError(
                        f"attachment_content_invalid:status={status}:content_type={content_type}"
                    )
                artifact = store.retain(
                    bucket="attachments",
                    url=final_url,
                    payload=body,
                    content_type=content_type,
                    status=status,
                    filename=label or None,
                )
                artifact.update(
                    {
                        "source_url": final_url,
                        "document_type": source["document_type"],
                        "parent_source_sha256": source["sha256"],
                        "attachment_filename": label,
                    }
                )
                store.append("source_inventory.jsonl", artifact)
                count += 1
            except Exception as exc:  # noqa: BLE001 - retain every attachment failure receipt
                store.append(
                    "failed_or_unavailable.jsonl",
                    {
                        "url": url,
                        "retrieved_at_utc": now(),
                        "reason": str(exc),
                        "parent_source_sha256": source["sha256"],
                    },
                )
            if idx % 100 == 0 or idx == len(candidates):
                print(
                    f"Progress: {idx}/{len(candidates)} attachments processed (downloaded: {count})"
                )
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/restricted/dav"))
    parser.add_argument("--date", required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print("Downloaded:", download(args.root, args.date, max_workers=args.workers))
