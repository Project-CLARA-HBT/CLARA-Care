"""Tests for POPETS-X01_lineage_graph (context-lineage graph + revocation closure).

Positive controls (must pass):
- ``derive_graph(disclosures, transforms)`` builds a typed, JSON-serializable
  ``LineageGraph`` with nodes (origin field, derived summary, cache object,
  retry payload, provider transport) and labeled derivation edges
  (principal/purpose/time/transform digest).
- Transitive descent along a linear chain A -> B -> C -> D: ``descendants(A)``
  returns ALL of B, C, D (multi-hop derived medication fact shape).
- Revocation closure of the chain origin is complete: origin + every
  transitively derived item, in deterministic sorted order.
- Scope-filtered closure (principal, purpose) follows only in-scope edges;
  the wildcard subject-wide revocation ("*") covers every purpose.
- ``assert_revocation_complete`` accepts a complete closure (proving zero
  transitive survivors) and is deterministic across repeated runs.
- Transform descriptors (multi-input/multi-output with digests) contribute
  derivation edges; diamond-shaped fan-out/fan-in closure is complete.
- JSON round-trip of every typed object; determinism (same inputs ->
  byte-equal serialization; no hidden clock/randomness).

Adversarial controls (must be refused / fail closed, never silently accepted):
- A derivation cycle is refused at construction (EDGE_CYCLE) and traversal
  helpers remain cycle-safe (no infinite loop) — a graph that validates clean
  can never hang ``descendants``/``revocation_closure``.
- An edge referencing an unknown ancestor is refused
  (EDGE_UNKNOWN_ANCESTOR — unlinked derivative, POPETS-CASE-07 shape).
- A MISSED descendant is detected by ``assert_revocation_complete``: a closure
  that forgets a transitive item raises REVOCATION_CLOSURE_INCOMPLETE naming
  the missed node (the RQ1 leak class is detectable, never silently purged
  or silently accepted).
- Malformed records (empty item_id, missing created_by, ill-typed time) raise
  stable uppercase reason codes, never unhandled exceptions.
- The node itself must be part of its own revocation closure.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.popets.lineage_graph import (
    LINEAGE_GRAPH_VERSION,
    REASON_EDGE_CYCLE,
    REASON_EDGE_MALFORMED,
    REASON_EDGE_UNKNOWN_ANCESTOR,
    REASON_REVOCATION_CLOSURE_INCOMPLETE,
    DisclosureRecord,
    LineageGraph,
    LineageGraphError,
    RevocationScope,
    assert_revocation_complete,
    derive_graph,
)

# ---------------------------------------------------------------------------
# Fixtures (synthetic structural placeholders; no PHI, no clock, no network)
# ---------------------------------------------------------------------------

CHAIN_DISCLOSURES = [
    # origin field -> derived summary -> cache object -> retry payload
    {
        "item_id": "summary_vitals_1",
        "created_by": "field_vitals_2026_01",
        "principal": "subj-1",
        "purpose": "clinical",
        "time": 11,
        "transform": "summarize",
        "node_kind": "derived_summary",
    },
    {
        "item_id": "cache_summary_v1",
        "created_by": "summary_vitals_1",
        "principal": "subj-1",
        "purpose": "clinical",
        "time": 12,
        "transform": "cache_write",
        "node_kind": "cache_object",
    },
    {
        "item_id": "retry_payload_1",
        "created_by": "cache_summary_v1",
        "principal": "subj-1",
        "purpose": "clinical",
        "time": 13,
        "transform": "retry_enqueue",
        "node_kind": "retry_payload",
    },
    {
        "item_id": "transport_outbound_1",
        "created_by": "retry_payload_1",
        "principal": "subj-1",
        "purpose": "clinical",
        "time": 14,
        "transform": "transport_send",
        "node_kind": "provider_transport",
    },
]


def _chain_graph() -> LineageGraph:
    return derive_graph(CHAIN_DISCLOSURES, roots=["field_vitals_2026_01"])


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_derive_graph_returns_typed_json_serializable_graph() -> None:
    graph = _chain_graph()
    assert isinstance(graph, LineageGraph)
    node_ids = {n.node_id for n in graph.nodes}
    assert "field_vitals_2026_01" in node_ids  # origin introduced as parent
    kinds = {n.node_id: n.kind for n in graph.nodes}
    assert kinds["summary_vitals_1"] == "derived_summary"
    assert kinds["cache_summary_v1"] == "cache_object"
    assert kinds["retry_payload_1"] == "retry_payload"
    assert kinds["transport_outbound_1"] == "provider_transport"
    # edges carry the principal/purpose/time/transform label tuple
    edge = next(e for e in graph.edges if e.child == "retry_payload_1")
    assert edge.parent == "cache_summary_v1"
    assert edge.principal == "subj-1"
    assert edge.purpose == "clinical"
    assert edge.time == 13
    assert edge.transform == "retry_enqueue"
    # JSON-serializable
    payload = json.dumps(
        graph.to_dict()
        if hasattr(graph, "to_dict")
        else {
            "nodes": [n.to_dict() for n in graph.nodes],
            "edges": [e.to_dict() for e in graph.edges],
        }
    )
    assert "retry_payload_1" in payload


def test_transitive_descent_linear_chain_returns_all_descendants() -> None:
    graph = _chain_graph()
    assert graph.descendants("field_vitals_2026_01") == (
        "cache_summary_v1",
        "retry_payload_1",
        "summary_vitals_1",
        "transport_outbound_1",
    )
    # mid-chain descent is transitive from that point only
    assert graph.descendants("summary_vitals_1") == (
        "cache_summary_v1",
        "retry_payload_1",
        "transport_outbound_1",
    )
    # a leaf has no descendants
    assert graph.descendants("transport_outbound_1") == ()


def test_revocation_closure_complete_on_chain() -> None:
    graph = _chain_graph()
    closure = graph.revocation_closure("field_vitals_2026_01")
    # origin itself + ALL transitive descendants, deterministic sorted order
    assert closure == (
        "cache_summary_v1",
        "field_vitals_2026_01",
        "retry_payload_1",
        "summary_vitals_1",
        "transport_outbound_1",
    )
    # purge-complete: every reachable descendant is inside the closure
    assert set(graph.descendants("field_vitals_2026_01")) <= set(closure)
    # audit accepts the complete closure (zero transitive survivors)
    assert_revocation_complete(graph, "field_vitals_2026_01", closure)


def test_scope_filtered_closure_and_subject_wide_wildcard() -> None:
    disclosures = [
        *CHAIN_DISCLOSURES,
        # a derivative built under a DIFFERENT purpose off the same origin
        {
            "item_id": "analytics_rollup_1",
            "created_by": "field_vitals_2026_01",
            "principal": "subj-1",
            "purpose": "analytics",
            "time": 15,
            "transform": "aggregate",
            "node_kind": "derived_summary",
        },
    ]
    graph = derive_graph(
        disclosures,
        roots=["field_vitals_2026_01"],
    )
    clinical = graph.revocation_closure(
        "field_vitals_2026_01", RevocationScope(principal="subj-1", purpose="clinical")
    )
    assert "cache_summary_v1" in clinical and "retry_payload_1" in clinical
    assert "analytics_rollup_1" not in clinical  # other purpose stays out of this closure
    wildcard = graph.revocation_closure(
        "field_vitals_2026_01", RevocationScope(principal="subj-1", purpose="*")
    )
    assert "analytics_rollup_1" in wildcard  # subject-wide withdrawal covers it
    assert set(wildcard) == {"field_vitals_2026_01", *graph.descendants("field_vitals_2026_01")}


def test_transform_spec_diamond_fanout_fanin_closure_complete() -> None:
    graph = derive_graph(
        [
            {
                "item_id": "summary_a",
                "created_by": "field_x",
                "principal": "subj-1",
                "purpose": "clinical",
                "time": 11,
                "node_kind": "derived_summary",
            },
            {
                "item_id": "summary_b",
                "created_by": "field_x",
                "principal": "subj-1",
                "purpose": "clinical",
                "time": 12,
                "node_kind": "derived_summary",
            },
            {
                "item_id": "merged_cache",
                "created_by": "summary_a",
                "principal": "subj-1",
                "purpose": "clinical",
                "time": 13,
                "transform": "merge",
                "node_kind": "cache_object",
            },
        ],
        roots=["field_x"],
        transforms=[
            {
                "transform_id": "merge_digest",
                "digest": "sha256:deadbeef",
                "input_nodes": ["summary_a", "summary_b"],
                "output_nodes": ["merged_cache"],
            }
        ],
    )
    assert graph.descendants("field_x") == ("merged_cache", "summary_a", "summary_b")
    closure = graph.revocation_closure("field_x")
    assert set(closure) == {"field_x", "merged_cache", "summary_a", "summary_b"}
    assert_revocation_complete(graph, "field_x", closure)
    digest_edges = [e for e in graph.edges if e.digest == "sha256:deadbeef"]
    edge = sorted(digest_edges, key=lambda e: e.parent)[0]
    assert edge.parent == "summary_a" and edge.child == "merged_cache"


def test_determinism_and_json_round_trip() -> None:
    g1 = _chain_graph()
    g2 = _chain_graph()
    assert json.dumps([n.to_dict() for n in g1.nodes]) == json.dumps(
        [n.to_dict() for n in g2.nodes]
    )
    assert json.dumps([e.to_dict() for e in g1.edges]) == json.dumps(
        [e.to_dict() for e in g2.edges]
    )
    record = DisclosureRecord.from_mapping(CHAIN_DISCLOSURES[0])
    assert DisclosureRecord.from_mapping(record.to_dict()) == record


def test_graph_error_is_value_error_with_version_constant() -> None:
    assert issubclass(LineageGraphError, ValueError)
    assert LINEAGE_GRAPH_VERSION == "1.0.0"


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_cycle_is_refused_at_construction() -> None:
    with pytest.raises(LineageGraphError) as excinfo:
        derive_graph(
            [
                {"item_id": "a", "created_by": "c"},
                {"item_id": "b", "created_by": "a"},
                {"item_id": "c", "created_by": "b"},  # c -> a -> b -> c
            ]
        )
    assert REASON_EDGE_CYCLE in str(excinfo.value)


def test_traversals_are_cycle_safe_without_infinite_loop() -> None:
    # Build a graph whose internal adjacency contains a cycle by injecting a
    # pre-built cycle-containing graph object directly (bypassing the
    # constructor-time rejection) to prove traversal-level cycle safety.
    cycled = derive_graph(
        [
            {"item_id": "b", "created_by": "a"},
            {"item_id": "d", "created_by": "c"},
        ],
        roots=["a", "c"],
    )
    injected = LineageGraph(
        nodes=cycled.nodes,
        edges=(
            *cycled.edges,
            # back edge b -> a closes the cycle a -> b -> a
            type(cycled.edges[0])(
                parent="b", child="a", principal=None, purpose=None, time=None, transform="corrupt"
            ),
            # cross link b -> c so the whole structure is one cycle-touching component
            type(cycled.edges[0])(
                parent="b", child="c", principal=None, purpose=None, time=None, transform="cross"
            ),
        ),
    )
    # Must terminate (no RecursionError, no hang) and return all reachable nodes
    # (descendants excludes the origin itself; the closure includes it).
    assert set(injected.descendants("a")) == {"b", "c", "d"}
    closure = injected.revocation_closure("a")
    assert set(closure) == {"a", "b", "c", "d"}
    # cycle-safe traversal also terminates for the audit helper
    assert_revocation_complete(injected, "a", closure)


def test_unknown_ancestor_is_refused() -> None:
    # An unlinked derivative whose parent is neither a child anywhere nor a
    # declared root is refused (POPETS-CASE-07 shape: unknown ancestry).
    with pytest.raises(LineageGraphError) as excinfo:
        derive_graph(
            [
                {
                    "item_id": "orphan_summary",
                    "created_by": "nonexistent_origin",
                    "principal": "subj-1",
                    "purpose": "clinical",
                }
            ]
        )
    assert REASON_EDGE_UNKNOWN_ANCESTOR in str(excinfo.value)
    # the same parent IS accepted once declared as a trusted root
    ok_graph = derive_graph(
        [{"item_id": "orphan_summary", "created_by": "nonexistent_origin"}],
        roots=["nonexistent_origin"],
    )
    assert ok_graph.has_node("orphan_summary")
    # a transform consuming an unknown ancestor is refused too
    with pytest.raises(LineageGraphError) as excinfo2:
        derive_graph(
            [{"item_id": "s1", "created_by": "root_a"}],
            roots=["root_a"],
            transforms=[
                {
                    "transform_id": "t1",
                    "digest": "d1",
                    "input_nodes": ["ghost"],
                    "output_nodes": ["s1"],
                }
            ],
        )
    assert REASON_EDGE_UNKNOWN_ANCESTOR in str(excinfo2.value)


def test_unknown_node_query_fails_closed() -> None:
    graph = _chain_graph()
    with pytest.raises(LineageGraphError) as excinfo:
        graph.descendants("ghost_node")
    assert REASON_EDGE_UNKNOWN_ANCESTOR in str(excinfo.value)
    with pytest.raises(LineageGraphError):
        graph.revocation_closure("ghost_node")
    assert REASON_EDGE_UNKNOWN_ANCESTOR in str(excinfo.value)


def test_missed_descendant_detected_by_assert_revocation_complete() -> None:
    graph = _chain_graph()
    # An incomplete purge that forgets the DEEPEST transitive item
    # (the retry payload parked in the queue — the canonical RQ1 leak).
    incomplete = ["field_vitals_2026_01", "summary_vitals_1", "cache_summary_v1"]
    with pytest.raises(LineageGraphError) as excinfo:
        assert_revocation_complete(graph, "field_vitals_2026_01", incomplete)
    assert REASON_REVOCATION_CLOSURE_INCOMPLETE in str(excinfo.value)
    assert "retry_payload_1" in str(excinfo.value)
    assert "transport_outbound_1" in str(excinfo.value)
    # A closure missing only the origin itself is also incomplete
    with pytest.raises(LineageGraphError) as excinfo2:
        assert_revocation_complete(
            graph, "field_vitals_2026_01", graph.descendants("field_vitals_2026_01")
        )
    assert REASON_REVOCATION_CLOSURE_INCOMPLETE in str(excinfo2.value)


def test_scope_filtered_missed_descendant_detected() -> None:
    disclosures = [
        *CHAIN_DISCLOSURES,
        {
            "item_id": "analytics_rollup_1",
            "created_by": "field_vitals_2026_01",
            "principal": "subj-1",
            "purpose": "analytics",
            "time": 15,
            "transform": "aggregate",
            "node_kind": "derived_summary",
        },
    ]
    graph = derive_graph(
        disclosures,
        roots=["field_vitals_2026_01"],
    )
    # forgetting the analytics-side branch is caught under the wildcard scope
    with pytest.raises(LineageGraphError) as excinfo:
        assert_revocation_complete(
            graph,
            "field_vitals_2026_01",
            [
                "field_vitals_2026_01",
                "summary_vitals_1",
                "cache_summary_v1",
                "retry_payload_1",
                "transport_outbound_1",
            ],
            scope=RevocationScope(principal="subj-1", purpose="*"),
        )
    assert REASON_REVOCATION_CLOSURE_INCOMPLETE in str(excinfo.value)
    assert "analytics_rollup_1" in str(excinfo.value)


def test_malformed_records_raise_stable_reason_codes() -> None:
    with pytest.raises(LineageGraphError) as excinfo_empty:
        derive_graph([{"item_id": "", "created_by": "x"}])
    assert REASON_EDGE_MALFORMED in str(excinfo_empty.value)
    with pytest.raises(LineageGraphError) as excinfo_no_parent:
        derive_graph([{"item_id": "y"}])
    assert REASON_EDGE_MALFORMED in str(excinfo_no_parent.value)
    with pytest.raises(LineageGraphError) as excinfo_time:
        derive_graph([{"item_id": "y", "created_by": "x", "time": -1}])
    assert REASON_EDGE_MALFORMED in str(excinfo_time.value)
    with pytest.raises(LineageGraphError) as excinfo_kind:
        derive_graph([{"item_id": "y", "created_by": "x", "node_kind": "quantum_state"}])
    assert "NODE_MALFORMED" in str(excinfo_kind.value)
    with pytest.raises(LineageGraphError) as excinfo_transform:
        derive_graph(
            [],
            transforms=[
                {"transform_id": "t", "digest": "d", "input_nodes": [], "output_nodes": ["o"]}
            ],
        )
    assert REASON_EDGE_MALFORMED in str(excinfo_transform.value)
