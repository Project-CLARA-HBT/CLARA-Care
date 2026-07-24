"""Validated, fail-closed contract for CLARA medical answers.

The module deliberately does not generate clinical facts.  It converts outputs
from the existing router, RAG verifier and CareGuard engine into a stable artifact
and enforces the safety invariants at the boundary presented to clients.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ClaimStatus = Literal["supported", "uncertain", "contradicted", "suppressed"]
UrgencyLevel = Literal["emergency", "urgent_review", "clinical_review", "routine"]


class MedicalClaim(BaseModel):
    claim_id: str
    text: str
    status: ClaimStatus
    evidence_ids: list[str] = Field(default_factory=list)
    actionable: bool = False
    decision_ready: bool = False

    @model_validator(mode="after")
    def supported_before_decision_ready(self) -> "MedicalClaim":
        if self.decision_ready and (self.status != "supported" or not self.evidence_ids):
            raise ValueError("decision-ready claims require supporting evidence")
        return self


class MedicalAnswerV2(BaseModel):
    schema_version: Literal["medical_answer_v2"] = "medical_answer_v2"
    audience: Literal["normal", "researcher", "doctor", "admin"]
    intent: str
    urgency: dict[str, Any]
    actions_now: list[str] = Field(default_factory=list)
    actions_today: list[str] = Field(default_factory=list)
    monitoring: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    problem_representation: str = ""
    differential: list[dict[str, Any]] = Field(default_factory=list)
    medication_safety: dict[str, Any] = Field(default_factory=dict)
    claims: list[MedicalClaim] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[dict[str, str]] = Field(default_factory=list)
    uncertainty: dict[str, Any]
    follow_up: list[str] = Field(default_factory=list)
    run_manifest: dict[str, Any]

    @model_validator(mode="after")
    def enforce_release_gates(self) -> "MedicalAnswerV2":
        if self.urgency.get("level") == "emergency" and not self.actions_now:
            raise ValueError("emergency answers must lead with an immediate action")
        evidence_ids = {
            str(item.get("evidence_id")) for item in self.evidence if item.get("evidence_id")
        }
        for claim in self.claims:
            if not set(claim.evidence_ids).issubset(evidence_ids):
                raise ValueError("claim references evidence absent from the snapshot")
        return self


_NEGATIONS = ("no ", "not ", "without ", "khong ", "không ", "chua ", "chưa ")
_RED_FLAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("breathing_difficulty", ("shortness of breath", "difficulty breathing", "khó thở", "kho tho")),
    (
        "severe_chest_pain",
        ("severe chest pain", "crushing chest pain", "đau ngực dữ dội", "dau nguc du doi"),
    ),
    (
        "stroke_signs",
        (
            "face droop",
            "slurred speech",
            "one-sided weakness",
            "méo miệng",
            "nói đớ",
            "yếu liệt một bên",
            "đột quỵ",
            "dot quy",
        ),
    ),
    (
        "anaphylaxis",
        (
            "anaphylaxis",
            "swollen tongue",
            "throat swelling",
            "sốc phản vệ",
            "soc phan ve",
            "sưng lưỡi",
        ),
    ),
    (
        "uncontrolled_bleeding",
        (
            "uncontrolled bleeding",
            "bleeding won't stop",
            "chảy máu không cầm",
            "chay mau khong cam",
        ),
    ),
    (
        "loss_of_consciousness",
        ("unconscious", "fainted", "loss of consciousness", "bất tỉnh", "bat tinh"),
    ),
    ("seizure", ("seizure", "convulsion", "co giật", "co giat")),
    ("overdose", ("overdose", "quá liều", "qua lieu")),
    ("self_harm", ("suicide", "kill myself", "end my life", "tự sát", "tu sat")),
)


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    plain = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", plain.replace("đ", "d")).strip()


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 18) : start]
    return any(prefix.endswith(negation) for negation in _NEGATIONS)


def detect_emergency_red_flags(text: str) -> list[str]:
    """Return deterministic bilingual red-flag codes, excluding simple negations."""

    folded = _fold(text)
    hits: list[str] = []
    for code, phrases in _RED_FLAG_RULES:
        for phrase in phrases:
            needle = _fold(phrase)
            start = folded.find(needle)
            if start >= 0 and not _is_negated(folded, start):
                hits.append(code)
                break
    return hits


def _stable_id(prefix: str, *parts: object) -> str:
    raw = "\x1f".join(str(part or "").strip() for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _snapshot_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for item in evidence:
        snapshot = dict(item)
        snapshot["evidence_id"] = _stable_id(
            "ev",
            item.get("source"),
            item.get("url"),
            item.get("title"),
            item.get("excerpt"),
        )
        snapshot.setdefault("retrieved_at", None)
        snapshots.append(snapshot)
    return snapshots


def _atomic_sentences(answer: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer.strip())
        if sentence.strip()
    ][:24]


def _is_actionable(text: str) -> bool:
    folded = _fold(text)
    tokens = (
        "take ",
        "start ",
        "stop ",
        "increase ",
        "decrease ",
        "dose ",
        "go to ",
        "call ",
        "seek ",
        "dung ",
        "uong ",
        "ngung ",
        "tang lieu",
        "giam lieu",
        "den ",
        "goi ",
    )
    return any(token in folded for token in tokens)


def _claims(
    answer: str,
    evidence: list[dict[str, Any]],
    factcheck: dict[str, Any],
    *,
    degraded: bool,
) -> list[MedicalClaim]:
    evidence_ids = [str(item["evidence_id"]) for item in evidence]
    verdict = str(factcheck.get("verdict") or "not_run").lower()
    verification_passed = bool(evidence_ids) and verdict in {"pass", "supported"} and not degraded
    contradicted = verdict in {"fail", "contradicted"}
    claims: list[MedicalClaim] = []
    for sentence in _atomic_sentences(answer):
        actionable = _is_actionable(sentence)
        if contradicted:
            status: ClaimStatus = "contradicted"
        elif verification_passed:
            status = "supported"
        elif actionable:
            status = "suppressed"
        else:
            status = "uncertain"
        claims.append(
            MedicalClaim(
                claim_id=_stable_id("cl", sentence),
                text=sentence,
                status=status,
                evidence_ids=evidence_ids if status == "supported" else [],
                actionable=actionable,
                decision_ready=actionable and status == "supported",
            )
        )
    return claims


def _medication_safety(careguard: dict[str, Any] | None, has_medications: bool) -> dict[str, Any]:
    if not has_medications:
        return {"status": "not_applicable", "findings": [], "decision_ready": True}
    if not isinstance(careguard, dict):
        return {
            "status": "not_checked",
            "findings": [],
            "decision_ready": False,
            "warning": "Medication safety checks were not completed; absence of a finding is not an all-clear.",
        }
    metadata = careguard.get("metadata") if isinstance(careguard.get("metadata"), dict) else {}
    alerts = careguard.get("ddi_alerts") if isinstance(careguard.get("ddi_alerts"), list) else []
    findings = [dict(item) for item in alerts if isinstance(item, dict)]
    unavailable = bool(metadata.get("rules_unavailable"))
    return {
        "status": "unavailable" if unavailable else "checked",
        "risk": careguard.get("risk", {}),
        "findings": findings,
        "recommendation": careguard.get("recommendation", ""),
        "decision_ready": not unavailable,
        "sources": metadata.get("source_used", []),
        "drugbank": metadata.get("drugbank", {}),
    }


def build_medical_answer_v2(
    *,
    answer: str,
    audience: str,
    intent: str,
    urgency_level: UrgencyLevel,
    emergency_red_flags: list[str],
    policy_action: str,
    model_used: str,
    evidence_ledger: list[dict[str, Any]],
    factcheck: dict[str, Any] | None,
    clinical_context: dict[str, Any] | None,
    missing_information: list[dict[str, str]],
    careguard: dict[str, Any] | None = None,
    harness_stages: list[dict[str, Any]] | None = None,
    answer_language: str = "vi",
) -> dict[str, Any]:
    """Build and validate the stable v2 artifact from real pipeline outputs."""

    context = clinical_context or {}
    evidence = _snapshot_evidence(evidence_ledger)
    fallback = model_used.startswith(("local-synth", "api-safe", "api-local"))
    claims = _claims(answer, evidence, factcheck or {}, degraded=fallback)
    medication_safety = _medication_safety(careguard, bool(context.get("medications")))
    unsupported = sum(claim.status != "supported" for claim in claims)
    emergency = urgency_level == "emergency"
    artifact = MedicalAnswerV2(
        audience=audience if audience in {"normal", "researcher", "doctor", "admin"} else "normal",
        intent=intent,
        urgency={
            "level": urgency_level,
            "emergency": emergency,
            "policy_action": policy_action,
        },
        actions_now=(
            [
                "Call local emergency services now or go to the nearest emergency department."
                if answer_language == "en"
                else "Gọi ngay số cấp cứu tại địa phương hoặc đến khoa Cấp cứu gần nhất."
            ]
            if emergency
            else []
        ),
        actions_today=[] if emergency else [claim.text for claim in claims if claim.decision_ready],
        monitoring=[],
        red_flags=emergency_red_flags,
        problem_representation=str(context.get("problem_representation") or ""),
        differential=[],
        medication_safety=medication_safety,
        claims=claims,
        evidence=evidence,
        contradictions=[],
        assumptions=[],
        missing_information=missing_information,
        uncertainty={
            "level": "high"
            if fallback or unsupported or not medication_safety["decision_ready"]
            else "low",
            "unsupported_claim_count": unsupported,
            "degraded": fallback,
        },
        follow_up=[] if emergency else [item["why_it_matters"] for item in missing_information[:3]],
        run_manifest={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_used": model_used,
            "evidence_count": len(evidence),
            "factcheck_verdict": str((factcheck or {}).get("verdict") or "not_run"),
            "careguard_status": medication_safety["status"],
            "harness_stages": harness_stages or [],
        },
    )
    return artifact.model_dump(mode="json")


def validate_medical_answer_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an externally stored/replayed artifact against current invariants."""

    return MedicalAnswerV2.model_validate(payload).model_dump(mode="json")
