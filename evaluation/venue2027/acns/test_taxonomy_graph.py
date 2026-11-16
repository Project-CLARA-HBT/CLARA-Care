"""Tests for ACNS-X08_taxonomy_graph — evidence taxonomy graph and path validation.

Positive controls:
- Loads YAML taxonomy specification into structured TaxonomyGraph
- Builds valid directed acyclic graph (DAG) with correct node and edge counts
- Validates supported evidence paths (both direct and multi-hop)
- Reports counterexamples and missing assumptions for invalid transitions
- Exports machine-readable JSON representation adhering to contract schema
- Renders graph as valid SVG visualization

Adversarial controls:
- Cycles detected: cycle introduction raises CYCLE_DETECTED and is detected by DFS
- Unsupported jumps rejected: multi-level unbacked transitions fail closed
- Reverse directional implications rejected: avoids implication without evidence
- Invalid node ID raises stable reason-coded TaxonomyGraphError(INVALID_NODE_ID)
- Malformed taxonomy specification raises TaxonomyGraphError(MALFORMED_TAXONOMY)
"""

from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from evaluation.venue2027.acns.taxonomy_graph import (
    CONTRACT_ID,
    SCHEMA_VERSION,
    TAXONOMY_GRAPH_VERSION,
    PathValidityResult,
    TaxonomyEdge,
    TaxonomyGraph,
    TaxonomyGraphError,
    TaxonomyNode,
    build_taxonomy_graph,
    emit_taxonomy_graph,
    export_graph,
    render_graph,
    validate_evidence_path,
    validate_transition,
)


@pytest.fixture
def taxonomy_graph() -> TaxonomyGraph:
    """Fixture returning the canonical evidence taxonomy graph."""
    return build_taxonomy_graph()


# ---------------------------------------------------------------------------
# Positive Controls
# ---------------------------------------------------------------------------


def test_load_yaml_taxonomy(taxonomy_graph: TaxonomyGraph) -> None:
    """Graph loads from YAML and contains all mandated lattice levels and classes."""
    assert len(taxonomy_graph.nodes) == 6
    assert len(taxonomy_graph.edges) == 10
    assert all(isinstance(node, TaxonomyNode) for node in taxonomy_graph.nodes.values())

    expected_levels = [
        "ASSUMED",
        "ASSEMBLED",
        "DISPATCHED",
        "ACKNOWLEDGED",
        "EXECUTED",
        "COMMITTED",
    ]
    actual_levels = [node.level for node in taxonomy_graph.nodes.values()]
    assert actual_levels == expected_levels

    # Node IDs match standard N0-N5 convention
    expected_ids = {
        "N0_ASSUMED",
        "N1_ASSEMBLED",
        "N2_DISPATCHED",
        "N3_ACKNOWLEDGED",
        "N4_EXECUTED",
        "N5_COMMITTED",
    }
    assert set(taxonomy_graph.nodes.keys()) == expected_ids

    # 4 valid edges, 6 invalid edges
    valid_edges = [e for e in taxonomy_graph.edges.values() if e.is_valid]
    invalid_edges = [e for e in taxonomy_graph.edges.values() if not e.is_valid]
    assert len(valid_edges) == 4
    assert len(invalid_edges) == 6


def test_build_valid_directed_graph(taxonomy_graph: TaxonomyGraph) -> None:
    """Graph represents a valid directed acyclic graph without cycles."""
    assert not taxonomy_graph.has_cycle()
    assert taxonomy_graph.detect_cycles() == []
    # assert_acyclic does not raise
    taxonomy_graph.assert_acyclic()

    # Node retrieval by full ID, level, and short prefix
    node_n0 = taxonomy_graph.get_node("N0_ASSUMED")
    assert node_n0.id == "N0_ASSUMED"
    assert node_n0.node_class == "sender_known_bytes"
    assert "rfc9334" in node_n0.citations

    node_by_level = taxonomy_graph.get_node("DISPATCHED")
    assert node_by_level.id == "N2_DISPATCHED"

    node_by_prefix = taxonomy_graph.get_node("N3")
    assert node_by_prefix.id == "N3_ACKNOWLEDGED"

    # Node properties populated
    for node in taxonomy_graph.nodes.values():
        assert len(node.definition) > 10
        assert len(node.trust_root) > 10
        assert len(node.observer_location) > 10
        assert len(node.proves) > 10
        assert len(node.does_not_prove) > 10
        assert len(node.citations) >= 1


