"""Machine-readable classification of the 25 W8 all-survive mutants.

GMT-06 (spec 2.8): each W8 all-survive mutant is mapped to exactly one
prespecified engineering category with a rationale. This module is the single
source of truth for the category assignment documented in
``research/assurance_soict/w8_survivor_analysis.md``. It is a descriptive
diagnosis — it never excludes a mutant from any W8 denominator and never
re-scores the sealed study.

Categories:
    generator_reach
    missing_oracle
    missing_path_test_target
    budget_exhaustion
    replay_reconstruction_blind_spot
    api_layer_absence
    possible_weak_mutant
    other_with_rationale
"""

from __future__ import annotations

import json
from pathlib import Path

CATEGORIES = (
    "generator_reach",
    "missing_oracle",
    "missing_path_test_target",
    "budget_exhaustion",
    "replay_reconstruction_blind_spot",
    "api_layer_absence",
    "possible_weak_mutant",
    "other_with_rationale",
)

# mutant_id -> (category, rationale). Rationale is a prose diagnosis, not an
# equivalence claim. See w8_survivor_analysis.md for the full table.
CLASSIFICATION: dict[str, tuple[str, str]] = {
    "M01-C": (
        "missing_oracle",
        "commitment apply_commitment_transition stale-base guard; concurrent-commit path exercised "
        + "(test_commitment_transition_shares_state_counter_and_reconstructs) and siblings M01-A/B killed, "
        + "but no frozen test constructs a mismatched base on the commitment apply path.",
    ),
    "M01-D": (
        "missing_oracle",
        "commitment propose_bound stale-base guard; bounded-proposal path reached (siblings M02-D/M07-B/M07-D "
        + "killed) but observed_base_state_version != base_state_version never constructed.",
    ),
    "M02-C": (
        "possible_weak_mutant",
        "commitment validate_base policy-version guard; dedicated test test_base_version_only_proposal_rejects_a_stale_policy_coordinate "
        + "exists and identical guard at validate_current (M02-D) is killed, so the base-site removal is masked by a "
        + "deeper/duplicated check on every path the matrix drives. Descriptive hypothesis, not an equivalence exclusion.",
    ),
    "M03-C": (
        "missing_oracle",
        "commitment validate_base consent-version guard; consent gating tested at route level but a proposal stamped "
        + "with an outdated consent_version is never constructed; generic siblings M03-A/B killed show the matrix can "
        + "observe consent revalidation where driven.",
    ),
    "M03-D": (
        "missing_oracle",
        "commitment validate_current consent-version guard; same construction gap as M03-C at the current-consent site.",
    ),
    "M04-B": (
        "missing_oracle",
        "generic _validate_proposal_snapshot subject-equality guard; function heavily exercised (M07-A/M08-A killed) and "
        + "foreign-profile rejection fires upstream at scope resolution, so the source.profile_id condition is never the "
        + "decisive check on an exercised path.",
    ),
    "M04-C": (
        "missing_oracle",
        "commitment propose subject-equality guard; foreign-profile tests resolve the mismatch before this guard.",
    ),
    "M04-D": (
        "missing_oracle",
        "commitment propose_bound subject-equality guard; same construction gap as M04-C at the bounded-proposal site.",
    ),
    "M05-C": (
        "missing_path_test_target",
        "commitment review actor-role guard; the commitment review flow is not driven by any frozen target, so no test "
        + "invokes review with a scope whose actor_role is outside policy.actor_roles.",
    ),
    "M06-B": (
        "missing_oracle",
        "commitment propose purpose-equality guard; purpose-change tests target the generic THSS path (different "
        + "function); the commitment propose purpose condition is never constructed.",
    ),
    "M06-C": (
        "missing_oracle",
        "generic compile_thss purpose-equality guard; compile_thss reached by pipeline/risk tests but always with a "
        + "matching scope; no mismatched-purpose input is constructed.",
    ),
    "M07-C": (
        "possible_weak_mutant",
        "generic compile_thss expired-scope guard; test_expired_scope_and_mismatched_proposal_fail_closed asserts expiry "
        + "and siblings M07-B/M07-D kill the earlier propose/propose_base guards, so the compiler-level guard is masked "
        + "by earlier scope-expiry rejection on exercised paths. Descriptive hypothesis, not an equivalence exclusion.",
    ),
    "M08-B": (
        "replay_reconstruction_blind_spot",
        "generic reconstruct_snapshot_artifact digest guard; the matrix observes admission-time digests (M08-A killed) "
        + "but never replays a tampered/diverged snapshot payload through reconstruction.",
    ),
    "M08-C": (
        "replay_reconstruction_blind_spot",
        "generic reconstruct_snapshot_artifact manifest self-digest guard; no frozen test replays a manifest whose "
        + "self-digest is inconsistent.",
    ),
    "M08-D": (
        "missing_oracle",
        "generic validate_snapshot_manifest digest-algorithm guard; function exercised (M07-A/M03-A/M02-A killed) but "
        + "every test uses the configured algorithm, so digest_algorithm != DIGEST_ALGORITHM is never constructed.",
    ),
    "M09-B": (
        "missing_path_test_target",
        "commitment validate_bound binding-mode guard; mandatory-THSS tests cover the generic path (M09-A/M09-C killed) "
        + "but commitment validate_bound is never driven with a non-snapshot_bound mode.",
    ),
    "M09-D": (
        "missing_oracle",
        "generic validate_snapshot_manifest THSS-downgrade guard; snapshot-manifest path exercised and downgrade tested "
        + "elsewhere (M09-A/M09-C killed) but the missing snapshot_id/manifest_digest condition is never constructed.",
    ),
    "M09-E": (
        "missing_path_test_target",
        "commitment validate_base binding-mode guard; base-only proposals exercised (test_base_version_only_proposal_is_"
        + "explicit_and_can_commit) but always with an actually-base-only proposal; the cross-mode admission attempt is "
        + "never constructed.",
    ),
    "M11-B": (
        "missing_oracle",
        "generic record_evidence provenance guard; provenance closure partly tested (M11-A killed by M1/M3) but no test "
        + "calls record_evidence with zero rows where the guard is decisive.",
    ),
    "M11-C": (
        "missing_oracle",
        "commitment evidence provenance guard; commitment evidence flows use disclosed same-profile evidence; no test "
        + "constructs foreign-profile or missing evidence at this site.",
    ),
    "M11-D": (
        "missing_oracle",
        "commitment evidence-subset guard; commitment tests use disclosed evidence but never construct evidence_ids "
        + "outside the proposal's observed_evidence_ids.",
    ),
    "M13-B": (
        "replay_reconstruction_blind_spot",
        "generic reconstruct_state superseded-selection guard; read-side reconstruction is never driven with overlapping "
        + "valid intervals; admission-time sibling M13-A killed isolates the gap to reconstruction.",
    ),
    "M13-C": (
        "missing_oracle",
        "generic compile_thss superseded-selection guard; compile_thss reached but no frozen test constructs overlapping/"
        + "superseded rows with valid_to >= valid_at inside the compiler.",
    ),
    "M14-B": (
        "missing_oracle",
        "commitment commit idempotency request-digest guard; idempotency exercised on the generic path (M14-A killed by "
        + "all methods) but no frozen commitment test replays the same key with a different request digest on commit.",
    ),
    "M14-C": (
        "missing_oracle",
        "commitment post-lock idempotency recheck; same construction gap as M14-B at the post-lock recheck site.",
    ),
}


