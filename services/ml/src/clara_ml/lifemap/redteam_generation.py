"""Governed synthetic red-team generation and human-review contracts.

The generator is deliberately provider-neutral. Callers may connect an approved
LLM, but can pass only bounded synthetic scenario seeds. Generated candidates
remain separate from held-out and real-world outcome evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, replace
from typing import Any, Literal

Locale = Literal["vi", "en"]
ReviewDecision = Literal["accepted", "rejected"]
ExpectedBehavior = Literal[
    "abstain",
    "emergency_escalate",
    "cite_sources",
    "ask_clarification",
    "reject_injection",
    "correct_temporal_order",
    "preserve_profile_isolation",
    "draft_only",
    "surface_conflict",
]
Generator = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

ALLOWED_DIMENSIONS = frozenset(
    {
        "longitudinal",
        "temporal",
        "multimodal",
        "correction",
        "contradiction",
        "missingness",
        "wearable_shift",
        "ood",
        "adaptive_policy",
        "prompt_injection",
        "profile_isolation",
        "emergency",
    }
)
ALLOWED_EXPECTED_BEHAVIORS = frozenset(
    {
        "abstain",
        "emergency_escalate",
        "cite_sources",
        "ask_clarification",
        "reject_injection",
        "correct_temporal_order",
        "preserve_profile_isolation",
        "draft_only",
        "surface_conflict",
    }
)
ALLOWED_RISK_TAGS = frozenset(
    {
        "unsupported_claim",
        "unsafe_action",
        "missing_citation",
        "cross_profile_leak",
        "temporal_error",
        "prompt_injection",
        "automation_bias",
        "overconfident_language",
        "emergency_delay",
    }
)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\s.-]?){8,15}(?!\d)")
_SAFE_REF = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:@/-]{2,127}")


class RedTeamContractError(ValueError):
    """A generation, review, or freezing invariant failed."""


@dataclass(frozen=True)
class ScenarioSeed:
    seed_id: str
    locale: Locale
    dimension: str
    objective: str


@dataclass(frozen=True)
class RedTeamCandidate:
    candidate_id: str
    seed_id: str
    locale: Locale
    dimension: str
    prompt: str
    expected_behaviors: tuple[ExpectedBehavior, ...]
    risk_tags: tuple[str, ...]
    source_model_ref: str
    template_sha256: str
    review_status: Literal["pending", "accepted", "rejected"] = "pending"
    reviewer_ref: str | None = None
    review_label: str | None = None
    synthetic: bool = True
    held_out: bool = False
    outcome_estimate_eligible: bool = False


@dataclass(frozen=True)
class RedTeamSuite:
    suite_version: str
    suite_sha256: str
    source_model_ref: str
    candidates: tuple[RedTeamCandidate, ...]
    synthetic_only: bool = True
    held_out: bool = False
    outcome_estimate_eligible: bool = False
    eligible_for_promotion: bool = False


def _normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _digest(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_bounded_text(value: Any, *, field: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or "\x00" in text:
        raise RedTeamContractError(f"{field}_invalid")
    return text


def _validate_seed(seed: ScenarioSeed) -> None:
    if (
        not _SAFE_REF.fullmatch(seed.seed_id)
        or seed.locale not in {"vi", "en"}
        or seed.dimension not in ALLOWED_DIMENSIONS
    ):
        raise RedTeamContractError("scenario_seed_invalid")
    _validate_bounded_text(seed.objective, field="scenario_objective", maximum=500)
    if _EMAIL.search(seed.objective) or _PHONE.search(seed.objective):
        raise RedTeamContractError("scenario_seed_possible_pii")


def _candidate_from_output(
    *,
    seed: ScenarioSeed,
    raw: dict[str, Any],
    source_model_ref: str,
    template_sha256: str,
) -> RedTeamCandidate:
    if set(raw) != {"prompt", "expected_behaviors", "risk_tags"}:
        raise RedTeamContractError("generator_output_schema_invalid")
    prompt = _validate_bounded_text(
        raw["prompt"], field="candidate_prompt", maximum=2_000
    )
    if _EMAIL.search(prompt) or _PHONE.search(prompt):
        raise RedTeamContractError("candidate_possible_pii")
    expected_raw = raw["expected_behaviors"]
    risks_raw = raw["risk_tags"]
    if (
        not isinstance(expected_raw, list)
        or not expected_raw
        or any(item not in ALLOWED_EXPECTED_BEHAVIORS for item in expected_raw)
        or not isinstance(risks_raw, list)
        or not risks_raw
        or any(item not in ALLOWED_RISK_TAGS for item in risks_raw)
    ):
        raise RedTeamContractError("generator_labels_invalid")
    expected = tuple(sorted(set(expected_raw)))
    risks = tuple(sorted({str(item) for item in risks_raw}))
    candidate_id = f"rt-{_digest([seed.seed_id, _normalized(prompt)])[:24]}"
    return RedTeamCandidate(
        candidate_id=candidate_id,
        seed_id=seed.seed_id,
        locale=seed.locale,
        dimension=seed.dimension,
        prompt=prompt,
        expected_behaviors=expected,  # type: ignore[arg-type]
        risk_tags=risks,
        source_model_ref=source_model_ref,
        template_sha256=template_sha256,
    )


async def generate_candidates(
    *,
    seeds: tuple[ScenarioSeed, ...],
    generator: Generator,
    source_model_ref: str,
    prompt_template: str,
) -> tuple[RedTeamCandidate, ...]:
    """Generate pending synthetic candidates from bounded, content-free seeds."""

    if (
        not seeds
        or len({seed.seed_id for seed in seeds}) != len(seeds)
        or not _SAFE_REF.fullmatch(source_model_ref)
    ):
        raise RedTeamContractError("generation_manifest_invalid")
    template = _validate_bounded_text(
        prompt_template, field="prompt_template", maximum=4_000
    )
    template_sha256 = hashlib.sha256(template.encode()).hexdigest()
    candidates: list[RedTeamCandidate] = []
    fingerprints: set[str] = set()
    for seed in seeds:
        _validate_seed(seed)
        raw = await generator(
            {
                "instruction": template,
                "seed": {
                    "seed_id": seed.seed_id,
                    "locale": seed.locale,
                    "dimension": seed.dimension,
                    "objective": seed.objective,
                    "synthetic_only": True,
                },
                "output_schema": {
                    "prompt": "string",
                    "expected_behaviors": sorted(ALLOWED_EXPECTED_BEHAVIORS),
                    "risk_tags": sorted(ALLOWED_RISK_TAGS),
                },
                "prohibited_inputs": [
                    "production_records",
                    "profile_identifiers",
                    "real_personal_data",
                    "held_out_cases",
                ],
            }
        )
        if not isinstance(raw, dict):
            raise RedTeamContractError("generator_output_schema_invalid")
        candidate = _candidate_from_output(
            seed=seed,
            raw=raw,
            source_model_ref=source_model_ref,
            template_sha256=template_sha256,
        )
        fingerprint = _digest(
            [candidate.locale, candidate.dimension, _normalized(candidate.prompt)]
        )
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        candidates.append(candidate)
    if not candidates:
        raise RedTeamContractError("generation_produced_no_unique_candidates")
    return tuple(candidates)


def review_candidate(
    candidate: RedTeamCandidate,
    *,
    decision: ReviewDecision,
    reviewer_ref: str,
    review_label: str,
) -> RedTeamCandidate:
    """Apply one explicit human review decision to a pending candidate."""

    if candidate.review_status != "pending":
        raise RedTeamContractError("candidate_already_reviewed")
    if not _SAFE_REF.fullmatch(reviewer_ref) or not reviewer_ref.startswith("reviewer:"):
        raise RedTeamContractError("reviewer_ref_invalid")
    label = _validate_bounded_text(review_label, field="review_label", maximum=80)
    return replace(
        candidate,
        review_status=decision,
        reviewer_ref=reviewer_ref,
        review_label=label,
    )


def freeze_reviewed_suite(
    *,
    suite_version: str,
    source_model_ref: str,
    candidates: Iterable[RedTeamCandidate],
) -> RedTeamSuite:
    """Freeze accepted human-reviewed cases as red-team evidence only."""

    if not _SAFE_REF.fullmatch(suite_version) or not _SAFE_REF.fullmatch(
        source_model_ref
    ):
        raise RedTeamContractError("suite_identity_invalid")
    rows = tuple(candidates)
    if (
        not rows
        or any(row.review_status == "pending" for row in rows)
        or any(row.source_model_ref != source_model_ref for row in rows)
    ):
        raise RedTeamContractError("suite_review_incomplete")
    accepted = tuple(
        sorted(
            (row for row in rows if row.review_status == "accepted"),
            key=lambda row: row.candidate_id,
        )
    )
    if not accepted or len({row.candidate_id for row in accepted}) != len(accepted):
        raise RedTeamContractError("suite_candidate_identity_invalid")
    manifest = [
        {
            "candidate_id": row.candidate_id,
            "seed_id": row.seed_id,
            "locale": row.locale,
            "dimension": row.dimension,
            "prompt_sha256": hashlib.sha256(row.prompt.encode()).hexdigest(),
            "expected_behaviors": row.expected_behaviors,
            "risk_tags": row.risk_tags,
            "source_model_ref": row.source_model_ref,
            "template_sha256": row.template_sha256,
            "review_status": row.review_status,
            "reviewer_ref": row.reviewer_ref,
            "review_label": row.review_label,
            "synthetic": True,
            "held_out": False,
            "outcome_estimate_eligible": False,
        }
        for row in accepted
    ]
    return RedTeamSuite(
        suite_version=suite_version,
        suite_sha256=_digest({"suite_version": suite_version, "cases": manifest}),
        source_model_ref=source_model_ref,
        candidates=accepted,
    )
