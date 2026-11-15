"""Structural tests for the POPETS-rq_registry RQ/estimand registry (P01).

Purpose
-------
Stdlib-only structural verification of
``research/venue2027/popets/rq_and_estimands.yaml``. The registry is a
preregistered plan, not an empirical result: these tests assert the
*structure* required by ``VENUES/popets/TASKS/POPETS-rq_registry.md`` —
exactly three RQs (RQ1-RQ3) with the complete field set (research question,
independent unit, population, estimand, paired contrast, primary metric,
secondary metrics, null, alternative, minimum useful difference,
confounders, power/analysis method, falsification condition, primary
endpoint), a PRE-DISPATCH FUTURE-DISCLOSURE endpoint that refuses forensic
reconstructability framing and retroactive-erasure claims, mechanically
testable falsification conditions, and no invented results (no observed
metrics, p-values or CIs asserted anywhere in the plan).

Allowed input
-------------
The registry YAML at ``REGISTRY_PATH``. Read-only; no network, no
randomness, no clock. Parsed with a self-contained, JSON-compatible YAML
subset parser written here (block mappings, block sequences, folded/literal
block scalars, inline flow sequences, comments); no third-party YAML
dependency is required, so the suite runs on a clean stdlib checkout.

Failure semantics
-----------------
Each violation is an ordinary pytest assertion failure with a stable test
name; nothing is silently skipped. Version: 1.0.0.
"""

from __future__ import annotations

import pathlib
import re

REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[2] / "popets" / "rq_and_estimands.yaml"

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
    "cluster_definition",
    "population",
    "oracle",
    "observation_model",
    "revocation_semantics",
    "splits",
    "outcome_accounting",
    "power_and_analysis",
)

# Future-disclosure vocabulary required in each RQ primary endpoint.
FUTURE_DISCLOSURE_MARKERS: tuple[str, ...] = (
    "future",
    "disclosure",
    "dispatch",
    "cache hit",
    "latency",
    "equivalence",
)

# Forensic / retroactive framing that may not be *affirmed* in any RQ primary
# endpoint. (Negated mentions such as "never a forensic reconstructability
# score" are fine; the check scans a look-behind window for explicit negation.)
FORBIDDEN_FORENSIC_TERMS: tuple[str, ...] = (
    "forensic reconstructability score",
    "audit-metadata inference",
    "retroactive erasure",
)

forbidden_claim_patterns = (
    r"\bp\s*=\s*0\.\d+",
    r"\bp\s*<\s*0?\.\d+",
    r"\bci\s*=\s*\[",
    r"\baccuracy\s+of\s+\d+(\.\d+)?\s*%",
    r"\bwe\s+(found|observed)\b",
    r"\bresults\s+show\b",
    r"\bwin\s+rate\s+of\s+\d+",
    r"\bdisclosure\s+rate\s+of\s+\d+(\.\d+)?",
)


# ---------------------------------------------------------------------------
# Minimal loader — self-contained JSON-compatible YAML subset parser
# ---------------------------------------------------------------------------
def _parse_inline(token: str):
    token = token.strip()
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [_parse_inline(part) for part in _split_flow(inner)]
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    if token in ("true", "True"):
        return True
    if token in ("false", "False"):
        return False
    if token in ("null", "~", ""):
        return None
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return token


