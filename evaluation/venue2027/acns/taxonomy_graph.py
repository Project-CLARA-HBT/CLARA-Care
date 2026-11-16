"""ACNS-X08_taxonomy_graph — evidence-boundary taxonomy graph representation and verification.

Purpose
-------
Task ACNS-X08_taxonomy_graph (Phase P05, venue acns) delivers the graph
representation of the evidence taxonomy for the SoK "Evidence Boundaries of
Attestation in Tool-Using AI Systems" (research/venue2027/VENUES/acns/RESEARCH_BLUEPRINT.md,
RQ2). The directed graph models the six-level evidence lattice (ASSUMED, ASSEMBLED,
DISPATCHED, ACKNOWLEDGED, EXECUTED, COMMITTED) across the five evidence classes
(sender-known bytes, transport delivery, provider-signed receipt, execution,
and persisted side effect).

Every edge in the graph represents an implication candidate annotated with:
- `trust_assumptions`: explicit extra assumptions required for the transition
- `counterexample_ids`: linked counterexample witnesses and negative control IDs
- `status`: whether the implication is valid or invalid absent assumptions
- `boundary_condition`: specific gap register identifiers (G1-G9)
- `failure_family`: threat model failure classification

The module strictly avoids directional implication without evidence: transitions
cannot leap across evidence classes or reverse lattice ordering without explicit,
valid proof anchors. Unsupported jumps and unbacked transitions fail closed.

Deliverables & Contracts
------------------------
- `build_taxonomy_graph(yaml_path=None) -> TaxonomyGraph`
- `validate_evidence_path(graph, from_node, to_node) -> PathValidityResult`
- `export_graph(graph=None) -> dict`
- `render_graph(evidence_types=None, edges=None, graph=None) -> str` (SVG export)
- `emit_taxonomy_graph(run_id=...) -> Path`

Allowed Input
-------------
Read-only access to `research/venue2027/acns/protocols/evidence_taxonomy.yaml`.
Synthetic inputs only: no PHI/PII, no external network, no database, no clock,
and no non-deterministic randomness.

Failure Semantics
-----------------
All errors raise `TaxonomyGraphError` with a stable uppercase `reason_code`:
- `INVALID_NODE_ID`: requested node ID or level not found in taxonomy
- `CYCLE_DETECTED`: graph contains or is modified to introduce directed cycles
- `UNSUPPORTED_JUMP`: transition leaps across levels without required evidence
- `INVALID_TRANSITION`: implication candidate is explicitly invalid
- `MALFORMED_TAXONOMY`: YAML specification missing required nodes or edges
- `NO_PATH_EXISTS`: no directed path exists between nodes

Version
-------
`TAXONOMY_GRAPH_VERSION = "1.0.0"`
`CONTRACT_ID = "clara.venue2027.acns.taxonomy-graph.v1"`
`SCHEMA_VERSION = "1"`
"""

from __future__ import annotations

import collections
import dataclasses
import html
import json
import pathlib
import re
from typing import Any, Final

TAXONOMY_GRAPH_VERSION: Final[str] = "1.0.0"
CONTRACT_ID: Final[str] = "clara.venue2027.acns.taxonomy-graph.v1"
SCHEMA_VERSION: Final[str] = "1"

REPO_ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_TAXONOMY_PATH: Final[pathlib.Path] = (
    REPO_ROOT / "research" / "venue2027" / "acns" / "protocols" / "evidence_taxonomy.yaml"
)

# Known counterexample witness mappings per threat-model gap
GAP_TO_WITNESS: Final[dict[str, str]] = {
    "G1": "dispatched-not-acknowledged",
    "G2": "acknowledged-not-executed",
    "G3": "executed-not-committed",
    "G4": "signed-receipt-wrong-context",
    "G7": "assembled-not-sent",
}


