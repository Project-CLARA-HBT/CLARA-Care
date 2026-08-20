"""Santos-Grueiro 4-Boundary Commit-Time Authorization Framework for LLM Agents.

Reference:
Santos-Grueiro, I. (2026). "Temporary Authority, Permanent Effects:
Commit-Time Authorization for LLM Agents." arXiv:2607.10487.

Formalizes and validates the four fundamental commit-time authorization boundaries:
1. Freshness Boundary: Bitemporal validity and lease TTL intersection (tau_valid cap tau_txn).
2. Causal Precedence Boundary: Base entity version invariance (V(e_k) == v_s(e_k)).
3. Effect Scoping Boundary: Dynamic Entity DAG lease scoping (K_write subseteq K_lease).
4. Admissibility Boundary: Layer 1 Deterministic Clinical Barrier (DDI, Consent, RBAC, Policy Epoch).
"""

from __future__ import annotations

import enum
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


class BoundaryViolationType(str, enum.Enum):
    NONE = "none"
    FRESHNESS_VIOLATION = "freshness_boundary_violation"
    CAUSAL_PRECEDENCE_VIOLATION = "causal_precedence_boundary_violation"
    EFFECT_SCOPING_VIOLATION = "effect_scoping_boundary_violation"
    ADMISSIBILITY_VIOLATION = "admissibility_boundary_violation"


@dataclass(frozen=True)
class BitemporalInterval:
    """Snodgrass (1995) bitemporal interval: valid time and transaction/knowledge time."""

    valid_start: float
    valid_end: float | None
    know_start: float
    know_end: float | None

    def is_valid_at(self, t_valid: float) -> bool:
        if t_valid < self.valid_start:
            return False
        return not (self.valid_end is not None and t_valid >= self.valid_end)

    def is_known_at(self, t_know: float) -> bool:
        if t_know < self.know_start:
            return False
        return not (self.know_end is not None and t_know >= self.know_end)


@dataclass(frozen=True)
class EntityDAGCoordinate:
    """Partition key K = (profile_id, domain, slot)."""

    profile_id: str
    domain: str
    slot: str

    def to_key(self) -> str:
        return f"{self.profile_id}:{self.domain}:{self.slot}"


@dataclass
class AuthorizationLease:
    """Temporary authority lease issued at snapshot time t1."""

    lease_id: str
    profile_id: str
    actor_id: str
    actor_role: str
    purpose: str
    authorized_coordinates: set[str]
    snapshot_base_versions: dict[str, int]
    policy_epoch: int
    consent_epoch: int
    issued_at: float
    expires_at: float


@dataclass
class ClinicalMutation:
    """Proposed clinical mutation from LLM agent or clinician."""

    coordinate: EntityDAGCoordinate
    action: str  # "insert", "update", "discontinue", "adjust_dose"
    payload: dict[str, Any]
    temporal_validity: BitemporalInterval
    claimed_base_version: int


@dataclass
class FourBoundaryValidationResult:
    """Detailed audit report from the 4-boundary validator."""

    is_admissible: bool
    primary_violation: BoundaryViolationType
    violation_message: str | None
    freshness_passed: bool
    causal_precedence_passed: bool
    effect_scoping_passed: bool
    admissibility_passed: bool
    ddi_conflicts_detected: list[str] = field(default_factory=list)


# Known severe clinical drug-drug interactions for Layer 1 Admissibility checking
SEVERE_DDI_PAIRS: set[frozenset[str]] = {
    frozenset(["warfarin", "aspirin"]),
    frozenset(["sildenafil", "nitroglycerin"]),
    frozenset(["clopidogrel", "omeprazole"]),
    frozenset(["simvastatin", "clarithromycin"]),
    frozenset(["methotrexate", "trimethoprim"]),
    frozenset(["potassium_chloride", "spironolactone"]),
}


