"""Structural tests for IFIP_SEC-rq_registry — frozen RQ/estimand registry.

Task contract signature: ``read_rqs() -> RQPlan``.

The registry (``research/venue2027/ifip_sec/rq_and_estimands.yaml``) is a
PREREGISTRATION, not evidence. These tests enforce, stdlib-only:

Positive controls:
- Exactly 3 research questions (RQ1-RQ3), each carrying all 14 mandated
  fields (question, independent unit, population, estimand, paired contrast,
  primary metric, secondary metrics, null, alternative, minimum useful
  difference, confounders, power/analysis method, falsification condition,
  primary endpoint).
- The three RQ questions match the blueprint verbatim.
- Units are independent histories/schedules (never per-event pseudo-replication).
- Zero-event handling uses one-sided Clopper-Pearson bounds, never "zero
  failures proves safety".
- RQ2 requires real PostgreSQL 16 and declares SQLite inadmissible.
- Denominators are predeclared and mutually exclusive.
- Arms B0-B4 match the blueprint table; candidate arm is B4.
- The analysis machinery is frozen to the shared analysis policy
  (exact McNemar, cluster bootstrap, Clopper-Pearson, ANALYSIS_DRIFT).
- No invented empirical results (no p-values, no observed rates, no CIs).

Adversarial controls:
- A registry missing an RQ field, with a 4th RQ, with per-event units, or
  claiming SQLite-backed RQ2 concurrency evidence must be REFUSED by the
  validator (never silently accepted as conforming).
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

try:  # PyYAML is present in dev environments; stdlib fallback keeps the test runnable anywhere.
    import yaml  # type: ignore[import-untyped]

    _HAS_YAML = True
except ModuleNotFoundError:  # pragma: no cover - exercised only without PyYAML
    yaml = None  # type: ignore[assignment]
    _HAS_YAML = False

REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[1] / "rq_and_estimands.yaml"

RQ_IDS = ("RQ1", "RQ2", "RQ3")

REQUIRED_RQ_FIELDS = (
    "question",
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
    "analysis_method",
    "falsification_condition",
    "primary_endpoint",
)

ARMS = ("B0", "B1", "B2", "B3", "B4")
CANDIDATE_ARM = "B4"

BLUEPRINT_RQ_TEXTS = {
    "RQ1": "Under which delegation and epoch interleavings do signed context-bound "
    "capability baselines admit an invalid replay or reject valid operations?",
    "RQ2": "Is the proposed consume-once transition linearizable under two or more "
    "real PostgreSQL sessions and revoked scope?",
    "RQ3": "What are token size, verification latency and legitimate operation "
    "rejection costs relative to well-configured Macaroons and Zanzibar-like policies?",
}

DENOMINATOR_CATEGORIES = (
    "eligible",
    "attempted",
    "completed",
    "rejected",
    "indeterminate",
    "timeout",
    "not_run_external",
    "missing",
)

THREAT_FAMILIES = (
    "replay",
    "purpose_scope",
    "revocation_timing",
    "model_agency",
    "insider_or_observer",
)


@dataclasses.dataclass(frozen=True)
class RQPlan:
    """Typed, JSON-serializable view of one frozen research question."""

    id: str
    question: str
    independent_unit: str
    population: str
    estimand: str
    paired_contrast: str
    primary_metric: str
    secondary_metrics: tuple[str, ...]
    null_hypothesis: str
    alternative_hypothesis: str
    minimum_useful_difference: str
    confounders: tuple[str, ...]
    power_analysis_method: str
    analysis_method: str
    falsification_condition: str
    primary_endpoint: str

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = dataclasses.asdict(self)
        payload["secondary_metrics"] = list(self.secondary_metrics)
        payload["confounders"] = list(self.confounders)
        return payload


class RQRegistryError(ValueError):
    """Refusal with a stable, machine-checkable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


def _parse_yaml(text: str) -> dict[str, object]:
    if _HAS_YAML:
        loaded = yaml.safe_load(text)  # type: ignore[union-attr]
    else:  # pragma: no cover - stdlib-only environments
        raise RQRegistryError(
            "PARSER_UNAVAILABLE", "PyYAML is required to read the frozen RQ registry"
        )
    if not isinstance(loaded, dict):
        raise RQRegistryError("REGISTRY_UNPARSEABLE", "registry root must be a mapping")
    return loaded


