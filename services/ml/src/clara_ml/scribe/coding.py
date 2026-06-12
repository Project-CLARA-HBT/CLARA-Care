"""Coding + medication-safety assistance for Scribe notes (task 1.7, Requirement 7).

`CodingAssistant.suggest(text)` produces ADVISORY metadata for a note:
- ICD code suggestions (each with the justifying text span) from a curated,
  pure keyword map — clearly marked as requiring clinician confirmation;
- normalized medications via the existing RAG drug lexicon / entity linker
  (lexicon-only = fast, offline, no network), degrading to surface text when
  unknown (Requirement 7.2);
- drug-drug interaction advisories via an INJECTABLE seam that, by default,
  REUSES the existing CareGuard/DDI path (``agents.careguard.run_careguard_analyze``,
  local rule set, external lookups disabled) — never reinvented (Requirement 7.3).

All output is additive metadata and never modifies the note's clinical text
(Requirement 7.4); nothing is presented as a confirmed diagnosis/prescription
(Requirement 7.5). Importing this module opens no socket.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from clara_ml.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "CodeSuggestion",
    "MedSuggestion",
    "EmCptSuggestion",
    "CodingResult",
    "CodingAssistant",
]


@dataclass(frozen=True, slots=True)
class CodeSuggestion:
    code: str
    system: str  # "ICD-10"
    description: str
    span: str  # the transcript/note text that justified the suggestion
    confirmed: bool = False  # always advisory until a clinician confirms


@dataclass(frozen=True, slots=True)
class MedSuggestion:
    surface: str  # text as mentioned
    normalized_name: str = ""
    rxcui: str = ""


@dataclass(frozen=True, slots=True)
class EmCptSuggestion:
    """An advisory E/M visit-level or CPT/procedure suggestion (Requirement 14).

    Each suggestion carries the justifying note/transcript text span(s) that
    support it (Req 14.2), is always advisory and ``selected=False`` until a
    clinician explicitly confirms it (Req 14.3/14.5), and is bilingual
    (Vietnamese-first ``display_vi`` alongside English ``display``, Req 14.6).
    ``level`` is the E/M visit level (1..5) for ``kind == "E/M"`` and ``None``
    for a CPT procedure.
    """

    code: str
    kind: str  # "E/M" | "CPT"
    system: str  # "E/M" | "CPT"
    display: str
    display_vi: str
    level: int | None = None
    spans: list[str] = field(default_factory=list)  # justifying text span(s)
    rationale: str = ""
    selected: bool = False  # NEVER True without explicit clinician confirmation
    status: str = "advisory"  # always advisory until confirmed

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "kind": self.kind,
            "system": self.system,
            "display": self.display,
            "display_vi": self.display_vi,
            "level": self.level,
            "spans": list(self.spans),
            "rationale": self.rationale,
            "selected": self.selected,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class CodingResult:
    icd: list[CodeSuggestion] = field(default_factory=list)
    medications: list[MedSuggestion] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)
    advisory: bool = True  # the whole result requires clinician confirmation
    # R14 (additive, flag-gated): E/M visit-level + CPT/procedure suggestions.
    # Empty unless RAG_SCRIBE_EM_CPT_CODING_ENABLED is on, so the flag-off
    # serialization is byte-for-byte identical to the Req 7 result.
    em_cpt: list[EmCptSuggestion] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "icd": [asdict(c) for c in self.icd],
            "medications": [asdict(m) for m in self.medications],
            "interactions": list(self.interactions),
            "advisory": self.advisory,
        }
        # Additive: only present when the E/M+CPT pass produced suggestions, so
        # the legacy (flag-off) coding_json payload is unchanged (Req 14.1).
        if self.em_cpt:
            out["em_cpt"] = [s.as_dict() for s in self.em_cpt]
        return out


# Curated, conservative keyword -> ICD-10 map (advisory only). Kept small and
# deterministic; the LLM/clinician refines. Each entry: (keyword, code, desc).
_ICD_KEYWORDS: list[tuple[str, str, str]] = [
    ("hypertension", "I10", "Essential (primary) hypertension"),
    ("tăng huyết áp", "I10", "Essential (primary) hypertension"),
    ("type 2 diabetes", "E11.9", "Type 2 diabetes mellitus without complications"),
    ("đái tháo đường", "E11.9", "Type 2 diabetes mellitus without complications"),
    ("asthma", "J45.909", "Unspecified asthma, uncomplicated"),
    ("hen", "J45.909", "Unspecified asthma, uncomplicated"),
    ("pneumonia", "J18.9", "Pneumonia, unspecified organism"),
    ("viêm phổi", "J18.9", "Pneumonia, unspecified organism"),
    ("urinary tract infection", "N39.0", "Urinary tract infection, site not specified"),
    ("acute pharyngitis", "J02.9", "Acute pharyngitis, unspecified"),
    ("viêm họng", "J02.9", "Acute pharyngitis, unspecified"),
    ("gastritis", "K29.70", "Gastritis, unspecified, without bleeding"),
    ("viêm dạ dày", "K29.70", "Gastritis, unspecified, without bleeding"),
    ("migraine", "G43.909", "Migraine, unspecified, not intractable"),
    ("anxiety", "F41.9", "Anxiety disorder, unspecified"),
]

# --- E/M + CPT coding (Requirement 14) -------------------------------------
# Conservative, deterministic, network-free keyword model. The E/M level is
# driven by Medical-Decision-Making (MDM) evidence — problems, prescription
# management, data reviewed, risk — which is the hardest axis to inflate with
# boilerplate, so the *defensible* ceiling resists upcoding (Req 14.4).

# Established-patient office-visit E/M codes by level (the common VN OPD case),
# with bilingual displays (Req 14.6).
_EM_CODE_BY_LEVEL: dict[int, str] = {
    1: "99211",
    2: "99212",
    3: "99213",
    4: "99214",
    5: "99215",
}
_EM_DISPLAY_EN: dict[int, str] = {
    1: "Office/outpatient visit, established patient, level 1 (minimal)",
    2: "Office/outpatient visit, established patient, level 2 (straightforward)",
    3: "Office/outpatient visit, established patient, level 3 (low complexity)",
    4: "Office/outpatient visit, established patient, level 4 (moderate complexity)",
    5: "Office/outpatient visit, established patient, level 5 (high complexity)",
}
_EM_DISPLAY_VI: dict[int, str] = {
    1: "Khám và quản lý (E/M) — mức 1, bệnh nhân tái khám (tối thiểu)",
    2: "Khám và quản lý (E/M) — mức 2, bệnh nhân tái khám (đơn giản)",
    3: "Khám và quản lý (E/M) — mức 3, bệnh nhân tái khám (phức tạp thấp)",
    4: "Khám và quản lý (E/M) — mức 4, bệnh nhân tái khám (phức tạp trung bình)",
    5: "Khám và quản lý (E/M) — mức 5, bệnh nhân tái khám (phức tạp cao)",
}

# Documented problems/diagnoses (English + Vietnamese). Used for MDM problem
# count; chronic entries also raise the defensible complexity floor.
_CHRONIC_PROBLEM_KEYWORDS: tuple[str, ...] = (
    "hypertension", "tăng huyết áp", "diabetes", "đái tháo đường", "tiểu đường",
    "asthma", "hen", "copd", "bệnh phổi tắc nghẽn", "heart failure", "suy tim",
    "chronic kidney", "suy thận mạn", "ckd", "coronary", "bệnh mạch vành",
    "hypothyroid", "suy giáp", "cirrhosis", "xơ gan", "epilepsy", "động kinh",
)
_ACUTE_PROBLEM_KEYWORDS: tuple[str, ...] = (
    "pneumonia", "viêm phổi", "pharyngitis", "viêm họng", "gastritis",
    "viêm dạ dày", "urinary tract infection", "nhiễm trùng tiểu", "migraine",
    "đau nửa đầu", "anxiety", "lo âu", "bronchitis", "viêm phế quản",
    "headache", "đau đầu", "fever", "sốt", "cough", "ho", "rash", "phát ban",
)

# Prescription-drug management (moderate-risk MDM, Req 14 anti-upcoding axis).
_PRESCRIPTION_CUES: tuple[str, ...] = (
    "prescribe", "prescribed", "prescription", "start", "started", "initiate",
    "initiated", "refill", "adjust dose", "adjusted dose", "titrate", "titrated",
    "increase dose", "decrease dose", "continue medication", "kê đơn", "kê toa",
    "đơn thuốc", "kê thuốc", "chỉnh liều", "tăng liều", "giảm liều",
    "duy trì thuốc",
)

# Data reviewed/ordered (labs, imaging, diagnostics) — MDM data axis. Cues are
# specific (a generic "reviewed" is excluded so reviewing history/exam narrative
# is not mistaken for diagnostic-data review).
_DATA_CUES: tuple[str, ...] = (
    "lab", "labs", "laboratory", "blood test", "cbc", "complete blood count",
    "x-ray", "x ray", "xray", "ecg", "ekg", "ct scan", "mri", "ultrasound",
    "biopsy", "culture", "metabolic panel", "lab panel", "ordered", "order labs",
    "results reviewed", "labs reviewed", "imaging reviewed", "data reviewed",
    "imaging", "xét nghiệm", "công thức máu", "chụp x quang", "x quang",
    "điện tâm đồ", "siêu âm", "chụp ct", "chụp mri", "cấy", "đánh giá kết quả",
    "chỉ định xét nghiệm",
)

# High-risk markers (high-complexity MDM risk axis) — hospitalization decision,
# threat to life, parenteral/intensive therapy.
_HIGH_RISK_CUES: tuple[str, ...] = (
    "hospitalize", "hospitalized", "hospitalization", "hospitalisation",
    "admit", "admitted", "admission", "icu", "intensive care",
    "life-threatening", "life threatening", "severe", "emergency", "parenteral",
    "intravenous", "iv drip", "intensive monitoring", "suicidal", "sepsis",
    "respiratory failure", "nhập viện", "cấp cứu", "hồi sức",
    "đe dọa tính mạng", "nguy kịch", "nặng", "suy hô hấp",
    "nhiễm trùng huyết", "truyền tĩnh mạch", "theo dõi tích cực",
)

# Documentation-breadth cues (history/exam). These are the gameable, low-bar
# axes a NAIVE level estimate keys on — so a note rich in these but thin on MDM
# is exactly where anti-upcoding (suggested ≤ defensible) bites.
_HISTORY_BREADTH_CUES: tuple[str, ...] = (
    "history of present illness", "hpi", "review of systems", "ros",
    "past medical history", "family history", "social history",
    "comprehensive history", "detailed history", "complete history",
    "bệnh sử", "tiền sử", "tiền căn", "khai thác bệnh sử", "tiền sử gia đình",
)
_EXAM_BREADTH_CUES: tuple[str, ...] = (
    "physical exam", "examination", "exam:", "on exam", "general appearance",
    "comprehensive exam", "detailed exam", "complete exam", "heent",
    "khám lâm sàng", "khám thực thể", "khám toàn diện", "thăm khám",
)

# CPT/procedure table: (keywords, code, display_en, display_vi). Conservative
# and bilingual (Req 14.6); each detected procedure yields one advisory CPT.
_CPT_PROCEDURES: tuple[tuple[tuple[str, ...], str, str, str], ...] = (
    (
        ("electrocardiogram", "ecg", "ekg", "điện tâm đồ", "đo điện tim"),
        "93000",
        "Electrocardiogram, routine ECG with interpretation and report",
        "Điện tâm đồ (ECG) thường quy kèm đọc và trả kết quả",
    ),
    (
        ("nebulizer", "nebulization", "khí dung", "phun khí dung"),
        "94640",
        "Nebulizer treatment for airway obstruction",
        "Khí dung điều trị tắc nghẽn đường thở",
    ),
    (
        ("spirometry", "pulmonary function test", "hô hấp ký", "đo chức năng hô hấp"),
        "94010",
        "Spirometry, pulmonary function test",
        "Đo chức năng hô hấp (hô hấp ký)",
    ),
    (
        ("intramuscular injection", "im injection", "therapeutic injection",
         "tiêm bắp", "tiêm thuốc điều trị"),
        "96372",
        "Therapeutic injection, subcutaneous or intramuscular",
        "Tiêm thuốc điều trị (dưới da hoặc tiêm bắp)",
    ),
    (
        ("incision and drainage", "i&d", "rạch dẫn lưu", "rạch thoát mủ"),
        "10060",
        "Incision and drainage of abscess (simple)",
        "Rạch và dẫn lưu áp xe (đơn giản)",
    ),
    (
        ("suture", "laceration repair", "wound repair", "khâu vết thương", "khâu da"),
        "12001",
        "Simple repair of superficial wound (suture)",
        "Khâu vết thương nông đơn giản",
    ),
    (
        ("venipuncture", "blood draw", "phlebotomy", "lấy máu tĩnh mạch",
         "lấy máu xét nghiệm"),
        "36415",
        "Collection of venous blood by venipuncture",
        "Lấy máu tĩnh mạch để xét nghiệm",
    ),
)


def _note_text(note: Any) -> str:
    """Coerce a note (str | :class:`~clara_ml.scribe.generator.Note` | None) to text."""

    if note is None:
        return ""
    if isinstance(note, str):
        return note
    sections = getattr(note, "sections", None)
    if isinstance(sections, dict):
        return "\n".join(str(v) for v in sections.values())
    return str(note)


def _match_spans(text: str, keywords: Iterable[str]) -> list[str]:
    """Return the deduped justifying text span(s) for any matched keyword.

    Matching is word-boundary aware: a keyword only matches when the characters
    immediately around it are non-alphanumeric (or string edges), so short tokens
    like ``"ho"`` (VN cough) or ``"hen"`` (VN asthma) never match inside a larger
    word (e.g. "shows", "comprehensive"). Each span is sliced from the ORIGINAL
    text (preserving its casing) so it is a faithful pointer to what was
    documented (Req 14.2).
    """

    lowered = text.lower()
    out: list[str] = []
    seen: set[str] = set()
    for kw in keywords:
        start = 0
        while True:
            idx = lowered.find(kw, start)
            if idx == -1:
                break
            end = idx + len(kw)
            before_ok = idx == 0 or not _is_word_char(lowered[idx - 1])
            after_ok = end >= len(lowered) or not _is_word_char(lowered[end])
            if before_ok and after_ok:
                span = text[idx:end].strip()
                key = span.lower()
                if span and key not in seen:
                    seen.add(key)
                    out.append(span)
                break
            start = idx + 1
    return out


def _is_word_char(char: str) -> bool:
    """True for alphanumeric (incl. Vietnamese diacritics) or underscore."""

    return char.isalnum() or char == "_"


@dataclass(frozen=True, slots=True)
class _EmSignals:
    """Detected MDM + documentation-breadth signals with their justifying spans."""

    problems: list[str]
    chronic: list[str]
    prescription: list[str]
    data: list[str]
    high_risk: list[str]
    history_breadth: list[str]
    exam_breadth: list[str]
    word_count: int

    @property
    def has_documentation(self) -> bool:
        return bool(
            self.problems
            or self.prescription
            or self.data
            or self.high_risk
            or self.history_breadth
            or self.exam_breadth
        )


def _extraction_surfaces(extraction: Any, attr: str) -> list[str]:
    """Read ``[item.surface ...]`` from a duck-typed StructuredExtraction, safely."""

    items = getattr(extraction, attr, None) or []
    out: list[str] = []
    for item in items:
        surface = str(getattr(item, "surface", "") or "").strip()
        if surface:
            out.append(surface)
    return out


def _detect_em_signals(text: str, extraction: Any = None) -> _EmSignals:
    """Extract MDM + breadth signals from the note text (+ optional extraction)."""

    chronic = _match_spans(text, _CHRONIC_PROBLEM_KEYWORDS)
    acute = _match_spans(text, _ACUTE_PROBLEM_KEYWORDS)
    prescription = _match_spans(text, _PRESCRIPTION_CUES)
    data = _match_spans(text, _DATA_CUES)
    high_risk = _match_spans(text, _HIGH_RISK_CUES)
    history_breadth = _match_spans(text, _HISTORY_BREADTH_CUES)
    exam_breadth = _match_spans(text, _EXAM_BREADTH_CUES)

    # Distinct documented problems = chronic ∪ acute keyword hits, plus any
    # structured-extraction problems/medications (provenance-linked evidence).
    problem_surfaces: list[str] = list(dict.fromkeys(chronic + acute))
    if extraction is not None:
        for surface in _extraction_surfaces(extraction, "problems"):
            if surface.lower() not in {p.lower() for p in problem_surfaces}:
                problem_surfaces.append(surface)
        # An extracted medication is prescription-drug management evidence.
        med_surfaces = _extraction_surfaces(extraction, "medications")
        for surface in med_surfaces:
            if surface.lower() not in {p.lower() for p in prescription}:
                prescription.append(surface)

    return _EmSignals(
        problems=problem_surfaces,
        chronic=chronic,
        prescription=prescription,
        data=data,
        high_risk=high_risk,
        history_breadth=history_breadth,
        exam_breadth=exam_breadth,
        word_count=len(text.split()),
    )


def _defensible_level_from_signals(sig: _EmSignals) -> int:
    """Highest E/M level the MDM evidence DEFENSIBLY supports (the anti-upcode ceiling)."""

    problem_count = len(sig.problems)
    has_chronic = bool(sig.chronic)

    level = 1
    if sig.has_documentation:
        level = 2
    # Low complexity: ≥2 problems, a chronic condition, or data reviewed.
    if problem_count >= 2 or has_chronic or sig.data:
        level = max(level, 3)
    # Moderate complexity: prescription-drug management, a chronic problem with
    # data workup, or ≥3 distinct problems.
    if sig.prescription or (has_chronic and sig.data) or problem_count >= 3:
        level = max(level, 4)
    # High complexity: high-risk markers AND at least one documented problem
    # (risk alone, with nothing else documented, is not defensibly level 5).
    if sig.high_risk and (problem_count >= 1 or has_chronic):
        level = 5
    return level


def _naive_level_from_signals(sig: _EmSignals) -> int:
    """A deliberately LESS conservative estimate keyed on gameable breadth axes.

    This models the over-coding tendency `suggest_em_cpt` must defend against:
    sheer history/exam verbosity and note length inflate it, but it is then
    clamped to the defensible ceiling so the suggestion never upcodes (Req 14.4).
    """

    naive = 2
    if sig.history_breadth:
        naive += 1
    if sig.exam_breadth:
        naive += 1
    if sig.word_count >= 60:
        naive += 1
    return min(naive, 5)


# Seam: given normalized meds, return interaction advisory strings.
InteractionFn = Callable[[Sequence[MedSuggestion]], list[str]]


def _default_interactions(meds: Sequence[MedSuggestion]) -> list[str]:
    """Surface DDI advisories by REUSING the CareGuard/DDI analysis path.

    Delegates to ``agents.careguard.run_careguard_analyze`` (the same local DDI
    rule set CareGuard uses) rather than reinventing an interaction table. Runs
    with external DDI lookups disabled so note-time coding stays fast and
    network-free, and is fully non-blocking: any failure degrades to no
    advisories — it never raises and never blocks note generation
    (Requirement 7.3).
    """

    names = [m.normalized_name or m.surface for m in meds if (m.normalized_name or m.surface)]
    if len(names) < 2:
        return []
    try:
        from clara_ml.agents.careguard import run_careguard_analyze

        analysis = run_careguard_analyze(
            {"medications": names, "external_ddi_enabled": False}
        )
    except Exception as exc:  # noqa: BLE001 - advisory must never block note gen
        logger.warning("coding_ddi_unavailable err=%s", exc.__class__.__name__)
        return []

    out: list[str] = []
    for alert in analysis.get("ddi_alerts", []) or []:
        if not isinstance(alert, dict) or alert.get("type") != "drug_drug":
            continue
        message = str(alert.get("message", "")).strip()
        if message and message not in out:
            out.append(message)
    return out


class CodingAssistant:
    """Produce advisory ICD + medication + interaction suggestions for a note."""

    def __init__(
        self,
        *,
        linker: Any | None = None,
        interaction_fn: InteractionFn | None = None,
        em_cpt_enabled: bool | None = None,
    ) -> None:
        self._linker = linker  # injectable; built lazily (lexicon-only) if None
        self._interaction_fn = interaction_fn or _default_interactions
        # R14 gate (default off ⇒ exactly Req 7 behavior). Injectable for tests.
        self._em_cpt_enabled = (
            bool(settings.rag_scribe_em_cpt_coding_enabled)
            if em_cpt_enabled is None
            else bool(em_cpt_enabled)
        )

    @property
    def em_cpt_enabled(self) -> bool:
        return self._em_cpt_enabled

    def _get_linker(self) -> Any | None:
        if self._linker is not None:
            return self._linker
        try:
            from clara_ml.rag.normalize.entity_linker import EntityLinker
            from clara_ml.rag.normalize.umls_client import UmlsClient

            # Lexicon-only (no network) for fast, deterministic note-time coding.
            self._linker = EntityLinker(UmlsClient(), max_network_lookups=0)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("coding_linker_unavailable err=%s", exc.__class__.__name__)
            self._linker = None
        return self._linker

    def suggest(self, text: str, *, lang: str = "vi", extraction: Any = None) -> CodingResult:
        clean = (text or "").strip()
        if not clean:
            return CodingResult()

        icd = self._suggest_icd(clean)
        meds = self._suggest_medications(clean, lang=lang)
        interactions = list(self._interaction_fn(meds))
        # Additive R14 pass: inert (empty) unless RAG_SCRIBE_EM_CPT_CODING_ENABLED.
        em_cpt = self.suggest_em_cpt(clean, lang=lang, extraction=extraction)
        return CodingResult(
            icd=icd,
            medications=meds,
            interactions=interactions,
            advisory=True,
            em_cpt=em_cpt,
        )

    def defensible_em_level(self, note: Any, *, extraction: Any = None) -> int:
        """Highest E/M visit level the documented evidence DEFENSIBLY supports.

        This is the anti-upcoding ceiling (Req 14.4): :meth:`suggest_em_cpt` never
        suggests a level above it. It is derived from Medical-Decision-Making
        evidence (documented problems, prescription-drug management, data
        reviewed, risk) — the axes that resist boilerplate inflation — optionally
        strengthened by the shared structured ``extraction`` (Req 13). Returns a
        level in ``1..5``; ``1`` when essentially nothing is documented.
        """

        text = _note_text(note)
        signals = _detect_em_signals(text, extraction)
        return _defensible_level_from_signals(signals)

    def suggest_em_cpt(
        self, note: Any, *, lang: str = "vi", extraction: Any = None
    ) -> list[EmCptSuggestion]:
        """Advisory E/M visit-level + CPT/procedure suggestions for a note (Req 14).

        Every suggestion carries justifying text span(s) (Req 14.2), is advisory
        and ``selected=False`` (Req 14.3/14.5), and is bilingual (Req 14.6). The
        suggested E/M level is clamped to :meth:`defensible_em_level` so it NEVER
        exceeds the defensible ceiling (anti-upcoding, Req 14.4). Inert (returns
        ``[]``) when ``RAG_SCRIBE_EM_CPT_CODING_ENABLED`` is off (Req 14.1) or the
        note is empty.
        """

        if not self._em_cpt_enabled:
            return []
        text = _note_text(note).strip()
        if not text:
            return []

        signals = _detect_em_signals(text, extraction)
        out: list[EmCptSuggestion] = []

        em = self._build_em_suggestion(signals)
        if em is not None:
            out.append(em)
        out.extend(self._build_cpt_suggestions(text))
        return out

    @staticmethod
    def _build_em_suggestion(signals: _EmSignals) -> EmCptSuggestion | None:
        """Build the single E/M suggestion, never above the defensible ceiling."""

        if not signals.has_documentation:
            return None  # nothing documented ⇒ no E/M suggestion (no fabrication)

        defensible = _defensible_level_from_signals(signals)
        naive = _naive_level_from_signals(signals)
        # Anti-upcoding (Req 14.4): suggest exactly the level the documented
        # medical decision-making DEFENSIBLY supports — never higher. A naive
        # heuristic keyed on narrative breadth/length (``naive``) may rate the
        # visit higher; we deliberately do NOT follow it past the defensible
        # ceiling, so the suggested level is always the defensible level.
        level = defensible

        # Justifying spans = the MDM/breadth evidence supporting the level. Every
        # suggestion must carry at least one span (Req 14.2).
        spans: list[str] = []
        for group in (
            signals.problems,
            signals.prescription,
            signals.data,
            signals.high_risk,
            signals.history_breadth,
            signals.exam_breadth,
        ):
            for span in group:
                if span not in spans:
                    spans.append(span)
        if not spans:
            return None

        upcode_note = ""
        if naive > defensible:
            upcode_note = (
                f" Breadth alone suggested level {naive}, but the documented "
                f"medical decision-making defensibly supports only level {defensible} "
                f"(anti-upcoding)."
            )
        rationale = (
            f"Suggested E/M level {level} from documented evidence "
            f"({len(signals.problems)} problem(s), "
            f"{'prescription management, ' if signals.prescription else ''}"
            f"{'data reviewed, ' if signals.data else ''}"
            f"{'high-risk factors, ' if signals.high_risk else ''}"
            f"defensible ceiling level {defensible})."
            + upcode_note
        )
        return EmCptSuggestion(
            code=_EM_CODE_BY_LEVEL[level],
            kind="E/M",
            system="E/M",
            display=_EM_DISPLAY_EN[level],
            display_vi=_EM_DISPLAY_VI[level],
            level=level,
            spans=spans,
            rationale=rationale.strip(),
            selected=False,
            status="advisory",
        )

    @staticmethod
    def _build_cpt_suggestions(text: str) -> list[EmCptSuggestion]:
        """Detect documented procedures and emit one advisory CPT each (Req 14.2)."""

        out: list[EmCptSuggestion] = []
        seen_codes: set[str] = set()
        for keywords, code, display_en, display_vi in _CPT_PROCEDURES:
            spans = _match_spans(text, keywords)
            if not spans or code in seen_codes:
                continue
            seen_codes.add(code)
            out.append(
                EmCptSuggestion(
                    code=code,
                    kind="CPT",
                    system="CPT",
                    display=display_en,
                    display_vi=display_vi,
                    level=None,
                    spans=spans,
                    rationale=f"Procedure documented: {', '.join(spans)}.",
                    selected=False,
                    status="advisory",
                )
            )
        return out

    @staticmethod
    def _suggest_icd(text: str) -> list[CodeSuggestion]:
        lowered = text.lower()
        out: list[CodeSuggestion] = []
        seen: set[str] = set()
        for keyword, code, desc in _ICD_KEYWORDS:
            if keyword in lowered and code not in seen:
                seen.add(code)
                out.append(
                    CodeSuggestion(code=code, system="ICD-10", description=desc, span=keyword)
                )
        return out

    def _suggest_medications(self, text: str, *, lang: str) -> list[MedSuggestion]:
        linker = self._get_linker()
        if linker is None:
            return []
        try:
            entities = list(linker.link(text, lang=lang) or [])
        except Exception as exc:  # noqa: BLE001 - total
            logger.warning("coding_link_failed err=%s", exc.__class__.__name__)
            return []
        out: list[MedSuggestion] = []
        seen: set[str] = set()
        for ent in entities:
            rxcui = str(getattr(ent, "rxcui", "") or "")
            name = str(getattr(ent, "canonical_name", "") or "")
            surface = name
            syns = getattr(ent, "synonyms", None) or []
            for syn in syns:
                if isinstance(syn, dict) and syn.get("kind") == "mention" and syn.get("name"):
                    surface = str(syn["name"])
                    break
            key = rxcui or name.lower()
            if key and key not in seen:
                seen.add(key)
                out.append(MedSuggestion(surface=surface, normalized_name=name, rxcui=rxcui))
        return out
