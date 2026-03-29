from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from .http_client import is_likely_pdf_url


def _extract_href_links(html: str, base_url: str) -> list[str]:
    pattern = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
    links: list[str] = []
    for raw_link in pattern.findall(html):
        link = raw_link.strip()
        if not link or link.startswith(("javascript:", "mailto:", "#")):
            continue
        absolute = urljoin(base_url, link)
        links.append(absolute)
    return links


def _extract_pdfjs_embedded_pdf(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    file_values = query.get("file") or []
    if not file_values:
        return None
    decoded = unquote(file_values[0]).strip()
    if decoded.startswith("http://") or decoded.startswith("https://"):
        return decoded
    return None


def discover_pdf_links(html: str, base_url: str, *, max_links: int) -> list[str]:
    links = _extract_href_links(html, base_url)
    candidates: list[str] = []
    seen: set[str] = set()

    for link in links:
        embedded = _extract_pdfjs_embedded_pdf(link)
        if embedded and is_likely_pdf_url(embedded):
            if embedded not in seen:
                seen.add(embedded)
                candidates.append(embedded)
            if len(candidates) >= max_links:
                break

        if is_likely_pdf_url(link) and link not in seen:
            seen.add(link)
            candidates.append(link)
            if len(candidates) >= max_links:
                break

    return candidates
