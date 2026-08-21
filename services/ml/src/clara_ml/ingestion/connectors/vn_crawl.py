"""Robots-respecting Vietnamese gap-fill HTML crawl connector (task 3.5).

``vn_crawl`` is the **only** HTML/crawl path in the ingestion plane; every other
source is API-first (task 3.4). It exists to fill coverage gaps the APIs cannot
reach (e.g. Vietnamese guidelines / Cục Quản lý Dược pages) and is deliberately
narrow and defensive (Requirement 6.2):

* **robots.txt is respected.** Before fetching a page, the connector loads the
  origin's ``robots.txt`` (through the same injectable HTTP client) and asks
  :class:`urllib.robotparser.RobotFileParser` whether the crawler user-agent may
  fetch the URL. Disallowed URLs are skipped. If ``robots.txt`` cannot be read,
  the connector fails *closed* and skips the URL.
* **An allow-list is enforced.** Every candidate URL's host must match a
  configured allowed-domains list (host or a subdomain of an allowed domain).
  The list is reused from the existing ``WEB_CRAWL_ALLOWED_DOMAINS`` setting in
  :mod:`clara_ml.config`; a per-source ``config_json['allowed_domains']`` (list
  or comma string) overrides it. An empty allow-list denies everything
  (secure-by-default).
* **Per-URL resilience.** A fetch/parse error on one URL never aborts the batch;
  the offending URL is skipped and the crawl continues.
* **Import-safe.** Importing this module opens no socket and builds no HTTP
  client — the client is created lazily by :class:`BaseSourceConnector` on first
  use, so robots/page fetches are fully injectable for tests.

Records are produced via :meth:`BaseSourceConnector.make_record` with
``doc_type='guideline'`` and ``lang='vi'`` by default, stamping the registry
``trust_tier`` (Requirement 6.4). Paging is the shared resumable offset-cursor
over the candidate-URL list (Requirement 6.5).
"""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from clara_ml.config import settings

from .base import BaseSourceConnector, ConnectorContext, FetchWindow, RawRecord

__all__ = ["VnCrawlConnector"]


# Tags whose contents are boilerplate/navigation and must not leak into the
# extracted main text.
_BOILERPLATE_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"\s+")


