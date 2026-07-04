"""Regression tests for the flag-gated DrugBank DDI merge in CareGuard.

Invariants asserted here:

* ``CAREGUARD_DRUGBANK_ENABLED`` defaults off, and with it off the resolved rule
  set + analyze output are byte-identical to the curated-only behavior.
* With the flag on, DrugBank shards merge as a *lower-precedence* layer: a curated
  Vietnamese rule wins on a conflicting pair (severity + message preserved), and
  DrugBank only contributes pairs the curated set does not already cover.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import clara_ml.agents.careguard as careguard
from clara_ml.agents.careguard import (
    _load_local_ddi_rules,
    _resolve_ddi_rules,
    run_careguard_analyze,
)


@pytest.fixture(autouse=True)
def _isolate_legacy_in_memory_merge(monkeypatch):
    """Isolate the legacy in-memory DrugBank merge path for this whole module.

    These tests validate the original ``careguard_drugbank_enabled`` in-memory
    merge. The newer memory-safe ``careguard_drugbank_sqlite_enabled`` layer
    defaults ON and would otherwise find the real local shards and append a
    ``+drugbank-*`` version suffix / extra alerts, breaking the byte-identical
    curated-only assertions here. Pin the SQLite layer OFF and reset its cached
    store so this module exercises only the legacy path it was written for.
    """
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_sqlite_enabled", False)
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE", None)
    monkeypatch.setattr(careguard, "_DRUGBANK_STORE_READY", False)


@pytest.fixture
def reset_drugbank_cache():
    careguard._DRUGBANK_DDI_CACHE_MTIME_NS = None
    careguard._DRUGBANK_DDI_CACHE_VERSION = "unknown"
    careguard._DRUGBANK_DDI_CACHE_RULES = []
    yield
    careguard._DRUGBANK_DDI_CACHE_MTIME_NS = None
    careguard._DRUGBANK_DDI_CACHE_VERSION = "unknown"
    careguard._DRUGBANK_DDI_CACHE_RULES = []


def _write_drugbank_shards(root: Path) -> Path:
    """Write a minimal DrugBank shard set: one curated-conflicting pair + one new pair."""
    drugbank_dir = root / "drugbank"
    ddi_dir = drugbank_dir / "ddi"
    ddi_dir.mkdir(parents=True, exist_ok=True)

    shard = {
        "version": "drugbank-test",
        "rules": [
            # Conflicts with curated warfarin+ibuprofen (curated = high, VN message).
            # DrugBank claims a *higher* severity + English message; curated must win.
            {
                "medications": ["ibuprofen", "warfarin"],
                "severity": "critical",
                "message": "DRUGBANK ENGLISH: bleeding risk is increased.",
            },
            # A pair the curated set does not cover -> should be added by the merge.
            {
                "medications": ["drugbankonly_a", "drugbankonly_b"],
                "severity": "high",
                "message": "The risk or severity of bleeding can be increased.",
            },
        ],
    }
    (ddi_dir / "ddi_i_000.json").write_text(json.dumps(shard, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "version": "drugbank-test",
        "source": "drugbank",
        "license": "commercial",
        "ddi_shards": [{"file": "ddi/ddi_i_000.json", "rule_count": 2}],
        "dictionary_shards": [],
    }
    (drugbank_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return drugbank_dir


def test_flag_off_resolves_to_curated_only(monkeypatch) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_enabled", False)

    curated_rules, curated_version = _load_local_ddi_rules()
    resolved_rules, resolved_version = _resolve_ddi_rules()

    assert resolved_rules == curated_rules
    assert resolved_version == curated_version


def test_flag_off_analyze_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_enabled", False)
    result = run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )
    assert result["risk"]["level"] in {"high", "critical"}
    # No DrugBank suffix on the version when the flag is off.
    assert "+" not in result["metadata"]["local_ddi_rules_version"]


def test_flag_on_merges_without_overriding_curated(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    drugbank_dir = _write_drugbank_shards(tmp_path)
    monkeypatch.setattr(careguard, "_DRUGBANK_DIR", drugbank_dir)
    monkeypatch.setattr(careguard, "_DRUGBANK_MANIFEST_PATH", drugbank_dir / "manifest.json")
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_enabled", True)

    curated_rules, _ = _load_local_ddi_rules()
    curated_by_pair = {rule.meds: rule for rule in curated_rules}
    conflicting_pair = frozenset({"warfarin", "ibuprofen"})
    new_pair = frozenset({"drugbankonly_a", "drugbankonly_b"})
    assert conflicting_pair in curated_by_pair  # precondition

    resolved_rules, resolved_version = _resolve_ddi_rules()
    resolved_by_pair = {rule.meds: rule for rule in resolved_rules}

    # Curated rule wins on the conflicting pair: severity + message preserved.
    curated_conflict = curated_by_pair[conflicting_pair]
    merged_conflict = resolved_by_pair[conflicting_pair]
    assert merged_conflict.severity == curated_conflict.severity
    assert merged_conflict.message == curated_conflict.message
    assert "DRUGBANK ENGLISH" not in merged_conflict.message

    # DrugBank-only pair is additively merged in.
    assert new_pair in resolved_by_pair
    assert resolved_by_pair[new_pair].severity == "high"

    # Version label reflects both layers.
    assert "+drugbank-test" in resolved_version


def test_flag_on_does_not_change_curated_pair_alert(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    drugbank_dir = _write_drugbank_shards(tmp_path)
    monkeypatch.setattr(careguard, "_DRUGBANK_DIR", drugbank_dir)
    monkeypatch.setattr(careguard, "_DRUGBANK_MANIFEST_PATH", drugbank_dir / "manifest.json")
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_enabled", True)

    result = run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )
    warfarin_alerts = [
        alert
        for alert in result["ddi_alerts"]
        if set(alert.get("medications", [])) == {"warfarin", "ibuprofen"}
    ]
    assert warfarin_alerts
    # Curated severity (high) preserved; DrugBank's "critical" did not override.
    assert warfarin_alerts[0]["severity"] == "high"
    assert "DRUGBANK ENGLISH" not in warfarin_alerts[0]["message"]


# ---------------------------------------------------------------------------
# Task 7.1: manifest verification + cache-by-mtime + degrade-to-curated.
# Req 5.3 (degrade to curated-only on missing/unparseable/malformed manifest or
# any missing/unparseable shard; never raise into analysis; never fabricate an
# all-clear) and Req 5.5 (surface the active rule-set version label).
# ---------------------------------------------------------------------------


def _point_loader_at(monkeypatch, drugbank_dir: Path) -> None:
    monkeypatch.setattr(careguard, "_DRUGBANK_DIR", drugbank_dir)
    monkeypatch.setattr(careguard, "_DRUGBANK_MANIFEST_PATH", drugbank_dir / "manifest.json")
    monkeypatch.setattr(careguard.settings, "careguard_drugbank_enabled", True)


def test_missing_manifest_degrades_to_curated(monkeypatch, tmp_path, reset_drugbank_cache) -> None:
    # Flag on but no DrugBank directory/manifest at all -> curated-only.
    _point_loader_at(monkeypatch, tmp_path / "drugbank")

    curated_rules, curated_version = _load_local_ddi_rules()
    resolved_rules, resolved_version = _resolve_ddi_rules()

    assert resolved_rules == curated_rules
    assert resolved_version == curated_version
    assert "+" not in resolved_version


def test_unparseable_manifest_degrades_to_curated(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    drugbank_dir = tmp_path / "drugbank"
    drugbank_dir.mkdir(parents=True, exist_ok=True)
    (drugbank_dir / "manifest.json").write_text("{ this is not valid json", encoding="utf-8")
    _point_loader_at(monkeypatch, drugbank_dir)

    curated_rules, curated_version = _load_local_ddi_rules()
    resolved_rules, resolved_version = _resolve_ddi_rules()

    assert resolved_rules == curated_rules
    assert resolved_version == curated_version


def test_manifest_missing_version_degrades_to_curated(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    drugbank_dir = tmp_path / "drugbank"
    ddi_dir = drugbank_dir / "ddi"
    ddi_dir.mkdir(parents=True, exist_ok=True)
    (ddi_dir / "ddi_i_000.json").write_text(
        json.dumps({"rules": [{"medications": ["a", "b"], "severity": "high", "message": "x"}]}),
        encoding="utf-8",
    )
    # Malformed manifest shape: no version present.
    (drugbank_dir / "manifest.json").write_text(
        json.dumps({"ddi_shards": [{"file": "ddi/ddi_i_000.json"}]}), encoding="utf-8"
    )
    _point_loader_at(monkeypatch, drugbank_dir)

    curated_rules, curated_version = _load_local_ddi_rules()
    resolved_rules, resolved_version = _resolve_ddi_rules()

    assert resolved_rules == curated_rules
    assert resolved_version == curated_version


def test_ddi_shards_not_a_list_degrades_to_curated(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    drugbank_dir = tmp_path / "drugbank"
    drugbank_dir.mkdir(parents=True, exist_ok=True)
    (drugbank_dir / "manifest.json").write_text(
        json.dumps({"version": "drugbank-test", "ddi_shards": "not-a-list"}), encoding="utf-8"
    )
    _point_loader_at(monkeypatch, drugbank_dir)

    curated_rules, _ = _load_local_ddi_rules()
    resolved_rules, resolved_version = _resolve_ddi_rules()

    assert resolved_rules == curated_rules
    assert "+" not in resolved_version


def test_missing_shard_degrades_to_curated_no_partial(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    # One valid shard + one referenced-but-missing shard. A missing shard must
    # degrade the WHOLE layer to curated-only (no partial DrugBank rule set).
    drugbank_dir = tmp_path / "drugbank"
    ddi_dir = drugbank_dir / "ddi"
    ddi_dir.mkdir(parents=True, exist_ok=True)
    good_shard = {
        "rules": [
            {"medications": ["drugbankonly_a", "drugbankonly_b"], "severity": "high", "message": "x"}
        ]
    }
    (ddi_dir / "ddi_i_000.json").write_text(json.dumps(good_shard), encoding="utf-8")
    manifest = {
        "version": "drugbank-test",
        "ddi_shards": [
            {"file": "ddi/ddi_i_000.json", "rule_count": 1},
            {"file": "ddi/ddi_i_001.json", "rule_count": 1},  # missing on disk
        ],
    }
    (drugbank_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _point_loader_at(monkeypatch, drugbank_dir)

    curated_rules, curated_version = _load_local_ddi_rules()
    resolved_rules, resolved_version = _resolve_ddi_rules()

    # Curated-only: the valid shard's pair is NOT partially merged in.
    assert resolved_rules == curated_rules
    assert resolved_version == curated_version
    assert frozenset({"drugbankonly_a", "drugbankonly_b"}) not in {r.meds for r in resolved_rules}


def test_unparseable_shard_degrades_to_curated(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    drugbank_dir = tmp_path / "drugbank"
    ddi_dir = drugbank_dir / "ddi"
    ddi_dir.mkdir(parents=True, exist_ok=True)
    (ddi_dir / "ddi_i_000.json").write_text("{ broken json", encoding="utf-8")
    manifest = {
        "version": "drugbank-test",
        "ddi_shards": [{"file": "ddi/ddi_i_000.json", "rule_count": 1}],
    }
    (drugbank_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _point_loader_at(monkeypatch, drugbank_dir)

    curated_rules, curated_version = _load_local_ddi_rules()
    resolved_rules, resolved_version = _resolve_ddi_rules()

    assert resolved_rules == curated_rules
    assert resolved_version == curated_version


def test_degrade_does_not_raise_into_analysis(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    # A broken DrugBank layer must never propagate into run_careguard_analyze and
    # must never fabricate an all-clear: a known curated high-risk pair still fires.
    drugbank_dir = tmp_path / "drugbank"
    drugbank_dir.mkdir(parents=True, exist_ok=True)
    (drugbank_dir / "manifest.json").write_text("not json at all", encoding="utf-8")
    _point_loader_at(monkeypatch, drugbank_dir)

    result = run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )
    assert result["risk"]["level"] in {"high", "critical"}
    # Degraded to curated-only -> version carries no DrugBank suffix.
    assert "+" not in result["metadata"]["local_ddi_rules_version"]


def test_cache_by_mtime_reparses_on_change_and_caches_on_same_mtime(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    import os

    drugbank_dir = tmp_path / "drugbank"
    ddi_dir = drugbank_dir / "ddi"
    ddi_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = drugbank_dir / "manifest.json"
    shard_path = ddi_dir / "ddi_i_000.json"

    def write_valid(version: str) -> None:
        shard = {
            "rules": [
                {
                    "medications": ["drugbankonly_a", "drugbankonly_b"],
                    "severity": "high",
                    "message": "x",
                }
            ]
        }
        shard_path.write_text(json.dumps(shard), encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {"version": version, "ddi_shards": [{"file": "ddi/ddi_i_000.json"}]}
            ),
            encoding="utf-8",
        )

    _point_loader_at(monkeypatch, drugbank_dir)

    # t1: valid manifest version v-one.
    write_valid("drugbank-v-one")
    os.utime(manifest_path, ns=(1_000_000_000, 1_000_000_000))
    rules1, version1 = careguard._load_drugbank_ddi_rules()
    assert version1 == "drugbank-v-one"
    assert rules1

    # t2 (different mtime): new version -> cache invalidated, re-parsed.
    write_valid("drugbank-v-two")
    os.utime(manifest_path, ns=(2_000_000_000, 2_000_000_000))
    _rules2, version2 = careguard._load_drugbank_ddi_rules()
    assert version2 == "drugbank-v-two"

    # Corrupt the manifest content but RESTORE the previous mtime (t2). Because
    # the loader caches by mtime, it must return the cached good result and must
    # NOT re-read the now-broken file.
    manifest_path.write_text("broken json", encoding="utf-8")
    os.utime(manifest_path, ns=(2_000_000_000, 2_000_000_000))
    _rules3, version3 = careguard._load_drugbank_ddi_rules()
    assert version3 == "drugbank-v-two"


def test_active_rule_set_version_surfaced_in_metadata(
    monkeypatch, tmp_path, reset_drugbank_cache
) -> None:
    # Req 5.5: merged layer surfaces curated+drugbank-<ver> in analysis metadata.
    drugbank_dir = _write_drugbank_shards(tmp_path)
    _point_loader_at(monkeypatch, drugbank_dir)

    result = run_careguard_analyze(
        {"medications": ["warfarin", "ibuprofen"], "external_ddi_enabled": False}
    )
    version_label = result["metadata"]["local_ddi_rules_version"]
    assert "+drugbank-test" in version_label
    assert version_label.startswith(_load_local_ddi_rules()[1])
