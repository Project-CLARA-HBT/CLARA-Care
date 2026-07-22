# ruff: noqa: E501
"""Tests for the memory-safe on-disk DrugBank SQLite DDI store.

These cover the store in isolation (build + lookup + degrade) and its
integration into ``run_careguard_analyze`` via the
``careguard_drugbank_sqlite_enabled`` flag. Invariants asserted:

* The store builds a SQLite index from shard files and looks up pairs
  order-independently.
* Curated Vietnamese rules always win on a conflicting pair (the SQLite layer is
  skipped for pairs the curated matcher already covers).
* A missing/malformed manifest or shard degrades to no contribution (never
  raises, never fabricates an all-clear), so CareGuard falls back to curated-only.
* The build is idempotent: a matching-version DB is reused without a rebuild.
"""

from __future__ import annotations

import json
from pathlib import Path

from clara_ml.agents import careguard
from clara_ml.agents.careguard_ddi_store import DrugBankDdiStore


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
    (drugbank_dir / "ddi_0.json").write_text(json.dumps(shard), encoding="utf-8")
    manifest = {
        "version": version,
        "source": "drugbank",
        "ddi_shards": [{"file": "ddi_0.json"}],
    }
    (drugbank_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return drugbank_dir


def _store_for(drugbank_dir: Path) -> DrugBankDdiStore:
    return DrugBankDdiStore(
        drugbank_dir=drugbank_dir,
        manifest_path=drugbank_dir / "manifest.json",
    )


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
        "manifest_matches_index": True,
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


def test_analyze_uses_sqlite_layer_and_curated_wins(tmp_path: Path, monkeypatch) -> None:
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

    # Curated wins: warfarin+ibuprofen stays high (curated), never the low
    # DrugBank override, and only ONE alert is emitted for the pair.
    result2 = careguard.run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )
    wi_alerts = [
        a
        for a in result2["ddi_alerts"]
        if a.get("type") == "drug_drug" and sorted(a["medications"]) == ["ibuprofen", "warfarin"]
    ]
    assert len(wi_alerts) == 1
    assert wi_alerts[0]["severity"] in {"high", "critical"}


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
