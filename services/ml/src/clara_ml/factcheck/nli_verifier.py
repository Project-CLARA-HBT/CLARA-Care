from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient


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
_DOSAGE_TERMS = {"liều", "lieu", "dose", "dosage", "mg", "viên", "vien", "uống", "uong"}
_INTERACTION_TERMS = {"tương", "tac", "interaction", "ddi", "dùng", "cùng", "warfarin", "aspirin"}
_CONTRAINDICATION_TERMS = {"chống", "chong", "contraindication", "contraindicated", "không nên", "avoid"}


@dataclass
class ClaimVerdict:
    claim: str
    claim_type: str
    nli_label: str
    support_status: str
    confidence: float
    overlap_score: float
    evidence_ref: str | None
    evidence_snippet: str
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "claim_type": self.claim_type,
            "nli_label": self.nli_label,
            "support_status": self.support_status,
            "confidence": round(float(self.confidence), 4),
            "overlap_score": round(float(self.overlap_score), 4),
            "evidence_ref": self.evidence_ref,
            "evidence_snippet": self.evidence_snippet,
            "rationale": self.rationale,
        }


NliClaimVerdict = ClaimVerdict


def _tokenize(text: str) -> set[str]:
    lowered = str(text or "").lower()
    return {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", lowered) if token}


def _compact_snippet(text: str, *, max_len: int = 180) -> str:
    snippet = " ".join(str(text or "").split()).strip()
    if not snippet:
        return ""
    if len(snippet) <= max_len:
        return snippet
    return f"{snippet[: max_len - 3]}..."


def infer_claim_type(claim: str) -> str:
    claim_tokens = _tokenize(claim)
    if claim_tokens.intersection(_DOSAGE_TERMS):
        return "dosage"
    if claim_tokens.intersection(_CONTRAINDICATION_TERMS):
        return "contraindication"
    if claim_tokens.intersection(_INTERACTION_TERMS):
        return "interaction"
    return "general"


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


def _claim_confidence(*, overlap_ratio: float, support_status: str) -> float:
    bounded_ratio = max(0.0, min(float(overlap_ratio), 1.0))
    if support_status == "contradicted":
        score = 0.2 + (0.28 * bounded_ratio)
    elif support_status == "supported":
        score = 0.56 + (0.4 * bounded_ratio)
    else:
        score = 0.2 + (0.3 * bounded_ratio)
    return max(0.05, min(0.98, score))


def _status_rationale(*, support_status: str, overlap_ratio: float, evidence_ref: str | None) -> str:
    if support_status == "supported":
        return f"Claim được evidence hỗ trợ (overlap={overlap_ratio:.2f}, ref={evidence_ref or 'n/a'})."
    if support_status == "contradicted":
        return f"Claim có dấu hiệu mâu thuẫn với evidence (overlap={overlap_ratio:.2f}, ref={evidence_ref or 'n/a'})."
    return "Chưa đủ bằng chứng hỗ trợ claim trong tập evidence hiện tại."


def classify_claim(
    claim: str,
    *,
    evidence_rows: list[dict[str, str]],
    support_threshold: float = 0.2,
) -> ClaimVerdict:
    overlap_ratio, matched_evidence = _best_overlap_match(claim, evidence_rows)
    evidence_text = matched_evidence.get("text", "") if matched_evidence else ""
    contradiction = _has_contradiction(claim, evidence_text, overlap_ratio)
    if contradiction:
        nli_label = "contradicted"
        support_status = "contradicted"
    elif overlap_ratio >= support_threshold:
        nli_label = "supported"
        support_status = "supported"
    else:
        nli_label = "insufficient"
        support_status = "insufficient"

    evidence_ref = matched_evidence.get("ref") if matched_evidence and overlap_ratio > 0 else None
    evidence_snippet = _compact_snippet(evidence_text, max_len=180) if evidence_ref else ""
    confidence = _claim_confidence(overlap_ratio=overlap_ratio, support_status=support_status)
    rationale = _status_rationale(
        support_status=support_status,
        overlap_ratio=overlap_ratio,
        evidence_ref=evidence_ref,
    )
    return ClaimVerdict(
        claim=claim,
        claim_type=infer_claim_type(claim),
        nli_label=nli_label,
        support_status=support_status,
        confidence=confidence,
        overlap_score=round(float(overlap_ratio), 4),
        evidence_ref=evidence_ref,
        evidence_snippet=evidence_snippet,
        rationale=rationale,
    )


def _strip_markdown_fence(raw: str) -> str:
    text = str(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _clamp_confidence(value: Any, *, default: float = 0.5) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(0.01, min(0.99, parsed))


def _normalize_llm_support_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"supported", "support", "entailment", "entailed"}:
        return "supported"
    if normalized in {"contradicted", "contradiction", "refuted", "conflict"}:
        return "contradicted"
    return "insufficient"


def _should_use_llm_nli(*, llm_enabled: bool | None) -> bool:
    strategy = str(settings.rag_nli_strategy or "").strip().lower()
    strategy_enabled = strategy in {"llm", "llm_hybrid", "hybrid_llm"}
    runtime_enabled = bool(settings.rag_nli_llm_enabled or strategy_enabled)
    if llm_enabled is not None:
        runtime_enabled = bool(llm_enabled)
    return runtime_enabled and bool(str(settings.deepseek_api_key or "").strip())


def _build_nli_client(*, timeout_ms: int) -> DeepSeekClient:
    timeout_seconds = max(0.15, float(timeout_ms) / 1000.0)
    return DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout_seconds=timeout_seconds,
        retries_per_base=0,
        retry_backoff_seconds=0.0,
        max_concurrency=settings.llm_global_max_concurrency,
        min_interval_seconds=settings.llm_global_min_interval_seconds,
        request_jitter_seconds=settings.llm_global_jitter_seconds,
    )