def test_validates_supported_evidence_paths(taxonomy_graph: TaxonomyGraph) -> None:
    """Valid evidence paths evaluate to is_valid=True with reason_code VALID_PATH."""
    # Direct valid transition N0 -> N1
    res_01 = validate_evidence_path(taxonomy_graph, "N0_ASSUMED", "N1_ASSEMBLED")
    assert res_01.is_valid
    assert res_01.reason_code == "VALID_PATH"
    assert res_01.edge_ids == ["E01_assumed_to_assembled"]

    # Direct valid transition N1 -> N2
    res_12 = validate_evidence_path(taxonomy_graph, "N1_ASSEMBLED", "N2_DISPATCHED")
    assert res_12.is_valid
    assert res_12.reason_code == "VALID_PATH"
    assert res_12.edge_ids == ["E02_assembled_to_dispatched"]

    # Multi-hop valid transition N0 -> N1 -> N2
    res_02 = validate_evidence_path(taxonomy_graph, "N0_ASSUMED", "N2_DISPATCHED")
    assert res_02.is_valid
    assert res_02.reason_code == "VALID_PATH"
    assert res_02.path == ["N0_ASSUMED", "N1_ASSEMBLED", "N2_DISPATCHED"]
    assert res_02.edge_ids == ["E01_assumed_to_assembled", "E02_assembled_to_dispatched"]

    # Multi-hop valid transition N3 -> N4 -> N5 (under TEE + persisted record)
    res_35 = validate_evidence_path(taxonomy_graph, "N3_ACKNOWLEDGED", "N5_COMMITTED")
    assert res_35.is_valid
    assert res_35.reason_code == "VALID_PATH"
    assert res_35.path == ["N3_ACKNOWLEDGED", "N4_EXECUTED", "N5_COMMITTED"]
    assert res_35.edge_ids == [
        "E09_receipt_tee_to_execution",
        "E10_execution_record_to_committed",
    ]

    # Same node is valid trivially
    res_same = validate_evidence_path(taxonomy_graph, "N2_DISPATCHED", "N2_DISPATCHED")
    assert res_same.is_valid
    assert res_same.reason_code == "SAME_NODE"
    assert res_same.path == ["N2_DISPATCHED"]


def test_reports_counterexamples_for_invalid_transitions(taxonomy_graph: TaxonomyGraph) -> None:
    """Invalid transitions are rejected and report counterexamples and missing gaps."""
    # E03: N2 -> N3 (bare transport acknowledgment to receipt)
    res_e03 = validate_evidence_path(taxonomy_graph, "N2_DISPATCHED", "N3_ACKNOWLEDGED")
    assert not res_e03.is_valid
    assert res_e03.reason_code == "INVALID_TRANSITION"
    assert "dispatched-not-acknowledged" in res_e03.counterexample_ids
    assert "G1" in res_e03.gaps
    assert res_e03.failure_families == ["replay"]
    assert len(res_e03.missing_assumptions) > 0

    # E04: N3 -> N4 without TEE
    res_e04 = validate_transition(taxonomy_graph, "E04_receipt_to_execution")
    assert not res_e04.is_valid
    assert res_e04.reason_code == "INVALID_TRANSITION"
    assert "acknowledged-not-executed" in res_e04.counterexample_ids
    assert "G2" in res_e04.gaps
    assert res_e04.failure_families == ["model_agency"]

    # E05: N4 -> N5 without durable store record
    res_e05 = validate_transition(taxonomy_graph, "E05_execution_to_committed")
    assert not res_e05.is_valid
    assert res_e05.reason_code == "INVALID_TRANSITION"
    assert "executed-not-committed" in res_e05.counterexample_ids
    assert "G3" in res_e05.gaps
    assert res_e05.failure_families == ["model_agency"]

    # E06: N2 -> N4 (transport to inference composite)
    res_e06 = validate_evidence_path(taxonomy_graph, "N2_DISPATCHED", "N4_EXECUTED")
    assert not res_e06.is_valid
    assert "NC2_transport_ack_implies_inference" in res_e06.counterexample_ids
    assert "G1" in res_e06.gaps
    assert "G2" in res_e06.gaps

    # E07: N1 -> N4 (hash-only token presented as hardware attestation)
    res_e07 = validate_evidence_path(taxonomy_graph, "N1_ASSEMBLED", "N4_EXECUTED")
    assert not res_e07.is_valid
    assert "NC1_hash_only_token_miscalled_hardware_attestation" in res_e07.counterexample_ids
    assert "G7" in res_e07.gaps
    assert "assembled-not-sent" in res_e07.counterexample_ids

    # E08: N3 -> N5 (receipt to committed composite)
    res_e08 = validate_transition(taxonomy_graph, "E08_receipt_to_committed")
    assert not res_e08.is_valid
    assert "G2" in res_e08.gaps
    assert "G3" in res_e08.gaps


