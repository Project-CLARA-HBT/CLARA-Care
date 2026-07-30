# ruff: noqa: E501
"""Tests for the memory-safe on-disk DrugBank SQLite DDI store.

These cover the store in isolation (build + lookup + degrade) and its
integration into ``run_careguard_analyze`` via the
``careguard_drugbank_sqlite_enabled`` flag. Invariants asserted:

* The store builds a SQLite index from shard files and looks up pairs
  order-independently.
* A ready DrugBank index is authoritative for conflicting pairs and its
  provenance is preserved in the public result.
* A missing/malformed manifest or shard degrades to no contribution (never
  raises, never fabricates an all-clear), so CareGuard falls back to curated-only.
* The build is idempotent: a matching-version DB is reused without a rebuild.
"""

from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path

import pytest

from clara_ml.agents import careguard
from clara_ml.agents.careguard_ddi_store import DrugBankDdiStore
from clara_ml.config import Settings


def _write_shards(root: Path, *, version: str = "drugbank-test-1") -> Path:
    drugbank_dir = root / "drugbank"
    drugbank_dir.mkdir(parents=True, exist_ok=True)
    shard = {
        "rules": [
            {
                "medications": ["DrugbankOnly_A", "DrugbankOnly_B"],
                "severity": "high",
                "message": "DrugBank-only pair interaction.",
            },
            {
                # Reversed order on disk to prove order-independent lookup.
                "medications": ["ibuprofen", "warfarin"],
                "severity": "low",
                "message": "This should NOT override the curated Vietnamese rule.",
            },
            {
                # Defensive: a single-med row must be dropped.
                "medications": ["solo_drug"],
                "severity": "critical",
                "message": "dropped",
            },
        ]
    }
    shard_path = drugbank_dir / "ddi_0.json"
    shard_path.write_text(json.dumps(shard), encoding="utf-8")
    dictionary = {
        "records": [
            {
                "brand_vn": "drugbankonly_a",
                "normalized_name": "drugbankonly_a",
                "active_ingredients": ["drugbankonly_a"],
                "rxcui": "",
                "drugbank_id": "DBTESTA",
            }
        ]
    }
    dictionary_path = drugbank_dir / "dictionary_0.json"
    dictionary_path.write_text(json.dumps(dictionary), encoding="utf-8")
    manifest = {
        "version": version,
        "source": "drugbank",
        "source_version": "test-source-1",
        "source_sha256": "a" * 64,
        "ddi_shards": [
            {"file": "ddi_0.json", "sha256": sha256(shard_path.read_bytes()).hexdigest()}
        ],
        "ddi_rule_count": 2,
        "dictionary_record_count": 1,
        "dictionary_shards": [
            {
                "file": "dictionary_0.json",
                "sha256": sha256(dictionary_path.read_bytes()).hexdigest(),
            }
        ],
    }
    unsigned = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    manifest["manifest_sha256"] = sha256(unsigned).hexdigest()
    (drugbank_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return drugbank_dir


def _store_for(drugbank_dir: Path) -> DrugBankDdiStore:
    return DrugBankDdiStore(
        drugbank_dir=drugbank_dir,
        manifest_path=drugbank_dir / "manifest.json",
    )


def test_drugbank_required_config_defaults_off_and_accepts_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CAREGUARD_DRUGBANK_REQUIRED", raising=False)
    assert Settings(_env_file=None).careguard_drugbank_required is False

    monkeypatch.setenv("CAREGUARD_DRUGBANK_REQUIRED", "true")
    assert Settings(_env_file=None).careguard_drugbank_required is True


def test_store_builds_and_looks_up_pairs(tmp_path: Path) -> None:
    drugbank_dir = _write_shards(tmp_path)
    store = _store_for(drugbank_dir)

    version = store.ensure_built()
    assert version == "drugbank-test-1"
    assert (drugbank_dir / "ddi_index.sqlite").exists()

    # Order-independent lookup.
    hits = store.lookup_pairs(["drugbankonly_b", "drugbankonly_a"])
    assert len(hits) == 1
    meds, severity, message = hits[0]
    assert meds == frozenset({"drugbankonly_a", "drugbankonly_b"})
    assert severity == "high"
    assert "DrugBank-only" in message
    assert store.readiness() == {
        "state": "ready",
        "version": "drugbank-test-1",
        "pair_count": 2,
        "dictionary_record_count": 1,
        "manifest_matches_index": True,
        "integrity_verified": True,
        "source_version": "test-source-1",
    }


def test_store_build_is_idempotent(tmp_path: Path) -> None:
    drugbank_dir = _write_shards(tmp_path)
    store = _store_for(drugbank_dir)
    assert store.ensure_built() == "drugbank-test-1"
    db_mtime = (drugbank_dir / "ddi_index.sqlite").stat().st_mtime_ns

    # Second call with a matching version must reuse the DB (no rebuild).
    store2 = _store_for(drugbank_dir)
    assert store2.ensure_built() == "drugbank-test-1"
    assert (drugbank_dir / "ddi_index.sqlite").stat().st_mtime_ns == db_mtime


def test_store_degrades_on_missing_manifest(tmp_path: Path) -> None:
    drugbank_dir = tmp_path / "drugbank"
    drugbank_dir.mkdir(parents=True)
    store = _store_for(drugbank_dir)
    assert store.ensure_built() is None
    assert store.lookup_pairs(["a", "b"]) == []


def test_store_degrades_on_malformed_shard(tmp_path: Path) -> None:
    drugbank_dir = _write_shards(tmp_path)
    (drugbank_dir / "ddi_0.json").write_text("{ not json", encoding="utf-8")
    # Bump the manifest version so ensure_built does not reuse a prior good DB.
    manifest = json.loads((drugbank_dir / "manifest.json").read_text())
    manifest["version"] = "drugbank-test-2"
    (drugbank_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    store = _store_for(drugbank_dir)
    assert store.ensure_built() is None


def test_store_fails_closed_when_a_verified_shard_changes(tmp_path: Path) -> None:
    drugbank_dir = _write_shards(tmp_path)
    shard_path = drugbank_dir / "ddi_0.json"
    shard_path.write_text('{"rules": []}', encoding="utf-8")

    # The manifest is still syntactically valid but its recorded artifact digest
    # no longer matches. Strict integrity must reject it before SQLite build.
    assert _store_for(drugbank_dir).ensure_built() is None


def test_store_resolves_dictionary_alias_with_traceable_identifiers(tmp_path: Path) -> None:
    drugbank_dir = _write_shards(tmp_path)
    dictionary = {
        "records": [
            {
                "brand_vn": "panadol extra",
                "normalized_name": "paracetamol",
                "active_ingredients": ["paracetamol", "caffeine"],
                "rxcui": "161",
                "drugbank_id": "DB00316",
            }
        ]
    }
    dictionary_path = drugbank_dir / "dictionary_0.json"
    dictionary_path.write_text(json.dumps(dictionary), encoding="utf-8")
    manifest_path = drugbank_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dictionary_shards"] = [
        {
            "file": "dictionary_0.json",
            "sha256": sha256(dictionary_path.read_bytes()).hexdigest(),
        }
    ]
    manifest["dictionary_record_count"] = 1
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    store = _store_for(drugbank_dir)
    assert store.ensure_built() == "drugbank-test-1"
    assert store.resolve_medication("Panadol Extra") == {
        "alias": "panadol extra",
        "normalized_name": "paracetamol",
        "active_ingredients": ["paracetamol", "caffeine"],
        "rxcui": "161",
        "drugbank_id": "DB00316",
        "source_version": "drugbank-test-1",
    }


def test_readiness_rejects_missing_pair_table_even_when_meta_looks_ready(
    tmp_path: Path,
) -> None:
    drugbank_dir = _write_shards(tmp_path)
    store = _store_for(drugbank_dir)
    assert store.ensure_built() == "drugbank-test-1"

    with sqlite3.connect(drugbank_dir / "ddi_index.sqlite") as conn:
        conn.execute("DROP TABLE ddi_pairs")
        conn.commit()

    assert store.readiness() == {
        "state": "degraded",
        "version": "drugbank-test-1",
        "pair_count": 0,
        "dictionary_record_count": 0,
        "manifest_matches_index": True,
        "integrity_verified": True,
        "source_version": "test-source-1",
    }


def test_analyze_uses_authoritative_sqlite_layer(tmp_path: Path, monkeypatch) -> None:
    drugbank_dir = _write_shards(tmp_path)
    # Point the module-level store at the temp shards and reset the cached store.
    monkeypatch.setattr(careguard, "_DRUGBANK_DIR", drugbank_dir)
    monkeypatch.setattr(careguard, "_DRUGBANK_MANIFEST_PATH", drugbank_dir / "manifest.json")
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE", None)
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE_READY", False)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", True)

    # A DrugBank-only pair surfaces from the SQLite layer.
    result = careguard.run_careguard_analyze(
        {
            "medications": ["drugbankonly_a", "drugbankonly_b"],
            "external_ddi_enabled": False,
        }
    )
    drug_pairs = [
        sorted(a["medications"]) for a in result["ddi_alerts"] if a.get("type") == "drug_drug"
    ]
    assert ["drugbankonly_a", "drugbankonly_b"] in drug_pairs
    assert "+drugbank-test-1" in result["metadata"]["local_ddi_rules_version"]
    drugbank_alert = next(
        alert
        for alert in result["ddi_alerts"]
        if sorted(alert.get("medications", []))
        == ["drugbankonly_a", "drugbankonly_b"]
    )
    assert drugbank_alert["source"] == "drugbank"
    assert "drugbank" in result["metadata"]["source_used"]
    assert result["metadata"]["drugbank"] == {
        "state": "ready",
        "version": "drugbank-test-1",
        "matched_alert_count": 1,
    }

    # DrugBank wins on an overlapping pair: only one licensed alert is emitted,
    # and neither its source nor severity is replaced by the curated fallback.
    class _UnexpectedExternalClient:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("external DDI must not run when DrugBank is ready")

    monkeypatch.setattr(careguard, "DrugSourceClient", _UnexpectedExternalClient)
    result2 = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": True}
    )
    wi_alerts = [
        a
        for a in result2["ddi_alerts"]
        if a.get("type") == "drug_drug" and sorted(a["medications"]) == ["ibuprofen", "warfarin"]
    ]
    assert len(wi_alerts) == 1
    assert wi_alerts[0]["severity"] == "low"
    assert wi_alerts[0]["source"] == "drugbank"
    assert wi_alerts[0]["source_version"] == "drugbank-test-1"
    assert wi_alerts[0]["source_statement"] == "This should NOT override the curated Vietnamese rule."
    assert wi_alerts[0]["reference"] == {
        "source": "DrugBank",
        "version": "drugbank-test-1",
        "medication_pair": ["ibuprofen", "warfarin"],
    }
    assert result2["metadata"]["source_used"] == ["drugbank"]
    assert result2["metadata"]["fallback_used"] is False
    assert result2["metadata"]["drugbank"]["matched_alert_count"] == 1


