"""Structural tests for the PST-rq_registry RQ/estimand registry (P01).

Purpose
-------
Stdlib-only structural verification of
``research/venue2027/pst/rq_and_estimands.yaml``. The registry is a
preregistered plan, not an empirical result: these tests assert the
*structure* required by ``VENUES/pst/TASKS/PST-rq_registry.md`` and
novelty-contract Condition 1 — exactly three RQs (RQ1-RQ3) with the
complete field set (research question verbatim from the blueprint,
independent unit, population, estimand, paired contrast, primary metric,
secondary metrics, null, alternative, minimum useful difference,
confounders, power/analysis method, falsification condition, primary
endpoint), the reconstructability endpoint class (explicitly NOT a new
access-control mechanism), the PoPETs differentiation, mechanically
testable falsification conditions, and no invented results (no observed
metrics, p-values, CIs, advantages or ratios asserted anywhere in the
plan).

Allowed input
-------------
The registry YAML at ``REGISTRY_PATH`` and the PST novelty contract at
``CONTRACT_PATH``. Read-only; no network, no randomness, no clock. Parsed
with the repository's PyYAML if available and otherwise with a minimal
indentation-based fallback parser restricted to the block-mapping /
sequence subset this registry uses; either path produces the same plain
nested dict/list structure.

Failure semantics
-----------------
Each violation is an ordinary pytest assertion failure with a stable test
name; nothing is silently skipped. Version: 1.0.0.
"""

from __future__ import annotations

import pathlib
import re

REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[2] / "pst" / "rq_and_estimands.yaml"
CONTRACT_PATH = pathlib.Path(__file__).resolve().parents[2] / "pst" / "novelty_contract.md"

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
    "unit_definition",
    "population",
    "oracle",
    "forensic_query_set",
    "attacker_model",
    "splits",
    "outcome_accounting",
    "power_and_analysis",
)

# Blueprint-verbatim research questions (VENUES/pst/RESEARCH_BLUEPRINT.md).
BLUEPRINT_RQ_TEXT: dict[str, str] = {
    "RQ1": (
        "What fraction of legitimate forensic questions remain answerable "
        "under hash-only, encrypted, and selective retention receipts?"
    ),
    "RQ2": (
        "Can linkage and attribute exposure be bounded under compromised "
        "read-only audit access, including auxiliary-data joins?"
    ),
    "RQ3": (
        "What retention, key deletion and proof-generation costs emerge "
        "across audit volumes and retention epochs?"
    ),
}

# Reconstructability-endpoint markers required in each RQ primary endpoint.
RECONSTRUCTABILITY_MARKERS: tuple[str, ...] = (
    "frontier",
    "reconstructability",
    "reconstruction-versus-linkability",
)

# Access-control framing that may not be *affirmed* in any endpoint or the
# contribution class. (Negated mentions such as "not an access-control
# mechanism" are fine; the check below scans a look-behind window for
# explicit negation.)
FORBIDDEN_ACCESS_CONTROL_TERMS: tuple[str, ...] = (
    "new access-control mechanism",
    "new authorization enforcement mechanism",
    "novel access-control mechanism",
)

# Sibling endpoints owned by other 2027 venues; PST must refuse them.
SIBLING_ENDPOINT_TERMS: tuple[str, ...] = (
    "revoked-context re-disclosure rate",
    "replay acceptance rate",
    "crash-consistency violation rate",
    "conformance divergence detection rate",
    "probing detection pr-auc",
    "unsafe clinical action rate",
)

# Empirical-value inventing patterns: an observed-value assertion in a
# design-time preregistration. Metric names and planning constants are
# fine; asserted observations are not.
OBSERVED_VALUE_PATTERNS: tuple[str, ...] = (
    r"answerability\s*=\s*0?\.\d+",
    r"advantage\s*=\s*0?\.\d+",
    r"attacker advantage of\s*0?\.\d+",
    r"linkability precision\s*=\s*0?\.\d+",
    r"retained bytes\s*=\s*\d+",
    r"latency\s*=\s*\d+(\.\d+)?\s*ms",
    r"p-value\s*=\s*0?\.\d+",
    r"recovered\s*\d+\s*bytes",
)

