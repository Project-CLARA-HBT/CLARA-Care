# ruff: noqa: E501
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
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
_DRUGBANK_DIR = Path(__file__).resolve().parent.parent / "nlp" / "seed_data" / "drugbank"
_DRUGBANK_MANIFEST_PATH = _DRUGBANK_DIR / "manifest.json"
_LOCAL_DDI_RULES_CACHE_MTIME_NS: int | None = None
_LOCAL_DDI_RULES_CACHE_VERSION: str = "unknown"
_LOCAL_DDI_RULES_CACHE_RULES: list[InteractionRule] = []
_DRUGBANK_DDI_CACHE_MTIME_NS: int | None = None
_DRUGBANK_DDI_CACHE_VERSION: str = "unknown"
_DRUGBANK_DDI_CACHE_RULES: list[InteractionRule] = []
# Pair-indexed DDI matcher cache (Req 5.4 / Property P8). The index maps each
# two-medication pair (a frozenset) to the interaction rule(s) for that pair and
# is rebuilt whenever the resolved rule-set version label changes (which in turn
# tracks the underlying file mtimes via ``_load_local_ddi_rules`` /
# ``_load_drugbank_ddi_rules``). Rules covering more/fewer than two medications
# are kept in a side list and matched by subset scan so the indexed matcher is
# exactly equivalent to the linear matcher for any rule set.
_DDI_PAIR_INDEX_CACHE_VERSION: str | None = None
_DDI_PAIR_INDEX_CACHE: dict[frozenset[str], list[InteractionRule]] = {}
_DDI_PAIR_INDEX_CACHE_OTHER: list[InteractionRule] = []
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

    if _LOCAL_DDI_RULES_CACHE_MTIME_NS == mtime_ns and _LOCAL_DDI_RULES_CACHE_RULES:
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
                message=(str(raw_rule.get("message", "")).strip() or "Potential DDI detected."),
            )
        )

    if not parsed_rules:
        return _LOCAL_DDI_RULES_CACHE_RULES, _LOCAL_DDI_RULES_CACHE_VERSION

    _LOCAL_DDI_RULES_CACHE_MTIME_NS = mtime_ns
    _LOCAL_DDI_RULES_CACHE_RULES = parsed_rules
    _LOCAL_DDI_RULES_CACHE_VERSION = version
    return _LOCAL_DDI_RULES_CACHE_RULES, _LOCAL_DDI_RULES_CACHE_VERSION