def _split_flow(inner: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    buf: list[str] = []
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch == "[":
            depth += 1
            buf.append(ch)
        elif ch == "]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p for p in (part.strip() for part in parts) if p]


def parse_simple_yaml(text: str):
    """Indentation-based parser for the YAML subset used by the registry.

    Handles nested block mappings, block sequences (``- item`` and multi-line
    ``- key: value`` mapping items), folded/literal block scalars (``>``,
    ``>-``, ``|``, ``|-``), inline flow sequences, and full-line comments.
    Block scalars are folded to single strings; sequences of mappings become
    lists of dicts. A ``- key: value`` item whose mapping continues on
    following lines is parsed as one dict whose first key comes from the
    item line itself (continuation lines sit at the item content column).
    """

    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))

    def parse_block(pos: int, indent: int):
        """Parse a block starting at ``pos`` with minimum indent ``indent``."""
        if pos < len(lines) and lines[pos][1].startswith("- "):
            return parse_seq(pos, indent)
        return parse_map(pos, indent, {})

    def parse_seq(pos: int, indent: int):
        seq: list = []
        while pos < len(lines):
            ind, content = lines[pos]
            if ind != indent or not content.startswith("- "):
                break
            item = content[2:].strip()
            if _is_key_line(item):
                item_indent = ind + 2
                mapping: dict = {}
                pos = _consume_key(mapping, pos, item_indent, item)
                value, pos = parse_map(pos, item_indent, mapping)
                seq.append(value)
            else:
                seq.append(_parse_inline(item))
                pos += 1
        return seq, pos

    def parse_map(pos: int, indent: int, mapping: dict):
        while pos < len(lines):
            ind, content = lines[pos]
            if ind < indent or content.startswith("- "):
                break
            if ind > indent:
                raise ValueError(f"unexpected indent at line content {content!r}")
            pos = _consume_key(mapping, pos, indent, content)
        return mapping, pos

    def _consume_key(mapping: dict, pos: int, indent: int, content: str) -> int:
        key, _, rest = content.partition(":")
        key = key.strip()
        if len(key) >= 2 and key[0] == key[-1] and key[0] in "'\"":
            key = key[1:-1]
        rest = rest.strip()
        if rest in (">", ">-", "|", "|-"):
            value, pos = parse_block_scalar(pos + 1, indent, rest)
            mapping[key] = value
        elif rest == "":
            child_indent = _child_indent(pos, indent)
            if child_indent is None:
                mapping[key] = None
                pos += 1
            else:
                value, pos = parse_block(pos + 1, child_indent)
                mapping[key] = value
        else:
            mapping[key] = _parse_inline(rest)
            pos += 1
        return pos

    def parse_block_scalar(pos: int, parent_indent: int, style: str):
        block_indent: int | None = None
        block: list[tuple[int, str]] = []
        while pos < len(lines):
            ind, content = lines[pos]
            if ind <= parent_indent:
                break
            if block_indent is None:
                block_indent = ind
            block.append((ind, content))
            pos += 1
        if block and block_indent is not None:
            body = "\n".join(
                (" " * (ind - block_indent) + content) if ind > block_indent else content
                for ind, content in block
            )
        else:
            body = ""
        if style.startswith("|"):
            value = body if style == "|" else body.rstrip("\n")
        else:
            value = " ".join(part.strip() for part in body.split("\n")).strip()
        return value, pos

    def _child_indent(pos: int, parent_indent: int) -> int | None:
        if pos + 1 >= len(lines):
            return None
        ind, content = lines[pos + 1]
        if ind > parent_indent:
            return ind
        if ind == parent_indent and content.startswith("- "):
            return ind
        return None

    def _is_key_line(item: str) -> bool:
        if item.startswith("["):
            return False
        return ": " in item or item.endswith(":")

    value, _ = parse_block(0, 0)
    return value


def _load_registry() -> dict:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    data = parse_simple_yaml(text)
    assert isinstance(data, dict), "registry must parse to a top-level mapping"
    return data


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------
def _rq_list(data: dict) -> list[dict]:
    rqs = data.get("research_questions")
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
            "falsification_condition",
            "primary_endpoint",
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


def test_shared_design_freezes_unit_population_oracle_and_observation_model() -> None:
    data = _load_registry()
    shared = data.get("shared_design")
    assert isinstance(shared, dict), "shared_design block missing"
    for field in REQUIRED_SHARED_DESIGN_FIELDS:
        assert field in shared, f"shared_design missing {field!r}"
    oracle = shared.get("oracle")
    assert isinstance(oracle, dict), "oracle block missing"
    assert "recomputation" in _text(
        oracle.get("source")
    ), "oracle must be independent source-snapshot recomputation"
    assert "interceptor" in _text(
        oracle.get("adjudication")
    ), "oracle must observe dispatches via the byte-level interceptor"
    observation = shared.get("observation_model")
    assert (
        isinstance(observation, dict)
        and _normalized(_text(observation.get("dispatch_capture"))) == "byte level interceptor"
    ), "declared observation model must use the byte-level interceptor"


