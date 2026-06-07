"""Clara Scribe note-template registry (task 0.4, Requirement 6).

Pure data: a template declares an ordered list of section keys. The note
generator (later wave) guarantees its output object has exactly these keys, so
the structure is deterministic regardless of transcript content (Requirement
6.2/6.3). Importing this module opens no socket and touches no database.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Template", "TEMPLATES", "DEFAULT_TEMPLATE_ID", "get_template", "list_templates"]

DEFAULT_TEMPLATE_ID = "soap"


@dataclass(frozen=True, slots=True)
class Template:
    """A clinical-note template: stable id + display name + ordered section keys."""

    id: str
    display_name: str
    section_keys: list[str] = field(default_factory=list)
    language: str = "en"


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


def get_template(template_id: str | None) -> Template | None:
    """Return the :class:`Template` for ``template_id`` (or ``None`` if unknown)."""

    if not template_id:
        return None
    return TEMPLATES.get(str(template_id).strip())


def list_templates() -> list[Template]:
    """Return all registered templates (order-preserving)."""

    return list(_TEMPLATE_LIST)
