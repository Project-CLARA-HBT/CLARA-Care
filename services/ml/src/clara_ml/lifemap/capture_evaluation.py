"""Versioned bilingual evaluation for the production Universal Capture boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

Extractor = Callable[..., dict[str, Any]]
EmergencyDetector = Callable[[str], bool]


class CaptureEvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class CaptureEvaluationReport:
    suite_version: str
    suite_sha256: str
    case_count: int
    extraction_case_count: int
    emergency_case_count: int
    field_precision: float
    field_recall: float
    critical_field_miss_rate: float
    wrong_medication_rate: float
    source_span_validity: float
    emergency_sensitivity: float
    emergency_specificity: float
    emergency_latency_p95_ms: float
    extraction_latency_p95_ms: float
    confirmation_actions_per_case: float
    locale_metrics: dict[str, dict[str, float]]
    gate_failures: tuple[str, ...]
    eligible_for_promotion: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalized(value: Any) -> str:
    return " ".join(str(value).casefold().replace(",", ".").split())


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def load_capture_suite(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        suite = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CaptureEvaluationError("capture_suite_json_invalid") from error
    if not isinstance(suite, dict) or set(suite) != {
        "suite_version",
        "thresholds",
        "cases",
    }:
        raise CaptureEvaluationError("capture_suite_schema_invalid")
    cases = suite["cases"]
    if not isinstance(cases, list) or not cases:
        raise CaptureEvaluationError("capture_suite_cases_invalid")
    ids: set[str] = set()
    locales: set[str] = set()
    modes: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise CaptureEvaluationError("capture_case_schema_invalid")
        required = {"case_id", "locale", "mode", "source_text"}
        if not required <= set(case):
            raise CaptureEvaluationError("capture_case_schema_invalid")
        case_id = str(case["case_id"])
        if not case_id or case_id in ids:
            raise CaptureEvaluationError("capture_case_identity_invalid")
        ids.add(case_id)
        locales.add(str(case["locale"]))
        modes.add(str(case["mode"]))
    if locales != {"vi", "en"} or modes != {"extraction", "emergency"}:
        raise CaptureEvaluationError("capture_suite_coverage_invalid")
    if not isinstance(suite["thresholds"], dict):
        raise CaptureEvaluationError("capture_thresholds_invalid")
    return suite, hashlib.sha256(raw).hexdigest()


def _evaluate_extraction_case(
    case: dict[str, Any],
    *,
    extractor: Extractor,
) -> dict[str, Any]:
    source_text = str(case["source_text"])
    kind = str(case.get("kind") or "")
    expected = case.get("expected_fields")
    critical = case.get("critical_fields")
    if (
        kind not in {"medication_label", "visit_document"}
        or not isinstance(expected, dict)
        or not isinstance(critical, list)
    ):
        raise CaptureEvaluationError("capture_extraction_case_invalid")
    checksum = hashlib.sha256(source_text.encode()).hexdigest()
    started = perf_counter()
    output = extractor(
        kind=kind,
        source_text=source_text,
        source_text_checksum=checksum,
    )
    latency_ms = (perf_counter() - started) * 1000
    candidate = output.get("candidate")
    if not isinstance(candidate, dict) or candidate.get("draft_only") is not True:
        raise CaptureEvaluationError("capture_output_not_draft")
    values = candidate.get("value")
    confidences = candidate.get("field_confidence")
    span_container = candidate.get("source_span")
    if not isinstance(span_container, dict):
        raise CaptureEvaluationError("capture_output_schema_invalid")
    spans = span_container.get("fields")
    if (
        not isinstance(values, dict)
        or not isinstance(confidences, dict)
        or not isinstance(spans, dict)
    ):
        raise CaptureEvaluationError("capture_output_schema_invalid")
    if span_container.get("text_checksum") != checksum:
        raise CaptureEvaluationError("capture_output_checksum_invalid")

    true_positive = 0
    false_positive = 0
    false_negative = 0
    span_valid = 0
    span_total = 0
    low_confidence = 0
    wrong_fields = 0
    for field, actual in values.items():
        expected_field = expected.get(field)
        correct = isinstance(expected_field, dict) and _normalized(actual) == _normalized(
            expected_field.get("value")
        )
        if correct:
            true_positive += 1
        else:
            false_positive += 1
            wrong_fields += 1
        confidence = confidences.get(field)
        if not isinstance(confidence, int | float) or isinstance(confidence, bool):
            raise CaptureEvaluationError("capture_confidence_invalid")
        if float(confidence) < float(case.get("review_confidence_floor", 0.8)):
            low_confidence += 1
        span_total += 1
        span = spans.get(field)
        if isinstance(span, dict):
            start, end = span.get("start"), span.get("end")
            if (
                isinstance(start, int)
                and isinstance(end, int)
                and 0 <= start < end <= len(source_text)
            ):
                expected_source = (
                    str(expected_field.get("source_text"))
                    if isinstance(expected_field, dict)
                    else ""
                )
                if not expected_source or source_text[start:end] == expected_source:
                    span_valid += 1
    missing_fields = set(expected) - set(values)
    false_negative += len(missing_fields)
    missing_critical = {str(item) for item in critical} - set(values)
    expected_medication = expected.get("medication_name")
    predicted_medication = values.get("medication_name")
    wrong_medication = bool(
        isinstance(expected_medication, dict)
        and predicted_medication is not None
        and _normalized(predicted_medication) != _normalized(expected_medication.get("value"))
    )
    expected_findings = {str(item) for item in case.get("security_findings", [])}
    actual_findings = {str(item) for item in candidate.get("security_findings", [])}
    if expected_findings != actual_findings:
        raise CaptureEvaluationError("capture_security_finding_mismatch")
    confirmation_actions = len(missing_critical) + wrong_fields + low_confidence
    return {
        "locale": str(case["locale"]),
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "critical_total": len(critical),
        "critical_missed": len(missing_critical),
        "medication_case": isinstance(expected_medication, dict),
        "wrong_medication": wrong_medication,
        "span_valid": span_valid,
        "span_total": span_total,
        "confirmation_actions": confirmation_actions,
        "latency_ms": latency_ms,
    }


def evaluate_capture_suite(
    suite: dict[str, Any],
    *,
    suite_sha256: str,
    extractor: Extractor,
    emergency_detector: EmergencyDetector,
) -> CaptureEvaluationReport:
    cases = suite["cases"]
    extraction_results: list[dict[str, Any]] = []
    emergency_results: list[dict[str, Any]] = []
    for case in cases:
        if case["mode"] == "extraction":
            extraction_results.append(_evaluate_extraction_case(case, extractor=extractor))
            continue
        expected = case.get("expected_emergency")
        if not isinstance(expected, bool):
            raise CaptureEvaluationError("capture_emergency_case_invalid")
        started = perf_counter()
        actual = emergency_detector(str(case["source_text"]))
        emergency_results.append(
            {
                "locale": str(case["locale"]),
                "expected": expected,
                "actual": actual,
                "latency_ms": (perf_counter() - started) * 1000,
            }
        )

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 1.0

    tp = sum(int(item["tp"]) for item in extraction_results)
    fp = sum(int(item["fp"]) for item in extraction_results)
    fn = sum(int(item["fn"]) for item in extraction_results)
    critical_total = sum(int(item["critical_total"]) for item in extraction_results)
    critical_missed = sum(int(item["critical_missed"]) for item in extraction_results)
    medication_cases = [item for item in extraction_results if item["medication_case"]]
    spans_total = sum(int(item["span_total"]) for item in extraction_results)
    spans_valid = sum(int(item["span_valid"]) for item in extraction_results)
    positive_emergency = [item for item in emergency_results if item["expected"]]
    negative_emergency = [item for item in emergency_results if not item["expected"]]
    values = {
        "field_precision": ratio(tp, tp + fp),
        "field_recall": ratio(tp, tp + fn),
        "critical_field_miss_rate": ratio(critical_missed, critical_total),
        "wrong_medication_rate": ratio(
            sum(bool(item["wrong_medication"]) for item in medication_cases),
            len(medication_cases),
        ),
        "source_span_validity": ratio(spans_valid, spans_total),
        "emergency_sensitivity": ratio(
            sum(item["actual"] is True for item in positive_emergency),
            len(positive_emergency),
        ),
        "emergency_specificity": ratio(
            sum(item["actual"] is False for item in negative_emergency),
            len(negative_emergency),
        ),
        "emergency_latency_p95_ms": _percentile(
            [float(item["latency_ms"]) for item in emergency_results],
            0.95,
        ),
        "extraction_latency_p95_ms": _percentile(
            [float(item["latency_ms"]) for item in extraction_results],
            0.95,
        ),
        "confirmation_actions_per_case": ratio(
            sum(int(item["confirmation_actions"]) for item in extraction_results),
            len(extraction_results),
        ),
    }
    locale_metrics: dict[str, dict[str, float]] = {}
    for locale in ("vi", "en"):
        rows = [item for item in extraction_results if item["locale"] == locale]
        locale_tp = sum(int(item["tp"]) for item in rows)
        locale_fp = sum(int(item["fp"]) for item in rows)
        locale_fn = sum(int(item["fn"]) for item in rows)
        locale_metrics[locale] = {
            "field_precision": ratio(locale_tp, locale_tp + locale_fp),
            "field_recall": ratio(locale_tp, locale_tp + locale_fn),
            "confirmation_actions_per_case": ratio(
                sum(int(item["confirmation_actions"]) for item in rows),
                len(rows),
            ),
        }

    thresholds = suite["thresholds"]
    minimum_metrics = {
        "field_precision",
        "field_recall",
        "source_span_validity",
        "emergency_sensitivity",
        "emergency_specificity",
    }
    maximum_metrics = {
        "critical_field_miss_rate",
        "wrong_medication_rate",
        "emergency_latency_p95_ms",
        "extraction_latency_p95_ms",
        "confirmation_actions_per_case",
    }
    if set(thresholds) != minimum_metrics | maximum_metrics:
        raise CaptureEvaluationError("capture_thresholds_invalid")
    failures = [
        key for key in sorted(minimum_metrics) if float(values[key]) < float(thresholds[key])
    ]
    failures.extend(
        key for key in sorted(maximum_metrics) if float(values[key]) > float(thresholds[key])
    )
    return CaptureEvaluationReport(
        suite_version=str(suite["suite_version"]),
        suite_sha256=suite_sha256,
        case_count=len(cases),
        extraction_case_count=len(extraction_results),
        emergency_case_count=len(emergency_results),
        field_precision=values["field_precision"],
        field_recall=values["field_recall"],
        critical_field_miss_rate=values["critical_field_miss_rate"],
        wrong_medication_rate=values["wrong_medication_rate"],
        source_span_validity=values["source_span_validity"],
        emergency_sensitivity=values["emergency_sensitivity"],
        emergency_specificity=values["emergency_specificity"],
        emergency_latency_p95_ms=values["emergency_latency_p95_ms"],
        extraction_latency_p95_ms=values["extraction_latency_p95_ms"],
        confirmation_actions_per_case=values["confirmation_actions_per_case"],
        locale_metrics=locale_metrics,
        gate_failures=tuple(failures),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from clara_api.lifemap.capture_domain import emergency_fast_path

    from clara_ml.lifemap.capture_extraction import extract_capture_text

    suite, digest = load_capture_suite(args.suite)
    report = evaluate_capture_suite(
        suite,
        suite_sha256=digest,
        extractor=extract_capture_text,
        emergency_detector=emergency_fast_path,
    )
    encoded = json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    if report.gate_failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