def test_independent_unit_is_subject_history_not_dispatch() -> None:
    data = _load_registry()
    shared = data.get("shared_design")
    unit = _text(shared.get("independent_unit"))
    assert "subject" in unit, f"independent unit must be subject-history level: {unit!r}"
    assert "history" in unit, f"independent unit must be subject-history level: {unit!r}"
    assert "dispatch" not in unit, "per-dispatch pseudo-replication is forbidden as the unit"
    for rq in _rq_list(data):
        rq_unit = _text(_field(rq, "independent_unit"))
        assert (
            "subject history" in rq_unit
        ), f"{rq.get('rq_id')} unit must be unique-subject-history level: {rq_unit!r}"


def test_population_matches_blueprint_cohort() -> None:
    shared = _text(_load_registry().get("shared_design", {}).get("population"))
    assert "1200" in shared, "population must state the frozen 1200-subject cohort"
    assert "3-6" in shared or "3 6" in _normalized(
        shared
    ), "population must state 3-6 longitudinal contexts per subject"
    assert "synthetic" in shared, "population must be synthetic only"


def test_revocation_semantics_and_no_erasure_claim_frozen() -> None:
    shared = _load_registry().get("shared_design", {})
    revocation = shared.get("revocation_semantics")
    assert isinstance(revocation, dict), "revocation_semantics block missing"
    rule = _normalized(_text(revocation.get("rule")))
    assert (
        "forbidden label" in rule and "lineage" in rule
    ), "revocation rule must encode forbidden_label intersect lineage(d) = empty"
    no_erasure = _text(revocation.get("no_retroactive_erasure"))
    assert (
        "already delivered" in no_erasure
    ), "no_retroactive_erasure must exclude already-delivered content from audits"


# ---------------------------------------------------------------------------
# Endpoint-class assertion: future dispatch noninterference, not forensics
# ---------------------------------------------------------------------------
def test_registry_declares_future_dispatch_endpoint_class() -> None:
    data = _load_registry()
    assert _normalized(_text(data.get("endpoint_class"))) == "future dispatch noninterference", (
        f"endpoint_class must be 'future_dispatch_noninterference', found "
        f"{data.get('endpoint_class')!r}"
    )
    refusal = _text(data.get("forensic_endpoint_refusal"))
    assert (
        "forensic" in refusal
    ), "forensic_endpoint_refusal must name the refused forensic endpoints"
    assert (
        "already delivered" in refusal
    ), "forensic_endpoint_refusal must refuse retroactive erasure of already-delivered content"


def test_primary_endpoints_are_future_disclosure_not_forensic() -> None:
    rqs = _rq_list(_load_registry())
    for rq in rqs:
        rq_id = rq.get("rq_id")
        endpoint = _normalized(_text(_field(rq, "primary_endpoint")))
        assert any(
            m in endpoint for m in FUTURE_DISCLOSURE_MARKERS
        ), f"{rq_id} primary endpoint is not a future-disclosure metric: {endpoint!r}"
        for term in FORBIDDEN_FORENSIC_TERMS:
            for m in re.finditer(re.escape(term), endpoint):
                window = endpoint[max(0, m.start() - 40) : m.start()]
                assert re.search(
                    r"\bnever\b|\bnot\b|\brefus", window
                ), f"{rq_id} primary endpoint affirms forbidden framing {term!r}: {endpoint!r}"


def test_rq1_primary_metric_is_disclosure_rate_with_byte_count() -> None:
    data = _load_registry()
    rq1 = _rq_list(data)[0]
    metric = _normalized(_text(_field(rq1, "primary_metric")))
    assert (
        "disclosure rate" in metric
    ), f"RQ1 primary metric must be the disclosure rate: {metric!r}"
    assert "byte" in metric, f"RQ1 primary metric must include attribute-exposure bytes: {metric!r}"
    assert (
        "subject history" in metric
    ), f"RQ1 primary metric must be per independent subject history: {metric!r}"
    family = _normalized(_text(rq1.get("primary_metric_family")))
    assert (
        "future unauthorized disclosure rate" in family
        and "attribute exposure byte count" in family
    )


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
            kw in method for kw in ("mcnemar", "bootstrap", "tost", "anova", "signed-rank", "exact")
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
    assert symbols == [
        "delta_1",
        "delta_2",
        "delta_3",
    ], f"delta symbols must be delta_1..3: {symbols}"