def test_machine_readable_json_export(taxonomy_graph: TaxonomyGraph) -> None:
    """Machine-readable export produces schema-conforming JSON dictionary."""
    exported = export_graph(taxonomy_graph)
    assert exported["contract"] == CONTRACT_ID
    assert exported["schema_version"] == SCHEMA_VERSION
    assert exported["graph_version"] == TAXONOMY_GRAPH_VERSION
    assert len(exported["nodes"]) == 6
    assert len(exported["edges"]) == 10
    assert exported["summary"]["total_nodes"] == 6
    assert exported["summary"]["total_edges"] == 10
    assert exported["summary"]["valid_edges"] == 4
    assert exported["summary"]["invalid_edges"] == 6
    assert not exported["summary"]["has_cycles"]

    # Check serialization round-trip
    serialized = json.dumps(exported)
    deserialized = json.loads(serialized)
    assert deserialized["contract"] == CONTRACT_ID

    # Emit to temporary file
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = pathlib.Path(tmp_dir) / "taxonomy_graph.json"
        written = emit_taxonomy_graph(run_id="test-run", out_path=out_file)
        assert written.is_file()
        on_disk = json.loads(written.read_text(encoding="utf-8"))
        assert on_disk["summary"]["total_nodes"] == 6


def test_render_graph_svg(taxonomy_graph: TaxonomyGraph) -> None:
    """SVG rendering produces valid XML/SVG with markers and annotations."""
    # Render from graph object
    svg_from_graph = render_graph(graph=taxonomy_graph)
    assert svg_from_graph.startswith("<svg")
    assert svg_from_graph.strip().endswith("</svg>")
    assert 'marker id="arrow-valid"' in svg_from_graph
    assert 'marker id="arrow-invalid"' in svg_from_graph
    assert "N0_ASSUMED" in svg_from_graph or "N0" in svg_from_graph
    assert "E01" in svg_from_graph

    # Render with explicit lists
    svg_explicit = render_graph(
        evidence_types=list(taxonomy_graph.nodes.values()),
        edges=list(taxonomy_graph.edges.values()),
    )
    assert svg_explicit.startswith("<svg")
    assert svg_explicit.strip().endswith("</svg>")


# ---------------------------------------------------------------------------
# Adversarial Controls
# ---------------------------------------------------------------------------


def test_cycles_detected(taxonomy_graph: TaxonomyGraph) -> None:
    """Cycles introduced into the graph are detected and rejected."""
    # Adding an edge that creates a cycle N5 -> N0
    cyclic_edge = TaxonomyEdge(
        id="E_cycle_test",
        from_node="N5_COMMITTED",
        to_node="N0_ASSUMED",
        claim="Cyclic back-edge test",
        status="valid",
        is_valid=True,
        trust_assumptions="Invalid assumption creating loop",
        boundary_condition="Cycle violation",
        failure_family="cycle",
    )

    # Adding with check_cycle=True raises TaxonomyGraphError
    with pytest.raises(TaxonomyGraphError) as exc_info:
        taxonomy_graph.add_edge(cyclic_edge, check_cycle=True)
    assert exc_info.value.reason_code == "CYCLE_DETECTED"
    assert "introduces a cycle" in str(exc_info.value)

    # Adding directly without check_cycle, then verifying graph-level detection
    taxonomy_graph.add_edge(cyclic_edge, check_cycle=False)
    assert taxonomy_graph.has_cycle()
    cycles = taxonomy_graph.detect_cycles()
    assert len(cycles) > 0
    assert any("N5_COMMITTED" in cyc and "N0_ASSUMED" in cyc for cyc in cycles)

    with pytest.raises(TaxonomyGraphError) as exc_assert:
        taxonomy_graph.assert_acyclic()
    assert exc_assert.value.reason_code == "CYCLE_DETECTED"

    # Path validation on cyclic graph flags CYCLE_DETECTED
    res_cyc = validate_evidence_path(taxonomy_graph, "N0_ASSUMED", "N5_COMMITTED")
    assert not res_cyc.is_valid
    assert res_cyc.reason_code == "CYCLE_DETECTED"


