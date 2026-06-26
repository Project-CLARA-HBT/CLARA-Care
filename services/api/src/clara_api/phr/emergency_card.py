"""Emergency summary card projection (Component K, Req 13).

A pure projection of allergies, current medications, conditions, blood type, and
emergency contact, controlled by owner field-inclusion preferences
(``emergency_card_prefs_json``). A field appears iff it is enabled in the prefs;
an empty record yields empty sections without error (Req 13.1, 13.3, 13.4,
Correctness Property 17). The persistent self-declared/decision-support
disclaimer is always attached (Req 13.5).
"""

from __future__ import annotations

from typing import Any

from clara_api.phr.provenance import hedge_text_bilingual

# Emergency-card fields and their default inclusion (all on by default).
EMERGENCY_CARD_FIELDS: tuple[str, ...] = (
    "allergies",
    "current_medications",
    "conditions",
    "blood_type",
    "emergency_contact",
)

DISCLAIMER_VI = (
    "Thẻ khẩn cấp này dựa trên thông tin tự khai, chỉ hỗ trợ quyết định, "
    "không phải bệnh án điện tử và không có giá trị pháp lý."
)
DISCLAIMER_EN = (
    "This emergency card is self-declared, decision-support only, "
    "not an EMR/EHR, and not legally binding."
)


def _field_enabled(prefs: dict | None, field: str) -> bool:
    if not isinstance(prefs, dict):
        return True
    value = prefs.get(field)
    if value is None:
        return True
    return bool(value)


def build_emergency_card(record: dict, prefs: dict | None = None) -> dict[str, Any]:
    """Project the owner-controlled emergency card (Req 13.1, 13.3, 13.4)."""

    card: dict[str, Any] = {"disclaimer": {"vi": DISCLAIMER_VI, "en": DISCLAIMER_EN}}

    if _field_enabled(prefs, "allergies"):
        card["allergies"] = [
            {
                "name": a.get("name") or a.get("substance") or "",
                "severity": a.get("severity") or "unknown",
                "reaction": a.get("reaction") or "",
            }
            for a in record.get("allergies") or []
        ]

    if _field_enabled(prefs, "current_medications"):
        card["current_medications"] = [
            {"name": m.get("name") or "", "dose": m.get("dose") or ""}
            for m in record.get("medications") or []
            if m.get("is_current", True)
        ]

    if _field_enabled(prefs, "conditions"):
        card["conditions"] = [
            {"name": c.get("name") or "", "status": c.get("status") or "unknown"}
            for c in record.get("conditions") or []
        ]

    if _field_enabled(prefs, "blood_type"):
        card["blood_type"] = (record.get("profile") or {}).get("blood_type") or ""

    if _field_enabled(prefs, "emergency_contact"):
        profile = record.get("profile") or {}
        card["emergency_contact"] = {
            "name": profile.get("emergency_contact_name") or "",
            "phone": profile.get("emergency_contact_phone") or "",
        }

    card["hedge"] = hedge_text_bilingual()
    return card