REQUIRED_PLANNING_CONSTANTS: tuple[str, ...] = (
    "20271115",
    "0.05",
    "0.10",
    "0.15",
    "10000",
)

BASELINE_ARMS: tuple[str, ...] = ("B0", "B1", "B2", "B3", "B4")

OUTCOME_STATUSES: tuple[str, ...] = (
    "eligible",
    "attempted",
    "completed",
    "rejected",
    "indeterminate",
    "timeout",
    "not_run_external",
    "missing",
)


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


def _parse_simple_yaml(text: str) -> dict:
    """Fallback parser for the block-mapping/sequence subset used here.

    Handles nested block mappings, block sequences, folded scalars
    (``>-`` / ``|``) and inline flow sequences. Folded continuation lines
    (deeper-indented plain text) are joined into their parent key, matching
    the registry's authored subset.
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
                # Push the mapping item at the item marker's own indent so its
                # child keys (at indent + 2) stay inside the item block and the
                # next "- " at this same indent pops it (next item).
                stack.append((indent, item))
                i += 1
            else:
                item.setdefault("_item", _scalar(body))
                i += 1
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val in (">-", "|", ">", "|-"):
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
                container[key] = " ".join(part.strip() for part in " ".join(block).split("\n")).strip()
            continue
        if val == "":
            nxt = lines[i + 1][1] if i + 1 < len(lines) else ""
            child: dict | list
            if nxt.startswith("- "):
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
        return [item.strip() for item in inner.split(",")] if inner else []
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


def _field(rq: dict, name: str):
    """Fetch a field tolerating the power-method key's two spellings."""
    if name in rq:
        return rq[name]
    if name == "power_and_analysis_method" and "power_and_analysis" in rq:
        return rq["power_and_analysis"]
    return None


