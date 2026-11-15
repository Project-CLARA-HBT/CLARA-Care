"""CLARA-Care 2027 venue study-schema builder.

Purpose
-------
Generate each venue's ``study.schema.json`` from the shared case contract plus
venue-specific fields, so all nine venues share one audited base while adding
their own unit/observer/family/decision/provenance/authority fields. Silent
nulls are disallowed by construction (every venue field has an explicit type and
a non-empty ``required`` list).

Allowed input
-------------
A venue id and the shared case schema.

Failure semantics
-----------------
Raises ``VenueSchemaError`` with a stable reason code for unknown venues or a
missing shared schema. Generated schemas are deterministic.

Version
-------
``VENUE_SCHEMA_VERSION = "1.0.0"``
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

VENUE_SCHEMA_VERSION = "1.0.0"

VENUES: tuple[str, ...] = (
    "compsac",
    "popets",
    "aime",
    "ifip_sec",
    "sacmat",
    "acns",
    "dsn",
    "dimva",
    "pst",
)

# Venue-specific additions on top of the shared case contract.
VENUE_UNIT_KIND: dict[str, str] = {
    "compsac": "independent_logical_schedule",
    "popets": "revocation_episode",
    "aime": "vignette_pair",
    "ifip_sec": "authorized_request_chain",
    "sacmat": "delegated_consent_case",
    "acns": "evidence_record",
    "dsn": "crash_recovery_episode",
    "dimva": "probing_campaign",
    "pst": "audit_case",
}

VENUE_OBSERVER: dict[str, str] = {
    "compsac": "transaction_history_checker",
    "popets": "re_disclosure_observer",
    "aime": "blinded_clinician",
    "ifip_sec": "replay_observer",
    "sacmat": "policy_engine_differential",
    "acns": "evidence_boundary_auditor",
    "dsn": "crash_injector",
    "dimva": "telemetry_observer",
    "pst": "forensic_reconstructor",
}


class VenueSchemaError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


def build_venue_schema(venue: str, shared_case_schema: dict) -> dict:
    """Return a deterministic venue study schema derived from the shared case."""

    if venue not in VENUES:
        raise VenueSchemaError("UNKNOWN_VENUE", f"unknown venue {venue!r}")
    if not isinstance(shared_case_schema, dict) or "properties" not in shared_case_schema:
        raise VenueSchemaError("BAD_SHARED_SCHEMA", "shared case schema missing properties")

    schema = copy.deepcopy(shared_case_schema)
    schema["$id"] = f"https://clara.care/venue2027/{venue}/study.schema.json"
    schema["title"] = f"CLARA-Care 2027 {venue} study record (v{VENUE_SCHEMA_VERSION})"
    schema["description"] = (
        "Venue-specific study record extending the shared case contract. "
        "Venue fields are required and typed; silent nulls are not permitted."
    )

    props = schema["properties"]
    props["venue"] = {"const": venue}
    props["venue_unit_kind"] = {
        "const": VENUE_UNIT_KIND[venue],
        "description": (
            "Venue-specific unit description. The shared 'unit_kind' enum stays "
            "authoritative for clustering; this field records the venue's own label."
        ),
    }
    props["observer"] = {
        "type": "string",
        "enum": [VENUE_OBSERVER[venue]],
        "description": "The independent observer/adjudicator for this venue.",
    }
    props["case_family"] = {
        "type": "string",
        "minLength": 1,
        "description": "Attack/benefit family this record belongs to.",
    }
    props["expected_decision"] = {
        "type": "string",
        "enum": ["ADMIT", "REJECT", "INDETERMINATE", "NOT_APPLICABLE"],
    }
    props["observed_decision"] = {
        "type": "string",
        "enum": ["ADMIT", "REJECT", "INDETERMINATE", "NOT_RUN_EXTERNAL", "EXECUTION_ERROR", "TIMEOUT"],
    }
    props["decision_agreement"] = {
        "type": "boolean",
        "description": "Whether observed matches expected; computed, not asserted.",
    }
    props["synthetic_provenance"] = {
        "type": "object",
        "required": ["generator_id", "generator_version", "seed"],
        "additionalProperties": False,
        "properties": {
            "generator_id": {"type": "string", "minLength": 1},
            "generator_version": {"type": "string", "minLength": 1},
            "seed": {"type": "integer"},
        },
    }
    props["source_authority"] = {
        "type": "string",
        "enum": ["SYNTHETIC_RESEARCH_ONLY"],
        "description": "Only synthetic research authority is permitted.",
    }

    required = list(schema.get("required", []))
    for field in (
        "venue",
        "venue_unit_kind",
        "observer",
        "case_family",
        "expected_decision",
        "observed_decision",
        "decision_agreement",
        "synthetic_provenance",
        "source_authority",
    ):
        if field not in required:
            required.append(field)
    schema["required"] = required
    schema["additionalProperties"] = False
    return schema


def write_venue_schema(venue: str, repo: str | Path) -> Path:
    root = Path(repo)
    shared = json.loads(
        (root / "research/venue2027/_shared/schemas/case.v1.schema.json").read_text()
    )
    schema = build_venue_schema(venue, shared)
    out = root / f"research/venue2027/{venue}/protocols/study.schema.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    return out
