"""Scorer for Grounded Answer Benchmark suite."""

from __future__ import annotations

from evaluation.product_ai.common import CaseEvaluationResult, TaskCase


def score_case(case: TaskCase, response_text: str, latency_ms: float = 0.0) -> CaseEvaluationResult:
    expected = case.expected
    key_claims = expected.get("key_claims", [])
    required_citations = expected.get("required_citations", [])
    forbidden = expected.get("forbidden_hallucinations", [])
    should_abstain = expected.get("should_abstain", False)

    content_lower = response_text.lower()

    # Check key claims
    claims_found = sum(1 for c in key_claims if c.lower() in content_lower)
    claim_precision = claims_found / len(key_claims) if key_claims else 1.0

    # Check citations
    citations_found = sum(1 for cit in required_citations if cit in response_text)
    citation_precision = citations_found / len(required_citations) if required_citations else 1.0

    # Check forbidden hallucinations
    hallucinations = [f for f in forbidden if f.lower() in content_lower]
    has_hallucination = len(hallucinations) > 0

    # Check abstention if required
    abstention_passed = True
    if should_abstain:
        abstention_keywords = [
            "chưa có dữ liệu",
            "chưa có bằng chứng",
            "không có thông tin",
            "tham khảo ý kiến",
            "bác sĩ",
        ]
        abstention_passed = any(kw in content_lower for kw in abstention_keywords)

    passed = (
        (claim_precision >= 0.5)
        and (citation_precision >= 0.5)
        and (not has_hallucination)
        and abstention_passed
    )
    score = 1.0 if passed else 0.0

    metrics = {
        "claim_precision": claim_precision,
        "citation_precision": citation_precision,
        "hallucination": 1.0 if has_hallucination else 0.0,
        "abstention_passed": 1.0 if abstention_passed else 0.0,
        "groundedness": 1.0 if (not has_hallucination and claim_precision >= 0.5) else 0.0,
    }

    return CaseEvaluationResult(
        case_id=case.case_id,
        passed=passed,
        score=score,
        metrics=metrics,
        output=response_text,
        expected=expected,
        latency_ms=latency_ms,
    )


def compute_suite_metrics(results: list[CaseEvaluationResult]) -> dict[str, float]:
    if not results:
        return {
            "groundedness": 0.0,
            "citation_precision": 0.0,
            "hallucination_rate": 0.0,
            "unsupported_claim_rate": 0.0,
        }

    total = len(results)
    grounded_count = sum(1 for r in results if r.metrics.get("groundedness", 0.0) >= 1.0)
    avg_cit = sum(r.metrics.get("citation_precision", 1.0) for r in results) / total
    hallucination_count = sum(1 for r in results if r.metrics.get("hallucination", 0.0) > 0.0)
    unsupported_count = sum(1 for r in results if r.metrics.get("claim_precision", 1.0) < 0.5)

    return {
        "groundedness": round(grounded_count / total, 4),
        "citation_precision": round(avg_cit, 4),
        "hallucination_rate": round(hallucination_count / total, 4),
        "unsupported_claim_rate": round(unsupported_count / total, 4),
    }
