"""Shared, deliberately conservative DAV acquisition primitives.

This module only contacts the three official DAV domains. Raw responses are
immutable content-addressed objects; derived records always retain their SHA.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

OFFICIAL_HOSTS = frozenset({"dav.gov.vn", "dichvucong.dav.gov.vn", "06dichvucong.dav.gov.vn"})
ATTACHMENT_EXTENSIONS = frozenset({".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".zip"})
USER_AGENT = "CLARA-Care DAV public-record research acquisition/1.0 (contact: research@clara.care)"
TIMEOUT_SECONDS = 25
MAX_RETRIES = 3


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
    if scheme != "https" or (parsed.hostname and parsed.hostname.lower() not in OFFICIAL_HOSTS):
        raise ValueError(f"non_official_dav_url:{url}")
    # Properly encode spaces and characters in URL path while preserving already escaped parts
    raw_path = unquote(parsed.path)
    quoted_path = quote(raw_path, safe="/:@&=+$,-_.!~*'()")
    return urlunparse((scheme, parsed.netloc.lower(), quoted_path, parsed.params, parsed.query, ""))


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._text: list[str] = []
        self._href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def links_from_html(payload: bytes, base_url: str) -> list[tuple[str, str]]:
    parser = Links()
    parser.feed(payload.decode("utf-8", errors="replace"))
    output: list[tuple[str, str]] = []
    for href, text in parser.links:
        candidate = urljoin(base_url, href)
        try:
            output.append((canonical_url(candidate), text))
        except ValueError:
            continue
    return output


def classify(title: str, url: str) -> str | None:
    text = f"{title} {url}".casefold()
    rules = {
        "withdrawals": ("thu hồi", "rút", "đình chỉ"),
        "renewals": ("gia hạn", "cấp lại", "renew"),
        "continued_validity": ("hiệu lực", "tiếp tục"),
        "amendments": ("thay đổi", "bổ sung", "điều chỉnh"),
        "corrections": ("đính chính", "sửa đổi", "correction"),
        "reference_drugs": ("thuốc tham chiếu", "biệt dược gốc"),
        "bioequivalence": ("tương đương sinh học", "sinh khả dụng"),
        "otc": ("không kê đơn", "otc"),
        "registration_publications": ("đăng ký lưu hành", "đăng ký thuốc", "cấp giấy đăng ký"),
    }
    return next(
        (kind for kind, words in rules.items() if any(word in text for word in words)), None
    )


def fetch(url: str) -> tuple[int, str, bytes, str]:
    """Fetch with bounded retries; callers persist both successful and failed receipts."""
    url = canonical_url(url)
    last_error = "unknown"
    for attempt in range(MAX_RETRIES):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.*,*/*",
                },
            )
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return (
                    response.status,
                    response.headers.get_content_type(),
                    response.read(),
                    response.url,
                )
        except HTTPError as exc:
            return exc.code, exc.headers.get_content_type() if exc.headers else "", exc.read(), url
        except (URLError, TimeoutError) as exc:
            last_error = str(exc)
            if attempt + 1 < MAX_RETRIES:
                time.sleep(2**attempt)
    raise RuntimeError(f"request_failed_after_retries:{last_error}")


class Store:
    def __init__(self, root: Path, retrieval_date: str) -> None:
        self.root = root
        self.date_root = root / "raw" / retrieval_date
        self.manifests = root / "manifests"
        self.manifests.mkdir(parents=True, exist_ok=True)
        self.date_root.mkdir(parents=True, exist_ok=True)

    def prior_receipt(self, url: str) -> dict[str, Any] | None:
        """Return an immutable successful receipt for this dated snapshot."""

        inventory = self.manifests / "source_inventory.jsonl"
        if not inventory.exists():
            return None
        canonical = canonical_url(url)
        for line in inventory.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("url") == canonical and row.get("http_status") == 200:
                raw_path = Path(str(row.get("raw_path", "")))
                if raw_path.is_file() and sha256(raw_path.read_bytes()) == row.get("sha256"):
                    return row
        return None

    def retain(
        self,
        *,
        bucket: str,
        url: str,
        payload: bytes,
        content_type: str,
        status: int,
        filename: str | None = None,
    ) -> dict[str, Any]:
        digest = sha256(payload)
        suffix = Path(filename or urlparse(url).path).suffix.lower()
        if not suffix or len(suffix) > 10:
            suffix = ".html" if "html" in content_type else ".bin"
        target = self.date_root / bucket / f"{digest}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != payload:
            raise RuntimeError("content_address_collision")
        if not target.exists():
            target.write_bytes(payload)
        return {
            "url": url,
            "raw_path": str(target),
            "sha256": digest,
            "bytes": len(payload),
            "http_status": status,
            "content_type": content_type,
            "retrieved_at_utc": now(),
        }

    def append(self, name: str, row: dict[str, Any]) -> None:
        with (self.manifests / name).open("a", encoding="utf-8") as file:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def decision_number(text: str) -> str | None:
    match = re.search(r"(?:số|so)\s*[:.]?\s*([0-9]+\s*/\s*[A-ZĐa-z-]+)", text, re.IGNORECASE)
    return re.sub(r"\s+", "", match.group(1)) if match else None


def registration_numbers(text: str) -> list[str]:
    matches = re.findall(
        r"\b(?:VD|VN|QLSP|GC|SĐK)\s*(?:-\s*)?[0-9]{2,6}(?:\s*-\s*[0-9]{2,4})?\b",
        text,
        re.IGNORECASE,
    )
    return sorted({re.sub(r"\s*-\s*", "-", value).upper() for value in matches})