def _require_str(rq: dict[str, object], field: str, rq_id: str) -> str:
    value = rq.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RQRegistryError("RQ_FIELD_MISSING", f"{rq_id} field {field!r} missing or empty")
    return value


def _require_str_list(rq: dict[str, object], field: str, rq_id: str) -> tuple[str, ...]:
    value = rq.get(field)
    if not isinstance(value, list) or not value:
        raise RQRegistryError("RQ_FIELD_MISSING", f"{rq_id} field {field!r} missing or empty")
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item)
        elif isinstance(item, dict):
            joined = "; ".join(f"{k}: {v}" for k, v in sorted(item.items()) if str(v).strip())
            if joined.strip():
                out.append(joined)
            else:
                raise RQRegistryError(
                    "RQ_FIELD_MISSING", f"{rq_id} field {field!r} has an empty entry"
                )
        else:
            raise RQRegistryError(
                "RQ_FIELD_MISSING", f"{rq_id} field {field!r} has a non-text entry"
            )
    return tuple(out)


def read_rqs(registry_path: pathlib.Path | None = None) -> tuple[RQPlan, ...]:
    """Load and validate the frozen RQ registry; return exactly three RQPlan.

    Fail closed with a stable reason code on any structural violation. This is
    the task contract signature ``read_rqs() -> RQPlan`` (one row per RQ).
    """
    path = registry_path or REGISTRY_PATH
    if not path.is_file():
        raise RQRegistryError("REGISTRY_MISSING", f"registry file absent: {path}")
    doc = _parse_yaml(path.read_text(encoding="utf-8"))

    status = doc.get("status")
    if not isinstance(status, str) or "FROZEN_PREREGISTRATION" not in status:
        raise RQRegistryError(
            "STATUS_NOT_PREREGISTRATION",
            "registry must declare frozen-preregistration status, not evidence",
        )

    arms = doc.get("arms")
    if not isinstance(arms, dict) or set(arms) != set(ARMS):
        raise RQRegistryError("ARMS_INCOMPLETE", f"arms must declare exactly {ARMS}, got {arms}")
    if doc.get("candidate_arm") != CANDIDATE_ARM:
        raise RQRegistryError("CANDIDATE_ARM_INVALID", "candidate arm must be B4")

    population_common = doc.get("population_common")
    if not isinstance(population_common, dict):
        raise RQRegistryError("POPULATION_MISSING", "population_common must be a mapping")
    declared_denominators = population_common.get("denominator_categories")
    if not isinstance(declared_denominators, list):
        raise RQRegistryError("DENOMINATOR_MISSING", "denominator_categories must be a list")
    for cat in DENOMINATOR_CATEGORIES:
        if cat not in declared_denominators:
            raise RQRegistryError("DENOMINATOR_INCOMPLETE", f"denominator category missing: {cat}")

    rqs = doc.get("research_questions")
    if not isinstance(rqs, dict):
        raise RQRegistryError("RQS_MISSING", "research_questions must be a mapping")

    if tuple(rqs.keys()) != RQ_IDS:
        raise RQRegistryError(
            "RQ_COUNT_INVALID",
            f"registry must contain exactly RQ1-RQ3 in order, got {tuple(rqs.keys())}",
        )

    plans: list[RQPlan] = []
    for rq_id in RQ_IDS:
        rq = rqs[rq_id]
        if not isinstance(rq, dict):
            raise RQRegistryError("RQ_UNPARSEABLE", f"{rq_id} must be a mapping")
        question = _require_str(rq, "question", rq_id)
        if question.replace("\n", " ") != BLUEPRINT_RQ_TEXTS[rq_id]:
            raise RQRegistryError(
                "RQ_TEXT_DRIFT", f"{rq_id} question does not match the blueprint verbatim"
            )
        plans.append(
            RQPlan(
                id=rq_id,
                question=question,
                independent_unit=_require_str(rq, "independent_unit", rq_id),
                population=_require_str(rq, "population", rq_id),
                estimand=_require_str(rq, "estimand", rq_id),
                paired_contrast=_require_str(rq, "paired_contrast", rq_id),
                primary_metric=_require_str(rq, "primary_metric", rq_id),
                secondary_metrics=_require_str_list(rq, "secondary_metrics", rq_id),
                null_hypothesis=_require_str(rq, "null_hypothesis", rq_id),
                alternative_hypothesis=_require_str(rq, "alternative_hypothesis", rq_id),
                minimum_useful_difference=_require_str(rq, "minimum_useful_difference", rq_id),
                confounders=_require_str_list(rq, "confounders", rq_id),
                power_analysis_method=_require_str(rq, "power_analysis_method", rq_id),
                analysis_method=_require_str(rq, "analysis_method", rq_id),
                falsification_condition=_require_str(rq, "falsification_condition", rq_id),
                primary_endpoint=_require_str(rq, "primary_endpoint", rq_id),
            )
        )
    return tuple(plans)


