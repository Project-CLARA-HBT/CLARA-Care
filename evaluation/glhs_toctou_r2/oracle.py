"""Oracle for E04 randomized TOCTOU schedule outcomes.

Defines admissible outcome sets for each schedule type.  The oracle is the
authoritative reference for what is and is not a safety violation.

Statistics (Role B) design:
- Primary endpoint: forbidden_commit_rate (target 0.0%, 1-sided 95% Wilson UCB across N >= 1,024).
- Secondary endpoints: safe_rejection_rate, indeterminate_rate, deadlock_rate,
  retry_rate, classification_stability across jitter repetitions.
- Classification categories (Admissible Outcome Set framework):
  1. COMMITTED_BEFORE_GOVERNANCE_MUTATION: Commit succeeded provably before governance drift.
  2. SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION: Commit safely rejected following governance drift.
  3. INDETERMINATE_ORDERING: Concurrent window where exact serial order is unprovable.
  4. FORBIDDEN_COMMIT: Safety violation (commit admitted after governance mutation).
  5. OPERATIONAL_DEADLOCK: Deadlock / serialization failure / lock wait timeout.

Red Team (Role E) verification:
- The oracle MUST NOT trivially accept all outcomes.
- Forbidden outcomes are verified here as actually forbidden.
- Indeterminate classification is honest: only concurrent windows where the
  ordering cannot be established are marked indeterminate.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from evaluation.glhs_toctou_r2.grammar import (
    BENIGN_MUTATIONS,
    EntityConfig,
    Modifier,
    MutationKind,
    SAFETY_CRITICAL_MUTATIONS,
    STALENESS_MUTATIONS,
    EXPIRY_MUTATIONS,
    ScheduleDescriptor,
    TimingMode,
    expected_outcome_for,
)

# ---------------------------------------------------------------------------
# Outcome Classification Categories
# ---------------------------------------------------------------------------

COMMITTED_BEFORE_GOVERNANCE_MUTATION = "COMMITTED_BEFORE_GOVERNANCE_MUTATION"
SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION = "SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION"
INDETERMINATE_ORDERING = "INDETERMINATE_ORDERING"
FORBIDDEN_COMMIT = "FORBIDDEN_COMMIT"
OPERATIONAL_DEADLOCK = "OPERATIONAL_DEADLOCK"

# Legacy/short aliases for backwards compatibility
SAFE = "SAFE"
FORBIDDEN = "FORBIDDEN"
OPERATIONAL = "OPERATIONAL"
INDETERMINATE = "INDETERMINATE"


# ---------------------------------------------------------------------------
# Outcome vocabulary
# ---------------------------------------------------------------------------

# These are the only admissible commit_outcome values.
ADMISSIBLE_COMMIT_OUTCOMES: frozenset[str] = frozenset({
    # Committed
    "transition_committed",
    "proposal_committed",
    # Rejected (safety)
    "consent_check_failed",
    "stale_state_version",
    "policy_check_failed",
    "role_check_failed",
    "evidence_not_found",
    "snapshot_expired",
    "snapshot_digest_mismatch",
    # Rejected (operational)
    "deadlock_detected",
    "could_not_serialize_access",
    "lock_wait_timeout",
    # Retry/rollback
    "rolled_back_stale",
    "retried_committed",
})

COMMITTED_OUTCOMES: frozenset[str] = frozenset({
    "transition_committed",
    "proposal_committed",
    "retried_committed",
})

OPERATIONAL_OUTCOMES: frozenset[str] = frozenset({
    "deadlock_detected",
    "could_not_serialize_access",
    "lock_wait_timeout",
})


def wilson_ucb_95(events: int, total: int, one_sided: bool = True) -> float:
    """Calculate the 95% Wilson score upper confidence bound for a binomial rate.

    Parameters
    ----------
    events : int
        Number of event occurrences (e.g., forbidden commits).
    total : int
        Total scientific observations (N >= 1,024).
    one_sided : bool
        If True, use z = 1.64485362695 (1-sided 95% confidence).
        If False, use z = 1.95996398454 (2-sided 95% / 1-sided 97.5% confidence).

    Returns
    -------
    float
        Upper confidence bound in [0.0, 1.0].
    """
    if total <= 0:
        return 0.0

    k = float(events)
    n = float(total)
    z = 1.6448536269514722 if one_sided else 1.959963984540054

    z2 = z * z
    p_hat = k / n
    center = (k + z2 / 2.0) / (n + z2)
    spread = (z / (n + z2)) * math.sqrt((k * (n - k) / n) + (z2 / 4.0))

    return min(1.0, max(0.0, center + spread))


# ---------------------------------------------------------------------------
# Admissible observation set
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdmissibleOutcomeSet:
    """The set of outcomes the oracle deems admissible for a schedule.

    ``safe_commit_outcomes``: commit outcomes where the commit is admitted
    and the oracle deems it safe (i.e., expected_outcome was ADMIT or the
    commit provably precedes the mutation).

    ``safe_rejection_outcomes``: commit outcomes that are rejections —
    always safe regardless of timing.

    ``operational_outcomes``: deadlock/serialization — never a safety
    success, but not a safety failure either.

    ``forbidden_outcomes``: commit outcomes that constitute a safety
    violation. Any observation landing here makes the run fail-closed.

    ``indeterminate_outcomes``: admitted commits in windows where ordering
    cannot be established. Recorded honestly; NOT counted as safe.
    """

    schedule_id: str
    expected_outcome: str
    safe_commit_outcomes: frozenset[str]
    safe_rejection_outcomes: frozenset[str]
    operational_outcomes: frozenset[str]
    forbidden_outcomes: frozenset[str]
    indeterminate_outcomes: frozenset[str]
    note: str = ""

    @property
    def allowed_outcomes(self) -> frozenset[str]:
        """Union of all non-forbidden outcomes."""
        return (
            self.safe_commit_outcomes
            | self.safe_rejection_outcomes
            | self.operational_outcomes
            | self.indeterminate_outcomes
        )

    def classify(self, commit_outcome: str) -> str:
        """Classify an observed commit outcome into one of the 5 canonical categories.

        Returns one of:
        - FORBIDDEN_COMMIT
        - OPERATIONAL_DEADLOCK
        - INDETERMINATE_ORDERING
        - COMMITTED_BEFORE_GOVERNANCE_MUTATION
        - SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION
        """
        if commit_outcome in self.forbidden_outcomes:
            return FORBIDDEN_COMMIT
        if commit_outcome in self.operational_outcomes:
            return OPERATIONAL_DEADLOCK
        if commit_outcome in self.indeterminate_outcomes:
            return INDETERMINATE_ORDERING
        if commit_outcome in self.safe_commit_outcomes:
            return COMMITTED_BEFORE_GOVERNANCE_MUTATION
        if commit_outcome in self.safe_rejection_outcomes:
            return SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION
        # Unknown outcome: fail closed.
        return FORBIDDEN_COMMIT

    def is_forbidden(self, commit_outcome: str) -> bool:
        return self.classify(commit_outcome) == FORBIDDEN_COMMIT

    def is_safe(self, commit_outcome: str) -> bool:
        c = self.classify(commit_outcome)
        return c in (COMMITTED_BEFORE_GOVERNANCE_MUTATION, SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION)

    def is_operational(self, commit_outcome: str) -> bool:
        return self.classify(commit_outcome) == OPERATIONAL_DEADLOCK

    def is_indeterminate(self, commit_outcome: str) -> bool:
        return self.classify(commit_outcome) == INDETERMINATE_ORDERING


def _build_admissible_set(desc: ScheduleDescriptor) -> AdmissibleOutcomeSet:
    """Build the oracle admissible outcome set for a schedule descriptor.

    Red Team Rule 1: The oracle must not trivially accept everything.
    For REJECT schedules the safe_commit_outcomes set MUST be empty or
    contain only provably pre-mutation commits.

    Red Team Rule 2: Forbidden outcomes are truly forbidden.
    For REJECT schedules, any commit outcome in COMMITTED_OUTCOMES is
    FORBIDDEN — NEVER in indeterminate or safe buckets.

    Red Team Rule 3: INDETERMINATE is honest.
    Only simultaneous_release or partial_overlap windows with safety-critical
    mutations produce INDETERMINATE. A schedule where the timing is
    mutation_before_commit and the mutation is safety-critical is ALWAYS
    FORBIDDEN if committed.
    """
    expected = desc.expected_outcome

    # Standard rejection outcome set (always safe).
    safe_rejections = frozenset({
        "consent_check_failed",
        "stale_state_version",
        "policy_check_failed",
        "role_check_failed",
        "evidence_not_found",
        "snapshot_expired",
        "snapshot_digest_mismatch",
        "rolled_back_stale",
    })

    # Operational outcomes (never safety success).
    ops = frozenset(OPERATIONAL_OUTCOMES)

    mutation_set = desc.mutation_set

    if expected == "OPERATIONAL":
        # Fault-injection schedule: only operational outcomes admissible.
        return AdmissibleOutcomeSet(
            schedule_id=desc.schedule_id,
            expected_outcome=expected,
            safe_commit_outcomes=frozenset(),
            safe_rejection_outcomes=safe_rejections,
            operational_outcomes=ops,
            forbidden_outcomes=frozenset(COMMITTED_OUTCOMES),
            indeterminate_outcomes=frozenset(),
            note="fault_injection_only_operational_outcomes_admissible",
        )

    if expected == "ADMIT":
        # Red Team check: benign-only mutations -> commit is safe.
        # But for commit_before_mutation timing, the commit provably preceded.
        safe_commits = frozenset(COMMITTED_OUTCOMES)
        forbidden: frozenset[str]
        if mutation_set & SAFETY_CRITICAL_MUTATIONS and desc.timing != TimingMode.COMMIT_BEFORE_MUTATION:
            # Mixed scenario: safety-critical mutation present but expected ADMIT.
            # This should not occur per grammar, but fail closed.
            safe_commits = frozenset()
            forbidden = frozenset(COMMITTED_OUTCOMES)
        else:
            forbidden = frozenset()
        return AdmissibleOutcomeSet(
            schedule_id=desc.schedule_id,
            expected_outcome=expected,
            safe_commit_outcomes=safe_commits,
            safe_rejection_outcomes=safe_rejections,
            operational_outcomes=ops,
            forbidden_outcomes=forbidden,
            indeterminate_outcomes=frozenset(),
            note="positive_control_admit_expected",
        )

    if expected == "INDETERMINATE":
        # Red Team Rule 3: Indeterminate is honest.
        # Simultaneous release or partial overlap with safety-critical.
        # A committed outcome here is INDETERMINATE, not SAFE.
        # We do NOT count it as safe, but we do NOT count it as forbidden
        # (because we cannot establish the ordering).
        safe_commits: frozenset[str] = frozenset()
        indeterminate = frozenset(COMMITTED_OUTCOMES)
        return AdmissibleOutcomeSet(
            schedule_id=desc.schedule_id,
            expected_outcome=expected,
            safe_commit_outcomes=safe_commits,
            safe_rejection_outcomes=safe_rejections,
            operational_outcomes=ops,
            forbidden_outcomes=frozenset(),
            indeterminate_outcomes=indeterminate,
            note="concurrent_window_ordering_unknowable",
        )

    # expected == "REJECT": Any committed outcome is FORBIDDEN.
    # Red Team Rule 1 and 2: safe_commit_outcomes MUST be empty for REJECT.
    # Red Team Rule 2: forbidden_outcomes MUST include all COMMITTED_OUTCOMES.
    if desc.timing == TimingMode.COMMIT_BEFORE_MUTATION and not (
        mutation_set & (STALENESS_MUTATIONS | EXPIRY_MUTATIONS)
    ):
        # Exception: commit provably completed first; committed is safe here
        # only for REJECT schedules where timing is commit_before_mutation and
        # the mutations are NOT staleness/expiry (staleness always rejects).
        # This represents the control arm.
        safe_commits_ctrl = frozenset(COMMITTED_OUTCOMES)
        forbidden_ctrl: frozenset[str] = frozenset()
        return AdmissibleOutcomeSet(
            schedule_id=desc.schedule_id,
            expected_outcome=expected,
            safe_commit_outcomes=safe_commits_ctrl,
            safe_rejection_outcomes=safe_rejections,
            operational_outcomes=ops,
            forbidden_outcomes=forbidden_ctrl,
            indeterminate_outcomes=frozenset(),
            note="commit_before_mutation_control_arm_commit_safe",
        )

    return AdmissibleOutcomeSet(
        schedule_id=desc.schedule_id,
        expected_outcome=expected,
        safe_commit_outcomes=frozenset(),
        safe_rejection_outcomes=safe_rejections,
        operational_outcomes=ops,
        forbidden_outcomes=frozenset(COMMITTED_OUTCOMES),
        indeterminate_outcomes=frozenset(),
        note="mutation_precedes_commit_committed_outcome_is_forbidden",
    )


class Oracle:
    """E04 TOCTOU oracle: classifies observed outcomes against expected safety contracts.

    Red Team validations:
    - Asserts that no REJECT schedule has committed outcomes in its safe set.
    - Asserts that INDETERMINATE schedules never have committed outcomes in forbidden.
    - Asserts that OPERATIONAL schedules cannot produce safety-success.
    """

    def __init__(self, schedules: Sequence[ScheduleDescriptor]) -> None:
        self._by_id: dict[str, AdmissibleOutcomeSet] = {}
        for desc in schedules:
            aos = _build_admissible_set(desc)
            self._red_team_verify(desc, aos)
            self._by_id[desc.schedule_id] = aos

    @staticmethod
    def _red_team_verify(desc: ScheduleDescriptor, aos: AdmissibleOutcomeSet) -> None:
        """Red Team: verify oracle invariants at construction time."""
        # RT-1: For REJECT schedules, safe_commit_outcomes must not contain
        # committed outcomes (except the commit-before-mutation special arm).
        if desc.expected_outcome == "REJECT":
            if aos.note != "commit_before_mutation_control_arm_commit_safe":
                overlap = aos.safe_commit_outcomes & COMMITTED_OUTCOMES
                if overlap:
                    raise AssertionError(
                        f"oracle_rt1_safe_commit_set_nonempty_for_reject:"
                        f"{desc.schedule_id}:{overlap}"
                    )
                # RT-2: forbidden MUST include all committed outcomes.
                missing_forbidden = COMMITTED_OUTCOMES - aos.forbidden_outcomes
                if missing_forbidden:
                    raise AssertionError(
                        f"oracle_rt2_forbidden_set_missing_committed:"
                        f"{desc.schedule_id}:{missing_forbidden}"
                    )

        # RT-3: INDETERMINATE schedules must not have committed in forbidden.
        if desc.expected_outcome == "INDETERMINATE":
            bad = aos.forbidden_outcomes & COMMITTED_OUTCOMES
            if bad:
                raise AssertionError(
                    f"oracle_rt3_indeterminate_committed_in_forbidden:"
                    f"{desc.schedule_id}:{bad}"
                )

        # RT-4: OPERATIONAL schedules must have empty safe_commit_outcomes.
        if desc.expected_outcome == "OPERATIONAL":
            if aos.safe_commit_outcomes:
                raise AssertionError(
                    f"oracle_rt4_operational_safe_commit_nonempty:"
                    f"{desc.schedule_id}"
                )

    def get(self, schedule_id: str) -> AdmissibleOutcomeSet | None:
        return self._by_id.get(schedule_id)

    def classify(self, schedule_id: str, commit_outcome: str) -> str:
        aos = self._by_id.get(schedule_id)
        if aos is None:
            return "UNKNOWN_SCHEDULE"
        return aos.classify(commit_outcome)

    def is_forbidden(self, schedule_id: str, commit_outcome: str) -> bool:
        aos = self.get(schedule_id)
        if aos is None:
            return True
        return aos.is_forbidden(commit_outcome)

    def is_safe(self, schedule_id: str, commit_outcome: str) -> bool:
        aos = self.get(schedule_id)
        if aos is None:
            return False
        return aos.is_safe(commit_outcome)

    def is_operational(self, schedule_id: str, commit_outcome: str) -> bool:
        aos = self.get(schedule_id)
        if aos is None:
            return False
        return aos.is_operational(commit_outcome)

    def is_indeterminate(self, schedule_id: str, commit_outcome: str) -> bool:
        aos = self.get(schedule_id)
        if aos is None:
            return False
        return aos.is_indeterminate(commit_outcome)

    def forbidden_commit_rate(
        self, results: Sequence[Mapping[str, object]]
    ) -> float:
        """Primary endpoint: fraction of observations with FORBIDDEN commits."""
        if not results:
            return 0.0
        forbidden = sum(
            1
            for r in results
            if self.is_forbidden(str(r.get("schedule_id", "")), str(r.get("commit_outcome", "")))
        )
        return forbidden / len(results)

    def wilson_ucb_95_forbidden_commit_rate(
        self, results: Sequence[Mapping[str, object]], one_sided: bool = True
    ) -> float:
        """Calculate 1-sided 95% Wilson score UCB for forbidden commit rate."""
        if not results:
            return 0.0
        forbidden_count = sum(
            1
            for r in results
            if self.is_forbidden(str(r.get("schedule_id", "")), str(r.get("commit_outcome", "")))
        )
        return wilson_ucb_95(forbidden_count, len(results), one_sided=one_sided)

    def safe_rejection_rate(
        self, results: Sequence[Mapping[str, object]]
    ) -> float:
        """Secondary: fraction of observations with safe rejections."""
        if not results:
            return 0.0
        safe = sum(
            1
            for r in results
            if self.classify(
                str(r.get("schedule_id", "")), str(r.get("commit_outcome", ""))
            ) == SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION
        )
        return safe / len(results)

    def indeterminate_rate(
        self, results: Sequence[Mapping[str, object]]
    ) -> float:
        """Secondary: fraction with INDETERMINATE classification."""
        if not results:
            return 0.0
        indet = sum(
            1
            for r in results
            if self.is_indeterminate(
                str(r.get("schedule_id", "")), str(r.get("commit_outcome", ""))
            )
        )
        return indet / len(results)

    def deadlock_rate(
        self, results: Sequence[Mapping[str, object]]
    ) -> float:
        """Secondary: fraction of observations ending in deadlock/operational contention."""
        if not results:
            return 0.0
        deadlocks = sum(
            1
            for r in results
            if self.is_operational(
                str(r.get("schedule_id", "")), str(r.get("commit_outcome", ""))
            )
            or str(r.get("commit_outcome", "")) in OPERATIONAL_OUTCOMES
        )
        return deadlocks / len(results)

    def classification_stability(
        self,
        results_a: Sequence[Mapping[str, object]],
        results_b: Sequence[Mapping[str, object]],
    ) -> float:
        """Secondary: agreement rate between two result sets (jitter repetitions).

        Returns the fraction of schedule_ids with matching classifications
        across both sets.
        """
        by_id_a = {str(r["schedule_id"]): str(r["commit_outcome"]) for r in results_a}
        by_id_b = {str(r["schedule_id"]): str(r["commit_outcome"]) for r in results_b}
        common = set(by_id_a) & set(by_id_b)
        if not common:
            return 0.0
        agree = sum(
            1
            for sid in common
            if self.classify(sid, by_id_a[sid]) == self.classify(sid, by_id_b[sid])
        )
        return agree / len(common)

    def summary(self, results: Sequence[Mapping[str, object]]) -> dict[str, object]:
        """Aggregate endpoint summary over an observation set."""
        from collections import Counter
        classifications: Counter[str] = Counter()
        for r in results:
            c = self.classify(str(r.get("schedule_id", "")), str(r.get("commit_outcome", "")))
            classifications[c] += 1
        total = len(results)
        forbidden_cnt = classifications[FORBIDDEN_COMMIT]
        raw_forbidden_rate = self.forbidden_commit_rate(results)
        ucb_95 = self.wilson_ucb_95_forbidden_commit_rate(results, one_sided=True)

        return {
            "total": total,
            "forbidden_count": forbidden_cnt,
            "safe_rejected_count": classifications[SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION],
            "committed_before_mutation_count": classifications[COMMITTED_BEFORE_GOVERNANCE_MUTATION],
            "operational_count": classifications[OPERATIONAL_DEADLOCK],
            "indeterminate_count": classifications[INDETERMINATE_ORDERING],
            "forbidden_commit_rate": round(raw_forbidden_rate, 6),
            "wilson_95_ucb_forbidden_commit_rate": round(ucb_95, 6),
            "safe_rejection_rate": round(self.safe_rejection_rate(results), 6),
            "indeterminate_rate": round(self.indeterminate_rate(results), 6),
            "deadlock_rate": round(self.deadlock_rate(results), 6),
            "primary_endpoint_pass": forbidden_cnt == 0,
        }

