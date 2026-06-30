"""Property + unit tests for the PHR enhanced pure-logic services.

Feature: personal-health-record
    Property 2 — RXCUI normalization soundness
    Property 3 — Duplicate detection (dedup)
    Property 4 — Coding soundness
    Property 5 — Validation rejection
    Property 6 — Provenance integrity
    Property 7 — Decision-support output is hedged
    Property 8 — Reconciliation conservation
    Property 9 — Allergy-aware conflict surfacing
    Property 15 — FHIR export round-trip and shape
    Property 17 — Emergency-card projection
    Property 18 — Reminder decision logic
    Property 19 — Completeness monotonicity
    Property 20 — PII-free telemetry

These services are deliberately free of HTTP/DB concerns, so they are exercised
in-process with hypothesis, mirroring the existing ``services/api/tests`` style.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_api.phr.coding import code_allergy_substance, code_condition
from clara_api.phr.completeness import completeness_telemetry, score_completeness
from clara_api.phr.emergency_card import EMERGENCY_CARD_FIELDS, build_emergency_card
from clara_api.phr.fhir_export import from_bundle, to_bundle
from clara_api.phr.normalizer import (
    SUPPORTED_DOSE_UNITS,
    flag_duplicate_medications,
)
from clara_api.phr.provenance import (
    HEDGE_TEXT_EN,
    HEDGE_TEXT_VI,
    hedge_text_bilingual,
    tag_provenance,
)
from clara_api.phr.reconciler import find_allergy_conflicts, reconcile
from clara_api.phr.reminders import evaluate_reminder
from clara_api.phr.validator import (
    PhrValidationError,
    validate_allergy,
    validate_condition,
    validate_medication,
    validate_observation,
)

_NAME_ALPHABET = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" "),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Property 3 — duplicate detection
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(rxcuis=st.lists(st.sampled_from(["", "161", "5640", "1191"]), min_size=0, max_size=8))
def test_property3_duplicate_detection(rxcuis: list[str]) -> None:
    meds = [{"id": f"m{i}", "rx_cui": rx} for i, rx in enumerate(rxcuis)]
    flagged = flag_duplicate_medications(meds)

    # Group canonical (first) id per non-empty rxcui.
    first_id_by_rxcui: dict[str, str] = {}
    for i, rx in enumerate(rxcuis):
        if rx and rx not in first_id_by_rxcui:
            first_id_by_rxcui[rx] = f"m{i}"

    for i, item in enumerate(flagged):
        rx = rxcuis[i]
        if not rx:
            assert item["duplicate_of"] is None
        elif first_id_by_rxcui[rx] == f"m{i}":
            assert item["duplicate_of"] is None  # canonical
        else:
            assert item["duplicate_of"] == first_id_by_rxcui[rx]


def test_property3_input_not_mutated() -> None:
    meds = [{"id": "a", "rx_cui": "161"}, {"id": "b", "rx_cui": "161"}]
    flag_duplicate_medications(meds)
    assert "duplicate_of" not in meds[0]
    assert "duplicate_of" not in meds[1]


# ---------------------------------------------------------------------------
# Property 4 — coding soundness
# ---------------------------------------------------------------------------


def test_property4_known_allergy_is_coded() -> None:
    substance, coded_id, is_coded = code_allergy_substance("Penicillin")
    assert is_coded is True
    assert coded_id == "7980"


@settings(max_examples=100, deadline=None)
@given(name=_NAME_ALPHABET)
def test_property4_unknown_allergy_is_uncoded(name: str) -> None:
    key = name.strip().lower()
    from clara_api.phr.coding import ALLERGY_SUBSTANCE_CODES

    if key in ALLERGY_SUBSTANCE_CODES:
        return  # known entry; covered by the example test above
    substance, coded_id, is_coded = code_allergy_substance(name)
    assert is_coded is False
    assert coded_id == ""


def test_property4_known_condition_is_coded() -> None:
    icd10, snomed, is_coded = code_condition("Hypertension")
    assert is_coded is True
    assert icd10 == "I10"


# ---------------------------------------------------------------------------
# Property 5 — validation rejection
# ---------------------------------------------------------------------------


def test_property5_future_diagnosed_on_rejected() -> None:
    future = (date.today() + timedelta(days=5)).isoformat()
    with pytest.raises(PhrValidationError) as exc:
        validate_condition({"name": "x", "status": "active", "diagnosed_on": future})
    assert exc.value.field == "diagnosed_on"


def test_property5_bad_dose_unit_rejected() -> None:
    with pytest.raises(PhrValidationError) as exc:
        validate_medication({"name": "panadol", "dose_unit": "spoonful"})
    assert exc.value.field == "dose_unit"


def test_property5_bad_severity_rejected() -> None:
    with pytest.raises(PhrValidationError) as exc:
        validate_allergy({"name": "penicillin", "severity": "deadly"})
    assert exc.value.field == "severity"


def test_property5_bad_status_rejected() -> None:
    with pytest.raises(PhrValidationError) as exc:
        validate_condition({"name": "x", "status": "chronic"})
    assert exc.value.field == "status"


def test_property5_non_numeric_observation_rejected() -> None:
    with pytest.raises(PhrValidationError) as exc:
        validate_observation({"name": "glucose", "value": "high", "unit": "mg/dL"})
    assert exc.value.field == "value"


@settings(max_examples=100, deadline=None)
@given(unit=st.sampled_from(sorted(SUPPORTED_DOSE_UNITS)))
def test_property5_supported_units_accepted(unit: str) -> None:
    out = validate_medication({"name": "panadol", "dose_unit": unit})
    assert out["dose_unit"] == unit


def test_property5_overlong_name_rejected() -> None:
    from clara_api.phr.validator import MAX_NAME_LEN

    with pytest.raises(PhrValidationError) as exc:
        validate_condition({"name": "a" * (MAX_NAME_LEN + 1), "status": "active"})

    assert exc.value.field == "name"


def test_property5_overlong_note_rejected() -> None:
    from clara_api.phr.validator import MAX_NOTE_LEN

    with pytest.raises(PhrValidationError) as exc:
        validate_allergy({"name": "penicillin", "note": "x" * (MAX_NOTE_LEN + 1)})

    assert exc.value.field == "note"


# ---------------------------------------------------------------------------
# Property 6 — provenance integrity
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(source=st.sampled_from(["self-declared", "ocr", "imported"]))
def test_property6_provenance_from_write_path(source: str) -> None:
    tagged = tag_provenance({"name": "x"}, information_source=source)
    assert tagged["information_source"] == source
    assert tagged["verification_status"]  # always present


def test_property6_self_declared_is_unconfirmed() -> None:
    tagged = tag_provenance({"name": "x", "verification_status": "confirmed"})
    assert tagged["verification_status"] == "unconfirmed"


def test_property6_invalid_source_rejected() -> None:
    with pytest.raises(ValueError):
        tag_provenance({"name": "x"}, information_source="forged")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Property 7 — hedge present
# ---------------------------------------------------------------------------


def test_property7_hedge_is_bilingual_and_clinician_review() -> None:
    text = hedge_text_bilingual()
    assert HEDGE_TEXT_VI in text
    assert HEDGE_TEXT_EN in text
    assert "bác sĩ" in text.lower() or "clinician" in text.lower()


# ---------------------------------------------------------------------------
# Property 8 — reconciliation conservation
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    phr_rx=st.lists(st.sampled_from(["", "161", "5640"]), max_size=6),
    cab_rx=st.lists(st.sampled_from(["", "161", "1191"]), max_size=6),
)
def test_property8_reconciliation_conservation(phr_rx: list[str], cab_rx: list[str]) -> None:
    phr_meds = [
        {"id": f"p{i}", "rx_cui": rx, "normalized_name": f"n{i}", "name": f"P{i}"}
        for i, rx in enumerate(phr_rx)
    ]
    cab_items = [
        {"id": f"c{i}", "rx_cui": rx, "normalized_name": f"cn{i}", "drug_name": f"C{i}"}
        for i, rx in enumerate(cab_rx)
    ]
    result = reconcile(phr_meds, cab_items)

    # Every input id appears in exactly one reconciled group's source refs.
    all_phr_ids: list[str] = []
    all_cab_ids: list[str] = []
    for med in result.medications:
        all_phr_ids.extend(med.sources["phr"])
        all_cab_ids.extend(med.sources["cabinet"])
    assert sorted(all_phr_ids) == sorted(f"p{i}" for i in range(len(phr_rx)))
    assert sorted(all_cab_ids) == sorted(f"c{i}" for i in range(len(cab_rx)))

    # Inputs are not mutated.
    assert all("duplicate_of" not in m for m in phr_meds)

    # Same non-empty rxcui collapses into one group.
    for rx in {*phr_rx, *cab_rx} - {""}:
        groups = [m for m in result.medications if m.rx_cui == rx]
        assert len(groups) <= 1


# ---------------------------------------------------------------------------
# Property 9 — allergy-aware conflict surfacing
# ---------------------------------------------------------------------------


def test_property9_conflict_surfaced_on_match() -> None:
    phr_meds = [{"id": "p0", "rx_cui": "723", "normalized_name": "amoxicillin", "name": "Amox"}]
    result = reconcile(phr_meds, [])
    allergies = [{"name": "Amoxicillin", "substance": "amoxicillin", "severity": "severe"}]
    conflicts = find_allergy_conflicts(result, allergies)
    assert len(conflicts) == 1
    assert conflicts[0]["severity"] == "severe"


def test_property9_no_conflict_when_unrelated() -> None:
    phr_meds = [{"id": "p0", "rx_cui": "161", "normalized_name": "paracetamol", "name": "Panadol"}]
    result = reconcile(phr_meds, [])
    allergies = [{"name": "Peanut", "substance": "peanut", "severity": "mild"}]
    assert find_allergy_conflicts(result, allergies) == []


# ---------------------------------------------------------------------------
# Property 15 — FHIR export round-trip and shape
# ---------------------------------------------------------------------------


def _sample_record() -> dict:
    return {
        "profile": {
            "full_name": "Test User",
            "date_of_birth": "1990-01-01",
            "gender": "female",
            "blood_type": "O+",
        },
        "allergies": [
            {
                "name": "Penicillin",
                "substance": "penicillin",
                "coded_substance_id": "7980",
                "severity": "moderate",
                "is_coded": True,
                "information_source": "self-declared",
                "verification_status": "unconfirmed",
            }
        ],
        "conditions": [
            {
                "name": "Hypertension",
                "status": "active",
                "icd10_code": "I10",
                "snomed_code": "38341003",
                "is_coded": True,
                "information_source": "self-declared",
                "verification_status": "unconfirmed",
            }
        ],
        "medications": [
            {
                "name": "Panadol",
                "rx_cui": "161",
                "normalized_name": "paracetamol",
                "is_normalized": True,
                "is_current": True,
                "information_source": "self-declared",
                "verification_status": "unconfirmed",
            }
        ],
        "observations": [
            {"name": "glucose", "value": "5.4", "unit": "mmol/L", "information_source": "ocr"}
        ],
    }


def test_property15_bundle_shape() -> None:
    bundle = to_bundle(_sample_record())
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Patient" in types
    assert "AllergyIntolerance" in types
    assert "Condition" in types
    assert "MedicationStatement" in types
    assert "Observation" in types


def test_property15_single_resource_is_subset() -> None:
    record = _sample_record()
    full = to_bundle(record, resource="all")
    meds_only = to_bundle(record, resource="medication")
    full_meds = [e for e in full["entry"] if e["resource"]["resourceType"] == "MedicationStatement"]
    assert meds_only["entry"] == full_meds


def test_property15_round_trip_recovers_coded_fields() -> None:
    record = _sample_record()
    recovered = from_bundle(to_bundle(record))
    assert recovered["allergies"][0]["coded_substance_id"] == "7980"
    assert recovered["conditions"][0]["icd10_code"] == "I10"
    assert recovered["medications"][0]["rx_cui"] == "161"
    assert recovered["allergies"][0]["verification_status"] == "unconfirmed"


# ---------------------------------------------------------------------------
# Property 17 — emergency-card projection
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    enabled=st.dictionaries(
        keys=st.sampled_from(list(EMERGENCY_CARD_FIELDS)),
        values=st.booleans(),
    )
)
def test_property17_field_inclusion(enabled: dict[str, bool]) -> None:
    record = _sample_record()
    card = build_emergency_card(record, enabled)
    field_to_key = {
        "allergies": "allergies",
        "current_medications": "current_medications",
        "conditions": "conditions",
        "blood_type": "blood_type",
        "emergency_contact": "emergency_contact",
    }
    for field, key in field_to_key.items():
        if enabled.get(field, True):
            assert key in card
        else:
            assert key not in card


def test_property17_empty_record_no_error() -> None:
    card = build_emergency_card({}, None)
    assert card["allergies"] == []
    assert card["current_medications"] == []
    assert "disclaimer" in card


# ---------------------------------------------------------------------------
# Property 18 — reminder decision logic
# ---------------------------------------------------------------------------


def test_property18_medication_reminder_requires_current_and_frequency() -> None:
    now = datetime(2026, 6, 16, 10, 0, 0)
    fired = evaluate_reminder(is_current=True, frequency="2x/day", scheduled_time=now, now=now)
    assert fired.fire_medication_reminder is True
    not_current = evaluate_reminder(
        is_current=False, frequency="2x/day", scheduled_time=now, now=now
    )
    assert not_current.fire_medication_reminder is False
    no_freq = evaluate_reminder(is_current=True, frequency="", scheduled_time=now, now=now)
    assert no_freq.fire_medication_reminder is False


def test_property18_refill_threshold() -> None:
    now = datetime(2026, 6, 16, 10, 0, 0)
    d = evaluate_reminder(
        is_current=True,
        frequency="1x/day",
        scheduled_time=None,
        now=now,
        remaining_supply=3,
        refill_threshold=5,
    )
    assert d.fire_refill_reminder is True
    d2 = evaluate_reminder(
        is_current=True,
        frequency="1x/day",
        scheduled_time=None,
        now=now,
        remaining_supply=10,
        refill_threshold=5,
    )
    assert d2.fire_refill_reminder is False


def test_property18_caregiver_nudge() -> None:
    now = datetime(2026, 6, 16, 10, 0, 0)
    d = evaluate_reminder(
        is_current=True,
        frequency="1x/day",
        scheduled_time=None,
        now=now,
        nudge_enabled=True,
        caregiver_share_active=True,
        dose_marked_taken=False,
        within_window=False,
    )
    assert d.notify_caregiver is True
    # Still within grace window ⇒ no nudge yet.
    d2 = evaluate_reminder(
        is_current=True,
        frequency="1x/day",
        scheduled_time=None,
        now=now,
        nudge_enabled=True,
        caregiver_share_active=True,
        dose_marked_taken=False,
        within_window=True,
    )
    assert d2.notify_caregiver is False


# ---------------------------------------------------------------------------
# Property 19 — completeness monotonicity
# ---------------------------------------------------------------------------


def test_property19_score_in_unit_interval_and_deterministic() -> None:
    record = _sample_record()
    r1 = score_completeness(record)
    r2 = score_completeness(record)
    assert r1 == r2
    assert 0.0 <= r1["score"] <= 1.0


def test_property19_adding_class_increases_score() -> None:
    base = {"profile": {}, "allergies": [], "medications": [], "conditions": []}
    before = score_completeness(base)["score"]
    base["allergies"] = [{"name": "penicillin"}]
    after = score_completeness(base)["score"]
    assert after > before


# ---------------------------------------------------------------------------
# Property 20 — PII-free telemetry
# ---------------------------------------------------------------------------


def test_property20_completeness_telemetry_is_pii_free() -> None:
    record = _sample_record()
    telemetry = completeness_telemetry(record)
    blob = repr(telemetry).lower()
    # No names, drug names, codes, or contact details leak.
    for forbidden in ("test user", "penicillin", "panadol", "hypertension", "i10", "161", "o+"):
        assert forbidden not in blob
    assert telemetry["phr_completeness_score"] >= 0.0
    assert set(telemetry).issuperset(
        {"present_classes", "missing_classes", "present_class_count", "missing_class_count"}
    )
