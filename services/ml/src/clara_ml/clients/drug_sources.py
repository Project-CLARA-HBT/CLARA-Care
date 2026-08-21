from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

import httpx

from clara_ml.config import settings

_OPENFDA_BASE_URL = "https://api.fda.gov/drug"
_CACHE_TTL_SECONDS = 600.0
_OPENFDA_PAIR_LIMIT = 12
_OPENFDA_LABEL_LIMIT = 8

# Suy luận severity từ free-text mục `drug_interactions` của nhãn FDA.
# Bảo thủ: cap ở "high", KHÔNG bao giờ trả "critical" từ text tự do.
_LABEL_SEVERITY_HIGH_CUES = (
    "contraindicated",
    "do not use",
    "should not be used",
    "avoid concomitant",
    "avoid use",
    "avoid coadministration",
)
_LABEL_SEVERITY_MEDIUM_CUES = (
    "monitor",
    "caution",
    "adjust",
    "reduce dose",
    "closely",
    "increased risk",
)
_LABEL_WINDOW = 160

_DDI_CONTEXT_CACHE: dict[tuple[str, ...], tuple[float, ExternalDDIResult]] = {}


@dataclass
class ExternalDDIResult:
    rxnav_alerts: list[dict[str, Any]] = field(default_factory=list)
    openfda_alerts: list[dict[str, Any]] = field(default_factory=list)
    openfda_evidence: dict[tuple[str, str], dict[str, int]] = field(default_factory=dict)
    openfda_pairs_checked: int = 0
    source_used: list[str] = field(default_factory=list)
    source_errors: dict[str, list[str]] = field(default_factory=dict)
    rxnav_status: str = ""


