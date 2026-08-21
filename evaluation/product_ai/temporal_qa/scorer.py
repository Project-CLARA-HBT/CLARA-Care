"""Scorer for Personal Temporal QA Benchmark suite."""

from __future__ import annotations

from evaluation.product_ai.common import CaseEvaluationResult, TaskCase


def score_case(case: TaskCase, response_text: str, latency_ms: float = 0.0) -> CaseEvaluationResult:
    expected = case.expected
    content_lower = response_text.lower()

    # Check correct current status/trend/entities
    passed = True
    stale_used = False
    superseded_leaked = False

    if "current_medication" in expected:
        cur = expected["current_medication"].lower()
        if cur not in content_lower:
            passed = False

    if "forbidden_as_current" in expected:
        for f in expected["forbidden_as_current"]:
            # If mentioned as currently active or without clarifying it was discontinued
            if f.lower() in content_lower:
                # check if marked as stopped/discontinued
                if not any(
                    k in content_lower for k in ["ngừng", "dừng", "cũ", "trước đây", "không còn"]
                ):
                    superseded_leaked = True
                    passed = False

    if "latest_bp" in expected:
        if expected["latest_bp"] not in response_text:
            passed = False

    if "stale_bp" in expected:
        for s in expected["stale_bp"]:
            if (
                s in response_text
                and "gần nhất" in content_lower
                and response_text.find(s) < response_text.find(expected.get("latest_bp", ""))
            ):
                stale_used = True

    if "trend" in expected:
        if expected["trend"].lower() not in content_lower:
            passed = False

    if "status" in expected:
        if expected["status"].lower() not in content_lower:
            passed = False

    score = 1.0 if (passed and not stale_used and not superseded_leaked) else 0.0

    metrics = {
        "temporal_correctness": 1.0 if score == 1.0 else 0.0,
        "stale_data_usage": 1.0 if stale_used else 0.0,
        "superseded_medication_leak": 1.0 if superseded_leaked else 0.0,
    }

    return CaseEvaluationResult(
        case_id=case.case_id,
        passed=score == 1.0,
        score=score,
        metrics=metrics,
        output=response_text,
        expected=expected,
        latency_ms=latency_ms,
    )


def compute_suite_metrics(results: list[CaseEvaluationResult]) -> dict[str, float]:
    if not results:
        return {
            "temporal_correctness": 0.0,
            "stale_data_usage_rate": 0.0,
            "superseded_medication_leak_rate": 0.0,
        }

    total = len(results)
    temporal_count = sum(1 for r in results if r.metrics.get("temporal_correctness", 0.0) >= 1.0)
    stale_count = sum(1 for r in results if r.metrics.get("stale_data_usage", 0.0) > 0.0)
    leak_count = sum(1 for r in results if r.metrics.get("superseded_medication_leak", 0.0) > 0.0)

    return {
        "temporal_correctness": round(temporal_count / total, 4),
        "stale_data_usage_rate": round(stale_count / total, 4),
        "superseded_medication_leak_rate": round(leak_count / total, 4),
    }
