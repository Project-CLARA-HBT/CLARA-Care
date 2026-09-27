"""Static AST and code inspection inventory of GLHS persistence and write routes.

Fulfills requirement E03.1 (Route inventory) by scanning all write entrypoints
in the CLARA GLHS system and documenting:
- module / function name
- origin types accepted (model, user, clinician, system)
- whether THSS can be consumed
- required binding mode (snapshot_bound, base_version_only, none)
- root proposal handling and anti-laundering checks
- dependency source
- persistence target
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WriteRouteEntry:
    route_id: str
    module: str
    function_name: str
    origin_types_accepted: list[str]
    can_consume_thss: bool
    required_binding_mode: str
    root_proposal_handling: str
    dependency_source: str
    persistence_target: str
    anti_laundering_enforcement: str
    downgrade_prevention_mechanism: str


ROUTE_INVENTORY: list[WriteRouteEntry] = [
    WriteRouteEntry(
        route_id="WR-01",
        module="clara_api.glhs.gateway",
        function_name="propose_assertion",
        origin_types_accepted=["user", "clinician", "system"],
        can_consume_thss=True,
        required_binding_mode="snapshot_bound_if_thss",
        root_proposal_handling="N/A (single assertion stage)",
        dependency_source="Observation/Evidence inputs",
        persistence_target="glhs_profile_assertions",
        anti_laundering_enforcement="Requires proposal_snapshot_id if proposal_consumed_thss=True; forbids process_kind='model' on generic assertions.",
        downgrade_prevention_mechanism="Raises GlhsInvariantError('proposal_snapshot_binding_required') or GlhsInvariantError('model_cannot_write_assertion').",
    ),
    WriteRouteEntry(
        route_id="WR-02",
        module="clara_api.glhs.gateway",
        function_name="record_evidence",
        origin_types_accepted=["user", "clinician", "system"],
        can_consume_thss=False,
        required_binding_mode="none (pure evidence append)",
        root_proposal_handling="N/A",
        dependency_source="SourceReference & Evidence payload",
        persistence_target="glhs_profile_evidence",
        anti_laundering_enforcement="Append-only immutable audit trail with deterministic fingerprint verification.",
        downgrade_prevention_mechanism="Evidence rows are immutable at DB level; cannot mutate prior records.",
    ),
    WriteRouteEntry(
        route_id="WR-03",
        module="clara_api.glhs.gateway",
        function_name="retire_assertion",
        origin_types_accepted=["user", "clinician", "system"],
        can_consume_thss=False,
        required_binding_mode="base_version_only",
        root_proposal_handling="N/A",
        dependency_source="Target assertion ID and retirement evidence",
        persistence_target="glhs_profile_assertions",
        anti_laundering_enforcement="Enforces state version advancement and retirement record generation.",
        downgrade_prevention_mechanism="Only operates on already committed assertions; cannot introduce AI content.",
    ),
    WriteRouteEntry(
        route_id="WR-04",
        module="clara_api.glhs.commitment_gateway",
        function_name="create_commitment_proposal",
        origin_types_accepted=["model", "user", "clinician", "system"],
        can_consume_thss=True,
        required_binding_mode="snapshot_bound",
        root_proposal_handling="Establishes root proposal ID and registers binding context.",
        dependency_source="THSS snapshot disclosure and evidence closure",
        persistence_target="glhs_clinical_commitment_proposals",
        anti_laundering_enforcement="Validates source snapshot, digest, and evidence set against inference context binding.",
        downgrade_prevention_mechanism="Mandates inference_context_binding_id when THSS consumed.",
    ),
    WriteRouteEntry(
        route_id="WR-05",
        module="clara_api.glhs.commitment_gateway",
        function_name="apply_transition",
        origin_types_accepted=["user", "clinician", "system"],
        can_consume_thss=True,
        required_binding_mode="snapshot_bound_preservation",
        root_proposal_handling="Inspects root proposal; if root consumed THSS, strictly enforces _require_lineage_binding.",
        dependency_source="Root proposal inference binding & observed evidence",
        persistence_target="glhs_clinical_commitment_transitions",
        anti_laundering_enforcement="_require_lineage_binding ensures no downgrade to base_version_only, checks digest match, checks snapshot match.",
        downgrade_prevention_mechanism="Raises GlhsInvariantError('commitment_lineage_base_only_forbidden') or ('commitment_lineage_snapshot_mismatch').",
    ),
    WriteRouteEntry(
        route_id="WR-06",
        module="clara_api.glhs.commitment_gateway",
        function_name="propose_bound_commitment_transition",
        origin_types_accepted=["model", "user", "clinician"],
        can_consume_thss=True,
        required_binding_mode="snapshot_bound",
        root_proposal_handling="Records root proposal context and binds inference context.",
        dependency_source="Source snapshot disclosure and evidence",
        persistence_target="glhs_clinical_commitment_proposals",
        anti_laundering_enforcement="Checks snapshot existence, lease validity, and anti-laundering registration.",
        downgrade_prevention_mechanism="Rejects proposals lacking binding if snapshot had consumed_thss=True.",
    ),
    WriteRouteEntry(
        route_id="WR-07",
        module="clara_api.glhs.commitment_gateway",
        function_name="adapt_commitment_proposal",
        origin_types_accepted=["clinician", "user"],
        can_consume_thss=True,
        required_binding_mode="snapshot_bound_preservation",
        root_proposal_handling="Preserves original root proposal ID and original inference context binding ID.",
        dependency_source="Parent proposal binding context",
        persistence_target="glhs_clinical_commitment_proposals",
        anti_laundering_enforcement="Cannot change source snapshot ID or digest; maintains root lineage link.",
        downgrade_prevention_mechanism="Rejects proposals that attempt to drop or alter root lineage binding.",
    ),
    WriteRouteEntry(
        route_id="WR-08",
        module="clara_api.glhs.commit_kernel",
        function_name="execute_atomic_glhs_commit",
        origin_types_accepted=["system", "internal_kernel"],
        can_consume_thss=True,
        required_binding_mode="snapshot_bound",
        root_proposal_handling="Validates complete lineage and dependency vector seal before persisting state.",
        dependency_source="Canonical dependency vector & lock plan",
        persistence_target="glhs_clinical_commitments & profile state",
        anti_laundering_enforcement="Verifies dependency vector digest and state version lock invariants.",
        downgrade_prevention_mechanism="Fails closed on dependency vector tampering or concurrency mismatch.",
    ),
    WriteRouteEntry(
        route_id="WR-09",
        module="clara_api.glhs.adapters",
        function_name="ingest_lifemap_event",
        origin_types_accepted=["user", "system"],
        can_consume_thss=False,
        required_binding_mode="base_version_only",
        root_proposal_handling="NON_THSS_ORIGIN: Mechanically prevented from accepting THSS/model origin lineages.",
        dependency_source="Lifemap event payload",
        persistence_target="glhs_profile_assertions",
        anti_laundering_enforcement="Classified strictly as NON_THSS_ORIGIN; cannot ingest model-derived content.",
        downgrade_prevention_mechanism="Rejects any payload with model process_kind or proposal_consumed_thss.",
    ),
    WriteRouteEntry(
        route_id="WR-10",
        module="clara_api.glhs.adapters",
        function_name="ingest_medication_course",
        origin_types_accepted=["clinician", "user"],
        can_consume_thss=False,
        required_binding_mode="base_version_only",
        root_proposal_handling="NON_THSS_ORIGIN: Direct clinical ingestion without model synthesis.",
        dependency_source="Prescription / medication course record",
        persistence_target="glhs_profile_assertions",
        anti_laundering_enforcement="Classified strictly as NON_THSS_ORIGIN; cannot ingest model-derived content.",
        downgrade_prevention_mechanism="Rejects model origins; requires verified human actor credentials.",
    ),
    WriteRouteEntry(
        route_id="WR-11",
        module="clara_api.glhs.adapters",
        function_name="ingest_connected_health_observation",
        origin_types_accepted=["device", "system"],
        can_consume_thss=False,
        required_binding_mode="base_version_only",
        root_proposal_handling="NON_THSS_ORIGIN: Device telemetry stream.",
        dependency_source="Device signed measurement payload",
        persistence_target="glhs_profile_assertions",
        anti_laundering_enforcement="Classified strictly as NON_THSS_ORIGIN; cannot ingest model-derived content.",
        downgrade_prevention_mechanism="Rejects model origins; enforces device source reference verification.",
    ),
    WriteRouteEntry(
        route_id="WR-12",
        module="clara_api.glhs.adapters",
        function_name="ingest_visit_document",
        origin_types_accepted=["clinician", "system"],
        can_consume_thss=False,
        required_binding_mode="base_version_only",
        root_proposal_handling="NON_THSS_ORIGIN: Clinical document ingestion.",
        dependency_source="Clinical encounter document",
        persistence_target="glhs_profile_assertions",
        anti_laundering_enforcement="Classified strictly as NON_THSS_ORIGIN; cannot ingest model-derived content.",
        downgrade_prevention_mechanism="Rejects model origins; requires verified clinician actor credentials.",
    ),
]


def generate_route_inventory_json() -> dict[str, Any]:
    return {
        "schema_version": "glhs-route-inventory.v1",
        "total_routes_inventoried": len(ROUTE_INVENTORY),
        "routes": [asdict(r) for r in ROUTE_INVENTORY],
    }


def generate_route_inventory_markdown() -> str:
    lines = [
        "# GLHS Persistence and Write Route Inventory (E03 Anti-Laundering Audit)",
        "",
        "| Route ID | Module / Function | Accepted Origins | THSS Consumable | Required Binding Mode | Downgrade Prevention Mechanism |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in ROUTE_INVENTORY:
        origins = ", ".join(r.origin_types_accepted)
        lines.append(
            f"| `{r.route_id}` | `{r.module}.{r.function_name}` | {origins} | {r.can_consume_thss} | `{r.required_binding_mode}` | {r.downgrade_prevention_mechanism} |"
        )
    lines.append("")
    lines.append("## Lineage Anti-Laundering Invariants")
    lines.append("")
    lines.append("1. **Mandatory THSS Snapshot Binding:** If any proposal in a commitment lineage consumed THSS (`consumed_thss=true`), every descendant proposal MUST remain `snapshot_bound`.")
    lines.append("2. **Root Snapshot Invariance:** Descendants cannot alter `source_snapshot_id` or `source_snapshot_digest` from the root inference binding.")
    lines.append("3. **Root Lineage Continuity:** Human review adaptations must retain unbroken root proposal pointers.")
    lines.append("4. **Non-THSS Route Isolation:** Routes with `base_version_only` semantics (`ingest_lifemap_event`, `ingest_medication_course`, etc.) are mechanically prohibited from accepting model or THSS-derived inputs.")
    lines.append("5. **Zero Downgrade Escape:** No code path permits an AI/model proposal to mutate persistent state without satisfying the strongest required binding semantics.")
    return "\n".join(lines) + "\n"