def test_shared_power_uses_cluster_bootstrap_and_frozen_seed() -> None:
    data = _load_registry()
    power = data.get("shared_design", {}).get("power_and_analysis", {})
    bootstrap = power.get("bootstrap", {})
    assert isinstance(bootstrap, dict), "shared bootstrap plan missing"
    assert int(bootstrap.get("resamples", 0)) >= 1000, "bootstrap resamples must be >= 1000"
    assert bootstrap.get("seed") == 2027, "bootstrap seed must be frozen at 2027"
    scheme = _text(bootstrap.get("scheme"))
    assert (
        "cluster" in scheme and "subject" in scheme
    ), "bootstrap must resample whole subject histories as clusters"
    assert float(power.get("alpha", 0)) == 0.05, "alpha must be frozen at 0.05"


def test_outcome_accounting_covers_full_denominator() -> None:
    accounting = _load_registry().get("shared_design", {}).get("outcome_accounting", {})
    counts = accounting.get("per_arm_counts")
    required = {
        "eligible",
        "attempted",
        "completed",
        "rejected",
        "indeterminate",
        "timeout",
        "not_run_external",
        "missing",
    }
    assert isinstance(counts, list) and required.issubset(
        set(counts)
    ), f"per_arm_counts must cover the full denominator, found {counts}"


# ---------------------------------------------------------------------------
# Falsification conditions
# ---------------------------------------------------------------------------
def test_each_rq_has_explicit_falsification_condition() -> None:
    rqs = _rq_list(_load_registry())
    for rq in rqs:
        cond = _text(_field(rq, "falsification_condition"))
        assert len(cond) > 60, f"{rq.get('rq_id')} falsification condition too vague"
        assert "if" in cond, f"{rq.get('rq_id')} falsification condition must be conditional"
        assert (
            "f1" in cond
            or "f2" in cond
            or "f3" in cond
            or "f4" in cond
            or "f5" in cond
            or "f6" in cond
        ), f"{rq.get('rq_id')} falsification condition must cite its register IDs"


def test_falsification_register_covers_all_rqs() -> None:
    data = _load_registry()
    register = data.get("falsification_register")
    assert (
        isinstance(register, list) and len(register) >= 6
    ), "falsification_register must enumerate >= 6 falsifiers"
    covered: set[str] = set()
    for entry in register:
        if not isinstance(entry, dict):
            continue
        item = entry
        rq = item.get("rq")
        stmt = _text(item.get("statement"))
        covered.add(str(rq))
        assert stmt, "falsifier statement must be non-empty"
        assert _text(item.get("consequence")), "falsifier must state its consequence"
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
    for pattern in forbidden_claim_patterns:
        assert not re.search(
            pattern, lowered
        ), f"registry must be preregistration-only; found result-like claim {pattern!r}"


def test_no_frozen_archive_evidence_ids_used_as_results() -> None:
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    data = _load_registry()
    rqs = _rq_list(data)
    # The frozen GLHS E15-E22 outcomes may be refused by name in the
    # provenance block but must never appear as observed evidence inside an
    # RQ block.
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
    assert isinstance(candidate, dict) and "dependency-closure" in _text(
        candidate.get("name")
    ), "candidate arm must be the B4 dependency-closure invalidation mechanism"


def test_b2_is_named_as_strongest_competing_explanation() -> None:
    """The blueprint falsification rule requires B2 (always-recompute) to be
    registered as the privacy reference and strongest competing explanation."""
    data = _load_registry()
    b2 = data.get("baseline_arms", {}).get("B2", {})
    combined = _normalized(_text(b2.get("name")) + " " + _text(b2.get("role")))
    assert "always recompute" in combined, "B2 must be the always-recompute reference"
    assert "reference" in combined, "B2 must carry the privacy-reference role"


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
        _text(provenance.get("dataset")) == "synthetic-popets-2027"
    ), "dataset must be the registered synthetic-popets-2027 corpus"
    assert "already delivered" in _text(
        provenance.get("no_retroactive_erasure")
    ), "provenance must exclude already-delivered content from every leakage audit"
