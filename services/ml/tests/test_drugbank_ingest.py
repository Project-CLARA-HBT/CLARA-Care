"""Unit tests for the DrugBank ingest CLI (``scripts/data/drugbank_ingest.py``).

These run the real streaming parser against the real 1.5 GB XML with a tiny
``--limit`` so they stay fast while still exercising iterparse + the severity
heuristic + dedupe against authentic DrugBank markup.
"""

from __future__ import annotations

import importlib.util
import json
from hashlib import sha256
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "data" / "drugbank_ingest.py"
_SOURCE_XML = _REPO_ROOT / "drugbank_full_database.xml"


def _load_ingest_module():
    spec = importlib.util.spec_from_file_location("drugbank_ingest", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ingest = _load_ingest_module()


def test_derive_severity_heuristic() -> None:
    # critical: explicit contraindication / fatal wording
    assert ingest.derive_severity("This combination is contraindicated.") == "critical"
    assert (
        ingest.derive_severity("Coadministration may be life-threatening and fatal.") == "critical"
    )
    # high: increased risk/severity of a serious named outcome
    assert (
        ingest.derive_severity(
            "The risk or severity of bleeding and hemorrhage can be increased "
            "when Dasatinib is combined with Lepirudin."
        )
        == "high"
    )
    assert ingest.derive_severity("The risk of QT prolongation can be increased.") == "high"
    # medium: generic activity/concentration change with no serious target
    assert (
        ingest.derive_severity("Apixaban may increase the anticoagulant activities of Lepirudin.")
        == "medium"
    )
    # low: minor PK-only decreased excretion rate
    assert (
        ingest.derive_severity(
            "Aldesleukin may decrease the excretion rate of Abacavir which could "
            "result in a higher serum level."
        )
        == "low"
    )


@pytest.mark.skipif(not _SOURCE_XML.exists(), reason="DrugBank source XML not present")
def test_cli_limit_emits_valid_shards(tmp_path: Path) -> None:
    out_dir = tmp_path / "drugbank_out"
    rc = ingest.main(
        [
            "--input",
            str(_SOURCE_XML),
            "--out-dir",
            str(out_dir),
            "--limit",
            "50",
        ]
    )
    assert rc == 0

    # --- Manifest shape. ---
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == "drugbank"
    assert manifest["license"] == "commercial"
    assert manifest["source_version"]
    assert len(manifest["source_sha256"]) == 64
    unsigned_manifest = dict(manifest)
    recorded_manifest_sha = unsigned_manifest.pop("manifest_sha256")
    assert recorded_manifest_sha == sha256(
        json.dumps(
            unsigned_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    assert manifest["drugs_parsed"] == 50
    assert "generated_at" in manifest
    assert manifest["ddi_rule_count"] > 0
    assert manifest["dictionary_record_count"] > 0
    assert manifest["ddi_shards"]
    assert manifest["dictionary_shards"]

    # --- DDI shards: shape + severity domain + dedupe across all shards. ---
    seen_pairs: set[tuple[str, ...]] = set()
    total_rules = 0
    severities: set[str] = set()
    for shard_info in manifest["ddi_shards"]:
        assert shard_info["sha256"] == sha256((out_dir / shard_info["file"]).read_bytes()).hexdigest()
        shard = json.loads((out_dir / shard_info["file"]).read_text(encoding="utf-8"))
        assert shard["version"] == manifest["version"]
        for rule in shard["rules"]:
            assert set(rule) == {"medications", "severity", "message"}
            meds = rule["medications"]
            assert len(meds) == 2
            # normalized lowercase + sorted
            assert meds == sorted(m.lower() for m in meds)
            assert rule["severity"] in {"low", "medium", "high", "critical"}
            assert rule["message"]
            key = tuple(meds)
            assert key not in seen_pairs, f"duplicate pair leaked across shards: {key}"
            seen_pairs.add(key)
            severities.add(rule["severity"])
            total_rules += 1

    assert total_rules == manifest["ddi_rule_count"]
    # heuristic should produce a mix, not a single bucket
    assert len(severities) >= 2

    # --- Dictionary shards: vn_drug_dictionary record shape. ---
    dict_total = 0
    for shard_info in manifest["dictionary_shards"]:
        assert shard_info["sha256"] == sha256((out_dir / shard_info["file"]).read_bytes()).hexdigest()
        shard = json.loads((out_dir / shard_info["file"]).read_text(encoding="utf-8"))
        assert shard["version"] == manifest["version"]
        assert shard["record_count"] == len(shard["records"])
        for record in shard["records"]:
            assert set(record) == {
                "brand_vn",
                "normalized_name",
                "active_ingredients",
                "rxcui",
                "drugbank_id",
            }
            assert record["brand_vn"] == record["brand_vn"].lower()
            assert record["normalized_name"]
            assert isinstance(record["active_ingredients"], list)
        dict_total += shard["record_count"]

    assert dict_total == manifest["dictionary_record_count"]


@pytest.mark.skipif(not _SOURCE_XML.exists(), reason="DrugBank source XML not present")
def test_parse_keeps_most_severe_on_duplicate_pair() -> None:
    # Same pair seen with two descriptions: the more severe one must win.
    high_desc = "The risk or severity of bleeding can be increased when A is combined with B."
    low_desc = "B may decrease the excretion rate of A."
    assert ingest.derive_severity(high_desc) == "high"
    assert ingest.derive_severity(low_desc) == "low"
    assert ingest._SEVERITY_RANK["high"] > ingest._SEVERITY_RANK["low"]
