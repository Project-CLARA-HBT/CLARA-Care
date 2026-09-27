"""Failure shrinker for E04 randomized TOCTOU campaign.

When a schedule produces a FORBIDDEN outcome, the shrinker attempts to
find the minimal mutation set and simplest timing mode that still
reproduces the forbidden classification.

Shrinking strategy:
1. Remove one mutation at a time; if still forbidden, keep the reduction.
2. Simplify timing: simultaneous_release → mutation_before_commit.
3. Remove modifier: any → none.
4. Simplify entity: delegated → owner_self.

The shrinker is deterministic and produces a shrink report with the
original and minimized schedule descriptors.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from evaluation.glhs_toctou_r2.executor import (
    E04ExecutorEnv,
    ScheduleResult,
    execute_schedule,
)
from evaluation.glhs_toctou_r2.grammar import (
    EntityConfig,
    Modifier,
    MutationKind,
    ScheduleDescriptor,
    TimingMode,
    expected_outcome_for,
    is_feasible,
)
from evaluation.glhs_toctou_r2.oracle import Oracle


def _try_shrink(
    desc: ScheduleDescriptor,
    env: E04ExecutorEnv,
    oracle: Oracle,
) -> ScheduleResult | None:
    """Run a candidate schedule and return result if FORBIDDEN, else None."""
    if not is_feasible(desc):
        return None
    desc_with_outcome = replace(desc, expected_outcome=expected_outcome_for(desc))
    # Rebuild oracle for this single schedule.
    try:
        local_oracle = Oracle([desc_with_outcome])
    except AssertionError:
        return None
    result = execute_schedule(desc_with_outcome, env, local_oracle)
    if result.forbidden:
        return result
    return None


def shrink_schedule(
    desc: ScheduleDescriptor,
    env: E04ExecutorEnv,
    oracle: Oracle,
) -> dict[str, object]:
    """Shrink a forbidden schedule to its minimal reproduction.

    Returns a report dict with the original descriptor, the minimized
    descriptor, and the number of shrink steps attempted.
    """
    current = desc
    steps = 0
    shrink_log: list[str] = []

    # Step 1: Remove mutations one at a time.
    if len(current.mutations) > 1:
        for i in range(len(current.mutations)):
            candidate_mutations = current.mutations[:i] + current.mutations[i + 1:]
            if not candidate_mutations:
                continue
            candidate = replace(current, mutations=candidate_mutations)
            result = _try_shrink(candidate, env, oracle)
            steps += 1
            if result is not None:
                shrink_log.append(f"removed_mutation_{current.mutations[i].value}")
                current = candidate
                break

    # Step 2: Simplify timing.
    timing_simplifications = [
        (TimingMode.PARTIAL_OVERLAP, TimingMode.SIMULTANEOUS_RELEASE),
        (TimingMode.SIMULTANEOUS_RELEASE, TimingMode.MUTATION_BEFORE_COMMIT),
        (TimingMode.READ_BEFORE_WRITE_AFTER, TimingMode.MUTATION_BEFORE_COMMIT),
        (TimingMode.DELAYED_COMMIT, TimingMode.MUTATION_BEFORE_COMMIT),
    ]
    for from_timing, to_timing in timing_simplifications:
        if current.timing == from_timing:
            candidate = replace(current, timing=to_timing)
            result = _try_shrink(candidate, env, oracle)
            steps += 1
            if result is not None:
                shrink_log.append(f"simplified_timing_{from_timing.value}_to_{to_timing.value}")
                current = candidate
                break

    # Step 3: Remove modifier.
    if current.modifier != Modifier.NONE:
        candidate = replace(current, modifier=Modifier.NONE)
        result = _try_shrink(candidate, env, oracle)
        steps += 1
        if result is not None:
            shrink_log.append(f"removed_modifier_{current.modifier.value}")
            current = candidate

    # Step 4: Simplify entity.
    entity_simplifications = [
        (EntityConfig.CROSS_PROFILE, EntityConfig.OWNER_SELF),
        (EntityConfig.UNRELATED_ENTITY, EntityConfig.OWNER_SELF),
        (EntityConfig.DELEGATED_ACTOR, EntityConfig.OWNER_SELF),
    ]
    for from_entity, to_entity in entity_simplifications:
        if current.entity == from_entity:
            candidate = replace(current, entity=to_entity)
            result = _try_shrink(candidate, env, oracle)
            steps += 1
            if result is not None:
                shrink_log.append(f"simplified_entity_{from_entity.value}_to_{to_entity.value}")
                current = candidate
                break

    return {
        "original": desc.to_dict(),
        "minimized": current.to_dict(),
        "shrink_steps": steps,
        "shrink_log": shrink_log,
        "reproduced": current.canonical_key != desc.canonical_key,
    }


def shrink_all_forbidden(
    results: Sequence[ScheduleResult],
    schedules: Sequence[ScheduleDescriptor],
    env: E04ExecutorEnv,
    oracle: Oracle,
) -> list[dict[str, object]]:
    """Shrink every forbidden result in the campaign."""
    by_id = {d.schedule_id: d for d in schedules}
    reports: list[dict[str, object]] = []
    for result in results:
        if result.forbidden:
            desc = by_id.get(result.schedule_id)
            if desc is not None:
                report = shrink_schedule(desc, env, oracle)
                reports.append(report)
    return reports
