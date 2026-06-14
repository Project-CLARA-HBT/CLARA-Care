"""Clara Scribe note-template registry (task 0.4 + 8.1, Requirements 6 & 19).

Pure data: a template declares an ordered list of section keys. The note
generator (later wave) guarantees its output object has exactly these keys, so
the structure is deterministic regardless of transcript content (Requirement
6.2/6.3). Importing this module opens no socket and touches no database.

Wave 8 (Requirement 19) extends this **same pure-data registry** with
specialty-specific templates and clinician-defined text macros/snippets, gated
behind ``RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED`` (default off). The extension is
strictly additive:

* The base Requirement 6 set (:data:`TEMPLATES` / :data:`_TEMPLATE_LIST`) is left
  byte-for-byte unchanged, so adding a specialty template or macro never alters
  the structure or output of any existing template (Req 19.5).
* When the flag is off, :func:`get_template` / :func:`list_templates` offer
  exactly the Requirement 6 set (Req 19.1).
* When the flag is on, specialty templates become selectable through the very
  same registry functions, so the note-generation call site does not change
  (Req 19.2). A selected specialty template still yields exactly the sections it
  declares, preserving the structure-completeness guarantee (Req 19.4).
* Specialty templates and macros are Vietnamese-first and bilingual where
  applicable (Req 19.6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from clara_ml.config import settings

__all__ = [
    "Template",
    "Macro",
    "TEMPLATES",
    "SPECIALTY_TEMPLATES",
    "MACROS",
    "DEFAULT_TEMPLATE_ID",
    "get_template",
    "list_templates",
    "get_macro",
    "list_macros",
    "insert_macro",
    "expand_macros",
]

DEFAULT_TEMPLATE_ID = "soap"


@dataclass(frozen=True, slots=True)
class Template:
    """A clinical-note template: stable id + display name + ordered section keys."""

    id: str
    display_name: str
    section_keys: list[str] = field(default_factory=list)
    language: str = "en"


@dataclass(frozen=True, slots=True)
class Macro:
    """A clinician-defined text macro/snippet that can be inserted into a note.

    Pure data (Req 19.3): a stable ``id`` + display name, a ``trigger`` token the
    clinician types (e.g. ``"/timbinhthuong"``), and the ``body`` text inserted in
    its place. Macros are Vietnamese-first, bilingual where applicable (Req 19.6).
    """

    id: str
    display_name: str
    trigger: str
    body: str
    language: str = "vi"


_TEMPLATE_LIST: list[Template] = [
    Template(
        id="soap",
        display_name="SOAP note",
        section_keys=["Subjective", "Objective", "Assessment", "Plan"],
    ),
    Template(
        id="h_and_p",
        display_name="History & Physical (H&P)",
        section_keys=[
            "Chief Complaint",
            "History of Present Illness",
            "Past Medical History",
            "Medications",
            "Allergies",
            "Physical Examination",
            "Assessment",
            "Plan",
        ],
    ),
    Template(
        id="progress_note",
        display_name="Progress note",
        section_keys=["Interval History", "Examination", "Assessment", "Plan"],
    ),
    Template(
        id="referral_letter",
        display_name="Referral letter",
        section_keys=["Reason for Referral", "Clinical Summary", "Current Medications", "Request"],
    ),
    Template(
        id="vn_benh_an",
        display_name="Bệnh án (Vietnamese)",
        section_keys=[
            "Lý do khám",
            "Bệnh sử",
            "Tiền sử",
            "Khám lâm sàng",
            "Chẩn đoán",
            "Hướng xử trí",
        ],
        language="vi",
    ),
]

TEMPLATES: dict[str, Template] = {tpl.id: tpl for tpl in _TEMPLATE_LIST}

# ---------------------------------------------------------------------------
# Requirement 19 extension — specialty templates + clinician macros (flag-gated).
#
# Vietnamese-first, bilingual where applicable (Req 19.6): each section key reads
# as ``"<Tiếng Việt> (<English>)"`` so the structure serves Vietnamese clinicians
# first while remaining intelligible bilingually. These live in their OWN list so
# the base Requirement 6 registry above is never mutated (Req 19.5 isolation).
# ---------------------------------------------------------------------------

_SPECIALTY_TEMPLATE_LIST: list[Template] = [
    Template(
        id="vn_tim_mach",
        display_name="Bệnh án tim mạch (Cardiology)",
        section_keys=[
            "Lý do khám (Chief Complaint)",
            "Bệnh sử tim mạch (Cardiac History)",
            "Yếu tố nguy cơ tim mạch (Cardiovascular Risk Factors)",
            "Khám tim mạch (Cardiovascular Examination)",
            "Cận lâm sàng - ECG/Siêu âm tim (Diagnostics - ECG/Echo)",
            "Chẩn đoán (Assessment)",
            "Hướng xử trí (Plan)",
        ],
        language="vi",
    ),
    Template(
        id="vn_nhi_khoa",
        display_name="Bệnh án nhi khoa (Pediatrics)",
        section_keys=[
            "Lý do khám (Chief Complaint)",
            "Bệnh sử (History of Present Illness)",
            "Tiền sử sản khoa & tiêm chủng (Birth & Immunization History)",
            "Tăng trưởng & phát triển (Growth & Development)",
            "Khám lâm sàng (Physical Examination)",
            "Chẩn đoán (Assessment)",
            "Hướng xử trí & liều theo cân nặng (Plan & Weight-based Dosing)",
        ],
        language="vi",
    ),
    Template(
        id="vn_tam_than",
        display_name="Bệnh án tâm thần (Psychiatry)",
        section_keys=[
            "Lý do khám (Chief Complaint)",
            "Bệnh sử tâm thần (History of Present Illness)",
            "Tiền sử tâm thần & điều trị (Past Psychiatric History)",
            "Khám trạng thái tâm thần (Mental Status Examination)",
            "Đánh giá nguy cơ (Risk Assessment)",
            "Chẩn đoán (Assessment)",
            "Kế hoạch điều trị (Treatment Plan)",
        ],
        language="vi",
    ),
    Template(
        id="vn_san_phu_khoa",
        display_name="Bệnh án sản phụ khoa (OB/GYN)",
        section_keys=[
            "Lý do khám (Chief Complaint)",
            "Tiền sử sản khoa (Obstetric History)",
            "Tiền sử phụ khoa & kinh nguyệt (Gynecologic & Menstrual History)",
            "Khám sản phụ khoa (Obstetric/Gynecologic Examination)",
            "Cận lâm sàng - Siêu âm (Diagnostics - Ultrasound)",
            "Chẩn đoán (Assessment)",
            "Hướng xử trí (Plan)",
        ],
        language="vi",
    ),
]

SPECIALTY_TEMPLATES: dict[str, Template] = {tpl.id: tpl for tpl in _SPECIALTY_TEMPLATE_LIST}

_MACRO_LIST: list[Macro] = [
    Macro(
        id="tim_binh_thuong",
        display_name="Khám tim bình thường (Normal cardiac exam)",
        trigger="/timbinhthuong",
        body="Tim đều, tần số trong giới hạn bình thường, T1 T2 rõ, không nghe tiếng thổi bệnh lý.",
    ),
    Macro(
        id="phoi_binh_thuong",
        display_name="Khám phổi bình thường (Normal lung exam)",
        trigger="/phoibinhthuong",
        body="Lồng ngực cân đối, rì rào phế nang êm dịu hai bên, không nghe ran.",
    ),
    Macro(
        id="bung_binh_thuong",
        display_name="Khám bụng bình thường (Normal abdominal exam)",
        trigger="/bungbinhthuong",
        body="Bụng mềm, không chướng, ấn không đau, gan lách không sờ chạm.",
    ),
    Macro(
        id="tu_van_cai_thuoc_la",
        display_name="Tư vấn cai thuốc lá (Smoking-cessation counseling)",
        trigger="/cainghuocla",
        body=(
            "Đã tư vấn người bệnh về lợi ích của việc cai thuốc lá và các nguy cơ "
            "tim mạch, hô hấp khi tiếp tục hút thuốc."
        ),
    ),
    Macro(
        id="hen_tai_kham",
        display_name="Hẹn tái khám (Follow-up appointment)",
        trigger="/taikham",
        body="Hẹn tái khám sau 2 tuần hoặc khi có dấu hiệu bất thường.",
    ),
]

MACROS: dict[str, Macro] = {macro.id: macro for macro in _MACRO_LIST}


def _specialty_enabled(override: bool | None) -> bool:
    """Resolve the Req 19 gate: explicit override wins, else the runtime flag."""

    if override is not None:
        return bool(override)
    return bool(settings.rag_scribe_specialty_templates_enabled)


def get_template(
    template_id: str | None, *, include_specialty: bool | None = None
) -> Template | None:
    """Return the :class:`Template` for ``template_id`` (or ``None`` if unknown).

    Base Requirement 6 templates are always resolvable (unchanged behavior). A
    specialty template (Req 19) resolves only when ``RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED``
    is on (or ``include_specialty=True`` is passed explicitly), so with the flag
    off the generator offers exactly the Requirement 6 set (Req 19.1).
    """

    if not template_id:
        return None
    tid = str(template_id).strip()
    base = TEMPLATES.get(tid)
    if base is not None:
        return base
    if _specialty_enabled(include_specialty):
        return SPECIALTY_TEMPLATES.get(tid)
    return None


def list_templates(*, include_specialty: bool | None = None) -> list[Template]:
    """Return all registered templates (order-preserving).

    With the Req 19 gate off this is exactly the Requirement 6 set (Req 19.1);
    with it on the specialty templates are appended after the base set (Req 19.2).
    The returned list is always a fresh copy.
    """

    if _specialty_enabled(include_specialty):
        return list(_TEMPLATE_LIST) + list(_SPECIALTY_TEMPLATE_LIST)
    return list(_TEMPLATE_LIST)


def get_macro(macro_id: str | None, *, include_specialty: bool | None = None) -> Macro | None:
    """Return the clinician :class:`Macro` for ``macro_id`` (Req 19.3).

    Gated by ``RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED``: returns ``None`` when the
    flag is off so the flag-off surface stays exactly the Requirement 6 set.
    """

    if not macro_id:
        return None
    if not _specialty_enabled(include_specialty):
        return None
    return MACROS.get(str(macro_id).strip())


def list_macros(*, include_specialty: bool | None = None) -> list[Macro]:
    """Return all clinician macros (Req 19.3), or ``[]`` when the gate is off."""

    if not _specialty_enabled(include_specialty):
        return []
    return list(_MACRO_LIST)


def insert_macro(text: str, macro: Macro, *, index: int | None = None) -> str:
    """Return ``text`` with ``macro.body`` inserted (Req 19.3).

    Pure string transform: it produces a NEW string and never mutates a note in
    place. ``index`` chooses the insertion offset; when ``None`` the macro body is
    appended (separated by a space when the existing text is non-empty).
    """

    body = macro.body
    if index is None:
        if not text:
            return body
        sep = "" if text.endswith((" ", "\n")) else " "
        return f"{text}{sep}{body}"
    pos = max(0, min(int(index), len(text)))
    return text[:pos] + body + text[pos:]


def expand_macros(text: str, *, include_specialty: bool | None = None) -> str:
    """Replace any macro ``trigger`` tokens in ``text`` with their bodies (Req 19.3).

    Returns ``text`` unchanged when the Req 19 gate is off (no macros available),
    keeping the flag-off behavior identical to Requirement 6.
    """

    if not text or not _specialty_enabled(include_specialty):
        return text
    out = text
    # Longest triggers first so a trigger that is a prefix of another never
    # shadows it during replacement.
    for macro in sorted(_MACRO_LIST, key=lambda m: len(m.trigger), reverse=True):
        if macro.trigger and macro.trigger in out:
            out = out.replace(macro.trigger, macro.body)
    return out
