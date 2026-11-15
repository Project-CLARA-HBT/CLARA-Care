"""Structural gate for ACNS-X03_evidence_taxonomy (evidence-boundary taxonomy).

Purpose
-------
Machine-checks task ``ACNS-X03_evidence_taxonomy`` (venue ``acns``, phase
``P04``) against its deliverable contract: ``research/venue2027/acns/
protocols/evidence_taxonomy.yaml`` must be a pre-registered, machine-checkable
evidence-boundary taxonomy node set for the SoK's evidence-to-claim lattice
(RQ1), distinguishing the five evidence classes -- sender-known bytes,
transport delivery, provider-signed receipt, execution and persisted side
effect -- with, per node: node id, definition, trust root, observer location,
what it proves, what it does NOT prove, and real citations (RFC 9334 RATS,
RFC 9162 transparency, W3C PROV) where relevant. Every edge must declare
trust assumptions. The task's mandated contract levels ``ASSUMED, ASSEMBLED,
DISPATCHED, ACKNOWLEDGED, EXECUTED, COMMITTED`` must all be present, the two
adversarial controls (hash-only token miscalled hardware attestation, false
implication transport->inference) must be registered with REJECT verdicts,
and no node may claim a mechanism: the taxonomy is a SoK coding instrument
claiming no new mechanism, protocol, detector or attestation scheme.

Allowed input
-------------
Read-only access to the taxonomy YAML and the threat-model markdown. No
network, no database, no provider calls, no randomness. Stdlib-only besides
pytest itself: the YAML subset authored here is parsed by a restricted
fallback parser (PyYAML if importable, else the minimal block scanner
below), matching the repository's convention in
``research/venue2027/pst/tests/test_rq_registry.py``.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``ACNS_X03_``; pytest reports the failing check directly.

Version
-------
``ACNS_X03_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import pathlib
import re

ACNS_X03_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
TAXONOMY_PATH = (
    REPO_ROOT / "research" / "venue2027" / "acns" / "protocols" / "evidence_taxonomy.yaml"
)
THREAT_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "threat_model.md"

# --- contract constants ------------------------------------------------------
CONTRACT = "clara.venue2027.acns.evidence-taxonomy.v1"

# The five evidence classes the task mandates distinguishing.
REQUIRED_NODE_CLASSES = (
    "sender_known_bytes",
    "transport_delivery",
    "provider_signed_receipt",
    "execution",
    "persisted_side_effect",
)

# The six lattice levels from the task signature.
REQUIRED_LEVELS = ("ASSUMED", "ASSEMBLED", "DISPATCHED", "ACKNOWLEDGED", "EXECUTED", "COMMITTED")

# Per-node required fields (task contract + blueprint).
REQUIRED_NODE_FIELDS = (
    "id",
    "node_class",
    "level",
    "definition",
    "trust_root",
    "observer_location",
    "proves",
    "does_not_prove",
    "citations",
)

# Per-edge required fields; trust_assumptions is the task's DoD item 1.
REQUIRED_EDGE_FIELDS = (
    "id",
    "from",
    "to",
    "claim",
    "status",
    "trust_assumptions",
    "boundary_condition",
    "failure_family",
)

# Real upstream citations that must appear in the citation registry.
REQUIRED_CITATION_IDS = ("rfc9334", "rfc9162", "w3c_prov_dm")

# Attack families registered by the frozen threat model (§2).
THREAT_FAMILIES = (
    "revocation_timing",
    "replay",
    "model_agency",
    "purpose_scope",
    "insider_or_observer",
)


# ---------------------------------------------------------------------------
# Loader: PyYAML if importable, else a restricted stdlib fallback
# ---------------------------------------------------------------------------
def _load_taxonomy() -> dict:
    text = TAXONOMY_PATH.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]

        data = yaml.safe_load(text)
        assert isinstance(data, dict)
        return data
    except ImportError:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict:
    """Fallback parser for the block-mapping/sequence subset authored here.

    Handles nested block mappings, block sequences of mappings, folded
    scalars (``>-``, ``|`` and inline variants) and inline flow sequences.
    List items under a key are matched by the child indent (>= key indent+1),
    which keeps sibling keys from being swallowed as items.
    """
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    root: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, root)]
    i = 0
    while i < len(lines):
        indent, line = lines[i]
        while stack and indent <= stack[-1][0] and len(stack) > 1:
            stack.pop()
        container = stack[-1][1]
        if line.startswith("- "):
            if not isinstance(container, list):
                i += 1
                continue
            item: dict = {}
            container.append(item)
            body = line[2:].strip()
            if ":" in body:
                key, _, val = body.partition(":")
                if val.strip():
                    item[key.strip()] = _scalar(val.strip())
                stack.append((indent, item))
                i += 1
            else:
                item.setdefault("_item", _scalar(body))
                i += 1
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val in (">-", "|", ">", "|-", ">2", "|2"):
            block: list[str] = []
            i += 1
            block_indent = None
            while i < len(lines):
                ind2, cont2 = lines[i]
                if ind2 <= indent:
                    break
                if block_indent is None:
                    block_indent = ind2
                block.append(cont2 if ind2 <= block_indent else " " * (ind2 - block_indent) + cont2)
                i += 1
            if isinstance(container, dict):
                container[key] = (
                    " ".join(part.strip() for part in " ".join(block).split("\n")).strip()
                )
            continue
        if val == "":
            nxt_indent = lines[i + 1][0] if i + 1 < len(lines) else -1
            nxt = lines[i + 1][1] if i + 1 < len(lines) else ""
            child: dict | list
            if nxt.startswith("- ") and nxt_indent > indent:
                child = []
            else:
                child = {}
            if isinstance(container, dict):
                container[key] = child
                stack.append((indent, child))
            i += 1
            continue
        if isinstance(container, dict):
            container[key] = _scalar(val)
        i += 1
    return root


def _scalar(token: str):
    token = token.strip()
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",")]
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    if token in ("true", "True"):
        return True
    if token in ("false", "False"):
        return False
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return token


TAX = _load_taxonomy()


# ---------------------------------------------------------------------------
# Document-level structure
# ---------------------------------------------------------------------------
def test_taxonomy_exists_and_loads() -> None:
    assert TAXONOMY_PATH.is_file(), "ACNS_X03_DOC: evidence_taxonomy.yaml missing"
    assert isinstance(TAX, dict) and TAX, "ACNS_X03_DOC: taxonomy did not parse to a mapping"


def test_contract_and_schema_version_declared() -> None:
    assert TAX.get("contract") == CONTRACT, (
        f"ACNS_X03_CONTRACT: expected contract {CONTRACT!r}, got {TAX.get('contract')!r}"
    )
    assert int(TAX.get("schema_version", 0)) >= 1, "ACNS_X03_CONTRACT: schema_version missing"
    assert (
        TAX.get("contribution_class") == "SoK"
    ), "ACNS_X03_CONTRACT: contribution_class must be SoK"
    assert (
        TAX.get("mechanism_claim") == "none_declared"
    ), "ACNS_X03_CONTRACT: SoK instrument must declare mechanism_claim none_declared"


def test_all_six_lattice_levels_declared() -> None:
    levels = TAX.get("lattice_levels")
    assert isinstance(levels, list), "ACNS_X03_LEVELS: lattice_levels missing"
    assert tuple(levels) == REQUIRED_LEVELS, (
        f"ACNS_X03_LEVELS: expected exact task contract levels {REQUIRED_LEVELS}, got {tuple(levels)}"
    )


def test_all_five_node_classes_present() -> None:
    classes = TAX.get("node_classes")
    assert isinstance(classes, list) and classes, "ACNS_X03_CLASSES: node_classes missing"
    ids = tuple(c.get("id") for c in classes if isinstance(c, dict))
    for required in REQUIRED_NODE_CLASSES:
        assert required in ids, (
            f"ACNS_X03_CLASSES: required node class {required!r} missing from {ids}"
        )
    for entry in classes:
        assert isinstance(entry.get("definition"), str) and entry["definition"].strip(), (
            f"ACNS_X03_CLASSES: class {entry.get('id')!r} lacks a definition"
        )


def test_citation_registry_has_real_upstream_sources() -> None:
    cites = TAX.get("citations")
    assert isinstance(cites, list) and cites, "ACNS_X03_CITES: citations registry missing"
    by_id = {c.get("id"): c for c in cites if isinstance(c, dict)}
    for cid in REQUIRED_CITATION_IDS:
        entry = by_id.get(cid)
        assert entry is not None, f"ACNS_X03_CITES: required citation {cid!r} missing"
        for field in ("identifier", "title", "url", "used_for"):
            value = entry.get(field)
            assert isinstance(value, str) and value.strip(), (
                f"ACNS_X03_CITES: citation {cid!r} lacks {field}"
            )
        assert entry["url"].startswith("https://"), (
            f"ACNS_X03_CITES: citation {cid!r} url must be https"
        )
    assert "9334" in by_id["rfc9334"]["identifier"], "ACNS_X03_CITES: RFC 9334 identifier wrong"
    assert "9162" in by_id["rfc9162"]["identifier"], "ACNS_X03_CITES: RFC 9162 identifier wrong"
    assert "PROV" in by_id["w3c_prov_dm"]["identifier"].upper() or "PROV" in str(
        by_id["w3c_prov_dm"].values()
    ).upper(), "ACNS_X03_CITES: W3C PROV citation malformed"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def _nodes() -> list[dict]:
    nodes = TAX.get("nodes")
    assert isinstance(nodes, list) and nodes, "ACNS_X03_NODES: nodes missing"
    return [n for n in nodes if isinstance(n, dict)]


def test_every_node_has_full_contract_fields() -> None:
    for node in _nodes():
        nid = node.get("id", "?")
        for field in REQUIRED_NODE_FIELDS:
            value = node.get(field)
            if field == "citations":
                assert isinstance(value, list), f"ACNS_X03_NODE[{nid}]: citations must be a list"
            else:
                assert isinstance(value, str) and value.strip(), (
                    f"ACNS_X03_NODE[{nid}]: required field {field!r} missing or empty"
                )


def test_node_levels_cover_all_six_levels() -> None:
    levels = [n.get("level") for n in _nodes()]
    for required in REQUIRED_LEVELS:
        assert required in levels, f"ACNS_X03_NODE_LEVELS: level {required!r} has no node"


def test_node_classes_map_to_required_classes() -> None:
    for node in _nodes():
        nid = node.get("id", "?")
        assert node.get("node_class") in REQUIRED_NODE_CLASSES, (
            f"ACNS_X03_NODE[{nid}]: node_class {node.get('node_class')!r} not a required class"
        )


def test_node_citations_reference_registered_sources() -> None:
    registry = {c.get("id") for c in TAX.get("citations", []) if isinstance(c, dict)}
    for node in _nodes():
        nid = node.get("id", "?")
        for cid in node.get("citations", []):
            assert cid in registry, (
                f"ACNS_X03_NODE[{nid}]: citation {cid!r} not in the citation registry"
            )


def test_each_node_class_has_at_least_one_node() -> None:
    present = {n.get("node_class") for n in _nodes()}
    for required in REQUIRED_NODE_CLASSES:
        assert required in present, (
            f"ACNS_X03_CLASS_COVERAGE: node class {required!r} has no node instance"
        )


def test_no_node_claims_a_mechanism() -> None:
    forbidden = re.compile(
        r"\bwe (?:introduce|propose|present|deploy|implement|build)\b"
        r"|\bnew (?:mechanism|protocol|detector|attestation scheme|primitive)\b"
        r"|\bnovel (?:mechanism|protocol|detector|scheme)\b",
        re.IGNORECASE,
    )
    for node in _nodes():
        nid = node.get("id", "?")
        for field in ("definition", "proves", "does_not_prove"):
            text = str(node.get(field, ""))
            match = forbidden.search(text)
            assert match is None, (
                f"ACNS_X03_NODE[{nid}]: field {field!r} claims a mechanism via {match.group(0)!r}"
            )
    top = str(TAX.get("paper", "")) + " " + str(TAX.get("mechanism_claim", ""))
    assert TAX.get("mechanism_claim") == "none_declared" or not forbidden.search(top), (
        "ACNS_X03_DOC: top-level metadata claims a mechanism"
    )


def test_node_semantics_marked_per_node() -> None:
    """Proves/does-not-prove must be non-trivially distinct per node."""
    for node in _nodes():
        nid = node.get("id", "?")
        proves = str(node.get("proves", "")).lower()
        does_not = str(node.get("does_not_prove", "")).lower()
        assert "not" in does_not, (
            f"ACNS_X03_NODE[{nid}]: does_not_prove must state exclusions explicitly"
        )
        assert len(proves) >= 40 and len(does_not) >= 40, (
            f"ACNS_X03_NODE[{nid}]: proves/does_not_prove too thin to code against"
        )


# ---------------------------------------------------------------------------
# Edges -- the DoD item: every edge has trust assumptions
# ---------------------------------------------------------------------------
def _edges() -> list[dict]:
    edges = TAX.get("edges")
    assert isinstance(edges, list) and edges, "ACNS_X03_EDGES: edges missing"
    return [e for e in edges if isinstance(e, dict)]


def test_every_edge_declares_trust_assumptions() -> None:
    for edge in _edges():
        eid = edge.get("id", "?")
        for field in REQUIRED_EDGE_FIELDS:
            value = edge.get(field)
            assert isinstance(value, str) and value.strip(), (
                f"ACNS_X03_EDGE[{eid}]: required field {field!r} missing or empty"
            )
        assert edge["status"] in ("valid", "invalid"), (
            f"ACNS_X03_EDGE[{eid}]: status must be valid or invalid, got {edge['status']!r}"
        )


def test_edge_endpoints_are_registered_nodes() -> None:
    ids = {n.get("id") for n in _nodes()}
    for edge in _edges():
        eid = edge.get("id", "?")
        assert edge.get("from") in ids, f"ACNS_X03_EDGE[{eid}]: from-node not registered"
        assert edge.get("to") in ids, f"ACNS_X03_EDGE[{eid}]: to-node not registered"


def test_invalid_edges_name_a_failure_family_from_threat_model() -> None:
    for edge in _edges():
        eid = edge.get("id", "?")
        if edge.get("status") == "invalid":
            assert edge.get("failure_family") in THREAT_FAMILIES, (
                f"ACNS_X03_EDGE[{eid}]: invalid edge must name a registered threat-model family"
            )


def test_adjacent_lattice_chain_is_present() -> None:
    """The full chain must be walkable: ASSUMED->...->COMMITTED."""
    level_of = {n.get("id"): n.get("level") for n in _nodes()}
    chain = list(zip(REQUIRED_LEVELS, REQUIRED_LEVELS[1:]))
    for lo, hi in chain:
        found = any(
            level_of.get(e.get("from")) == lo and level_of.get(e.get("to")) == hi
            for e in _edges()
        )
        assert found, f"ACNS_X03_CHAIN: no edge connects {lo} -> {hi}"


def test_mandated_invalid_implications_registered() -> None:
    by_id = {e.get("id"): e for e in _edges()}
    for eid in ("E03_transport_ack_to_receipt", "E04_receipt_to_execution", "E06_transport_to_inference"):
        edge = by_id.get(eid)
        assert edge is not None, f"ACNS_X03_NEGATIVE: mandated invalid edge {eid!r} missing"
        assert edge.get("status") == "invalid", (
            f"ACNS_X03_NEGATIVE: {eid!r} must be an invalid implication"
        )


# ---------------------------------------------------------------------------
# Adversarial and positive controls (paired matrix cells)
# ---------------------------------------------------------------------------
def test_adversarial_controls_present_with_reject_verdicts() -> None:
    controls = TAX.get("adversarial_controls")
    assert isinstance(controls, list) and len(controls) >= 2, (
        "ACNS_X03_CONTROLS: at least two adversarial controls required"
    )
    edge_ids = {e.get("id") for e in _edges()}
    for control in controls:
        cid = control.get("id", "?")
        for field in ("claim_under_attack", "why_invalid", "expected_oracle_verdict"):
            value = control.get(field)
            assert isinstance(value, str) and value.strip(), (
                f"ACNS_X03_CONTROLS[{cid}]: field {field!r} missing"
            )
        assert control.get("edge_ref") in edge_ids, (
            f"ACNS_X03_CONTROLS[{cid}]: edge_ref not a registered edge"
        )
        assert control.get("expected_oracle_verdict") == "REJECT", (
            f"ACNS_X03_CONTROLS[{cid}]: adversarial control must be frozen REJECT"
        )


def test_hash_only_and_transport_inference_controls_registered() -> None:
    text = str(TAX.get("adversarial_controls", []))
    assert "hash" in text.lower(), "ACNS_X03_CONTROLS: hash-only-token control missing"
    assert "transport" in text.lower(), "ACNS_X03_CONTROLS: transport->inference control missing"


def test_positive_controls_capped_not_expanded() -> None:
    controls = TAX.get("positive_controls")
    assert isinstance(controls, list) and controls, "ACNS_X03_CONTROLS: positive controls missing"
    edge_ids = {e.get("id") for e in _edges()}
    for control in controls:
        cid = control.get("id", "?")
        assert control.get("edge_ref") in edge_ids, (
            f"ACNS_X03_CONTROLS[{cid}]: edge_ref not a registered edge"
        )
        assert "ACCEPT" in str(control.get("expected_oracle_verdict", "")), (
            f"ACNS_X03_CONTROLS[{cid}]: positive control must accept at a level"
        )
        cap = str(control.get("cap_note", ""))
        assert "no extension" in cap.lower() or "never extends" in cap.lower() or "no claim" in cap.lower(), (
            f"ACNS_X03_CONTROLS[{cid}]: positive control must state its cap explicitly"
        )


# ---------------------------------------------------------------------------
# Consistency with the frozen threat model
# ---------------------------------------------------------------------------
def test_trusted_components_aligned_with_threat_model() -> None:
    components = TAX.get("trusted_components")
    assert isinstance(components, dict) and components, "ACNS_X03_TC: trusted_components missing"
    for tc in ("TC1", "TC2", "TC3", "TC4", "TC5", "TC6"):
        assert tc in components, f"ACNS_X03_TC: {tc} missing"
    threat = THREAT_PATH.read_text(encoding="utf-8")
    for tc in ("TC1", "TC3", "TC6"):
        assert tc in threat, f"ACNS_X03_TC: {tc} not defined in threat_model.md"


def test_gap_register_boundaries_referenced() -> None:
    text = str(TAX)
    for gap in ("G1", "G2", "G3", "G7"):
        assert gap in text, f"ACNS_X03_GAPS: gap register boundary {gap} not referenced"
    threat = THREAT_PATH.read_text(encoding="utf-8")
    for gap in ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"):
        assert gap in threat, f"ACNS_X03_GAPS: gap {gap} missing from threat model register"


def test_execution_status_disclaims_empirical_values() -> None:
    status = TAX.get("execution_status")
    assert isinstance(status, dict), "ACNS_X03_STATUS: execution_status section missing"
    assert status.get("empirical_values") == "none", (
        "ACNS_X03_STATUS: design-time document must assert no empirical values"
    )
    note = str(status.get("note", ""))
    assert "manifest.json" in note, (
        "ACNS_X03_STATUS: observed statistics must route via artifacts manifest"
    )


def test_document_records_base_sha() -> None:
    prov = TAX.get("provenance")
    assert isinstance(prov, dict), "ACNS_X03_PROV: provenance section missing"
    sha = str(prov.get("base_sha", ""))
    assert re.fullmatch(r"[0-9a-f]{40}", sha), (
        "ACNS_X03_PROV: base_sha must be a full 40-hex git SHA"
    )