def classify(mutant_id: str) -> tuple[str, str]:
    """Return (category, rationale) for one all-survive mutant."""
    try:
        return CLASSIFICATION[mutant_id]
    except KeyError as exc:
        raise KeyError(f"no classification recorded for {mutant_id}") from exc


def validate_classification(*, analysis_path: Path) -> dict[str, object]:
    """Validate the classifier against the sealed analysis all-survive set."""
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    per_mutant = analysis["per_mutant_method"]
    all_survive = sorted(
        mutant_id
        for mutant_id, by_method in per_mutant.items()
        if all(
            by_method[method]["detected_any_seed"] == 0
            for method in (
                "M0_regression",
                "M1_stateless_property",
                "M2_state_machine",
                "M3_combined",
            )
        )
    )
    if set(all_survive) != set(CLASSIFICATION):
        raise ValueError(
            "govmut_w8_classifier_mismatch: classified set != sealed all-survive set"
        )
    for mutant_id, (category, rationale) in CLASSIFICATION.items():
        if category not in CATEGORIES:
            raise ValueError(f"govmut_w8_classifier_bad_category:{mutant_id}")
        if not rationale:
            raise ValueError(f"govmut_w8_classifier_missing_rationale:{mutant_id}")
    counts: dict[str, int] = {category: 0 for category in CATEGORIES}
    for category, _ in CLASSIFICATION.values():
        counts[category] = counts.get(category, 0) + 1
    return {
        "classified_count": len(CLASSIFICATION),
        "all_survive_count": len(all_survive),
        "category_counts": counts,
        "categories": list(CATEGORIES),
    }