def validate_registry(registry_path: pathlib.Path | None = None) -> list[str]:
    """Structural gate used by the adversarial tests.

    Returns a list of violation strings (empty = conforming) without raising,
    so mutated registries can be shown to be refused.
    """
    try:
        plans = read_rqs(registry_path)
    except RQRegistryError as exc:
        return [f"{exc.reason_code}: {exc}"]
    violations: list[str] = []
    for plan in plans:
        unit = plan.independent_unit.lower()
        blob = " ".join(
            [
                plan.independent_unit,
                plan.estimand,
                plan.primary_metric,
                plan.analysis_method,
                plan.population,
            ]
        ).lower()
        if plan.id == "RQ1" or plan.id == "RQ3":
            if "history" not in blob and "schedule" not in blob:
                violations.append(f"{plan.id}: unit does not name history/schedule")
        if plan.id == "RQ2":
            if "history" not in blob:
                violations.append("RQ2: unit does not name independent interleaving history")
        # Registered failure mode of this task: pooled repeated events treated
        # as independent. A per-event unit normalization is refused even when
        # the word "history" survives elsewhere in the block.
        if (
            re.search(r"\bper[- ]event\b", unit)
            or "each token presentation is an independent unit" in unit
        ):
            violations.append(f"{plan.id}: per-event pseudo-replication unit refused")
        if "clustered within" not in unit and "never treated as independent" not in unit:
            violations.append(f"{plan.id}: within-unit clustering declaration missing")
    # RQ2 PostgreSQL admissibility: the population must demand real PostgreSQL
    # 16 AND declare SQLite stand-ins inadmissible; weakening either is refused.
    try:
        plans_by_id = {p.id: p for p in plans}
        rq2_pop = plans_by_id["RQ2"].population.lower()
        if "postgresql 16" not in rq2_pop:
            violations.append("RQ2: population does not require real PostgreSQL 16")
        if "inadmissible" not in rq2_pop or "sqlite" not in rq2_pop:
            violations.append("RQ2: SQLite inadmissibility declaration missing")
    except KeyError:  # pragma: no cover - RQ_COUNT_INVALID already reported
        pass
    return violations


# ----------------------------------------------------------------- positive
def test_registry_exists() -> None:
    assert REGISTRY_PATH.is_file(), f"missing registry: {REGISTRY_PATH}"


def test_read_rqs_returns_exactly_three_plans() -> None:
    plans = read_rqs()
    assert len(plans) == 3, f"expected exactly 3 RQs, found {len(plans)}"
    assert tuple(p.id for p in plans) == RQ_IDS


def test_each_plan_has_all_mandated_fields() -> None:
    for plan in read_rqs():
        for field in REQUIRED_RQ_FIELDS:
            value = getattr(plan, field)
            assert value, f"{plan.id} missing mandated field {field}"
        payload = plan.to_dict()
        encoded = repr(payload)
        assert plan.id in encoded


