"""Structural test for the COMPSAC-rq_registry preregistration.

Purpose
-------
Machine-checks that ``research/venue2027/compsac/rq_and_estimands.yaml``
satisfies the frozen RQ-plan contract for the COMPSAC 2027 study: exactly
three preregistered RQs (RQ1-RQ3), every required design field present and
non-empty for each RQ, the RQ1 two-gate primary endpoint (safety gate AND
utility gate, INDEPENDENT_EVIDENCE_PROTOCOL rule 5), preregistered
falsification conditions matching the blueprint falsification rule, the
required statistical methods (exact McNemar, cluster bootstrap,
Clopper-Pearson zero-event bound, Fisher exact), the independent-unit /
population / estimand trio, and no invented numeric research results (the
registry records design decisions only; measured outcomes belong in
artifacts/venue2027/compsac/<run_id>/, never here).

Allowed input
-------------
Read-only access to the registry YAML file. No network, no DB, no provider
calls. Parsed with the PyYAML parser if available, otherwise a stdlib
fallback loader covering this registry's block/flow mappings, block
sequences and flow sequences (no anchors, no multi-line scalars beyond the
plain single-line and double-quoted forms used here).

Failure semantics
-----------------
Each check fails with an assertion message naming the missing or drifting
contract element; no silent passes. Adversarial controls verify the loader
refuses malformed/undefined input instead of inventing values, so a broken
registry can never satisfy this suite by coercion.

Version
-------
``compsac-rq-registry-test-v1``
"""

from __future__ import annotations

import pathlib
import re

REGISTRY = pathlib.Path(__file__).resolve().parents[1] / "rq_and_estimands.yaml"

RQ_IDS = ("RQ1", "RQ2", "RQ3")

RQ_REQUIRED_FIELDS = (
    "research_question",
    "independent_unit",
    "population",
    "estimand",
    "paired_contrast",
    "primary_metric",
    "secondary_metrics",
    "null_hypothesis",
    "alternative_hypothesis",
    "minimum_useful_difference",
    "confounders",
    "power_analysis_method",
    "falsification_condition",
    "primary_endpoint",
)

TOP_LEVEL_REQUIRED = (
    "schema_version",
    "task_id",
    "venue",
    "phase",
    "status",
    "registry_version",
    "paper_title",
    "independent_oracle",
    "independent_unit",
    "cluster_definition",
    "population_frame",
    "baseline_arms",
    "preregistration",
    "analysis_contract",
    "rqs",
)

BASELINE_ARMS = ("B0", "B1", "B2", "B3", "B4")

CONFOUNDERS_REQUIRED = ("contention", "density", "Zipf")


def _load_registry() -> dict:
    """Parse the registry YAML with PyYAML, else a strict stdlib fallback.

    The fallback parses exactly the constructs this registry uses (single-line
    mappings, double-quoted scalars, block sequences, flow sequences, nested
    block mappings). Anything it cannot interpret raises AssertionError, so a
    syntactically broken registry fails closed instead of parsing to None.
    """

    assert REGISTRY.is_file(), f"rq registry missing at {REGISTRY}"
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    except ImportError:
        data = _load_registry_stdlib(REGISTRY)
    assert isinstance(data, dict), "registry must parse to a mapping"
    return data


def _load_registry_stdlib(path: pathlib.Path) -> dict:
    """Strict stdlib YAML subset loader (fail-closed)."""

    root: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, root)]

    def scalar(raw: str):
        raw = raw.strip()
        if raw.startswith("["):
            if not raw.endswith("]"):
                raise AssertionError("unterminated flow sequence (fail closed)")
            inner = raw[1:-1].strip()
            return [_scalar_token(t) for t in _split_flow(inner)] if inner else []
        if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
            return raw[1:-1].replace('\\"', '"')
        return raw

    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", 1)[0].rstrip() if not raw_line.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        if raw_line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()
        if content.startswith("- "):
            item = content[2:].strip()
            while stack and indent <= stack[-1][0] and not isinstance(stack[-1][1], list):
                stack.pop()
            parent = stack[-1][1]
            assert isinstance(parent, list), f"line {lineno}: sequence without list parent"
            if ":" in item and not item.startswith('"'):
                key, _, value = item.partition(":")
                child: dict = {}
                parent.append(child)
                child[key.strip()] = scalar(value) if value.strip() else {}
                stack.append((indent + 2, child))
            else:
                parent.append(scalar(item))
            continue
        key, sep, value = content.partition(":")
        assert sep, f"line {lineno}: not a mapping entry: {content!r}"
        key = key.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        assert isinstance(parent, dict), f"line {lineno}: mapping without dict parent"
        if value.strip():
            parent[key] = scalar(value)
        else:
            child = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def _split_flow(inner: str) -> list[str]:
    parts, depth, current = [], 0, []
    for ch in inner:
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            current.append(ch)
    if current:
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _scalar_token(token: str):
    token = token.strip()
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        return token[1:-1]
    return token


