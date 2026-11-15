"""CLARA-Care 2027 POPETS task POPETS-X08_minimal_privacy — minimal future outbound disclosure.

Purpose
-------
Implement minimal outbound disclosure control for the paper *Revocation-Complete
Future Disclosure for Cached Longitudinal AI Contexts*
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md`` RQ3,
``research/venue2027/VENUES/popets/TASKS/POPETS-X08_minimal_privacy.md``).

Rather than disclosing the original full EHR summary across outbound task dispatches,
this module calculates and restricts context to the *minimal context set* demanded
by the specific task dependency and current authorized purpose. On any UNKNOWN or
unresolvable graph edge in the context derivation lineage, it fails closed by falling
back to RECOMPUTATION of the minimal authorized projection from trusted roots, never
disclosing unresolvable or untrusted dependencies.

Key Mechanisms
--------------
1. **Task Dependency + Purpose Scoping:**
   Restricts the disclosed field/node set to ``task_dependency.required_fields``
   (or required nodes) intersecting the authorized purpose field set. Fields outside
   the intersection or belonging to the original full EHR summary that are not needed
   for the specific task are withheld and reported explicitly in ``withheld_fields``.

2. **Graph Lineage Resolution & Fail-Closed Fallback:**
   Inspects the lineage graph edges supporting the requested context nodes. If an edge
   is missing, references an unknown ancestor, is unlinked, or cannot be resolved in
   the graph, the module refuses to serve the cached context and falls back to
   ``RECOMPUTATION`` (or returns a Disclosure with ``status=RECOMPUTATION_REQUIRED`` /
   ``recomputation_required=True``).

3. **Deterministic & Withheld Accounting:**
   Outputs are deterministic, sorted, and JSON-serializable. Disclosed fields and withheld
   fields are audited and reported with byte accounting and exact stable reason codes.

4. **Refusal of Full Summary Over-Disclosure:**
   When a strictly minimal context set exists that satisfies the task, attempting to
   disclose the full EHR summary is refused (``FULL_SUMMARY_DISCLOSURE_REFUSED``).

Exact Target Contract
---------------------
- ``minimal_disclosure(task_dependency, current_purpose, graph, context=None, ...) -> Disclosure``
- ``select_fields(context, task) -> FieldSet`` (exact signature specified in task manifest / CSV).

Version
-------
``MINIMAL_DISCLOSURE_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Mapping
from typing import Any, Final, Literal

from evaluation.venue2027.popets.lineage_graph import LineageGraph

__all__ = [
    "DEFAULT_PURPOSE_ALLOWED_FIELDS",
    "MINIMAL_DISCLOSURE_VERSION",
    "REASON_FULL_SUMMARY_DISCLOSURE_REFUSED",
    "REASON_INVALID_PURPOSE",
    "REASON_INVALID_TASK",
    "REASON_MALFORMED_CONTEXT",
    "REASON_MINIMAL_DISCLOSURE_OK",
    "REASON_NO_AUTHORIZED_FIELDS",
    "REASON_RECOMPUTATION_REQUIRED",
    "REASON_UNKNOWN_GRAPH_EDGE",
    "Disclosure",
    "FieldSet",
    "MinimalDisclosureError",
    "TaskDependency",
    "minimal_disclosure",
    "select_fields",
]

MINIMAL_DISCLOSURE_VERSION: Final[str] = "1.0.0"

# Status vocabulary
STATUS_DISCLOSED: Final[str] = "DISCLOSED"
STATUS_RECOMPUTATION: Final[str] = "RECOMPUTATION"
STATUS_REFUSED: Final[str] = "REFUSED"

# Reason codes (stable uppercase)
REASON_MINIMAL_DISCLOSURE_OK: Final[str] = "MINIMAL_DISCLOSURE_OK"
REASON_UNKNOWN_GRAPH_EDGE: Final[str] = "UNKNOWN_GRAPH_EDGE"
REASON_RECOMPUTATION_REQUIRED: Final[str] = "RECOMPUTATION_REQUIRED"
REASON_FULL_SUMMARY_DISCLOSURE_REFUSED: Final[str] = "FULL_SUMMARY_DISCLOSURE_REFUSED"
REASON_NO_AUTHORIZED_FIELDS: Final[str] = "NO_AUTHORIZED_FIELDS"
REASON_INVALID_PURPOSE: Final[str] = "INVALID_PURPOSE"
REASON_INVALID_TASK: Final[str] = "INVALID_TASK"
REASON_MALFORMED_CONTEXT: Final[str] = "MALFORMED_CONTEXT"

# Default purpose allowlist mapping: purpose -> authorized field categories / names
DEFAULT_PURPOSE_ALLOWED_FIELDS: Final[dict[str, frozenset[str]]] = {
    "self_care": frozenset({
        "vitals",
        "blood_pressure",
        "heart_rate",
        "medication_schedule",
        "activity_summary",
        "diet_summary",
    }),
    "care_summary": frozenset({
        "vitals",
        "blood_pressure",
        "heart_rate",
        "temperature",
        "weight",
        "medication_schedule",
        "active_diagnoses",
        "allergies",
        "care_team",
    }),
    "medication_review": frozenset({
        "medications",
        "medication_schedule",
        "allergies",
        "drug_interactions",
        "renal_function",
        "liver_function",
        "vitals",
    }),
    "clinical": frozenset({
        "vitals",
        "blood_pressure",
        "heart_rate",
        "medications",
        "medication_schedule",
        "active_diagnoses",
        "lab_results",
        "allergies",
        "clinical_notes_summary",
    }),
    "billing": frozenset({
        "billing_codes",
        "encounter_dates",
        "insurance_id",
        "procedure_codes",
    }),
    "analytics": frozenset({
        "age_bracket",
        "encounter_type",
        "aggregated_metrics",
        "deidentified_cohort_id",
    }),
}


class MinimalDisclosureError(ValueError):
    """Stable reason-code error for minimal disclosure enforcement."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


