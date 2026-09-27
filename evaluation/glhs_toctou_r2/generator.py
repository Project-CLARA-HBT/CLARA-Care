"""Schedule generator for the E04 randomized TOCTOU campaign.

Generates >= 1,024 unique logical schedules by exhaustive product expansion
over the grammar dimensions, augmented by compound-mutation expansion and
randomized modifier injection.  After expansion, infeasible combinations are
pruned and duplicates (by canonical key) are removed.

The generator is deterministic: given the same seed, it produces the same
schedule set.  The seed is frozen at protocol creation time.

Statistics (Role B) primary unit: unique logical schedule (by canonical_key).
Jitter repetitions are robustness probes, never new scientific N.
"""

from __future__ import annotations

import hashlib
import itertools
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from evaluation.glhs_toctou_r2.grammar import (
    BENIGN_MUTATIONS,
    COMPOUND_MUTATION_SETS,
    EntityConfig,
    Modifier,
    MutationKind,
    SAFETY_CRITICAL_MUTATIONS,
    STALENESS_MUTATIONS,
    EXPIRY_MUTATIONS,
    ScheduleDescriptor,
    TimingMode,
    expected_outcome_for,
    is_feasible,
)

# Frozen generator seed for reproducibility.
GENERATOR_SEED = 20260928_04
MINIMUM_UNIQUE_SCHEDULES = 1024


def _schedule_id(index: int) -> str:
    return f"E04-TOCTOU-{index:05d}"


def _single_mutation_expansion() -> list[ScheduleDescriptor]:
    """Expand the Cartesian product of single mutations x timing x entity x modifier."""
    schedules: list[ScheduleDescriptor] = []
    index = 0
    for mutation in MutationKind:
        for timing in TimingMode:
            for entity in EntityConfig:
                for modifier in Modifier:
                    desc = ScheduleDescriptor(
                        schedule_id=_schedule_id(index),
                        mutations=(mutation,),
                        timing=timing,
                        entity=entity,
                        modifier=modifier,
                    )
                    if is_feasible(desc):
                        desc = replace(
                            desc,
                            expected_outcome=expected_outcome_for(desc),
                        )
                        schedules.append(desc)
                        index += 1
    return schedules


def _compound_mutation_expansion(start_index: int) -> list[ScheduleDescriptor]:
    """Expand compound mutation sets across timing and entity dimensions."""
    schedules: list[ScheduleDescriptor] = []
    index = start_index
    for mutation_set in COMPOUND_MUTATION_SETS:
        for timing in TimingMode:
            for entity in (EntityConfig.OWNER_SELF, EntityConfig.DELEGATED_ACTOR):
                for modifier in (Modifier.NONE, Modifier.COMPETING_LOCK, Modifier.RETRY_AFTER_ROLLBACK):
                    desc = ScheduleDescriptor(
                        schedule_id=_schedule_id(index),
                        mutations=mutation_set,
                        timing=timing,
                        entity=entity,
                        modifier=modifier,
                        compound=True,
                    )
                    if is_feasible(desc):
                        desc = replace(
                            desc,
                            expected_outcome=expected_outcome_for(desc),
                        )
                        schedules.append(desc)
                        index += 1
    return schedules


def _positive_controls(start_index: int, rng: random.Random, count: int = 64) -> list[ScheduleDescriptor]:
    """Generate positive-control schedules (ADMIT expected)."""
    schedules: list[ScheduleDescriptor] = []
    index = start_index
    benign_list = sorted(BENIGN_MUTATIONS, key=lambda m: m.value)
    for _ in range(count):
        mutation = rng.choice(benign_list)
        timing = rng.choice([TimingMode.COMMIT_BEFORE_MUTATION, TimingMode.MUTATION_BEFORE_COMMIT])
        entity = rng.choice([EntityConfig.OWNER_SELF, EntityConfig.DELEGATED_ACTOR])
        desc = ScheduleDescriptor(
            schedule_id=_schedule_id(index),
            mutations=(mutation,),
            timing=timing,
            entity=entity,
            modifier=Modifier.NONE,
            expected_outcome="ADMIT",
        )
        if is_feasible(desc):
            schedules.append(desc)
            index += 1
    return schedules


