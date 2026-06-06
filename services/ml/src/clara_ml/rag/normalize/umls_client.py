"""License-aware, cached UTS / RxNorm REST client (task 7.1).

``UmlsClient`` is the shared lookup surface the entity linker (task 7.2) and the
knowledge-graph builder (task 8.1) build on. It wraps two upstream services:

* **RxNorm REST** (``https://rxnav.nlm.nih.gov/REST``) — the public RxNav API.
  Needs **no API key**. Used for concept search, synonyms (brand/generic), and
  relationship traversal.
* **UMLS Metathesaurus** (``https://uts-ws.nlm.nih.gov/rest``) — the licensed
  UTS REST API. Needs the **UTS API key**. Used to resolve a free-text mention
  to a UMLS Concept Unique Identifier (CUI).

Design contract (Requirements 9.4, 15.3):

* **License-aware.** The UTS key is read from config/env, never hard-coded. The
  UMLS Metathesaurus is only called when a key is present (licensed access);
  RxNorm is always callable because it is public. Required source attribution
  is recorded on the client (:attr:`LICENSE_ATTRIBUTIONS`) so callers can honour
  RxNorm/UMLS licensing obligations when persisting derived data (Req 15.3).
* **Graceful degradation.** Every public method is total: on rate-limit (429),
  unauthorized (401/403), not-found (404), any 5xx, a network error, or a
  malformed payload, the method returns an *empty* result (``[]`` / ``None``)
  rather than raising. This lets the entity linker / query expander fall back to
  recall-only behavior with the original query terms intact (Requirement 9.4).
* **Cached + idempotent.** Lookups are memoized in an injectable, clearable,
  bounded in-memory cache so repeated calls are cheap and return identical
  results without re-hitting the network.
* **Import-safe.** Importing this module opens no socket and builds no HTTP
  client. The :mod:`httpx` client is created lazily on first request, and an
  injected client/factory (used in tests) takes precedence — so the whole
  surface is verifiable with a fake client and no live network.
"""

from __future__ import annotations

import logging
import os
from collections import OrderedDict
from collections.abc import MutableMapping
from typing import Any

from clara_ml.config import settings

logger = logging.getLogger(__name__)

__all__ = ["UmlsClient"]

# ---------------------------------------------------------------------------
# Endpoints + tuning
# ---------------------------------------------------------------------------

_RXNORM_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
_UTS_BASE_URL = "https://uts-ws.nlm.nih.gov/rest"

# HTTP statuses treated as "no result" rather than an error (graceful).
# 401/403 = unauthorized/licensing, 404 = not found, 429 = rate-limited.
_SOFT_STATUSES = frozenset({400, 401, 403, 404, 429})

_DEFAULT_TIMEOUT_SECONDS = 4.0
_DEFAULT_CACHE_MAX_ENTRIES = 4096

# RxNorm term-type (TTY) → synonym kind classification.
_BRAND_TTYS = frozenset({"BN", "SBD", "SBDC", "SBDF", "SBDG", "BPCK"})
_GENERIC_TTYS = frozenset(
    {"IN", "PIN", "MIN", "SCD", "SCDC", "SCDF", "SCDG", "GPCK"}
)

# Required attribution strings per source vocabulary (license-aware, Req 15.3).
# Callers persisting derived entities record these alongside the data.
LICENSE_ATTRIBUTIONS: dict[str, str] = {
    "RXNORM": (
        "This product uses publicly available data courtesy of the U.S. National "
        "Library of Medicine (NLM), National Institutes of Health, RxNorm. It is "
        "not endorsed or certified by NLM."
    ),
    "UMLS": (
        "This product uses the UMLS Metathesaurus courtesy of the U.S. National "
        "Library of Medicine (NLM) under a UMLS Metathesaurus License."
    ),
}


# ---------------------------------------------------------------------------
# Small, self-contained parsing helpers (network-free)
# ---------------------------------------------------------------------------


def _coerce_str(value: Any) -> str:
    """Coerce ``value`` to a trimmed string, taking the first item of a list."""

    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return _coerce_str(value[0]) if value else ""
    return str(value).strip()


def _as_list(value: Any) -> list[Any]:
    """Return ``value`` as a list (RxNav fields are sometimes scalars)."""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _classify_tty(tty: str) -> str:
    """Map an RxNorm TTY to a synonym ``kind`` (brand / generic / synonym)."""

    upper = (tty or "").strip().upper()
    if upper in _BRAND_TTYS:
        return "brand"
    if upper in _GENERIC_TTYS:
        return "generic"
    return "synonym"