def _verify_and_parse_drugbank_manifest() -> tuple[list[InteractionRule], str] | None:
    """Verify the DrugBank manifest + shards and return (rules, version) or None.

    Manifest-shape verification (Req 5.3): the manifest MUST be a JSON object
    with a non-empty ``version`` and a ``ddi_shards`` list whose every entry is a
    ``{"file": <non-empty>, ...}`` object. Every referenced shard MUST itself be a
    readable JSON object carrying a ``rules`` list.

    Degrade-to-curated semantics: on ANY missing/unparseable manifest, malformed
    manifest shape, or ANY missing/unparseable referenced shard, this returns
    ``None`` so the caller drops the entire DrugBank layer and uses curated-only.
    A single bad shard never yields a partial DrugBank rule set. This function
    never raises — every failure mode maps to ``None``.
    """
    # Missing or unreadable manifest -> degrade.
    try:
        manifest_raw = _DRUGBANK_MANIFEST_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        manifest = json.loads(manifest_raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(manifest, dict):
        return None

    # version MUST be present and non-empty.
    version = str(manifest.get("version") or "").strip()
    if not version:
        return None

    # ddi_shards MUST be a list of {file, ...} objects.
    shards = manifest.get("ddi_shards")
    if not isinstance(shards, list):
        return None

    parsed_rules: list[InteractionRule] = []
    seen_pairs: set[frozenset[str]] = set()
    for shard in shards:
        if not isinstance(shard, dict):
            return None
        shard_file = str(shard.get("file") or "").strip()
        if not shard_file:
            return None
        shard_path = _DRUGBANK_DIR / shard_file
        # Missing or unparseable referenced shard -> degrade entirely.
        try:
            shard_payload = json.loads(shard_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(shard_payload, dict):
            return None
        raw_rules = shard_payload.get("rules")
        if not isinstance(raw_rules, list):
            return None
        for raw_rule in raw_rules:
            if not isinstance(raw_rule, dict):
                continue
            meds = frozenset(_normalize_text_list(raw_rule.get("medications")))
            if len(meds) < 2 or meds in seen_pairs:
                continue
            seen_pairs.add(meds)
            parsed_rules.append(
                InteractionRule(
                    meds=meds,
                    severity=_normalize_severity(raw_rule.get("severity")),
                    message=(str(raw_rule.get("message", "")).strip() or "Potential DDI detected."),
                )
            )

    return parsed_rules, version


def _load_drugbank_ddi_rules() -> tuple[list[InteractionRule], str]:
    """Load DrugBank DDI shards (additive layer), caching by manifest mtime.

    Returns the parsed DrugBank rules plus the manifest version. The shards are
    generated by ``scripts/data/drugbank_ingest.py`` and live under
    ``nlp/seed_data/drugbank/``. The result is cached keyed by the manifest mtime,
    mirroring ``_load_local_ddi_rules``: the manifest + shards are re-parsed only
    when the manifest mtime changes. This loader is only ever invoked when the
    ``CAREGUARD_DRUGBANK_ENABLED`` flag is on, so when the flag is off the
    DrugBank directory is never touched and behavior is byte-identical to today.

    Degrade-to-curated (Req 5.3): a missing/unparseable/malformed manifest or any
    missing/unparseable referenced shard yields an empty DrugBank rule set
    (version ``"unknown"``), so ``_resolve_ddi_rules`` falls back to curated-only.
    The degrade outcome is cached against the offending mtime too, so we do not
    re-read a known-bad manifest on every analysis. This never raises.
    """
    global _DRUGBANK_DDI_CACHE_MTIME_NS
    global _DRUGBANK_DDI_CACHE_RULES
    global _DRUGBANK_DDI_CACHE_VERSION

    try:
        mtime_ns = _DRUGBANK_MANIFEST_PATH.stat().st_mtime_ns
    except OSError:
        # Missing manifest -> degrade to curated-only.
        _DRUGBANK_DDI_CACHE_MTIME_NS = None
        _DRUGBANK_DDI_CACHE_RULES = []
        _DRUGBANK_DDI_CACHE_VERSION = "unknown"
        return _DRUGBANK_DDI_CACHE_RULES, _DRUGBANK_DDI_CACHE_VERSION

    # Cache hit: re-parse only when the manifest mtime changes.
    if _DRUGBANK_DDI_CACHE_MTIME_NS == mtime_ns:
        return _DRUGBANK_DDI_CACHE_RULES, _DRUGBANK_DDI_CACHE_VERSION

    parsed = _verify_and_parse_drugbank_manifest()
    if parsed is None:
        # Malformed manifest or missing/unparseable shard -> degrade to
        # curated-only, caching the degrade against this mtime.
        _DRUGBANK_DDI_CACHE_MTIME_NS = mtime_ns
        _DRUGBANK_DDI_CACHE_RULES = []
        _DRUGBANK_DDI_CACHE_VERSION = "unknown"
        return _DRUGBANK_DDI_CACHE_RULES, _DRUGBANK_DDI_CACHE_VERSION

    parsed_rules, version = parsed
    _DRUGBANK_DDI_CACHE_MTIME_NS = mtime_ns
    _DRUGBANK_DDI_CACHE_RULES = parsed_rules
    _DRUGBANK_DDI_CACHE_VERSION = version
    return _DRUGBANK_DDI_CACHE_RULES, _DRUGBANK_DDI_CACHE_VERSION


def _resolve_ddi_rules() -> tuple[list[InteractionRule], str]:
    """Return the active DDI rule set + version label for the detector.

    Default (flag off): the curated Vietnamese ``careguard_ddi_rules.v1.json``
    rules, unchanged. When ``CAREGUARD_DRUGBANK_ENABLED`` is on, DrugBank shards
    are merged as a *lower-precedence* layer: a curated rule always wins on a
    conflicting medication pair (both its severity and Vietnamese message are
    preserved), and DrugBank only contributes pairs the curated set does not
    already cover.
    """
    curated_rules, curated_version = _load_local_ddi_rules()
    if not settings.careguard_drugbank_enabled:
        return curated_rules, curated_version

    drugbank_rules, drugbank_version = _load_drugbank_ddi_rules()
    if not drugbank_rules:
        return curated_rules, curated_version

    curated_pairs = {rule.meds for rule in curated_rules}
    merged_rules = list(curated_rules)
    for rule in drugbank_rules:
        if rule.meds in curated_pairs:
            continue
        merged_rules.append(rule)

    merged_version = f"{curated_version}+{drugbank_version}"
    return merged_rules, merged_version


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

    version = str(payload.get("version") or _VN_DRUG_DICTIONARY_PATH.stem).strip() or "unknown"
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


def _is_openfda_bad_request_error(error: object) -> bool:
    if not isinstance(error, str):
        return False
    return error.strip().lower().startswith("http_400")


def _sanitize_source_errors_for_output(
    source_errors: dict[str, list[str]],
    *,
    has_non_openfda_signal: bool,
) -> dict[str, list[str]]:
    sanitized: dict[str, list[str]] = {}
    for source_name, raw_errors in source_errors.items():
        normalized_errors = [
            str(raw_error).strip() for raw_error in raw_errors if str(raw_error).strip()
        ]
        if not normalized_errors:
            continue

        if source_name == "openfda":
            bad_request_errors = [
                error for error in normalized_errors if _is_openfda_bad_request_error(error)
            ]
            other_errors = [
                error for error in normalized_errors if not _is_openfda_bad_request_error(error)
            ]
            if other_errors:
                if has_non_openfda_signal:
                    sanitized[source_name] = sorted(set(other_errors))
                else:
                    sanitized[source_name] = sorted(set(other_errors + bad_request_errors))
                continue

            if not has_non_openfda_signal and bad_request_errors:
                sanitized[source_name] = sorted(set(bad_request_errors))
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


def _ddi_alert_from_rule(rule: InteractionRule) -> dict[str, Any]:
    """Build the End_User-localized alert dict for a matched interaction rule.

    Shared by both the linear (``_detect_ddi_alerts``) and pair-indexed
    (``_detect_ddi_alerts_indexed``) matchers so the two paths emit byte-identical
    alerts for the same rule (Property P8 index equivalence).
    """
    return {
        "type": "drug_drug",
        "severity": rule.severity,
        "medications": sorted(rule.meds),
        "message": _localize_ddi_message(rule.message),
        "source": "local_rules",
    }


def _detect_ddi_alerts(
    medications: list[str],
    rules: list[InteractionRule],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    med_set = set(medications)
    for rule in rules:
        if rule.meds.issubset(med_set):
            alerts.append(_ddi_alert_from_rule(rule))
    return alerts


def _build_ddi_pair_index(
    rules: list[InteractionRule],
) -> tuple[dict[frozenset[str], list[InteractionRule]], list[InteractionRule]]:
    """Partition rules into a two-medication pair index + a side list.

    The pair index keys each ``frozenset`` of exactly two normalized medication
    names to the interaction rule(s) for that pair, enabling O(1) lookup per
    candidate pair. Rules whose medication set is not exactly two (defensive: the
    loaders already drop ``< 2``) are returned separately and matched by a subset
    scan so the indexed matcher stays exactly equivalent to the linear matcher.
    """
    pair_index: dict[frozenset[str], list[InteractionRule]] = {}
    other_rules: list[InteractionRule] = []
    for rule in rules:
        if len(rule.meds) == 2:
            pair_index.setdefault(rule.meds, []).append(rule)
        else:
            other_rules.append(rule)
    return pair_index, other_rules


def _resolve_ddi_pair_index(
    rules: list[InteractionRule],
    version: str,
) -> tuple[dict[frozenset[str], list[InteractionRule]], list[InteractionRule]]:
    """Return the pair index for ``rules``, cached by the rule-set version label.

    The version label tracks the resolved rule set (curated, optionally
    ``+drugbank-…``) and is bumped by the underlying mtime-keyed loaders whenever
    the source files change, so caching on it rebuilds the index exactly when the
    rule set changes (Req 5.4).
    """
    global _DDI_PAIR_INDEX_CACHE_VERSION
    global _DDI_PAIR_INDEX_CACHE
    global _DDI_PAIR_INDEX_CACHE_OTHER

    if _DDI_PAIR_INDEX_CACHE_VERSION == version and (
        _DDI_PAIR_INDEX_CACHE or _DDI_PAIR_INDEX_CACHE_OTHER
    ):
        return _DDI_PAIR_INDEX_CACHE, _DDI_PAIR_INDEX_CACHE_OTHER

    pair_index, other_rules = _build_ddi_pair_index(rules)
    _DDI_PAIR_INDEX_CACHE_VERSION = version
    _DDI_PAIR_INDEX_CACHE = pair_index
    _DDI_PAIR_INDEX_CACHE_OTHER = other_rules
    return pair_index, other_rules


def _detect_ddi_alerts_indexed(
    medications: list[str],
    pair_index: dict[frozenset[str], list[InteractionRule]],
    other_rules: list[InteractionRule],
) -> list[dict[str, Any]]:
    """Pair-indexed equivalent of ``_detect_ddi_alerts`` (Req 5.4 / Property P8).

    Enumerates the C(n,2) distinct medication pairs and does an O(1) frozenset
    lookup into ``pair_index`` instead of scanning every rule. The resulting
    alert set is identical to the linear matcher for any rule set + medicine
    list; any non-pair rules are matched by the same subset scan as the linear
    path to preserve that equivalence.
    """
    alerts: list[dict[str, Any]] = []
    distinct_meds = sorted(set(medications))
    for i in range(len(distinct_meds)):
        for j in range(i + 1, len(distinct_meds)):
            matched = pair_index.get(frozenset((distinct_meds[i], distinct_meds[j])))
            if not matched:
                continue
            for rule in matched:
                alerts.append(_ddi_alert_from_rule(rule))

    if other_rules:
        med_set = set(medications)
        for rule in other_rules:
            if rule.meds.issubset(med_set):
                alerts.append(_ddi_alert_from_rule(rule))
    return alerts


def _apply_severity_floor(
    existing: dict[str, Any],
    incoming_severity: str,
    incoming_message: str,
    incoming_sources: set[str],
) -> None:
    """Raise an already-merged pair's severity to the max across all sources.

    Severity floor (INV / Req 4.1, 4.2): the merged severity for a medication
    pair equals the maximum severity asserted by any contributing source and is
    never lowered. A higher incoming severity raises the floor; a lower or equal
    one is ignored.

    INV-2 (Req 4.3): an openFDA-only signal (severity inferred from free text,
    capped at ``high`` in ``drug_sources.py``) may raise the severity floor but
    MUST NOT overwrite the curated Vietnamese message for the pair.
    """
    existing_rank = _SEVERITY_RANK[_normalize_severity(existing.get("severity"))]
    incoming_rank = _SEVERITY_RANK[incoming_severity]
    if incoming_rank > existing_rank:
        existing["severity"] = incoming_severity
        # INV-2: alert openfda-only (severity suy luận từ free-text) KHÔNG được
        # ghi đè message tiếng Việt đã biên tập của local rule.
        if incoming_sources != {"openfda"}:
            existing["message"] = incoming_message


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

        # Severity floor (max-severity-per-pair) + openFDA message protection.
        _apply_severity_floor(
            existing, incoming_severity, incoming_message, incoming_sources
        )

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

    has_high_risk_ddi = any(
        alert.get("type") == "drug_drug"
        and _normalize_severity(alert.get("severity")) in {"high", "critical"}
        for alert in ddi_alerts
    )
    has_medium_risk_ddi = any(
        alert.get("type") == "drug_drug" and _normalize_severity(alert.get("severity")) == "medium"
        for alert in ddi_alerts
    )

    # Base level from the aggregated score and the per-pair DDI floors. The
    # medium floor (CG-1) keeps a medium drug_drug alert from collapsing back to
    # low; the high-risk-DDI floor anchors a credible high pair at >= high.
    if has_high_risk_ddi and score >= 3:
        base_score, base_level = max(score, 5), "high"
    elif has_medium_risk_ddi:
        base_score, base_level = max(score, 1), "medium"
    elif score >= 9:
        base_score, base_level = score, "critical"
    elif score >= 5:
        base_score, base_level = score, "high"
    elif score >= 2:
        base_score, base_level = score, "medium"
    else:
        base_score, base_level = score, "low"

    # Emergency fast-path (Req 7.2 / Property 9): a recognized critical symptom
    # short-circuits the risk level to at least `high`, and to `critical` when
    # it co-occurs with a high-risk drug-drug interaction. This floor only ever
    # raises the level — it never lowers the base level the score/DDI logic set.
    if critical_symptoms:
        if has_high_risk_ddi:
            return max(base_score, 9), "critical"
        if _SEVERITY_RANK[base_level] < _SEVERITY_RANK["high"]:
            return max(base_score, 5), "high"
    return base_score, base_level


def _recommendation_for(
    level: str,
    ddi_alerts: list[dict[str, Any]],
    critical_symptoms: list[str],
) -> str:
    # Emergency fast-path (Req 7.2 / Property 9): a recognized critical symptom
    # short-circuits to an urgent-care directive regardless of the DDI-derived
    # level, with no diagnostic or prescriptive language.
    if critical_symptoms:
        return (
            "Triệu chứng hiện tại có thể là dấu hiệu cấp cứu. Hãy đến cơ sở y tế "
            "hoặc gọi cấp cứu ngay, nhất là khi có khó thở, đau ngực, ngất "
            "hoặc chảy máu nhiều."
        )

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
    if ddi_alerts:
        if "buồn ngủ" in primary_message or "chóng mặt" in primary_message:
            return "Theo dõi buồn ngủ hoặc chóng mặt. Tránh lái xe và vận hành máy nếu thấy lơ mơ."
        return "Theo dõi triệu chứng mới và hỏi bác sĩ hoặc dược sĩ nếu cần dùng cùng trong nhiều ngày."
    return "Chưa thấy nguy cơ tương tác lớn ngay lúc này. Nếu đơn thuốc thay đổi, nên kiểm tra lại."


# Fail-closed recommendation (Req 6.4): shown verbatim when the curated DDI rule
# store cannot be read. It explicitly states the check could not be completed and
# is NOT an "all-clear", so a degraded read never reassures the user falsely.
_RULES_UNAVAILABLE_RECOMMENDATION = (
    "Hiện chưa thể hoàn tất kiểm tra tương tác thuốc vì không đọc được dữ liệu "
    "tra cứu. Đây KHÔNG phải là kết luận \"không có tương tác\". Vui lòng thử lại "
    "sau và hỏi bác sĩ hoặc dược sĩ trước khi dùng nhiều thuốc cùng lúc."
)


def _rules_unavailable_result(
    *,
    raw_medications: list[str],
    medications: list[str],
    vn_dictionary_metadata: dict[str, Any],
    external_ddi_enabled: bool,
    external_ddi_flag_source: str,
    local_ddi_rules_version: str,
) -> dict:
    """Fail-closed analysis result when the curated DDI rule store is unreadable.

    Req 6.4 / 6.5: when the local curated rule store
    (``careguard_ddi_rules.v1.json``) cannot be read or yields no rules, the
    analysis MUST fail closed with a safe Vietnamese message and MUST NOT emit a
    fabricated all-clear (an empty "no interaction" result presented as
    reassurance). The risk level is the non-committal ``"unknown"`` (never
    ``"low"``), no alerts are returned, ``metadata.rules_unavailable`` is set so
    callers can detect the degraded path, and ``fallback_used`` is true (Req
    6.2). This metadata flag is only ever present on the fail-closed path, so the
    normal (rules-present) path stays byte-equivalent to baseline (Req 12.2).
    """
    return {
        "risk": {
            "level": "unknown",
            "score": 0,
            "factors": ["rules_unavailable"],
        },
        "ddi_alerts": [],
        "recommendation": _RULES_UNAVAILABLE_RECOMMENDATION,
        "metadata": {
            "pipeline": "p2-careguard-ddi-standard-v2",
            "fallback_used": True,
            "rules_unavailable": True,
            "external_ddi_enabled": external_ddi_enabled,
            "external_ddi_flag_source": external_ddi_flag_source,
            "local_ddi_rules_version": local_ddi_rules_version,
            "vn_dictionary_version": vn_dictionary_metadata.get("version", "unknown"),
            "vn_dictionary_record_count": vn_dictionary_metadata.get("record_count", 0),
            "vn_dictionary_mapped_count": vn_dictionary_metadata.get("mapped_count", 0),
            "vn_dictionary_mapped_items": vn_dictionary_metadata.get("mapped_items", []),
            "vn_dictionary_input_count": vn_dictionary_metadata.get("input_count", 0),
            "normalization_confidence": vn_dictionary_metadata.get("normalization_confidence", 0.0),
            "normalization_pair_coverage_low": False,
            "normalized_medication_count": len(medications),
            "raw_medication_count": len(raw_medications),
            "normalized_inputs": vn_dictionary_metadata.get("normalized_inputs", []),
            "source_used": [],
            "source_errors": {"local_rules": ["rules_unavailable"]},
            "openfda_pairs_checked": 0,
            "openfda_alert_count": 0,
            "rxnav_status": "",
        },
    }


def run_careguard_analyze(payload: dict) -> dict:
    symptoms = _normalize_text_list(payload.get("symptoms"))
    raw_medications = _normalize_text_list(payload.get("medications"))
    medications, vn_dictionary_metadata = _normalize_medications_with_vn_dictionary(raw_medications)
    allergies = _normalize_text_list(payload.get("allergies"))
    labs = payload.get("labs")

    external_ddi_flag_source = "runtime" if "external_ddi_enabled" in payload else "env"
    external_ddi_enabled = _as_bool(
        payload.get("external_ddi_enabled"),
        default=settings.external_ddi_enabled,
    )

    local_rules, local_ddi_rules_version = _resolve_ddi_rules()

    # Fail-closed for safety (Req 6.4 / 6.5): if the curated rule store itself is
    # unreadable/empty we must not fabricate an all-clear. `_load_local_ddi_rules`
    # returns an empty list when `careguard_ddi_rules.v1.json` cannot be read or
    # parsed (and no prior good copy is cached); detect that here and return a
    # safe, non-committal Vietnamese result instead of an empty "no interaction"
    # one. Checked against the curated store specifically so a missing optional
    # DrugBank layer never triggers fail-closed.
    curated_rules, _ = _load_local_ddi_rules()
    if not curated_rules:
        return _rules_unavailable_result(
            raw_medications=raw_medications,
            medications=medications,
            vn_dictionary_metadata=vn_dictionary_metadata,
            external_ddi_enabled=external_ddi_enabled,
            external_ddi_flag_source=external_ddi_flag_source,
            local_ddi_rules_version=local_ddi_rules_version,
        )

    if settings.careguard_ddi_index_enabled:
        pair_index, other_rules = _resolve_ddi_pair_index(local_rules, local_ddi_rules_version)
        local_ddi_alerts = _detect_ddi_alerts_indexed(medications, pair_index, other_rules)
    else:
        local_ddi_alerts = _detect_ddi_alerts(medications, local_rules)
    source_used = ["local_rules"]
    source_errors: dict[str, list[str]] = {}
    external_ddi_alerts: list[dict[str, Any]] = []
    openfda_alerts: list[dict[str, Any]] = []
    openfda_evidence: dict[tuple[str, str], dict[str, int]] = {}
    openfda_pairs_checked = 0
    rxnav_status = ""
    needs_external_lookup = len(set(medications)) >= 2

    if needs_external_lookup and external_ddi_enabled:
        try:
            # Favor deterministic fallback behavior on slow upstreams by avoiding retry storms.
            external = DrugSourceClient(
                timeout_seconds=settings.external_ddi_timeout_seconds,
                max_retries=0,
            ).fetch_ddi_context(medications)
            external_ddi_alerts = external.rxnav_alerts
            openfda_alerts = external.openfda_alerts
            openfda_evidence = external.openfda_evidence
            openfda_pairs_checked = int(getattr(external, "openfda_pairs_checked", 0))
            rxnav_status = getattr(external, "rxnav_status", "")
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

    # INV-3: chỉ tính local + rxnav (KHÔNG tính openfda) cho cờ suppress http_400.
    has_non_openfda_signal = bool(local_ddi_alerts or external_ddi_alerts) or (
        "rxnav" in source_used
    )
    source_errors = _sanitize_source_errors_for_output(
        source_errors,
        has_non_openfda_signal=has_non_openfda_signal,
    )

    # Synthetic-alert suppression (INV-2): openfda_alerts (suy luận từ nhãn/sự kiện FDA)
    # openfda_evidence (co-occurrence counts từ FAERS) chỉ enrich các cặp thuốc đã có
    # alert từ local_rules/rxnav — KHÔNG tự tạo alert độc lập (INV-2). Ngược lại,
    # openfda_alerts là tương tác THẬT đọc từ mục `drug_interactions` của nhãn FDA
    # (tầng label-alert của fixUI) nên ĐƯỢC nhập merge như alert hợp lệ; chúng mang
    # sẵn source="openfda" nên không ghi đè message tiếng Việt của local rule.
    ddi_alerts = _merge_drug_alerts(
        local_ddi_alerts, external_ddi_alerts + openfda_alerts, openfda_evidence
    )
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
            "openfda_alert_count": len(openfda_alerts),
            "rxnav_status": rxnav_status,
        },
    }
