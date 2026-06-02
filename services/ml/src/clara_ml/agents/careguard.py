# ruff: noqa: E501
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from clara_ml.clients.drug_sources import DrugSourceClient
from clara_ml.config import settings


@dataclass(frozen=True)
class InteractionRule:
    meds: frozenset[str]
    severity: str
    message: str


_LOCAL_DDI_RULES_PATH = (
    Path(__file__).resolve().parent.parent / "nlp" / "seed_data" / "careguard_ddi_rules.v1.json"
)
_VN_DRUG_DICTIONARY_PATH = (
    Path(__file__).resolve().parent.parent / "nlp" / "seed_data" / "vn_drug_dictionary.json"
)
_LOCAL_DDI_RULES_CACHE_MTIME_NS: int | None = None
_LOCAL_DDI_RULES_CACHE_VERSION: str = "unknown"
_LOCAL_DDI_RULES_CACHE_RULES: list[InteractionRule] = []
_VN_DICTIONARY_CACHE_MTIME_NS: int | None = None
_VN_DICTIONARY_CACHE_VERSION: str = "unknown"
_VN_DICTIONARY_RECORD_COUNT: int = 0
_VN_DICTIONARY_ALIAS_LOOKUP: dict[str, str] = {}
_VN_DICTIONARY_ACTIVE_INGREDIENTS: dict[str, list[str]] = {}
_VN_DICTIONARY_RXCUI_MAP: dict[str, str] = {}

_CRITICAL_SYMPTOMS = {
    "chest pain",
    "shortness of breath",
    "fainting",
    "severe bleeding",
}

_SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_SEVERITY_SCORE = {
    "low": 0,
    "medium": 1,
    "high": 3,
    "critical": 5,
}

_DOSAGE_UNIT_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s*(mg|g|mcg|μg|ml|iu|%)\b", re.IGNORECASE)
_DOSAGE_COUNT_PATTERN = re.compile(r"\bx\s*\d+\b", re.IGNORECASE)
_ROUTE_FORM_TOKENS = {
    "tablet",
    "tablets",
    "tab",
    "tabs",
    "capsule",
    "capsules",
    "cap",
    "caps",
    "syrup",
    "suspension",
    "solution",
    "cream",
    "ointment",
    "gel",
    "patch",
    "injection",
    "injectable",
    "sl",
    "iv",
    "im",
    "po",
    "bid",
    "tid",
    "qid",
    "od",
    "hs",
    "vien",
    "ống",
    "ong",
}


def _normalize_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip().lower()] if value.strip() else []
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip().lower())
        return normalized
    return []


def _normalize_text_token(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def _canonicalize_medication_token(token: str) -> str:
    if not token:
        return ""
    cleaned = token
    cleaned = _DOSAGE_UNIT_PATTERN.sub(" ", cleaned)
    cleaned = _DOSAGE_COUNT_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"[/(),;+]", " ", cleaned)
    normalized_parts: list[str] = []
    for raw_part in cleaned.split():
        part = raw_part.strip().lower()
        if not part:
            continue
        if part in _ROUTE_FORM_TOKENS:
            continue
        if part.isdigit():
            continue
        normalized_parts.append(part)
    return " ".join(normalized_parts)


def _normalize_severity(value: object) -> str:
    severity = str(value).strip().lower()
    return severity if severity in _SEVERITY_RANK else "medium"


