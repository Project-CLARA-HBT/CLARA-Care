"""Tests for the frozen GLHS repeat/jitter manifest.

No database is connected; these tests prove the manifest is loadable,
byte-stable (deterministic seed list), and fail-closed against tampering.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.glhs_postgres_toctou.repeat_manifest import (
    FREEZE_ID,
    INTERLEAVING_MODES,
    JITTER_RANGE_MS,
    REPETITIONS_PER_LOGICAL_SCHEDULE,
    build_repeat_manifest,
    derive_seed_list,
    validate_repeat_manifest,
)

MANIFEST_PATH = Path("research/glhs_journal/concurrency_repetition_v1/repeat_manifest.json")


def test_frozen_manifest_on_disk_is_valid() -> None:
    import json

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    result = validate_repeat_manifest(manifest)
    assert result["status"] == "VALIDATED_REPEAT_MANIFEST_NOT_EXECUTED"
    assert result["freeze_id"] == FREEZE_ID
    assert result["repetitions_per_logical_schedule"] == REPETITIONS_PER_LOGICAL_SCHEDULE


def test_build_and_validate_frozen_manifest() -> None:
    manifest = build_repeat_manifest()
    result = validate_repeat_manifest(manifest)
    assert result["jitter_range_ms"] == JITTER_RANGE_MS
    assert set(manifest["interleaving_modes"]) == set(INTERLEAVING_MODES)
    assert manifest["repetition_role"] == "robustness_execution_not_scientific_n"
    assert manifest["scientific_n"] == 12


def test_seed_list_is_deterministic_and_unique() -> None:
    seeds_a = derive_seed_list()
    seeds_b = derive_seed_list()
    assert seeds_a == seeds_b
    assert len(seeds_a) == REPETITIONS_PER_LOGICAL_SCHEDULE
    assert len(set(seeds_a)) == REPETITIONS_PER_LOGICAL_SCHEDULE


def test_manifest_refuses_tampered_status() -> None:
    manifest = build_repeat_manifest()
    manifest["status"] = "draft_not_run"
    with pytest.raises(ValueError, match="repeat_manifest_not_frozen"):
        validate_repeat_manifest(manifest)


def test_manifest_refuses_tampered_repetition_count() -> None:
    manifest = build_repeat_manifest()
    manifest["repetitions_per_logical_schedule"] = 10
    with pytest.raises(ValueError, match="repeat_manifest_repetition_count_invalid"):
        validate_repeat_manifest(manifest)


def test_manifest_refuses_tampered_jitter_range() -> None:
    manifest = build_repeat_manifest()
    manifest["jitter"]["range_ms"] = 500
    with pytest.raises(ValueError, match="repeat_manifest_jitter_range_invalid"):
        validate_repeat_manifest(manifest)


def test_manifest_refuses_tampered_seed_list() -> None:
    manifest = build_repeat_manifest()
    manifest["jitter"]["seeds"][0] = 1
    with pytest.raises(ValueError, match="repeat_manifest_jitter_seed_list_mismatch"):
        validate_repeat_manifest(manifest)


def test_manifest_refuses_missing_no_majority_vote_rule() -> None:
    manifest = build_repeat_manifest()
    manifest["no_majority_voting_into_safety"] = False
    with pytest.raises(ValueError, match="repeat_manifest_majority_voting_not_forbidden"):
        validate_repeat_manifest(manifest)
