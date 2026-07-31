#!/usr/bin/env python3
"""Stream-parse the DrugBank full-database XML into CLARA seed shards.

CLARA holds a commercial DrugBank license, so emitting derived data files into
the repository is permitted. This tool is *additive*: it only writes new shard
files plus a manifest. It never mutates CLARA's curated Vietnamese seed files
(``careguard_ddi_rules.v1.json`` / ``vn_drug_dictionary.json``).

The source file is ~1.5 GB, so the parser uses ``xml.etree.ElementTree.iterparse``
and clears each top-level ``<drug>`` element (and the accumulating root) as soon
as it is processed. The XML is never loaded fully into memory.

Outputs (under ``--out-dir``, default ``services/ml/.../seed_data/drugbank/``):

* ``ddi/ddi_<letter>_<index>.json`` — DDI rule shards in CLARA's DDI rule shape
  ``{"version", "rules": [{"medications", "severity", "message"}]}``.
* ``dictionary/dict_<letter>_<index>.json`` — brand/synonym dictionary shards in
  the ``vn_drug_dictionary`` record shape
  ``{"version", "record_count", "records": [{"brand_vn", "normalized_name",
  "active_ingredients", "rxcui"}]}``.
* ``manifest.json`` — lists all shards + counts + source/license + timestamp.

Severity heuristic (documented; see ``derive_severity``):

The DrugBank ``<description>`` free-text is mapped to CLARA's
``low|medium|high|critical`` scale by ordered keyword matching (first match wins):

1. ``critical`` — explicit contraindication or fatal / life-threatening wording
   ("contraindicated", "should not be combined", "is not recommended", "fatal",
   "life-threatening").
2. ``high`` — an *increase* in the risk or severity of a serious adverse event
   ("risk or severity ... can be increased" / "increased risk of ...") whose
   target is a serious outcome (bleeding, hemorrhage, QT prolongation, serotonin
   syndrome, rhabdomyolysis/myopathy, hyperkalemia, CNS/respiratory depression,
   hypotension, seizure, torsade, hepatotoxicity, nephrotoxicity, bone-marrow
   suppression, cardiotoxicity).
3. ``low`` — minor pharmacokinetic-only changes, specifically a decreased
   *excretion rate* ("may decrease the excretion" / "excretion rate ... can be
   decreased").
4. ``medium`` — the catch-all for changes in drug "activities"/"activity",
   serum concentration, metabolism, absorption, or a generic risk/severity bump
   with no serious named target. This is also the default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

NS = "http://www.drugbank.ca"

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# Serious adverse outcomes that escalate an "increased risk/severity" phrase to high.
_HIGH_RISK_TARGETS = (
    "bleeding",
    "hemorrhage",
    "haemorrhage",
    "qt prolongation",
    "qtc prolongation",
    "torsade",
    "serotonin syndrome",
    "rhabdomyolysis",
    "myopathy",
    "myotoxicity",
    "hyperkalemia",
    "hyperkalaemia",
    "cns depression",
    "respiratory depression",
    "central nervous system depression",
    "hypotension",
    "hypertensive crisis",
    "seizure",
    "hepatotoxicity",
    "nephrotoxicity",
    "neurotoxicity",
    "cardiotoxicity",
    "bone marrow",
    "neutropenia",
    "agranulocytosis",
    "methemoglobinemia",
)

_CRITICAL_MARKERS = (
    "contraindicated",
    "is contraindicated",
    "should not be combined",
    "should not be co-administered",
    "should not be coadministered",
    "must not be combined",
    "is not recommended",
    "life-threatening",
    "life threatening",
    "fatal",
)

# Default shard size cap. With ~57k deduped pairs this keeps each JSON file well
# under the ~5 MB ceiling regardless of single-letter skew.
_MAX_RECORDS_PER_SHARD = 5000


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def derive_severity(description: str) -> str:
    """Map a DrugBank interaction description to CLARA severity (see module docstring)."""
    text = description.lower()

    for marker in _CRITICAL_MARKERS:
        if marker in text:
            return "critical"

    risk_phrase = (
        "risk or severity" in text
        or "increased risk" in text
        or "increase the risk" in text
        or "risk of" in text
    )
    if risk_phrase and any(target in text for target in _HIGH_RISK_TARGETS):
        return "high"

    if "excretion rate" in text or "decrease the excretion" in text:
        return "low"

    return "medium"


def _shard_letter(name: str) -> str:
    first = name[:1].lower()
    return first if first.isalpha() else "_"


def _iter_drugs(input_path: Path, limit: int | None) -> Iterator[ET.Element]:
    """Yield top-level ``<drug>`` elements, clearing them to bound memory."""
    context = ET.iterparse(str(input_path), events=("start", "end"))
    root: ET.Element | None = None
    depth = 0
    yielded = 0

    for event, elem in context:
        if event == "start":
            if root is None:
                root = elem
            depth += 1
            continue

        # event == "end"
        if _local_tag(elem.tag) == "drug" and depth == 2:
            yield elem
            yielded += 1
            elem.clear()
            if root is not None:
                root.clear()
            if limit is not None and yielded >= limit:
                break
        depth -= 1


def _collect_aliases(drug: ET.Element) -> list[str]:
    aliases: list[str] = []

    synonyms = drug.find(_q("synonyms"))
    if synonyms is not None:
        for synonym in synonyms.findall(_q("synonym")):
            value = _text(synonym)
            if value:
                aliases.append(value)

    international = drug.find(_q("international-brands"))
    if international is not None:
        for brand in international.findall(_q("international-brand")):
            value = _text(brand.find(_q("name")))
            if value:
                aliases.append(value)

    return aliases


def _primary_drugbank_id(drug: ET.Element) -> str:
    for identifier in drug.findall(_q("drugbank-id")):
        value = _text(identifier)
        if value and identifier.get("primary", "false").lower() == "true":
            return value
    return ""


def parse_drugbank(
    input_path: Path,
    limit: int | None,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]], int]:
    """Stream the XML and return (ddi_by_pair, dictionary_by_brand, drugs_seen).

    ``ddi_by_pair`` is keyed by the sorted lowercase drug pair; the most severe
    interaction wins on conflict and carries its own description as the message.
    ``dictionary_by_brand`` is keyed by lowercase brand alias.
    """
    ddi_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    dictionary_by_brand: dict[str, dict[str, Any]] = {}
    drugs_seen = 0

    for drug in _iter_drugs(input_path, limit):
        drugs_seen += 1
        name = _text(drug.find(_q("name")))
        if not name:
            continue
        canonical = name.lower()
        drugbank_id = _primary_drugbank_id(drug)

        # --- Dictionary: canonical self-record + alias records. ---
        def _add_dictionary_record(brand_value: str) -> None:
            brand = brand_value.strip().lower()
            if not brand or brand in dictionary_by_brand:
                return
            dictionary_by_brand[brand] = {
                "brand_vn": brand,
                "normalized_name": canonical,
                "active_ingredients": [canonical],
                "rxcui": "",
                "drugbank_id": drugbank_id,
            }

        _add_dictionary_record(canonical)
        for alias in _collect_aliases(drug):
            _add_dictionary_record(alias)

        # --- DDI rules. ---
        interactions = drug.find(_q("drug-interactions"))
        if interactions is None:
            continue
        for interaction in interactions.findall(_q("drug-interaction")):
            other_name = _text(interaction.find(_q("name")))
            description = _text(interaction.find(_q("description")))
            if not other_name:
                continue
            other = other_name.lower()
            if other == canonical:
                continue

            pair = tuple(sorted((canonical, other)))
            severity = derive_severity(description)
            message = description or "Potential drug-drug interaction detected."

            existing = ddi_by_pair.get(pair)
            if (
                existing is None
                or _SEVERITY_RANK[severity] > _SEVERITY_RANK[existing["severity"]]
            ):
                ddi_by_pair[pair] = {
                    "medications": [pair[0], pair[1]],
                    "severity": severity,
                    "message": message,
                }

    return ddi_by_pair, dictionary_by_brand, drugs_seen


def _chunk(records: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(records), size):
        yield records[start : start + size]


def _bucket_by_letter(
    records: list[dict[str, Any]],
    key: str,
) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        letter = _shard_letter(str(record[key]))
        buckets.setdefault(letter, []).append(record)
    return buckets


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("manifest_sha256", None)
    return hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def write_shards(
    out_dir: Path,
    ddi_by_pair: dict[tuple[str, str], dict[str, Any]],
    dictionary_by_brand: dict[str, dict[str, Any]],
    drugs_seen: int,
    version: str,
    source_version: str,
    source_sha256: str,
    max_records_per_shard: int = _MAX_RECORDS_PER_SHARD,
) -> dict[str, Any]:
    ddi_dir = out_dir / "ddi"
    dict_dir = out_dir / "dictionary"
    ddi_dir.mkdir(parents=True, exist_ok=True)
    dict_dir.mkdir(parents=True, exist_ok=True)

    # --- DDI shards (key on alphabetically-first medication). ---
    ddi_rules = sorted(
        ddi_by_pair.values(),
        key=lambda rule: (rule["medications"][0], rule["medications"][1]),
    )
    # ``_bucket_by_letter`` keys on a string field; ``medications`` is a list, so
    # bucket DDI rules on the alphabetically-first medication explicitly.
    ddi_buckets: dict[str, list[dict[str, Any]]] = {}
    for rule in ddi_rules:
        letter = _shard_letter(rule["medications"][0])
        ddi_buckets.setdefault(letter, []).append(rule)

    ddi_shards: list[dict[str, Any]] = []
    for letter in sorted(ddi_buckets):
        for index, chunk in enumerate(
            _chunk(ddi_buckets[letter], max_records_per_shard)
        ):
            filename = f"ddi_{letter}_{index:03d}.json"
            payload = {"version": version, "rules": chunk}
            (ddi_dir / filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            ddi_shards.append(
                {
                    "file": f"ddi/{filename}",
                    "rule_count": len(chunk),
                    "sha256": _sha256_path(ddi_dir / filename),
                }
            )

    # --- Dictionary shards (key on brand_vn). ---
    dict_records = sorted(dictionary_by_brand.values(), key=lambda rec: rec["brand_vn"])
    dict_buckets = _bucket_by_letter(dict_records, key="brand_vn")

    dict_shards: list[dict[str, Any]] = []
    for letter in sorted(dict_buckets):
        for index, chunk in enumerate(
            _chunk(dict_buckets[letter], max_records_per_shard)
        ):
            filename = f"dict_{letter}_{index:03d}.json"
            payload = {"version": version, "record_count": len(chunk), "records": chunk}
            (dict_dir / filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            dict_shards.append(
                {
                    "file": f"dictionary/{filename}",
                    "record_count": len(chunk),
                    "sha256": _sha256_path(dict_dir / filename),
                }
            )

    manifest = {
        "version": version,
        "source": "drugbank",
        "source_version": source_version,
        "source_sha256": source_sha256,
        "license": "commercial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "drugs_parsed": drugs_seen,
        "ddi_rule_count": len(ddi_rules),
        "dictionary_record_count": len(dict_records),
        "ddi_shards": ddi_shards,
        "dictionary_shards": dict_shards,
    }
    manifest["manifest_sha256"] = _manifest_digest(manifest)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _default_input() -> Path:
    return Path(__file__).resolve().parents[2] / "drugbank_full_database.xml"


def _default_out_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "services"
        / "ml"
        / "src"
        / "clara_ml"
        / "nlp"
        / "seed_data"
        / "drugbank"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest DrugBank XML into CLARA seed shards."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=_default_input(),
        help="Path to the DrugBank full-database XML (default: repo-root file).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_default_out_dir(),
        help="Directory to write shards + manifest into.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Parse only the first N <drug> entries (for smoke tests).",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Override the shard version label (default: drugbank-<UTC-date>).",
    )
    parser.add_argument(
        "--source-version",
        default=None,
        help="DrugBank database release identifier; defaults to the generated artifact version.",
    )
    args = parser.parse_args(argv)

    input_path: Path = args.input
    if not input_path.exists():
        parser.error(f"input not found: {input_path}")

    version = (
        args.version or f"drugbank-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    )

    ddi_by_pair, dictionary_by_brand, drugs_seen = parse_drugbank(
        input_path, args.limit
    )
    manifest = write_shards(
        out_dir=args.out_dir,
        ddi_by_pair=ddi_by_pair,
        dictionary_by_brand=dictionary_by_brand,
        drugs_seen=drugs_seen,
        version=version,
        source_version=str(args.source_version or version).strip(),
        source_sha256=_sha256_path(input_path),
    )

    print(f"DrugBank ingest complete -> {args.out_dir}")
    print(f"  drugs parsed:        {manifest['drugs_parsed']}")
    print(
        f"  DDI rules:           {manifest['ddi_rule_count']} "
        f"({len(manifest['ddi_shards'])} shard(s))"
    )
    print(
        f"  dictionary records:  {manifest['dictionary_record_count']} "
        f"({len(manifest['dictionary_shards'])} shard(s))"
    )
    print(f"  version:             {manifest['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
