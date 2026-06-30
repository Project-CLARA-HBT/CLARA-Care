"""Validation + data-sanity for PHR entries (Component M, Req 15) and the coding
helpers' acceptance domains (Components D/C).

All checks raise :class:`PhrValidationError` with a descriptive, Vietnamese-first
bilingual message naming the offending field/value; the endpoint layer maps this
to HTTP ``422`` (Correctness Property 5). The validator also assigns/verifies
entry IDs server-side (Req 15.3) and never trusts client-supplied IDs.
"""

from __future__ import annotations

import uuid
from datetime import date

from clara_api.phr.coding import code_allergy_substance, code_condition
from clara_api.phr.normalizer import SUPPORTED_DOSE_UNITS

ALLOWED_SEVERITIES: frozenset[str] = frozenset({"mild", "moderate", "severe", "unknown"})
ALLOWED_CONDITION_STATUSES: frozenset[str] = frozenset(
    {"active", "resolved", "monitoring", "unknown"}
)

# Observation units that require a numeric value (Req 10.3).
NUMERIC_OBSERVATION_UNITS: frozenset[str] = frozenset(
    {"mg/dl", "mmol/l", "mmhg", "bpm", "%", "kg", "cm", "/min", "g/dl", "iu/l", "u/l"}
)

# Field length ceilings (Req 15.5). Mirrors the pydantic schema constraints so the
# pure-logic path and the request-schema path agree.
MAX_NAME_LEN = 160
MAX_NOTE_LEN = 500
MAX_TEXT_LEN = 200


class PhrValidationError(ValueError):
    """Raised when an entry/field violates a data-sanity rule (Req 15)."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def _today() -> date:
    return date.today()


def _check_length(value: object, field: str, limit: int) -> None:
    """Reject an over-long string field (Req 15.5)."""

    text = str(value or "")
    if len(text) > limit:
        raise PhrValidationError(
            field,
            (
                f"Giá trị quá dài (tối đa {limit} ký tự) / "
                f"value too long (max {limit} characters)"
            ),
        )


def assign_entry_id(existing_id: str | None = None) -> str:
    """Assign/verify a server-owned entry id (Req 15.3).

    Client-supplied ids are never trusted: a fresh ``srv_`` id is always minted.
    """

    return f"srv_{uuid.uuid4().hex[:24]}"


def _reject_future_date(value: date | None, field: str) -> None:
    if value is not None and value > _today():
        raise PhrValidationError(
            field,
            f"Ngày không được ở tương lai / date must not be in the future ({value.isoformat()})",
        )


def validate_date_of_birth(value: date | None) -> None:
    """Reject a future date of birth (Req 15.1)."""

    _reject_future_date(value, "date_of_birth")


def validate_medication(entry: dict, *, assign_id: bool = True) -> dict:
    """Validate + normalize a medication entry's domain fields (Req 3.1, 3.5, 15)."""

    out = dict(entry)
    if assign_id:
        out["id"] = assign_entry_id(out.get("id"))

    name = str(out.get("name") or "").strip()
    if not name:
        raise PhrValidationError("name", "Tên thuốc là bắt buộc / medication name is required")
    if len(name) > MAX_NAME_LEN:
        raise PhrValidationError("name", "Tên thuốc quá dài / medication name too long")

    dose_unit = str(out.get("dose_unit") or "").strip()
    if dose_unit and dose_unit.lower() not in SUPPORTED_DOSE_UNITS:
        raise PhrValidationError(
            "dose_unit",
            (
                f"Đơn vị liều không hợp lệ / unsupported dose unit: '{dose_unit}'. "
                f"Hỗ trợ / supported: {sorted(SUPPORTED_DOSE_UNITS)}"
            ),
        )

    dose_amount = out.get("dose_amount")
    if dose_amount is not None:
        try:
            dose_value = float(dose_amount)
        except (TypeError, ValueError) as exc:
            raise PhrValidationError(
                "dose_amount", "Liều phải là số / dose amount must be numeric"
            ) from exc
        if dose_value < 0:
            raise PhrValidationError(
                "dose_amount", "Liều không được âm / dose amount must be non-negative"
            )

    started_on = out.get("started_on")
    _reject_future_date(_coerce_date(started_on, "started_on"), "started_on")
    _check_length(out.get("route"), "route", MAX_TEXT_LEN)
    _check_length(out.get("frequency"), "frequency", MAX_TEXT_LEN)
    _check_length(out.get("note"), "note", MAX_NOTE_LEN)
    return out


