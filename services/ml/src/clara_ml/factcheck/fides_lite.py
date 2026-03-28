from __future__ import annotations

import re
from dataclasses import dataclass
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
        }


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", text.lower()) if token}


def _split_claims(answer: str) -> list[str]:
    chunks = re.split(r"[.!?\n]+", answer)
    claims = [chunk.strip() for chunk in chunks if len(chunk.strip()) >= 20]
    return claims[:8]


def _best_overlap_ratio(claim: str, evidence_texts: list[str]) -> float:
    claim_tokens = _tokenize(claim)
    if not claim_tokens:
        return 0.0
    best = 0.0
    for text in evidence_texts:
        doc_tokens = _tokenize(text)
        if not doc_tokens:
            continue
        overlap = len(claim_tokens.intersection(doc_tokens))
        ratio = overlap / max(len(claim_tokens), 1)
        if ratio > best:
            best = ratio
    return best


def run_fides_lite(
    *,
    answer: str,
    retrieved_context: list[dict[str, Any]],
) -> FactCheckResult:
    evidence_texts = [str(item.get("text", "")) for item in retrieved_context if item.get("text")]
    claims = _split_claims(answer)

    if not claims:
        return FactCheckResult(
            enabled=True,
            stage="fides-lite-v1",
            verdict="pass",
            confidence=0.55,
            supported_claims=0,
            total_claims=0,
            unsupported_claims=[],
            evidence_count=len(evidence_texts),
            severity="low",
            note="Khong co atomic claim de kiem chung.",
        )

    if not evidence_texts:
        return FactCheckResult(
            enabled=True,
            stage="fides-lite-v1",
            verdict="warn",
            confidence=0.35,
            supported_claims=0,
            total_claims=len(claims),
            unsupported_claims=claims[:3],
            evidence_count=0,
            severity="high",
            note="Khong co evidence retrieval de fact-check.",
        )

    supported_claims = 0
    unsupported_claims: list[str] = []

    for claim in claims:
        ratio = _best_overlap_ratio(claim, evidence_texts)
        if ratio >= 0.18:
            supported_claims += 1
        else:
            unsupported_claims.append(claim)

    support_ratio = supported_claims / max(len(claims), 1)

    if support_ratio >= 0.75:
        verdict = "pass"
        severity = "low"
        confidence = 0.85
        note = "Da doi chieu voi evidence retrieval va dat nguong ho tro."
    elif support_ratio >= 0.4:
        verdict = "warn"
        severity = "medium"
        confidence = 0.65
        note = "Mot phan claim chua du bang chung, can hien thi canh bao."
    else:
        verdict = "warn"
        severity = "high"
        confidence = 0.45
        note = "Da so claim khong duoc ho tro boi evidence retrieval."

    return FactCheckResult(
        enabled=True,
        stage="fides-lite-v1",
        verdict=verdict,
        confidence=confidence,
        supported_claims=supported_claims,
        total_claims=len(claims),
        unsupported_claims=unsupported_claims[:3],
        evidence_count=len(evidence_texts),
        severity=severity,
        note=note,
    )
