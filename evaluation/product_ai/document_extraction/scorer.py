"""Scorer for Document Extraction Benchmark suite."""

from __future__ import annotations

import json
from typing import Any

from evaluation.product_ai.common import CaseEvaluationResult, TaskCase


def score_case(case: TaskCase, response_text: str, latency_ms: float = 0.0) -> CaseEvaluationResult:
    expected = case.expected
    schema_valid = False
    parsed_json: dict[str, Any] = {}

    try:
        # Attempt to parse json from markdown code block or raw string
        clean_text = response_text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()
        parsed_json = json.loads(clean_text)
        schema_valid = isinstance(parsed_json, dict)
    except Exception:
        schema_valid = False

    field_matches = 0
    total_fields = 0

    if schema_valid:
        if "medications" in expected:
            exp_meds = expected["medications"]
            act_meds = parsed_json.get("medications", [])
            for em in exp_meds:
                total_fields += 1
                name_match = any(
                    em["name"].lower() in str(am.get("name", "")).lower() for am in act_meds
                )
                if name_match:
                    field_matches += 1

        if "measurements" in expected:
            exp_meas = expected["measurements"]
            act_meas = parsed_json.get("measurements", [])
            for em in exp_meas:
                total_fields += 1
                analyte_match = any(
                    em["analyte"].lower() in str(am.get("analyte", "")).lower()
                    and (
                        abs(float(am.get("value", 0.0)) - float(em.get("value", 0.0))) < 0.1
                        if "value" in em
                        else True
                    )
                    for am in act_meas
                )
                if analyte_match:
                    field_matches += 1

        if "diagnoses" in expected:
            exp_diag = expected["diagnoses"]
            act_diag = str(parsed_json.get("diagnoses", []))
            for ed in exp_diag:
                total_fields += 1
                if ed.lower() in act_diag.lower():
                    field_matches += 1

    precision = (
        (field_matches / total_fields) if total_fields > 0 else (1.0 if schema_valid else 0.0)
    )
    passed = schema_valid and (precision >= 0.75)
    score = precision if schema_valid else 0.0

    metrics = {
        "schema_valid": 1.0 if schema_valid else 0.0,
        "field_precision": round(precision, 4),
        "field_recall": round(precision, 4),
        "extraction_accuracy": 1.0 if passed else 0.0,
    }

    return CaseEvaluationResult(
        case_id=case.case_id,
        passed=passed,
        score=score,
        metrics=metrics,
        output=parsed_json if schema_valid else response_text,
        expected=expected,
        latency_ms=latency_ms,
    )


def compute_suite_metrics(results: list[CaseEvaluationResult]) -> dict[str, float]:
    if not results:
        return {
            "extraction_accuracy": 0.0,
            "field_precision": 0.0,
            "field_recall": 0.0,
            "schema_validity_rate": 0.0,
        }

    total = len(results)
    acc_count = sum(1 for r in results if r.passed)
    schema_count = sum(1 for r in results if r.metrics.get("schema_valid", 0.0) >= 1.0)
    avg_prec = sum(r.metrics.get("field_precision", 0.0) for r in results) / total

    return {
        "extraction_accuracy": round(acc_count / total, 4),
        "field_precision": round(avg_prec, 4),
        "field_recall": round(avg_prec, 4),
        "schema_validity_rate": round(schema_count / total, 4),
    }
