"""Deterministic Emergency and Red-Flag Detector for Care Navigation.

Guarantees safety-first triage by identifying acute life-threatening signs
(chest pain, acute dyspnea, stroke signs, severe hemorrhage, anaphylaxis,
acute suicidal ideation) via rule-based keyword and pattern matching.
Findings from this detector cannot be downgraded by generative LLMs or downstream logic.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import ClassVar, Literal

RedFlagCategory = Literal[
    "chest_pain",
    "acute_dyspnea",
    "stroke_signs",
    "severe_hemorrhage",
    "anaphylaxis",
    "acute_suicidal_ideation",
    "unconscious_or_seizure",
]


@dataclass(frozen=True)
class RedFlagFinding:
    """Represents a detected red-flag symptom or emergency indicator."""

    category: RedFlagCategory | str
    matched_phrase: str
    severity: Literal["EMERGENCY"] = "EMERGENCY"
    evidence_snippet: str = ""
    description_vi: str = ""
    description_en: str = ""


class EmergencyRedFlagDetector:
    """Deterministic, bilingual emergency and red flag detector.

    Enforces the safety floor across all care navigation and symptom check flows.
    """

    _NEGATIONS: ClassVar[tuple[str, ...]] = (
        "khong ",
        "khong bi ",
        "khong co ",
        "chua tung ",
        "chua bi ",
        "khong thay ",
        "loai tru ",
        "het ",
        "da het ",
        "khong con ",
        "no ",
        "denies ",
        "denied ",
        "negative for ",
        "without ",
        "rules out ",
        "ruled out ",
        "free of ",
    )

    # Categories with bilingual trigger phrases (normalized / unaccented forms)
    _RULES: ClassVar[dict[RedFlagCategory, tuple[str, ...]]] = {
        "chest_pain": (
            "dau nguc",
            "tuc nguc",
            "nang nguc",
            "dau that nguc",
            "bop nghet nguc",
            "dau nhoi nguc",
            "dau nguc trai",
            "dau nguc lan",
            "chest pain",
            "crushing chest pain",
            "substernal pain",
            "substernal pressure",
            "pressure in chest",
            "pain radiating to left arm",
            "pain radiating to jaw",
            "tightness in chest",
            "heavy chest",
        ),
        "acute_dyspnea": (
            "kho tho cap",
            "kho tho du doi",
            "khong tho duoc",
            "kho tho dot ngot",
            "nghet tho",
            "tho gap du doi",
            "tho doc du doi",
            "hut hoi tram trong",
            "tho rit",
            "tim tai",
            "co keo long nguc",
            "acute dyspnea",
            "severe shortness of breath",
            "cannot breathe",
            "can't breathe",
            "unable to breathe",
            "gasping for air",
            "severe breathlessness",
            "stridor",
            "cyanosis",
            "respiratory distress",
        ),
        "stroke_signs": (
            "dot quy",
            "tai bien",
            "meo mieng",
            "meo mat",
            "liet mat",
            "yeu nua nguoi",
            "liet nua nguoi",
            "yeu liet mot ben",
            "yeu tay chan mot ben",
            "noi ngong dot ngot",
            "khong noi duoc dot ngot",
            "mat thi luc dot ngot",
            "mat thang bang dot ngot",
            "stroke",
            "facial droop",
            "face drooping",
            "arm weakness",
            "one sided weakness",
            "slurred speech",
            "sudden loss of speech",
            "sudden numbness one side",
            "sudden loss of balance",
            "fast signs",
        ),
        "severe_hemorrhage": (
            "chay mau khong cam",
            "chay mau du doi",
            "chay mau o at",
            "chay mau nhieu",
            "non ra mau",
            "ho ra mau",
            "ho ra mau set",
            "ho ra mau tuoi",
            "di ngoai ra mau tuoi o at",
            "phan den nhu ba ca phe",
            "xuat huyet nang",
            "severe bleeding",
            "heavy bleeding",
            "severe hemorrhage",
            "massive bleeding",
            "uncontrolled bleeding",
            "bleeding won't stop",
            "vomiting blood",
            "hematemesis",
            "coughing up blood",
            "hemoptysis",
            "rectal bleeding massive",
        ),
        "anaphylaxis": (
            "soc phan ve",
            "sung moi luoi",
            "sung luoi",
            "sung hong",
            "nghen hong kho tho",
            "phu thanh quan",
            "phu mach",
            "di ung nang kho tho",
            "noi me day kem kho tho",
            "anaphylaxis",
            "anaphylactic",
            "swollen tongue",
            "throat swelling",
            "swollen throat",
            "swollen lips and difficulty breathing",
            "severe allergic reaction",
            "angioedema with airway",
            "airway obstruction allergic",
        ),
        "acute_suicidal_ideation": (
            "tu sat",
            "tu tu",
            "muon tu sat",
            "muon tu tu",
            "muon chet",
            "muon ket lieu",
            "y dinh tu sat",
            "ke hoach tu sat",
            "cat co tay",
            "uong thuoc tu tu",
            "suicide",
            "suicidal",
            "want to kill myself",
            "want to die",
            "end my life",
            "commit suicide",
            "suicidal ideation",
            "suicide attempt",
            "suicide plan",
            "kill myself",
        ),
        "unconscious_or_seizure": (
            "bat tinh",
            "hon me",
            "ngat xiu khong tinh",
            "co giat lien tuc",
            "co giat du doi",
            "unconscious",
            "loss of consciousness",
            "unresponsive",
            "continuous seizure",
            "status epilepticus",
        ),
    }

    _DESCRIPTIONS_VI: ClassVar[dict[RedFlagCategory, str]] = {
        "chest_pain": "Đau hoặc tức nặng ngực cấp tính (nguy cơ biến cố tim mạch cấp)",
        "acute_dyspnea": "Khó thở cấp tính / suy hô hấp nghiêm trọng",
        "stroke_signs": "Dấu hiệu nghi ngờ đột quỵ (méo miệng, yếu liệt nửa người, rối loạn ngôn ngữ)",
        "severe_hemorrhage": "Xuất huyết nặng hoặc chảy máu không cầm",
        "anaphylaxis": "Dấu hiệu sốc phản vệ / phù nề đường thở cấp",
        "acute_suicidal_ideation": "Ý định hoặc hành vi tự hại / tự sát cấp tính",
        "unconscious_or_seizure": "Bất tỉnh, hôn mê hoặc co giật",
    }

    _DESCRIPTIONS_EN: ClassVar[dict[RedFlagCategory, str]] = {
        "chest_pain": "Acute chest pain or substernal pressure (potential acute cardiovascular event)",
        "acute_dyspnea": "Acute severe dyspnea / respiratory distress",
        "stroke_signs": "Suspected stroke signs (facial droop, unilateral weakness, sudden speech loss)",
        "severe_hemorrhage": "Severe or uncontrolled hemorrhage",
        "anaphylaxis": "Anaphylaxis / acute upper airway compromise",
        "acute_suicidal_ideation": "Acute suicidal ideation or self-harm intent",
        "unconscious_or_seizure": "Loss of consciousness, coma, or acute seizure",
    }

    @staticmethod
    def fold_text(text: str) -> str:
        """Normalize Vietnamese text to lowercase ASCII without combining marks."""
        normalized = unicodedata.normalize("NFD", text.lower())
        plain = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        plain = plain.replace("đ", "d").replace("Đ", "d")
        return re.sub(r"\s+", " ", plain).strip()

    @classmethod
    def _is_negated(cls, text: str, start: int) -> bool:
        """Check if the matched trigger is preceded by a negation within 36 characters."""
        window = text[max(0, start - 36) : start]
        if not window:
            return False
        # If there's a contrastive conjunction ("nhung", "but", "tuy nhien") after the negation, reset window
        for contrast in ("nhung ", "but ", "tuy nhien ", "however "):
            idx = window.rfind(contrast)
            if idx >= 0:
                window = window[idx + len(contrast) :]

        return any(neg.strip() in window for neg in cls._NEGATIONS)

    @classmethod
    def detect(cls, text: str) -> list[RedFlagFinding]:
        """Scan input text and return all detected emergency red-flag findings.

        Guarantees deterministic matching and checks for explicit negations.
        """
        if not text or not text.strip():
            return []

        folded = cls.fold_text(text)
        findings: list[RedFlagFinding] = []
        seen_categories: set[str] = set()

        for category, triggers in cls._RULES.items():
            if category in seen_categories:
                continue
            for trigger in triggers:
                needle = cls.fold_text(trigger)
                # Word-boundary or exact token containment check
                start = folded.find(needle)
                if start >= 0 and not cls._is_negated(folded, start):
                    # Extract original snippet around trigger
                    orig_start = max(0, start - 10)
                    orig_end = min(len(text), start + len(needle) + 10)
                    snippet = text[orig_start:orig_end].strip()

                    findings.append(
                        RedFlagFinding(
                            category=category,
                            matched_phrase=trigger,
                            severity="EMERGENCY",
                            evidence_snippet=snippet or trigger,
                            description_vi=cls._DESCRIPTIONS_VI.get(category, trigger),
                            description_en=cls._DESCRIPTIONS_EN.get(category, trigger),
                        )
                    )
                    seen_categories.add(category)
                    break

        return findings

    @classmethod
    def has_emergency(cls, text: str) -> bool:
        """Fast boolean probe for any emergency red-flag in the text."""
        return len(cls.detect(text)) > 0
