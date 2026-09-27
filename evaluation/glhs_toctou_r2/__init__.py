"""E04: Generated PostgreSQL TOCTOU Campaign.

Phase 4 randomized schedule generation, oracle-based verification,
execution, failure shrinking, and statistical analysis.
"""

from evaluation.glhs_toctou_r2.analyze import (
    CampaignAnalysis,
    CategoricalMetrics,
    analyze_campaign_results,
    compute_one_sided_wilson_upper,
    compute_wilson_score_interval,
    generate_summary_report,
)
from evaluation.glhs_toctou_r2.executor import (
    E04ExecutorEnv,
    ScheduleResult,
    execute_campaign,
    execute_schedule,
)
from evaluation.glhs_toctou_r2.generator import (
    GENERATOR_SEED,
    MINIMUM_UNIQUE_SCHEDULES,
    generate_schedules,
    mutation_distribution,
    outcome_distribution,
    schedule_set_digest,
    timing_distribution,
)
from evaluation.glhs_toctou_r2.grammar import (
    BENIGN_MUTATIONS,
    COMPOUND_MUTATION_SETS,
    SAFETY_CRITICAL_MUTATIONS,
    EntityConfig,
    Modifier,
    MutationKind,
    ScheduleDescriptor,
    TimingMode,
    expected_outcome_for,
    is_feasible,
)
from evaluation.glhs_toctou_r2.oracle import (
    ADMISSIBLE_COMMIT_OUTCOMES,
    COMMITTED_OUTCOMES,
    OPERATIONAL_OUTCOMES,
    AdmissibleOutcomeSet,
    Oracle,
)
from evaluation.glhs_toctou_r2.shrink import shrink_all_forbidden, shrink_schedule

__all__ = [
    "ADMISSIBLE_COMMIT_OUTCOMES",
    "BENIGN_MUTATIONS",
    "COMPOUND_MUTATION_SETS",
    "COMMITTED_OUTCOMES",
    "GENERATOR_SEED",
    "MINIMUM_UNIQUE_SCHEDULES",
    "OPERATIONAL_OUTCOMES",
    "SAFETY_CRITICAL_MUTATIONS",
    "AdmissibleOutcomeSet",
    "CampaignAnalysis",
    "CategoricalMetrics",
    "E04ExecutorEnv",
    "EntityConfig",
    "Modifier",
    "MutationKind",
    "Oracle",
    "ScheduleDescriptor",
    "ScheduleResult",
    "TimingMode",
    "analyze_campaign_results",
    "compute_one_sided_wilson_upper",
    "compute_wilson_score_interval",
    "execute_campaign",
    "execute_schedule",
    "expected_outcome_for",
    "generate_schedules",
    "generate_summary_report",
    "is_feasible",
    "mutation_distribution",
    "outcome_distribution",
    "schedule_set_digest",
    "shrink_all_forbidden",
    "shrink_schedule",
    "timing_distribution",
]
