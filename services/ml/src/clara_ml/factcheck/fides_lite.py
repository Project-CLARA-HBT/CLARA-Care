from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FactCheckResult:
    enabled: bool
    stage: str
    verdict: str
    confidence: float
    supported_claims: int
    total_claims: int
    unsupported_claims: list[str]
    evidence_count: int
    severity: str
    note: str
    fide_report: dict[str, Any] = field(default_factory=dict)
    verification_matrix: list[dict[str, Any]] = field(default_factory=list)
    contradiction_summary: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "stage": self.stage,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "supported_claims": self.supported_claims,
            "total_claims": self.total_claims,
            "unsupported_claims": self.unsupported_claims,
            "evidence_count": self.evidence_count,
            "severity": self.severity,
            "note": self.note,
            "fide_report": self.fide_report,
            "verification_matrix": self.verification_matrix,
            "contradiction_summary": self.contradiction_summary,
        }


_NEGATION_TERMS = {
    "khong",
    "không",
    "chua",
    "chưa",
    "no",
    "not",
    "never",
    "without",
    "tranh",
    "avoid",
    "contraindicated",
}
_INCREASE_TERMS = {"tang", "tăng", "increase", "increased", "higher", "cao"}
_DECREASE_TERMS = {"giam", "giảm", "decrease", "reduced", "lower", "thap"}
_CITATION_PATTERNS = [
    re.compile(r"\[[^\]]+\]"),
    re.compile(r"\(source[^)]*\)", re.IGNORECASE),
    re.compile(r"\(nguon[^)]*\)", re.IGNORECASE),
]