def test_unsupported_jumps_rejected(taxonomy_graph: TaxonomyGraph) -> None:
    """Unsupported multi-level jumps without proof are rejected fail-closed."""
    # Jumping from N0 to N5 (full lattice jump across N2->N3 unbridged gap)
    res_05 = validate_evidence_path(taxonomy_graph, "N0_ASSUMED", "N5_COMMITTED")
    assert not res_05.is_valid
    assert res_05.reason_code == "UNSUPPORTED_JUMP"
    assert len(res_05.counterexample_ids) > 0
    assert len(res_05.missing_assumptions) > 0

    # Jumping from N2 to N5 (transport to commit without receipt or execution)
    res_25 = validate_evidence_path(taxonomy_graph, "N2_DISPATCHED", "N5_COMMITTED")
    assert not res_25.is_valid
    assert res_25.reason_code in ("UNSUPPORTED_JUMP", "INVALID_TRANSITION")
    assert len(res_25.missing_assumptions) > 0


def test_reverse_directional_implications_rejected(taxonomy_graph: TaxonomyGraph) -> None:
    """Reverse directional implication without evidence is strictly rejected."""
    # N5 to N0 (committed cannot imply assumed intent without explicit backward evidence)
    res_rev_50 = validate_evidence_path(taxonomy_graph, "N5_COMMITTED", "N0_ASSUMED")
    assert not res_rev_50.is_valid
    assert res_rev_50.reason_code == "NO_PATH_EXISTS"
    assert "No implication path exists" in res_rev_50.message

    # N4 to N2
    res_rev_42 = validate_evidence_path(taxonomy_graph, "N4_EXECUTED", "N2_DISPATCHED")
    assert not res_rev_42.is_valid
    assert res_rev_42.reason_code == "NO_PATH_EXISTS"

    # N3 to N1
    res_rev_31 = validate_evidence_path(taxonomy_graph, "N3_ACKNOWLEDGED", "N1_ASSEMBLED")
    assert not res_rev_31.is_valid
    assert res_rev_31.reason_code == "NO_PATH_EXISTS"


def test_invalid_node_id_raises_error(taxonomy_graph: TaxonomyGraph) -> None:
    """Invalid or nonexistent node identifiers raise TaxonomyGraphError(INVALID_NODE_ID)."""
    with pytest.raises(TaxonomyGraphError) as exc_src:
        validate_evidence_path(taxonomy_graph, "NONEXISTENT_NODE", "N1_ASSEMBLED")
    assert exc_src.value.reason_code == "INVALID_NODE_ID"

    with pytest.raises(TaxonomyGraphError) as exc_dst:
        validate_evidence_path(taxonomy_graph, "N0_ASSUMED", "UNKNOWN_TARGET")
    assert exc_dst.value.reason_code == "INVALID_NODE_ID"

    with pytest.raises(TaxonomyGraphError) as exc_get:
        taxonomy_graph.get_node("INVALID_ID")
    assert exc_get.value.reason_code == "INVALID_NODE_ID"

    # Invalid node in edge creation
    bad_edge = TaxonomyEdge(
        id="E_bad",
        from_node="INVALID_NODE",
        to_node="N1_ASSEMBLED",
        claim="bad",
        status="valid",
        is_valid=True,
        trust_assumptions="none",
        boundary_condition="none",
        failure_family="none",
    )
    with pytest.raises(TaxonomyGraphError) as exc_edge:
        taxonomy_graph.add_edge(bad_edge)
    assert exc_edge.value.reason_code == "INVALID_NODE_ID"


def test_malformed_taxonomy_raises_error() -> None:
    """Nonexistent or malformed taxonomy specification raises TaxonomyGraphError."""
    # Nonexistent file
    with pytest.raises(TaxonomyGraphError) as exc_missing:
        build_taxonomy_graph("/tmp/nonexistent_taxonomy_file.yaml")
    assert exc_missing.value.reason_code == "MALFORMED_TAXONOMY"

    # Malformed YAML without required keys
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        tmp.write("invalid_root:\n  some_key: 123\n")
        tmp_path = pathlib.Path(tmp.name)

    try:
        with pytest.raises(TaxonomyGraphError) as exc_malformed:
            build_taxonomy_graph(tmp_path)
        assert exc_malformed.value.reason_code == "MALFORMED_TAXONOMY"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_path_validity_result_dataclass() -> None:
    """PathValidityResult serializes cleanly to dict."""
    res = PathValidityResult(
        is_valid=True,
        from_node="N0_ASSUMED",
        to_node="N1_ASSEMBLED",
        path=["N0_ASSUMED", "N1_ASSEMBLED"],
        edge_ids=["E01"],
        edges=[],
        counterexample_ids=[],
        missing_assumptions=[],
        failure_families=[],
        gaps=[],
        reason_code="VALID_PATH",
        message="Valid path",
    )
    d = res.to_dict()
    assert d["is_valid"] is True
    assert d["reason_code"] == "VALID_PATH"
    assert json.dumps(d)
