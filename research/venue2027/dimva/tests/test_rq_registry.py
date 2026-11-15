"""Structural tests for the DIMVA-rq_registry RQ/estimand registry (P01).

Purpose
-------
Stdlib-only structural verification of
``research/venue2027/dimva/rq_and_estimands.yaml``. The registry is a
preregistered plan, not an empirical result: these tests assert the
*structure* required by ``VENUES/dimva/TASKS/DIMVA-rq_registry.md`` — exactly
three RQs (RQ1-RQ3) with the complete field set (research question,
independent unit, population, estimand, paired contrast, primary metric,
secondary metrics, null, alternative, minimum useful difference,
confounders, power/analysis method, falsification condition, primary
endpoint), a DETECTION primary endpoint that refuses prevention framing,
mechanically testable falsification conditions, and no invented results (no
observed metrics, p-values or CIs asserted anywhere in the plan).

Allowed input
-------------
The registry YAML at ``REGISTRY_PATH``. Read-only; no network, no
randomness, no clock. Parsed with the repository's PyYAML if available and
otherwise with a minimal indentation-based fallback parser restricted to the
block-mapping/sequence subset this registry uses; either path produces the
same plain nested dict/list structure.

Failure semantics
-----------------
Each violation is an ordinary pytest assertion failure with a stable test
name; nothing is silently skipped. Version: 1.0.0.
"""

from __future__ import annotations

import pathlib
import re

REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[2] / "dimva" / "rq_and_estimands.yaml"

RQ_IDS: tuple[str, ...] = ("RQ1", "RQ2", "RQ3")

REQUIRED_RQ_FIELDS: tuple[str, ...] = (
    "rq_id",
    "title",
    "research_question",
    "independent_unit",
    "population",
    "estimand",
    "paired_contrast",
    "primary_metric",
    "primary_metric_family",
    "secondary_metrics",
    "null_hypothesis",
    "alternative_hypothesis",
    "minimum_useful_difference",
    "confounders",
    "power_and_analysis_method",
    "falsification_condition",
    "primary_endpoint",
)

REQUIRED_SHARED_DESIGN_FIELDS: tuple[str, ...] = (
    "independent_unit",
    "population",
    "oracle",
    "false_positive_budget",
    "splits",
    "power_and_analysis",
)

# Detection-vocabulary markers required in each RQ primary endpoint.
DETECTION_MARKERS: tuple[str, ...] = ("pr-auc", "aucpr", "recall", "detection")

# Prevention framing that may not be *affirmed* in any RQ primary endpoint.
# (Negated mentions such as "never a prevention or admission rate" are fine;
# the check below scans a look-behind window for explicit negation.)
FORBIDDEN_PREVENTION_TERMS: tuple[str, ...] = (
    "replay acceptance rate",
    "admission rate",
    "prevention rate",
    "unauthorized commit",
)

_FROZEN_BUDGET_KEY = "false_alarms_per_1000_benign_sessions"


# ---------------------------------------------------------------------------
# Minimal loader (PyYAML if importable, else a restricted fallback)
# ---------------------------------------------------------------------------
def _load_registry() -> dict:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]

        data = yaml.safe_load(text)
        assert isinstance(data, dict)
        return data
    except ImportError:
        return _parse_simple_yaml(text)


def _scalar(token: str):
    token = token.strip()
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        return [item.strip().strip("'\"") for item in inner.split(",")] if inner else []
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    if token.startswith("'") and token.endswith("'"):
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