class DrugSourceClient:
    def __init__(
        self,
        timeout_seconds: float = 1.5,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.15,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def fetch_ddi_context(self, medications: list[str]) -> ExternalDDIResult:
        meds = sorted({med.strip().lower() for med in medications if med and med.strip()})
        result = ExternalDDIResult()
        if len(meds) < 2:
            return result
        cache_key = tuple(meds)
        now = time.time()
        cached_item = _DDI_CONTEXT_CACHE.get(cache_key)
        if cached_item:
            cached_at, cached_value = cached_item
            if (now - cached_at) <= _CACHE_TTL_SECONDS:
                return self._clone_result(cached_value)
            _DDI_CONTEXT_CACHE.pop(cache_key, None)

        # Tầng 2 — RxNav interaction API đã bị NLM gỡ (1/2024), trả 404.
        # Không gọi nữa; ghi trạng thái vào rxnav_status (KHÔNG vào source_errors
        # để không trip fallback_used). rxnav_alerts giữ rỗng.
        result.rxnav_status = "endpoint_retired"

        if settings.openfda_label_alerts_enabled:
            label_alerts, label_counts, label_errors, label_success = (
                self._fetch_openfda_label_alerts(meds)
            )
        else:
            label_alerts, label_counts, label_errors, label_success = [], {}, set(), False

        event_counts, event_errors, event_success, pairs_checked = (
            self._fetch_openfda_event_counts(meds)
        )

        if label_alerts:
            result.openfda_alerts = label_alerts
        result.openfda_pairs_checked = pairs_checked

        # Gộp evidence: label_mentions (từ scan nhãn) + event_reports (từ event-count).
        evidence: dict[tuple[str, str], dict[str, int]] = {}
        for pair, count in label_counts.items():
            evidence.setdefault(pair, {})["label_mentions"] = count
        for pair, count in event_counts.items():
            evidence.setdefault(pair, {})["event_reports"] = count
        if evidence:
            result.openfda_evidence = evidence

        if (label_success or event_success) and "openfda" not in result.source_used:
            result.source_used.append("openfda")
        openfda_errors = label_errors | event_errors
        if openfda_errors:
            result.source_errors["openfda"] = sorted(openfda_errors)

        _DDI_CONTEXT_CACHE[cache_key] = (now, self._clone_result(result))
        return result

    @staticmethod
    def _clone_result(result: ExternalDDIResult) -> ExternalDDIResult:
        return ExternalDDIResult(
            rxnav_alerts=[dict(item) for item in result.rxnav_alerts],
            openfda_alerts=[dict(item) for item in result.openfda_alerts],
            openfda_evidence={
                pair: dict(values)
                for pair, values in result.openfda_evidence.items()
            },
            openfda_pairs_checked=int(result.openfda_pairs_checked),
            source_used=list(result.source_used),
            source_errors={
                source_name: list(errors)
                for source_name, errors in result.source_errors.items()
            },
            rxnav_status=result.rxnav_status,
        )

    def _fetch_openfda_label_alerts(
        self,
        medications: list[str],
    ) -> tuple[list[dict[str, Any]], dict[tuple[str, str], int], set[str], bool]:
        """Đọc mục `drug_interactions` của nhãn từng thuốc rồi quét cross-mention.

        Trả về (alerts, label_mention_counts_by_pair, errors, success).
        Mỗi alert là một tương tác THẬT (nguồn "openfda"), khác với evidence count.
        """
        alerts: list[dict[str, Any]] = []
        mention_counts: dict[tuple[str, str], int] = {}
        errors: set[str] = set()
        success = False

        label_text: dict[str, str] = {}
        with httpx.Client(timeout=self._timeout_seconds) as client:
            for med in medications[:_OPENFDA_LABEL_LIMIT]:
                data, error = self._request_json(
                    client,
                    f"{_OPENFDA_BASE_URL}/label.json",
                    params={"search": f'openfda.generic_name:"{med}"', "limit": 1},
                    allow_not_found=True,
                )
                if error:
                    errors.add(self._normalize_openfda_error(error))
                    continue
                success = True
                results = data.get("results")
                if not isinstance(results, list) or not results:
                    continue
                first = results[0] if isinstance(results[0], dict) else {}
                raw = first.get("drug_interactions")
                if isinstance(raw, list):
                    text = " ".join(str(item) for item in raw)
                elif isinstance(raw, str):
                    text = raw
                else:
                    text = ""
                if text:
                    label_text[med] = text

        # Quét in-memory mọi cặp (không tốn thêm HTTP).
        for med_a, med_b in combinations(medications, 2):
            pair_key: tuple[str, str] = (med_a, med_b) if med_a < med_b else (med_b, med_a)
            match = self._match_in_label(label_text.get(med_a, ""), med_b)
            if match is None:
                match = self._match_in_label(label_text.get(med_b, ""), med_a)
            if match is None:
                continue
            count, severity, snippet = match
            mention_counts[pair_key] = count
            alerts.append(
                {
                    "type": "drug_drug",
                    "severity": severity,
                    "medications": list(pair_key),
                    "message": snippet,
                    "source": "openfda",
                }
            )

        return alerts, mention_counts, errors, success

    def _fetch_openfda_event_counts(
        self,
        medications: list[str],
    ) -> tuple[dict[tuple[str, str], int], set[str], bool, int]:
        """Đếm số báo cáo tác dụng phụ (FAERS) cho mỗi cặp — chỉ là evidence."""
        counts: dict[tuple[str, str], int] = {}
        errors: set[str] = set()
        success = False
        pairs_checked = 0

        with httpx.Client(timeout=self._timeout_seconds) as client:
            for med_a, med_b in list(combinations(medications, 2))[:_OPENFDA_PAIR_LIMIT]:
                pairs_checked += 1
                data, error = self._request_json(
                    client,
                    f"{_OPENFDA_BASE_URL}/event.json",
                    params={
                        "search": (
                            f'patient.drug.medicinalproduct:"{med_a.upper()}" AND '
                            f'patient.drug.medicinalproduct:"{med_b.upper()}"'
                        ),
                        "limit": 1,
                    },
                    allow_not_found=True,
                )
                if error:
                    errors.add(self._normalize_openfda_error(error))
                    continue
                success = True
                hits = self._extract_total_count(data)
                if hits > 0:
                    pair_key: tuple[str, str] = (med_a, med_b) if med_a < med_b else (med_b, med_a)
                    counts[pair_key] = hits

        return counts, errors, success, pairs_checked

    @classmethod
    def _match_in_label(cls, text: str, other: str) -> tuple[int, str, str] | None:
        """Dò tên `other` trong text nhãn (word-boundary, case-insensitive).

        Trả (số lần khớp, severity suy luận, snippet) hoặc None nếu không khớp.
        """
        other = other.strip()
        if not text or not other:
            return None
        pattern = re.compile(rf"\b{re.escape(other)}\b", re.IGNORECASE)
        spans = list(pattern.finditer(text))
        if not spans:
            return None
        first = spans[0]
        window = text[max(0, first.start() - _LABEL_WINDOW) : first.end() + _LABEL_WINDOW]
        severity = cls._infer_label_severity(window)
        snippet = cls._snippet_around(text, first.start(), first.end())
        return len(spans), severity, snippet

    @staticmethod
    def _infer_label_severity(window: str) -> str:
        lowered = window.lower()
        if any(cue in lowered for cue in _LABEL_SEVERITY_HIGH_CUES):
            return "high"
        if any(cue in lowered for cue in _LABEL_SEVERITY_MEDIUM_CUES):
            return "medium"
        return "medium"

    @staticmethod
    def _snippet_around(text: str, start: int, end: int, radius: int = 120) -> str:
        left = max(0, start - radius)
        right = min(len(text), end + radius)
        fragment = " ".join(text[left:right].split())
        prefix = "…" if left > 0 else ""
        suffix = "…" if right < len(text) else ""
        return f"{prefix}{fragment}{suffix}"

    @staticmethod
    def _normalize_openfda_error(error: str) -> str:
        normalized = str(error).strip()
        if not normalized:
            return "unknown_error"
        if normalized.lower().startswith("http_400:"):
            return "http_400:bad_request"
        return normalized

    def _request_json(
        self,
        client: httpx.Client,
        url: str,
        params: dict[str, Any],
        allow_not_found: bool = False,
    ) -> tuple[dict[str, Any], str | None]:
        last_error = "unknown_error"

        for attempt in range(self._max_retries + 1):
            try:
                response = client.get(url, params=params)
                if allow_not_found and response.status_code == 404:
                    return {}, None
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    return payload, None
                return {}, None
            except httpx.TimeoutException as exc:
                last_error = f"timeout:{url}:{exc.__class__.__name__}"
            except httpx.HTTPStatusError as exc:
                last_error = f"http_{exc.response.status_code}:{url}"
            except (httpx.HTTPError, ValueError) as exc:
                last_error = f"transport_error:{url}:{exc.__class__.__name__}"

            if attempt < self._max_retries:
                time.sleep(self._retry_backoff_seconds * (attempt + 1))

        return {}, last_error

    @staticmethod
    def _extract_total_count(payload: dict[str, Any]) -> int:
        if not isinstance(payload, dict):
            return 0
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            return 0
        results = meta.get("results")
        if not isinstance(results, dict):
            return 0
        total = results.get("total")
        return int(total) if isinstance(total, int) else 0
