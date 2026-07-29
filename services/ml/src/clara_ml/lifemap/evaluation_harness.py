"""Versioned longitudinal LifeMap AI golden-set evaluation harness."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REQUIRED_DIMENSIONS = frozenset(
    {
        "longitudinal",
        "temporal",
        "multimodal",
        "correction",
        "contradiction",
        "missingness",
        "wearable_shift",
        "ood",
        "adaptive_policy",
    }
)
REQUIRED_LOCALES = frozenset({"vi", "en"})


class EvaluationHarnessError(ValueError):
    pass


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    locale: Literal["vi", "en"]
    dimension: str
    expected: dict[str, Any]
    synthetic: bool
    held_out: bool


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    output: dict[str, Any]
    latency_ms: float
    cost_units: float


@dataclass(frozen=True)
class HarnessReport:
    suite_version: str
    suite_sha256: str
    case_count: int
    passed: int
    failed: int
    dimension_pass_rate: dict[str, float]
    locale_pass_rate: dict[str, float]
    failures: tuple[dict[str, str], ...]
    eligible_for_promotion: bool = False


def load_golden_suite(path: Path) -> tuple[str, str, tuple[GoldenCase, ...]]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {
        "suite_version",
        "cases",
    }:
        raise EvaluationHarnessError("golden_suite_schema_invalid")
    if not isinstance(payload["cases"], list):
        raise EvaluationHarnessError("golden_cases_not_list")
    cases = []
    for raw_case in payload["cases"]:
        if not isinstance(raw_case, dict) or set(raw_case) != {
            "case_id",
            "locale",
            "dimension",
            "expected",
            "synthetic",
            "held_out",
        }:
            raise EvaluationHarnessError("golden_case_schema_invalid")
        case = GoldenCase(
            case_id=str(raw_case["case_id"]),
            locale=raw_case["locale"],
            dimension=str(raw_case["dimension"]),
            expected=dict(raw_case["expected"]),
            synthetic=bool(raw_case["synthetic"]),
            held_out=bool(raw_case["held_out"]),
        )
        cases.append(case)
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise EvaluationHarnessError("golden_case_identity_invalid")
    dimensions = {case.dimension for case in cases}
    locales = {case.locale for case in cases}
    if not REQUIRED_DIMENSIONS <= dimensions or not REQUIRED_LOCALES <= locales:
        raise EvaluationHarnessError("golden_suite_coverage_incomplete")
    if any(case.locale not in REQUIRED_LOCALES or not case.expected for case in cases):
        raise EvaluationHarnessError("golden_case_content_invalid")
    return (
        str(payload["suite_version"]),
        hashlib.sha256(raw).hexdigest(),
        tuple(cases),
    )


def _matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _matches(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and all(item in actual for item in expected)
    return expected == actual


def evaluate_golden_results(
    *,
    suite_version: str,
    suite_sha256: str,
    cases: tuple[GoldenCase, ...],
    results: tuple[CaseResult, ...],
) -> HarnessReport:
    if not suite_version or len(suite_sha256) != 64:
        raise EvaluationHarnessError("suite_identity_invalid")
    by_id = {result.case_id: result for result in results}
    if len(by_id) != len(results) or set(by_id) != {case.case_id for case in cases}:
        raise EvaluationHarnessError("result_case_set_mismatch")
    failures: list[dict[str, str]] = []
    dimension_counts: dict[str, list[bool]] = {}
    locale_counts: dict[str, list[bool]] = {}
    for case in cases:
        result = by_id[case.case_id]
        if result.latency_ms < 0 or result.cost_units < 0:
            raise EvaluationHarnessError("result_operational_metric_invalid")
        passed = _matches(case.expected, result.output)
        dimension_counts.setdefault(case.dimension, []).append(passed)
        locale_counts.setdefault(case.locale, []).append(passed)
        if not passed:
            failures.append(
                {
                    "case_id": case.case_id,
                    "dimension": case.dimension,
                    "locale": case.locale,
                    "reason": "expected_contract_not_met",
                }
            )
    dimension_rates = {
        key: sum(values) / len(values) for key, values in dimension_counts.items()
    }
    locale_rates = {
        key: sum(values) / len(values) for key, values in locale_counts.items()
    }
    passed_count = len(cases) - len(failures)
    return HarnessReport(
        suite_version=suite_version,
        suite_sha256=suite_sha256,
        case_count=len(cases),
        passed=passed_count,
        failed=len(failures),
        dimension_pass_rate=dimension_rates,
        locale_pass_rate=locale_rates,
        failures=tuple(failures),
        # Passing a repository harness never grants model promotion.
        eligible_for_promotion=False,
    )