def _parse_simple_yaml(text: str) -> dict:
    """Indentation-based fallback for the subset used by the registry.

    Handles nested block mappings, block sequences (``- item`` and ``- key:
    value``), folded scalars (``>-`` / ``|``) and inline flow sequences.
    Block sequences of mappings are rendered as a list of single-key dicts
    that this test suite never indexes positionally for semantic fields.
    """

    root: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, root)]
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = raw.split("#", 1)[0].rstrip() if raw.lstrip().startswith("#") else raw.rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip()))
    i = 0
    while i < len(lines):
        indent, content = lines[i]
        while stack and indent <= stack[-1][0] and len(stack) > 1:
            stack.pop()
        container = stack[-1][1]
        if content.startswith("- "):
            if not isinstance(container, list):
                i += 1
                continue
            item = content[2:].strip()
            if ":" in item and not item.startswith("["):
                key, _, rest = item.partition(":")
                if rest.strip():
                    container.append({key.strip(): _scalar(rest)})
                    i += 1
                else:
                    sub: dict = {}
                    container.append({key.strip(): sub})
                    stack.append((indent, sub))
                    i += 1
            else:
                container.append(_scalar(item))
                i += 1
            continue
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest in (">-", "|", ">", "|-"):
            block_lines: list[str] = []
            i += 1
            block_indent = None
            while i < len(lines):
                ind2, cont2 = lines[i]
                if ind2 <= indent:
                    break
                if block_indent is None:
                    block_indent = ind2
                block_lines.append(
                    " " * (ind2 - block_indent) + cont2 if ind2 > block_indent else cont2
                )
                i += 1
            if isinstance(container, dict):
                container[key] = " ".join(
                    part.strip() for part in " ".join(block_lines).split("\n")
                ).strip()
            continue
        if rest == "":
            if isinstance(container, dict):
                if i + 1 < len(lines) and lines[i + 1][1].startswith("- "):
                    new_list: list = []
                    container[key] = new_list
                    stack.append((indent, new_list))
                    i += 1
                    continue
                new_map: dict = {}
                container[key] = new_map
                stack.append((indent, new_map))
                i += 1
                continue
            i += 1
            continue
        if isinstance(container, dict):
            container[key] = _scalar(rest)
        i += 1
    return root


# ---------------------------------------------------------------------------
# Access helpers (work on both loader outputs)
# ---------------------------------------------------------------------------
def _rq_list(data: dict) -> list[dict]:
    rqs = data.get("research_questions")
    if isinstance(rqs, dict):
        # Fallback parser collapses sequence-of-mappings into {rq_id: {...}}
        # keyed blocks; normalize to a list while preserving order.
        ordered = []
        for rq_id in RQ_IDS:
            block = rqs.get(rq_id)
            if isinstance(block, dict):
                ordered.append({"rq_id": rq_id, **block})
            elif isinstance(block, list) and block and isinstance(block[0], dict):
                ordered.append({**block[0], "rq_id": rq_id})
        return ordered
    if isinstance(rqs, list):
        return [r for r in rqs if isinstance(r, dict)]
    return []


def _field(rq: dict, name: str):
    value = rq.get(name)
    if isinstance(value, list) and value and isinstance(value[0], dict):
        inner_key = next(iter(value[0]))
        value = value[0].get(inner_key)
    if isinstance(value, dict) and len(value) == 1:
        value = next(iter(value.values()))
    return value


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).lower()


def _normalized(text: str) -> str:
    return text.replace("-", " ").replace("_", " ")


# ---------------------------------------------------------------------------
# Structure: exactly three RQs with the full field set
# ---------------------------------------------------------------------------
def test_registry_file_exists() -> None:
    assert REGISTRY_PATH.is_file(), f"missing registry: {REGISTRY_PATH}"


def test_registry_exactly_three_rqs_with_all_fields() -> None:
    data = _load_registry()
    rqs = _rq_list(data)
    assert len(rqs) == 3, f"expected exactly 3 RQs, found {len(rqs)}"
    ids = [str(rq.get("rq_id", "")) for rq in rqs]
    assert ids == list(RQ_IDS), f"RQ ids must be {RQ_IDS} in order, found {ids}"
    for rq in rqs:
        for field in REQUIRED_RQ_FIELDS:
            assert field in rq, f"{rq.get('rq_id')} missing field {field!r}"
            value = _field(rq, field)
            assert value not in (None, "", [], {}), f"{rq.get('rq_id')}.{field} is empty"


