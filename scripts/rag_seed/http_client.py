from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class HttpClient:
    def __init__(self, *, timeout_seconds: float, sleep_seconds: float) -> None:
        self.timeout_seconds = max(timeout_seconds, 0.5)
        self.sleep_seconds = max(sleep_seconds, 0.0)

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "User-Agent": "CLARA-RAG-Seed/1.0 (+https://github.com/Project-CLARA-HBT/CLARA-Care)",
            "Accept": "*/*",
        }

    def get_bytes(self, url: str) -> tuple[bytes, str]:
        request = Request(url, headers=self._headers())
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read()
            content_type = (
                str(response.headers.get("Content-Type") or "").strip().lower()
            )
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        return body, content_type

    def get_text(self, url: str) -> str:
        body, _ = self.get_bytes(url)
        return body.decode("utf-8", errors="ignore")


def normalize_url_candidates(raw_text: str) -> list[str]:
    pattern = re.compile(r"https?://[^\s<>\")']+")
    candidates = []
    for match in pattern.findall(raw_text):
        cleaned = match.rstrip(".,;:!?)\"'")
        if cleaned:
            candidates.append(cleaned)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def is_likely_pdf_url(url: str) -> bool:
    lowered = url.lower()
    return (
        lowered.endswith(".pdf")
        or ".pdf?" in lowered
        or "/download/" in lowered
        or "/getfile/" in lowered
        or "pdfjsviewer" in lowered
    )


def within_domain(url: str, allowed_hosts: Iterable[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == item or host.endswith(f".{item}") for item in allowed_hosts)


def write_pdf_file(
    dest_dir: Path, *, source_id: str, download_url: str, payload: bytes
) -> tuple[Path, str]:
    digest = hashlib.sha256(payload).hexdigest()
    safe_source = source_id.lower().replace("/", "-")
    file_name = f"{safe_source}-{digest[:12]}.pdf"
    file_path = dest_dir / safe_source / file_name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(payload)
    return file_path, digest
