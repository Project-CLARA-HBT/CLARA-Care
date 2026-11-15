"""CLARA-Care 2027 POPETS task POPETS-X01_lineage_graph — context-lineage graph.

Purpose
-------
Build and audit the **context-lineage graph** for the paper *Revocation-Complete
Future Disclosure for Cached Longitudinal AI Contexts*
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``,
``research/venue2027/VENUES/popets/TASKS/POPETS-X01_lineage_graph.md``,
``research/venue2027/popets/threat_model.md``).

The graph is the structural substrate of the noninterference predicate
``forbidden_label(g, p) ∩ lineage(d) = ∅`` (threat model §2):

- **Nodes** are context artifacts on the five derivation paths of threat
  model §1: original field/record (origin), derived summary, cache object,
  retry payload, provider transport payload, embedding pointer — every
  platform-side artifact consulted while assembling a dispatch.
- **Edges** are derivation/disclosure relations, labeled with the
  ``(principal, purpose, time, transform)`` tuple the task contract requires
  (``transform`` carries a caller-supplied transform identifier/digest).

The exact target contract of the task is ``derive_graph(disclosures,
transforms) -> LineageGraph``. On top of construction, this module provides the
revocation-closure surfaces required by the study:

- :meth:`LineageGraph.descendants` — every artifact transitively derived from
  a node (forward closure along derivation edges).
- :meth:`LineageGraph.revocation_closure` — the **complete** set of transitively
  derived items (including the node itself) that must be purged when consent
  for ``(principal, purpose)`` is revoked: every node reachable from the
  revoked node through an edge whose label intersects the revoked scope.
- :func:`assert_revocation_complete` — proves the closure covers every
  reachable descendant: it re-walks the reachable subgraph ignoring the
  scope filter and fails closed with ``REVOCATION_CLOSURE_INCOMPLETE`` if any
  reachable descendant is missing from the closure. A passing assertion is the
  machine-checkable form of "zero transitive survivors"
  (threat model §7.5, POPETS-CASE-03).

Allowed input
-------------
- ``disclosures``: iterable of JSON-serializable mappings (or
  :class:`DisclosureRecord` instances) with ``item_id``, ``created_by`` (the
  parent artifact consumed), optional ``principal``, ``purpose``, ``time``,
  ``transform``, ``node_kind``. Each record contributes the parent node, the
  derived child node, and a directed ``parent -> child`` derivation edge.
- ``transforms``: optional iterable of transform descriptors
  (``{"transform_id", "digest", "input_nodes", "output_nodes"}``) contributing
  explicit multi-input/multi-output edges; unknown endpoint ids are rejected
  unless they are being introduced by ``disclosures`` in the same call.
- Node ids: non-empty strings. Labels (principal/purpose) must be non-empty
  strings when present. ``time`` must be a non-negative integer (the ledger's
  logical clock — threat model §2 R5; no hidden wall clock).

Failure semantics (fail closed, stable uppercase reason codes — errors surface
as :class:`LineageGraphError`, never as silent acceptance)
----------------------------------------------------------------------------------------------
- ``EDGE_MALFORMED`` — a disclosure/transform record is ill-typed or lacks a
  non-empty ``item_id``/``created_by``/``transform_id``.
- ``EDGE_UNKNOWN_ANCESTOR`` — an edge references a parent node that is neither
  introduced by any record nor declared as a root (missing-ancestor probe,
  POPETS-CASE-07 shape: unlinked derivatives are refused, never guessed).
- ``EDGE_CYCLE`` — a derivation cycle is detected (cycle validation, task §3
  step "validate cycles and missing ancestors"); the offending cycle path is
  reported. Traversals (:meth:`descendants`, :meth:`revocation_closure`) are
  additionally cycle-safe by construction (iterative DFS with an on-stack set),
  so a graph that was validated without a cycle can never loop.
- ``NODE_MALFORMED`` — an ill-typed node id or label.
- ``SCOPE_MALFORMED`` — ill-typed principal/purpose in a scope query.
- ``REVOCATION_CLOSURE_INCOMPLETE`` — :func:`assert_revocation_complete` found
  a reachable descendant outside the computed closure (the adversarial leak
  class this module exists to catch: a missed descendant is the RQ1 leak).

Determinism
-----------
Pure functions over injected data; no clock, no randomness, no I/O. All outputs
(``descendants``, ``revocation_closure``, ``to_dict``) are sorted and
JSON-serializable; repeated construction from the same inputs yields byte-equal
serializations.

Scope note (threat model §5.2, novelty contract): the revocation closure covers
platform-side stored artifacts and derived items only. It makes **no** claim
about bytes already delivered to external providers (``OUT_OF_SCOPE_PAST``) or
about model memorization (``NOT_GUARANTEED``); those orthogonal surfaces are
governed by :mod:`evaluation.venue2027.popets.revocation_model`.

Version
-------
``LINEAGE_GRAPH_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from typing import Any, Final, Literal

__all__ = [
    "LINEAGE_GRAPH_VERSION",
    "NODE_KINDS",
    "REASON_EDGE_CYCLE",
    "REASON_EDGE_MALFORMED",
    "REASON_EDGE_UNKNOWN_ANCESTOR",
    "REASON_NODE_MALFORMED",
    "REASON_REVOCATION_CLOSURE_INCOMPLETE",
    "REASON_SCOPE_MALFORMED",
    "DerivationEdge",
    "DisclosureRecord",
    "LineageGraph",
    "LineageGraphError",
    "LineageNode",
    "RevocationScope",
    "TransformSpec",
    "assert_revocation_complete",
    "derive_graph",
]

LINEAGE_GRAPH_VERSION = "1.0.0"

#: Node kinds on the five derivation paths (threat model §1).
NodeKind = Literal[
    "origin_field",
    "derived_summary",
    "cache_object",
    "retry_payload",
    "provider_transport",
    "embedding_pointer",
]

NODE_KINDS: Final[tuple[str, ...]] = (
    "origin_field",
    "derived_summary",
    "cache_object",
    "retry_payload",
    "provider_transport",
    "embedding_pointer",
)

REASON_EDGE_MALFORMED = "EDGE_MALFORMED"
REASON_EDGE_UNKNOWN_ANCESTOR = "EDGE_UNKNOWN_ANCESTOR"
REASON_EDGE_CYCLE = "EDGE_CYCLE"
REASON_NODE_MALFORMED = "NODE_MALFORMED"
REASON_SCOPE_MALFORMED = "SCOPE_MALFORMED"
REASON_REVOCATION_CLOSURE_INCOMPLETE = "REVOCATION_CLOSURE_INCOMPLETE"


class LineageGraphError(ValueError):
    """Stable-reason-code error surface for lineage construction/audit."""


# ---------------------------------------------------------------------------
# Input contracts (JSON-serializable typed objects)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DisclosureRecord:
    """One derivation event: ``created_by`` (parent) derived ``item_id`` (child).

    ``principal``/``purpose``/``time`` label the edge (the consent scope under
    which the derivation happened); ``transform`` identifies the derivation
    operation (caller-supplied identifier or digest — a digest is provenance
    metadata only, never clinical proof, task §3 step 4).
    """

    item_id: str
    created_by: str
    principal: str | None = None
    purpose: str | None = None
    time: int | None = None
    transform: str | None = None
    node_kind: NodeKind | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "created_by": self.created_by,
            "principal": self.principal,
            "purpose": self.purpose,
            "time": self.time,
            "transform": self.transform,
            "node_kind": self.node_kind,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | DisclosureRecord) -> DisclosureRecord:
        if isinstance(raw, DisclosureRecord):
            return raw
        if not isinstance(raw, Mapping):
            raise LineageGraphError(f"{REASON_EDGE_MALFORMED}: record must be an object")
        item_id = raw.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise LineageGraphError(f"{REASON_EDGE_MALFORMED}: item_id must be a non-empty string")
        created_by = raw.get("created_by")
        if not isinstance(created_by, str) or not created_by:
            raise LineageGraphError(
                f"{REASON_EDGE_MALFORMED}: created_by must be a non-empty string"
            )
        principal = _opt_str(raw.get("principal"), "principal")
        purpose = _opt_str(raw.get("purpose"), "purpose")
        transform = _opt_str(raw.get("transform"), "transform")
        node_kind = raw.get("node_kind")
        if node_kind is not None and node_kind not in NODE_KINDS:
            raise LineageGraphError(f"{REASON_NODE_MALFORMED}: unknown node_kind {node_kind!r}")
        time = raw.get("time")
        if time is not None and (isinstance(time, bool) or not isinstance(time, int) or time < 0):
            raise LineageGraphError(f"{REASON_EDGE_MALFORMED}: time must be a non-negative integer")
        return cls(
            item_id=item_id,
            created_by=created_by,
            principal=principal,
            purpose=purpose,
            time=time,
            transform=transform,
            node_kind=node_kind,  # type: ignore[arg-type]
        )


@dataclasses.dataclass(frozen=True)
class TransformSpec:
    """Explicit multi-input/multi-output transform descriptor.

    Contributes one edge per (input, output) pair, each labeled with the
    transform identifier/digest. Output nodes that no disclosure record
    introduces must exist as inputs or as previously-seen nodes.
    """

    transform_id: str
    digest: str
    input_nodes: tuple[str, ...]
    output_nodes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "transform_id": self.transform_id,
            "digest": self.digest,
            "input_nodes": list(self.input_nodes),
            "output_nodes": list(self.output_nodes),
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | TransformSpec) -> TransformSpec:
        if isinstance(raw, TransformSpec):
            return raw
        if not isinstance(raw, Mapping):
            raise LineageGraphError(f"{REASON_EDGE_MALFORMED}: transform must be an object")
        transform_id = raw.get("transform_id")
        if not isinstance(transform_id, str) or not transform_id:
            raise LineageGraphError(
                f"{REASON_EDGE_MALFORMED}: transform_id must be a non-empty string"
            )
        digest = raw.get("digest")
        if not isinstance(digest, str) or not digest:
            raise LineageGraphError(f"{REASON_EDGE_MALFORMED}: digest must be a non-empty string")
        inputs = _str_tuple(raw.get("input_nodes"), "input_nodes")
        outputs = _str_tuple(raw.get("output_nodes"), "output_nodes")
        if not inputs or not outputs:
            raise LineageGraphError(
                f"{REASON_EDGE_MALFORMED}: transform needs >=1 input and >=1 output node"
            )
        return cls(
            transform_id=transform_id, digest=digest, input_nodes=inputs, output_nodes=outputs
        )


@dataclasses.dataclass(frozen=True)
class RevocationScope:
    """The ``(principal, purpose)`` scope being revoked.

    ``purpose="*"`` is the subject-wide withdrawal of the X05 vocabulary: it
    intersects every purpose label on an edge.
    """

    principal: str
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return {"principal": self.principal, "purpose": self.purpose}


# ---------------------------------------------------------------------------
# Output contracts
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class LineageNode:
    """One context artifact in the graph."""

    node_id: str
    kind: NodeKind | None
    first_seen_time: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "first_seen_time": self.first_seen_time,
        }


@dataclasses.dataclass(frozen=True)
class DerivationEdge:
    """Directed derivation edge ``parent -> child`` with its scope label."""

    parent: str
    child: str
    principal: str | None
    purpose: str | None
    time: int | None
    transform: str | None
    digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent": self.parent,
            "child": self.child,
            "principal": self.principal,
            "purpose": self.purpose,
            "time": self.time,
            "transform": self.transform,
            "digest": self.digest,
        }


@dataclasses.dataclass(frozen=True)
class LineageGraph:
    """Immutable context-lineage graph; deterministic and JSON-serializable.

    Derived structures (children adjacency, cycle-safe traversal state) are
    computed once at construction. Traversals are iterative with an on-stack
    set, so cycles can never cause non-termination even on a corrupted store.
    """

    nodes: tuple[LineageNode, ...]
    edges: tuple[DerivationEdge, ...]

    def __post_init__(self) -> None:
        children: dict[str, tuple[str, ...]] = {}
        adjacency: dict[str, tuple[DerivationEdge, ...]] = {}
        for edge in self.edges:
            children.setdefault(edge.parent, ())
            children.setdefault(edge.child, ())
            adjacency.setdefault(edge.parent, ())
            adjacency[edge.parent] = adjacency[edge.parent] + (edge,)
        object.__setattr__(self, "_children", children)
        object.__setattr__(self, "_adjacency", adjacency)

    # -- derived views -------------------------------------------------------

    @property
    def children(self) -> dict[str, tuple[str, ...]]:
        return {p: tuple(c) for p, c in self._children.items()}

    @property
    def adjacency(self) -> dict[str, tuple[DerivationEdge, ...]]:
        return {p: tuple(e) for p, e in self._adjacency.items()}

    def has_node(self, node_id: str) -> bool:
        return any(n.node_id == node_id for n in self.nodes)

    # -- core queries ---------------------------------------------------------

    def descendants(self, node: str) -> tuple[str, ...]:
        """ALL transitively derived items reachable from ``node`` (excluding it).

        Cycle-safe iterative DFS; deterministic sorted output.
        """
        return tuple(sorted(self._reachable(node).keys()))

    def revocation_closure(
        self, node: str, scope: RevocationScope | None = None
    ) -> tuple[str, ...]:
        """Every transitively derived item that must be purged on revocation.

        With ``scope`` given, traversal follows only edges whose label
        intersects the revoked scope (edge-level purpose/principal matching —
        the reverse-edge invalidation of blueprint arm B4); the node itself is
        always included. With ``scope=None`` this equals the node plus its full
        descendant set. Deterministic, sorted, JSON-serializable.
        """
        if scope is None:
            return tuple(sorted({node, *self.descendants(node)}))
        if not isinstance(scope, RevocationScope):
            raise LineageGraphError(f"{REASON_SCOPE_MALFORMED}: scope must be a RevocationScope")
        _validate_node_id(node)
        reachable = self._reachable(node, scope=scope)
        return tuple(sorted({node, *reachable.keys()}))

    # -- internals -------------------------------------------------------------

    def _reachable(self, node: str, scope: RevocationScope | None = None) -> dict[str, int | None]:
        """Cycle-safe iterative DFS over children of ``node``.

        Returns ``{descendant: first_visit_order}`` (order for determinism of
        multi-input merges, not for display). Raises ``EDGE_UNKNOWN_ANCESTOR``
        if ``node`` is absent from the graph (missing-ancestor probe).
        """
        if not self.has_node(node):
            raise LineageGraphError(f"{REASON_EDGE_UNKNOWN_ANCESTOR}: unknown node {node!r}")
        found: dict[str, int | None] = {}
        stack: list[tuple[str, bool]] = [(node, False)]
        on_path: set[str] = set()
        order = 0
        while stack:
            current, processed = stack.pop()
            if processed:
                on_path.discard(current)
                continue
            if current in on_path:
                continue
            if current in found:
                continue
            if current != node:
                found[current] = order
                order += 1
            on_path.add(current)
            stack.append((current, True))
            for edge in self._adjacency.get(current, ()):
                if scope is not None and not _edge_in_scope(edge, scope):
                    continue
                stack.append((edge.child, False))
        return found


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def derive_graph(
    disclosures: Iterable[Mapping[str, Any] | DisclosureRecord],
    transforms: Iterable[Mapping[str, Any] | TransformSpec] | None = None,
    roots: Iterable[str | Mapping[str, Any]] | None = None,
) -> LineageGraph:
    """Build the context-lineage graph from derivation records (task contract).

    Each disclosure record contributes parent ``created_by``, child ``item_id``,
    and one labeled derivation edge. Children are introduced by records; a
    parent that is neither a child of any record/transform output nor declared
    in ``roots`` (the trusted origin set — original fields/records) is refused
    with ``EDGE_UNKNOWN_ANCESTOR`` so an unlinked derivative can never silently
    look root-trustworthy (missing-ancestor validation, POPETS-CASE-07 shape).
    A cycle is refused at construction (``EDGE_CYCLE``) *and* every traversal
    remains cycle-safe regardless. Deterministic: node/edge order is normalized
    (nodes sorted by id, edges by (parent, child, transform, digest)).
    """
    nodes_by_id: dict[str, LineageNode] = {}
    edges: list[DerivationEdge] = []

    def introduce(node_id: str, kind: NodeKind | None, time: int | None) -> None:
        if node_id not in nodes_by_id:
            nodes_by_id[node_id] = LineageNode(node_id=node_id, kind=kind, first_seen_time=time)

    records = [DisclosureRecord.from_mapping(r) for r in disclosures]
    transform_specs = [TransformSpec.from_mapping(t) for t in (transforms or ())]

    # Declared roots: trusted origins (original fields/records). Roots are the
    # ONLY way a parent-only node becomes part of the graph.
    declared_roots: dict[str, LineageNode] = {}
    for root in roots or ():
        if isinstance(root, Mapping):
            nid = root.get("node_id")
            kind = root.get("kind")
            time = root.get("first_seen_time")
        else:
            nid, kind, time = root, None, None
        _validate_node_id(nid)
        if kind is not None and kind not in NODE_KINDS:
            raise LineageGraphError(f"{REASON_NODE_MALFORMED}: unknown node_kind {kind!r}")
        if time is not None and (isinstance(time, bool) or not isinstance(time, int) or time < 0):
            raise LineageGraphError(
                f"{REASON_EDGE_MALFORMED}: root first_seen_time must be a non-negative integer"
            )
        if nid not in declared_roots:
            declared_roots[nid] = LineageNode(node_id=nid, kind=kind, first_seen_time=time)

    # Missing-ancestor validation: every derivation parent must be either an
    # output/child introduced by some record/transform or a declared root.
    child_ids = {rec.item_id for rec in records}
    child_ids.update(out for spec in transform_specs for out in spec.output_nodes)
    for rec in records:
        if rec.created_by not in child_ids and rec.created_by not in declared_roots:
            raise LineageGraphError(
                f"{REASON_EDGE_UNKNOWN_ANCESTOR}: record {rec.item_id!r} derives from "
                f"unknown ancestor {rec.created_by!r} (not a child anywhere, not a declared root)"
            )
    for spec in transform_specs:
        for input_node in spec.input_nodes:
            if input_node not in child_ids and input_node not in declared_roots:
                raise LineageGraphError(
                    f"{REASON_EDGE_UNKNOWN_ANCESTOR}: transform {spec.transform_id!r} consumes "
                    f"unknown ancestor {input_node!r} (not a child anywhere, not a declared root)"
                )

    # Introduce nodes: roots first (trusted origins), then record endpoints.
    for nid, node in declared_roots.items():
        introduce(nid, node.kind, node.first_seen_time)
    for rec in records:
        introduce(
            rec.created_by,
            None if rec.created_by not in declared_roots else declared_roots[rec.created_by].kind,
            rec.time,
        )
        introduce(rec.item_id, rec.node_kind, rec.time)
    for spec in transform_specs:
        for nid in (*spec.input_nodes, *spec.output_nodes):
            introduce(nid, None, None)

    # Edges.
    for rec in records:
        edges.append(
            DerivationEdge(
                parent=rec.created_by,
                child=rec.item_id,
                principal=rec.principal,
                purpose=rec.purpose,
                time=rec.time,
                transform=rec.transform,
                digest=None,
            )
        )
    for spec in transform_specs:
        for input_node in spec.input_nodes:
            for output_node in spec.output_nodes:
                edges.append(
                    DerivationEdge(
                        parent=input_node,
                        child=output_node,
                        principal=None,
                        purpose=None,
                        time=None,
                        transform=spec.transform_id,
                        digest=spec.digest,
                    )
                )

    # Cycle validation (task contract: validate cycles and missing ancestors).
    _reject_cycles(nodes_by_id, edges)

    normalized_edges = tuple(sorted(edges, key=_edge_sort_key))
    normalized_nodes = tuple(nodes_by_id[nid] for nid in sorted(nodes_by_id))
    return LineageGraph(nodes=normalized_nodes, edges=normalized_edges)


# ---------------------------------------------------------------------------
# Revocation-completeness audit
# ---------------------------------------------------------------------------


def assert_revocation_complete(
    graph: LineageGraph,
    node: str,
    closure: Iterable[str],
    scope: RevocationScope | None = None,
) -> None:
    """Prove ``closure`` covers EVERY reachable descendant of ``node``.

    Re-walks the reachable subgraph from ``node`` independently of the
    candidate closure (full unfiltered reachability when ``scope`` is None;
    scope-filtered reachability otherwise) and raises
    ``REVOCATION_CLOSURE_INCOMPLETE`` listing the missed descendants — the
    adversarial "missed descendant" leak class (RQ1) is thus detectable by
    construction, never silently accepted. The node itself must be in the
    closure too (revocation removes the origin as well).
    """
    if not isinstance(graph, LineageGraph):
        raise LineageGraphError(f"{REASON_EDGE_MALFORMED}: graph must be a LineageGraph")
    required = (
        {node, *graph.descendants(node)}
        if scope is None
        else set(graph.revocation_closure(node, scope))
    )
    supplied = {str(x) for x in closure}
    missing = sorted(required - supplied)
    if missing:
        raise LineageGraphError(
            f"{REASON_REVOCATION_CLOSURE_INCOMPLETE}: closure misses reachable "
            f"descendants: {missing}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opt_str(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise LineageGraphError(f"{REASON_NODE_MALFORMED}: {field} must be a non-empty string")
    return value


def _str_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple | set | frozenset):
        raise LineageGraphError(f"{REASON_EDGE_MALFORMED}: {field} must be an array")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise LineageGraphError(
                f"{REASON_EDGE_MALFORMED}: {field} entries must be non-empty strings"
            )
        out.append(item)
    return tuple(out)


def _validate_node_id(node_id: Any) -> None:
    if not isinstance(node_id, str) or not node_id:
        raise LineageGraphError(f"{REASON_NODE_MALFORMED}: node id must be a non-empty string")


def _edge_in_scope(edge: DerivationEdge, scope: RevocationScope) -> bool:
    """Edge matches the revoked scope iff principal matches AND purpose matches.

    An unlabeled edge (no principal/purpose) cannot be shown to be outside the
    revoked scope, so it is treated as in-scope (fail closed — never a silent
    escape hatch). ``purpose == "*"`` (subject-wide withdrawal) matches every
    purpose label, mirroring X05 semantics.
    """
    if edge.principal is None or edge.principal == scope.principal:
        principal_match = True
    else:
        principal_match = False
    if scope.purpose == "*":
        return principal_match
    return principal_match and (edge.purpose is None or edge.purpose == scope.purpose)


def _edge_sort_key(edge: DerivationEdge) -> tuple[str, str, str | None, str | None]:
    return (edge.parent, edge.child, edge.transform, edge.digest)


def _reject_cycles(node_ids: dict[str, LineageNode], edges: list[DerivationEdge]) -> None:
    """Kahn's algorithm cycle detection; reports one concrete cycle path."""
    indegree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    seen_edges: set[tuple[str, str]] = set()
    for edge in edges:
        pair = (edge.parent, edge.child)
        if pair in seen_edges:
            continue
        seen_edges.add(pair)
        adjacency[edge.parent].append(edge.child)
        indegree[edge.child] += 1
    queue = sorted(nid for nid, deg in indegree.items() if deg == 0)
    processed = 0
    while queue:
        current = queue.pop()
        processed += 1
        for child in adjacency[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if processed != len(node_ids):
        remaining = sorted(nid for nid, deg in indegree.items() if deg > 0)
        cycle_path = _find_cycle_path(remaining, adjacency)
        raise LineageGraphError(
            f"{REASON_EDGE_CYCLE}: derivation cycle detected among {remaining}"
            + (f" (path: {' -> '.join(cycle_path)})" if cycle_path else "")
        )


def _find_cycle_path(remaining: list[str], adjacency: dict[str, list[str]]) -> list[str]:
    """Extract one concrete cycle path among ``remaining`` nodes."""
    remaining_set = set(remaining)
    for start in remaining:
        path: list[str] = [start]
        pos: dict[str, int] = {start: 0}
        current = start
        while True:
            nexts = [c for c in adjacency.get(current, []) if c in remaining_set]
            if not nexts:
                break
            nxt = sorted(nexts)[0]
            if nxt in pos:
                return path[pos[nxt] :] + [nxt]
            pos[nxt] = len(path)
            path.append(nxt)
            current = nxt
    return []