class TaxonomyGraphError(ValueError):
    """Stable reason-coded error for evidence taxonomy graph operations."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code
        self.message = message


@dataclasses.dataclass(frozen=True)
class TaxonomyNode:
    """A node in the evidence-boundary taxonomy lattice."""

    id: str
    node_class: str
    level: str
    definition: str
    trust_root: str
    observer_location: str
    proves: str
    does_not_prove: str
    citations: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_class": self.node_class,
            "level": self.level,
            "definition": self.definition,
            "trust_root": self.trust_root,
            "observer_location": self.observer_location,
            "proves": self.proves,
            "does_not_prove": self.does_not_prove,
            "citations": list(self.citations),
        }


@dataclasses.dataclass(frozen=True)
class TaxonomyEdge:
    """A directed implication edge annotated with assumptions and counterexamples."""

    id: str
    from_node: str
    to_node: str
    claim: str
    status: str
    is_valid: bool
    trust_assumptions: str
    boundary_condition: str
    failure_family: str
    witness_ref: str | None = None
    counterexample_ids: list[str] = dataclasses.field(default_factory=list)
    related_gaps: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "claim": self.claim,
            "status": self.status,
            "is_valid": self.is_valid,
            "trust_assumptions": self.trust_assumptions,
            "boundary_condition": self.boundary_condition,
            "failure_family": self.failure_family,
            "witness_ref": self.witness_ref,
            "counterexample_ids": list(self.counterexample_ids),
            "related_gaps": list(self.related_gaps),
        }


@dataclasses.dataclass(frozen=True)
class PathValidityResult:
    """Result of evaluating an evidence path between two taxonomy nodes."""

    is_valid: bool
    from_node: str
    to_node: str
    path: list[str]
    edge_ids: list[str]
    edges: list[dict[str, Any]]
    counterexample_ids: list[str]
    missing_assumptions: list[str]
    failure_families: list[str]
    gaps: list[str]
    reason_code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "path": list(self.path),
            "edge_ids": list(self.edge_ids),
            "edges": list(self.edges),
            "counterexample_ids": list(self.counterexample_ids),
            "missing_assumptions": list(self.missing_assumptions),
            "failure_families": list(self.failure_families),
            "gaps": list(self.gaps),
            "reason_code": self.reason_code,
            "message": self.message,
        }


class TaxonomyGraph:
    """Directed graph representing the evidence taxonomy with assumption annotations."""

    def __init__(
        self,
        nodes: dict[str, TaxonomyNode],
        edges: dict[str, TaxonomyEdge],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.nodes: dict[str, TaxonomyNode] = dict(nodes)
        self.edges: dict[str, TaxonomyEdge] = dict(edges)
        self.metadata: dict[str, Any] = dict(metadata or {})
        self._level_to_node: dict[str, str] = {node.level: node.id for node in self.nodes.values()}

    def get_node(self, node_id_or_level: str) -> TaxonomyNode:
        """Resolve a node by full ID (e.g. N0_ASSUMED) or level name (e.g. ASSUMED)."""
        target = node_id_or_level.strip()
        if target in self.nodes:
            return self.nodes[target]
        if target in self._level_to_node:
            return self.nodes[self._level_to_node[target]]
        # Also check without prefix, e.g. N0 -> N0_ASSUMED
        for nid, node in self.nodes.items():
            if nid.startswith(f"{target}_") or target == nid:
                return node
        raise TaxonomyGraphError(
            "INVALID_NODE_ID",
            f"Node '{node_id_or_level}' not found in evidence taxonomy graph.",
        )

    def add_node(self, node: TaxonomyNode) -> None:
        """Add a taxonomy node to the graph."""
        self.nodes[node.id] = node
        self._level_to_node[node.level] = node.id

    def add_edge(self, edge: TaxonomyEdge, check_cycle: bool = False) -> None:
        """Add a directed edge. If check_cycle is True, raises on cycles."""
        if edge.from_node not in self.nodes:
            raise TaxonomyGraphError(
                "INVALID_NODE_ID", f"Source node '{edge.from_node}' not in graph."
            )
        if edge.to_node not in self.nodes:
            raise TaxonomyGraphError(
                "INVALID_NODE_ID", f"Target node '{edge.to_node}' not in graph."
            )
        self.edges[edge.id] = edge
        if check_cycle and self.has_cycle():
            del self.edges[edge.id]
            raise TaxonomyGraphError(
                "CYCLE_DETECTED",
                f"Adding edge '{edge.id}' ({edge.from_node} -> {edge.to_node}) introduces a cycle.",
            )

    def get_edge(self, from_node: str, to_node: str) -> TaxonomyEdge | None:
        """Get the direct edge between two nodes if one exists."""
        from_id = self.get_node(from_node).id
        to_id = self.get_node(to_node).id
        for edge in self.edges.values():
            if edge.from_node == from_id and edge.to_node == to_id:
                return edge
        return None

    def get_outgoing_edges(self, node_id: str, valid_only: bool = False) -> list[TaxonomyEdge]:
        """Return all outgoing edges from a given node."""
        nid = self.get_node(node_id).id
        return [
            edge
            for edge in self.edges.values()
            if edge.from_node == nid and (not valid_only or edge.is_valid)
        ]

    def get_incoming_edges(self, node_id: str, valid_only: bool = False) -> list[TaxonomyEdge]:
        """Return all incoming edges into a given node."""
        nid = self.get_node(node_id).id
        return [
            edge
            for edge in self.edges.values()
            if edge.to_node == nid and (not valid_only or edge.is_valid)
        ]

    def has_cycle(self) -> bool:
        """Check if any directed cycle exists in the graph."""
        return len(self.detect_cycles()) > 0

    def detect_cycles(self) -> list[list[str]]:
        """Return all detected directed cycles as lists of node IDs."""
        visited: set[str] = set()
        rec_stack: list[str] = []
        cycles: list[list[str]] = []

        adj: dict[str, list[str]] = collections.defaultdict(list)
        for edge in self.edges.values():
            adj[edge.from_node].append(edge.to_node)

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    idx = rec_stack.index(neighbor)
                    cycle = [*rec_stack[idx:], neighbor]
                    if cycle not in cycles:
                        cycles.append(cycle)
            rec_stack.pop()

        for node_id in self.nodes:
            if node_id not in visited:
                dfs(node_id)
        return cycles

    def assert_acyclic(self) -> None:
        """Raise TaxonomyGraphError if any cycle is present in the graph."""
        cycles = self.detect_cycles()
        if cycles:
            cycle_desc = " -> ".join(cycles[0])
            raise TaxonomyGraphError(
                "CYCLE_DETECTED",
                f"Taxonomy graph contains directed cycle: {cycle_desc}",
            )

    def export_graph(self) -> dict[str, Any]:
        """Export the complete graph as a JSON-serializable dictionary."""
        valid_count = sum(1 for e in self.edges.values() if e.is_valid)
        invalid_count = len(self.edges) - valid_count
        return {
            "schema_version": SCHEMA_VERSION,
            "contract": CONTRACT_ID,
            "graph_version": TAXONOMY_GRAPH_VERSION,
            "lattice_levels": self.metadata.get(
                "lattice_levels",
                ["ASSUMED", "ASSEMBLED", "DISPATCHED", "ACKNOWLEDGED", "EXECUTED", "COMMITTED"],
            ),
            "node_classes": self.metadata.get("node_classes", []),
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "adversarial_controls": self.metadata.get("adversarial_controls", []),
            "positive_controls": self.metadata.get("positive_controls", []),
            "trusted_components": self.metadata.get("trusted_components", {}),
            "citations": self.metadata.get("citations", []),
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "valid_edges": valid_count,
                "invalid_edges": invalid_count,
                "has_cycles": self.has_cycle(),
            },
        }

    def render_graph(self) -> str:
        """Render the taxonomy graph as SVG visualization."""
        return render_graph(graph=self)


# ---------------------------------------------------------------------------
# YAML Parser and Builder
# ---------------------------------------------------------------------------


def _parse_yaml_fallback(text: str) -> dict[str, Any]:
    """Minimal block scanner for YAML subset in case pyyaml is unavailable."""
    try:
        import yaml

        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except ImportError:
        pass

    # Basic regex-based extractor for top-level structures
    raise TaxonomyGraphError(
        "MALFORMED_TAXONOMY",
        "PyYAML is required to parse the full evidence taxonomy specification.",
    )


def build_taxonomy_graph(yaml_path: str | pathlib.Path | None = None) -> TaxonomyGraph:
    """Build a TaxonomyGraph from the evidence taxonomy YAML file.

    Parameters
    ----------
    yaml_path : str | Path | None
        Path to evidence_taxonomy.yaml. Defaults to canonical repository path.

    Returns
    -------
    TaxonomyGraph
        Annotated directed graph representation.
    """
    path = pathlib.Path(yaml_path) if yaml_path is not None else DEFAULT_TAXONOMY_PATH
    if not path.is_file():
        raise TaxonomyGraphError(
            "MALFORMED_TAXONOMY",
            f"Evidence taxonomy specification not found at {path}",
        )

    text = path.read_text(encoding="utf-8")
    try:
        import yaml

        raw = yaml.safe_load(text)
    except Exception:
        raw = _parse_yaml_fallback(text)

    if not isinstance(raw, dict) or "nodes" not in raw or "edges" not in raw:
        raise TaxonomyGraphError(
            "MALFORMED_TAXONOMY",
            "Taxonomy document must contain 'nodes' and 'edges' top-level keys.",
        )

    # Index adversarial controls by edge_ref
    adversarial_controls = raw.get("adversarial_controls", [])
    adv_by_edge: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for adv in adversarial_controls:
        edge_ref = adv.get("edge_ref")
        if edge_ref:
            adv_by_edge[edge_ref].append(adv)

    nodes: dict[str, TaxonomyNode] = {}
    for item in raw.get("nodes", []):
        nid = str(item.get("id", "")).strip()
        if not nid:
            continue
        node = TaxonomyNode(
            id=nid,
            node_class=str(item.get("node_class", "")).strip(),
            level=str(item.get("level", "")).strip(),
            definition=str(item.get("definition", "")).strip(),
            trust_root=str(item.get("trust_root", "")).strip(),
            observer_location=str(item.get("observer_location", "")).strip(),
            proves=str(item.get("proves", "")).strip(),
            does_not_prove=str(item.get("does_not_prove", "")).strip(),
            citations=list(item.get("citations", [])),
        )
        nodes[nid] = node

    edges: dict[str, TaxonomyEdge] = {}
    for item in raw.get("edges", []):
        eid = str(item.get("id", "")).strip()
        if not eid:
            continue
        from_n = str(item.get("from", "")).strip()
        to_n = str(item.get("to", "")).strip()
        status = str(item.get("status", "")).strip().lower()
        is_valid = status == "valid"
        assumptions = str(item.get("trust_assumptions", "")).strip()
        boundary = str(item.get("boundary_condition", "")).strip()
        failure_family = str(item.get("failure_family", "none")).strip()
        witness_ref = item.get("witness_ref")

        # Extract gaps from boundary_condition or adversarial controls
        gaps_found: list[str] = sorted(set(re.findall(r"\b(G[1-9])\b", boundary)))
        adv_list = adv_by_edge.get(eid, [])
        for adv in adv_list:
            for g in adv.get("related_gaps", []):
                if g not in gaps_found:
                    gaps_found.append(g)

        # Build counterexample IDs
        counterexample_ids: list[str] = []
        for adv in adv_list:
            adv_id = adv.get("id")
            if adv_id and adv_id not in counterexample_ids:
                counterexample_ids.append(adv_id)

        # Also map gaps to runnable witness names
        for gap in gaps_found:
            witness_name = GAP_TO_WITNESS.get(gap)
            if witness_name and witness_name not in counterexample_ids:
                counterexample_ids.append(witness_name)

        edge = TaxonomyEdge(
            id=eid,
            from_node=from_n,
            to_node=to_n,
            claim=str(item.get("claim", "")).strip(),
            status=status,
            is_valid=is_valid,
            trust_assumptions=assumptions,
            boundary_condition=boundary,
            failure_family=failure_family,
            witness_ref=str(witness_ref).strip() if witness_ref else None,
            counterexample_ids=counterexample_ids,
            related_gaps=gaps_found,
        )
        edges[eid] = edge

    metadata = {
        "schema_version": raw.get("schema_version", SCHEMA_VERSION),
        "contract": raw.get("contract", CONTRACT_ID),
        "lattice_levels": raw.get("lattice_levels", []),
        "node_classes": raw.get("node_classes", []),
        "trusted_components": raw.get("trusted_components", {}),
        "adversarial_controls": raw.get("adversarial_controls", []),
        "positive_controls": raw.get("positive_controls", []),
        "citations": raw.get("citations", []),
    }

    return TaxonomyGraph(nodes=nodes, edges=edges, metadata=metadata)


# ---------------------------------------------------------------------------
# Path Validation Logic
# ---------------------------------------------------------------------------


def validate_evidence_path(
    graph: TaxonomyGraph,
    from_node: str,
    to_node: str,
    *,
    edge_id: str | None = None,
) -> PathValidityResult:
    """Validate whether an evidence path exists from from_node to to_node.

    Avoids directional implication without evidence:
    - If a valid path composed solely of valid edges exists, returns is_valid=True.
    - If the transition involves invalid edge(s) or unsupported level jumps,
      returns is_valid=False and annotates counterexample IDs, missing assumptions,
      and failure families.
    - If an invalid node ID is provided, raises TaxonomyGraphError(INVALID_NODE_ID).
    - If a cycle is present in the graph and traversed, flags CYCLE_DETECTED.

    Parameters
    ----------
    graph : TaxonomyGraph
        The evidence taxonomy graph.
    from_node : str
        Source node identifier or lattice level (e.g. 'N0_ASSUMED' or 'ASSUMED').
    to_node : str
        Destination node identifier or lattice level (e.g. 'N2_DISPATCHED').
    edge_id : str | None
        Optional specific edge ID to validate directly.
    """
    src = graph.get_node(from_node)
    dst = graph.get_node(to_node)

    # Check for graph-level cycle
    if graph.has_cycle():
        cycles = graph.detect_cycles()
        cycle_nodes = set()
        for cyc in cycles:
            cycle_nodes.update(cyc)
        if src.id in cycle_nodes or dst.id in cycle_nodes:
            return PathValidityResult(
                is_valid=False,
                from_node=src.id,
                to_node=dst.id,
                path=[],
                edge_ids=[],
                edges=[],
                counterexample_ids=["CYCLE_DETECTED"],
                missing_assumptions=["Graph must be an acyclic partial order (DAG)."],
                failure_families=["cycle_violation"],
                gaps=[],
                reason_code="CYCLE_DETECTED",
                message=f"Cycle detected in taxonomy involving {src.id} or {dst.id}.",
            )

    # Identical node check
    if src.id == dst.id:
        return PathValidityResult(
            is_valid=True,
            from_node=src.id,
            to_node=dst.id,
            path=[src.id],
            edge_ids=[],
            edges=[],
            counterexample_ids=[],
            missing_assumptions=[],
            failure_families=[],
            gaps=[],
            reason_code="SAME_NODE",
            message=f"Source and target are the same evidence node '{src.id}'.",
        )

    # If a specific edge was requested, evaluate that exact edge
    if edge_id is not None:
        if edge_id not in graph.edges:
            raise TaxonomyGraphError(
                "INVALID_EDGE_ID",
                f"Edge '{edge_id}' not found in taxonomy graph.",
            )
        edge = graph.edges[edge_id]
        if edge.from_node != src.id or edge.to_node != dst.id:
            return PathValidityResult(
                is_valid=False,
                from_node=src.id,
                to_node=dst.id,
                path=[src.id, dst.id],
                edge_ids=[edge.id],
                edges=[edge.to_dict()],
                counterexample_ids=edge.counterexample_ids,
                missing_assumptions=[edge.trust_assumptions],
                failure_families=[edge.failure_family] if edge.failure_family != "none" else [],
                gaps=edge.related_gaps,
                reason_code="EDGE_ENDPOINT_MISMATCH",
                message=f"Edge '{edge.id}' connects {edge.from_node}->{edge.to_node}, not {src.id}->{dst.id}.",
            )
        if edge.is_valid:
            return PathValidityResult(
                is_valid=True,
                from_node=src.id,
                to_node=dst.id,
                path=[src.id, dst.id],
                edge_ids=[edge.id],
                edges=[edge.to_dict()],
                counterexample_ids=[],
                missing_assumptions=[],
                failure_families=[],
                gaps=[],
                reason_code="VALID_PATH",
                message=f"Direct valid transition via edge '{edge.id}'.",
            )
        return PathValidityResult(
            is_valid=False,
            from_node=src.id,
            to_node=dst.id,
            path=[src.id, dst.id],
            edge_ids=[edge.id],
            edges=[edge.to_dict()],
            counterexample_ids=edge.counterexample_ids,
            missing_assumptions=[edge.trust_assumptions],
            failure_families=[edge.failure_family] if edge.failure_family != "none" else [],
            gaps=edge.related_gaps,
            reason_code="INVALID_TRANSITION",
            message=f"Implication candidate '{edge.id}' is invalid: {edge.claim}",
        )

    # Search for valid-only path using BFS
    queue: collections.deque[tuple[str, list[str], list[str]]] = collections.deque(
        [(src.id, [src.id], [])]
    )
    visited_valid: set[str] = {src.id}
    valid_solution: tuple[list[str], list[str]] | None = None

    while queue:
        curr, path_nodes, path_edges = queue.popleft()
        if curr == dst.id:
            valid_solution = (path_nodes, path_edges)
            break
        for edge in graph.get_outgoing_edges(curr, valid_only=True):
            if edge.to_node not in visited_valid:
                visited_valid.add(edge.to_node)
                queue.append(
                    (
                        edge.to_node,
                        [*path_nodes, edge.to_node],
                        [*path_edges, edge.id],
                    )
                )

    if valid_solution:
        p_nodes, p_edges = valid_solution
        edge_dicts = [graph.edges[eid].to_dict() for eid in p_edges]
        return PathValidityResult(
            is_valid=True,
            from_node=src.id,
            to_node=dst.id,
            path=p_nodes,
            edge_ids=p_edges,
            edges=edge_dicts,
            counterexample_ids=[],
            missing_assumptions=[],
            failure_families=[],
            gaps=[],
            reason_code="VALID_PATH",
            message=f"Supported evidence path: {' -> '.join(p_nodes)}",
        )

    # No valid path exists: find why. Search all edges (including invalid ones)
    queue_all: collections.deque[tuple[str, list[str], list[str]]] = collections.deque(
        [(src.id, [src.id], [])]
    )
    visited_all: set[str] = {src.id}
    best_candidate: tuple[list[str], list[str]] | None = None

    while queue_all:
        curr, path_nodes, path_edges = queue_all.popleft()
        if curr == dst.id:
            best_candidate = (path_nodes, path_edges)
            break
        for edge in graph.get_outgoing_edges(curr, valid_only=False):
            if edge.to_node not in visited_all:
                visited_all.add(edge.to_node)
                queue_all.append(
                    (
                        edge.to_node,
                        [*path_nodes, edge.to_node],
                        [*path_edges, edge.id],
                    )
                )

    # Check direct edge if present
    direct_edge = graph.get_edge(src.id, dst.id)

    if direct_edge and not direct_edge.is_valid:
        return PathValidityResult(
            is_valid=False,
            from_node=src.id,
            to_node=dst.id,
            path=[src.id, dst.id],
            edge_ids=[direct_edge.id],
            edges=[direct_edge.to_dict()],
            counterexample_ids=direct_edge.counterexample_ids,
            missing_assumptions=[direct_edge.trust_assumptions],
            failure_families=(
                [direct_edge.failure_family] if direct_edge.failure_family != "none" else []
            ),
            gaps=direct_edge.related_gaps,
            reason_code="INVALID_TRANSITION",
            message=(
                f"Direct transition '{direct_edge.id}' is invalid: "
                f"{direct_edge.claim}. Missing: {direct_edge.boundary_condition}"
            ),
        )

    if best_candidate:
        p_nodes, p_edges = best_candidate
        edge_objs = [graph.edges[eid] for eid in p_edges]
        counterexamples: list[str] = []
        missing_assumptions: list[str] = []
        failure_fams: list[str] = []
        gaps: list[str] = []

        for e in edge_objs:
            if not e.is_valid:
                for c in e.counterexample_ids:
                    if c not in counterexamples:
                        counterexamples.append(c)
                if e.trust_assumptions and e.trust_assumptions not in missing_assumptions:
                    missing_assumptions.append(e.trust_assumptions)
                if e.failure_family != "none" and e.failure_family not in failure_fams:
                    failure_fams.append(e.failure_family)
                for g in e.related_gaps:
                    if g not in gaps:
                        gaps.append(g)

        return PathValidityResult(
            is_valid=False,
            from_node=src.id,
            to_node=dst.id,
            path=p_nodes,
            edge_ids=p_edges,
            edges=[e.to_dict() for e in edge_objs],
            counterexample_ids=counterexamples,
            missing_assumptions=missing_assumptions,
            failure_families=failure_fams,
            gaps=gaps,
            reason_code="UNSUPPORTED_JUMP",
            message=(
                f"Implication path from '{src.id}' to '{dst.id}' contains "
                f"unsupported transition(s): {', '.join(e.id for e in edge_objs if not e.is_valid)}."
            ),
        )

    # Disconnected or backwards direction
    return PathValidityResult(
        is_valid=False,
        from_node=src.id,
        to_node=dst.id,
        path=[],
        edge_ids=[],
        edges=[],
        counterexample_ids=[],
        missing_assumptions=[
            f"No directed evidence path exists from '{src.id}' to '{dst.id}'. "
            "Directional implication without evidence is rejected."
        ],
        failure_families=["directional_violation"],
        gaps=[],
        reason_code="NO_PATH_EXISTS",
        message=(
            f"No implication path exists from '{src.id}' to '{dst.id}'. "
            "Reverse transitions and disconnected jumps are strictly rejected."
        ),
    )


def validate_transition(graph: TaxonomyGraph, edge_id: str) -> PathValidityResult:
    """Validate a single transition by edge ID."""
    if edge_id not in graph.edges:
        raise TaxonomyGraphError(
            "INVALID_EDGE_ID",
            f"Edge '{edge_id}' not found in taxonomy graph.",
        )
    edge = graph.edges[edge_id]
    return validate_evidence_path(
        graph,
        edge.from_node,
        edge.to_node,
        edge_id=edge.id,
    )


# ---------------------------------------------------------------------------
# Machine-Readable Export and SVG Rendering
# ---------------------------------------------------------------------------


def export_graph(graph: TaxonomyGraph | None = None) -> dict[str, Any]:
    """Export machine-readable JSON dictionary of the evidence taxonomy graph."""
    active_graph = graph if graph is not None else build_taxonomy_graph()
    return active_graph.export_graph()


def render_graph(
    evidence_types: list[Any] | None = None,
    edges: list[Any] | None = None,
    graph: TaxonomyGraph | None = None,
) -> str:
    """Render the evidence taxonomy graph as SVG.

    Exact target contract: render_graph(evidence_types, edges) -> SVG string.
    Supports either explicit evidence_types/edges lists or graph object.
    """
    active_graph = graph if graph is not None else build_taxonomy_graph()

    # Determine nodes to render
    node_list: list[TaxonomyNode] = []
    if evidence_types is not None:
        for item in evidence_types:
            if isinstance(item, TaxonomyNode):
                node_list.append(item)
            elif isinstance(item, dict) and "id" in item:
                node_list.append(active_graph.get_node(item["id"]))
            elif isinstance(item, str):
                node_list.append(active_graph.get_node(item))
    if not node_list:
        node_list = list(active_graph.nodes.values())

    # Determine edges to render
    edge_list: list[TaxonomyEdge] = []
    if edges is not None:
        for item in edges:
            if isinstance(item, TaxonomyEdge):
                edge_list.append(item)
            elif isinstance(item, dict) and "id" in item and item["id"] in active_graph.edges:
                edge_list.append(active_graph.edges[item["id"]])
            elif isinstance(item, str) and item in active_graph.edges:
                edge_list.append(active_graph.edges[item])
    if not edge_list:
        edge_list = list(active_graph.edges.values())

    # Layout geometry
    width = 1100
    height = 680
    node_width = 140
    node_height = 70
    start_x = 50
    spacing_x = 170
    base_y = 260

    # Node positions along horizontal lattice
    coords: dict[str, tuple[int, int]] = {}
    for i, node in enumerate(node_list):
        coords[node.id] = (start_x + i * spacing_x, base_y)

    svg_parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        'style="background-color: #fafafa; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif;">',
        "  <defs>",
        '    <marker id="arrow-valid" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
        '      <polygon points="0 0, 10 3.5, 0 7" fill="#2e7d32" />',
        "    </marker>",
        '    <marker id="arrow-invalid" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
        '      <polygon points="0 0, 10 3.5, 0 7" fill="#c62828" />',
        "    </marker>",
        '    <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%">',
        '      <feDropShadow dx="1" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.1"/>',
        "    </filter>",
        "  </defs>",
        '  <text x="50" y="45" font-size="20" font-weight="bold" fill="#212121">'
        "ACNS Evidence-Boundary Taxonomy Implication Graph"
        "</text>",
        '  <text x="50" y="70" font-size="12" fill="#616161">'
        "Green: Valid implications under declared trust assumptions | "
        "Red Dashed: Invalid transitions naming counterexample gaps"
        "</text>",
    ]

    # Render edges
    # Offset vertical arcs for multi-hop or alternative edges
    edge_offsets: dict[str, int] = {
        "E06_transport_to_inference": -110,
        "E07_hash_only_to_hardware_attestation": -170,
        "E08_receipt_to_committed": 120,
        "E09_receipt_tee_to_execution": -40,
        "E10_execution_record_to_committed": -40,
        "E04_receipt_to_execution": 40,
        "E05_execution_to_committed": 40,
    }

    for edge in edge_list:
        if edge.from_node not in coords or edge.to_node not in coords:
            continue
        x1, y1 = coords[edge.from_node]
        x2, y2 = coords[edge.to_node]

        is_valid = edge.is_valid
        stroke = "#2e7d32" if is_valid else "#c62828"
        stroke_dash = "" if is_valid else 'stroke-dasharray="6,4" '
        marker = "arrow-valid" if is_valid else "arrow-invalid"

        offset_y = edge_offsets.get(edge.id, 0)
        start_pt = (x1 + node_width, y1 + node_height // 2)
        end_pt = (x2, y2 + node_height // 2)

        if offset_y == 0:
            svg_parts.append(
                f'  <line x1="{start_pt[0]}" y1="{start_pt[1]}" x2="{end_pt[0]}" y2="{end_pt[1]}" '
                f'stroke="{stroke}" stroke-width="2.5" {stroke_dash}marker-end="url(#{marker})" />'
            )
        else:
            ctrl_x = (start_pt[0] + end_pt[0]) // 2
            ctrl_y = start_pt[1] + offset_y
            svg_parts.append(
                f'  <path d="M {start_pt[0]} {start_pt[1]} Q {ctrl_x} {ctrl_y} {end_pt[0]} {end_pt[1]}" '
                f'fill="none" stroke="{stroke}" stroke-width="2.5" {stroke_dash}marker-end="url(#{marker})" />'
            )

        # Label on edge
        lbl_x = (start_pt[0] + end_pt[0]) // 2
        lbl_y = ((start_pt[1] + end_pt[1]) // 2) + (offset_y // 2 if offset_y else -8)
        tag = edge.id.split("_")[0]
        if not is_valid and edge.related_gaps:
            tag += f" [{','.join(edge.related_gaps)}]"
        svg_parts.append(
            f'  <text x="{lbl_x}" y="{lbl_y}" font-size="10" font-weight="600" '
            f'fill="{stroke}" text-anchor="middle">{html.escape(tag)}</text>'
        )

    # Render nodes
    for node in node_list:
        if node.id not in coords:
            continue
        x, y = coords[node.id]
        clean_name = node.id.replace("N0_", "").replace("N1_", "").replace("N2_", "")
        clean_name = (
            clean_name.replace("N3_", "").replace("N4_", "").replace("N5_", "").replace("_", " ")
        )
        cls_name = node.node_class.replace("_", " ")

        svg_parts.append(
            f'  <g transform="translate({x},{y})" filter="url(#shadow)">'
            f'    <rect width="{node_width}" height="{node_height}" rx="8" ry="8" '
            f'fill="#ffffff" stroke="#37474f" stroke-width="2" />'
            f'    <rect width="{node_width}" height="24" rx="8" ry="8" fill="#eceff1" />'
            f'    <rect y="16" width="{node_width}" height="8" fill="#eceff1" />'
            f'    <text x="{node_width // 2}" y="16" font-size="11" font-weight="bold" '
            f'fill="#263238" text-anchor="middle">{html.escape(node.id.split("_")[0])}: {html.escape(clean_name)}</text>'
            f'    <text x="{node_width // 2}" y="42" font-size="9" fill="#546e7a" '
            f'text-anchor="middle">{html.escape(cls_name)}</text>'
            f'    <text x="{node_width // 2}" y="56" font-size="8" fill="#78909c" '
            f'text-anchor="middle">{html.escape(node.level)}</text>'
            "  </g>"
        )

    svg_parts.append("</svg>\n")
    return "\n".join(svg_parts)


def emit_taxonomy_graph(
    run_id: str = "acns-x08-taxonomy-graph-1.0.0",
    out_path: pathlib.Path | None = None,
    yaml_path: str | pathlib.Path | None = None,
) -> pathlib.Path:
    """Emit the machine-readable taxonomy graph artifact to disk."""
    graph = build_taxonomy_graph(yaml_path=yaml_path)
    data = graph.export_graph()

    if out_path is None:
        target_dir = REPO_ROOT / "artifacts" / "venue2027" / "acns" / run_id
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / "taxonomy_graph.json"
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