def _rq_body(data: dict, rq: str) -> dict:
    rqs = data["rqs"]
    assert isinstance(rqs, dict), "rqs must be a mapping"
    assert rq in rqs, f"missing {rq} in registry"
    body = rqs[rq]
    assert isinstance(body, dict), f"{rq} must be a mapping"
    return body


# ---------------------------------------------------------------- positive controls


def test_exactly_three_rqs() -> None:
    data = _load_registry()
    assert set(data["rqs"].keys()) == set(
        RQ_IDS
    ), f"registry must preregister exactly RQ1-RQ3, found {sorted(data['rqs'])}"


def test_all_top_level_sections_present() -> None:
    data = _load_registry()
    for field in TOP_LEVEL_REQUIRED:
        assert field in data, f"registry missing required top-level field: {field}"
        assert data[field] not in (None, "", [], {}), f"field {field} is empty"


def test_every_rq_has_all_required_fields_nonempty() -> None:
    data = _load_registry()
    for rq in RQ_IDS:
        body = _rq_body(data, rq)
        for field in RQ_REQUIRED_FIELDS:
            assert field in body, f"{rq} missing required field: {field}"
            value = body[field]
            assert value not in (None, "", [], {}), f"{rq}.{field} is empty"
            if isinstance(value, str):
                assert value.strip(), f"{rq}.{field} is whitespace-only"
            if isinstance(value, list):
                assert len(value) >= 3, f"{rq}.{field} must enumerate multiple entries, got {value}"


def test_rq1_primary_metric_has_both_safety_and_utility_gates() -> None:
    data = _load_registry()
    primary = _rq_body(data, "RQ1")["primary_metric"]
    assert isinstance(primary, dict), "RQ1 primary_metric must be a mapping with both gates"
    for gate in ("safety_gate", "utility"):
        assert gate in primary, f"RQ1 two-gate primary metric missing: {gate}"
        assert str(primary[gate]).strip(), f"RQ1 gate {gate} is empty"
    safety_text = str(primary["safety_gate"]).lower()
    utility_text = str(primary["utility"]).lower()
    assert "forbidden commit" in safety_text, "safety gate must be the forbidden commit rate"
    assert "false-stale" in utility_text, "utility gate must be the oracle-defined false-stale rate"
    assert "zero" in safety_text, "safety gate must require zero forbidden commits"
    endpoint = str(_rq_body(data, "RQ1")["primary_endpoint"]).lower()
    assert (
        "safety gate" in endpoint and "utility gate" in endpoint
    ), "RQ1 primary_endpoint must state the two-gate (safety + utility) endpoint"


def test_rq2_rq3_primary_endpoints_declared() -> None:
    data = _load_registry()
    rq2_endpoint = str(_rq_body(data, "RQ2")["primary_endpoint"]).lower()
    assert (
        "detection rate" in rq2_endpoint or "detection proportion" in rq2_endpoint
    ), "RQ2 primary endpoint must be the separate-oracle detection rate"
    assert "propagation depth" in rq2_endpoint, "RQ2 primary endpoint must count propagation depth"
    rq3_endpoint = str(_rq_body(data, "RQ3")["primary_endpoint"]).lower()
    assert (
        "throughput" in rq3_endpoint and "ratio" in rq3_endpoint
    ), "RQ3 primary endpoint must be the B4-vs-B2 committed throughput ratio"
    assert "crossover" in rq3_endpoint, "RQ3 primary endpoint must define the crossover"


