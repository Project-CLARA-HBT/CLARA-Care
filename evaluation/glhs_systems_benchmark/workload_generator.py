"""Standardized Clinical Workload Generator for Systems Concurrency Benchmarks.

Generates standardized, reproducible clinical transaction workloads across 5 scenario families:
1. Clean Updates: Single-entity/clean attribute updates with valid consent and no DDI.
2. Multi-Entity Cross-Domain: Multi-resource transactions spanning medications, conditions, and labs.
3. TOCTOU Governance Revocations: Dynamic consent/policy drift races between snapshot and commit.
4. Severe DDI Contradictions: Contraindicated drug combination challenges exposing clinical safety barriers.
5. Disjoint Parallel Partitions: High-concurrency operations targeting non-overlapping entity partitions.
"""

from __future__ import annotations

import enum
import random
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

# Standard Severe Drug-Drug Interaction pairs for clinical testing
SEVERE_DDI_PAIRS: list[tuple[str, str]] = [
    ("warfarin", "aspirin"),
    ("sildenafil", "nitroglycerin"),
    ("clopidogrel", "omeprazole"),
    ("simvastatin", "clarithromycin"),
    ("methotrexate", "trimethoprim"),
    ("potassium_chloride", "spironolactone"),
]

# Standard Medication Catalog for synthetic workload generation
MEDICATION_CATALOG: list[str] = [
    "metformin",
    "lisinopril",
    "atorvastatin",
    "amlodipine",
    "omeprazole",
    "levothyroxine",
    "albuterol",
    "gabapentin",
    "losartan",
    "hydrochlorothiazide",
    "metoprolol",
    "pantoprazole",
]

# Standard Condition Catalog
CONDITION_CATALOG: list[str] = [
    "hypertension",
    "type_2_diabetes",
    "hyperlipidemia",
    "asthma",
    "gastroesophageal_reflux",
    "hypothyroidism",
    "chronic_kidney_disease",
    "osteoarthritis",
]

# Standard Observation / Lab Catalog
OBSERVATION_CATALOG: list[str] = [
    "systolic_bp",
    "diastolic_bp",
    "hba1c",
    "serum_creatinine",
    "fasting_glucose",
    "ldl_cholesterol",
    "potassium_level",
    "inr",
]


class ScenarioFamily(enum.StrEnum):
    """The 5 canonical scenario families for transactional governance benchmarking."""

    CLEAN_UPDATE = "clean_update"
    CROSS_DOMAIN = "cross_domain"
    TOCTOU_REVOCATION = "toctou_revocation"
    SEVERE_DDI = "severe_ddi"
    DISJOINT_PARTITIONS = "disjoint_partitions"


@dataclass(frozen=True)
class PartitionCoord:
    """Canonical identifier for an entity partition: (profile_id, domain, slot)."""

    profile_id: str
    domain: str
    slot: str

    def to_key(self) -> str:
        """Returns the canonical partition key string."""
        return f"{self.profile_id}:{self.domain}:{self.slot}"

    @classmethod
    def from_key(cls, key: str) -> PartitionCoord:
        """Parses a canonical key string into a PartitionCoord."""
        parts = key.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid partition key format: '{key}', expected 'profile:domain:slot'")
        return cls(profile_id=parts[0], domain=parts[1], slot=parts[2])