def test_ready_drugbank_skips_external_enrichment_without_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    drugbank_dir = _write_shards(tmp_path)
    monkeypatch.setattr(careguard, "_DRUGBANK_DIR", drugbank_dir)
    monkeypatch.setattr(careguard, "_DRUGBANK_MANIFEST_PATH", drugbank_dir / "manifest.json")
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE", None)
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE_READY", False)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", True)

    class _UnexpectedExternalClient:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("external DDI must not run when DrugBank is ready")

    monkeypatch.setattr(careguard, "DrugSourceClient", _UnexpectedExternalClient)

    result = careguard.run_careguard_analyze(
        {
            "medications": ["drugbankonly_a", "drugbankonly_b"],
            "external_ddi_enabled": True,
        }
    )

    assert result["metadata"]["source_used"] == ["drugbank"]
    assert result["metadata"]["source_errors"] == {}
    assert result["metadata"]["fallback_used"] is False
    assert result["metadata"]["drugbank"] == {
        "state": "ready",
        "version": "drugbank-test-1",
        "matched_alert_count": 1,
    }


def test_required_drugbank_unavailable_fails_closed_without_ddi_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_required", True)
    monkeypatch.setattr(careguard, "_drugbank_sqlite_alerts", lambda *_args, **_kwargs: ([], ""))
    monkeypatch.setattr(
        careguard,
        "get_drugbank_readiness",
        lambda: {
            "state": "unavailable",
            "version": "",
            "pair_count": 0,
            "manifest_matches_index": False,
            "required": True,
        },
    )

    class _UnexpectedExternalClient:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("strict DrugBank mode must not call external DDI")

    monkeypatch.setattr(careguard, "DrugSourceClient", _UnexpectedExternalClient)

    result = careguard.run_careguard_analyze(
        {
            "medications": ["warfarin", "ibuprofen"],
            "allergies": ["warfarin"],
            "symptoms": ["chest pain"],
            "labs": {"egfr": 20},
            "external_ddi_enabled": True,
        }
    )

    assert result["ddi_status"] == {
        "state": "unavailable",
        "conclusion_available": False,
        "required_source": "drugbank",
        "reason": "drugbank_unavailable",
    }
    assert not any(alert.get("type") == "drug_drug" for alert in result["ddi_alerts"])
    assert any(alert.get("type") == "drug_allergy" for alert in result["ddi_alerts"])
    assert result["risk"]["level"] == "high"
    assert "critical_symptom:chest pain" in result["risk"]["factors"]
    assert "lab_flag:severe_renal_impairment" in result["risk"]["factors"]
    assert "không có tương tác" in result["recommendation"]
    assert result["metadata"]["source_used"] == []
    assert result["metadata"]["source_errors"] == {
        "drugbank": ["required_source_unavailable"]
    }
    assert result["metadata"]["fallback_used"] is True
    assert result["metadata"]["degraded"] is True