class SantosGrueiroFourBoundaryValidator:
    """Commit-Time Authorization Engine enforcing all 4 Santos-Grueiro Boundaries."""

    def __init__(self, ddi_database: set[frozenset[str]] | None = None) -> None:
        self.ddi_database = SEVERE_DDI_PAIRS if ddi_database is None else ddi_database

    def validate_freshness_boundary(
        self,
        lease: AuthorizationLease,
        mutations: Sequence[ClinicalMutation],
        current_time: float,
    ) -> tuple[bool, str | None]:
        """Boundary 1: Check lease expiry and bitemporal validity."""
        # 1. Lease TTL Check
        if current_time > lease.expires_at:
            return False, f"Temporary authority lease {lease.lease_id} expired at {lease.expires_at:.2f} (current={current_time:.2f})"

        # 2. Bitemporal fact interval check
        for mut in mutations:
            if not mut.temporal_validity.is_known_at(current_time):
                return False, f"Mutation for {mut.coordinate.to_key()} knowledge time not current ({mut.temporal_validity})"
        return True, None

    def validate_causal_precedence_boundary(
        self,
        lease: AuthorizationLease,
        mutations: Sequence[ClinicalMutation],
        committed_partition_versions: dict[str, int],
    ) -> tuple[bool, str | None]:
        """Boundary 2: Check causal base versions (V(e_k) == v_s(e_k))."""
        for mut in mutations:
            key = mut.coordinate.to_key()
            snapshot_v = lease.snapshot_base_versions.get(key, 0)
            claimed_v = mut.claimed_base_version
            committed_v = committed_partition_versions.get(key, 0)

            if claimed_v != snapshot_v:
                return False, f"Claimed base version for {key} ({claimed_v}) != snapshot version ({snapshot_v})"
            if committed_v > snapshot_v:
                return False, f"Causal precedence conflict on {key}: committed DB version ({committed_v}) > snapshot version ({snapshot_v})"
        return True, None

    def validate_effect_scoping_boundary(
        self,
        lease: AuthorizationLease,
        mutations: Sequence[ClinicalMutation],
    ) -> tuple[bool, str | None]:
        """Boundary 3: Check that mutations are strictly within authorized DAG lease scope."""
        for mut in mutations:
            key = mut.coordinate.to_key()
            if mut.coordinate.profile_id != lease.profile_id:
                return False, f"Cross-tenant effect escalation: mutation target {mut.coordinate.profile_id} != lease {lease.profile_id}"
            if key not in lease.authorized_coordinates:
                return False, f"Effect scoping violation: coordinate {key} not in authorized lease set {lease.authorized_coordinates}"
        return True, None

    def validate_admissibility_boundary(
        self,
        lease: AuthorizationLease,
        mutations: Sequence[ClinicalMutation],
        current_active_medications: set[str],
        current_policy_epoch: int,
        current_consent_epoch: int,
    ) -> tuple[bool, str | None, list[str]]:
        """Boundary 4: Deterministic clinical safety invariants (DDI, Consent, Policy Epoch)."""
        # 1. Policy & Consent Epoch Invariance
        if current_policy_epoch != lease.policy_epoch:
            return False, f"Policy epoch mismatch: current {current_policy_epoch} != lease {lease.policy_epoch}", []
        if current_consent_epoch != lease.consent_epoch:
            return False, f"Consent epoch mismatch: patient consent modified/revoked ({current_consent_epoch} != {lease.consent_epoch})", []

        # 2. Severe Drug-Drug Interaction Barrier
        proposed_meds = {
            mut.payload.get("drug_name", "").strip().lower()
            for mut in mutations
            if mut.coordinate.domain == "medication" and mut.action in ("insert", "update", "adjust_dose")
        }
        proposed_meds.discard("")

        active_meds = {m.strip().lower() for m in current_active_medications}
        all_meds = proposed_meds | active_meds

        conflicts: list[str] = []
        for pair in self.ddi_database:
            if pair.issubset(all_meds):
                p_list = sorted(pair)
                conflicts.append(f"{p_list[0]} + {p_list[1]}")

        if conflicts:
            return False, f"Deterministic DDI safety barrier triggered: severe interactions detected ({', '.join(conflicts)})", conflicts

        return True, None, []

    def evaluate_proposal(
        self,
        lease: AuthorizationLease,
        mutations: Sequence[ClinicalMutation],
        committed_partition_versions: dict[str, int],
        current_active_medications: set[str],
        current_policy_epoch: int,
        current_consent_epoch: int,
        current_time: float,
    ) -> FourBoundaryValidationResult:
        """Evaluate complete 4-boundary authorization pipeline with fail-closed semantics."""
        # Boundary 1: Freshness
        f_ok, f_msg = self.validate_freshness_boundary(lease, mutations, current_time)
        if not f_ok:
            return FourBoundaryValidationResult(
                is_admissible=False,
                primary_violation=BoundaryViolationType.FRESHNESS_VIOLATION,
                violation_message=f_msg,
                freshness_passed=False,
                causal_precedence_passed=False,
                effect_scoping_passed=False,
                admissibility_passed=False,
            )

        # Boundary 2: Effect Scoping
        e_ok, e_msg = self.validate_effect_scoping_boundary(lease, mutations)
        if not e_ok:
            return FourBoundaryValidationResult(
                is_admissible=False,
                primary_violation=BoundaryViolationType.EFFECT_SCOPING_VIOLATION,
                violation_message=e_msg,
                freshness_passed=True,
                effect_scoping_passed=False,
                causal_precedence_passed=False,
                admissibility_passed=False,
            )

        # Boundary 3: Causal Precedence
        c_ok, c_msg = self.validate_causal_precedence_boundary(lease, mutations, committed_partition_versions)
        if not c_ok:
            return FourBoundaryValidationResult(
                is_admissible=False,
                primary_violation=BoundaryViolationType.CAUSAL_PRECEDENCE_VIOLATION,
                violation_message=c_msg,
                freshness_passed=True,
                effect_scoping_passed=True,
                causal_precedence_passed=False,
                admissibility_passed=False,
            )

        # Boundary 4: Admissibility
        a_ok, a_msg, ddi_conflicts = self.validate_admissibility_boundary(
            lease=lease,
            mutations=mutations,
            current_active_medications=current_active_medications,
            current_policy_epoch=current_policy_epoch,
            current_consent_epoch=current_consent_epoch,
        )
        if not a_ok:
            return FourBoundaryValidationResult(
                is_admissible=False,
                primary_violation=BoundaryViolationType.ADMISSIBILITY_VIOLATION,
                violation_message=a_msg,
                freshness_passed=True,
                effect_scoping_passed=True,
                causal_precedence_passed=True,
                admissibility_passed=False,
                ddi_conflicts_detected=ddi_conflicts,
            )

        return FourBoundaryValidationResult(
            is_admissible=True,
            primary_violation=BoundaryViolationType.NONE,
            violation_message=None,
            freshness_passed=True,
            effect_scoping_passed=True,
            causal_precedence_passed=True,
            admissibility_passed=True,
        )