@dataclass
class ClinicalWorkloadItem:
    """Standardized transactional clinical workload item."""

    workload_id: str
    scenario_family: ScenarioFamily
    patient_id: str
    profile_id: str
    policy_id: str
    expected_policy_epoch: int
    expected_consent_epoch: int
    target_partitions: list[str]
    proposed_medications: list[str] = field(default_factory=list)
    active_medications: list[str] = field(default_factory=list)
    has_governance_drift: bool = False
    has_severe_ddi: bool = False
    is_disjoint: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert item to dictionary representation."""
        data = asdict(self)
        data["scenario_family"] = self.scenario_family.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClinicalWorkloadItem:
        """Create item from dictionary representation."""
        data_copy = dict(data)
        if isinstance(data_copy.get("scenario_family"), str):
            data_copy["scenario_family"] = ScenarioFamily(data_copy["scenario_family"])
        return cls(**data_copy)


def generate_clean_update(
    workload_id: str,
    patient_idx: int = 1,
    seed: int | None = None,
) -> ClinicalWorkloadItem:
    """Generate a clean single-entity update workload item."""
    rng = random.Random(seed)
    profile_id = f"profile_{patient_idx:03d}"
    med = rng.choice(MEDICATION_CATALOG)
    coord = PartitionCoord(profile_id=profile_id, domain="medication", slot=med)

    return ClinicalWorkloadItem(
        workload_id=workload_id,
        scenario_family=ScenarioFamily.CLEAN_UPDATE,
        patient_id=f"patient_{patient_idx:03d}",
        profile_id=profile_id,
        policy_id="glhs_policy_v1",
        expected_policy_epoch=1,
        expected_consent_epoch=1,
        target_partitions=[coord.to_key()],
        proposed_medications=[med],
        active_medications=[],
        has_governance_drift=False,
        has_severe_ddi=False,
        is_disjoint=False,
        payload={
            "action": "update_medication_dosage",
            "medication": med,
            "dosage": f"{rng.choice([10, 20, 50, 100, 500])}mg",
            "frequency": "daily",
        },
    )


def generate_cross_domain(
    workload_id: str,
    patient_idx: int = 1,
    seed: int | None = None,
) -> ClinicalWorkloadItem:
    """Generate a multi-entity cross-domain update workload item."""
    rng = random.Random(seed)
    profile_id = f"profile_{patient_idx:03d}"
    med = rng.choice(MEDICATION_CATALOG)
    cond = rng.choice(CONDITION_CATALOG)
    obs = rng.choice(OBSERVATION_CATALOG)

    p_med = PartitionCoord(profile_id=profile_id, domain="medication", slot=med)
    p_cond = PartitionCoord(profile_id=profile_id, domain="condition", slot=cond)
    p_obs = PartitionCoord(profile_id=profile_id, domain="observation", slot=obs)

    return ClinicalWorkloadItem(
        workload_id=workload_id,
        scenario_family=ScenarioFamily.CROSS_DOMAIN,
        patient_id=f"patient_{patient_idx:03d}",
        profile_id=profile_id,
        policy_id="glhs_policy_v1",
        expected_policy_epoch=1,
        expected_consent_epoch=1,
        target_partitions=[p_med.to_key(), p_cond.to_key(), p_obs.to_key()],
        proposed_medications=[med],
        active_medications=[],
        has_governance_drift=False,
        has_severe_ddi=False,
        is_disjoint=False,
        payload={
            "action": "cross_domain_care_plan_update",
            "medication": {"code": med, "dose": "500mg"},
            "condition": {"code": cond, "status": "active"},
            "observation": {"code": obs, "value": round(rng.uniform(70.0, 150.0), 1)},
        },
    )


def generate_toctou_revocation(
    workload_id: str,
    patient_idx: int = 1,
    seed: int | None = None,
) -> ClinicalWorkloadItem:
    """Generate a TOCTOU governance drift race workload item."""
    rng = random.Random(seed)
    profile_id = f"profile_{patient_idx:03d}"
    med = rng.choice(MEDICATION_CATALOG)
    coord = PartitionCoord(profile_id=profile_id, domain="medication", slot=med)

    return ClinicalWorkloadItem(
        workload_id=workload_id,
        scenario_family=ScenarioFamily.TOCTOU_REVOCATION,
        patient_id=f"patient_{patient_idx:03d}",
        profile_id=profile_id,
        policy_id="glhs_policy_v1",
        expected_policy_epoch=1,  # Snapshot taken at epoch 1
        expected_consent_epoch=1,  # Snapshot taken at epoch 1 (system drifted to epoch 2)
        target_partitions=[coord.to_key()],
        proposed_medications=[med],
        active_medications=[],
        has_governance_drift=True,
        has_severe_ddi=False,
        is_disjoint=False,
        payload={
            "action": "restricted_treatment_proposal",
            "medication": med,
            "simulated_drift": "consent_revocation_at_t_mid",
        },
    )


def generate_severe_ddi(
    workload_id: str,
    patient_idx: int = 1,
    seed: int | None = None,
) -> ClinicalWorkloadItem:
    """Generate a severe DDI contradiction workload item."""
    rng = random.Random(seed)
    profile_id = f"profile_{patient_idx:03d}"
    med_pair = rng.choice(SEVERE_DDI_PAIRS)
    p_med1 = PartitionCoord(profile_id=profile_id, domain="medication", slot=med_pair[0])
    p_med2 = PartitionCoord(profile_id=profile_id, domain="medication", slot=med_pair[1])

    return ClinicalWorkloadItem(
        workload_id=workload_id,
        scenario_family=ScenarioFamily.SEVERE_DDI,
        patient_id=f"patient_{patient_idx:03d}",
        profile_id=profile_id,
        policy_id="glhs_policy_v1",
        expected_policy_epoch=1,
        expected_consent_epoch=1,
        target_partitions=[p_med1.to_key(), p_med2.to_key()],
        proposed_medications=list(med_pair),
        active_medications=[med_pair[0]],  # Patient already taking med1, proposing med2
        has_governance_drift=False,
        has_severe_ddi=True,
        is_disjoint=False,
        payload={
            "action": "contraindicated_prescription_attempt",
            "existing_medication": med_pair[0],
            "new_medication": med_pair[1],
            "severity": "CRITICAL_FATAL",
        },
    )


def generate_disjoint_partition(
    workload_id: str,
    partition_idx: int,
    total_partitions: int = 64,
    seed: int | None = None,
) -> ClinicalWorkloadItem:
    """Generate an isolated disjoint partition workload item for horizontal scaling test."""
    rng = random.Random(seed)
    profile_id = f"profile_disjoint_{(partition_idx % total_partitions):03d}"
    slot = f"slot_{partition_idx:03d}"
    coord = PartitionCoord(profile_id=profile_id, domain="partition", slot=slot)

    return ClinicalWorkloadItem(
        workload_id=workload_id,
        scenario_family=ScenarioFamily.DISJOINT_PARTITIONS,
        patient_id=f"patient_disjoint_{(partition_idx % total_partitions):03d}",
        profile_id=profile_id,
        policy_id="glhs_policy_v1",
        expected_policy_epoch=1,
        expected_consent_epoch=1,
        target_partitions=[coord.to_key()],
        proposed_medications=[],
        active_medications=[],
        has_governance_drift=False,
        has_severe_ddi=False,
        is_disjoint=True,
        payload={
            "action": "parallel_partition_update",
            "partition_slot": slot,
            "data_value": rng.randint(1000, 9999),
        },
    )


def generate_workload(
    count: int = 500,
    scenario_mix: dict[ScenarioFamily, float] | None = None,
    seed: int = 42,
    num_patients: int = 10,
    num_partitions: int = 64,
) -> list[ClinicalWorkloadItem]:
    """Generate a standardized clinical transaction workload batch.

    Args:
        count: Total number of transactions to generate.
        scenario_mix: Optional mapping of scenario families to proportion (weights).
                     If None, generates an equal 20% balanced distribution.
        seed: Random seed for deterministic reproducibility.
        num_patients: Number of patient profiles to cycle through.
        num_partitions: Number of disjoint partition slots.

    Returns:
        List of ClinicalWorkloadItem transactions.
    """
    rng = random.Random(seed)
    workload: list[ClinicalWorkloadItem] = []

    if scenario_mix is None:
        # Standard balanced distribution across all 5 families
        families = list(ScenarioFamily)
        weights = [0.20, 0.20, 0.20, 0.20, 0.20]
    else:
        families = list(scenario_mix.keys())
        total_w = sum(scenario_mix.values())
        weights = [w / total_w for w in scenario_mix.values()]

    for i in range(count):
        wid = f"tx_{i:05d}"
        chosen_family = rng.choices(families, weights=weights, k=1)[0]
        patient_idx = (i % num_patients) + 1
        item_seed = seed + i * 17

        if chosen_family == ScenarioFamily.CLEAN_UPDATE:
            item = generate_clean_update(wid, patient_idx=patient_idx, seed=item_seed)
        elif chosen_family == ScenarioFamily.CROSS_DOMAIN:
            item = generate_cross_domain(wid, patient_idx=patient_idx, seed=item_seed)
        elif chosen_family == ScenarioFamily.TOCTOU_REVOCATION:
            item = generate_toctou_revocation(wid, patient_idx=patient_idx, seed=item_seed)
        elif chosen_family == ScenarioFamily.SEVERE_DDI:
            item = generate_severe_ddi(wid, patient_idx=patient_idx, seed=item_seed)
        elif chosen_family == ScenarioFamily.DISJOINT_PARTITIONS:
            part_idx = i % num_partitions
            item = generate_disjoint_partition(
                wid, partition_idx=part_idx, total_partitions=num_partitions, seed=item_seed
            )
        else:
            raise ValueError(f"Unsupported scenario family: {chosen_family}")

        workload.append(item)

    return workload


def validate_workload_distribution(
    workload: Sequence[ClinicalWorkloadItem],
) -> dict[str, int]:
    """Computes count summary across all scenario families in the workload."""
    counts: dict[str, int] = {f.value: 0 for f in ScenarioFamily}
    for item in workload:
        counts[item.scenario_family.value] += 1
    return counts