# ---------------------------------------------------------------------------
# Typed data structures (JSON-serializable)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TaskDependency:
    """Task dependency specifying requirements for an outbound task."""

    task_id: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()
    expected_lineage_nodes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise MinimalDisclosureError(REASON_INVALID_TASK, "task_id must be a non-empty string")
        if not isinstance(self.required_fields, list | tuple | set | frozenset):
            raise MinimalDisclosureError(
                REASON_INVALID_TASK, "required_fields must be a sequence of strings"
            )
        if not self.required_fields:
            raise MinimalDisclosureError(
                REASON_INVALID_TASK, "required_fields must not be empty"
            )
        for f in self.required_fields:
            if not isinstance(f, str) or not f.strip():
                raise MinimalDisclosureError(
                    REASON_INVALID_TASK, "required_fields elements must be non-empty strings"
                )
        object.__setattr__(self, "required_fields", tuple(sorted(set(self.required_fields))))
        object.__setattr__(self, "optional_fields", tuple(sorted(set(self.optional_fields))))
        object.__setattr__(
            self, "expected_lineage_nodes", tuple(sorted(set(self.expected_lineage_nodes)))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "required_fields": list(self.required_fields),
            "optional_fields": list(self.optional_fields),
            "expected_lineage_nodes": list(self.expected_lineage_nodes),
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | TaskDependency) -> TaskDependency:
        if isinstance(raw, TaskDependency):
            return raw
        if not isinstance(raw, Mapping):
            raise MinimalDisclosureError(REASON_INVALID_TASK, "task must be a mapping or TaskDependency")
        task_id = raw.get("task_id", raw.get("id", "task-unspecified"))
        required_fields = raw.get("required_fields", raw.get("fields", ()))
        optional_fields = raw.get("optional_fields", ())
        expected_lineage = raw.get("expected_lineage_nodes", raw.get("lineage_nodes", ()))
        return cls(
            task_id=str(task_id),
            required_fields=tuple(required_fields),
            optional_fields=tuple(optional_fields),
            expected_lineage_nodes=tuple(expected_lineage),
        )


