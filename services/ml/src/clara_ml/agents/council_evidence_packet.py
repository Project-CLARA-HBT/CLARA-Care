"""Bounded evidence-packet boundary for the Council shadow specialists.

Council's released recommendation is deterministic and must never depend on
retrieval.  This module is deliberately narrower: it accepts a *server-created*
retrieval snapshot only as opaque evidence identifiers plus controlled source
categories for the optional, model-registry-governed shadow path.  It rejects
text, URLs, titles, prompts, scores and unknown tools so an upstream retrieval
record cannot become an instruction channel for a specialist model.

The packet is not clinical evidence content.  Shadow specialists may expose its
availability for later human review, but can neither use it to support a
clinical finding nor make it alter Council triage, access, or persisted facts.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
)

_PACKET_VERSION = "council-evidence-packet.v1"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")

# This is a tool allowlist, not a caller-provided capability.  Adding a new
# retrieval provider requires a code review here and a matching task-contract
# review; an arbitrary ``tool`` field is rejected.
CouncilEvidenceTool = Literal["retrieval_snapshot"]
ALLOWED_COUNCIL_EVIDENCE_TOOLS = frozenset({"retrieval_snapshot"})
CouncilEvidenceCategory = Literal[
    "clinical_guideline",
    "systematic_review",
    "randomized_trial",
    "observational_study",
    "regulatory_label",
    "public_health_guidance",
]


class _EvidenceReference(BaseModel):
    """An opaque, reviewable reference inside an approved retrieval snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_id: StrictStr
    category: CouncilEvidenceCategory

    @field_validator("evidence_id")
    @classmethod
    def _stable_id(cls, value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise ValueError("invalid evidence_id")
        return value


class _EvidenceSnapshotInput(BaseModel):
    """Strict ingress contract for a server-produced retrieval snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool: CouncilEvidenceTool
    retrieval_snapshot_id: StrictStr
    evidence: list[_EvidenceReference] = Field(min_length=1, max_length=12)

    @field_validator("retrieval_snapshot_id")
    @classmethod
    def _snapshot_id(cls, value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise ValueError("invalid retrieval_snapshot_id")
        return value


def validated_council_evidence_packet(value: object) -> dict[str, Any] | None:
    """Return the only safe specialist-facing representation, or ``None``.

    The strict model rejects extras rather than silently accepting a retrieval
    ``snippet``/``url``/``prompt`` field.  De-duplication gives stable, bounded
    output even when an upstream retrieval source repeats an identifier.
    """

    if not isinstance(value, Mapping):
        return None
    try:
        parsed = _EvidenceSnapshotInput.model_validate(dict(value))
    except ValidationError:
        return None
    if parsed.tool not in ALLOWED_COUNCIL_EVIDENCE_TOOLS:
        return None

    seen: set[str] = set()
    evidence: list[dict[str, str]] = []
    for item in parsed.evidence:
        if item.evidence_id in seen:
            continue
        seen.add(item.evidence_id)
        evidence.append({"evidence_id": item.evidence_id, "category": item.category})

    if not evidence:
        return None
    return {
        "packet_version": _PACKET_VERSION,
        "tool": parsed.tool,
        "retrieval_snapshot_id": parsed.retrieval_snapshot_id,
        "evidence": evidence,
    }


def public_evidence_packet_summary(packet: dict[str, Any] | None) -> dict[str, Any]:
    """Return the non-clinical audit projection attached to shadow output."""

    if not isinstance(packet, dict):
        return {"status": "not_supplied", "evidence_count": 0, "categories": []}
    items = packet.get("evidence")
    if not isinstance(items, list):
        return {"status": "rejected", "evidence_count": 0, "categories": []}
    categories = sorted(
        {
            item.get("category")
            for item in items
            if isinstance(item, dict) and isinstance(item.get("category"), str)
        }
    )
    return {
        "status": "validated",
        "packet_version": packet.get("packet_version"),
        "tool": packet.get("tool"),
        "retrieval_snapshot_id": packet.get("retrieval_snapshot_id"),
        "evidence_count": len(items),
        "categories": categories,
        "release_effect": "none_shadow_only",
    }