def _load_local_ddi_rules() -> tuple[list[InteractionRule], str]:
    global _LOCAL_DDI_RULES_CACHE_MTIME_NS
    global _LOCAL_DDI_RULES_CACHE_RULES
    global _LOCAL_DDI_RULES_CACHE_VERSION

    try:
        mtime_ns = _LOCAL_DDI_RULES_PATH.stat().st_mtime_ns
    except OSError:
        return _LOCAL_DDI_RULES_CACHE_RULES, _LOCAL_DDI_RULES_CACHE_VERSION

    if (
        _LOCAL_DDI_RULES_CACHE_MTIME_NS == mtime_ns
        and _LOCAL_DDI_RULES_CACHE_RULES
    ):
        return _LOCAL_DDI_RULES_CACHE_RULES, _LOCAL_DDI_RULES_CACHE_VERSION

    try:
        payload = json.loads(_LOCAL_DDI_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _LOCAL_DDI_RULES_CACHE_RULES, _LOCAL_DDI_RULES_CACHE_VERSION

    version = str(payload.get("version") or _LOCAL_DDI_RULES_PATH.stem).strip() or "unknown"
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        return _LOCAL_DDI_RULES_CACHE_RULES, _LOCAL_DDI_RULES_CACHE_VERSION

    parsed_rules: list[InteractionRule] = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            continue
        meds = frozenset(_normalize_text_list(raw_rule.get("medications")))
        if len(meds) < 2:
            continue
        parsed_rules.append(
            InteractionRule(
                meds=meds,
                severity=_normalize_severity(raw_rule.get("severity")),
                message=(
                    str(raw_rule.get("message", "")).strip()
                    or "Potential DDI detected."
                ),
            )
        )

    if not parsed_rules:
        return _LOCAL_DDI_RULES_CACHE_RULES, _LOCAL_DDI_RULES_CACHE_VERSION

    _LOCAL_DDI_RULES_CACHE_MTIME_NS = mtime_ns
    _LOCAL_DDI_RULES_CACHE_RULES = parsed_rules
    _LOCAL_DDI_RULES_CACHE_VERSION = version
    return _LOCAL_DDI_RULES_CACHE_RULES, _LOCAL_DDI_RULES_CACHE_VERSION


def _load_vn_drug_dictionary() -> tuple[str, int]:
    global _VN_DICTIONARY_CACHE_MTIME_NS
    global _VN_DICTIONARY_CACHE_VERSION
    global _VN_DICTIONARY_RECORD_COUNT
    global _VN_DICTIONARY_ALIAS_LOOKUP
    global _VN_DICTIONARY_ACTIVE_INGREDIENTS
    global _VN_DICTIONARY_RXCUI_MAP

    try:
        mtime_ns = _VN_DRUG_DICTIONARY_PATH.stat().st_mtime_ns
    except OSError:
        return _VN_DICTIONARY_CACHE_VERSION, _VN_DICTIONARY_RECORD_COUNT

    if _VN_DICTIONARY_CACHE_MTIME_NS == mtime_ns and _VN_DICTIONARY_ALIAS_LOOKUP:
        return _VN_DICTIONARY_CACHE_VERSION, _VN_DICTIONARY_RECORD_COUNT

    try:
        payload = json.loads(_VN_DRUG_DICTIONARY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _VN_DICTIONARY_CACHE_VERSION, _VN_DICTIONARY_RECORD_COUNT

    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        return _VN_DICTIONARY_CACHE_VERSION, _VN_DICTIONARY_RECORD_COUNT

    alias_lookup: dict[str, str] = {}
    active_ingredients_by_canonical: dict[str, list[str]] = {}
    rxcui_by_canonical: dict[str, str] = {}
    parsed_count = 0

    for record in raw_records:
        if not isinstance(record, dict):
            continue
        brand = _normalize_text_token(record.get("brand_vn"))
        canonical = _normalize_text_token(record.get("normalized_name"))
        if not brand or not canonical:
            continue

        alias_lookup[brand] = canonical
        parsed_count += 1

        normalized_actives: list[str] = []
        raw_actives = record.get("active_ingredients")
        if isinstance(raw_actives, list):
            for raw_active in raw_actives:
                normalized_active = _normalize_text_token(raw_active)
                if normalized_active and normalized_active not in normalized_actives:
                    normalized_actives.append(normalized_active)
        if not normalized_actives:
            normalized_actives = [canonical]
        active_ingredients_by_canonical.setdefault(canonical, normalized_actives)

        rxcui = str(record.get("rxcui") or "").strip()
        if rxcui:
            rxcui_by_canonical.setdefault(canonical, rxcui)

    if not alias_lookup:
        return _VN_DICTIONARY_CACHE_VERSION, _VN_DICTIONARY_RECORD_COUNT

    version = (
        str(payload.get("version") or _VN_DRUG_DICTIONARY_PATH.stem).strip()
        or "unknown"
    )
    _VN_DICTIONARY_CACHE_MTIME_NS = mtime_ns
    _VN_DICTIONARY_CACHE_VERSION = version
    _VN_DICTIONARY_RECORD_COUNT = parsed_count
    _VN_DICTIONARY_ALIAS_LOOKUP = alias_lookup
    _VN_DICTIONARY_ACTIVE_INGREDIENTS = active_ingredients_by_canonical
    _VN_DICTIONARY_RXCUI_MAP = rxcui_by_canonical
    return _VN_DICTIONARY_CACHE_VERSION, _VN_DICTIONARY_RECORD_COUNT


def _normalize_medications_with_vn_dictionary(
    medications: list[str],
) -> tuple[list[str], dict[str, Any]]:
    version, record_count = _load_vn_drug_dictionary()
    if not medications:
        return [], {
            "version": version,
            "record_count": record_count,
            "mapped_count": 0,
            "mapped_items": [],
        }

    mapped_items: list[dict[str, str]] = []
    normalized_inputs: list[dict[str, str]] = []
    normalized_medications: list[str] = []
    seen: set[str] = set()

    for medication in medications:
        input_token = _normalize_text_token(medication)
        if not input_token:
            continue
        canonical_input = _canonicalize_medication_token(input_token) or input_token
        canonical = _VN_DICTIONARY_ALIAS_LOOKUP.get(
            canonical_input,
            _VN_DICTIONARY_ALIAS_LOOKUP.get(input_token, canonical_input),
        )
        active_ingredients = _VN_DICTIONARY_ACTIVE_INGREDIENTS.get(canonical, [canonical])
        normalized_inputs.append(
            {
                "input": input_token,
                "canonical_input": canonical_input,
                "normalized_name": canonical,
            }
        )

        if canonical != input_token or canonical_input != input_token:
            mapped_items.append(
                {
                    "input": input_token,
                    "canonical_input": canonical_input,
                    "normalized_name": canonical,
                    "rxcui": _VN_DICTIONARY_RXCUI_MAP.get(canonical, ""),
                }
            )

        for candidate in [canonical, *active_ingredients]:
            normalized_candidate = _canonicalize_medication_token(
                _normalize_text_token(candidate)
            ) or _normalize_text_token(candidate)
            if not normalized_candidate or normalized_candidate in seen:
                continue
            seen.add(normalized_candidate)
            normalized_medications.append(normalized_candidate)

    input_count = len(normalized_inputs)
    mapped_count = len(mapped_items)
    normalization_confidence = 1.0 if input_count == 0 else mapped_count / input_count
    pair_coverage_ratio = 1.0 if input_count == 0 else len(normalized_medications) / input_count

    return normalized_medications, {
        "version": version,
        "record_count": record_count,
        "mapped_count": mapped_count,
        "mapped_items": mapped_items[:20],
        "input_count": input_count,
        "normalization_confidence": round(min(max(normalization_confidence, 0.0), 1.0), 3),
        "pair_coverage_ratio": round(min(max(pair_coverage_ratio, 0.0), 1.0), 3),
        "normalized_inputs": normalized_inputs[:20],
    }


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def _pair_key(medications: object) -> tuple[str, ...]:
    return tuple(sorted(set(_normalize_text_list(medications))))


def _parse_sources(value: object, default: str | None = None) -> set[str]:
    sources: set[str] = set()
    if isinstance(value, str):
        for item in value.split(","):
            normalized = item.strip().lower()
            if normalized:
                sources.add(normalized)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                sources.add(item.strip().lower())

    if default and not sources:
        sources.add(default)
    return sources


# Upstream connector sources whose transport/HTTP errors are diagnostic noise.
# Their errors (e.g. ``openfda http_400``, ``rxnav status=503``) must never reach
# the End_User; they are only meaningful when no alternative signal could be obtained.
_CONNECTOR_SOURCE_NAMES = frozenset({"rxnav", "openfda"})


def _sanitize_source_errors_for_output(
    source_errors: dict[str, list[str]],
    *,
    signal_sources: frozenset[str],
) -> dict[str, list[str]]:
    """Suppress upstream connector errors from output metadata when an
    alternative valid signal still exists, retaining them only when no
    alternative signal remains.

    Connector errors such as ``openfda http_400`` or ``rxnav status=503`` are
    internal diagnostics. Per Requirement 3.6 / Property 9, a connector error
    from source ``X`` is dropped entirely (so it can never surface to the
    End_User) whenever a valid signal from a source *other than* ``X`` remains;
    it is retained in metadata for operators only when ``X`` is the sole source
    that could have produced a signal. Checking for an *alternative* source
    (rather than any signal) keeps a connector's own partial success from
    masking that same connector's failures.

    Non-connector internal markers (e.g. ``normalization`` coverage notes or
    ``external`` config/state flags) are preserved as-is since they are not
    upstream connector errors.
    """
    sanitized: dict[str, list[str]] = {}
    for source_name, raw_errors in source_errors.items():
        normalized_errors = [
            str(raw_error).strip() for raw_error in raw_errors if str(raw_error).strip()
        ]
        if not normalized_errors:
            continue

        if source_name in _CONNECTOR_SOURCE_NAMES:
            # Drop the connector error when any *other* source still yielded a
            # valid signal; retain it only when this connector is the lone
            # source that could have produced one.
            if signal_sources - {source_name}:
                continue
            sanitized[source_name] = sorted(set(normalized_errors))
            continue

        sanitized[source_name] = sorted(set(normalized_errors))

    return sanitized


def _contains_vietnamese_text(value: str) -> bool:
    return bool(re.search(r"[À-ỹ]", value))


def _localize_ddi_message(message: object) -> str:
    raw_message = str(message).strip()
    if not raw_message:
        return "Hai thuốc này có thể tương tác với nhau."

    normalized = raw_message.lower()
    if "gi bleeding risk" in normalized or "blunt aspirin effect" in normalized:
        return (
            "Dùng cùng nhau có thể làm tăng nguy cơ chảy máu dạ dày "
            "và làm giảm tác dụng bảo vệ tim mạch của aspirin."
        )
    if "antiplatelet activation may be reduced" in normalized or "cyp interaction" in normalized:
        return "Omeprazole có thể làm giảm hiệu quả chống kết tập tiểu cầu của clopidogrel."
    if "additive cns sedation" in normalized or "sedation may occur" in normalized:
        return "Dùng cùng nhau có thể làm tăng buồn ngủ, chóng mặt và giảm tập trung."
    if "myopathy" in normalized or "rhabdomyolysis" in normalized:
        return "Phối hợp này có thể làm tăng nguy cơ đau cơ, yếu cơ hoặc tổn thương cơ."
    if "hyperkalemia" in normalized or "potassium-sparing" in normalized:
        return "Phối hợp này có thể làm tăng kali máu, nhất là khi có bệnh thận."
    if "major bleeding risk" in normalized or "bleeding risk increases" in normalized:
        return "Phối hợp này có thể làm tăng nguy cơ chảy máu."
    if _contains_vietnamese_text(raw_message):
        return raw_message
    return "Hai thuốc này có thể tương tác với nhau. Nên hỏi bác sĩ hoặc dược sĩ để kiểm tra lại."


def _detect_ddi_alerts(
    medications: list[str],
    rules: list[InteractionRule],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    med_set = set(medications)
    for rule in rules:
        if rule.meds.issubset(med_set):
            alerts.append(
                {
                    "type": "drug_drug",
                    "severity": rule.severity,
                    "medications": sorted(rule.meds),
                    "message": _localize_ddi_message(rule.message),
                    "source": "local_rules",
                }
            )
    return alerts


def _merge_drug_alerts(
    local_alerts: list[dict[str, Any]],
    external_alerts: list[dict[str, Any]],
    openfda_evidence: dict[tuple[str, str], dict[str, int]],
) -> list[dict[str, Any]]:
    merged_by_pair: dict[tuple[str, ...], dict[str, Any]] = {}

    def ingest(alert: dict[str, Any], default_source: str) -> None:
        if alert.get("type") != "drug_drug":
            return
        key = _pair_key(alert.get("medications"))
        if len(key) < 2:
            return

        incoming_severity = _normalize_severity(alert.get("severity"))
        incoming_rank = _SEVERITY_RANK[incoming_severity]
        incoming_message = _localize_ddi_message(
            str(alert.get("message", "")).strip() or "Potential DDI detected."
        )
        incoming_sources = _parse_sources(alert.get("source"), default=default_source)

        existing = merged_by_pair.get(key)
        if existing is None:
            merged_by_pair[key] = {
                "type": "drug_drug",
                "severity": incoming_severity,
                "medications": list(key),
                "message": incoming_message,
                "_sources": incoming_sources,
            }
            return

        existing_severity = _normalize_severity(existing.get("severity"))
        existing_rank = _SEVERITY_RANK[existing_severity]
        if incoming_rank > existing_rank:
            existing["severity"] = incoming_severity
            existing["message"] = incoming_message

        existing_sources = existing.setdefault("_sources", set())
        if isinstance(existing_sources, set):
            existing_sources.update(incoming_sources)

    for alert in local_alerts:
        ingest(alert, default_source="local_rules")
    for alert in external_alerts:
        ingest(alert, default_source="rxnav")

    for pair, evidence in openfda_evidence.items():
        key = tuple(sorted(pair))
        label_mentions = int(evidence.get("label_mentions", 0))
        event_reports = int(evidence.get("event_reports", 0))

        existing = merged_by_pair.get(key)
        if existing is None:
            continue

        existing_sources = existing.setdefault("_sources", set())
        if isinstance(existing_sources, set):
            existing_sources.add("openfda")

        merged_evidence = existing.setdefault("evidence", {})
        if isinstance(merged_evidence, dict):
            merged_evidence["openfda_label_mentions"] = max(
                label_mentions,
                int(merged_evidence.get("openfda_label_mentions", 0)),
            )
            merged_evidence["openfda_event_reports"] = max(
                event_reports,
                int(merged_evidence.get("openfda_event_reports", 0)),
            )

    alerts: list[dict[str, Any]] = []
    for alert in merged_by_pair.values():
        sources = alert.pop("_sources", set())
        if isinstance(sources, set):
            alert["source"] = ",".join(sorted(sources)) if sources else "local_rules"
        alerts.append(alert)

    alerts.sort(
        key=lambda item: (
            -_SEVERITY_RANK[_normalize_severity(item.get("severity"))],
            tuple(item.get("medications", [])),
        )
    )
    return alerts


def _detect_allergy_conflicts(medications: list[str], allergies: list[str]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    med_set = set(medications)
    for allergy in allergies:
        if allergy in med_set:
            alerts.append(
                {
                    "type": "drug_allergy",
                    "severity": "high",
                    "medications": [allergy],
                    "message": f"Thuốc này trùng với dị ứng đã khai báo: {allergy}.",
                    "source": "local_rules",
                }
            )
    return alerts


def _critical_symptom_hits(symptoms: list[str]) -> list[str]:
    hits: list[str] = []
    for symptom in symptoms:
        if symptom in _CRITICAL_SYMPTOMS:
            hits.append(symptom)
    return hits


def _lab_risk_flags(labs: object) -> list[str]:
    if not isinstance(labs, dict):
        return []

    flags: list[str] = []
    egfr = labs.get("egfr")
    creatinine = labs.get("creatinine")
    if isinstance(egfr, (int, float)) and egfr < 30:
        flags.append("severe_renal_impairment")
    if isinstance(creatinine, (int, float)) and creatinine > 2.0:
        flags.append("elevated_creatinine")
    return flags


def _risk_from_signals(
    ddi_alerts: list[dict[str, Any]],
    critical_symptoms: list[str],
    lab_flags: list[str],
) -> tuple[int, str]:
    score = 0
    for alert in ddi_alerts:
        severity = _normalize_severity(alert.get("severity"))
        score += _SEVERITY_SCORE[severity]

    score += len(critical_symptoms) * 2
    score += len(lab_flags)

    severe_bleeding = "severe bleeding" in critical_symptoms
    has_high_risk_ddi = any(
        alert.get("type") == "drug_drug"
        and _normalize_severity(alert.get("severity")) in {"high", "critical"}
        for alert in ddi_alerts
    )
    has_medium_risk_ddi = any(
        alert.get("type") == "drug_drug"
        and _normalize_severity(alert.get("severity")) == "medium"
        for alert in ddi_alerts
    )

    if severe_bleeding and has_high_risk_ddi:
        return max(score, 9), "critical"
    if has_high_risk_ddi and score >= 3:
        return max(score, 5), "high"

    # Compute the base level from the aggregate score thresholds first, then apply
    # the medium floor. The medium floor is a lower bound only: a `medium` drug_drug
    # alert raises the overall level to at least `medium`, but it must never reduce
    # an already-higher level (e.g. when symptoms/labs push the score into the
    # `high`/`critical` range). Placing the floor after the thresholds keeps
    # `high`/`critical` aggregation unchanged and a genuine `low` preserved.
    if score >= 9:
        level = "critical"
    elif score >= 5:
        level = "high"
    elif score >= 2:
        level = "medium"
    else:
        level = "low"

    if has_medium_risk_ddi and _SEVERITY_RANK[level] < _SEVERITY_RANK["medium"]:
        return max(score, 1), "medium"

    return score, level


def _recommendation_for(
    level: str,
    ddi_alerts: list[dict[str, Any]],
    critical_symptoms: list[str],
) -> str:
    primary_message = " ".join(
        str(alert.get("message", "")).strip().lower()
        for alert in ddi_alerts
        if str(alert.get("message", "")).strip()
    )
    if level == "critical":
        return (
            "Đây là nguy cơ rất cao. Đến cơ sở y tế ngay, nhất là khi có khó thở, ngất, "
            "đau ngực hoặc chảy máu nhiều."
        )
    if level == "high":
        if "chảy máu" in primary_message:
            return (
                "Không tự tiếp tục phối hợp nếu chưa được bác sĩ xác nhận. Đi khám ngay nếu có "
                "nôn ra máu, đi ngoài phân đen, chóng mặt nhiều hoặc chảy máu khó cầm."
            )
        if "đau cơ" in primary_message or "tổn thương cơ" in primary_message:
            return (
                "Liên hệ bác sĩ hoặc dược sĩ sớm để rà soát đơn thuốc. Đi khám ngay nếu đau cơ tăng nhanh, "
                "yếu cơ nhiều hoặc nước tiểu sẫm màu."
            )
        if "kali máu" in primary_message:
            return (
                "Cần được bác sĩ hoặc dược sĩ kiểm tra sớm. Đi khám nếu mệt nhiều, yếu cơ, hồi hộp "
                "hoặc tiểu ít hơn bình thường."
            )
        return (
            "Không tự phối hợp hoặc tiếp tục dùng cùng nếu chưa được bác sĩ xác nhận. "
            "Liên hệ bác sĩ hoặc dược sĩ sớm để rà soát đơn thuốc."
        )
    if level == "medium":
        if "aspirin" in primary_message or "chảy máu" in primary_message:
            return (
                "Không tự dùng kéo dài cùng nhau. Nên hỏi bác sĩ hoặc dược sĩ trong ngày "
                "để kiểm tra lại cách dùng và thời điểm uống."
            )
        if "clopidogrel" in primary_message or "chống kết tập tiểu cầu" in primary_message:
            return (
                "Nên hỏi bác sĩ hoặc dược sĩ trong ngày để kiểm tra lại phối hợp này. "
                "Không tự đổi giờ uống hoặc kéo dài dùng cùng nếu chưa được hướng dẫn."
            )
        return (
            "Nên hỏi bác sĩ hoặc dược sĩ trong ngày để kiểm tra lại cách dùng. "
            "Không tự tăng liều hoặc phối hợp kéo dài."
        )
    if critical_symptoms:
        return "Dù mức tương tác không cao, các triệu chứng hiện tại vẫn cần được đi khám gấp."
    if ddi_alerts:
        if "buồn ngủ" in primary_message or "chóng mặt" in primary_message:
            return "Theo dõi buồn ngủ hoặc chóng mặt. Tránh lái xe và vận hành máy nếu thấy lơ mơ."
        return "Theo dõi triệu chứng mới và hỏi bác sĩ hoặc dược sĩ nếu cần dùng cùng trong nhiều ngày."
    return "Chưa thấy nguy cơ tương tác lớn ngay lúc này. Nếu đơn thuốc thay đổi, nên kiểm tra lại."


def run_careguard_analyze(payload: dict) -> dict:
    symptoms = _normalize_text_list(payload.get("symptoms"))
    raw_medications = _normalize_text_list(payload.get("medications"))
    medications, vn_dictionary_metadata = _normalize_medications_with_vn_dictionary(raw_medications)
    allergies = _normalize_text_list(payload.get("allergies"))
    labs = payload.get("labs")

    local_rules, local_ddi_rules_version = _load_local_ddi_rules()
    local_ddi_alerts = _detect_ddi_alerts(medications, local_rules)
    source_used = ["local_rules"]
    source_errors: dict[str, list[str]] = {}
    external_ddi_alerts: list[dict[str, Any]] = []
    openfda_evidence: dict[tuple[str, str], dict[str, int]] = {}
    openfda_pairs_checked = 0
    needs_external_lookup = len(set(medications)) >= 2
    external_ddi_flag_source = "runtime" if "external_ddi_enabled" in payload else "env"
    external_ddi_enabled = _as_bool(
        payload.get("external_ddi_enabled"),
        default=settings.external_ddi_enabled,
    )

    if needs_external_lookup and external_ddi_enabled:
        try:
            # Favor deterministic fallback behavior on slow upstreams by avoiding retry storms.
            external = DrugSourceClient(
                timeout_seconds=settings.external_ddi_timeout_seconds,
                max_retries=0,
            ).fetch_ddi_context(medications)
            external_ddi_alerts = external.rxnav_alerts
            openfda_evidence = external.openfda_evidence
            openfda_pairs_checked = int(getattr(external, "openfda_pairs_checked", 0))
            source_errors = external.source_errors
            for source_name in external.source_used:
                if source_name not in source_used:
                    source_used.append(source_name)
        except Exception as exc:  # pragma: no cover - defensive hard-crash guard
            source_errors["external"] = [f"unhandled_error:{exc.__class__.__name__}"]
    elif needs_external_lookup:
        source_errors["external"] = ["disabled_by_config"]

    normalization_pair_coverage_low = bool(raw_medications) and len(set(medications)) < 2
    if normalization_pair_coverage_low:
        source_errors.setdefault("normalization", []).append("low_pair_coverage")

    # Determine which sources produced a valid signal (a DDI alert or a
    # successful upstream lookup). A connector's transport/HTTP error is only
    # retained in metadata when no *alternative* source produced a signal; while
    # an alternative signal exists the connector error is suppressed entirely so
    # it can never reach the End_User (Requirement 3.6 / Property 9).
    signal_sources: set[str] = set()
    if local_ddi_alerts:
        signal_sources.add("local_rules")
    if external_ddi_alerts:
        signal_sources.add("rxnav")
    for source in source_used:
        if source in {"rxnav", "openfda"}:
            signal_sources.add(source)
    source_errors = _sanitize_source_errors_for_output(
        source_errors,
        signal_sources=frozenset(signal_sources),
    )

    ddi_alerts = _merge_drug_alerts(local_ddi_alerts, external_ddi_alerts, openfda_evidence)
    allergy_alerts = _detect_allergy_conflicts(medications, allergies)
    all_alerts = ddi_alerts + allergy_alerts

    critical_symptoms = _critical_symptom_hits(symptoms)
    lab_flags = _lab_risk_flags(labs)
    score, level = _risk_from_signals(all_alerts, critical_symptoms, lab_flags)

    factors = [f"critical_symptom:{s}" for s in critical_symptoms]
    factors.extend(f"lab_flag:{flag}" for flag in lab_flags)
    factors.extend(
        f"alert:{alert['type']}:{_normalize_severity(alert.get('severity'))}"
        for alert in all_alerts
    )

    external_source_used = any(source in {"rxnav", "openfda"} for source in source_used)
    fallback_used = needs_external_lookup and (
        not external_source_used or bool(source_errors) or normalization_pair_coverage_low
    )

    return {
        "risk": {
            "level": level,
            "score": score,
            "factors": factors,
        },
        "ddi_alerts": all_alerts,
        "recommendation": _recommendation_for(level, all_alerts, critical_symptoms),
        "metadata": {
            "pipeline": "p2-careguard-ddi-standard-v2",
            "fallback_used": fallback_used,
            "external_ddi_enabled": external_ddi_enabled,
            "external_ddi_flag_source": external_ddi_flag_source,
            "local_ddi_rules_version": local_ddi_rules_version,
            "vn_dictionary_version": vn_dictionary_metadata["version"],
            "vn_dictionary_record_count": vn_dictionary_metadata["record_count"],
            "vn_dictionary_mapped_count": vn_dictionary_metadata["mapped_count"],
            "vn_dictionary_mapped_items": vn_dictionary_metadata["mapped_items"],
            "vn_dictionary_input_count": vn_dictionary_metadata["input_count"],
            "normalization_confidence": vn_dictionary_metadata["normalization_confidence"],
            "normalization_pair_coverage_low": normalization_pair_coverage_low,
            "normalized_medication_count": len(medications),
            "raw_medication_count": len(raw_medications),
            "normalized_inputs": vn_dictionary_metadata["normalized_inputs"],
            "source_used": source_used,
            "source_errors": source_errors,
            "openfda_pairs_checked": openfda_pairs_checked,
        },
    }