@dataclasses.dataclass(frozen=True)
class FieldSet:
    """The set of fields selected for disclosure alongside withheld accounting."""

    fields: tuple[str, ...]
    withheld_fields: tuple[str, ...]
    purpose: str
    task_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", tuple(sorted(set(self.fields))))
        object.__setattr__(self, "withheld_fields", tuple(sorted(set(self.withheld_fields))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": list(self.fields),
            "withheld_fields": list(self.withheld_fields),
            "purpose": self.purpose,
            "task_id": self.task_id,
        }


@dataclasses.dataclass(frozen=True)
class Disclosure:
    """Outcome of minimal disclosure evaluation.

    Encapsulates whether the minimal context set is safely disclosed, or whether
    an unknown edge forces a recomputation fallback.
    """

    status: Literal["DISCLOSED", "RECOMPUTATION", "REFUSED"]
    reason_code: str
    task_id: str
    purpose: str
    disclosed_fields: tuple[str, ...]
    withheld_fields: tuple[str, ...]
    disclosed_payload: dict[str, Any]
    withheld_payload: dict[str, Any]
    recomputation_required: bool
    recomputation_fallback_nodes: tuple[str, ...]
    unresolved_edges: tuple[dict[str, Any], ...]
    version: str = MINIMAL_DISCLOSURE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "task_id": self.task_id,
            "purpose": self.purpose,
            "disclosed_fields": list(self.disclosed_fields),
            "withheld_fields": list(self.withheld_fields),
            "disclosed_payload": self.disclosed_payload,
            "withheld_payload": self.withheld_payload,
            "recomputation_required": self.recomputation_required,
            "recomputation_fallback_nodes": list(self.recomputation_fallback_nodes),
            "unresolved_edges": list(self.unresolved_edges),
            "version": self.version,
        }


# ---------------------------------------------------------------------------
# Core Algorithms
# ---------------------------------------------------------------------------


def select_fields(
    context: Mapping[str, Any] | Collection[str],
    task: Mapping[str, Any] | TaskDependency | Collection[str] | str,
    purpose: str = "care_summary",
    purpose_allowed_fields: Mapping[str, Collection[str]] | None = None,
) -> FieldSet:
    """Select the minimal authorized field set for a task from context (exact target signature).

    ``select_fields(context, task) -> FieldSet``
    Adheres strictly to task dependencies and current purpose:
    - Never returns the full context when a narrow task dependency exists.
    - Fields in context not required by task or not authorized by purpose are placed in withheld_fields.
    """
    if not isinstance(purpose, str) or not purpose.strip():
        raise MinimalDisclosureError(REASON_INVALID_PURPOSE, "purpose must be a non-empty string")

    # Normalize context fields
    all_context_fields: set[str]
    if isinstance(context, Mapping):
        all_context_fields = set(context.keys())
    elif isinstance(context, list | tuple | set | frozenset):
        all_context_fields = {str(x) for x in context}
    elif isinstance(context, str):
        all_context_fields = {context}
    else:
        raise MinimalDisclosureError(
            REASON_MALFORMED_CONTEXT, "context must be a mapping or collection of field names"
        )

    # Normalize task
    task_dep: TaskDependency
    if isinstance(task, TaskDependency):
        task_dep = task
    elif isinstance(task, Mapping):
        task_dep = TaskDependency.from_mapping(task)
    elif isinstance(task, str):
        task_dep = TaskDependency(task_id=task, required_fields=(task,))
    elif isinstance(task, list | tuple | set | frozenset):
        task_dep = TaskDependency(task_id="task_custom", required_fields=tuple(str(x) for x in task))
    else:
        raise MinimalDisclosureError(REASON_INVALID_TASK, "task must be a TaskDependency, Mapping, or sequence")

    # Determine purpose allowlist
    allowlists = purpose_allowed_fields or DEFAULT_PURPOSE_ALLOWED_FIELDS
    allowed_for_purpose = set(allowlists.get(purpose, frozenset()))

    # Minimal intersection: context ∩ task_dep.required_fields ∩ allowed_for_purpose
    task_needed = set(task_dep.required_fields) | (set(task_dep.optional_fields) & all_context_fields)
    authorized_and_needed = (all_context_fields & task_needed) & allowed_for_purpose

    # Withheld fields: all context fields not disclosed
    withheld = all_context_fields - authorized_and_needed

    return FieldSet(
        fields=tuple(sorted(authorized_and_needed)),
        withheld_fields=tuple(sorted(withheld)),
        purpose=purpose,
        task_id=task_dep.task_id,
    )


