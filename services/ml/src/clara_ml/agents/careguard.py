# ruff: noqa: E501
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clara_ml.agents.careguard_ddi_store import DrugBankDdiStore
from clara_ml.clients.drug_sources import DrugSourceClient
from clara_ml.config import settings
from clara_ml.language_renderer import (
    RenderingInput,
    render_careguard_wording_draft,
    render_explanation,
)
from clara_ml.language_renderer.schemas import ActionCode, Audience, Severity
from clara_ml.nlp.vietnamese_clinical import (
    analyze_vietnamese_clinical_text,
    fold_vietnamese_for_matching,
)
from clara_ml.nlp_vi import enrich_clinical_utterance_with_llm


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


def _configured_drugbank_paths() -> tuple[Path, Path, Path]:
    """Resolve the deployment-owned DrugBank bundle without exposing paths.

    Empty settings preserve the package-local development fixture. Production
    may mount a licensed bundle outside the image and point the manifest and
    SQLite index at independent, container-visible locations. The manifest's
    directory remains the only permitted root for its relative shard paths.
    """

    configured_manifest = settings.careguard_drugbank_manifest_path.strip()
    manifest_path = Path(configured_manifest) if configured_manifest else _DRUGBANK_MANIFEST_PATH
    configured_sqlite = settings.careguard_drugbank_sqlite_path.strip()
    sqlite_path = Path(configured_sqlite) if configured_sqlite else manifest_path.parent / "ddi_index.sqlite"
    return manifest_path.parent, manifest_path, sqlite_path

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

