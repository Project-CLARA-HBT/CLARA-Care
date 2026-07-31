"""Rule-first, revision-linked LifeMap review findings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Mapping

FindingKind = Literal["duplicate", "contradiction", "missingness", "model_proposal"]


@dataclass(frozen=True)
class ReviewFact:
    revision_id: str
    field_key: str
    value: Any
    occurred_at: datetime
    truth_state: str


@dataclass(frozen=True)
class ReviewFinding:
    kind: FindingKind
    revision_ids: tuple[str, ...]
    field_key: str
    reason_code: str
    proposal_source: Literal["rule", "nli", "llm"]
    requires_human_resolution: bool = True
    rule_version: str = "lifemap-review-rules-v1"

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "revision_ids": list(self.revision_ids),
            "field_key": self.field_key,
            "reason_code": self.reason_code,
            "proposal_source": self.proposal_source,
            "requires_human_resolution": True,
            "rule_version": self.rule_version,
        }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def rule_first_findings(
    facts: tuple[ReviewFact, ...],
    *,
    required_fields: frozenset[str] = frozenset(),
    duplicate_window: timedelta = timedelta(hours=24),
) -> tuple[ReviewFinding, ...]:
    active = tuple(
        fact
        for fact in facts
        if fact.truth_state not in {"invalidated", "entered_in_error", "superseded"}
    )
    findings: list[ReviewFinding] = []
    present = {fact.field_key for fact in active if fact.value not in (None, "", [])}
    for field in sorted(required_fields - present):
        findings.append(
            ReviewFinding(
                kind="missingness",
                revision_ids=(),
                field_key=field,
                reason_code="required_field_missing",
                proposal_source="rule",
            )
        )
    ordered = sorted(active, key=lambda fact: (fact.field_key, fact.occurred_at, fact.revision_id))
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            if right.field_key != left.field_key:
                break
            if right.occurred_at - left.occurred_at > duplicate_window:
                break
            refs = tuple(sorted({left.revision_id, right.revision_id}))
            if _canonical(left.value) == _canonical(right.value):
                findings.append(
                    ReviewFinding(
                        kind="duplicate",
                        revision_ids=refs,
                        field_key=left.field_key,
                        reason_code="same_field_value_within_window",
                        proposal_source="rule",
                    )
                )
            else:
                findings.append(
                    ReviewFinding(
                        kind="contradiction",
                        revision_ids=refs,
                        field_key=left.field_key,
                        reason_code="different_field_value_within_window",
                        proposal_source="rule",
                    )
                )
    unique = {
        (finding.kind, finding.revision_ids, finding.field_key, finding.reason_code): finding
        for finding in findings
    }
    return tuple(unique[key] for key in sorted(unique))


def validate_model_proposals(
    proposals: Any,
    *,
    authorized_revision_ids: frozenset[str],
    authorized_revision_fields: Mapping[str, str] | None = None,
    max_proposals: int = 20,
) -> tuple[ReviewFinding, ...]:
    """Accept bounded NLI/LLM proposals as review-only, never truth actions."""

    if not isinstance(proposals, list) or len(proposals) > max_proposals:
        return ()
    accepted: list[ReviewFinding] = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        source = proposal.get("source")
        refs = proposal.get("revision_ids")
        if source not in {"nli", "llm"} or not isinstance(refs, list):
            continue
        clean_refs = tuple(sorted({str(ref) for ref in refs if str(ref)}))
        if (
            len(clean_refs) != 2
            or not set(clean_refs) <= authorized_revision_ids
        ):
            continue
        field = proposal.get("field_key")
        if not isinstance(field, str) or not field or len(field) > 64:
            continue
        relation = proposal.get("relation")
        if relation not in {"possible_duplicate", "possible_conflict"}:
            continue
        if authorized_revision_fields is not None and any(
            authorized_revision_fields.get(ref) != field for ref in clean_refs
        ):
            continue
        accepted.append(
            ReviewFinding(
                kind="model_proposal",
                revision_ids=clean_refs,
                field_key=field,
                reason_code=str(relation),
                proposal_source=source,
            )
        )
    unique = {
        (finding.revision_ids, finding.field_key): finding
        for finding in accepted
    }
    return tuple(unique[key] for key in sorted(unique))
