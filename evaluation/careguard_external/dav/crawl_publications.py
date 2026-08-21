"""Exhaustively walk DAV registration-news archive pages and retain each detail page."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .core import Store, classify, decision_number, fetch, links_from_html, now


def crawl(root: Path, retrieval_date: str) -> list[dict]:
    store = Store(root, retrieval_date)
    discovery = json.loads((store.manifests / "discovery.json").read_text(encoding="utf-8"))
    # Each discovered regulatory section is independently paged.  Preserve its
    # type across anonymous "next page" links rather than relying on link text.
    queue = [row for row in discovery["sections"] if "-cn" in row["url"] or "-c" in row["url"]]
    visited, articles = set(), []
    while queue:
        section = queue.pop(0)
        url = section["url"]
        if url in visited:
            continue
        visited.add(url)
        try:
            source = store.prior_receipt(url)
            if source is None:
                status, content_type, payload, final_url = fetch(url)
                source = store.retain(
                    bucket=section["document_type"],
                    url=final_url,
                    payload=payload,
                    content_type=content_type,
                    status=status,
                )
                store.append("source_inventory.jsonl", source)
            else:
                status, content_type, final_url = (
                    source["http_status"],
                    source["content_type"],
                    source["url"],
                )
                payload = Path(source["raw_path"]).read_bytes()
            source.update(
                {
                    "title": section["title"],
                    "document_type": section["document_type"],
                    "decision_number": decision_number(section["title"]),
                    "source_url": final_url,
                }
            )
            if status != 200 or "html" not in content_type:
                continue
            for linked_url, title in links_from_html(payload, final_url):
                kind = classify(title, linked_url) or section["document_type"]
                is_article = re.search(r"-n\d+\.html$", linked_url) is not None
                is_page = (
                    "trang" in linked_url.casefold()
                    or "-page" in linked_url.casefold()
                    or "next" in title.casefold()
                    or "sau" == title.casefold()
                ) and not is_article
                if is_page:
                    queue.append(
                        {
                            "url": linked_url,
                            "title": title,
                            "document_type": section["document_type"],
                        }
                    )
                elif is_article:
                    article = {
                        "url": linked_url,
                        "title": title,
                        "document_type": kind,
                        "discovered_from": final_url,
                    }
                    if linked_url not in {item["url"] for item in articles}:
                        articles.append(article)
        except Exception as exc:  # noqa: BLE001 - retain every public-source failure receipt
            store.append(
                "failed_or_unavailable.jsonl",
                {"url": url, "retrieved_at_utc": now(), "reason": str(exc)},
            )
    (store.manifests / "publication_queue.json").write_text(
        json.dumps(sorted(articles, key=lambda x: x["url"]), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return articles


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/restricted/dav"))
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    print(len(crawl(args.root, args.date)))