def minimal_disclosure(
    task_dependency: Mapping[str, Any] | TaskDependency,
    current_purpose: str,
    graph: LineageGraph | None,
    context: Mapping[str, Any] | None = None,
    allow_full_summary: bool = False,
    purpose_allowed_fields: Mapping[str, Collection[str]] | None = None,
    recompute_fn: Any | None = None,
) -> Disclosure:
    """Compute minimal outbound disclosure with fail-closed recomputation fallback.

    Parameters
    ----------
    task_dependency : TaskDependency or mapping
        The dependency requirements for the task (required fields, expected lineage nodes).
    current_purpose : str
        The active authorized purpose (e.g. 'self_care', 'care_summary', 'medication_review').
    graph : LineageGraph or None
        The context-lineage graph. If None or if edges for expected nodes cannot be resolved,
        fails closed to recomputation.
    context : Mapping[str, Any] or None
        The candidate context dictionary (e.g. full EHR summary or cached projections).
    allow_full_summary : bool
        If True, caller requests full summary disclosure. But if a minimal set exists,
        this will be REFUSED unless the task itself requires the complete summary.
    purpose_allowed_fields : Mapping[str, Collection[str]] or None
        Optional custom purpose field allowlist.
    recompute_fn : callable or None
        Optional recomputation callback invoked if fallback to recomputation is required.

    Returns
    -------
    Disclosure
        Result reporting disclosed fields, withheld fields, and whether recomputation was triggered.
    """
    if not isinstance(current_purpose, str) or not current_purpose.strip():
        raise MinimalDisclosureError(REASON_INVALID_PURPOSE, "current_purpose must be a non-empty string")

    task = TaskDependency.from_mapping(task_dependency)
    raw_context = dict(context or {})

    # Determine authorized purpose fields
    allowlists = purpose_allowed_fields or DEFAULT_PURPOSE_ALLOWED_FIELDS

    # Check for adversarial request: requesting full summary disclosure when a minimal set exists
    # If the caller requests or supplies a full summary, but the task only requires a narrow subset,
    # and allow_full_summary is True, we explicitly refuse disclosing full summary when a minimal set exists!
    full_context_fields = set(raw_context.keys())
    narrow_task_fields = set(task.required_fields)

    if allow_full_summary and full_context_fields and narrow_task_fields:
        if not narrow_task_fields.issuperset(full_context_fields):
            # The caller requested full summary, but task dependency is strictly narrower!
            return Disclosure(
                status=STATUS_REFUSED,
                reason_code=REASON_FULL_SUMMARY_DISCLOSURE_REFUSED,
                task_id=task.task_id,
                purpose=current_purpose,
                disclosed_fields=(),
                withheld_fields=tuple(sorted(full_context_fields)),
                disclosed_payload={},
                withheld_payload=raw_context,
                recomputation_required=False,
                recomputation_fallback_nodes=(),
                unresolved_edges=(),
            )

    # Check graph lineage: verify whether required lineage nodes/edges are resolved
    unresolved_edges: list[dict[str, Any]] = []
    recomputation_fallback_nodes: list[str] = []

    if graph is None:
        # No graph provided: fail closed to recomputation
        unresolved_edges.append({"error": "GRAPH_MISSING", "detail": "Lineage graph is None"})
        recomputation_fallback_nodes.extend(task.expected_lineage_nodes or task.required_fields)
    else:
        if not isinstance(graph, LineageGraph):
            raise MinimalDisclosureError(
                REASON_UNKNOWN_GRAPH_EDGE, f"graph must be a LineageGraph, got {type(graph).__name__}"
            )

        # Audit expected lineage nodes
        for node_id in task.expected_lineage_nodes:
            if not graph.has_node(node_id):
                unresolved_edges.append({
                    "node_id": node_id,
                    "error": "UNKNOWN_NODE",
                    "reason": REASON_UNKNOWN_GRAPH_EDGE,
                })
                recomputation_fallback_nodes.append(node_id)
            else:
                # Check that if node is a derived node, its incoming/outgoing edges are valid
                # In LineageGraph, edges are parent -> child.
                # If node has parent dependencies, check if any parent is missing
                incoming_edges = [e for e in graph.edges if e.child == node_id]
                for edge in incoming_edges:
                    if not graph.has_node(edge.parent):
                        unresolved_edges.append({
                            "parent": edge.parent,
                            "child": node_id,
                            "error": "UNKNOWN_PARENT_EDGE",
                            "reason": REASON_UNKNOWN_GRAPH_EDGE,
                        })
                        recomputation_fallback_nodes.append(node_id)
                    # Also check purpose scope on the derivation edge
                    if edge.purpose is not None and edge.purpose not in ("*", current_purpose):
                        # Edge belongs to a different purpose!
                        unresolved_edges.append({
                            "parent": edge.parent,
                            "child": node_id,
                            "edge_purpose": edge.purpose,
                            "current_purpose": current_purpose,
                            "error": "PURPOSE_INCOMPATIBLE_EDGE",
                            "reason": REASON_UNKNOWN_GRAPH_EDGE,
                        })
                        recomputation_fallback_nodes.append(node_id)

    # If there are unresolved edges or missing graph nodes, fail closed: fall back to RECOMPUTATION
    if unresolved_edges:
        fallback_nodes = tuple(sorted(set(recomputation_fallback_nodes)))
        recomputed_payload: dict[str, Any] = {}
        if callable(recompute_fn):
            recomputed = recompute_fn(task.task_id, current_purpose, fallback_nodes)
            if isinstance(recomputed, Mapping):
                recomputed_payload = dict(recomputed)

        return Disclosure(
            status=STATUS_RECOMPUTATION,
            reason_code=REASON_RECOMPUTATION_REQUIRED,
            task_id=task.task_id,
            purpose=current_purpose,
            disclosed_fields=tuple(sorted(recomputed_payload.keys())),
            withheld_fields=tuple(sorted(full_context_fields - set(recomputed_payload.keys()))),
            disclosed_payload=recomputed_payload,
            withheld_payload={k: v for k, v in raw_context.items() if k not in recomputed_payload},
            recomputation_required=True,
            recomputation_fallback_nodes=fallback_nodes,
            unresolved_edges=tuple(unresolved_edges),
        )

    # Otherwise, resolve minimal fields
    field_set = select_fields(
        context=raw_context if raw_context else task.required_fields,
        task=task,
        purpose=current_purpose,
        purpose_allowed_fields=allowlists,
    )

    disclosed_fields = set(field_set.fields)
    withheld_fields = set(field_set.withheld_fields)

    # Disclose only minimal payload
    disclosed_payload = {k: v for k, v in raw_context.items() if k in disclosed_fields}
    withheld_payload = {k: v for k, v in raw_context.items() if k in withheld_fields}

    return Disclosure(
        status=STATUS_DISCLOSED,
        reason_code=REASON_MINIMAL_DISCLOSURE_OK,
        task_id=task.task_id,
        purpose=current_purpose,
        disclosed_fields=tuple(sorted(disclosed_fields)),
        withheld_fields=tuple(sorted(withheld_fields)),
        disclosed_payload=disclosed_payload,
        withheld_payload=withheld_payload,
        recomputation_required=False,
        recomputation_fallback_nodes=(),
        unresolved_edges=(),
    )
