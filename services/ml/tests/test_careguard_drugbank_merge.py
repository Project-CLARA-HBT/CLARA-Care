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