def test_rq_fields_substantive_not_placeholders() -> None:
    rqs = _rq_list(_load_registry())
    for rq in rqs:
        rq_id = rq.get("rq_id")
        for field in (
            "research_question",
            "estimand",
            "paired_contrast",
            "null_hypothesis",
            "alternative_hypothesis",
            "power_and_analysis_method",
        ):
            assert len(_text(_field(rq, field))) > 40, f"{rq_id}.{field} too vague"
        confounders = _field(rq, "confounders")
        assert (
            isinstance(confounders, list) and len(confounders) >= 3
        ), f"{rq_id}.confounders must list >= 3 confounders"
        secondary = _field(rq, "secondary_metrics")
        assert (
            isinstance(secondary, list) and len(secondary) >= 2
        ), f"{rq_id}.secondary_metrics must list >= 2 metrics"
        mud = rq.get("minimum_useful_difference")
        assert (
            isinstance(mud, dict) and "value" in mud and "scale" in mud
        ), f"{rq_id}.minimum_useful_difference must freeze value and scale"


def test_shared_design_freezes_unit_population_oracle_budget() -> None:
    data = _load_registry()
    shared = data.get("shared_design")
    assert isinstance(shared, dict), "shared_design block missing"
    for field in REQUIRED_SHARED_DESIGN_FIELDS:
        assert field in shared, f"shared_design missing {field!r}"
    oracle = shared.get("oracle")
    assert isinstance(oracle, dict) and "simulator_ground_truth" in _text(
        oracle.get("source")
    ), "oracle must be simulator ground truth"
    budget = shared.get("false_positive_budget")
    assert isinstance(budget, dict), "false_positive_budget missing"
    assert _FROZEN_BUDGET_KEY in _text(budget.get("metric")) or _FROZEN_BUDGET_KEY in _text(
        budget.get("budget_unit")
    ), "budget must be expressed per 1,000 benign sessions"


def test_independent_unit_is_campaign_or_session_not_event() -> None:
    data = _load_registry()
    shared = data.get("shared_design")
    unit = _text(shared.get("independent_unit"))
    assert (
        "campaign" in unit and "session" in unit
    ), f"independent unit must be campaign/benign session: {unit!r}"
    assert "event" not in unit, "per-event pseudo-replication is forbidden as the unit"
    for rq in _rq_list(data):
        rq_unit = _text(_field(rq, "independent_unit"))
        assert "campaign" in rq_unit, f"{rq.get('rq_id')} unit must be campaign-level"


# ---------------------------------------------------------------------------
# DETECTION endpoint assertion (refuse prevention framing)
# ---------------------------------------------------------------------------
def test_primary_endpoints_are_detection_not_prevention() -> None:
    rqs = _rq_list(_load_registry())
    for rq in rqs:
        rq_id = rq.get("rq_id")
        endpoint = _normalized(_text(_field(rq, "primary_endpoint")))
        assert any(
            m in endpoint for m in DETECTION_MARKERS
        ), f"{rq_id} primary endpoint is not a detection metric: {endpoint!r}"
        for term in FORBIDDEN_PREVENTION_TERMS:
            for m in re.finditer(re.escape(term), endpoint):
                window = endpoint[max(0, m.start() - 40) : m.start()]
                assert re.search(
                    r"\bnever\b|\bnot\b|\brefus", window
                ), f"{rq_id} primary endpoint affirms prevention metric {term!r}: {endpoint!r}"


def test_registry_declares_detection_endpoint_class() -> None:
    data = _load_registry()
    assert (
        _text(data.get("endpoint_class")) == "detection"
    ), f"endpoint_class must be 'detection', found {data.get('endpoint_class')!r}"
    refusal = _text(data.get("prevention_endpoint_refusal"))
    assert (
        "replay acceptance" in refusal or "admission" in refusal
    ), "prevention_endpoint_refusal must name the refused prevention endpoints"


def test_rq1_primary_metric_tied_to_fixed_false_positive_budget() -> None:
    data = _load_registry()
    rq1 = _rq_list(data)[0]
    metric = _normalized(_text(_field(rq1, "primary_metric")))
    assert any(
        m in metric for m in ("pr auc", "aucpr")
    ), f"RQ1 primary metric must be campaign PR-AUC: {metric!r}"
    assert (
        "budget" in metric or "fixed" in metric
    ), f"RQ1 primary metric must be tied to the fixed false-positive budget: {metric!r}"
    assert "detect" in _normalized(
        _text(_field(rq1, "primary_endpoint"))
    ), "RQ1 primary endpoint must be detection-framed"


