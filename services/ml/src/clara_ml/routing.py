from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass
class RouteResult:
    role: str
    intent: str
    confidence: float
    emergency: bool


class P1RoleIntentRouter:
    EMERGENCY_KEYWORDS = (
        "kho tho",
        "dau nguc du doi",
        "bat tinh",
        "co giat",
        "dot quy",
        "soc phan ve",
        "chay mau khong cam",
        "tu sat",
        "suicide",
        "overdose",
    )

    ROLE_KEYWORDS = {
        "doctor": (
            "benh nhan",
            "chan doan",
            "phac do",
            "ddi",
            "contraindication",
            "clinical",
            "dosing",
            "toa thuoc",
        ),
        "researcher": (
            "meta-analysis",
            "systematic review",
            "rct",
            "cohort",
            "dataset",
            "protocol",
            "pubmed",
            "p-value",
        ),
        "normal": (
            "trieu chung",
            "hoi",
            "tu van",
            "thuoc",
            "an uong",
            "tap luyen",
            "suc khoe",
            "cham soc",
        ),
    }

    INTENT_KEYWORDS = {
        "normal": {
            "symptom_triage": ("trieu chung", "dau", "sot", "ho", "kham"),
            "medication_safety": ("thuoc", "lieu", "tuong tac", "di ung", "quen lieu"),
            "lifestyle_guidance": ("an uong", "tap", "ngu", "giam can", "lifestyle"),
        },
        "researcher": {
            "evidence_review": ("meta-analysis", "systematic", "evidence", "pubmed"),
            "study_design": ("protocol", "rct", "cohort", "sample size", "randomized"),
            "data_analysis": ("dataset", "p-value", "regression", "bias", "confounder"),
        },
        "doctor": {
            "doctor_case_review": ("benh nhan", "ca benh", "xet nghiem", "chan doan"),
            "doctor_ddi_check": ("ddi", "tuong tac", "contraindication", "chong chi dinh"),
            "doctor_treatment_plan": ("phac do", "dieu tri", "lieu", "ke don", "theo doi"),
        },
    }

    INTENT_PRIORITY = {
        "normal": ("medication_safety", "symptom_triage", "lifestyle_guidance"),
        "researcher": ("evidence_review", "study_design", "data_analysis"),
        "doctor": ("doctor_ddi_check", "doctor_case_review", "doctor_treatment_plan"),
    }

    def route(self, query: str, role_hint: str | None = None) -> RouteResult:
        normalized = self._normalize(query)
        if self._contains_any(normalized, self.EMERGENCY_KEYWORDS):
            return RouteResult(
                role="doctor",
                intent="emergency_triage",
                confidence=0.995,
                emergency=True,
            )

        role_hint_normalized = (role_hint or "").strip().lower()
        if role_hint_normalized in {"normal", "researcher", "doctor"}:
            role = role_hint_normalized
            role_confidence = 0.99
        else:
            role, role_confidence = self._classify_role(normalized)
        intent, intent_confidence = self._classify_intent(role, normalized)
        confidence = round((role_confidence + intent_confidence) / 2.0, 3)
        return RouteResult(role=role, intent=intent, confidence=confidence, emergency=False)

    @staticmethod
    def _normalize(text: str) -> str:
        lowered = text.lower().strip()
        folded = unicodedata.normalize("NFD", lowered)
        without_marks = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
        collapsed = re.sub(r"\s+", " ", without_marks)
        return collapsed

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _count_hits(text: str, keywords: tuple[str, ...]) -> int:
        return sum(1 for keyword in keywords if keyword in text)

    def _classify_role(self, normalized_query: str) -> tuple[str, float]:
        role_scores = {
            role: self._count_hits(normalized_query, keywords)
            for role, keywords in self.ROLE_KEYWORDS.items()
        }
        role = max(role_scores, key=role_scores.get)
        hits = role_scores[role]
        if hits == 0:
            return "normal", 0.56
        return role, min(0.95, 0.62 + 0.11 * hits)

    def _classify_intent(self, role: str, normalized_query: str) -> tuple[str, float]:
        intents = self.INTENT_KEYWORDS[role]
        intent_scores = {
            intent: self._count_hits(normalized_query, keywords)
            for intent, keywords in intents.items()
        }
        priority = {name: idx for idx, name in enumerate(self.INTENT_PRIORITY[role])}
        intent = min(
            intent_scores.keys(),
            key=lambda name: (-intent_scores[name], priority.get(name, len(priority))),
        )
        hits = intent_scores[intent]
        if hits == 0:
            default_intent = {
                "normal": "symptom_triage",
                "researcher": "evidence_review",
                "doctor": "doctor_case_review",
            }[role]
            return default_intent, 0.58
        return intent, min(0.95, 0.64 + 0.1 * hits)