class VnCrawlConnector(BaseSourceConnector):
    """Gap-fill HTML connector that honours ``robots.txt`` and an allow-list.

    The candidate URLs come from ``config_json['seed_urls']`` (a list, or a
    comma/whitespace-separated string) and/or whitespace-separated URLs in
    :attr:`FetchWindow.query`. Each :meth:`fetch` call returns one resumable
    page of the de-duplicated URL list.
    """

    DEFAULT_USER_AGENT = "CLARA-ML-Crawler/0.1 (+robots-respecting)"

    def __init__(
        self,
        context: ConnectorContext,
        *,
        http_client_factory: Any | None = None,
        timeout_seconds: float = 10.0,
        user_agent: str | None = None,
    ) -> None:
        super().__init__(
            context,
            http_client_factory=http_client_factory,
            timeout_seconds=timeout_seconds,
        )
        cfg = context.config_json
        self._user_agent = (
            user_agent
            or str(cfg.get("user_agent") or "").strip()
            or self.DEFAULT_USER_AGENT
        )
        # robots_respect mirrors kb_source_registry.robots_respect; defaults on.
        self._respect_robots = bool(cfg.get("robots_respect", True))
        self._default_lang = str(cfg.get("lang") or "vi").strip() or "vi"
        self._doc_type = str(cfg.get("doc_type") or "guideline").strip() or "guideline"
        max_chars = cfg.get("max_chars")
        self._max_chars = int(max_chars) if isinstance(max_chars, int) and max_chars > 0 else 0
        self._allowed_domains = self._resolve_allowed_domains()
        # Per-origin robots cache so we read robots.txt at most once per host.
        self._robots_cache: dict[str, RobotFileParser | None] = {}

    # -- contract ----------------------------------------------------------

    def fetch(
        self,
        window: FetchWindow,
        cursor: str | None = None,
    ) -> tuple[list[RawRecord], str | None]:
        """Crawl one resumable page of candidate URLs.

        Off-allow-list hosts and robots-disallowed URLs are skipped; per-URL
        fetch/parse failures are swallowed so the batch never crashes
        (Requirement 6.2). The returned cursor advances over the URL list — not
        the surfaced records — so resuming never reprocesses skipped URLs
        (Requirement 6.5).
        """

        urls = self._candidate_urls(window)
        if not urls:
            return [], None

        offset = self.decode_offset_cursor(cursor)
        page_size = self.resolve_page_size(window)
        page = urls[offset : offset + page_size]

        records: list[RawRecord] = []
        for url in page:
            record = self._fetch_one(url)
            if record is not None:
                records.append(record)

        next_cursor = self.next_offset_cursor(
            offset=offset,
            page_size=page_size,
            fetched=len(page),
        )
        return records, next_cursor

    # -- candidate URLs ----------------------------------------------------

    def _candidate_urls(self, window: FetchWindow) -> list[str]:
        raw = self.context.config_json.get("seed_urls")
        if raw is None:
            raw = self.context.config_json.get("urls")

        collected: list[str] = []
        if isinstance(raw, str):
            collected.extend(self._split_urls(raw))
        elif isinstance(raw, (list, tuple, set)):
            collected.extend(str(item).strip() for item in raw)
        if window.query:
            collected.extend(self._split_urls(window.query))

        seen: set[str] = set()
        ordered: list[str] = []
        for url in collected:
            url = url.strip()
            if url and url not in seen:
                seen.add(url)
                ordered.append(url)
        return ordered

    @staticmethod
    def _split_urls(value: str) -> list[str]:
        return [item for item in re.split(r"[\s,]+", str(value or "")) if item]

    # -- per-URL fetch -----------------------------------------------------

    def _fetch_one(self, url: str) -> RawRecord | None:
        try:
            if not self._is_domain_allowed(url):
                return None
            if not self._is_allowed_by_robots(url):
                return None
            page_html = self._get_text(url)
            if not page_html:
                return None
            title, body = self._extract_main_text(page_html)
            if not body.strip():
                return None
            return self.make_record(
                external_id=self._url_hash(url),
                raw_text=body,
                title=title,
                url=url,
                lang=self._default_lang,
                doc_type=self._doc_type,
                effective_date=None,
            )
        except Exception:
            # Per-URL resilience: a single bad page must not abort the batch.
            return None

    def _get_text(self, url: str) -> str:
        response = self.http_client().get(url)
        status = int(getattr(response, "status_code", 200) or 200)
        if status >= 400:
            return ""
        return getattr(response, "text", "") or ""

    # -- allow-list enforcement -------------------------------------------

    def _resolve_allowed_domains(self) -> set[str]:
        """Resolve the allow-list, preferring a per-source override.

        ``config_json['allowed_domains']`` (list or comma string) wins when
        present; otherwise the global ``WEB_CRAWL_ALLOWED_DOMAINS`` setting from
        :mod:`clara_ml.config` is reused.
        """

        raw = self.context.config_json.get("allowed_domains")
        if raw is None:
            raw = settings.web_crawl_allowed_domains

        if isinstance(raw, str):
            items: list[str] = raw.split(",")
        elif isinstance(raw, (list, tuple, set)):
            items = [str(item) for item in raw]
        else:
            items = []
        return {item.strip().lower() for item in items if item and item.strip()}

    def _is_domain_allowed(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").strip().lower()
        if not host:
            return False
        if not self._allowed_domains:
            # Secure-by-default: an empty allow-list denies every host.
            return False
        if host in self._allowed_domains:
            return True
        return any(host.endswith(f".{domain}") for domain in self._allowed_domains)

    # -- robots.txt enforcement -------------------------------------------

    def _is_allowed_by_robots(self, url: str) -> bool:
        if not self._respect_robots:
            return True
        parser = self._robots_parser_for(url)
        if parser is None:
            # Could not determine the rules -> fail closed and skip.
            return False
        try:
            return bool(parser.can_fetch(self._user_agent, url))
        except Exception:
            return False

    def _robots_parser_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        host = parsed.netloc
        if not host:
            return None
        scheme = parsed.scheme or "https"
        origin = f"{scheme}://{host}"
        if origin in self._robots_cache:
            return self._robots_cache[origin]
        parser = self._load_robots(origin)
        self._robots_cache[origin] = parser
        return parser

    def _load_robots(self, origin: str) -> RobotFileParser | None:
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = self.http_client().get(robots_url)
        except Exception:
            # Network/transport failure reading robots.txt -> fail closed.
            return None

        status = int(getattr(response, "status_code", 200) or 200)
        if status in (401, 403):
            # Unauthorized/forbidden robots.txt -> treat the whole site as off-limits.
            parser.disallow_all = True  # type: ignore[attr-defined]
            return parser
        if status >= 400:
            # Missing robots.txt (e.g. 404) -> standard convention allows all.
            parser.allow_all = True  # type: ignore[attr-defined]
            return parser

        body = getattr(response, "text", "") or ""
        parser.parse(body.splitlines())
        return parser

    # -- HTML main-text extraction ----------------------------------------

    def _extract_main_text(self, raw_html: str) -> tuple[str, str]:
        title = self._extract_title(raw_html)

        body = raw_html
        for tag in _BOILERPLATE_TAGS:
            body = re.sub(
                rf"(?is)<{tag}\b.*?>.*?</{tag}>",
                " ",
                body,
            )
        # Drop HTML comments, then all remaining tags.
        body = re.sub(r"(?s)<!--.*?-->", " ", body)
        body = re.sub(r"(?s)<[^>]+>", " ", body)
        body = html.unescape(body)
        body = _WS_RE.sub(" ", body).strip()
        if self._max_chars > 0:
            body = body[: self._max_chars]
        return title, body

    @staticmethod
    def _extract_title(raw_html: str) -> str:
        match = _TITLE_RE.search(raw_html) or _H1_RE.search(raw_html)
        if not match:
            return ""
        title = html.unescape(re.sub(r"(?s)<[^>]+>", " ", match.group(1)))
        return _WS_RE.sub(" ", title).strip()

    # -- misc --------------------------------------------------------------

    @staticmethod
    def _url_hash(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()
