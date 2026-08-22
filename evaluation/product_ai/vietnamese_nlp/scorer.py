"""Scorer for Vietnamese Clinical NLP Benchmark suite."""

from __future__ import annotations

import json
from typing import Any

from evaluation.product_ai.common import CaseEvaluationResult, TaskCase


_CLINICAL_SYNONYMS: dict[str, tuple[str, ...]] = {
    "nóng rát thượng vị": (
        "nóng rát thượng vị",
        "cảm giác nóng rát thượng vị",
        "rát thượng vị",
        "nóng thượng vị",
        "nóng ruột",
        "ợ nóng",
        "heartburn",
    ),
    "trào ngược": (
        "trào ngược",
        "ợ chua",
        "ợ acid",
        "ợ nóng",
        "trào ngược dạ dày",
        "trào ngược axit",
        "trào ngược dạ dày thực quản",
        "gerd",
    ),
    "đau rát dạ dày": (
        "đau rát dạ dày",
        "đau rát thượng vị",
        "đau rát vùng thượng vị",
        "đau vùng thượng vị",
        "đau thượng vị",
        "đau dạ dày",
        "xót bụng",
        "xót dạ dày",
        "viêm loét dạ dày",
        "tăng tiết axit",
    ),
    "chóng mặt": ("chóng mặt", "choáng váng", "say xẩm", "hoa mắt"),
    "hạ huyết áp tư thế": (
        "hạ huyết áp tư thế",
        "tụt huyết áp tư thế",
        "tối sầm mắt",
        "thiếu máu não",
        "hạ áp tư thế",
    ),
    "cắt ruột thừa": ("cắt ruột thừa", "phẫu thuật ruột thừa", "appendectomy"),
    "ngày thứ 3 sau mổ": ("ngày thứ 3 sau mổ", "ngày thứ ba sau mổ", "ngày 3 sau mổ", "post-op d3", "post op d3"),
}


def _term_matches(term: str, text: str) -> bool:
    t_lower = term.lower()
    if t_lower in text:
        return True
    synonyms = _CLINICAL_SYNONYMS.get(t_lower, ())
    return any(s.lower() in text for s in synonyms)


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
        matches = sum(1 for t in exp_terms if _term_matches(t, full_search_text))
        colloquial_score = matches / len(exp_terms) if exp_terms else 1.0
        if colloquial_score < 0.5:
            passed = False

    if "normalized" in expected:
        if expected["normalized"].lower() not in full_search_text:
            passed = False

    if "procedure" in expected:
        if not _term_matches(expected["procedure"], full_search_text):
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
