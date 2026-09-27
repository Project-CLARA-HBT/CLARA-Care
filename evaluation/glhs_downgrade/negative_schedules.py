"""Negative laundering templates and schedule generators for GLHS E03 downgrade assurance.

E03 Evaluates:
1. Snapshot-bound model proposal downgraded to `base_version_only` at submission.
2. Human-reviewed proposal dropping parent's `inference_context_binding_id`.
3. Lineage parent substitution (pointing to a different benign proposal).
4. Snapshot ID substitution during clinician review.
5. Binding-mode mutation (`snapshot_bound` altered to `base_version_only` post-review).
6. Forged `proposal_consumed_thss=False` on a THSS-derived proposal.
7. Cross-profile snapshot injection (referencing patient A's snapshot for patient B).
8. Cross-actor coordinate substitution (swapping unprivileged actor ID into privileged slot).
9. Purpose/task laundering (generating under `RESEARCH` and committing under `TREATMENT`).
10. Direct bypass injection via non-governed raw mutation endpoints.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class LaunderingTemplate(StrEnum):
    """The 10 canonical negative downgrade/laundering attack templates for E03."""

    TEMPLATE_1_MODEL_DOWNGRADE_BASE_ONLY = "template_1_model_downgrade_base_only"
    TEMPLATE_2_HUMAN_REVIEW_DROP_BINDING = "template_2_human_review_drop_binding"
    TEMPLATE_3_LINEAGE_PARENT_SUBSTITUTION = "template_3_lineage_parent_substitution"
    TEMPLATE_4_SNAPSHOT_SUBSTITUTION_REVIEW = "template_4_snapshot_substitution_review"
    TEMPLATE_5_POST_REVIEW_BINDING_MUTATION = "template_5_post_review_binding_mutation"
    TEMPLATE_6_FORGED_NON_CONSUMED_THSS = "template_6_forged_non_consumed_thss"
    TEMPLATE_7_CROSS_PROFILE_SNAPSHOT_INJECTION = (
        "template_7_cross_profile_snapshot_injection"
    )
    TEMPLATE_8_CROSS_ACTOR_COORDINATE_SUBSTITUTION = (
        "template_8_cross_actor_coordinate_substitution"
    )
    TEMPLATE_9_PURPOSE_TASK_LAUNDERING = "template_9_purpose_task_laundering"
    TEMPLATE_10_DIRECT_BYPASS_RAW_MUTATION = "template_10_direct_bypass_raw_mutation"


TEMPLATE_DESCRIPTIONS: dict[LaunderingTemplate, str] = {
    LaunderingTemplate.TEMPLATE_1_MODEL_DOWNGRADE_BASE_ONLY: (
        "Snapshot-bound model proposal downgraded to base_version_only at submission"
    ),
    LaunderingTemplate.TEMPLATE_2_HUMAN_REVIEW_DROP_BINDING: (
        "Human-reviewed proposal dropping parent's inference_context_binding_id"
    ),
    LaunderingTemplate.TEMPLATE_3_LINEAGE_PARENT_SUBSTITUTION: (
        "Lineage parent substitution pointing to a different benign proposal"
    ),
    LaunderingTemplate.TEMPLATE_4_SNAPSHOT_SUBSTITUTION_REVIEW: (
        "Snapshot ID or manifest digest substitution during clinician review"
    ),
    LaunderingTemplate.TEMPLATE_5_POST_REVIEW_BINDING_MUTATION: (
        "Binding-mode mutation (snapshot_bound altered to base_version_only post-review)"
    ),
    LaunderingTemplate.TEMPLATE_6_FORGED_NON_CONSUMED_THSS: (
        "Forged proposal_consumed_thss=False on a THSS-derived proposal"
    ),
    LaunderingTemplate.TEMPLATE_7_CROSS_PROFILE_SNAPSHOT_INJECTION: (
        "Cross-profile snapshot injection referencing patient A's snapshot for patient B"
    ),
    LaunderingTemplate.TEMPLATE_8_CROSS_ACTOR_COORDINATE_SUBSTITUTION: (
        "Cross-actor coordinate substitution swapping unprivileged actor into privileged slot"
    ),
    LaunderingTemplate.TEMPLATE_9_PURPOSE_TASK_LAUNDERING: (
        "Purpose/task laundering generating under RESEARCH and committing under TREATMENT"
    ),
    LaunderingTemplate.TEMPLATE_10_DIRECT_BYPASS_RAW_MUTATION: (
        "Direct bypass injection via non-governed raw mutation endpoints"
    ),
}

DOMAINS: tuple[str, ...] = ("medications", "allergies", "conditions", "observations")
TASKS: tuple[str, ...] = (
    "dosage_adjustment",
    "ddi_mitigation",
    "contraindication_audit",
    "allergy_inactivation",
    "condition_status_update",
    "vital_monitoring",
    "care_plan_step",
    "lab_triage",
    "adverse_event_record",
)


@dataclass(frozen=True)
class LaunderingSchedule:
    """A concrete executable test schedule for E03 anti-laundering assurance."""

    schedule_id: str
    template: LaunderingTemplate | None
    template_name: str
    is_negative: bool
    domain: str
    task: str
    purpose: str
    actor_role: str
    review_role: str
    mutation_payload: dict[str, Any]
    expected_rejection: bool
    expected_invariant_error: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "template": self.template.value if self.template else None,
            "template_name": self.template_name,
            "is_negative": self.is_negative,
            "domain": self.domain,
            "task": self.task,
            "purpose": self.purpose,
            "actor_role": self.actor_role,
            "review_role": self.review_role,
            "mutation_payload": self.mutation_payload,
            "expected_rejection": self.expected_rejection,
            "expected_invariant_error": self.expected_invariant_error,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LaunderingSchedule:
        template_val = data.get("template")
        template = LaunderingTemplate(template_val) if template_val else None
        return cls(
            schedule_id=data["schedule_id"],
            template=template,
            template_name=data["template_name"],
            is_negative=data["is_negative"],
            domain=data["domain"],
            task=data["task"],
            purpose=data["purpose"],
            actor_role=data["actor_role"],
            review_role=data["review_role"],
            mutation_payload=data.get("mutation_payload", {}),
            expected_rejection=data["expected_rejection"],
            expected_invariant_error=data["expected_invariant_error"],
            description=data["description"],
            metadata=data.get("metadata", {}),
        )


def _generate_template_1_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 1: Snapshot-bound model proposal downgraded to base_version_only at submission."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_1_MODEL_DOWNGRADE_BASE_ONLY
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        actor_role = "clinician" if i % 2 == 0 else "owner"
        mutation_mode = (
            "base_version_only_param" if i % 3 == 0 else (
                "propose_base_gateway_call" if i % 3 == 1 else "strip_snapshot_binding"
            )
        )
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T01-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="self_care" if actor_role == "owner" else "care_management",
                actor_role=actor_role,
                review_role="clinician",
                mutation_payload={
                    "mutation_mode": mutation_mode,
                    "target_binding_mode": "base_version_only",
                    "strip_snapshot_fields": True,
                    "origin": "model",
                },
                expected_rejection=True,
                expected_invariant_error="commitment_base_model_forbidden",
                description=(
                    f"Model proposal in domain '{domain}' for task '{task}' attempts "
                    f"to downgrade binding mode to base_version_only via {mutation_mode}."
                ),
            )
        )
    return schedules


def _generate_template_2_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 2: Human-reviewed proposal dropping parent's inference_context_binding_id."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_2_HUMAN_REVIEW_DROP_BINDING
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        review_role = "clinician" if i % 3 != 0 else "owner"
        mutation_mode = "set_binding_id_none" if i % 2 == 0 else "strip_binding_pre_commit"
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T02-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="care_management" if review_role == "clinician" else "self_care",
                actor_role="model",
                review_role=review_role,
                mutation_payload={
                    "mutation_mode": mutation_mode,
                    "tamper_binding_id_to": None,
                    "action_stage": "post_human_review",
                },
                expected_rejection=True,
                expected_invariant_error="commitment_lineage_binding_missing",
                description=(
                    f"Human reviewer ({review_role}) reviews model proposal for '{task}' "
                    f"in '{domain}' but drops inference_context_binding_id before commit."
                ),
            )
        )
    return schedules


def _generate_template_3_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 3: Lineage parent substitution (pointing to a different benign proposal)."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_3_LINEAGE_PARENT_SUBSTITUTION
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        substitution_target = (
            "unrelated_commitment_proposal"
            if i % 3 == 0
            else ("foreign_state_proposal" if i % 3 == 1 else "forged_parent_uuid")
        )
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T03-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="care_management",
                actor_role="model",
                review_role="clinician",
                mutation_payload={
                    "substitution_target": substitution_target,
                    "target_commitment_domain": domain,
                },
                expected_rejection=True,
                expected_invariant_error="commitment_lineage_binding_mismatch",
                description=(
                    f"Reviewed proposal for '{domain}:{task}' substitutes parent lineage "
                    f"pointer with {substitution_target}."
                ),
            )
        )
    return schedules


def _generate_template_4_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 4: Snapshot ID substitution during clinician review."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_4_SNAPSHOT_SUBSTITUTION_REVIEW
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        swap_field = (
            "source_snapshot_id"
            if i % 3 == 0
            else ("source_snapshot_digest" if i % 3 == 1 else "both_id_and_digest")
        )
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T04-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="care_management",
                actor_role="model",
                review_role="clinician",
                mutation_payload={
                    "swap_field": swap_field,
                    "synthetic_snapshot_id": f"snap-forged-{i:04d}",
                    "synthetic_digest": f"sha256:forged-digest-{i:04d}",
                },
                expected_rejection=True,
                expected_invariant_error="commitment_lineage_snapshot_mismatch",
                description=(
                    f"Clinician review for '{domain}:{task}' substitutes {swap_field} "
                    f"away from root binding snapshot."
                ),
            )
        )
    return schedules


def _generate_template_5_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 5: Binding-mode mutation (snapshot_bound altered to base_version_only post-review)."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_5_POST_REVIEW_BINDING_MUTATION
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T05-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="care_management",
                actor_role="model",
                review_role="clinician",
                mutation_payload={
                    "mutate_column": "context_binding_mode",
                    "initial_mode": "snapshot_bound",
                    "mutated_mode": "base_version_only",
                    "tamper_stage": "pre_commit_apply",
                },
                expected_rejection=True,
                expected_invariant_error="commitment_lineage_base_only_forbidden",
                description=(
                    f"Post-review commitment proposal for '{domain}:{task}' alters "
                    f"context_binding_mode from snapshot_bound to base_version_only."
                ),
            )
        )
    return schedules


def _generate_template_6_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 6: Forged proposal_consumed_thss=False on a THSS-derived proposal."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_6_FORGED_NON_CONSUMED_THSS
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        forge_point = (
            "assertion_flag" if i % 2 == 0 else "binding_row_consumed_thss"
        )
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T06-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="self_care" if i % 2 == 0 else "care_management",
                actor_role="model",
                review_role="clinician",
                mutation_payload={
                    "forge_point": forge_point,
                    "forged_consumed_thss": False,
                    "actual_consumed_thss": True,
                },
                expected_rejection=True,
                expected_invariant_error="commitment_lineage_binding_required",
                description=(
                    f"Proposal for '{domain}:{task}' originated from THSS but sets "
                    f"consumed_thss=False at {forge_point} to evade snapshot checks."
                ),
            )
        )
    return schedules


def _generate_template_7_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 7: Cross-profile snapshot injection (referencing patient A's snapshot for patient B)."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_7_CROSS_PROFILE_SNAPSHOT_INJECTION
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        injection_target = (
            "snapshot_manifest" if i % 2 == 0 else "inference_context_binding"
        )
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T07-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="care_management",
                actor_role="model",
                review_role="clinician",
                mutation_payload={
                    "injection_target": injection_target,
                    "profile_a_role": "donor_patient",
                    "profile_b_role": "target_patient",
                },
                expected_rejection=True,
                expected_invariant_error="proposal_snapshot_scope_forbidden",
                description=(
                    f"Cross-profile injection in '{domain}:{task}': attaches patient A's "
                    f"{injection_target} to patient B's commitment proposal."
                ),
            )
        )
    return schedules


def _generate_template_8_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 8: Cross-actor coordinate substitution (swapping unprivileged actor ID into privileged slot)."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_8_CROSS_ACTOR_COORDINATE_SUBSTITUTION
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        unprivileged_role = "caregiver" if i % 2 == 0 else "owner"
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T08-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="care_management",
                actor_role="model",
                review_role=unprivileged_role,
                mutation_payload={
                    "actor_role_used": unprivileged_role,
                    "required_authority": "clinician",
                    "spoofed_field": "review_actor_role",
                },
                expected_rejection=True,
                expected_invariant_error="commitment_review_authority_required",
                description=(
                    f"Unprivileged actor ({unprivileged_role}) attempts to review/commit "
                    f"clinical commitment for '{domain}:{task}' requiring clinician role."
                ),
            )
        )
    return schedules


def _generate_template_9_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 9: Purpose/task laundering (generating under RESEARCH and committing under TREATMENT)."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_9_PURPOSE_TASK_LAUNDERING
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        origin_purpose = "research" if i % 2 == 0 else "analytics"
        commit_purpose = "self_care" if i % 2 == 0 else "care_management"
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T09-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose=commit_purpose,
                actor_role="model",
                review_role="clinician",
                mutation_payload={
                    "origin_purpose": origin_purpose,
                    "commit_purpose": commit_purpose,
                    "cross_purpose_laundering": True,
                },
                expected_rejection=True,
                expected_invariant_error="commitment_proposal_scope_mismatch",
                description=(
                    f"Snapshot compiled under purpose '{origin_purpose}' but proposal "
                    f"committed under clinical purpose '{commit_purpose}' for '{domain}:{task}'."
                ),
            )
        )
    return schedules


def _generate_template_10_schedules(count: int = 18) -> list[LaunderingSchedule]:
    """Template 10: Direct bypass injection via non-governed raw mutation endpoints."""
    schedules: list[LaunderingSchedule] = []
    template = LaunderingTemplate.TEMPLATE_10_DIRECT_BYPASS_RAW_MUTATION
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        bypass_endpoint = (
            "direct_model_commit_call"
            if i % 3 == 0
            else ("direct_generic_assertion_write" if i % 3 == 1 else "unreviewed_proposal_apply")
        )
        schedules.append(
            LaunderingSchedule(
                schedule_id=f"E03-T10-{i + 1:02d}",
                template=template,
                template_name=template.value,
                is_negative=True,
                domain=domain,
                task=task,
                purpose="care_management",
                actor_role="model",
                review_role="none",
                mutation_payload={
                    "bypass_endpoint": bypass_endpoint,
                    "skip_human_review": True,
                    "raw_commit_origin": "model",
                },
                expected_rejection=True,
                expected_invariant_error="model_cannot_commit_commitment",
                description=(
                    f"Direct bypass attempt via '{bypass_endpoint}' attempting raw "
                    f"model commit for '{domain}:{task}' without human review."
                ),
            )
        )
    return schedules


def generate_negative_schedules(per_template_count: int = 18) -> list[LaunderingSchedule]:
    """Generate all negative laundering test schedules across 10 templates.

    Default: 18 schedules/template * 10 templates = 180 negative schedules (>=160 required).
    """
    schedules: list[LaunderingSchedule] = []
    schedules.extend(_generate_template_1_schedules(per_template_count))
    schedules.extend(_generate_template_2_schedules(per_template_count))
    schedules.extend(_generate_template_3_schedules(per_template_count))
    schedules.extend(_generate_template_4_schedules(per_template_count))
    schedules.extend(_generate_template_5_schedules(per_template_count))
    schedules.extend(_generate_template_6_schedules(per_template_count))
    schedules.extend(_generate_template_7_schedules(per_template_count))
    schedules.extend(_generate_template_8_schedules(per_template_count))
    schedules.extend(_generate_template_9_schedules(per_template_count))
    schedules.extend(_generate_template_10_schedules(per_template_count))
    return schedules


def generate_positive_controls(count: int = 36) -> list[LaunderingSchedule]:
    """Generate valid positive control review chains (>=32 required).

    These chains execute complete valid workflows:
    1. THSS snapshot compiled.
    2. Inference context binding created.
    3. Snapshot-bound model proposal created.
    4. Clinician/owner reviews model proposal, preserving binding ID and lineage.
    5. Commitment transition applied with valid provenance.
    """
    controls: list[LaunderingSchedule] = []
    transitions = ("OPEN", "ACTIVE", "RESOLVED", "CANCELLED")
    for i in range(count):
        domain = DOMAINS[i % len(DOMAINS)]
        task = TASKS[i % len(TASKS)]
        transition = transitions[i % len(transitions)]
        review_role = "clinician" if i % 2 == 0 else "owner"
        purpose = "care_management" if review_role == "clinician" else "self_care"
        controls.append(
            LaunderingSchedule(
                schedule_id=f"E03-CTRL-{i + 1:02d}",
                template=None,
                template_name="positive_control_review_chain",
                is_negative=False,
                domain=domain,
                task=task,
                purpose=purpose,
                actor_role="model",
                review_role=review_role,
                mutation_payload={
                    "valid_control_chain": True,
                    "target_transition": transition,
                    "preserves_root_lineage": True,
                    "preserves_inference_binding": True,
                },
                expected_rejection=False,
                expected_invariant_error="",
                description=(
                    f"Valid positive control review chain in '{domain}' for '{task}' "
                    f"transitioning to '{transition}' reviewed by '{review_role}'."
                ),
            )
        )
    return controls


def generate_all_schedules(
    negative_per_template: int = 18, control_count: int = 36
) -> list[LaunderingSchedule]:
    """Generate complete suite of negative mutation schedules + positive controls."""
    all_schedules = generate_negative_schedules(negative_per_template)
    all_schedules.extend(generate_positive_controls(control_count))
    return all_schedules


def export_schedules_json(
    path: Path | str, negative_per_template: int = 18, control_count: int = 36
) -> list[dict[str, Any]]:
    """Export generated schedules to JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    schedules = generate_all_schedules(negative_per_template, control_count)
    raw = [s.to_dict() for s in schedules]
    with p.open("w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
    return raw


def load_schedules_json(path: Path | str) -> list[LaunderingSchedule]:
    """Load schedules from JSON file."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [LaunderingSchedule.from_dict(item) for item in raw]