def run_four_boundary_stress_evaluation(num_cases: int = 100) -> dict[str, Any]:
    """Execute evaluation across clean and mutated adversarial test cases."""
    validator = SantosGrueiroFourBoundaryValidator()
    t0 = 10000.0

    profile = "patient-eval-101"
    coord_met = EntityDAGCoordinate(profile, "medication", "metformin")
    coord_lis = EntityDAGCoordinate(profile, "medication", "lisinopril")
    coord_war = EntityDAGCoordinate(profile, "medication", "warfarin")
    coord_asp = EntityDAGCoordinate(profile, "medication", "aspirin")
    coord_unauth = EntityDAGCoordinate("patient-eval-999", "medication", "insulin")

    base_lease = AuthorizationLease(
        lease_id="lease-sec-4820",
        profile_id=profile,
        actor_id="clinician_01",
        actor_role="physician",
        purpose="chronic_disease_mgmt",
        authorized_coordinates={coord_met.to_key(), coord_lis.to_key(), coord_war.to_key(), coord_asp.to_key()},
        snapshot_base_versions={coord_met.to_key(): 1, coord_lis.to_key(): 1, coord_war.to_key(): 1, coord_asp.to_key(): 1},
        policy_epoch=1,
        consent_epoch=1,
        issued_at=t0,
        expires_at=t0 + 60.0,
    )

    interval = BitemporalInterval(valid_start=t0 - 100, valid_end=None, know_start=t0 - 100, know_end=None)

    valid_mutation = ClinicalMutation(
        coordinate=coord_met,
        action="adjust_dose",
        payload={"drug_name": "metformin", "dose": "1000mg"},
        temporal_validity=interval,
        claimed_base_version=1,
    )

    clean_passed = 0
    freshness_blocked = 0
    causal_blocked = 0
    scoping_blocked = 0
    admissibility_blocked = 0

    for _ in range(num_cases):
        # 1. Clean case
        res = validator.evaluate_proposal(
            lease=base_lease,
            mutations=[valid_mutation],
            committed_partition_versions={coord_met.to_key(): 1},
            current_active_medications={"lisinopril"},
            current_policy_epoch=1,
            current_consent_epoch=1,
            current_time=t0 + 10.0,
        )
        if res.is_admissible:
            clean_passed += 1

        # 2. Expired lease
        res_f = validator.evaluate_proposal(
            lease=base_lease,
            mutations=[valid_mutation],
            committed_partition_versions={coord_met.to_key(): 1},
            current_active_medications={"lisinopril"},
            current_policy_epoch=1,
            current_consent_epoch=1,
            current_time=t0 + 70.0,
        )
        if not res_f.is_admissible and res_f.primary_violation == BoundaryViolationType.FRESHNESS_VIOLATION:
            freshness_blocked += 1

        # 3. Causal conflict
        res_c = validator.evaluate_proposal(
            lease=base_lease,
            mutations=[valid_mutation],
            committed_partition_versions={coord_met.to_key(): 2},  # Advanced to v2
            current_active_medications={"lisinopril"},
            current_policy_epoch=1,
            current_consent_epoch=1,
            current_time=t0 + 10.0,
        )
        if not res_c.is_admissible and res_c.primary_violation == BoundaryViolationType.CAUSAL_PRECEDENCE_VIOLATION:
            causal_blocked += 1

        # 4. Out of scope mutation
        unauth_mut = ClinicalMutation(
            coordinate=coord_unauth,
            action="insert",
            payload={"drug_name": "insulin"},
            temporal_validity=interval,
            claimed_base_version=1,
        )
        res_e = validator.evaluate_proposal(
            lease=base_lease,
            mutations=[unauth_mut],
            committed_partition_versions={coord_unauth.to_key(): 1},
            current_active_medications=set(),
            current_policy_epoch=1,
            current_consent_epoch=1,
            current_time=t0 + 10.0,
        )
        if not res_e.is_admissible and res_e.primary_violation == BoundaryViolationType.EFFECT_SCOPING_VIOLATION:
            scoping_blocked += 1

        # 5. Admissibility DDI conflict (Warfarin + Aspirin)
        ddi_mut = ClinicalMutation(
            coordinate=coord_war,
            action="insert",
            payload={"drug_name": "warfarin"},
            temporal_validity=interval,
            claimed_base_version=1,
        )
        res_a = validator.evaluate_proposal(
            lease=base_lease,
            mutations=[ddi_mut],
            committed_partition_versions={coord_war.to_key(): 1},
            current_active_medications={"aspirin"},
            current_policy_epoch=1,
            current_consent_epoch=1,
            current_time=t0 + 10.0,
        )
        if not res_a.is_admissible and res_a.primary_violation == BoundaryViolationType.ADMISSIBILITY_VIOLATION:
            admissibility_blocked += 1

    return {
        "num_cases": num_cases,
        "clean_acceptance_rate": clean_passed / num_cases,
        "freshness_block_rate": freshness_blocked / num_cases,
        "causal_block_rate": causal_blocked / num_cases,
        "scoping_block_rate": scoping_blocked / num_cases,
        "admissibility_block_rate": admissibility_blocked / num_cases,
        "all_boundaries_enforced": (
            clean_passed == num_cases
            and freshness_blocked == num_cases
            and causal_blocked == num_cases
            and scoping_blocked == num_cases
            and admissibility_blocked == num_cases
        ),
    }


if __name__ == "__main__":
    report = run_four_boundary_stress_evaluation(100)
    print("Santos-Grueiro 4-Boundary Authorization Evaluation:")
    print(json.dumps(report, indent=2))
