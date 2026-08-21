"""Scorer for Vietnamese Clinical NLP Benchmark suite."""

from __future__ import annotations

import json
from typing import Any

from evaluation.product_ai.common import CaseEvaluationResult, TaskCase


def score_case(case: TaskCase, response_text: str, latency_ms: float = 0.0) -> CaseEvaluationResult:
    expected = case.expected
    # Normalize comparison text from JSON or raw text
    parsed_json: dict[str, Any] = {}
    try:
        clean = response_text.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        parsed_json = json.loads(clean)
    except Exception:
        parsed_json = {}

    full_search_text = (
        json.dumps(parsed_json, ensure_ascii=False) if parsed_json else response_text
    ).lower()

    passed = True
    abbr_score = 1.0
    neg_score = 1.0
    colloquial_score = 1.0

    if "abbreviations" in expected:
        exp_abbr = expected["abbreviations"]
        act_abbr = parsed_json.get("abbreviations", {})
        matches = 0
        for k, v in exp_abbr.items():
            if k in str(act_abbr) or v.lower() in full_search_text:
                matches += 1
        abbr_score = matches / len(exp_abbr)
        if abbr_score < 0.75:
            passed = False

    if "symptoms" in expected:
        exp_sym = expected["symptoms"]
        act_sym = parsed_json.get("symptoms", [])
        matches = 0
        for s in exp_sym:
            s_name = s["name"]
            # Verify negation is correctly identified
            found = False
            for act_s in act_sym:
                if s_name.lower() in str(act_s.get("name", "")).lower() and act_s.get(
                    "negated", False
                ) == s.get("negated", True):
                    found = True
                    break
            if found or (
                s_name.lower() in full_search_text
                and ("không" in full_search_text or "chưa" in full_search_text)
            ):
                matches += 1
        neg_score = matches / len(exp_sym)
        if neg_score < 0.75:
            passed = False

    if "terms" in expected:
        exp_terms = expected["terms"]
        matches = sum(1 for t in exp_terms if t.lower() in full_search_text)
        colloquial_score = matches / len(exp_terms) if exp_terms else 1.0
        if colloquial_score < 0.5:
            passed = False

    if "normalized" in expected:
        if expected["normalized"].lower() not in full_search_text:
            passed = False

    if "procedure" in expected:
        if expected["procedure"].lower() not in full_search_text:
            passed = False

    score = 1.0 if passed else 0.0

    metrics = {
        "abbreviation_accuracy": abbr_score,
        "negation_accuracy": neg_score,
        "colloquial_accuracy": colloquial_score,
        "nlp_case_accuracy": 1.0 if passed else 0.0,
    }

    return CaseEvaluationResult(
        case_id=case.case_id,
        passed=passed,
        score=score,
        metrics=metrics,
        output=parsed_json or response_text,
        expected=expected,
        latency_ms=latency_ms,
    )


def compute_suite_metrics(results: list[CaseEvaluationResult]) -> dict[str, float]:
    if not results:
        return {
            "vietnamese_nlp_accuracy": 0.0,
            "abbreviation_resolution_accuracy": 0.0,
            "negation_handling_accuracy": 0.0,
            "colloquial_mapping_accuracy": 0.0,
        }

    total = len(results)
    acc_count = sum(1 for r in results if r.passed)
    avg_abbr = sum(r.metrics.get("abbreviation_accuracy", 1.0) for r in results) / total
    avg_neg = sum(r.metrics.get("negation_accuracy", 1.0) for r in results) / total
    avg_colloquial = sum(r.metrics.get("colloquial_accuracy", 1.0) for r in results) / total

    return {
        "vietnamese_nlp_accuracy": round(acc_count / total, 4),
        "abbreviation_resolution_accuracy": round(avg_abbr, 4),
        "negation_handling_accuracy": round(avg_neg, 4),
        "colloquial_mapping_accuracy": round(avg_colloquial, 4),
    }