def validate_allergy(entry: dict, *, assign_id: bool = True) -> dict:
    """Validate an allergy entry and offer coding (Req 4.1, 4.2, 4.4, 4.5)."""

    out = dict(entry)
    if assign_id:
        out["id"] = assign_entry_id(out.get("id"))

    name = str(out.get("name") or "").strip()
    if not name:
        raise PhrValidationError("name", "Tên dị nguyên là bắt buộc / allergy name is required")
    _check_length(name, "name", MAX_NAME_LEN)
    _check_length(out.get("reaction"), "reaction", MAX_TEXT_LEN)
    _check_length(out.get("note"), "note", MAX_NOTE_LEN)

    severity = str(out.get("severity") or "unknown").strip().lower()
    if severity not in ALLOWED_SEVERITIES:
        raise PhrValidationError(
            "severity",
            (
                f"Mức độ không hợp lệ / invalid severity: '{severity}'. "
                f"Hỗ trợ / allowed: {sorted(ALLOWED_SEVERITIES)}"
            ),
        )
    out["severity"] = severity

    # Offer coding from the free-text substance/name; never block on it (Req 4.4).
    substance_input = str(out.get("substance") or name)
    substance, coded_id, is_coded = code_allergy_substance(substance_input)
    out["substance"] = substance or substance_input.strip().lower()
    out["coded_substance_id"] = coded_id
    out["is_coded"] = is_coded
    return out


def validate_condition(entry: dict, *, assign_id: bool = True) -> dict:
    """Validate a condition entry and offer coding (Req 5.1–5.4, 15.2)."""

    out = dict(entry)
    if assign_id:
        out["id"] = assign_entry_id(out.get("id"))

    name = str(out.get("name") or "").strip()
    if not name:
        raise PhrValidationError("name", "Tên bệnh là bắt buộc / condition name is required")
    _check_length(name, "name", MAX_NAME_LEN)
    _check_length(out.get("note"), "note", MAX_NOTE_LEN)

    status = str(out.get("status") or "unknown").strip().lower()
    if status not in ALLOWED_CONDITION_STATUSES:
        raise PhrValidationError(
            "status",
            (
                f"Trạng thái không hợp lệ / invalid clinical status: '{status}'. "
                f"Hỗ trợ / allowed: {sorted(ALLOWED_CONDITION_STATUSES)}"
            ),
        )
    out["status"] = status

    _reject_future_date(_coerce_date(out.get("diagnosed_on"), "diagnosed_on"), "diagnosed_on")

    icd10, snomed, is_coded = code_condition(name)
    # Respect explicit codes already on the entry; otherwise offer the lookup.
    out["icd10_code"] = str(out.get("icd10_code") or icd10)
    out["snomed_code"] = str(out.get("snomed_code") or snomed)
    out["is_coded"] = bool(out["icd10_code"] or out["snomed_code"] or is_coded)
    return out


def validate_observation(entry: dict, *, assign_id: bool = True) -> dict:
    """Validate a structured observation (Req 10.1–10.3, 15.2)."""

    out = dict(entry)
    if assign_id:
        out["entry_id"] = assign_entry_id(out.get("entry_id"))

    name = str(out.get("name") or "").strip()
    if not name:
        raise PhrValidationError("name", "Tên chỉ số là bắt buộc / observation name is required")
    _check_length(name, "name", MAX_NAME_LEN)
    _check_length(out.get("unit"), "unit", MAX_TEXT_LEN)
    _check_length(out.get("value"), "value", MAX_TEXT_LEN)

    unit = str(out.get("unit") or "").strip()
    value = out.get("value")
    if unit and unit.lower() in NUMERIC_OBSERVATION_UNITS:
        if not _is_numeric(value):
            raise PhrValidationError(
                "value",
                (
                    f"Giá trị phải là số cho đơn vị / value must be numeric for unit '{unit}': "
                    f"'{value}'"
                ),
            )

    _reject_future_date(_coerce_date(out.get("observed_on"), "observed_on"), "observed_on")
    return out


def _is_numeric(value: object) -> bool:
    if value is None:
        return False
    try:
        float(str(value).strip())
    except (TypeError, ValueError):
        return False
    return True


def _coerce_date(value: object, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise PhrValidationError(field, f"Ngày không hợp lệ / invalid date: '{value}'") from exc