def _tokenize(text: str) -> set[str]:
    lowered = text.lower()
    return {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", lowered) if token}


def _split_claims(answer: str) -> list[str]:
    raw_chunks = re.split(r"[.!?\n\r•\-]+", answer)
    claims: list[str] = []
    seen: set[str] = set()
    for chunk in raw_chunks:
        claim = " ".join(chunk.split()).strip()
        if len(claim) < 20:
            continue
        dedupe_key = claim.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        claims.append(claim)
        if len(claims) >= 10:
            break
    return claims


def _compact_snippet(text: str, *, max_len: int = 180) -> str:
    snippet = " ".join(str(text or "").split()).strip()
    if not snippet:
        return ""
    if len(snippet) <= max_len:
        return snippet
    return f"{snippet[: max_len - 3]}..."


def _build_evidence_rows(retrieved_context: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, item in enumerate(retrieved_context, start=1):
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text", "")).split()).strip()
        if not text:
            continue
        ref = str(item.get("id") or f"evidence-{index}").strip() or f"evidence-{index}"
        rows.append({"ref": ref, "text": text})
    return rows


def _best_overlap_match(
    claim: str,
    evidence_rows: list[dict[str, str]],
) -> tuple[float, dict[str, str] | None]:
    claim_tokens = _tokenize(claim)
    if not claim_tokens:
        return 0.0, None
    best_ratio = 0.0
    best_row: dict[str, str] | None = None
    for row in evidence_rows:
        text = row.get("text", "")
        doc_tokens = _tokenize(text)
        if not doc_tokens:
            continue
        overlap = len(claim_tokens.intersection(doc_tokens))
        ratio = overlap / max(len(claim_tokens), 1)
        if ratio > best_ratio:
            best_ratio = ratio
            best_row = row
    return best_ratio, best_row


def _claim_confidence(*, overlap_ratio: float, support_status: str) -> float:
    bounded_ratio = max(0.0, min(float(overlap_ratio), 1.0))
    if support_status == "contradicted":
        score = 0.18 + (0.22 * bounded_ratio)
    elif support_status == "supported":
        score = 0.55 + (0.4 * bounded_ratio)
    else:
        score = 0.22 + (0.28 * bounded_ratio)
    return round(max(0.05, min(0.98, score)), 4)


def _build_matrix_summary(
    verification_matrix: list[dict[str, Any]],
    *,
    claims_count: int,
    supported_claims: int,
) -> dict[str, Any]:
    unsupported_count = 0
    contradicted_count = 0
    for row in verification_matrix:
        if not isinstance(row, dict):
            continue
        status = str(row.get("support_status") or "").strip().lower()
        if status == "unsupported":
            unsupported_count += 1
        elif status == "contradicted":
            contradicted_count += 1

    support_ratio = supported_claims / max(claims_count, 1) if claims_count > 0 else 0.0
    return {
        "version": "claim-v1",
        "total_claims": claims_count,
        "supported_claims": supported_claims,
        "unsupported_claims": unsupported_count,
        "contradicted_claims": contradicted_count,
        "support_ratio": round(float(support_ratio), 4),
    }


def _build_contradiction_summary(
    verification_matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    contradiction_rows: list[dict[str, Any]] = []
    for row in verification_matrix:
        if not isinstance(row, dict):
            continue
        if str(row.get("support_status") or "").strip().lower() != "contradicted":
            continue
        contradiction_rows.append(row)

    contradiction_count = len(contradiction_rows)
    note = (
        "Phát hiện claim mâu thuẫn với evidence retrieval."
        if contradiction_count > 0
        else "Không phát hiện claim mâu thuẫn."
    )
    details = [
        {
            "claim": item.get("claim", ""),
            "evidence_ref": item.get("evidence_ref"),
            "evidence_snippet": item.get("evidence_snippet", ""),
            "overlap_score": item.get("overlap_score", 0.0),
            "confidence": item.get("confidence", 0.0),
        }
        for item in contradiction_rows[:5]
    ]
    return {
        "version": "claim-v1",
        "has_contradiction": contradiction_count > 0,
        "contradiction_count": contradiction_count,
        "claims": [str(item.get("claim", "")) for item in contradiction_rows[:5]],
        "details": details,
        "note": note,
    }


def _contains_any(tokens: set[str], lexicon: set[str]) -> bool:
    return bool(tokens.intersection(lexicon))


def _has_contradiction(claim: str, evidence: str, overlap_ratio: float) -> bool:
    if not evidence or overlap_ratio < 0.16:
        return False

    claim_tokens = _tokenize(claim)
    evidence_tokens = _tokenize(evidence)

    claim_has_negation = _contains_any(claim_tokens, _NEGATION_TERMS)
    evidence_has_negation = _contains_any(evidence_tokens, _NEGATION_TERMS)
    if claim_has_negation != evidence_has_negation and overlap_ratio >= 0.2:
        return True

    claim_increase = _contains_any(claim_tokens, _INCREASE_TERMS)
    evidence_increase = _contains_any(evidence_tokens, _INCREASE_TERMS)
    claim_decrease = _contains_any(claim_tokens, _DECREASE_TERMS)
    evidence_decrease = _contains_any(evidence_tokens, _DECREASE_TERMS)

    if claim_increase and evidence_decrease and overlap_ratio >= 0.24:
        return True
    if claim_decrease and evidence_increase and overlap_ratio >= 0.24:
        return True

    return False


def _has_citations(answer: str, context_ids: list[str]) -> bool:
    lowered = answer.lower()
    if any(pattern.search(answer) for pattern in _CITATION_PATTERNS):
        return True
    for source_id in context_ids:
        if source_id and source_id.lower() in lowered:
            return True
    return False


def _build_fide_report(
    *,
    claims_count: int,
    evidence_count: int,
    supported_claims: int,
    verdict: str,
    severity: str,
    confidence: float,
    note: str,
    unsupported_claims: list[str],
    verification_matrix: list[dict[str, Any]],
    verification_matrix_summary: dict[str, Any],
    contradiction_summary: dict[str, Any],
    citation_present: bool,
    mode: str,
) -> dict[str, Any]:
    coverage = supported_claims / max(claims_count, 1) if claims_count > 0 else 0.0
    contradiction_count = int(verification_matrix_summary.get("contradicted_claims", 0))
    return {
        "framework": "fide-v1",
        "mode": mode,
        "stages": [
            {
                "id": "foundation",
                "status": "completed" if claims_count >= 0 else "failed",
                "claims_count": claims_count,
                "note": "Extracted atomic claims from answer.",
            },
            {
                "id": "integrity",
                "status": "completed" if evidence_count > 0 else "warning",
                "evidence_count": evidence_count,
                "citation_present": citation_present,
                "coverage": round(float(coverage), 4),
                "contradiction_count": contradiction_count,
                "verification_matrix_summary": verification_matrix_summary,
            },
            {
                "id": "decision",
                "status": verdict,
                "severity": severity,
                "confidence": round(float(confidence), 4),
            },
            {
                "id": "explanation",
                "status": "completed",
                "note": note,
                "unsupported_claims": unsupported_claims[:3],
            },
        ],
        "summary": {
            "claims_count": claims_count,
            "supported_claims": supported_claims,
            "unsupported_claims": int(verification_matrix_summary.get("unsupported_claims", 0)),
            "contradicted_claims": contradiction_count,
            "coverage": round(float(coverage), 4),
            "evidence_count": evidence_count,
            "citation_present": citation_present,
            "verdict": verdict,
            "severity": severity,
            "confidence": round(float(confidence), 4),
        },
        "verification_matrix": {
            "version": "claim-v1",
            "summary": verification_matrix_summary,
            "rows": verification_matrix,
        },
        "contradiction_summary": contradiction_summary,
    }


def run_fides_lite(
    *,
    answer: str,
    retrieved_context: list[dict[str, Any]],
    mode: str = "lite",
) -> FactCheckResult:
    normalized_mode = mode.strip().lower() if isinstance(mode, str) else "lite"
    if normalized_mode not in {"lite", "strict"}:
        normalized_mode = "lite"

    evidence_rows = _build_evidence_rows(retrieved_context)
    context_ids = [str(item.get("id", "")) for item in retrieved_context if item.get("id")]
    claims = _split_claims(answer)

    if not claims:
        verification_matrix: list[dict[str, Any]] = []
        verification_matrix_summary = _build_matrix_summary(
            verification_matrix,
            claims_count=0,
            supported_claims=0,
        )
        contradiction_summary = _build_contradiction_summary(verification_matrix)
        return FactCheckResult(
            enabled=True,
            stage="fides-lite-v1.1",
            verdict="pass",
            confidence=0.55,
            supported_claims=0,
            total_claims=0,
            unsupported_claims=[],
            evidence_count=len(evidence_rows),
            severity="low",
            note="Không có mệnh đề trọng yếu để kiểm chứng.",
            verification_matrix=verification_matrix,
            contradiction_summary=contradiction_summary,
            fide_report=_build_fide_report(
                claims_count=0,
                evidence_count=len(evidence_rows),
                supported_claims=0,
                verdict="pass",
                severity="low",
                confidence=0.55,
                note="Không có mệnh đề trọng yếu để kiểm chứng.",
                unsupported_claims=[],
                verification_matrix=verification_matrix,
                verification_matrix_summary=verification_matrix_summary,
                contradiction_summary=contradiction_summary,
                citation_present=_has_citations(answer, context_ids),
                mode=normalized_mode,
            ),
        )

    if not evidence_rows:
        verification_matrix = [
            {
                "claim": claim,
                "support_status": "unsupported",
                "overlap_score": 0.0,
                "confidence": _claim_confidence(overlap_ratio=0.0, support_status="unsupported"),
                "evidence_ref": None,
                "evidence_snippet": "",
            }
            for claim in claims
        ]
        verification_matrix_summary = _build_matrix_summary(
            verification_matrix,
            claims_count=len(claims),
            supported_claims=0,
        )
        contradiction_summary = _build_contradiction_summary(verification_matrix)
        return FactCheckResult(
            enabled=True,
            stage="fides-lite-v1.1",
            verdict="warn",
            confidence=0.35,
            supported_claims=0,
            total_claims=len(claims),
            unsupported_claims=claims[:3],
            evidence_count=0,
            severity="high",
            note="Không có bằng chứng truy xuất để fact-check.",
            verification_matrix=verification_matrix,
            contradiction_summary=contradiction_summary,
            fide_report=_build_fide_report(
                claims_count=len(claims),
                evidence_count=0,
                supported_claims=0,
                verdict="warn",
                severity="high",
                confidence=0.35,
                note="Không có bằng chứng truy xuất để fact-check.",
                unsupported_claims=claims[:3],
                verification_matrix=verification_matrix,
                verification_matrix_summary=verification_matrix_summary,
                contradiction_summary=contradiction_summary,
                citation_present=_has_citations(answer, context_ids),
                mode=normalized_mode,
            ),
        )

    supported_claims = 0
    unsupported_claims: list[str] = []
    contradicted_claims: list[str] = []
    verification_matrix: list[dict[str, Any]] = []

    for claim in claims:
        ratio, matched_evidence = _best_overlap_match(claim, evidence_rows)
        evidence_text = matched_evidence.get("text", "") if matched_evidence else ""
        contradiction = _has_contradiction(claim, evidence_text, ratio)
        if contradiction:
            support_status = "contradicted"
        elif ratio >= 0.2:
            support_status = "supported"
        else:
            support_status = "unsupported"

        if contradiction:
            contradicted_claims.append(claim)
        elif ratio >= 0.2:
            supported_claims += 1
        else:
            unsupported_claims.append(claim)
        verification_matrix.append(
            {
                "claim": claim,
                "support_status": support_status,
                "overlap_score": round(float(ratio), 4),
                "confidence": _claim_confidence(overlap_ratio=ratio, support_status=support_status),
                "evidence_ref": matched_evidence.get("ref") if matched_evidence and ratio > 0 else None,
                "evidence_snippet": (
                    _compact_snippet(evidence_text, max_len=180)
                    if matched_evidence and ratio > 0
                    else ""
                ),
            }
        )

    support_ratio = supported_claims / max(len(claims), 1)
    citation_present = _has_citations(answer, context_ids)

    confidence = 0.45 + (0.45 * support_ratio)
    if contradicted_claims:
        confidence -= 0.25 * min(1.0, len(contradicted_claims) / max(len(claims), 1))
    if not citation_present:
        confidence -= 0.08
    confidence = max(0.25, min(0.95, confidence))

    pass_threshold = 0.8 if normalized_mode == "strict" else 0.75
    warn_threshold = 0.55 if normalized_mode == "strict" else 0.4

    if contradicted_claims:
        verdict = "fail"
        severity = "high"
        note = "Phát hiện claim có dấu hiệu mâu thuẫn với bằng chứng truy xuất."
    elif support_ratio >= pass_threshold:
        verdict = "pass"
        severity = "low"
        if citation_present:
            note = "Đã đối chiếu với evidence retrieval và đạt ngưỡng hỗ trợ cao."
        else:
            note = "Claim được hỗ trợ tốt, nhưng câu trả lời chưa ghi rõ citation."
    elif support_ratio >= warn_threshold:
        verdict = "warn"
        severity = "medium"
        note = "Một phần claim chưa đủ bằng chứng, cần hiển thị cảnh báo."
    else:
        verdict = "warn"
        severity = "high"
        note = "Đa số claim không được hỗ trợ bởi evidence retrieval."

    unsupported_bundle = unsupported_claims + [
        f"[contradiction] {claim}" for claim in contradicted_claims
    ]
    verification_matrix_summary = _build_matrix_summary(
        verification_matrix,
        claims_count=len(claims),
        supported_claims=supported_claims,
    )
    contradiction_summary = _build_contradiction_summary(verification_matrix)

    return FactCheckResult(
        enabled=True,
        stage="fides-lite-v1.1",
        verdict=verdict,
        confidence=confidence,
        supported_claims=supported_claims,
        total_claims=len(claims),
        unsupported_claims=unsupported_bundle[:3],
        evidence_count=len(evidence_rows),
        severity=severity,
        note=note,
        verification_matrix=verification_matrix,
        contradiction_summary=contradiction_summary,
        fide_report=_build_fide_report(
            claims_count=len(claims),
            evidence_count=len(evidence_rows),
            supported_claims=supported_claims,
            verdict=verdict,
            severity=severity,
            confidence=confidence,
            note=note,
            unsupported_claims=unsupported_bundle,
            verification_matrix=verification_matrix,
            verification_matrix_summary=verification_matrix_summary,
            contradiction_summary=contradiction_summary,
            citation_present=citation_present,
            mode=normalized_mode,
        ),
    )
