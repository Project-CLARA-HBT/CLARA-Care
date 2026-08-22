"""Scorer for Grounded Answer Benchmark suite."""

from __future__ import annotations

import re

from evaluation.product_ai.common import CaseEvaluationResult, TaskCase


_CLAIM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "chưa có dữ liệu": ("chưa có dữ liệu", "không có dữ liệu", "chưa có thông tin", "không có thông tin"),
    "bằng chứng y khoa": ("bằng chứng y khoa", "bằng chứng khoa học", "bằng chứng y học", "bằng chứng lâm sàng"),
    "rối loạn tiêu hóa": ("rối loạn tiêu hóa", "tiêu hóa", "đầy hơi", "buồn nôn", "tiêu chảy"),
    "nhiễm toan acid lactic": ("nhiễm toan acid lactic", "nhiễm toan lactic", "lactic acidosis"),
    "hội chứng reye": ("hội chứng reye", "reye"),
    "không được sử dụng": ("không được sử dụng", "không được dùng", "chống chỉ định", "tuyệt đối không"),
    "mục tiêu hba1c": ("mục tiêu hba1c", "hba1c", "kiểm soát đường huyết"),
    "cyp2c19": ("cyp2c19", "ức chế enzyme"),
    "giảm hiệu lực": ("giảm hiệu lực", "giảm tác dụng", "giảm hoạt tính", "giảm hiệu quả"),
    "tuyệt đối không": ("tuyệt đối không", "không được", "tránh dùng", "chống chỉ định"),
    "xuất huyết": ("xuất huyết", "chảy máu", "xuất huyết tiêu hóa"),
    "giai đoạn 3b": ("giai đoạn 3b", "g3b", "suy giảm chức năng thận từ trung bình đến nặng", "giai đoạn 3"),
    "kdigo": ("kdigo", "theo phân loại"),
    "cùng một thời điểm": ("cùng một thời điểm", "cố định", "mỗi ngày"),
    "buổi sáng": ("buổi sáng", "sáng"),
    "4000": ("4000", "4g", "4 g", "4 gam", "4000mg", "4000 mg"),
    "24 giờ": ("24 giờ", "24h", "một ngày", "1 ngày", "24 tiếng"),
    "không được nghiền": ("không được nghiền", "không nghiền", "không bẻ", "không nhai"),
    "nguy cơ quá liều": ("nguy cơ quá liều", "quá liều", "độc tính", "giải phóng ồ ạt"),
}


def _claim_matches(claim: str, text: str) -> bool:
    c_lower = claim.lower()
    if c_lower in text:
        return True
    synonyms = _CLAIM_SYNONYMS.get(c_lower, ())
    return any(s.lower() in text for s in synonyms)


def score_case(case: TaskCase, response_text: str, latency_ms: float = 0.0) -> CaseEvaluationResult:
    expected = case.expected
    key_claims = expected.get("key_claims", [])
    required_citations = expected.get("required_citations", [])
    forbidden = expected.get("forbidden_hallucinations", [])
    should_abstain = expected.get("should_abstain", False)

    content_lower = response_text.lower()

    # Check key claims
    claims_found = sum(1 for c in key_claims if _claim_matches(c, content_lower))
    claim_precision = claims_found / len(key_claims) if key_claims else 1.0

    # Check citations
    citations_found = sum(1 for cit in required_citations if cit in response_text)
    citation_precision = citations_found / len(required_citations) if required_citations else 1.0

    # Check forbidden hallucinations (excluding negated/refuted mentions)
    hallucinations = []
    for f in forbidden:
        f_lower = f.lower()
        if f_lower in content_lower:
            # Check if negated/refuted with regex across nearby words
            neg_pattern = rf"(?:không|chưa|không có|chưa có|không thể|chưa thể|chưa có bằng chứng|không có bằng chứng|tránh|cấm|tuyệt đối không)[^\.\n]{{0,120}}{re.escape(f_lower)}"
            if not re.search(neg_pattern, content_lower):
                hallucinations.append(f)
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
