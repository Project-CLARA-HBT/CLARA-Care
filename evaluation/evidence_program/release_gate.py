"""Fail-closed release gate for any future headline evidence claim."""

from __future__ import annotations

from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

REQUIRED = frozenset(
    {
        "status",
        "release_id",
        "run_id",
        "code_revision",
        "protocol_sha256",
        "external_cohort_attested",
        "independent_adjudication_attested",
        "two_model_family_utility_attested",
        "real_boundary_adversarial_attested",
        "postgres_fullstack_attested",
        "approved_by",
        "approved_at",
    }
)


def validate(path: Path) -> None:
    """Require a frozen, independently approved, end-to-end release record."""

    value = load_frozen_json(path)
    missing = REQUIRED.difference(value)
    if missing:
        raise FreezeError("missing_headline_release_fields:" + ",".join(sorted(missing)))
    if value["status"] != "approved":
        raise FreezeError("headline_release_not_approved")
    if not all(
        value[field]
        for field in (
            "external_cohort_attested",
            "independent_adjudication_attested",
            "two_model_family_utility_attested",
            "real_boundary_adversarial_attested",
            "postgres_fullstack_attested",
            "approved_by",
            "approved_at",
        )
    ):
        raise FreezeError("headline_release_evidence_or_approval_missing")