def test_required_drugbank_manifest_mismatch_reports_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_required", True)
    monkeypatch.setattr(careguard, "_drugbank_sqlite_alerts", lambda *_args, **_kwargs: ([], ""))
    monkeypatch.setattr(
        careguard,
        "get_drugbank_readiness",
        lambda: {
            "state": "degraded",
            "version": "drugbank-stale",
            "pair_count": 2,
            "manifest_matches_index": False,
            "required": True,
        },
    )

    result = careguard.run_careguard_analyze(
        {
            "medications": ["warfarin", "ibuprofen"],
            "external_ddi_enabled": False,
        }
    )

    assert result["risk"]["level"] == "unknown"
    assert result["ddi_alerts"] == []
    assert result["ddi_status"]["reason"] == "drugbank_degraded"
    assert result["metadata"]["drugbank"]["manifest_matches_index"] is False
    assert result["metadata"]["source_errors"] == {
        "drugbank": ["required_source_degraded"]
    }


def test_required_ready_empty_result_remains_authoritative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drugbank_dir = _write_shards(tmp_path)
    monkeypatch.setattr(careguard, "_DRUGBANK_DIR", drugbank_dir)
    monkeypatch.setattr(careguard, "_DRUGBANK_MANIFEST_PATH", drugbank_dir / "manifest.json")
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE", None)
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE_READY", False)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", True)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_required", True)

    class _UnexpectedExternalClient:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("ready empty DrugBank result must remain authoritative")

    monkeypatch.setattr(careguard, "DrugSourceClient", _UnexpectedExternalClient)
    result = careguard.run_careguard_analyze(
        {
            "medications": ["paracetamol", "loratadine"],
            "external_ddi_enabled": True,
        }
    )

    assert result["metadata"]["source_used"] == ["drugbank"]
    assert result["metadata"]["fallback_used"] is False
    assert result["metadata"]["drugbank"]["state"] == "ready"
    assert not any(alert.get("type") == "drug_drug" for alert in result["ddi_alerts"])
    assert "ddi_status" not in result


def test_analyze_flag_off_is_curated_only(tmp_path: Path, monkeypatch) -> None:
    drugbank_dir = _write_shards(tmp_path)
    monkeypatch.setattr(careguard, "_DRUGBANK_DIR", drugbank_dir)
    monkeypatch.setattr(careguard, "_DRUGBANK_MANIFEST_PATH", drugbank_dir / "manifest.json")
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE", None)
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE_READY", False)
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", False)

    result = careguard.run_careguard_analyze(
        {
            "medications": ["drugbankonly_a", "drugbankonly_b"],
            "external_ddi_enabled": False,
        }
    )
    # No DrugBank contribution and no version suffix when the flag is off.
    assert "+drugbank" not in result["metadata"]["local_ddi_rules_version"]
    drug_pairs = [
        sorted(a["medications"]) for a in result["ddi_alerts"] if a.get("type") == "drug_drug"
    ]
    assert ["drugbankonly_a", "drugbankonly_b"] not in drug_pairs
