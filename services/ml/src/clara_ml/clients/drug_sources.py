from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
import time
from typing import Any

import httpx


_RXNAV_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
_OPENFDA_BASE_URL = "https://api.fda.gov/drug"
_SEVERITY_MAP = {
    "contraindicated": "critical",
    "major": "high",
    "high": "high",
    "significant": "medium",
    "moderate": "medium",
    "minor": "low",
    "low": "low",
}
_CACHE_TTL_SECONDS = 600.0
_OPENFDA_PAIR_LIMIT = 12
_DDI_CONTEXT_CACHE: dict[tuple[str, ...], tuple[float, "ExternalDDIResult"]] = {}


@dataclass
class ExternalDDIResult:
    rxnorm_map: dict[str, str] = field(default_factory=dict)
    rxnav_alerts: list[dict[str, Any]] = field(default_factory=list)
    openfda_evidence: dict[tuple[str, str], dict[str, int]] = field(default_factory=dict)
    openfda_pairs_checked: int = 0
    source_used: list[str] = field(default_factory=list)
    source_errors: dict[str, list[str]] = field(default_factory=dict)


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

        rxnorm_map, rxnav_alerts, rxnav_errors = self._fetch_rxnav_interactions(meds)
        if rxnorm_map:
            result.rxnorm_map = rxnorm_map
        if rxnav_alerts:
            result.rxnav_alerts = rxnav_alerts
        if rxnorm_map and "rxnav" not in result.source_used:
            result.source_used.append("rxnav")
        if rxnav_errors:
            result.source_errors["rxnav"] = sorted(rxnav_errors)

        openfda_evidence, openfda_errors, openfda_success, openfda_pairs_checked = (
            self._fetch_openfda_evidence(meds)
        )
        if openfda_evidence:
            result.openfda_evidence = openfda_evidence
        result.openfda_pairs_checked = openfda_pairs_checked
        if openfda_success and "openfda" not in result.source_used:
            result.source_used.append("openfda")
        if openfda_errors:
            result.source_errors["openfda"] = sorted(openfda_errors)

        _DDI_CONTEXT_CACHE[cache_key] = (now, self._clone_result(result))
        return result

    @staticmethod
    def _clone_result(result: ExternalDDIResult) -> ExternalDDIResult:
        return ExternalDDIResult(
            rxnorm_map=dict(result.rxnorm_map),
            rxnav_alerts=[dict(item) for item in result.rxnav_alerts],
            openfda_evidence={
                tuple(pair): dict(values)
                for pair, values in result.openfda_evidence.items()
            },
            openfda_pairs_checked=int(result.openfda_pairs_checked),
            source_used=list(result.source_used),
            source_errors={
                source_name: list(errors)
                for source_name, errors in result.source_errors.items()
            },
        )

    def _fetch_rxnav_interactions(
        self,
        medications: list[str],
    ) -> tuple[dict[str, str], list[dict[str, Any]], set[str]]:
        rxnorm_map: dict[str, str] = {}
        errors: set[str] = set()

        with httpx.Client(timeout=self._timeout_seconds) as client:
            for med in medications:
                data, error = self._request_json(
                    client,
                    f"{_RXNAV_BASE_URL}/rxcui.json",
                    params={"name": med},
                )
                if error:
                    errors.add(error)
                    continue
                rxcui = self._extract_rxcui(data)
                if rxcui:
                    rxnorm_map[med] = rxcui

            if len(rxnorm_map) < 2:
                return rxnorm_map, [], errors

            payload, error = self._request_json(
                client,
                f"{_RXNAV_BASE_URL}/interaction/list.json",
                params={"rxcuis": "+".join(sorted(set(rxnorm_map.values())))},
                allow_not_found=True,
            )
            if error:
                errors.add(error)
                return rxnorm_map, [], errors

        alerts = self._parse_rxnav_interactions(payload, rxnorm_map)
        return rxnorm_map, alerts, errors

    def _fetch_openfda_evidence(
        self,
        medications: list[str],
    ) -> tuple[dict[tuple[str, str], dict[str, int]], set[str], bool, int]:
        evidence: dict[tuple[str, str], dict[str, int]] = {}
        errors: set[str] = set()
        success = False
        pairs_checked = 0

        with httpx.Client(timeout=self._timeout_seconds) as client:
            # Keep a bounded pair-set for predictable latency on demo paths.
            # Increased bound to reduce misses on polypharmacy without exploding latency.
            for med_a, med_b in list(combinations(medications, 2))[:_OPENFDA_PAIR_LIMIT]:
                pair_key = tuple(sorted((med_a, med_b)))
                pairs_checked += 1

                label_search = (
                    f'(openfda.generic_name:"{med_a}" AND drug_interactions:"{med_b}") OR '
                    f'(openfda.generic_name:"{med_b}" AND drug_interactions:"{med_a}")'
                )
                label_data, label_error = self._request_json(
                    client,
                    f"{_OPENFDA_BASE_URL}/label.json",
                    params={
                        "search": label_search,
                        "limit": 1,
                    },
                    allow_not_found=True,
                )
                if label_error:
                    errors.add(label_error)
                    label_hits = 0
                    label_query_success = False
                else:
                    label_query_success = True
                    label_hits = self._extract_total_count(label_data)

                event_data, event_error = self._request_json(
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
                if event_error:
                    errors.add(event_error)
                    event_hits = 0
                    event_query_success = False
                else:
                    event_hits = self._extract_total_count(event_data)
                    event_query_success = True

                if label_query_success or event_query_success:
                    success = True

                if label_hits > 0 or event_hits > 0:
                    evidence[pair_key] = {
                        "label_mentions": label_hits,
                        "event_reports": event_hits,
                    }

        return evidence, errors, success, pairs_checked

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
    def _extract_rxcui(payload: dict[str, Any]) -> str | None:
        id_group = payload.get("idGroup")
        if not isinstance(id_group, dict):
            return None
        rxnorm_ids = id_group.get("rxnormId")
        if not isinstance(rxnorm_ids, list) or not rxnorm_ids:
            return None
        rxcui = rxnorm_ids[0]
        return str(rxcui).strip() if rxcui else None

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

    def _parse_rxnav_interactions(
        self,
        payload: dict[str, Any],
        rxnorm_map: dict[str, str],
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        rxcui_to_med = {rxcui: med for med, rxcui in rxnorm_map.items()}

        groups = payload.get("fullInteractionTypeGroup")
        if not isinstance(groups, list):
            return alerts

        for group in groups:
            if not isinstance(group, dict):
                continue
            full_types = group.get("fullInteractionType")
            if not isinstance(full_types, list):
                continue

            for full_type in full_types:
                if not isinstance(full_type, dict):
                    continue
                interaction_pairs = full_type.get("interactionPair")
                if not isinstance(interaction_pairs, list):
                    continue

                for pair in interaction_pairs:
                    if not isinstance(pair, dict):
                        continue

                    meds: set[str] = set()
                    concepts = pair.get("interactionConcept")
                    if isinstance(concepts, list):
                        for concept in concepts:
                            if not isinstance(concept, dict):
                                continue
                            min_item = concept.get("minConceptItem")
                            if not isinstance(min_item, dict):
                                continue
                            rxcui = str(min_item.get("rxcui", "")).strip()
                            if rxcui and rxcui in rxcui_to_med:
                                meds.add(rxcui_to_med[rxcui])

                    if len(meds) < 2:
                        continue

                    message = str(pair.get("description", "")).strip()
                    if not message:
                        message = "Potential interaction identified by RxNav."

                    severity = self._normalize_severity(str(pair.get("severity", "")).lower())
                    alerts.append(
                        {
                            "type": "drug_drug",
                            "severity": severity,
                            "medications": sorted(meds),
                            "message": message,
                            "source": "rxnav",
                        }
                    )

        return alerts

    @staticmethod
    def _normalize_severity(raw: str) -> str:
        if not raw:
            return "medium"

        for key, normalized in _SEVERITY_MAP.items():
            if key in raw:
                return normalized

        return "medium"