def _resolve_umls_api_key() -> str:
    """Resolve the UTS API key from config then environment (never hard-coded).

    The ``services/ml`` settings object has no dedicated ``umls_api_key`` field
    today, so this reads ``getattr(settings, 'umls_api_key', '')`` first (future
    proof, in case the field is added) and falls back to the ``UMLS_API_KEY``
    environment variable. Returns ``""`` when no key is configured, which keeps
    the UMLS Metathesaurus calls disabled (RxNorm still works without a key).
    """

    configured = _coerce_str(getattr(settings, "umls_api_key", ""))
    if configured:
        return configured
    return _coerce_str(os.environ.get("UMLS_API_KEY", ""))


class UmlsClient:
    """Cached, graceful UTS / RxNorm lookup surface.

    Public method surface (intentionally small and documented):

    * :meth:`search_rxnorm(name)` → ``list[concept]`` where each concept is
      ``{"rxcui", "name", "tty", "synonym"}``.
    * :meth:`rxcui_for(name)` → ``str | None`` exact RxCUI for a name.
    * :meth:`rxcui_synonyms(rxcui)` → ``list[{"name", "lang", "kind"}]``
      (brand/generic/synonym variants).
    * :meth:`umls_cui_for(name)` → ``str | None`` (UMLS CUI; needs the UTS key).
    * :meth:`related_rxcui(rxcui, relation)` → ``list[str]`` of related RxCUIs.

    All methods are total and never raise on upstream failure (Requirement 9.4).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        rxnorm_base_url: str | None = None,
        uts_base_url: str | None = None,
        http_client: Any | None = None,
        http_client_factory: Any | None = None,
        cache: MutableMapping[str, Any] | None = None,
        cache_max_entries: int = _DEFAULT_CACHE_MAX_ENTRIES,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        # License key: explicit arg wins, else resolve from config/env.
        self._api_key = _coerce_str(api_key) if api_key is not None else _resolve_umls_api_key()
        self._rxnorm_base = (rxnorm_base_url or _RXNORM_BASE_URL).rstrip("/")
        self._uts_base = (uts_base_url or _UTS_BASE_URL).rstrip("/")
        self._timeout_seconds = max(float(timeout_seconds), 0.1)

        # Lazy HTTP: an injected client (tests) wins; otherwise a factory builds
        # one on first use. Nothing is created at construction time.
        self._injected_client = http_client
        self._http_client_factory = http_client_factory
        self._owned_client: Any | None = None

        # Injectable, clearable, bounded cache (insertion-ordered eviction).
        self._cache: MutableMapping[str, Any] = cache if cache is not None else OrderedDict()
        self._cache_max_entries = max(int(cache_max_entries), 1)

    # ------------------------------------------------------------------
    # License / capability introspection (Requirement 15.3)
    # ------------------------------------------------------------------

    @property
    def umls_available(self) -> bool:
        """True when a UTS key is configured (UMLS Metathesaurus is licensed)."""

        return bool(self._api_key)

    @staticmethod
    def required_attribution(vocab: str) -> str:
        """Return the required attribution string for a source vocabulary.

        ``vocab`` is matched case-insensitively against ``{"RXNORM", "UMLS"}``;
        an unknown vocabulary returns ``""`` so callers can default safely.
        """

        return LICENSE_ATTRIBUTIONS.get((vocab or "").strip().upper(), "")

    # ------------------------------------------------------------------
    # Cache management (injectable / clearable)
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Drop all memoized lookups."""

        self._cache.clear()

    def _cache_get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = value
        # Bound the cache: evict the oldest entry (insertion order) when over
        # capacity. Works for both ``OrderedDict`` and a plain ``dict``.
        while len(self._cache) > self._cache_max_entries:
            try:
                oldest = next(iter(self._cache))
            except StopIteration:  # pragma: no cover - empty mapping
                break
            self._cache.pop(oldest, None)

    # ------------------------------------------------------------------
    # Lazy HTTP + resilient request boundary
    # ------------------------------------------------------------------

    def _client(self) -> Any:
        """Return the HTTP client, constructing one lazily if needed."""

        if self._injected_client is not None:
            return self._injected_client
        if self._owned_client is None:
            if self._http_client_factory is not None:
                self._owned_client = self._http_client_factory()
            else:
                import httpx  # local import keeps module import network-free

                self._owned_client = httpx.Client(timeout=self._timeout_seconds)
        return self._owned_client

    def _request_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any | None:
        """``GET`` ``url`` and return parsed JSON, or ``None`` on any failure.

        This is the single resilience boundary: soft HTTP statuses
        (``_SOFT_STATUSES``, incl. 401/403/429), any other non-2xx status, a
        transport/network error, and any JSON-decode error all collapse to
        ``None``. Nothing escapes as an exception (Requirement 9.4).
        """

        try:
            response = self._client().get(url, params=params or {}, headers=self._headers())
        except Exception as exc:  # network/transport error → graceful empty
            logger.debug("umls_request_failed url=%s err=%s", url, type(exc).__name__)
            return None

        status = getattr(response, "status_code", 0)
        if status in _SOFT_STATUSES:
            logger.debug("umls_soft_status url=%s status=%s", url, status)
            return None
        if not (200 <= int(status or 0) < 300):
            logger.debug("umls_bad_status url=%s status=%s", url, status)
            return None

        try:
            return response.json()
        except Exception as exc:  # malformed payload → graceful empty
            logger.debug("umls_decode_failed url=%s err=%s", url, type(exc).__name__)
            return None

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"Accept": "application/json", "User-Agent": "CLARA-ML/0.1"}

    def close(self) -> None:
        """Close the owned HTTP client if one was created (no-op otherwise)."""

        if self._owned_client is not None:
            close = getattr(self._owned_client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # pragma: no cover - defensive
                    pass
            self._owned_client = None

    def __enter__(self) -> "UmlsClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # RxNorm REST (public, no key required)
    # ------------------------------------------------------------------

    def search_rxnorm(self, name: str) -> list[dict[str, str]]:
        """Resolve a drug name to RxNorm concepts via ``/drugs.json``.

        Returns a de-duplicated list of concept dicts
        ``{"rxcui", "name", "tty", "synonym"}``. Returns ``[]`` for an empty
        name or any upstream failure (graceful, Requirement 9.4). Results are
        cached so repeated searches are idempotent and cheap.
        """

        term = _coerce_str(name)
        if not term:
            return []

        cache_key = f"search_rxnorm:{term.lower()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]

        payload = self._request_json(f"{self._rxnorm_base}/drugs.json", {"name": term})
        concepts = self._parse_drug_concepts(payload)
        self._cache_set(cache_key, concepts)
        return [dict(item) for item in concepts]

    def rxcui_for(self, name: str) -> str | None:
        """Return the exact RxCUI for ``name`` via ``/rxcui.json`` (or ``None``).

        Falls back to ``None`` on no match or any upstream failure. Cached.
        """

        term = _coerce_str(name)
        if not term:
            return None

        cache_key = f"rxcui_for:{term.lower()}"
        if cache_key in self._cache:
            return self._cache_get(cache_key)

        payload = self._request_json(f"{self._rxnorm_base}/rxcui.json", {"name": term})
        rxcui: str | None = None
        if isinstance(payload, dict):
            id_group = payload.get("idGroup")
            if isinstance(id_group, dict):
                ids = _as_list(id_group.get("rxnormId"))
                for candidate in ids:
                    value = _coerce_str(candidate)
                    if value:
                        rxcui = value
                        break
        self._cache_set(cache_key, rxcui)
        return rxcui

    def rxcui_synonyms(self, rxcui: str) -> list[dict[str, str]]:
        """Return brand/generic/synonym names related to ``rxcui``.

        Uses ``/rxcui/{rxcui}/allrelated.json`` and classifies each related
        concept's term type (TTY) into a ``kind`` of ``"brand"``/``"generic"``/
        ``"synonym"``. Each item is ``{"name", "lang", "kind"}`` with ``lang``
        defaulting to ``"en"`` (RxNorm is English). Returns ``[]`` on any
        failure. Cached and de-duplicated by ``(name, kind)``.
        """

        key = _coerce_str(rxcui)
        if not key:
            return []

        cache_key = f"rxcui_synonyms:{key}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]

        payload = self._request_json(f"{self._rxnorm_base}/rxcui/{key}/allrelated.json")
        synonyms = self._parse_related_synonyms(payload)
        self._cache_set(cache_key, synonyms)
        return [dict(item) for item in synonyms]

    def related_rxcui(self, rxcui: str, relation: str) -> list[str]:
        """Return RxCUIs related to ``rxcui`` by an RxNorm relationship.

        ``relation`` is an RxNorm ``rela`` value (e.g. ``"has_tradename"``,
        ``"tradename_of"``, ``"consists_of"``, ``"ingredient_of"``). Used by the
        graph builder (task 8.1) to materialize drug-relationship edges. Returns
        ``[]`` on an empty argument or any upstream failure. Cached, ordered,
        de-duplicated.
        """

        key = _coerce_str(rxcui)
        rela = _coerce_str(relation)
        if not key or not rela:
            return []

        cache_key = f"related_rxcui:{key}:{rela.lower()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return list(cached)

        payload = self._request_json(
            f"{self._rxnorm_base}/rxcui/{key}/related.json", {"rela": rela}
        )
        related = self._parse_related_rxcui(payload)
        self._cache_set(cache_key, related)
        return list(related)

    # ------------------------------------------------------------------
    # UMLS Metathesaurus (UTS — licensed, key required)
    # ------------------------------------------------------------------

    def umls_cui_for(self, name: str) -> str | None:
        """Return the first UMLS CUI for ``name`` via the UTS search API.

        Requires a configured UTS API key (licensed access). When no key is
        present this returns ``None`` **without any network call** (license-aware
        gating). Also returns ``None`` on no match or any upstream failure
        (rate-limit/unauthorized/unavailable — Requirement 9.4). Cached.
        """

        term = _coerce_str(name)
        if not term:
            return None
        if not self._api_key:
            # License-aware: do not call the licensed endpoint without a key.
            return None

        cache_key = f"umls_cui_for:{term.lower()}"
        if cache_key in self._cache:
            return self._cache_get(cache_key)

        payload = self._request_json(
            f"{self._uts_base}/search/current",
            {"string": term, "apiKey": self._api_key, "pageSize": 1},
        )
        cui = self._parse_first_cui(payload)
        self._cache_set(cache_key, cui)
        return cui

    # ------------------------------------------------------------------
    # Payload parsers (resilient — tolerate missing / mis-typed fields)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_drug_concepts(payload: Any) -> list[dict[str, str]]:
        if not isinstance(payload, dict):
            return []
        drug_group = payload.get("drugGroup")
        if not isinstance(drug_group, dict):
            return []
        groups = drug_group.get("conceptGroup")
        if not isinstance(groups, list):
            return []

        concepts: list[dict[str, str]] = []
        seen: set[str] = set()
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_tty = _coerce_str(group.get("tty"))
            properties = group.get("conceptProperties")
            if not isinstance(properties, list):
                continue
            for prop in properties:
                if not isinstance(prop, dict):
                    continue
                rxcui = _coerce_str(prop.get("rxcui"))
                name = _coerce_str(prop.get("name"))
                if not rxcui and not name:
                    continue
                dedupe_key = (rxcui or name).lower()
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                concepts.append(
                    {
                        "rxcui": rxcui,
                        "name": name,
                        "tty": _coerce_str(prop.get("tty")) or group_tty,
                        "synonym": _coerce_str(prop.get("synonym")),
                    }
                )
        return concepts

    @staticmethod
    def _parse_related_synonyms(payload: Any) -> list[dict[str, str]]:
        if not isinstance(payload, dict):
            return []
        related_group = payload.get("allRelatedGroup")
        if not isinstance(related_group, dict):
            return []
        groups = related_group.get("conceptGroup")
        if not isinstance(groups, list):
            return []

        synonyms: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for group in groups:
            if not isinstance(group, dict):
                continue
            kind = _classify_tty(_coerce_str(group.get("tty")))
            properties = group.get("conceptProperties")
            if not isinstance(properties, list):
                continue
            for prop in properties:
                if not isinstance(prop, dict):
                    continue
                name = _coerce_str(prop.get("name"))
                if not name:
                    continue
                dedupe_key = (name.lower(), kind)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                synonyms.append({"name": name, "lang": "en", "kind": kind})
        return synonyms

    @staticmethod
    def _parse_related_rxcui(payload: Any) -> list[str]:
        if not isinstance(payload, dict):
            return []
        related_group = payload.get("relatedGroup")
        if not isinstance(related_group, dict):
            return []
        groups = related_group.get("conceptGroup")
        if not isinstance(groups, list):
            return []

        rxcuis: list[str] = []
        seen: set[str] = set()
        for group in groups:
            if not isinstance(group, dict):
                continue
            properties = group.get("conceptProperties")
            if not isinstance(properties, list):
                continue
            for prop in properties:
                if not isinstance(prop, dict):
                    continue
                rxcui = _coerce_str(prop.get("rxcui"))
                if rxcui and rxcui not in seen:
                    seen.add(rxcui)
                    rxcuis.append(rxcui)
        return rxcuis

    @staticmethod
    def _parse_first_cui(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        results = result.get("results")
        if not isinstance(results, list):
            return None
        for item in results:
            if not isinstance(item, dict):
                continue
            ui = _coerce_str(item.get("ui"))
            if ui and ui.upper() != "NONE":
                return ui
        return None