def _randomized_augmentation(
    start_index: int,
    rng: random.Random,
    target_count: int,
    existing_keys: set[str],
) -> list[ScheduleDescriptor]:
    """Generate additional random schedules to reach the target count."""
    schedules: list[ScheduleDescriptor] = []
    index = start_index
    mutations_list = list(MutationKind)
    timings_list = list(TimingMode)
    entities_list = list(EntityConfig)
    modifiers_list = list(Modifier)
    attempts = 0
    max_attempts = target_count * 20

    while len(schedules) < target_count and attempts < max_attempts:
        attempts += 1
        # Pick 1-3 mutations randomly.
        n_mutations = rng.choice([1, 1, 1, 2, 2, 3])
        mutations = tuple(sorted(
            rng.sample(mutations_list, min(n_mutations, len(mutations_list))),
            key=lambda m: m.value,
        ))
        timing = rng.choice(timings_list)
        entity = rng.choice(entities_list)
        modifier = rng.choice(modifiers_list)
        writer_count = rng.choice([2, 2, 2, 3, 4])
        compound = len(mutations) > 1

        desc = ScheduleDescriptor(
            schedule_id=_schedule_id(index),
            mutations=mutations,
            timing=timing,
            entity=entity,
            modifier=modifier,
            compound=compound,
            writer_count=writer_count,
        )
        if not is_feasible(desc):
            continue
        if desc.canonical_key in existing_keys:
            continue
        desc = replace(desc, expected_outcome=expected_outcome_for(desc))
        schedules.append(desc)
        existing_keys.add(desc.canonical_key)
        index += 1

    return schedules


def generate_schedules(
    *,
    seed: int = GENERATOR_SEED,
    minimum: int = MINIMUM_UNIQUE_SCHEDULES,
) -> list[ScheduleDescriptor]:
    """Generate at least ``minimum`` unique logical schedules.

    Returns the deduplicated, feasibility-filtered schedule set sorted by
    schedule_id.  The canonical_key guarantees that no two schedules
    represent the same logical interleaving.
    """
    rng = random.Random(seed)

    # Phase 1: exhaustive single-mutation expansion.
    singles = _single_mutation_expansion()

    # Phase 2: compound-mutation expansion.
    compounds = _compound_mutation_expansion(start_index=len(singles))

    # Phase 3: positive controls.
    controls = _positive_controls(
        start_index=len(singles) + len(compounds),
        rng=rng,
        count=64,
    )

    # Deduplicate by canonical key.
    seen_keys: set[str] = set()
    unique: list[ScheduleDescriptor] = []
    for desc in singles + compounds + controls:
        if desc.canonical_key not in seen_keys:
            seen_keys.add(desc.canonical_key)
            unique.append(desc)

    # Phase 4: random augmentation to reach the minimum.
    shortfall = max(0, minimum - len(unique))
    if shortfall > 0:
        augmented = _randomized_augmentation(
            start_index=len(singles) + len(compounds) + len(controls),
            rng=rng,
            target_count=shortfall,
            existing_keys=seen_keys,
        )
        unique.extend(augmented)

    # Re-assign stable sequential IDs after dedup.
    result: list[ScheduleDescriptor] = []
    for idx, desc in enumerate(unique):
        result.append(replace(desc, schedule_id=_schedule_id(idx)))

    if len(result) < minimum:
        raise RuntimeError(
            f"generator_produced_{len(result)}_schedules_below_minimum_{minimum}"
        )

    return result


def schedule_set_digest(schedules: Sequence[ScheduleDescriptor]) -> str:
    """SHA-256 digest of the canonical schedule set for integrity sealing."""
    canonical = "|".join(d.canonical_key for d in sorted(schedules, key=lambda s: s.schedule_id))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def outcome_distribution(schedules: Sequence[ScheduleDescriptor]) -> dict[str, int]:
    """Count schedules by expected_outcome."""
    return dict(Counter(d.expected_outcome for d in schedules))


def timing_distribution(schedules: Sequence[ScheduleDescriptor]) -> dict[str, int]:
    """Count schedules by timing mode."""
    return dict(Counter(d.timing.value for d in schedules))


def mutation_distribution(schedules: Sequence[ScheduleDescriptor]) -> dict[str, int]:
    """Count schedules by mutation kind (each mutation in a compound is counted)."""
    counter: Counter[str] = Counter()
    for d in schedules:
        for m in d.mutations:
            counter[m.value] += 1
    return dict(counter)