def _llm_verify_claims(
    *,
    claims: list[str],
    evidence_rows: list[dict[str, str]],
    timeout_ms: int,
    llm_client: DeepSeekClient | None = None,
) -> dict[int, dict[str, Any]]:
    if not claims:
        return {}
    evidence_compact = [
        {
            "ref": str(item.get("ref") or "").strip(),
            "text": _compact_snippet(str(item.get("text") or ""), max_len=240),
        }
        for item in evidence_rows[:16]
    ]
    system_prompt = (
        "You are a strict clinical NLI verifier. Return STRICT JSON only. "
        "Do not include markdown."
    )
    prompt = (
        "Verify each claim against the provided evidence list.\n"
        "Output EXACT JSON schema:\n"
        "{\n"
        '  "rows": [\n'
        "    {\n"
        '      "claim_index": 0,\n'
        '      "support_status": "supported|contradicted|insufficient",\n'
        '      "confidence": 0.0,\n'
        '      "evidence_ref": "optional-ref",\n'
        '      "rationale": "short reason"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- If evidence does not clearly support claim, use insufficient.\n"
        "- Use contradicted only when evidence clearly conflicts.\n"
        "- confidence range [0,1].\n\n"
        f"claims={json.dumps(claims, ensure_ascii=False)}\n"
        f"evidence={json.dumps(evidence_compact, ensure_ascii=False)}\n"
    )
    client = llm_client or _build_nli_client(timeout_ms=timeout_ms)
    response = client.generate(prompt=prompt, system_prompt=system_prompt)
    cleaned = _strip_markdown_fence(response.content)
    payload = json.loads(cleaned)
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return {}
    available_refs = {str(item.get("ref") or "").strip() for item in evidence_rows}
    normalized: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            claim_index = int(row.get("claim_index"))
        except (TypeError, ValueError):
            continue
        if claim_index < 0 or claim_index >= len(claims):
            continue
        support_status = _normalize_llm_support_status(row.get("support_status"))
        confidence = _clamp_confidence(row.get("confidence"), default=0.5)
        evidence_ref = str(row.get("evidence_ref") or "").strip() or None
        if evidence_ref and evidence_ref not in available_refs:
            evidence_ref = None
        rationale = _compact_snippet(str(row.get("rationale") or ""), max_len=200)
        normalized[claim_index] = {
            "support_status": support_status,
            "confidence": confidence,
            "evidence_ref": evidence_ref,
            "rationale": rationale or "LLM NLI verification applied.",
        }
    return normalized


def _apply_llm_nli_overrides(
    *,
    base_rows: list[ClaimVerdict],
    llm_rows: dict[int, dict[str, Any]],
    evidence_rows: list[dict[str, str]],
) -> list[ClaimVerdict]:
    if not llm_rows:
        return base_rows
    evidence_map = {
        str(item.get("ref") or "").strip(): _compact_snippet(
            str(item.get("text") or ""),
            max_len=180,
        )
        for item in evidence_rows
    }
    merged: list[ClaimVerdict] = []
    for idx, base in enumerate(base_rows):
        override = llm_rows.get(idx)
        if not override:
            merged.append(base)
            continue
        status = str(override.get("support_status") or base.support_status).strip().lower()
        evidence_ref = str(override.get("evidence_ref") or "").strip() or base.evidence_ref
        evidence_snippet = evidence_map.get(evidence_ref or "", base.evidence_snippet or "")
        rationale = str(override.get("rationale") or "").strip() or base.rationale
        merged.append(
            ClaimVerdict(
                claim=base.claim,
                claim_type=base.claim_type,
                nli_label=status,
                support_status=status,
                confidence=_clamp_confidence(override.get("confidence"), default=base.confidence),
                overlap_score=base.overlap_score,
                evidence_ref=evidence_ref,
                evidence_snippet=evidence_snippet,
                rationale=rationale,
            )
        )
    return merged