# ``medication_text`` is a deliberately bounded, opt-in input for a person who
# writes a medicine list as a Vietnamese sentence rather than one array item per
# medicine.  It is not a clinical note parser: exact aliases are merely
# candidates for the existing DrugBank identity resolver below.  Keeping this
# limit here (rather than trusting the API proxy) protects every internal caller
# of ``run_careguard_analyze`` as well.
_MAX_MEDICATION_TEXT_CHARS = 2_000
_MAX_FREE_TEXT_MEDICATION_CANDIDATES = 24
_FREE_TEXT_MEDICATION_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "bao",
        "bi",
        "cung",
        "co",
        "cua",
        "dang",
        "de",
        "duoc",
        "hay",
        "hoac",
        "la",
        "minh",
        "mot",
        "nhung",
        "sau",
        "toi",
        "tren",
        "va",
        "voi",
        "uống",
        "uong",
        "dung",
        "xai",
        "su",
        "dung",
        "taking",
        "take",
        "on",
        "medication",
        "medicine",
        "drug",
        "thuoc",
        "thuốc",
        "vien",
        "viên",
        "sang",
        "trua",
        "toi",
        "ngay",
        "lan",
    }
)
_FREE_TEXT_MEDICATION_CONTEXT = re.compile(
    r"(?:thuốc|thuoc|medicine|medication|drug)\s+([\w-]{2,64})",
    re.IGNORECASE,
)


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
    drugbank_store = (
        _get_drugbank_store() if settings.careguard_drugbank_sqlite_enabled else None
    )
    drugbank_dictionary_version = drugbank_store.version if drugbank_store else ""

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
        rxcui = _VN_DICTIONARY_RXCUI_MAP.get(canonical, "")
        drugbank_id = ""
        resolution_source = "vn_dictionary" if canonical != canonical_input else "input"

        # The verified DrugBank dictionary is a deterministic alias lookup. It
        # does not guess or use an LLM; a miss intentionally leaves the local
        # normalized token unchanged. This preserves the Vietnamese dictionary
        # as an additive layer while exposing licensed-source traceability.
        if drugbank_store is not None:
            resolution = None
            for candidate in (input_token, canonical_input, canonical):
                resolution = drugbank_store.resolve_medication(candidate)
                if resolution is not None:
                    break
            if resolution is not None:
                canonical = str(resolution["normalized_name"])
                resolved_actives = resolution.get("active_ingredients")
                if isinstance(resolved_actives, list):
                    active_ingredients = [
                        str(item)
                        for item in resolved_actives
                        if isinstance(item, str) and item
                    ] or [canonical]
                rxcui = str(resolution.get("rxcui") or "")
                drugbank_id = str(resolution.get("drugbank_id") or "")
                resolution_source = "drugbank_dictionary"
        normalized_inputs.append(
            {
                "input": input_token,
                "canonical_input": canonical_input,
                "normalized_name": canonical,
                "resolution_source": resolution_source,
                "drugbank_id": drugbank_id,
            }
        )

        if canonical != input_token or canonical_input != input_token:
            mapped_items.append(
                {
                    "input": input_token,
                    "canonical_input": canonical_input,
                    "normalized_name": canonical,
                    "rxcui": rxcui,
                    "drugbank_id": drugbank_id,
                    "resolution_source": resolution_source,
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
        "drugbank_dictionary_version": drugbank_dictionary_version,
    }


def _valid_cabinet_item_id(value: object) -> int | None:
    """Accept only a bounded positive integer supplied by the trusted API."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 2_147_483_647:
        return None
    return value


def _strict_drugbank_input_rows(
    medications: list[str],
    medications_with_meta: object,
) -> list[tuple[str, int | None]]:
    """Bind trusted cabinet IDs only when every duplicate alias is unambiguous.

    `medications_with_meta` is an API-internal transport envelope, never an
    authorization source.  An entry can bind only through a positive
    ``cabinet_item_id`` and an exact ``input_alias`` that appears in the request
    medication list.  Duplicate aliases receive IDs only when the number of
    unique trusted entries exactly matches the number of raw occurrences; any
    mismatch leaves every duplicate unbound rather than risking a selection for
    the wrong cabinet item.
    """

    aliases = [
        _canonicalize_medication_token(_normalize_text_token(medication))
        for medication in medications
    ]
    rows = [(alias, None) for alias in aliases if alias]
    if not isinstance(medications_with_meta, list):
        return rows

    positions_by_alias: dict[str, list[int]] = {}
    for position, (alias, _item_id) in enumerate(rows):
        positions_by_alias.setdefault(alias, []).append(position)
    ids_by_alias: dict[str, list[int]] = {}
    for entry in medications_with_meta[:100]:
        if not isinstance(entry, dict):
            continue
        item_id = _valid_cabinet_item_id(entry.get("cabinet_item_id"))
        alias = _canonicalize_medication_token(_normalize_text_token(entry.get("input_alias")))
        if item_id is None or not alias or alias not in positions_by_alias:
            continue
        ids_by_alias.setdefault(alias, []).append(item_id)

    for alias, positions in positions_by_alias.items():
        item_ids = ids_by_alias.get(alias, [])
        if len(item_ids) != len(positions) or len(set(item_ids)) != len(item_ids):
            continue
        for position, item_id in zip(positions, item_ids, strict=True):
            rows[position] = (alias, item_id)
    return rows


def _requested_drugbank_resolutions(
    value: object,
) -> tuple[dict[int, tuple[str, str, str] | None], dict[str, tuple[str, str] | None]]:
    """Parse a bounded selection packet without trusting its identifiers.

    The API will bind a selection to an owner-scoped cabinet item.  ML repeats
    the source binding here: this helper only associates the request with a
    normalized user alias; :meth:`DrugBankDdiStore.resolve_medication_choice`
    later checks the identifier and artifact version against the licensed index.
    Conflicting duplicate selections deliberately become invalid rather than
    allowing request order to choose a medication identity.
    """

    if not isinstance(value, list):
        return {}, {}
    requested_by_item: dict[int, tuple[str, str, str] | None] = {}
    requested_by_alias: dict[str, tuple[str, str] | None] = {}
    for entry in value[:100]:
        if not isinstance(entry, dict):
            continue
        alias = _canonicalize_medication_token(_normalize_text_token(entry.get("input_alias")))
        drugbank_id = str(entry.get("drugbank_id") or "").strip()[:128]
        source_version = str(entry.get("drugbank_version") or "").strip()[:128]
        if not alias:
            continue
        candidate = (drugbank_id, source_version) if drugbank_id and source_version else None
        item_id = _valid_cabinet_item_id(entry.get("cabinet_item_id"))
        if item_id is not None:
            item_candidate = (alias, drugbank_id, source_version) if candidate else None
            if item_id in requested_by_item and requested_by_item[item_id] != item_candidate:
                requested_by_item[item_id] = None
            else:
                requested_by_item[item_id] = item_candidate
        elif alias in requested_by_alias and requested_by_alias[alias] != candidate:
            requested_by_alias[alias] = None
        else:
            requested_by_alias[alias] = candidate
    return requested_by_item, requested_by_alias


def _strict_drugbank_candidate_view(
    candidate: dict[str, object],
    *,
    source_version: str,
) -> dict[str, object] | None:
    """Return only a bounded, source-backed candidate safe for user selection."""

    drugbank_id = str(candidate.get("drugbank_id") or "").strip()
    normalized_name = _normalize_text_token(candidate.get("normalized_name"))
    active_ingredients = candidate.get("active_ingredients")
    if not drugbank_id or not normalized_name or not isinstance(active_ingredients, list):
        return None
    return {
        "drugbank_id": drugbank_id,
        "normalized_name": normalized_name,
        "active_ingredients": [
            _normalize_text_token(item) for item in active_ingredients if _normalize_text_token(item)
        ][:12]
        or [normalized_name],
        "rxcui": str(candidate.get("rxcui") or "").strip()[:64],
        "source_version": source_version,
    }


def _normalize_medications_with_strict_drugbank_choices(
    medications: list[str],
    *,
    requested_resolutions: object,
    medications_with_meta: object,
) -> tuple[list[str], dict[str, Any]]:
    """Resolve medication identity only from a current licensed DrugBank choice.

    This function is intentionally isolated from the legacy Vietnamese
    dictionary/alias-map path.  When the rollout flag is enabled, an unknown or
    many-to-one alias becomes a terminal clarification requirement—not a local
    mapping, fuzzy guess, model prediction, or partial DDI check.
    """

    version, record_count = _load_vn_drug_dictionary()
    resolution_requests_by_item, resolution_requests_by_alias = _requested_drugbank_resolutions(
        requested_resolutions
    )
    store = _get_drugbank_store()
    source_version = store.version if store is not None else ""
    normalized_medications: list[str] = []
    normalized_inputs: list[dict[str, str]] = []
    mapped_items: list[dict[str, str]] = []
    clarifications: list[dict[str, object]] = []
    seen: set[str] = set()

    for input_token, cabinet_item_id in _strict_drugbank_input_rows(
        medications,
        medications_with_meta,
    ):
        candidates = store.medication_candidates(input_token) if store is not None else []
        requested = (
            resolution_requests_by_item.get(cabinet_item_id)
            if cabinet_item_id is not None
            else resolution_requests_by_alias.get(input_token)
        )
        selection_alias_matches_item = bool(
            cabinet_item_id is None
            or requested is None
            or requested[0] == input_token
        )
        selected: dict[str, object] | None = None
        clarification_reason = ""
        if requested is not None and selection_alias_matches_item:
            selected_id, selected_version = (
                (requested[1], requested[2])
                if cabinet_item_id is not None
                else requested
            )
            selected = store.resolve_medication_choice(
                input_token,
                drugbank_id=selected_id,
                source_version=selected_version,
            ) if store is not None else None
            if selected is None:
                clarification_reason = "invalid_or_stale_selection"
        elif (
            (cabinet_item_id is not None and cabinet_item_id in resolution_requests_by_item)
            or (cabinet_item_id is None and input_token in resolution_requests_by_alias)
        ):
            clarification_reason = "invalid_or_conflicting_selection"
        elif len(candidates) == 1:
            selected = candidates[0]
            if _strict_drugbank_candidate_view(selected, source_version=source_version) is None:
                selected = None
                clarification_reason = "candidate_missing_stable_identifier"
        elif len(candidates) > 1:
            clarification_reason = "ambiguous_alias"
        else:
            clarification_reason = "unrecognized_alias"

        if selected is None:
            clarification_candidates = [
                view
                for item in candidates
                if (view := _strict_drugbank_candidate_view(item, source_version=source_version))
                is not None
            ]
            clarification: dict[str, object] = {
                "input_alias": input_token,
                "reason": clarification_reason or "unrecognized_alias",
                "candidates": clarification_candidates,
            }
            if cabinet_item_id is not None:
                clarification["cabinet_item_id"] = cabinet_item_id
            clarifications.append(clarification)
            continue

        selected_view = _strict_drugbank_candidate_view(selected, source_version=source_version)
        if selected_view is None:
            clarification = {
                "input_alias": input_token,
                "reason": "candidate_missing_stable_identifier",
                "candidates": [],
            }
            if cabinet_item_id is not None:
                clarification["cabinet_item_id"] = cabinet_item_id
            clarifications.append(clarification)
            continue
        canonical = str(selected_view["normalized_name"])
        active_ingredients = list(selected_view["active_ingredients"])
        normalized_inputs.append(
            {
                "input": input_token,
                "canonical_input": input_token,
                "normalized_name": canonical,
                "resolution_source": "drugbank_user_choice"
                if requested is not None and selection_alias_matches_item
                else "drugbank_dictionary",
                "drugbank_id": str(selected_view["drugbank_id"]),
            }
        )
        if canonical != input_token:
            mapped_items.append(
                {
                    "input": input_token,
                    "canonical_input": input_token,
                    "normalized_name": canonical,
                    "rxcui": str(selected_view["rxcui"]),
                    "drugbank_id": str(selected_view["drugbank_id"]),
                    "resolution_source": "drugbank_user_choice"
                    if requested is not None and selection_alias_matches_item
                    else "drugbank_dictionary",
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

    input_count = len([m for m in medications if _normalize_text_token(m)])
    mapped_count = len(mapped_items)
    return normalized_medications, {
        "version": version,
        "record_count": record_count,
        "mapped_count": mapped_count,
        "mapped_items": mapped_items[:20],
        "input_count": input_count,
        "normalization_confidence": round(
            min(max((len(normalized_inputs) / input_count) if input_count else 1.0, 0.0), 1.0),
            3,
        ),
        "pair_coverage_ratio": round(
            min(
                max((len(normalized_medications) / input_count) if input_count else 1.0, 0.0),
                1.0,
            ),
            3,
        ),
        "normalized_inputs": normalized_inputs[:20],
        "drugbank_dictionary_version": source_version,
        "clarifications": clarifications[:20],
    }


def _bounded_medication_text(value: object) -> tuple[str, str]:
    """Return a bounded, explicit free-text medication field.

    The caller must use the dedicated ``medication_text`` field.  In
    particular, we never reinterpret an arbitrary symptom, chat, or note field
    as a medicine list.  A malformed or oversized value is a clarification
    condition rather than a best-effort truncation that could silently omit a
    medicine from an interaction check.
    """

    if value is None:
        return "", "absent"
    if not isinstance(value, str):
        return "", "invalid"
    text = value.strip()
    if not text:
        return "", "empty"
    if len(text) > _MAX_MEDICATION_TEXT_CHARS:
        return "", "too_long"
    return text, "valid"


def _append_unique_medication_candidate(
    values: list[str],
    candidate: str,
) -> None:
    normalized = _canonicalize_medication_token(_normalize_text_token(candidate))
    if not normalized or any(_normalize_text_token(item) == normalized for item in values):
        return
    values.append(normalized)


def _free_text_medication_candidates(
    medication_text: str,
    *,
    field_state: str,
) -> tuple[list[str], dict[str, object]]:
    """Extract only exact, reviewable aliases from Vietnamese list-like text.

    Vietnamese clinical NLP contributes surface candidates and ambiguity cues;
    the local Vietnamese dictionary contributes known exact phrases; and a
    ready DrugBank index may contribute *only* exact alias matches.  None of
    these paths chooses a DrugBank identity.  The strict resolver below remains
    responsible for one-vs-many selection and source-version validation.
    """

    empty_metadata: dict[str, object] = {
        "state": "not_used"
        if field_state in {"absent", "empty"}
        else "requires_clarification",
        "field_state": field_state,
        "extracted_candidate_count": 0,
        "ambiguous_candidate_count": 0,
        "unresolved_text_present": field_state not in {"absent", "empty"},
        "extractor": "deterministic_vietnamese_clinical_v1",
    }
    if field_state in {"absent", "empty"}:
        return [], empty_metadata
    if field_state != "valid":
        return [], empty_metadata

    analysis = analyze_vietnamese_clinical_text(medication_text)
    normalized_text = analysis.normalized_text
    folded_text = fold_vietnamese_for_matching(normalized_text)
    candidates: list[str] = []
    matched_aliases: set[str] = set()
    matched_spans: list[tuple[int, int]] = []

    # The small local dictionary is an exact phrase inventory.  Scan longest
    # first so an input such as "panadol extra" is preserved as that full alias,
    # not as a shorter overlapping product name.
    _load_vn_drug_dictionary()
    for alias in sorted(_VN_DICTIONARY_ALIAS_LOOKUP, key=lambda item: (-len(item), item)):
        folded_alias = fold_vietnamese_for_matching(alias)
        if len(folded_alias) < 3:
            continue
        for match in re.finditer(rf"(?<!\w){re.escape(folded_alias)}(?!\w)", folded_text):
            if any(match.start() < end and start < match.end() for start, end in matched_spans):
                continue
            _append_unique_medication_candidate(candidates, alias)
            matched_aliases.add(folded_alias)
            matched_spans.append((match.start(), match.end()))
            if len(candidates) >= _MAX_FREE_TEXT_MEDICATION_CANDIDATES:
                break
        if len(candidates) >= _MAX_FREE_TEXT_MEDICATION_CANDIDATES:
            break

    # NLP mentions include known Vietnamese shorthand and spelling variants.
    # We preserve their exact source surface, never their suggested canonical
    # name, so the next stage still has to prove the alias against DrugBank.
    ambiguous_candidate_count = 0
    for mention in analysis.medication_mentions:
        if mention.ambiguous:
            ambiguous_candidate_count += 1
        folded_surface = fold_vietnamese_for_matching(mention.surface)
        if any(
            re.search(rf"(?<!\w){re.escape(folded_surface)}(?!\w)", alias)
            for alias in matched_aliases
        ):
            continue
        _append_unique_medication_candidate(candidates, mention.surface)

    # A complete licensed index may contain aliases outside the small public
    # dictionary.  Probe bounded token n-grams and retain only exact index
    # aliases.  This is deterministic source lookup, not fuzzy matching or an
    # LLM-mediated canonicalization.  Querying a not-ready index contributes no
    # candidates; the unresolved gate below then fails closed.
    store = _get_drugbank_store() if settings.careguard_drugbank_sqlite_enabled else None
    tokens = re.findall(r"[\w-]+", normalized_text, flags=re.UNICODE)
    for width in range(min(4, len(tokens)), 0, -1):
        if len(candidates) >= _MAX_FREE_TEXT_MEDICATION_CANDIDATES:
            break
        for start in range(0, len(tokens) - width + 1):
            phrase_tokens = tokens[start : start + width]
            folded_phrase_tokens = [fold_vietnamese_for_matching(token) for token in phrase_tokens]
            if not phrase_tokens or all(token in _FREE_TEXT_MEDICATION_STOPWORDS for token in folded_phrase_tokens):
                continue
            if any(token.isdigit() for token in phrase_tokens):
                continue
            alias = _canonicalize_medication_token(" ".join(phrase_tokens))
            folded_alias = fold_vietnamese_for_matching(alias)
            if not alias or any(
                re.search(rf"(?<!\w){re.escape(folded_alias)}(?!\w)", item)
                for item in matched_aliases
            ):
                continue
            if store is not None and store.medication_candidates(alias):
                _append_unique_medication_candidate(candidates, alias)
                matched_aliases.add(folded_alias)
                if len(candidates) >= _MAX_FREE_TEXT_MEDICATION_CANDIDATES:
                    break

    # Do not call a partial extraction a complete medication list.  If the
    # field supplied no exact source-backed candidate, or a user explicitly
    # names an unrecognised "thuốc ..." item, require clarification.  The
    # response intentionally exposes only categorical/count metadata, never
    # free-text content through telemetry or operational output.
    unresolved_context = False
    for context_match in _FREE_TEXT_MEDICATION_CONTEXT.finditer(normalized_text):
        named_token = fold_vietnamese_for_matching(context_match.group(1))
        if not any(
            re.search(rf"(?<!\w){re.escape(named_token)}(?!\w)", alias)
            for alias in matched_aliases
        ):
            unresolved_context = True
            break
    unresolved_text = not candidates or unresolved_context
    metadata = {
        "state": "requires_clarification"
        if unresolved_text or ambiguous_candidate_count
        else "used",
        "field_state": field_state,
        "extracted_candidate_count": len(candidates),
        "ambiguous_candidate_count": ambiguous_candidate_count,
        "unresolved_text_present": unresolved_text,
        "extractor": "deterministic_vietnamese_clinical_v1",
    }
    return candidates, metadata


def _free_text_medication_clarification_result(
    *,
    raw_medications: list[str],
    symptoms: list[str],
    extraction: dict[str, object],
) -> dict[str, Any]:
    """Fail closed before DDI when a free-text medicine list is incomplete."""

    return {
        "status": "requires_medication_clarification",
        "clarifications": [
            {
                "reason": "free_text_medication_identity_unresolved",
                "candidates": [],
            }
        ],
        "urgent_support_required": bool(_critical_symptom_hits(symptoms)),
        "metadata": {
            "pipeline": "p2-careguard-ddi-standard-v2",
            "clarification_required": True,
            "clarification_source": "deterministic_vietnamese_medication_extraction",
            "raw_medication_count": len(raw_medications),
            "normalized_medication_count": 0,
            "free_text_medication_extraction": extraction,
        },
    }


def _augment_raw_medications_with_validated_spans(
    raw_medications: list[str],
) -> tuple[list[str], dict[str, object]]:
    """Optionally add exact original medication spans to deterministic lookup.

    The model cannot provide a normalized drug, DrugBank ID, dose, interaction,
    severity, or recommendation. It may only nominate an exact substring of
    the user's original input; deterministic Vietnamese/DrugBank resolution is
    still the sole authority for what is actually checked.
    """

    baseline = list(raw_medications)
    if not (
        settings.clinical_language_llm_extraction_enabled
        and settings.careguard_clinical_span_augmentation_enabled
        and baseline
    ):
        return baseline, {"state": "disabled", "added_candidate_count": 0}
    source_text = "\n".join(baseline)
    packet = enrich_clinical_utterance_with_llm(source_text, settings=settings)
    if packet.implementation != "hybrid_source_spans_v1":
        return baseline, {"state": "fallback", "added_candidate_count": 0}

    candidates = list(baseline)
    seen = {item.casefold().strip() for item in candidates}
    for span in packet.source_spans:
        if span.category != "medication":
            continue
        candidate = source_text[span.start : span.end].strip()
        # A candidate spanning separate input rows is ambiguous. Preserve the
        # raw rows and do not manufacture a joined medication name.
        if not candidate or "\n" in candidate or candidate.casefold() in seen:
            continue
        seen.add(candidate.casefold())
        candidates.append(candidate)
    return candidates, {
        "state": "used",
        "added_candidate_count": len(candidates) - len(baseline),
        "model_version": packet.extractor_model_version,
        "prompt_version": packet.extractor_prompt_version,
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


def _ddi_alert_from_rule(
    rule: InteractionRule,
    *,
    source: str = "local_rules",
) -> dict[str, Any]:
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
        "source": source,
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


# Module-level on-disk DrugBank store (memory-safe SQLite pair index). Built
# lazily on first use and reused thereafter; a build/lookup failure degrades to
# no DrugBank contribution (curated-only), so this never crashes analysis.
_DRUGBANK_STORE: DrugBankDdiStore | None = None
_DRUGBANK_STORE_READY: bool = False


def _get_drugbank_store() -> DrugBankDdiStore | None:
    """Return the built DrugBank SQLite store, or None to degrade to curated-only.

    The store is constructed once and its on-disk index is built once (idempotent:
    a matching-version DB is reused without a rebuild). Any failure returns None.
    """
    global _DRUGBANK_STORE, _DRUGBANK_STORE_READY
    if _DRUGBANK_STORE_READY:
        try:
            if (
                _DRUGBANK_STORE is not None
                and _DRUGBANK_STORE.readiness().get("state") == "ready"
            ):
                return _DRUGBANK_STORE
        except Exception:  # noqa: BLE001 - a readiness failure must fail closed
            pass
        # A mounted bundle can arrive or be atomically refreshed after this
        # process started. Re-evaluate a degraded/missing store instead of
        # retaining an unsafe stale cache until a manual restart.
        _DRUGBANK_STORE_READY = False
        _DRUGBANK_STORE = None
    try:
        drugbank_dir, manifest_path, sqlite_path = _configured_drugbank_paths()
        store = DrugBankDdiStore(
            drugbank_dir=drugbank_dir,
            manifest_path=manifest_path,
            sqlite_path=sqlite_path,
            integrity_required=settings.careguard_drugbank_manifest_integrity_required,
        )
        built_version = store.ensure_built()
        _DRUGBANK_STORE = store if built_version else None
    except Exception:  # noqa: BLE001 - never let store init break analysis
        _DRUGBANK_STORE = None
    _DRUGBANK_STORE_READY = True
    return _DRUGBANK_STORE


def _drugbank_sqlite_alerts(
    medications: list[str],
    *,
    existing_alerts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """DrugBank DDI alerts from the on-disk SQLite store + the built version label.

    ``existing_alerts`` is retained for backward-compatible callers that want to
    suppress already-covered pairs. The production analysis passes an empty list
    because DrugBank is authoritative whenever its full index is ready.

    Each hit carries record-level provenance: the licensed source, artifact
    version, normalized pair, and original DrugBank interaction statement. Never
    raises: a missing/failed store yields no contribution and an empty version
    label so the caller can fail closed or use its explicitly marked fallback.
    """
    store = _get_drugbank_store()
    if store is None:
        return [], ""
    readiness = store.readiness()
    if (
        readiness.get("state") != "ready"
        or not readiness.get("manifest_matches_index")
        or not readiness.get("version")
    ):
        return [], ""
    covered_pairs: set[frozenset[str]] = set()
    for alert in existing_alerts:
        meds = alert.get("medications")
        if isinstance(meds, list) and len(meds) == 2:
            covered_pairs.add(frozenset(str(m) for m in meds))
    alerts: list[dict[str, Any]] = []
    for meds, severity, message in store.lookup_pairs(medications):
        if meds in covered_pairs:
            continue
        alert = _ddi_alert_from_rule(
            InteractionRule(meds=meds, severity=severity, message=message),
            source="drugbank",
        )
        alert.update(
            {
                "source_version": store.version,
                "source_statement": message,
                "reference": {
                    "source": "DrugBank",
                    "version": store.version,
                    "medication_pair": sorted(meds),
                },
            }
        )
        alerts.append(alert)
    return alerts, store.version


def get_drugbank_readiness() -> dict[str, object]:
    """Return a content-free readiness projection for the licensed DDI index."""

    if not settings.careguard_drugbank_sqlite_enabled:
        return {
            "state": "disabled",
            "version": "",
            "pair_count": 0,
            "dictionary_record_count": 0,
            "manifest_matches_index": False,
            "integrity_verified": False,
            "required": bool(settings.careguard_drugbank_required),
        }
    store = _get_drugbank_store()
    if store is None:
        return {
            "state": "unavailable",
            "version": "",
            "pair_count": 0,
            "dictionary_record_count": 0,
            "manifest_matches_index": False,
            "integrity_verified": False,
            "required": bool(settings.careguard_drugbank_required),
        }
    readiness = store.readiness()
    readiness["required"] = bool(settings.careguard_drugbank_required)
    return readiness


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
            merged_alert: dict[str, Any] = {
                "type": "drug_drug",
                "severity": incoming_severity,
                "medications": list(key),
                "message": incoming_message,
                "_sources": incoming_sources,
            }
            if "drugbank" in incoming_sources:
                for provenance_key in (
                    "source_version",
                    "source_statement",
                    "reference",
                ):
                    if alert.get(provenance_key) is not None:
                        merged_alert[provenance_key] = alert[provenance_key]
            merged_by_pair[key] = merged_alert
            return

        # Severity floor (max-severity-per-pair) + openFDA message protection.
        _apply_severity_floor(existing, incoming_severity, incoming_message, incoming_sources)

        existing_sources = existing.setdefault("_sources", set())
        if isinstance(existing_sources, set):
            existing_sources.update(incoming_sources)
        if "drugbank" in incoming_sources:
            for provenance_key in (
                "source_version",
                "source_statement",
                "reference",
            ):
                if alert.get(provenance_key) is not None:
                    existing[provenance_key] = alert[provenance_key]

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
    'tra cứu. Đây KHÔNG phải là kết luận "không có tương tác". Vui lòng thử lại '
    "sau và hỏi bác sĩ hoặc dược sĩ trước khi dùng nhiều thuốc cùng lúc."
)

_DRUGBANK_REQUIRED_UNAVAILABLE_RECOMMENDATION = (
    "Hiện chưa thể hoàn tất kiểm tra tương tác thuốc vì dữ liệu DrugBank bắt buộc "
    "không sẵn sàng hoặc chưa vượt qua kiểm tra toàn vẹn. Đây KHÔNG phải là kết "
    'luận "không có tương tác". Không tự bắt đầu, ngừng hoặc thay đổi thuốc dựa '
    "trên kết quả này; vui lòng thử lại và hỏi bác sĩ hoặc dược sĩ."
)


def _consumer_wording_from_final_result(
    result: dict[str, Any],
    *,
    locale: str,
) -> dict[str, Any]:
    """Render an additive consumer projection from final deterministic facts.

    This boundary deliberately receives *only* the final CareGuard result.  It
    cannot invoke DrugBank, inspect a raw medication string, alter a severity,
    or alter the legacy recommendation.  The output is therefore suitable as a
    feature-flagged presentation aid while the existing DDI object remains the
    authoritative API contract.
    """

    risk = result.get("risk")
    metadata = result.get("metadata")
    if not isinstance(risk, dict) or not isinstance(metadata, dict):
        return {}

    level = str(risk.get("level") or "unknown").strip().lower()
    severity_by_level: dict[str, Severity] = {
        "critical": "emergency",
        "high": "urgent_review",
        "medium": "clinical_review",
        "low": "routine",
        # An unavailable DDI conclusion must never look like an all-clear.
        "unknown": "clinical_review",
    }
    severity = severity_by_level.get(level, "clinical_review")
    action_by_severity: dict[Severity, list[ActionCode]] = {
        "emergency": ["seek_emergency"],
        "urgent_review": ["contact_clinician"],
        "clinical_review": ["contact_clinician"],
        "routine": ["monitor"],
    }

    audience: Audience = "en" if locale.lower().startswith("en") else "lay_vi"
    english = audience == "en"
    warnings: list[str] = []
    ddi_status = result.get("ddi_status")
    conclusion_available = not (
        isinstance(ddi_status, dict) and ddi_status.get("conclusion_available") is False
    )
    if metadata.get("rules_unavailable") or not conclusion_available:
        warnings.append(
            "The required source could not fully verify the medication interaction; "
            "no alert does not mean it is safe."
            if english
            else "Chưa thể xác nhận đầy đủ tương tác thuốc từ nguồn bắt buộc; "
            "không có cảnh báo không đồng nghĩa là an toàn."
        )
    if metadata.get("normalization_pair_coverage_low"):
        warnings.append(
            "One or more medicines may not have been identified well enough to check every pair."
            if english
            else "Có thể chưa nhận diện đủ thuốc để kiểm tra toàn bộ các cặp thuốc."
        )

    evidence_labels: list[str] = []
    drugbank = metadata.get("drugbank")
    if isinstance(drugbank, dict) and drugbank.get("state") == "ready":
        version = str(drugbank.get("version") or "").strip()
        evidence_labels.append(f"DrugBank{f' ({version})' if version else ''}")
    elif "local_rules" in metadata.get("source_used", []):
        evidence_labels.append(
            "Internal medication-check rules" if english else "Quy tắc kiểm tra thuốc nội bộ"
        )
    elif isinstance(ddi_status, dict) and ddi_status.get("required_source") == "drugbank":
        evidence_labels.append("DrugBank unavailable" if english else "DrugBank chưa sẵn sàng")

    medication_names: set[str] = set()
    # These values are used only by the local fidelity verifier below.  They
    # are never placed in the model prompt, telemetry, or consumer projection.
    alerts = result.get("ddi_alerts")
    for alert in alerts if isinstance(alerts, list) else []:
        if not isinstance(alert, dict):
            continue
        for medication in alert.get("medications", []):
            if isinstance(medication, str) and medication.strip():
                medication_names.add(medication.strip())
    normalized_inputs = metadata.get("normalized_inputs")
    for row in normalized_inputs if isinstance(normalized_inputs, list) else []:
        if not isinstance(row, dict):
            continue
        for key in ("input", "canonical_input", "normalized_name"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                medication_names.add(value.strip())
    # The dictionary aliases are already loaded during deterministic
    # normalization. Including them locally prevents a model draft from
    # inventing a common known medication that was not part of this result.
    medication_names.update(_VN_DICTIONARY_ALIAS_LOOKUP)
    medication_names.update(_VN_DICTIONARY_ACTIVE_INGREDIENTS)

    source = RenderingInput(
        audience=audience,
        severity=severity,
        action_codes=action_by_severity[severity],
        mandatory_warnings=warnings,
        uncertainty_level=(
            "high" if warnings or bool(metadata.get("fallback_used")) else "low"
        ),
        evidence_labels=evidence_labels,
        medication_names=sorted(medication_names)[:500],
    )
    deterministic = render_explanation(source)
    rendered = render_careguard_wording_draft(
        source,
        deterministic=deterministic,
        settings=settings,
    )
    return rendered.model_dump(mode="json")


def _with_consumer_wording(result: dict[str, Any], *, locale: str) -> dict[str, Any]:
    """Keep the legacy result byte-compatible unless the release flag is on."""

    if not settings.careguard_wording_renderer_enabled:
        return result
    result["consumer_explanation"] = _consumer_wording_from_final_result(
        result,
        locale=locale,
    )
    return result


def _drugbank_required_unavailable_result(
    *,
    raw_medications: list[str],
    medications: list[str],
    allergies: list[str],
    symptoms: list[str],
    labs: object,
    vn_dictionary_metadata: dict[str, Any],
    external_ddi_enabled: bool,
    external_ddi_flag_source: str,
    local_ddi_rules_version: str,
    readiness: dict[str, object],
) -> dict:
    """Fail closed when a required DrugBank index is not operational.

    Drug-drug conclusions are deliberately empty and neither curated rules nor
    external providers are consulted. Independent, deterministic safety checks
    remain active so a DrugBank outage cannot hide a declared allergy,
    recognized emergency symptom, or supported lab-risk flag.
    """

    allergy_alerts = _detect_allergy_conflicts(medications, allergies)
    critical_symptoms = _critical_symptom_hits(symptoms)
    lab_flags = _lab_risk_flags(labs)
    score, independent_level = _risk_from_signals(
        allergy_alerts,
        critical_symptoms,
        lab_flags,
    )
    has_independent_signal = bool(allergy_alerts or critical_symptoms or lab_flags)
    if has_independent_signal:
        level = (
            independent_level
            if _SEVERITY_RANK[independent_level] >= _SEVERITY_RANK["medium"]
            else "medium"
        )
    else:
        level = "unknown"

    factors = [f"critical_symptom:{item}" for item in critical_symptoms]
    factors.extend(f"lab_flag:{item}" for item in lab_flags)
    factors.extend(
        f"alert:{alert['type']}:{_normalize_severity(alert.get('severity'))}"
        for alert in allergy_alerts
    )
    factors.append("ddi_check:drugbank_unavailable")

    if critical_symptoms:
        independent_recommendation = _recommendation_for(
            level,
            allergy_alerts,
            critical_symptoms,
        )
        recommendation = (
            f"{independent_recommendation} {_DRUGBANK_REQUIRED_UNAVAILABLE_RECOMMENDATION}"
        )
    elif allergy_alerts:
        recommendation = (
            "Phát hiện thuốc trùng với dị ứng đã khai báo; không dùng thuốc đó và "
            "hãy liên hệ bác sĩ hoặc dược sĩ. "
            f"{_DRUGBANK_REQUIRED_UNAVAILABLE_RECOMMENDATION}"
        )
    else:
        recommendation = _DRUGBANK_REQUIRED_UNAVAILABLE_RECOMMENDATION

    readiness_state = str(readiness.get("state") or "unavailable")
    ddi_status = {
        "state": "unavailable",
        "conclusion_available": False,
        "required_source": "drugbank",
        "reason": f"drugbank_{readiness_state}",
    }
    return {
        "risk": {
            "level": level,
            "score": score,
            "factors": factors,
        },
        # This legacy field also carries non-DDI allergy alerts. It never
        # contains a ``drug_drug`` item on the strict unavailable path.
        "ddi_alerts": allergy_alerts,
        "ddi_status": ddi_status,
        "recommendation": recommendation,
        "metadata": {
            "pipeline": "p2-careguard-ddi-standard-v2",
            "fallback_used": True,
            "degraded": True,
            "ddi_status": ddi_status,
            "drugbank_required": True,
            "external_ddi_enabled": external_ddi_enabled,
            "external_ddi_flag_source": external_ddi_flag_source,
            "local_ddi_rules_version": local_ddi_rules_version,
            "vn_dictionary_version": vn_dictionary_metadata.get("version", "unknown"),
            "vn_dictionary_record_count": vn_dictionary_metadata.get("record_count", 0),
            "vn_dictionary_mapped_count": vn_dictionary_metadata.get("mapped_count", 0),
            "vn_dictionary_mapped_items": vn_dictionary_metadata.get("mapped_items", []),
            "vn_dictionary_input_count": vn_dictionary_metadata.get("input_count", 0),
            "drugbank_dictionary_version": vn_dictionary_metadata.get(
                "drugbank_dictionary_version", ""
            ),
            "normalization_confidence": vn_dictionary_metadata.get("normalization_confidence", 0.0),
            "normalization_pair_coverage_low": False,
            "normalized_medication_count": len(medications),
            "raw_medication_count": len(raw_medications),
            "normalized_inputs": vn_dictionary_metadata.get("normalized_inputs", []),
            "clinical_span_augmentation": vn_dictionary_metadata.get(
                "clinical_span_augmentation", {"state": "disabled", "added_candidate_count": 0}
            ),
            "source_used": [],
            "source_errors": {
                "drugbank": [f"required_source_{readiness_state}"],
            },
            "drugbank": {
                "state": readiness_state,
                "version": str(readiness.get("version") or ""),
                "pair_count": int(readiness.get("pair_count") or 0),
                "manifest_matches_index": bool(readiness.get("manifest_matches_index")),
                "matched_alert_count": 0,
            },
            "openfda_pairs_checked": 0,
            "openfda_alert_count": 0,
            "rxnav_status": "",
        },
    }


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
            "drugbank_dictionary_version": vn_dictionary_metadata.get(
                "drugbank_dictionary_version", ""
            ),
            "normalization_confidence": vn_dictionary_metadata.get("normalization_confidence", 0.0),
            "normalization_pair_coverage_low": False,
            "normalized_medication_count": len(medications),
            "raw_medication_count": len(raw_medications),
            "normalized_inputs": vn_dictionary_metadata.get("normalized_inputs", []),
            "clinical_span_augmentation": vn_dictionary_metadata.get(
                "clinical_span_augmentation", {"state": "disabled", "added_candidate_count": 0}
            ),
            "source_used": [],
            "source_errors": {"local_rules": ["rules_unavailable"]},
            "openfda_pairs_checked": 0,
            "openfda_alert_count": 0,
            "rxnav_status": "",
        },
    }


def _medication_clarification_required_result(
    *,
    raw_medications: list[str],
    vn_dictionary_metadata: dict[str, Any],
    readiness: dict[str, object],
    symptoms: list[str],
) -> dict[str, Any]:
    """Terminal no-DDI state while a DrugBank medication identity is unresolved.

    Deliberately omit ``risk``, ``ddi_alerts`` and ``recommendation``: a partial
    comparison must never look like an all-clear or a complete interaction
    assessment.  Urgent symptom state stays explicit so a clarification prompt
    cannot obscure the emergency fast-path in a consuming surface.
    """

    critical_symptoms = _critical_symptom_hits(symptoms)
    return {
        "status": "requires_medication_clarification",
        "clarifications": vn_dictionary_metadata.get("clarifications", []),
        "urgent_support_required": bool(critical_symptoms),
        "metadata": {
            "pipeline": "p2-careguard-ddi-standard-v2",
            "clarification_required": True,
            "clarification_source": "drugbank_exact_dictionary",
            "raw_medication_count": len(raw_medications),
            "normalized_medication_count": 0,
            "vn_dictionary_version": vn_dictionary_metadata.get("version", "unknown"),
            "vn_dictionary_record_count": vn_dictionary_metadata.get("record_count", 0),
            "drugbank_dictionary_version": vn_dictionary_metadata.get(
                "drugbank_dictionary_version", ""
            ),
            "drugbank": {
                "state": str(readiness.get("state") or "unavailable"),
                "version": str(readiness.get("version") or ""),
                "manifest_matches_index": bool(readiness.get("manifest_matches_index")),
                "integrity_verified": bool(readiness.get("integrity_verified")),
            },
        },
    }


def run_careguard_analyze(payload: dict) -> dict:
    locale = str(payload.get("locale") or "vi").strip() or "vi"
    symptoms = _normalize_text_list(payload.get("symptoms"))
    raw_medications = _normalize_text_list(payload.get("medications"))
    medication_text, medication_text_state = _bounded_medication_text(
        payload.get("medication_text")
    )
    free_text_medications, free_text_extraction = _free_text_medication_candidates(
        medication_text,
        field_state=medication_text_state,
    )
    for candidate in free_text_medications:
        if candidate not in raw_medications:
            raw_medications.append(candidate)
    allergies = _normalize_text_list(payload.get("allergies"))
    labs = payload.get("labs")

    external_ddi_flag_source = "runtime" if "external_ddi_enabled" in payload else "env"
    external_ddi_enabled = _as_bool(
        payload.get("external_ddi_enabled"),
        default=settings.external_ddi_enabled,
    )
    # A caller may tighten this guarantee (the medication-course route does),
    # but an untrusted request can never relax a deployment-level requirement.
    # This keeps the strict DrugBank path fail-closed even when the ML service is
    # shared with the backward-compatible CareGuard endpoint.
    drugbank_required = settings.careguard_drugbank_required or _as_bool(
        payload.get("drugbank_required"),
        default=False,
    )

    clarification_enabled = settings.careguard_medication_clarification_enabled
    if free_text_extraction.get("state") == "requires_clarification":
        return _with_consumer_wording(
            _free_text_medication_clarification_result(
                raw_medications=raw_medications,
                symptoms=symptoms,
                extraction=free_text_extraction,
            ),
            locale=locale,
        )
    if clarification_enabled:
        # The optional clinical-language span augmenter may nominate only exact
        # source spans, but this strict identity path intentionally does not let
        # it change which medication aliases require a licensed DrugBank choice.
        # No model, Vietnamese alias map, or local rule can select a candidate.
        medications, vn_dictionary_metadata = _normalize_medications_with_strict_drugbank_choices(
            raw_medications,
            requested_resolutions=payload.get("medication_resolutions"),
            medications_with_meta=payload.get("medications_with_meta"),
        )
        vn_dictionary_metadata["clinical_span_augmentation"] = {
            "state": "bypassed_for_drugbank_clarification",
            "added_candidate_count": 0,
        }
        vn_dictionary_metadata["free_text_medication_extraction"] = free_text_extraction
        clarification_readiness = get_drugbank_readiness()
        if drugbank_required and clarification_readiness.get("state") != "ready":
            clarification_readiness["required"] = True
            return _with_consumer_wording(
                _drugbank_required_unavailable_result(
                    raw_medications=raw_medications,
                    medications=medications,
                    allergies=allergies,
                    symptoms=symptoms,
                    labs=labs,
                    vn_dictionary_metadata=vn_dictionary_metadata,
                    external_ddi_enabled=external_ddi_enabled,
                    external_ddi_flag_source=external_ddi_flag_source,
                    local_ddi_rules_version=_load_local_ddi_rules()[1],
                    readiness=clarification_readiness,
                ),
                locale=locale,
            )
        # A clarification response without a current exact licensed dictionary
        # would invite a local/LLM fallback.  Block instead; no partial DDI or
        # all-clear conclusion may be produced on this rollout path.
        if clarification_readiness.get("state") != "ready":
            return _medication_clarification_required_result(
                raw_medications=raw_medications,
                vn_dictionary_metadata=vn_dictionary_metadata,
                readiness=clarification_readiness,
                symptoms=symptoms,
            )
        if vn_dictionary_metadata.get("clarifications"):
            return _medication_clarification_required_result(
                raw_medications=raw_medications,
                vn_dictionary_metadata=vn_dictionary_metadata,
                readiness=clarification_readiness,
                symptoms=symptoms,
            )
    else:
        normalizer_inputs, clinical_span_augmentation = _augment_raw_medications_with_validated_spans(
            raw_medications
        )
        medications, vn_dictionary_metadata = _normalize_medications_with_vn_dictionary(
            normalizer_inputs
        )
        vn_dictionary_metadata["clinical_span_augmentation"] = clinical_span_augmentation
        vn_dictionary_metadata["free_text_medication_extraction"] = free_text_extraction

    local_rules, local_ddi_rules_version = _resolve_ddi_rules()

    # Keep track of the fallback store separately. A healthy full DrugBank index
    # is sufficient to run DDI even if this small curated fallback is absent.
    # We fail closed below only when neither source can be used.
    curated_rules, _ = _load_local_ddi_rules()

    if curated_rules and settings.careguard_ddi_index_enabled:
        pair_index, other_rules = _resolve_ddi_pair_index(local_rules, local_ddi_rules_version)
        local_ddi_alerts = _detect_ddi_alerts_indexed(medications, pair_index, other_rules)
    elif curated_rules:
        local_ddi_alerts = _detect_ddi_alerts(medications, local_rules)
    else:
        local_ddi_alerts = []

    # Memory-safe DrugBank layer: the full DrugBank set is ~1.4M pairs and cannot
    # be held in RAM on a small host, so it lives in an on-disk SQLite index and
    # is queried per medication pair. When that licensed index is ready it is the
    # authoritative DDI source. Curated local rules are retained only as a
    # fail-safe for deployments where DrugBank is disabled or unavailable; they
    # must never mask DrugBank provenance for a pair present in the full index.
    drugbank_layer_version = ""
    drugbank_alerts: list[dict[str, Any]] = []
    if settings.careguard_drugbank_sqlite_enabled:
        drugbank_alerts, drugbank_layer_version = _drugbank_sqlite_alerts(
            medications, existing_alerts=[]
        )
        if drugbank_layer_version:
            local_ddi_rules_version = f"{local_ddi_rules_version}+{drugbank_layer_version}"
            # A ready DrugBank index was queried for every medication pair. Its
            # hits (including an empty set) are authoritative; do not manufacture
            # or override licensed results with local rules.
            local_ddi_alerts = drugbank_alerts
    if drugbank_required and not drugbank_layer_version:
        readiness = get_drugbank_readiness()
        readiness["required"] = True
        return _with_consumer_wording(
            _drugbank_required_unavailable_result(
                raw_medications=raw_medications,
                medications=medications,
                allergies=allergies,
                symptoms=symptoms,
                labs=labs,
                vn_dictionary_metadata=vn_dictionary_metadata,
                external_ddi_enabled=external_ddi_enabled,
                external_ddi_flag_source=external_ddi_flag_source,
                local_ddi_rules_version=local_ddi_rules_version,
                readiness=readiness,
            ),
            locale=locale,
        )
    if not drugbank_layer_version and not curated_rules:
        return _with_consumer_wording(
            _rules_unavailable_result(
                raw_medications=raw_medications,
                medications=medications,
                vn_dictionary_metadata=vn_dictionary_metadata,
                external_ddi_enabled=external_ddi_enabled,
                external_ddi_flag_source=external_ddi_flag_source,
                local_ddi_rules_version=local_ddi_rules_version,
            ),
            locale=locale,
        )
    source_used = ["drugbank"] if drugbank_layer_version else ["local_rules"]
    source_errors: dict[str, list[str]] = {}
    external_ddi_alerts: list[dict[str, Any]] = []
    openfda_alerts: list[dict[str, Any]] = []
    openfda_evidence: dict[tuple[str, str], dict[str, int]] = {}
    openfda_pairs_checked = 0
    rxnav_status = ""
    needs_external_lookup = len(set(medications)) >= 2

    # The licensed full DrugBank index is authoritative. RxNav/openFDA are only
    # fallback enrichments when that index is unavailable; allowing a same-pair
    # external alert to raise severity or replace the message would make the
    # displayed claim inconsistent with its DrugBank reference.
    if needs_external_lookup and external_ddi_enabled and not drugbank_layer_version:
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
    elif needs_external_lookup and not drugbank_layer_version:
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
    non_optional_source_errors = dict(source_errors)
    if drugbank_layer_version:
        # External enrichment is optional once the full DrugBank index has been
        # checked. An intentionally disabled/unavailable enrichment source does
        # not mean the authoritative DDI lookup fell back.
        non_optional_source_errors.pop("external", None)
    fallback_used = needs_external_lookup and (
        (not drugbank_layer_version and not external_source_used)
        or bool(non_optional_source_errors)
        or normalization_pair_coverage_low
    )

    return _with_consumer_wording(
        {
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
                "drugbank_required": drugbank_required,
                "external_ddi_enabled": external_ddi_enabled,
                "external_ddi_flag_source": external_ddi_flag_source,
                "local_ddi_rules_version": local_ddi_rules_version,
                "vn_dictionary_version": vn_dictionary_metadata["version"],
                "vn_dictionary_record_count": vn_dictionary_metadata["record_count"],
                "vn_dictionary_mapped_count": vn_dictionary_metadata["mapped_count"],
                "vn_dictionary_mapped_items": vn_dictionary_metadata["mapped_items"],
                "vn_dictionary_input_count": vn_dictionary_metadata["input_count"],
                "drugbank_dictionary_version": vn_dictionary_metadata.get(
                    "drugbank_dictionary_version", ""
                ),
                "normalization_confidence": vn_dictionary_metadata["normalization_confidence"],
                "normalization_pair_coverage_low": normalization_pair_coverage_low,
                "normalized_medication_count": len(medications),
                "raw_medication_count": len(raw_medications),
                "normalized_inputs": vn_dictionary_metadata["normalized_inputs"],
                "clinical_span_augmentation": vn_dictionary_metadata.get(
                    "clinical_span_augmentation", {"state": "disabled", "added_candidate_count": 0}
                ),
                "free_text_medication_extraction": vn_dictionary_metadata.get(
                    "free_text_medication_extraction",
                    {"state": "not_used", "extractor": "deterministic_vietnamese_clinical_v1"},
                ),
                "source_used": source_used,
                "source_errors": source_errors,
                "drugbank": {
                    "state": "ready"
                    if drugbank_layer_version
                    else (
                        "disabled"
                        if not settings.careguard_drugbank_sqlite_enabled
                        else "unavailable"
                    ),
                    "version": drugbank_layer_version,
                    "matched_alert_count": len(drugbank_alerts),
                },
                "openfda_pairs_checked": openfda_pairs_checked,
                "openfda_alert_count": len(openfda_alerts),
                "rxnav_status": rxnav_status,
            },
        },
        locale=locale,
    )