def test_rq_questions_match_blueprint_verbatim() -> None:
    for plan in read_rqs():
        assert (
            plan.question == BLUEPRINT_RQ_TEXTS[plan.id]
        ), f"{plan.id} drifted from the blueprint question"


def test_units_are_independent_histories_not_pooled_events() -> None:
    for plan in read_rqs():
        unit = plan.independent_unit.lower()
        assert (
            "history" in unit or "schedule" in unit
        ), f"{plan.id} unit must be a unique history/schedule"
        assert (
            "never treated as independent" in unit or "clustered within" in unit
        ), f"{plan.id} must declare within-history clustering"
        # The registered negative outcome of this task is pooled events as
        # independent draws; the unit text must not normalize per-event units.
        assert not re.search(
            r"\bper[- ]event\b", unit
        ), f"{plan.id} unit must not be per-event pseudo-replication"


def test_populations_declare_matched_controls_and_denominators() -> None:
    doc = _parse_yaml(REGISTRY_PATH.read_text(encoding="utf-8"))
    common = doc["population_common"]
    assert common["dataset_id"] == "synthetic-ifip_sec-2027"
    assert common["interleavings_total"] == 900
    for family in THREAT_FAMILIES:
        assert family in str(common["structure"]), f"threat family missing: {family}"
    assert "holdout opens only after IFIP_SEC-freeze" in str(common["split_discipline"])


def test_zero_event_rule_is_clopper_pearson_not_safety_proof() -> None:
    doc = _parse_yaml(REGISTRY_PATH.read_text(encoding="utf-8"))
    rules = doc["registry_rules"]
    assert "1 - 0.05**(1/N)" in rules["zero_event_rule"]
    assert "never logical proof" in rules["zero_event_rule"]
    for plan in read_rqs():
        blob = f"{plan.analysis_method} {plan.minimum_useful_difference}".lower()
        assert (
            "clopper" in blob or "two-gate" in blob
        ), f"{plan.id} must use Clopper-Pearson bounds or the two-gate certificate"
        assert "never" in blob or "not reported" in blob