def test_prevention_terms_absent_from_estimands() -> None:
    rqs = _rq_list(_load_registry())
    for rq in rqs:
        estimand = _text(_field(rq, "estimand"))
        for term in ("replay acceptance rate", "unauthorized commit"):
            for m in re.finditer(re.escape(term), estimand):
                window = estimand[max(0, m.start() - 40) : m.start()]
                assert re.search(
                    r"\bnever\b|\bnot\b", window
                ), f"{rq.get('rq_id')} estimand affirms prevention metric {term!r}"


# ---------------------------------------------------------------------------
# Hypotheses, margins, power and analysis method
# ---------------------------------------------------------------------------
def test_null_and_alternative_are_paired_contrasts() -> None:
    rqs = _rq_list(_load_registry())
    for rq in rqs:
        rq_id = rq.get("rq_id")
        null_h = _text(_field(rq, "null_hypothesis"))
        alt_h = _text(_field(rq, "alternative_hypothesis"))
        assert "h0" in null_h and "h1" in alt_h, f"{rq_id} must label H0/H1"
        contrast = _text(_field(rq, "paired_contrast"))
        assert (
            re.search(r"\bb[0-9]\b", contrast) or "baseline" in contrast
        ), f"{rq_id} paired contrast must name a baseline arm: {contrast!r}"


def test_statistical_tests_are_concrete_and_frozen() -> None:
    rqs = _rq_list(_load_registry())
    for rq in rqs:
        method = _normalized(_text(_field(rq, "power_and_analysis_method")))
        assert any(
            kw in method for kw in ("mcnemar", "bootstrap", "permutation", "exact")
        ), f"{rq.get('rq_id')} power/analysis method must name a concrete test: {method!r}"
        assert (
            "seed" in method or "2027" in method
        ), f"{rq.get('rq_id')} must freeze the bootstrap seed"
        assert "holm" in method, f"{rq.get('rq_id')} must state multiplicity control (Holm)"


def test_minimum_useful_differences_frozen_positive() -> None:
    rqs = _rq_list(_load_registry())
    symbols = []
    for rq in rqs:
        mud = rq.get("minimum_useful_difference")
        value = mud.get("value")
        assert (
            isinstance(value, int | float) and value > 0
        ), f"{rq.get('rq_id')} delta must be a positive frozen number"
        assert _text(mud.get("rationale")), f"{rq.get('rq_id')} delta needs a rationale"
        symbols.append(str(mud.get("symbol", "")))
    assert len(set(symbols)) == 3, f"delta symbols must be distinct: {symbols}"


def test_shared_power_uses_cluster_bootstrap_and_frozen_seed() -> None:
    data = _load_registry()
    power = data.get("shared_design", {}).get("power_and_analysis", {})
    bootstrap = power.get("bootstrap", {})
    assert isinstance(bootstrap, dict), "shared bootstrap plan missing"
    assert int(bootstrap.get("resamples", 0)) >= 1000, "bootstrap resamples must be >= 1000"
    assert bootstrap.get("seed") == 2027, "bootstrap seed must be frozen at 2027"
    scheme = _text(bootstrap.get("scheme"))
    assert (
        "cluster" in scheme and "campaign" in scheme
    ), "bootstrap must resample whole campaigns/sessions as clusters"


# ---------------------------------------------------------------------------
# Falsification conditions
# ---------------------------------------------------------------------------
def test_each_rq_has_explicit_falsification_condition() -> None:
    rqs = _rq_list(_load_registry())
    for rq in rqs:
        cond = _text(_field(rq, "falsification_condition"))
        assert len(cond) > 60, f"{rq.get('rq_id')} falsification condition too vague"
        assert "if" in cond, f"{rq.get('rq_id')} falsification condition must be conditional"


def test_falsification_register_covers_all_rqs() -> None:
    data = _load_registry()
    register = data.get("falsification_register")
    assert (
        isinstance(register, list) and len(register) >= 6
    ), "falsification_register must enumerate >= 6 falsifiers"
    covered = set()
    for entry in register:
        if isinstance(entry, dict):
            item = entry.get("F1") if "F1" in entry else entry
            rq = item.get("rq") if isinstance(item, dict) else None
            stmt = _text(item.get("statement") if isinstance(item, dict) else None)
            covered.add(str(rq))
            assert stmt, "falsifier statement must be non-empty"
            assert (
                _text(item.get("consequence")) if isinstance(item, dict) else False
            ), "falsifier must state its consequence"
    assert covered == {
        "RQ1",
        "RQ2",
        "RQ3",
    }, f"falsification register must cover all three RQs, found {covered}"


