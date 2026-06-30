"""Unit (example-based) tests for the MedicationReconciler (Component F).

Feature: personal-health-record — Task 5.1

These complement the property-based conservation test (Property 8, task 5.2) with
concrete examples and edge cases for ``reconcile`` and ``find_allergy_conflicts``:
same-RXCUI collapse across stores, uncoded grouping by normalized name, distinct
keying for uncoded+unnamed items, input immutability, and conflict matching rules.
"""

from __future__ import annotations

import copy

from clara_api.phr.reconciler import (
    ReconciledMedication,
    ReconciliationResult,
    find_allergy_conflicts,
    reconcile,
)


def test_same_rxcui_collapses_phr_and_cabinet_into_one_group() -> None:
    phr_meds = [{"id": "p0", "rx_cui": "161", "normalized_name": "paracetamol", "name": "Panadol"}]
    cabinet_items = [
        {"id": "c0", "rx_cui": "161", "normalized_name": "paracetamol", "drug_name": "Hapacol"}
    ]

    result = reconcile(phr_meds, cabinet_items)

    assert len(result.medications) == 1
    med = result.medications[0]
    assert med.rx_cui == "161"
    assert med.key == "rxcui:161"
    assert med.sources == {"phr": ["p0"], "cabinet": ["c0"]}


def test_distinct_rxcuis_stay_separate() -> None:
    phr_meds = [
        {"id": "p0", "rx_cui": "161", "normalized_name": "paracetamol", "name": "Panadol"},
        {"id": "p1", "rx_cui": "1191", "normalized_name": "aspirin", "name": "Aspirin"},
    ]

    result = reconcile(phr_meds, [])

    keys = {m.key for m in result.medications}
    assert keys == {"rxcui:161", "rxcui:1191"}


def test_uncoded_items_group_by_normalized_name() -> None:
    phr_meds = [{"id": "p0", "rx_cui": "", "normalized_name": "vitamin c", "name": "Vit C"}]
    cabinet_items = [
        {"id": "c0", "rx_cui": "", "normalized_name": "Vitamin C", "drug_name": "Vitamin C 500"}
    ]

    result = reconcile(phr_meds, cabinet_items)

    # Normalized name is lower-cased into the key, so both collapse together.
    assert len(result.medications) == 1
    med = result.medications[0]
    assert med.key == "name:vitamin c"
    assert med.sources == {"phr": ["p0"], "cabinet": ["c0"]}


def test_uncoded_and_unnamed_items_kept_distinct() -> None:
    phr_meds = [
        {"id": "p0", "rx_cui": "", "normalized_name": "", "name": ""},
        {"id": "p1", "rx_cui": "", "normalized_name": "", "name": ""},
    ]

    result = reconcile(phr_meds, [])

    # Conservation: nothing merged away when there is no shared key.
    assert len(result.medications) == 2
    assert {m.key for m in result.medications} == {"phr:p0", "phr:p1"}


def test_empty_rxcui_prefers_later_non_empty_rxcui_in_same_name_group() -> None:
    phr_meds = [
        {"id": "p0", "rx_cui": "", "normalized_name": "ibuprofen", "name": "Ibuprofen"},
    ]
    cabinet_items = [
        {"id": "c0", "rx_cui": "", "normalized_name": "ibuprofen", "drug_name": "Brufen"},
    ]

    result = reconcile(phr_meds, cabinet_items)

    assert len(result.medications) == 1
    assert result.medications[0].sources == {"phr": ["p0"], "cabinet": ["c0"]}


def test_inputs_are_not_mutated() -> None:
    phr_meds = [{"id": "p0", "rx_cui": "161", "normalized_name": "paracetamol", "name": "Panadol"}]
    cabinet_items = [{"id": "c0", "rx_cui": "161", "normalized_name": "paracetamol"}]
    phr_before = copy.deepcopy(phr_meds)
    cabinet_before = copy.deepcopy(cabinet_items)

    reconcile(phr_meds, cabinet_items)

    assert phr_meds == phr_before
    assert cabinet_items == cabinet_before


def test_empty_inputs_yield_empty_result() -> None:
    result = reconcile([], [])
    assert isinstance(result, ReconciliationResult)
    assert result.medications == []


def test_as_dict_shape_is_serialisable() -> None:
    result = reconcile(
        [{"id": "p0", "rx_cui": "161", "normalized_name": "paracetamol", "name": "Panadol"}],
        [{"id": "c0", "rx_cui": "161", "normalized_name": "paracetamol"}],
    )

    payload = result.as_dict()

    assert payload == {
        "medications": [
            {
                "key": "rxcui:161",
                "rx_cui": "161",
                "display_name": "Panadol",
                "normalized_name": "paracetamol",
                "sources": {"phr": ["p0"], "cabinet": ["c0"]},
            }
        ]
    }


def test_conflict_surfaced_on_rxcui_match() -> None:
    result = ReconciliationResult(
        medications=[
            ReconciledMedication(
                key="rxcui:723",
                rx_cui="723",
                display_name="Amox",
                normalized_name="amoxicillin",
                sources={"phr": ["p0"], "cabinet": []},
            )
        ]
    )
    allergies = [{"name": "Amoxicillin", "coded_substance_id": "723", "severity": "severe"}]

    conflicts = find_allergy_conflicts(result, allergies)

    assert len(conflicts) == 1
    assert conflicts[0]["match"] == "rxcui"
    assert conflicts[0]["severity"] == "severe"


def test_conflict_surfaced_on_name_match() -> None:
    result = reconcile(
        [{"id": "p0", "rx_cui": "723", "normalized_name": "amoxicillin", "name": "Amox"}], []
    )
    allergies = [{"name": "Amoxicillin", "substance": "amoxicillin", "severity": "moderate"}]

    conflicts = find_allergy_conflicts(result, allergies)

    assert len(conflicts) == 1
    assert conflicts[0]["match"] == "name"
    assert conflicts[0]["medication"] == "Amox"


def test_no_conflict_when_unrelated() -> None:
    result = reconcile(
        [{"id": "p0", "rx_cui": "161", "normalized_name": "paracetamol", "name": "Panadol"}], []
    )
    allergies = [{"name": "Peanut", "substance": "peanut", "severity": "mild"}]

    assert find_allergy_conflicts(result, allergies) == []
