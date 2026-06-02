from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clara_api.api.v1.endpoints.research import _fetch_source_hub_records
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.schemas import SourceHubSourceKey

router = APIRouter()

_ALL_SEARCH_SOURCES: tuple[SourceHubSourceKey, ...] = (
    "pubmed",
    "rxnorm",
    "openfda",
    "dailymed",
    "europepmc",
    "semantic_scholar",
    "clinicaltrials",
    "davidrug",
)
_PER_SOURCE_LIMIT_MIN = 1
_PER_SOURCE_LIMIT_MAX = 30
_TOTAL_LIMIT_MIN = 1
_TOTAL_LIMIT_MAX = 200
_PER_SOURCE_TIMEOUT_SECONDS = 15.0


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    sources: list[SourceHubSourceKey] | None = None
    per_source_limit: int = Field(default=8, ge=1, le=100)
    total_limit: int = Field(default=60, ge=1, le=500)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _resolve_sources(raw_sources: list[SourceHubSourceKey] | None) -> list[SourceHubSourceKey]:
    if not raw_sources:
        return list(_ALL_SEARCH_SOURCES)

    # Keep user order while removing duplicates.
    seen: set[SourceHubSourceKey] = set()
    resolved: list[SourceHubSourceKey] = []
    for source in raw_sources:
        if source in seen:
            continue
        seen.add(source)
        resolved.append(source)
    return resolved or list(_ALL_SEARCH_SOURCES)


def _serialize_result(record: Any) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        data = record.model_dump()
    elif isinstance(record, dict):
        data = record
    else:
        data = {}
    return {
        "id": str(data.get("id") or ""),
        "title": str(data.get("title") or ""),
        "url": data.get("url"),
        "snippet": data.get("snippet"),
        "source": str(data.get("source") or ""),
        "external_id": data.get("external_id"),
        "published_at": data.get("published_at"),
    }


def _search_source_with_timeout(
    *,
    source: SourceHubSourceKey,
    query: str,
    per_source_limit: int,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    # Each source runs with its own timeout so one slow upstream does not block all results.
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_fetch_source_hub_records, source, query, per_source_limit)
        try:
            records, warnings = future.result(timeout=_PER_SOURCE_TIMEOUT_SECONDS)
            serialized = [_serialize_result(item) for item in records]
            return serialized, list(warnings), []
        except FutureTimeoutError:
            future.cancel()
            return [], [], [f"TimeoutError: vượt {_PER_SOURCE_TIMEOUT_SECONDS:.0f}s"]
        except httpx.TimeoutException:
            return [], [], ["TimeoutException: nguồn ngoài phản hồi quá chậm"]
        except httpx.HTTPError as exc:
            return [], [], [f"HTTPError: {exc.__class__.__name__}"]
        except Exception as exc:  # pragma: no cover - defensive path
            return [], [], [f"{exc.__class__.__name__}: {exc}"]


@router.post("/")
def search_multi_source(
    payload: SearchRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
) -> dict[str, object]:
    query = payload.query.strip()
    sources = _resolve_sources(payload.sources)
    per_source_limit = _clamp(
        payload.per_source_limit,
        _PER_SOURCE_LIMIT_MIN,
        _PER_SOURCE_LIMIT_MAX,
    )
    total_limit = _clamp(payload.total_limit, _TOTAL_LIMIT_MIN, _TOTAL_LIMIT_MAX)

    results: list[dict[str, Any]] = []
    source_used: list[str] = []
    source_errors: dict[str, list[str]] = {}
    warnings: list[str] = []

    for source in sources:
        source_results, source_warnings, errors = _search_source_with_timeout(
            source=source,
            query=query,
            per_source_limit=per_source_limit,
        )
        if errors:
            source_errors[source] = errors
            continue

        source_used.append(source)
        if source_warnings:
            warnings.extend([f"{source}: {warning}" for warning in source_warnings])
        if source_results:
            results.extend(source_results)

    # Stable de-dup by (source, id/title) before cutting to total limit.
    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in results:
        item_key = (
            str(item.get("source") or ""),
            str(item.get("id") or item.get("title") or ""),
        )
        if item_key in seen_keys:
            continue
        seen_keys.add(item_key)
        deduped.append(item)
        if len(deduped) >= total_limit:
            break

    return {
        "query": query,
        "results": deduped,
        "source_used": source_used,
        "source_errors": source_errors,
        "warnings": warnings,
        "meta": {
            "role": token.role,
            "intent": "multi_source_search",
            "router": "federated_source_hub_search",
            "total_results": len(deduped),
        },
    }
