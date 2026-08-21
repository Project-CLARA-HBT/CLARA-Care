"""Unit tests for ``vn_crawl`` robots.txt + allowed-domains enforcement.

Feature: rag-knowledge-pipeline, task 3.6 (optional unit-test task).

``VnCrawlConnector`` is the *only* HTML/crawl path in the ingestion plane and is
deliberately defensive (Requirement 6.2). These tests pin three guarantees,
with the HTTP transport fully injected (no real network):

1. **robots.txt is respected** — a URL disallowed by the origin's ``robots.txt``
   is never fetched (no page GET is issued for it) and yields no record, while a
   sibling URL allowed by the same ``robots.txt`` is fetched and surfaced.
2. **allowed-domains is enforced** — a URL whose host is outside the configured
   allow-list is rejected *before* any network I/O: neither its page nor its
   origin's ``robots.txt`` is ever requested.
3. **only the HTML path is taken** — the connector reaches content purely by
   HTTP-GETting HTML (robots.txt + page), extracting main text from the markup;
   it issues no API-style call and stamps ``doc_type='guideline'`` / ``lang='vi'``.

_Requirements: 6.2_
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from clara_ml.ingestion.connectors.base import ConnectorContext, FetchWindow
from clara_ml.ingestion.connectors.vn_crawl import VnCrawlConnector

# ---------------------------------------------------------------------------
# Injected HTTP transport doubles (no real sockets)
# ---------------------------------------------------------------------------


class FakeResponse:
    """Minimal stand-in for an ``httpx.Response`` (only the fields used)."""

    def __init__(self, *, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class RecordingHttpClient:
    """Fake HTTP client that records every ``get`` and serves canned responses.

    ``responses`` maps an exact URL to the :class:`FakeResponse` to return. Any
    URL not present returns a 404 (so an unexpected fetch is visibly "missing").
    Every requested URL is appended to :attr:`requested_urls` so tests can assert
    exactly which network calls happened.
    """

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self._responses = responses
        self.requested_urls: list[str] = []

    def get(self, url: str) -> FakeResponse:
        self.requested_urls.append(url)
        return self._responses.get(url, FakeResponse(status_code=404, text=""))

    def close(self) -> None:  # pragma: no cover - parity with httpx.Client
        pass


def _make_connector(
    *,
    responses: dict[str, FakeResponse],
    config_json: dict,
) -> tuple[VnCrawlConnector, RecordingHttpClient]:
    client = RecordingHttpClient(responses)
    context = ConnectorContext(
        source_key="vn_dav",
        trust_tier=2,
        license_code="public",
        attribution="Cục Quản lý Dược",
        base_url="https://kcb.vn",
        config_json=config_json,
    )
    connector = VnCrawlConnector(
        context,
        http_client_factory=lambda: client,
    )
    return connector, client


_PAGE_HTML = (
    "<html><head><title>Hướng dẫn điều trị</title></head>"
    "<body><nav>bỏ qua điều hướng</nav>"
    "<p>Phác đồ điều trị tăng huyết áp theo Bộ Y tế.</p>"
    "</body></html>"
)


# ---------------------------------------------------------------------------
# 1. robots.txt is respected — disallowed URLs are NOT fetched
# ---------------------------------------------------------------------------


def test_robots_disallowed_url_is_not_fetched() -> None:
    allowed_url = "https://kcb.vn/public/guideline"
    disallowed_url = "https://kcb.vn/private/secret"
    robots_url = "https://kcb.vn/robots.txt"

    responses = {
        robots_url: FakeResponse(
            status_code=200,
            text="User-agent: *\nDisallow: /private\n",
        ),
        allowed_url: FakeResponse(status_code=200, text=_PAGE_HTML),
        disallowed_url: FakeResponse(status_code=200, text=_PAGE_HTML),
    }
    connector, client = _make_connector(
        responses=responses,
        config_json={
            "allowed_domains": ["kcb.vn"],
            "seed_urls": [allowed_url, disallowed_url],
        },
    )

    records, _ = connector.fetch(FetchWindow(page_size=10))

    # The robots-disallowed page must never be fetched...
    assert disallowed_url not in client.requested_urls
    # ...yet robots.txt and the allowed page were.
    assert robots_url in client.requested_urls
    assert allowed_url in client.requested_urls

    # Only the allowed URL surfaces a record.
    assert [r.url for r in records] == [allowed_url]


def test_robots_unreadable_fails_closed() -> None:
    """When robots.txt is forbidden (403), the whole origin is treated off-limits."""

    page_url = "https://kcb.vn/public/guideline"
    robots_url = "https://kcb.vn/robots.txt"

    responses = {
        robots_url: FakeResponse(status_code=403, text=""),
        page_url: FakeResponse(status_code=200, text=_PAGE_HTML),
    }
    connector, client = _make_connector(
        responses=responses,
        config_json={"allowed_domains": ["kcb.vn"], "seed_urls": [page_url]},
    )

    records, _ = connector.fetch(FetchWindow(page_size=10))

    assert records == []
    # robots.txt was consulted; the page itself was never fetched (fail closed).
    assert robots_url in client.requested_urls
    assert page_url not in client.requested_urls


# ---------------------------------------------------------------------------
# 2. allowed-domains is enforced — off-list URLs are rejected before I/O
# ---------------------------------------------------------------------------


def test_off_allowlist_url_is_rejected_without_network() -> None:
    on_list_url = "https://kcb.vn/public/guideline"
    off_list_url = "https://evil.example/public/guideline"
    kcb_robots = "https://kcb.vn/robots.txt"
    evil_robots = "https://evil.example/robots.txt"

    responses = {
        kcb_robots: FakeResponse(status_code=200, text="User-agent: *\nAllow: /\n"),
        on_list_url: FakeResponse(status_code=200, text=_PAGE_HTML),
        # Provide responses for the evil host too; the connector must never use them.
        evil_robots: FakeResponse(status_code=200, text="User-agent: *\nAllow: /\n"),
        off_list_url: FakeResponse(status_code=200, text=_PAGE_HTML),
    }
    connector, client = _make_connector(
        responses=responses,
        config_json={
            "allowed_domains": ["kcb.vn"],
            "seed_urls": [on_list_url, off_list_url],
        },
    )

    records, _ = connector.fetch(FetchWindow(page_size=10))

    # Off-allow-list host: neither its page nor its robots.txt is ever requested.
    assert off_list_url not in client.requested_urls
    assert evil_robots not in client.requested_urls

    # Only the in-allow-list URL is surfaced.
    assert [r.url for r in records] == [on_list_url]


def test_empty_allowlist_denies_everything() -> None:
    """Secure-by-default: an empty allow-list rejects every host, no I/O."""

    page_url = "https://kcb.vn/public/guideline"
    connector, client = _make_connector(
        responses={page_url: FakeResponse(status_code=200, text=_PAGE_HTML)},
        config_json={"allowed_domains": [], "seed_urls": [page_url]},
    )

    records, _ = connector.fetch(FetchWindow(page_size=10))

    assert records == []
    assert client.requested_urls == []


def test_subdomain_of_allowed_domain_is_accepted() -> None:
    sub_url = "https://moh.kcb.vn/public/guideline"
    robots_url = "https://moh.kcb.vn/robots.txt"

    responses = {
        robots_url: FakeResponse(status_code=200, text="User-agent: *\nAllow: /\n"),
        sub_url: FakeResponse(status_code=200, text=_PAGE_HTML),
    }
    connector, _ = _make_connector(
        responses=responses,
        config_json={"allowed_domains": ["kcb.vn"], "seed_urls": [sub_url]},
    )

    records, _ = connector.fetch(FetchWindow(page_size=10))

    assert [r.url for r in records] == [sub_url]


# ---------------------------------------------------------------------------
# 3. only the HTML path is taken
# ---------------------------------------------------------------------------


def test_only_html_path_is_taken() -> None:
    page_url = "https://kcb.vn/public/guideline"
    robots_url = "https://kcb.vn/robots.txt"

    responses = {
        robots_url: FakeResponse(status_code=200, text="User-agent: *\nAllow: /\n"),
        page_url: FakeResponse(status_code=200, text=_PAGE_HTML),
    }
    connector, client = _make_connector(
        responses=responses,
        config_json={"allowed_domains": ["kcb.vn"], "seed_urls": [page_url]},
    )

    records, _ = connector.fetch(FetchWindow(page_size=10))

    assert len(records) == 1
    record = records[0]

    # Content was obtained by extracting main text from HTML markup...
    assert record.title == "Hướng dẫn điều trị"
    assert "Phác đồ điều trị tăng huyết áp" in record.raw_text
    # ...boilerplate/navigation is stripped, not surfaced.
    assert "bỏ qua điều hướng" not in record.raw_text
    # HTML connector defaults: Vietnamese guideline provenance, registry tier.
    assert record.doc_type == "guideline"
    assert record.lang == "vi"
    assert record.trust_tier == 2
    assert record.source_key == "vn_dav"

    # Every network call was a plain HTTP(S) GET of either robots.txt or the
    # HTML page — there is no API-style endpoint on this path.
    assert set(client.requested_urls) == {robots_url, page_url}
    for url in client.requested_urls:
        scheme = urlparse(url).scheme
        assert scheme in {"http", "https"}
    assert any(u.endswith("/robots.txt") for u in client.requested_urls)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