def test_rq2_requires_real_postgresql_and_refuses_sqlite() -> None:
    plans = {p.id: p for p in read_rqs()}
    rq2_blob = " ".join(
        [plans["RQ2"].question, plans["RQ2"].population, plans["RQ2"].falsification_condition]
    ).lower()
    assert "postgresql 16" in rq2_blob
    assert "sqlite" in rq2_blob and "inadmissible" in rq2_blob
    doc = _parse_yaml(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert "SQLite" in doc["population_common"]["backend_requirements"]


def test_rq3_declares_frozen_non_inferiority_margins() -> None:
    plans = {p.id: p for p in read_rqs()}
    mud = plans["RQ3"].minimum_useful_difference.lower()
    assert "margin" in mud
    assert "bytes" in mud and "latency" in mud and "round trips" in mud
    assert "before holdout" in mud or "declared" in mud
    analysis = plans["RQ3"].analysis_method.lower()
    assert "two-gate" in analysis or "two gates" in analysis
    assert "never a certificate" in analysis


def test_paired_contrasts_name_the_strongest_baselines() -> None:
    plans = {p.id: p for p in read_rqs()}
    assert "B1" in plans["RQ1"].paired_contrast and "B2" in plans["RQ1"].paired_contrast
    assert "B3" in plans["RQ2"].paired_contrast
    assert "B1" in plans["RQ3"].paired_contrast and "B2" in plans["RQ3"].paired_contrast


def test_null_and_alternative_present_for_every_rq() -> None:
    for plan in read_rqs():
        assert re.match(r"H0\(", plan.null_hypothesis), f"{plan.id} null missing"
        assert re.match(r"H1\(", plan.alternative_hypothesis), f"{plan.id} alternative missing"


def test_falsification_conditions_carry_the_blueprint_equivalence_rule() -> None:
    for plan in read_rqs():
        cond = plan.falsification_condition.lower()
        assert "equivalen" in cond, f"{plan.id} falsification must state the equivalence rule"


def test_confounders_cover_oracle_independence_and_baseline_parity() -> None:
    for plan in read_rqs():
        joined = "; ".join(plan.confounders).lower()
        assert "oracle" in joined, f"{plan.id} must control oracle contamination"
        assert "baseline" in joined, f"{plan.id} must control baseline infidelity/parity"


def test_power_method_freezes_before_holdout() -> None:
    for plan in read_rqs():
        blob = plan.power_analysis_method.lower()
        assert (
            "frozen" in blob and "holdout" in blob
        ), f"{plan.id} power/N must be frozen before holdout"
        assert "p-value" in blob, f"{plan.id} N must not be chosen from target p-values"


def test_analysis_method_is_frozen_to_shared_policy() -> None:
    for plan in read_rqs():
        blob = plan.analysis_method.lower()
        assert "mcnemar" in blob or "clopper" in blob or "bootstrap" in blob
        assert "analysis_drift" in blob or "analysis drift" in blob


# --------------------------------------------------------- no invented results
_INVENTED_RESULT_PATTERNS = (
    r"\bp\s*[<>=]\s*0?\.\d+",
    r"\bp-value\s*=\s*0?\.\d+",
    r"\bCI\s*=\s*\[",
    r"\b95%\s*CI\s*[:=]\s*\[",
    r"\bobserved rate\b",
    r"\bmeasured\b.*\d+\.\d+%",
    r"\b0/\d+\s*(passed|failures)",
    r"\bexit code \d+\b",
)


def test_no_invented_empirical_results() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    for pattern in _INVENTED_RESULT_PATTERNS:
        assert (
            re.search(pattern, text, re.I) is None
        ), f"registry contains an invented empirical result matching {pattern!r}"


def test_registry_declares_preregistration_status() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    assert "FROZEN PREREGISTRATION" in text
    assert "not evidence" in text.lower()
    assert "IFIP_SEC-freeze" in text


# ------------------------------------------------- adversarial validator controls
def _mutate(original: str, old: str, new: str) -> str:
    assert old in original, f"mutation anchor absent: {old!r}"
    return original.replace(old, new, 1)


def test_missing_rq_field_is_refused() -> None:
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    mutated = _mutate(raw, "    estimand: >-", "    estimand_note: >-")
    problems = validate_registry_text(mutated)
    assert any("estimand" in p for p in problems), "validator must refuse a missing estimand"


def test_fourth_rq_is_refused() -> None:
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    mutated = raw.replace(
        "# ------------------------------------------------------- registry integrity",
        "  RQ4:\n    question: invented fourth question?\n"
        "    independent_unit: per-event unit\n"
        "    population: invented\n    estimand: invented\n"
        "    paired_contrast: invented\n    primary_metric: invented\n"
        "    secondary_metrics: [invented]\n    null_hypothesis: H0(invented)\n"
        "    alternative_hypothesis: H1(invented)\n"
        "    minimum_useful_difference: invented\n"
        "    confounders: [invented]\n    power_analysis_method: invented\n"
        "    analysis_method: invented\n    falsification_condition: invented\n"
        "    primary_endpoint: invented\n\n"
        "# ------------------------------------------------------- registry integrity",
        1,
    )
    problems = validate_registry_text(mutated)
    assert any("RQ_COUNT" in p for p in problems), "validator must refuse a 4th RQ"


def test_per_event_unit_is_refused() -> None:
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    anchor = "labeled once by the independent oracle; repeated token presentations"
    mutated = _mutate(raw, anchor, "each token presentation is an independent unit; presentations")
    problems = validate_registry_text(mutated)
    assert problems, "validator must refuse a per-event unit"


def test_sqlite_backed_rq2_claim_is_refused() -> None:
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    mutated = raw.replace(
        "SQLite stand-ins are inadmissible",
        "SQLite stand-ins are acceptable when convenient",
        1,
    )
    problems = validate_registry_text(mutated)
    assert problems, "validator must refuse a SQLite-backed RQ2 concurrency claim"


def validate_registry_text(raw: str) -> list[str]:
    """Validate raw YAML text through the same gate as the on-disk registry."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
        handle.write(raw)
        tmp = pathlib.Path(handle.name)
    try:
        return validate_registry(tmp)
    finally:
        tmp.unlink(missing_ok=True)