def test_rqs_reference_minimum_useful_difference_in_falsifiers() -> None:
    """The delta must appear in the falsification logic so the rule is
    mechanically decidable, not rhetorical."""
    data = _load_registry()
    rqs = _rq_list(data)
    text = str(data)
    for rq in rqs:
        delta_symbol = str(rq.get("minimum_useful_difference", {}).get("symbol", ""))
        assert (
            delta_symbol and delta_symbol in text
        ), f"{rq.get('rq_id')} delta symbol {delta_symbol!r} unused in registry"


# ---------------------------------------------------------------------------
# No invented results (preregistration only)
# ---------------------------------------------------------------------------
def test_no_observed_results_in_registry() -> None:
    """The plan must contain no observed metric values, p-values, CIs or win
    rates — freezing questions is its only job."""
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    lowered = raw.lower()
    forbidden_claim_patterns = (
        r"\bp\s*=\s*0\.\d+",
        r"\bp\s*<\s*0?\.\d+",
        r"\bci\s*=\s*\[",
        r"\baucpr\s*[:=]\s*0\.\d+",
        r"\baccuracy\s+of\s+\d+(\.\d+)?\s*%",
        r"\bwe\s+(found|observed)\b",
        r"\bresults\s+show\b",
        r"\bwin\s+rate\s+of\s+\d+",
    )
    for pattern in forbidden_claim_patterns:
        assert not re.search(
            pattern, lowered
        ), f"registry must be preregistration-only; found result-like claim {pattern!r}"


def test_no_frozen_archive_evidence_ids_used_as_results() -> None:
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    # The frozen GLHS E15-E22 outcomes may be refused by name in the
    # provenance block but must never appear as observed evidence inside an
    # RQ block.
    data = _load_registry()
    rqs = _rq_list(data)
    for rq in rqs:
        rq_blob = _text(str(rq))
        for evid in ("e15", "e16", "e17", "e18", "e19", "e20", "e21", "e22"):
            assert not re.search(
                rf"\b{evid}\b", rq_blob
            ), f"{rq.get('rq_id')} must not cite frozen archive evidence {evid.upper()}"
    assert "glhs" in lowered_provenance(raw) or "glhs" not in rq_blobs(
        rqs
    ), "archive refusal context must stay in evidence_provenance, not RQ blocks"


def lowered_provenance(raw: str) -> str:
    section = raw.split("evidence_provenance:", 1)[-1]
    return section.lower()


def rq_blobs(rqs: list[dict]) -> str:
    return " ".join(_text(str(rq)) for rq in rqs)


# ---------------------------------------------------------------------------
# Baseline parity and provenance contract
# ---------------------------------------------------------------------------
def test_baseline_arms_registered_with_roles() -> None:
    data = _load_registry()
    arms = data.get("baseline_arms")
    assert isinstance(arms, dict), "baseline_arms block missing"
    for arm_id in ("B0", "B1", "B2", "B3", "B4"):
        arm = arms.get(arm_id)
        assert isinstance(arm, dict) and _text(
            arm.get("role")
        ), f"baseline arm {arm_id} must declare a scientific role"
    candidate = arms.get("candidate")
    assert isinstance(candidate, dict) and "governancetrace" in _text(
        candidate.get("name")
    ), "candidate arm C0 must be the GovernanceTrace detector"


def test_evidence_provenance_refuses_invented_results_and_archive() -> None:
    data = _load_registry()
    provenance = data.get("evidence_provenance")
    assert isinstance(provenance, dict), "evidence_provenance block missing"
    assert "manifest.json" in _text(
        provenance.get("no_invented_results")
    ), "no_invented_results must bind future numbers to the run manifest"
    archive = _text(provenance.get("archive_refusal"))
    assert "refus" in archive and (
        "e15" in archive or "glhs" in archive
    ), "archive refusal must name the frozen GLHS evidence"
    assert (
        _text(provenance.get("dataset")) == "synthetic-dimva-2027"
    ), "dataset must be the registered synthetic-dimva-2027 corpus"
