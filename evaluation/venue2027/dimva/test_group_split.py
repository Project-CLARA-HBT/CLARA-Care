"""Tests for DIMVA-X08_splitter — strict independent cross-domain holdout.

Positive vectors cover determinism, full disjoint coverage (every group in
exactly one split), identity-bridge merging (family/tenant/tooling/lineage),
the returned leakage audit and schema-valid reproducible output. Adversarial
vectors prove fail-closed refusals: an event-level split (one campaign
fragmented into multiple group records) is REFUSED as leaky, and two
campaigns from the same attacker family / tenant cannot land in different
splits — the splitter keeps them together and flags the bridge in the audit
instead of silently separating them.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from evaluation.venue2027.dimva import group_split as gs

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def group(
    gid: str,
    *,
    family: str = "low_and_slow",
    tenant: str = "tenant_a",
    templates: list[str] | None = None,
    lineage: str = "gen-2027-a",
    **extra: str,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "group_id": gid,
        "attacker_family": family,
        "tenant": tenant,
        "tooling_templates": templates if templates is not None else [f"tmpl-{gid}"],
        "source_lineage": lineage,
    }
    entry.update(extra)
    return entry


def _assert_valid_partitions(partitions: gs.Partitions, n_groups: int) -> None:
    seen: dict[str, str] = {}
    for label in gs.SPLITS:
        members = getattr(partitions, label)
        for entry in members:
            gid = entry["group_id"]
            assert gid not in seen, f"group {gid!r} spans {seen[gid]} and {label}"
            seen[gid] = label
            assert partitions.assignment[gid] == label
    assert len(seen) == n_groups
    assert not partitions.audit.bridge_overlap_report
    assert partitions.audit.clean


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_deterministic_same_seed_byte_identical() -> None:
    groups = [
        group(f"g{i:02d}", family=f"fam{i % 6}", tenant=f"t{i % 6}", lineage=f"lin{i % 6}")
        for i in range(18)
    ]
    a = gs.split(groups, seed=2027)
    b = gs.split(list(groups), seed=2027)
    assert a.assignment == b.assignment
    assert a.partition_sha256 == b.partition_sha256
    assert a.to_dict() == b.to_dict()
    assert [g["group_id"] for g in a.train] == [g["group_id"] for g in b.train]
    assert [g["group_id"] for g in a.dev] == [g["group_id"] for g in b.dev]
    assert [g["group_id"] for g in a.test] == [g["group_id"] for g in b.test]


def test_different_seed_changes_component_layout() -> None:
    groups = [
        group(f"g{i:02d}", family=f"fam{i}", tenant=f"t{i}", lineage=f"lin{i}") for i in range(12)
    ]
    a = gs.split(groups, seed=1)
    b = gs.split(groups, seed=2)
    assert a.partition_sha256 != b.partition_sha256


def test_every_group_in_exactly_one_split_and_all_splits_used() -> None:
    groups = [
        group(f"g{i:02d}", family=f"fam{i}", tenant=f"t{i}", lineage=f"lin{i}") for i in range(30)
    ]
    partitions = gs.split(groups, seed=7)
    _assert_valid_partitions(partitions, n_groups=30)
    assert {partitions.assignment[g["group_id"]] for g in groups} == set(gs.SPLITS)
    assert partitions.train and partitions.dev and partitions.test


def test_default_ratios_respected_across_components() -> None:
    groups = [
        group(f"g{i:02d}", family=f"fam{i}", tenant=f"t{i}", lineage=f"lin{i}") for i in range(20)
    ]
    partitions = gs.split(groups, seed=11)
    counts = {label: len(getattr(partitions, label)) for label in gs.SPLITS}
    assert counts["train"] / 20 == pytest.approx(0.6, abs=0.15)
    assert counts["dev"] / 20 == pytest.approx(0.2, abs=0.15)
    assert counts["test"] / 20 == pytest.approx(0.2, abs=0.15)


def test_same_family_tenant_lineage_kept_together() -> None:
    groups = [
        group("a1", family="burst_probe", tenant="t_x", lineage="lin_1"),
        group("a2", family="burst_probe", tenant="t_x", lineage="lin_1"),
        group("b1", family="benign_session", tenant="t_y", lineage="lin_2"),
        group("b2", family="benign_session", tenant="t_y", lineage="lin_2"),
        group("c1", family="low_and_slow", tenant="t_z", lineage="lin_3"),
        group("c2", family="low_and_slow", tenant="t_z", lineage="lin_3"),
    ]
    partitions = gs.split(groups, seed=3)
    _assert_valid_partitions(partitions, n_groups=6)
    assert partitions.assignment["a1"] == partitions.assignment["a2"]
    assert partitions.assignment["b1"] == partitions.assignment["b2"]
    assert partitions.assignment["c1"] == partitions.assignment["c2"]
    shared_attributes = {
        ("attacker_family", "burst_probe"),
        ("tenant", "t_x"),
        ("source_lineage", "lin_1"),
    }
    flagged = {(f.kind, f.attribute) for f in partitions.audit.findings}
    assert shared_attributes <= flagged


def test_shared_tooling_template_bridges_groups() -> None:
    groups = [
        group("s1", family="fam_a", tenant="t_a", lineage="lin_a", templates=["tmpl_shared"]),
        group("s2", family="fam_b", tenant="t_b", lineage="lin_b", templates=["tmpl_shared"]),
        group("free1", family="fam_c", tenant="t_c", lineage="lin_c", templates=["tmpl_c1"]),
        group("free2", family="fam_d", tenant="t_d", lineage="lin_d", templates=["tmpl_d1"]),
        group("free3", family="fam_e", tenant="t_e", lineage="lin_e", templates=["tmpl_e1"]),
    ]
    partitions = gs.split(groups, seed=5)
    _assert_valid_partitions(partitions, n_groups=5)
    assert partitions.assignment["s1"] == partitions.assignment["s2"]
    assert any(
        f.kind == gs.BK_TOOLING_TEMPLATE and f.attribute == "tmpl_shared"
        for f in partitions.audit.findings
    )


def test_template_paraphrase_near_duplicate_is_bridged() -> None:
    """Cross-tenant alias + template paraphrase near-duplicate: merged, flagged."""

    groups = [
        group(
            "p1",
            family="fam_a",
            tenant="tenant_alpha",
            lineage="lin_a",
            templates=["Probe-Tool.01"],
        ),
        group(
            "p2", family="fam_b", tenant="tenant_beta", lineage="lin_b", templates=["probe_tool_01"]
        ),
        group("q1", family="fam_c", tenant="tenant_gamma", lineage="lin_c", templates=["other-1"]),
        group("q2", family="fam_d", tenant="tenant_delta", lineage="lin_d", templates=["other-2"]),
        group(
            "q3", family="fam_e", tenant="tenant_epsilon", lineage="lin_e", templates=["other-3"]
        ),
    ]
    partitions = gs.split(groups, seed=9)
    _assert_valid_partitions(partitions, n_groups=5)
    assert partitions.assignment["p1"] == partitions.assignment["p2"]
    finding = next(
        f for f in partitions.audit.findings if f.kind == gs.BK_TOOLING_TEMPLATE_PARAPHRASE
    )
    assert finding.attribute == "probe_tool_01"
    assert set(finding.group_ids) == {"p1", "p2"}
    assert set(finding.raw_values) == {"Probe-Tool.01", "probe_tool_01"}
    assert gs.canonical_template("Probe-Tool.01") == gs.canonical_template("probe_tool_01")


def test_audit_reports_exact_bridges_and_clean_state() -> None:
    groups = [
        group("a1", family="fam_1", tenant="t_1", lineage="lin_1"),
        group("a2", family="fam_1", tenant="t_1", lineage="lin_1"),
        group("solo", family="fam_2", tenant="t_2", lineage="lin_2"),
        group("loner", family="fam_3", tenant="t_3", lineage="lin_3"),
        group("extra", family="fam_4", tenant="t_4", lineage="lin_4"),
    ]
    partitions = gs.split(groups, seed=13)
    assert partitions.audit.group_count == 5
    assert partitions.audit.component_count == 4
    assert partitions.audit.unit_of_inference == "campaign_group"
    family_findings = [f for f in partitions.audit.findings if f.kind == "attacker_family"]
    assert len(family_findings) == 1
    assert set(family_findings[0].group_ids) == {"a1", "a2"}
    assert partitions.audit.bridge_overlap_report == ()
    assert partitions.audit.clean
    serialized = json.dumps(partitions.to_dict(), sort_keys=True)
    assert json.loads(serialized)["audit"]["clean"] is True


def test_transitive_bridge_chain_collapses_into_one_component() -> None:
    """n1—n2 share a family, n2—n3 a tenant, n3—n4 a lineage, n4—n5 a template.

    Union-find must transitively collapse n1..n4 into ONE component so they
    all land in the same split; n5 and n6 stay bridge-free and independent.
    """

    groups = [
        group("n1", family="fam_chain", tenant="t_a", lineage="lin_a", templates=["tA"]),
        group("n2", family="fam_chain", tenant="t_chain", lineage="lin_b", templates=["tB"]),
        group("n3", family="fam_c", tenant="t_chain", lineage="lin_chain", templates=["tC"]),
        group("n4", family="fam_d", tenant="t_d", lineage="lin_chain", templates=["tD"]),
        group("n5", family="fam_e", tenant="t_e", lineage="lin_e", templates=["tE"]),
        group("n6", family="fam_f", tenant="t_f", lineage="lin_f", templates=["tF"]),
    ]
    partitions = gs.split(groups, seed=21)
    assert partitions.audit.component_count == 3
    assert partitions.audit.group_count == 6
    assert {partitions.assignment[g] for g in ("n1", "n2", "n3", "n4")} == {
        partitions.assignment["n1"]
    }
    assert partitions.audit.clean


def test_to_dict_is_json_serializable_with_version() -> None:
    groups = [group(f"g{i}", family=f"f{i}", tenant=f"t{i}", lineage=f"l{i}") for i in range(6)]
    partitions = gs.split(groups, seed=31)
    payload = partitions.to_dict()
    assert payload["schema_version"] == gs.GROUP_SPLIT_VERSION
    assert payload["seed"] == 31
    round_trip = json.loads(json.dumps(payload))
    assert round_trip["assignment"] == payload["assignment"]


def test_custom_ratios_honored() -> None:
    groups = [
        group(f"g{i:02d}", family=f"fam{i}", tenant=f"t{i}", lineage=f"lin{i}") for i in range(10)
    ]
    partitions = gs.split(groups, seed=17, ratios=gs.SplitRatios(train=0.5, dev=0.25, test=0.25))
    counts = {label: len(getattr(partitions, label)) for label in gs.SPLITS}
    assert sum(counts.values()) == 10
    assert counts["train"] == 5


def test_output_mutation_isolation_between_runs() -> None:
    groups = [group(f"g{i}", family=f"f{i}", tenant=f"t{i}", lineage=f"l{i}") for i in range(6)]
    first = gs.split(groups, seed=42)
    second = gs.split(groups, seed=42)
    first.assignment["g0"] = "MUTATED"
    assert second.assignment["g0"] != "MUTATED"
    assert first.partition_sha256 == second.partition_sha256


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_event_level_split_refused_duplicate_group_id() -> None:
    """Several records claiming ONE campaign identity is an event-level split."""

    event_fragments = [
        group("camp_1", family="burst_probe", tenant="t_1", lineage="lin_1"),
        group("camp_1", family="burst_probe", tenant="t_1", lineage="lin_1"),
        group("solo", family="benign_session", tenant="t_2", lineage="lin_2"),
        group("extra", family="fam_x", tenant="t_3", lineage="lin_3"),
        group("last", family="fam_y", tenant="t_4", lineage="lin_4"),
    ]
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split(event_fragments, seed=2027)
    assert excinfo.value.reason_code == gs.RC_EVENT_LEVEL_SPLIT_REFUSED
    assert "camp_1" in excinfo.value.detail
    assert "campaign" in excinfo.value.detail


def test_event_level_split_refused_shared_campaign_id() -> None:
    """Event fragments sharing a campaign_id must never be spread over splits."""

    fragments = [
        group("ev_1", campaign_id="camp_9"),
        group("ev_2", campaign_id="camp_9"),
        group("ev_3", campaign_id="camp_9"),
        group("solo", family="benign_session", tenant="t_2", lineage="lin_2"),
        group("extra", family="fam_x", tenant="t_3", lineage="lin_3"),
    ]
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split(fragments, seed=2027)
    assert excinfo.value.reason_code == gs.RC_EVENT_LEVEL_SPLIT_REFUSED


def test_same_family_and_tenant_campaigns_cannot_land_in_different_splits() -> None:
    """Two campaigns from one attacker family/tenant stay together + leak flag."""

    campaigns = [
        group("camp_a", family="low_and_slow", tenant="tenant_shared", lineage="lin_a"),
        group("camp_b", family="low_and_slow", tenant="tenant_shared", lineage="lin_b"),
        group("camp_c", family="benign_session", tenant="t_other", lineage="lin_c"),
        group("camp_d", family="burst_probe", tenant="t_x", lineage="lin_d"),
        group("camp_e", family="cross_tool_obfuscation", tenant="t_y", lineage="lin_e"),
        group("camp_f", family="fam_z", tenant="t_z", lineage="lin_f"),
    ]
    partitions = gs.split(campaigns, seed=99)
    _assert_valid_partitions(partitions, n_groups=6)
    assert (
        partitions.assignment["camp_a"] == partitions.assignment["camp_b"]
    ), "same attacker family + tenant must stay in one split"
    family_finding = next(
        f
        for f in partitions.audit.findings
        if f.kind == "attacker_family"
        and f.attribute == "low_and_slow"
        and {"camp_a", "camp_b"} <= set(f.group_ids)
    )
    tenant_finding = next(
        f
        for f in partitions.audit.findings
        if f.kind == "tenant"
        and f.attribute == "tenant_shared"
        and {"camp_a", "camp_b"} <= set(f.group_ids)
    )
    assert family_finding and tenant_finding
    overlaps = gs.detect_bridge_overlaps(campaigns, partitions.assignment)
    assert overlaps == ()


def test_leak_detector_reports_exact_overlap_for_forced_leaky_assignment() -> None:
    """A hand-forced assignment that separates bridged groups is reported."""

    campaigns = [
        group("camp_a", family="same_family", tenant="shared_t", lineage="lin_a"),
        group("camp_b", family="same_family", tenant="shared_t", lineage="lin_b"),
        group("camp_c", family="fam_c", tenant="t_c", lineage="lin_c"),
        group("camp_d", family="fam_d", tenant="t_d", lineage="lin_d"),
        group("camp_e", family="fam_e", tenant="t_e", lineage="lin_e"),
        group("camp_f", family="fam_f", tenant="t_f", lineage="lin_f"),
    ]
    leaky = {
        "camp_a": "train",
        "camp_b": "test",
        "camp_c": "train",
        "camp_d": "dev",
        "camp_e": "test",
        "camp_f": "dev",
    }
    overlaps = gs.detect_bridge_overlaps(campaigns, leaky)
    assert overlaps, "forced leaky assignment must produce an exact overlap report"
    family_overlap = next(
        o for o in overlaps if o.kind == "attacker_family" and o.attribute == "same_family"
    )
    assert set(family_overlap.group_ids) == {"camp_a", "camp_b"}
    assert set(family_overlap.splits) == {"train", "test"}
    tenant_overlap = next(o for o in overlaps if o.kind == "tenant" and o.attribute == "shared_t")
    assert set(tenant_overlap.splits) == {"train", "test"}


def test_detect_bridge_overlaps_refuses_incomplete_assignment() -> None:
    campaigns = [
        group("camp_a", family="fam_a", tenant="t_a", lineage="l_a"),
        group("camp_b", family="fam_b", tenant="t_b", lineage="l_b"),
    ]
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.detect_bridge_overlaps(campaigns, {"camp_a": "train"})
    assert excinfo.value.reason_code == gs.RC_INCOMPLETE_ASSIGNMENT
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.detect_bridge_overlaps(campaigns, {"camp_a": "train", "camp_b": "holdout"})
    assert excinfo.value.reason_code == gs.RC_INVALID_SPLIT_LABEL


def test_empty_groups_refused() -> None:
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split([], seed=1)
    assert excinfo.value.reason_code == gs.RC_EMPTY_GROUPS


def test_unknown_and_missing_fields_refused() -> None:
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split([dict(group("g1"), reason_code="DENIED")], seed=1)
    assert excinfo.value.reason_code == gs.RC_UNKNOWN_GROUP_FIELD
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split([{"group_id": "g1", "attacker_family": "f", "tenant": "t"}], seed=1)
    assert excinfo.value.reason_code == gs.RC_MISSING_GROUP_FIELD


def test_malformed_field_values_refused() -> None:
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split([group("g1", tenant="  ")], seed=1)
    assert excinfo.value.reason_code == gs.RC_INVALID_GROUP_FIELD
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split([group("g1", templates="tmpl-1")], seed=1)
    assert excinfo.value.reason_code == gs.RC_INVALID_GROUP_FIELD
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split([group("g1", templates=[42])], seed=1)
    assert excinfo.value.reason_code == gs.RC_INVALID_GROUP_FIELD


def test_invalid_seed_and_ratios_refused() -> None:
    groups = [group(f"g{i}", family=f"f{i}", tenant=f"t{i}", lineage=f"l{i}") for i in range(6)]
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split(groups, seed="7")  # type: ignore[arg-type]
    assert excinfo.value.reason_code == gs.RC_INVALID_SEED
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split(groups, seed=True)
    assert excinfo.value.reason_code == gs.RC_INVALID_SEED
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split(groups, seed=1, ratios=gs.SplitRatios(train=0.5, dev=0.5, test=0.5))
    assert excinfo.value.reason_code == gs.RC_INVALID_SPLIT_RATIOS
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split(groups, seed=1, ratios=dataclasses.replace(gs.SplitRatios(), train=1.2))
    assert excinfo.value.reason_code == gs.RC_INVALID_SPLIT_RATIOS


def test_total_bridge_collapse_refused() -> None:
    """Bridges collapsing everything below three components cannot fill splits."""

    collapsed = [
        group("x1", family="one", tenant="t1", lineage="lin1"),
        group("x2", family="one", tenant="t1", lineage="lin1"),
        group("x3", family="one", tenant="t1", lineage="lin1"),
    ]
    with pytest.raises(gs.GroupingError) as excinfo:
        gs.split(collapsed, seed=2)
    assert excinfo.value.reason_code == gs.RC_DEGENERATE_COMPONENT_COUNT
    assert excinfo.value.detail.count("component") >= 1