def summarize_verdicts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_claims = len(rows)
    supported_claims = 0
    contradicted_claims = 0
    unsupported_claims = 0
    for row in rows:
        status = str(row.get("support_status") or "").strip().lower()
        if status == "supported":
            supported_claims += 1
        elif status == "contradicted":
            contradicted_claims += 1
        else:
            unsupported_claims += 1

    support_ratio = supported_claims / max(total_claims, 1) if total_claims > 0 else 0.0
    return {
        "version": "claim-v2-nli",
        "total_claims": total_claims,
        "supported_claims": supported_claims,
        "unsupported_claims": unsupported_claims,
        "contradicted_claims": contradicted_claims,
        "support_ratio": round(float(support_ratio), 4),
    }


def contradiction_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    contradicted_rows = [
        row
        for row in rows
        if str(row.get("support_status") or "").strip().lower() == "contradicted"
    ]
    details = [
        {
            "claim": row.get("claim", ""),
            "claim_type": row.get("claim_type", "general"),
            "evidence_ref": row.get("evidence_ref"),
            "evidence_snippet": row.get("evidence_snippet", ""),
            "overlap_score": row.get("overlap_score", 0.0),
            "confidence": row.get("confidence", 0.0),
            "rationale": row.get("rationale", ""),
        }
        for row in contradicted_rows[:5]
    ]
    return {
        "version": "claim-v2-nli",
        "has_contradiction": bool(contradicted_rows),
        "contradiction_count": len(contradicted_rows),
        "claims": [str(item.get("claim") or "") for item in contradicted_rows[:5]],
        "details": details,
        "note": (
            "Phát hiện claim mâu thuẫn với evidence retrieval."
            if contradicted_rows
            else "Không phát hiện claim mâu thuẫn."
        ),
    }


def build_verification_matrix(
    claims: list[str],
    *,
    evidence_rows: list[dict[str, str]],
) -> dict[str, Any]:
    rows = [classify_claim(claim, evidence_rows=evidence_rows).as_dict() for claim in claims]
    summary = summarize_verdicts(rows)
    contradiction = contradiction_summary(rows)
    return {
        "version": "claim-v2-nli",
        "rows": rows,
        "summary": summary,
        "contradiction_summary": contradiction,
}


def verify_claims(
    *,
    claims: list[str],
    evidence_rows: list[dict[str, str]],
    llm_enabled: bool | None = None,
    llm_timeout_ms: int | None = None,
    llm_client: DeepSeekClient | None = None,
) -> list[ClaimVerdict]:
    base_rows = [classify_claim(claim, evidence_rows=evidence_rows) for claim in claims]
    allow_llm = _should_use_llm_nli(llm_enabled=llm_enabled) or (
        llm_client is not None and (llm_enabled is None or bool(llm_enabled))
    )
    if not allow_llm:
        return base_rows

    timeout_ms = int(
        settings.rag_nli_llm_timeout_ms if llm_timeout_ms is None else llm_timeout_ms
    )
    timeout_ms = max(100, timeout_ms)
    try:
        llm_rows = _llm_verify_claims(
            claims=claims,
            evidence_rows=evidence_rows,
            timeout_ms=timeout_ms,
            llm_client=llm_client,
        )
        return _apply_llm_nli_overrides(
            base_rows=base_rows,
            llm_rows=llm_rows,
            evidence_rows=evidence_rows,
        )
    except Exception:
        return base_rows


def summarize_verification_matrix(
    *,
    rows: list[dict[str, Any]],
    total_claims: int | None = None,
) -> dict[str, Any]:
    summary = summarize_verdicts(rows)
    if total_claims is not None:
        inferred_total = max(int(total_claims), int(summary.get("total_claims") or 0))
        supported = int(summary.get("supported_claims") or 0)
        contradicted = int(summary.get("contradicted_claims") or 0)
        unsupported = max(inferred_total - supported - contradicted, int(summary.get("unsupported_claims") or 0))
        support_ratio = supported / max(inferred_total, 1) if inferred_total > 0 else 0.0
        summary = {
            **summary,
            "total_claims": inferred_total,
            "unsupported_claims": unsupported,
            "support_ratio": round(float(support_ratio), 4),
        }
    return summary


def build_contradiction_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return contradiction_summary(rows)