def _text(value) -> str:
    if isinstance(value, dict):
        return " ".join(str(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value)


def _folded(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _rq_list(data: dict) -> list:
    rqs = data.get("research_questions")
    assert isinstance(rqs, list), "research_questions must be a list"
    return rqs


def _negated(window: str, term: str) -> bool:
    """True if every occurrence of ``term`` in ``window`` is explicitly negated."""
    for match in re.finditer(re.escape(term), window):
        look_behind = window[max(0, match.start() - 60) : match.start()].lower()
        if not re.search(r"\b(not|never|no|refuse[ds]?|forbid|out of scope|isn't)\b", look_behind):
            return False
    return True


# ---------------------------------------------------------------------------
# Structure: exactly three RQs with the full field set
# ---------------------------------------------------------------------------
def test_registry_file_exists() -> None:
    assert REGISTRY_PATH.is_file(), f"missing registry: {REGISTRY_PATH}"


def test_registry_header_and_identity() -> None:
    data = _load_registry()
    assert data.get("schema_version") == "clara.venue2027.rq_registry.v1"
    assert data.get("venue") == "pst"
    assert data.get("task_id") == "PST-rq_registry"
    assert data.get("phase") == "P01"
    assert "ReceiptMin" in str(data.get("study_title", "")), "paper title missing"
    assert (
        data.get("preregistration_status") == "frozen_before_any_arm_runs"
    ), "preregistration status must declare freezing before any arm runs"
    assert data.get("dataset") == "synthetic-pst-2027", "dataset declaration missing"
    assert data.get("reuses_archive") == [], "archive reuse must be empty"


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
    data = _load_registry()
    for rq in _rq_list(data):
        rq_id = rq.get("rq_id")
        for field in (
            "research_question",
            "estimand",
            "paired_contrast",
            "null_hypothesis",
            "alternative_hypothesis",
            "power_and_analysis_method",
            "falsification_condition",
            "primary_endpoint",
        ):
            assert len(_folded(_text(_field(rq, field)))) > 60, f"{rq_id}.{field} too vague"
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


# ---------------------------------------------------------------------------
# Positive controls: blueprint verbatim + reconstructability endpoint class
# ---------------------------------------------------------------------------
def test_rq_text_verbatim_from_blueprint() -> None:
    data = _load_registry()
    for rq in _rq_list(data):
        rq_id = rq.get("rq_id")
        expected = _folded(BLUEPRINT_RQ_TEXT[rq_id])
        actual = _folded(_text(_field(rq, "research_question")))
        assert expected in actual, f"{rq_id}: research_question not verbatim from blueprint"


def test_independent_unit_is_history_not_event() -> None:
    data = _load_registry()
    shared = data.get("shared_design", {})
    unit = _text(shared.get("unit_definition")) + " " + _text(shared.get("independent_unit"))
    assert "case history" in _folded(unit), "independent unit must be a case history"
    assert "pseudo-replication" in _folded(unit) or "never treated as independent" in _folded(
        unit
    ), "anti-pseudo-replication rule must be stated in the unit definition"
    for rq in _rq_list(data):
        rq_unit = _folded(_text(_field(rq, "independent_unit")))
        assert (
            "history" in rq_unit or "subject" in rq_unit
        ), f"{rq.get('rq_id')} unit must be history/subject-level, got {rq_unit!r}"
        assert "per-event" not in rq_unit.replace(
            "never a per-event", ""
        ), f"{rq.get('rq_id')} must not adopt a per-event unit"


def test_primary_endpoints_are_reconstructability_frontier() -> None:
    data = _load_registry()
    for rq in _rq_list(data):
        endpoint = _folded(_text(_field(rq, "primary_endpoint")))
        hit = [m for m in RECONSTRUCTABILITY_MARKERS if m in endpoint]
        assert hit, (
            f"{rq.get('rq_id')} primary_endpoint must name a reconstructability/frontier "
            f"marker, got {endpoint!r}"
        )


def test_no_access_control_mechanism_claim() -> None:
    data = _load_registry()
    assert (
        data.get("contribution_class") == "measurement_not_access_control_mechanism"
    ), "contribution_class must declare measurement, not access control"
    assert "access_control_boundary" in data, "access-control boundary block missing"
    for rq in _rq_list(data):
        window = _folded(
            _text(_field(rq, "primary_endpoint")) + " " + _text(_field(rq, "estimand"))
        )
        for term in FORBIDDEN_ACCESS_CONTROL_TERMS:
            assert _negated(
                window, term
            ), f"{rq.get('rq_id')} affirms forbidden access-control claim {term!r}"
    # The novelty contract itself must carry the same boundary.
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "does not propose a new access-control mechanism" in contract


def test_no_sibling_venue_endpoint_affirmed() -> None:
    data = _load_registry()
    for rq in _rq_list(data):
        window = _folded(
            _text(_field(rq, "primary_endpoint"))
            + " "
            + _text(_field(rq, "primary_metric"))
            + " "
            + _text(_field(rq, "estimand"))
        )
        for term in SIBLING_ENDPOINT_TERMS:
            assert _negated(
                window, term
            ), f"{rq.get('rq_id')} affirms sibling-venue endpoint {term!r}"


# ---------------------------------------------------------------------------
# Shared design: oracle, attacker model, splits, accounting
# ---------------------------------------------------------------------------
def test_shared_design_freezes_unit_population_oracle_attacker() -> None:
    data = _load_registry()
    shared = data.get("shared_design")
    assert isinstance(shared, dict), "shared_design block missing"
    for field in REQUIRED_SHARED_DESIGN_FIELDS:
        assert field in shared, f"shared_design missing {field!r}"
    oracle = shared.get("oracle")
    assert isinstance(oracle, dict), "oracle block missing"
    oracle_text = _folded(_text(oracle))
    assert (
        "trusted offline complete ledger" in oracle_text
    ), "oracle must be the trusted offline complete ledger"
    assert (
        "never imports" in oracle_text or "candidate never imports" in oracle_text
    ), "oracle independence (no candidate import) must be declared"
    attacker = shared.get("attacker_model")
    assert isinstance(attacker, dict), "attacker_model block missing"
    attacker_text = _folded(_text(attacker))
    assert "read-only audit reader" in attacker_text, "compromised audit reader missing"
    assert "auxiliary" in attacker_text, "auxiliary-data join attacker missing"
    query_set = shared.get("forensic_query_set")
    assert isinstance(query_set, dict), "forensic_query_set block missing"
    assert _folded(_text(query_set)).count("frozen") >= 1, "query set must be frozen ex ante"


def test_baseline_arms_registered_with_roles() -> None:
    data = _load_registry()
    arms = data.get("baseline_arms")
    assert isinstance(arms, dict), "baseline_arms block missing"
    for arm in BASELINE_ARMS:
        assert arm in arms, f"baseline arm {arm} missing"
        assert "role" in arms[arm], f"baseline arm {arm} missing role"
    assert "not_run_external" in _folded(
        _text(arms)
    ), "NOT_RUN_EXTERNAL transparency status must be declared"
    assert "never replaced by an unnamed custom surrogate" in _folded(
        _text(arms)
    ), "NOT_RUN_EXTERNAL must never be replaced by an unnamed surrogate"


def test_outcome_accounting_reports_all_statuses() -> None:
    data = _load_registry()
    accounting = _folded(_text(data.get("shared_design", {}).get("outcome_accounting")))
    for status in OUTCOME_STATUSES:
        assert status in accounting, f"outcome status {status!r} missing from accounting"
    assert (
        "never" in accounting and "coerce" in accounting
    ), "INDETERMINATE non-coercion rule missing"


# ---------------------------------------------------------------------------
# Hypotheses, margins, power, seeds
# ---------------------------------------------------------------------------
def test_hypotheses_are_directional_with_registered_bounds() -> None:
    data = _load_registry()
    for rq in _rq_list(data):
        rq_id = rq.get("rq_id")
        h0 = _folded(_text(_field(rq, "null_hypothesis")))
        h1 = _folded(_text(_field(rq, "alternative_hypothesis")))
        assert h0 and h1, f"{rq_id} must state directional null and alternative"
        assert re.search(r"\d+\.\d+", h0), f"{rq_id} null must state a numeric bound"
        assert re.search(r"\d+\.\d+", h1), f"{rq_id} alternative must state a numeric bound"


def test_frozen_constants_present() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    for constant in REQUIRED_PLANNING_CONSTANTS:
        assert constant in text, f"design-time constant {constant!r} missing"
    assert (
        text.count("seed 20271115") >= 2
    ), "fixed analysis seed 20271115 must pin bootstrap resampling"


def test_statistical_tests_are_concrete_and_frozen() -> None:
    text = _folded(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert "permutation test" in text, "permutation test method missing"
    assert "bootstrap" in text, "bootstrap CI method missing"
    assert "holm" in text, "multiplicity correction missing"
    assert "clopper-pearson" in text, "zero-event Clopper-Pearson bound missing"
    assert "assert_frozen_analysis" in text, "frozen-plan drift guard reference missing"
    assert "analysis_policy" in text, "shared analysis_policy reference missing"


def test_power_uses_pilot_and_predeclared_denominator() -> None:
    data = _load_registry()
    power = _folded(_text(data.get("shared_design", {}).get("power_and_analysis")))
    assert "pilot" in power, "pilot variance estimation missing"
    assert (
        "never chosen from target p-values" in power
    ), "prospective sample size must not be chosen from target p-values"
    for rq in _rq_list(data):
        rq_id = rq.get("rq_id")
        method = _folded(_text(_field(rq, "power_and_analysis_method")))
        assert "denominator" in method, f"{rq_id} must declare its primary denominator"
        for status in ("eligible", "indeterminate", "not_run_external"):
            assert status in method, f"{rq_id} power method must report {status} counts"


# ---------------------------------------------------------------------------
# Adversarial controls: falsification, no invented results, provenance
# ---------------------------------------------------------------------------
def test_each_rq_has_explicit_falsification_condition() -> None:
    data = _load_registry()
    for rq in _rq_list(data):
        falsifier = _folded(_text(_field(rq, "falsification_condition")))
        assert falsifier, f"{rq.get('rq_id')} missing falsification condition"
        assert "reject" in falsifier, f"{rq.get('rq_id')} falsifier must state rejection"


def test_falsification_register_covers_all_rqs_and_study_level() -> None:
    data = _load_registry()
    register = data.get("falsification_register")
    assert isinstance(register, list) and register, "falsification_register missing"
    rq_falsifiers = {entry.get("rq") for entry in register}
    for rq_id in RQ_IDS:
        assert rq_id in rq_falsifiers, f"falsification register missing {rq_id}"
    assert (
        "study_level" in rq_falsifiers
    ), "study-level B2-dominance falsification rule missing from register"
    study_level = [e for e in register if e.get("rq") == "study_level"]
    assert any(
        "B2" in _text(e.get("statement", "")) for e in study_level
    ), "study-level falsifier must name the B2 encrypted-log dominance rule"


def test_falsification_conditions_match_novelty_contract() -> None:
    blocks = {
        rq.get("rq_id"): _folded(_text(_field(rq, "falsification_condition")))
        for rq in _rq_list(_load_registry())
    }
    assert "margin m1" in blocks["RQ1"], "RQ1 falsifier must reference the frozen margin m1"
    assert "b1" in blocks["RQ1"], "RQ1 falsifier must cover the B1-indistinguishability case"
    assert "0.10" in blocks["RQ2"], "RQ2 falsifier must reference the registered exposure bound"
    assert "b1/b2" in blocks["RQ2"], "RQ2 falsifier must cover the B1/B2-advantage case"
    assert "b3 and b2" in blocks["RQ3"], "RQ3 falsifier must reference B3/B2 joint dominance"
    assert "equivalence margin" in blocks["RQ3"], "RQ3 falsifier must check equivalence"
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "dominates the minimized receipts (B4) on privacy (RQ2 exposure bounds)" in contract or (
        "dominates" in contract and "RQ2" in contract
    ), "novelty contract must commit the same B2-dominance gate"


def test_no_invented_observed_values() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    for pattern in OBSERVED_VALUE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        assert match is None, (
            f"pattern {pattern!r} matched {match.group(0)!r} — observed values are "
            "forbidden in a preregistration"
        )
    assert "manifest.json" in text, "observed values must route via run manifests"
    assert "preregistered" in _folded(text) or "preregistration" in _folded(
        text
    ), "preregistration declaration missing"


def test_no_frozen_archive_evidence_used_as_results() -> None:
    text = _folded(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert "e15" in text, "archive refusal must name the frozen E15–E22 rows"
    assert "healthinf" in text, "archive refusal must name the accepted HEALTHINF paper"
    assert "refused" in text or "background" in text, "refusal wording missing"
    assert (
        "reuses_archive: []" in text or "reuses_archive" in text
    ), "reuses_archive declaration missing"


def test_popets_differentiation_is_declared() -> None:
    text = _folded(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert "popets" in text, "PoPETs differentiation missing"
    assert (
        "revoked-context re-disclosure rate" in text
    ), "PoPETs sibling endpoint must be named to differentiate"
    assert (
        "never a pst baseline" in text or "is never a pst baseline" in text
    ), "the PoPETs cache-invalidator must be refused as a PST baseline"
    assert "post hoc" in text, "PST must state its post hoc (not future-facing) direction"


def test_no_placeholder_text() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    for marker in ("TBD", "TODO", "FIXME", "XXX", "<placeholder"):
        assert marker not in text, f"placeholder {marker!r} present"


def test_evidence_provenance_block_present() -> None:
    data = _load_registry()
    provenance = data.get("evidence_provenance")
    assert isinstance(provenance, dict), "evidence_provenance block missing"
    for field in (
        "no_invented_results",
        "oracle_independence",
        "archive_refusal",
        "popets_separation",
        "holdout_discipline",
    ):
        assert field in provenance, f"evidence_provenance missing {field!r}"
        assert len(_folded(_text(provenance[field]))) > 40, f"evidence_provenance.{field} too vague"