def test_falsification_conditions_preregistered_and_aligned() -> None:
    data = _load_registry()
    for rq in RQ_IDS:
        text = str(_rq_body(data, rq)["falsification_condition"]).strip()
        assert len(text) > 80, f"{rq} falsification_condition too thin to be falsifiable"
    assert "forbidden commit" in str(
        _rq_body(data, "RQ1")["falsification_condition"]
    ), "RQ1 falsifier must be the forbidden-commit rule"
    assert "fails to detect" in str(
        _rq_body(data, "RQ2")["falsification_condition"]
    ), "RQ2 falsifier must be an undetected injected flaw"
    assert "as fast" in str(
        _rq_body(data, "RQ3")["falsification_condition"]
    ), "RQ3 falsifier must be the null-throughput-benefit rule"
    assert "falsification_global" in data, "global falsification rule missing"
    global_rule = str(data["falsification_global"]).lower()
    assert (
        "forbidden commit" in global_rule and "as fast" in global_rule
    ), "global falsifier must carry both blueprint falsification rules"


def test_independent_unit_is_the_logical_schedule() -> None:
    data = _load_registry()
    for scope in (data, *(_rq_body(data, rq) for rq in RQ_IDS)):
        unit = str(scope["independent_unit"]).lower()
        assert "schedule" in unit, "independent unit must be the independent logical schedule"
    top_unit = str(data["independent_unit"]).lower()
    assert (
        "pseudo-replication" in top_unit
    ), "top-level independent unit must refuse per-event pseudo-replication"
    for rq in RQ_IDS:
        cluster_text = str(_rq_body(data, rq)["independent_unit"]).lower()
        assert "cluster" in cluster_text, f"{rq} unit must bind its schedule to one cluster"
    assert (
        "cluster_definition" in data and "cluster" in str(data["cluster_definition"]).lower()
    ), "cluster definition missing"


def test_population_is_case_arm_seed() -> None:
    data = _load_registry()
    frame = str(data["population_frame"])
    for token in ("case", "arm", "seed"):
        assert token in frame, f"population frame missing '{token}' dimension"
    for rq in RQ_IDS:
        population = str(_rq_body(data, rq)["population"]).lower()
        assert "case x arm x seed" in population, f"{rq} population not case x arm x seed"
        assert (
            "5 independent seeds" in population or "at least 5 independent seeds" in population
        ), f"{rq} population must require >= 5 independent seeds per setting"


def test_null_and_alternative_declared_per_rq() -> None:
    data = _load_registry()
    for rq in RQ_IDS:
        body = _rq_body(data, rq)
        null_text = str(body["null_hypothesis"]).lower()
        alt_text = str(body["alternative_hypothesis"]).lower()
        assert len(null_text) > 40 and len(alt_text) > 40, f"{rq} null/alternative too thin"
        assert null_text != alt_text, f"{rq} null and alternative must differ"


def test_minimum_useful_difference_declared_per_rq() -> None:
    data = _load_registry()
    for rq in RQ_IDS:
        text = str(_rq_body(data, rq)["minimum_useful_difference"]).strip()
        assert len(text) > 40, f"{rq} minimum_useful_difference must be concrete"
    rq1_mud = str(_rq_body(data, "RQ1")["minimum_useful_difference"])
    assert "0.10" in rq1_mud, "RQ1 minimum useful difference must be an absolute margin"


def test_confounders_cover_blueprint_grid() -> None:
    data = _load_registry()
    for rq in RQ_IDS:
        confounders = [_normalize(c) for c in _rq_body(data, rq)["confounders"]]
        joined = " | ".join(confounders)
        for token in CONFOUNDERS_REQUIRED:
            assert token.lower() in joined.lower(), f"{rq} confounders missing: {token}"


def test_power_method_names_required_tests() -> None:
    data = _load_registry()
    rq1_power = str(_rq_body(data, "RQ1")["power_analysis_method"]).lower()
    assert "mcnemar" in rq1_power, "RQ1 power method must name exact McNemar"
    assert "bootstrap" in rq1_power, "RQ1 power method must name the cluster bootstrap"
    assert (
        "clopper" in rq1_power or "1 - 0.05" in rq1_power
    ), "RQ1 power method must name the Clopper-Pearson zero-event bound"
    rq2_power = str(_rq_body(data, "RQ2")["power_analysis_method"]).lower()
    assert (
        "clopper" in rq2_power and "fisher" in rq2_power
    ), "RQ2 power method must name Clopper-Pearson intervals and Fisher exact"
    rq3_power = str(_rq_body(data, "RQ3")["power_analysis_method"]).lower()
    assert "bootstrap" in rq3_power, "RQ3 power method must name the paired bootstrap"
    contract = str(data["analysis_contract"]).lower()
    assert (
        "mcnemar" in contract and "bootstrap" in contract
    ), "analysis contract must freeze paired tests"
    assert (
        "indeterminate" in contract
    ), "analysis contract must forbid coercing indeterminate outcomes"


