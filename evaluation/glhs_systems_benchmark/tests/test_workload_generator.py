"""Unit tests for standardized clinical workload generator."""

from __future__ import annotations

import pytest

from evaluation.glhs_systems_benchmark.workload_generator import (
    SEVERE_DDI_PAIRS,
    ClinicalWorkloadItem,
    PartitionCoord,
    ScenarioFamily,
    generate_clean_update,
    generate_cross_domain,
    generate_disjoint_partition,
    generate_severe_ddi,
    generate_toctou_revocation,
    generate_workload,
    validate_workload_distribution,
)


def test_partition_coord_formatting_and_parsing() -> None:
    coord = PartitionCoord(profile_id="profile_001", domain="medication", slot="metformin")
    key = coord.to_key()
    assert key == "profile_001:medication:metformin"

    parsed = PartitionCoord.from_key(key)
    assert parsed == coord

    with pytest.raises(ValueError, match="Invalid partition key format"):
        PartitionCoord.from_key("invalid_key")


def test_generate_clean_update() -> None:
    item = generate_clean_update("tx_001", patient_idx=1, seed=42)
    assert item.workload_id == "tx_001"
    assert item.scenario_family == ScenarioFamily.CLEAN_UPDATE
    assert item.has_governance_drift is False
    assert item.has_severe_ddi is False
    assert len(item.target_partitions) == 1
    assert item.target_partitions[0].startswith("profile_001:medication:")


def test_generate_cross_domain() -> None:
    item = generate_cross_domain("tx_002", patient_idx=2, seed=42)
    assert item.workload_id == "tx_002"
    assert item.scenario_family == ScenarioFamily.CROSS_DOMAIN
    assert len(item.target_partitions) == 3
    domains = [p.split(":")[1] for p in item.target_partitions]
    assert set(domains) == {"medication", "condition", "observation"}


def test_generate_toctou_revocation() -> None:
    item = generate_toctou_revocation("tx_003", patient_idx=3, seed=42)
    assert item.workload_id == "tx_003"
    assert item.scenario_family == ScenarioFamily.TOCTOU_REVOCATION
    assert item.has_governance_drift is True
    assert item.expected_consent_epoch == 1


def test_generate_severe_ddi() -> None:
    item = generate_severe_ddi("tx_004", patient_idx=4, seed=42)
    assert item.workload_id == "tx_004"
    assert item.scenario_family == ScenarioFamily.SEVERE_DDI
    assert item.has_severe_ddi is True
    assert len(item.proposed_medications) == 2
    med_pair = tuple(item.proposed_medications)
    assert (med_pair in SEVERE_DDI_PAIRS) or ((med_pair[1], med_pair[0]) in SEVERE_DDI_PAIRS)


def test_generate_disjoint_partition() -> None:
    item = generate_disjoint_partition("tx_005", partition_idx=7, total_partitions=64, seed=42)
    assert item.workload_id == "tx_005"
    assert item.scenario_family == ScenarioFamily.DISJOINT_PARTITIONS
    assert item.is_disjoint is True
    assert item.target_partitions[0] == "profile_disjoint_007:partition:slot_007"


def test_generate_workload_balanced_distribution() -> None:
    count = 100
    workload = generate_workload(count=count, seed=42)
    assert len(workload) == count

    dist = validate_workload_distribution(workload)
    # Balanced should have all 5 families represented
    for fam in ScenarioFamily:
        assert dist[fam.value] > 0
        assert abs(dist[fam.value] - (count / 5)) <= 10


def test_workload_serialization_roundtrip() -> None:
    item = generate_clean_update("tx_ser_01", patient_idx=5, seed=99)
    d = item.to_dict()
    restored = ClinicalWorkloadItem.from_dict(d)
    assert restored.workload_id == item.workload_id
    assert restored.scenario_family == item.scenario_family
    assert restored.target_partitions == item.target_partitions