def test_baseline_arms_and_oracle_declared() -> None:
    data = _load_registry()
    arms = data["baseline_arms"]
    assert isinstance(arms, dict), "baseline_arms must be a mapping"
    assert set(arms.keys()) == set(
        BASELINE_ARMS
    ), f"baseline arms must be exactly {BASELINE_ARMS}, found {sorted(arms)}"
    assert "postgresql" in str(arms["B2"]).lower(), "B2 must be PostgreSQL SERIALIZABLE"
    assert "candidate" in str(arms["B4"]).lower(), "B4 must be the candidate"
    oracle = str(data["independent_oracle"]).lower()
    assert (
        "no candidate import" in oracle or "apart from the candidate" in oracle
    ), "independent oracle must be import-disjoint from the candidate"


def test_status_is_preregistered_only_and_downstream_signature_present() -> None:
    data = _load_registry()
    assert (
        data["status"] == "preregistered_only"
    ), "registry must be marked preregistered_only; measured results never live here"
    assert "read_rqs" in str(
        data["downstream_signature"]
    ), "downstream signature read_rqs()->RQPlan missing"
    assert data["task_id"] == "COMPSAC-rq_registry"
    assert data["venue"] == "compsac" and data["phase"] == "P01"


# ---------------------------------------------------------------- adversarial controls


def test_no_invented_numeric_results() -> None:
    """The registry records design decisions only -- never measured outcomes."""

    text = REGISTRY.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"(p\s*=\s*0\.\d+|p\s*<\s*0\.\d+"
        r"|\d+(\.\d+)?\s*(x|×)\s*(faster|higher|lower)"
        r"|\d+(\.\d+)?\s*ops/sec\s*(measured|observed)"
        r"|\d+(\.\d+)?\s*ms\s*(measured|observed)"
        r"|(measured|observed)\s+(rate|throughput|latency)\s+of\s+\d)",
        re.IGNORECASE,
    )
    hits = forbidden.findall(text)
    assert not hits, f"apparent invented empirical results in registry: {hits}"
    assert "TODO: fill in after run" not in text, "no post-hoc result placeholders allowed"


def test_no_post_hoc_result_placeholders_or_target_p_values() -> None:
    data = _load_registry()
    prereg = data["preregistration"]
    assert isinstance(prereg, dict) and prereg, "preregistration block missing"
    assert (
        "no_results_recorded" in prereg
    ), "registry must declare that no measured results are recorded here"
    assert "frozen_before_holdout" in prereg, "freeze-before-holdout declaration missing"
    contract = str(data["analysis_contract"]).lower()
    assert (
        "never chosen from target p-values" in contract
    ), "analysis contract must refuse p-value-targeted sample sizes"


def test_loader_refuses_undefined_document() -> None:
    """Fail closed: an empty/malformed registry must not parse to usable data."""

    empty = _load_registry_stdlib_content("# only a comment line\n")
    assert empty == {}, "stdlib loader must return empty mapping for comment-only input"
    malformed = _load_registry_stdlib_content("key: [unclosed flow\n")
    assert (
        malformed == {}
    ), "stdlib loader must refuse malformed flow input instead of inventing a registry"
    garbage = _load_registry_stdlib_content("this line has no colon\n")
    assert garbage == {}, "stdlib loader must fail closed on malformed lines"


def _load_registry_stdlib_content(text: str):
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        tmp = pathlib.Path(fh.name)
    try:
        return _load_registry_stdlib(tmp)
    except AssertionError:
        return {}
    finally:
        tmp.unlink(missing_ok=True)


def _normalize(value) -> str:
    return value if isinstance(value, str) else " ".join(map(str, value))
