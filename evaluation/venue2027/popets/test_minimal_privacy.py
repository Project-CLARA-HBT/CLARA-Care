"""Tests for POPETS-X08_minimal_privacy (minimal future outbound disclosure).

Positive controls (must pass):
- Narrow task discloses strictly less than full EHR summary:
  Given a comprehensive EHR summary context (vitals, diagnoses, medications, labs, notes, billing),
  a narrow task (e.g. vitals-monitoring or medication-check) discloses only the minimal required
  field set and reports all remaining fields in withheld_fields.
- Purpose change narrows disclosure:
  The same task evaluated under a broad clinical purpose vs a restrictive self_care purpose
  selects a strictly narrower or disjoint minimal field set, correctly withholding fields outside
  the authorized purpose allowlist.
- Lineage-backed resolution:
  When graph lineage nodes and edges for the required task dependencies exist and are valid,
  the disclosure succeeds with status DISCLOSED and recomputation_required=False.
- Exact target contract select_fields(context, task):
  Returns a FieldSet with fields and withheld_fields accurately partitioned and deterministic.
- Deterministic JSON-serializable outputs.

Adversarial controls (must be refused / fail closed):
- Unknown graph edge forces fallback to RECOMPUTATION:
  When a task dependency requires a context node whose parent edge is missing or unknown
  in the graph (fail closed, never disclose unresolvable dependency), minimal_disclosure
  falls back to RECOMPUTATION (status=RECOMPUTATION, recomputation_required=True).
- Purpose-incompatible graph edge forces recomputation:
  When a lineage edge belongs to a different purpose, it cannot be traversed for the current
  purpose, forcing recomputation.
- Full summary disclosure refused when a minimal set exists:
  When allow_full_summary=True is attempted on a request where a minimal context set exists,
  minimal_disclosure actively refuses to disclose the full EHR summary
  (status=REFUSED, reason_code=FULL_SUMMARY_DISCLOSURE_REFUSED).
- Malformed task / purpose / context inputs fail closed with stable reason codes.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from evaluation.venue2027.popets.lineage_graph import (
    LineageGraph,
    derive_graph,
)
from evaluation.venue2027.popets.minimal_disclosure import (
    MINIMAL_DISCLOSURE_VERSION,
    REASON_FULL_SUMMARY_DISCLOSURE_REFUSED,
    REASON_INVALID_PURPOSE,
    REASON_INVALID_TASK,
    REASON_MALFORMED_CONTEXT,
    REASON_MINIMAL_DISCLOSURE_OK,
    REASON_RECOMPUTATION_REQUIRED,
    STATUS_DISCLOSED,
    STATUS_RECOMPUTATION,
    STATUS_REFUSED,
    FieldSet,
    MinimalDisclosureError,
    TaskDependency,
    minimal_disclosure,
    select_fields,
)

# ---------------------------------------------------------------------------
# Fixtures: Full EHR summary and synthetic lineage graph
# ---------------------------------------------------------------------------

SAMPLE_FULL_EHR_SUMMARY = {
    "vitals": {"bp": "120/80", "hr": 72, "temp": 98.6},
    "blood_pressure": "120/80",
    "heart_rate": 72,
    "temperature": 98.6,
    "weight": 70.5,
    "active_diagnoses": ["I10 - Essential Hypertension", "E11 - Type 2 Diabetes"],
    "medications": ["Lisinopril 10mg", "Metformin 500mg"],
    "medication_schedule": {"morning": ["Lisinopril 10mg", "Metformin 500mg"]},
    "allergies": ["Penicillin"],
    "lab_results": {"hba1c": 6.8, "creatinine": 0.9},
    "clinical_notes_summary": "Patient is clinically stable, compliance is high.",
    "billing_codes": ["99214", "83036"],
    "insurance_id": "INS-99210-XYZ",
}


@pytest.fixture
def clean_lineage_graph() -> LineageGraph:
    """Graph with valid provenance for vitals and medications."""
    disclosures = [
        # Origin roots -> summaries -> cache objects
        {
            "item_id": "summary_vitals_1",
            "created_by": "field_vitals_origin",
            "principal": "patient-1",
            "purpose": "care_summary",
            "time": 10,
            "transform": "summarize",
            "node_kind": "derived_summary",
        },
        {
            "item_id": "cache_vitals_1",
            "created_by": "summary_vitals_1",
            "principal": "patient-1",
            "purpose": "care_summary",
            "time": 12,
            "transform": "cache_store",
            "node_kind": "cache_object",
        },
        {
            "item_id": "summary_meds_1",
            "created_by": "field_meds_origin",
            "principal": "patient-1",
            "purpose": "medication_review",
            "time": 11,
            "transform": "summarize",
            "node_kind": "derived_summary",
        },
    ]
    roots = ["field_vitals_origin", "field_meds_origin"]
    return derive_graph(disclosures=disclosures, roots=roots)


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_positive_narrow_task_discloses_much_less_than_full_summary(
    clean_lineage_graph: LineageGraph,
) -> None:
    """A narrow task (e.g. vitals monitoring) discloses strictly a subset of the EHR."""
    task = TaskDependency(
        task_id="task_vitals_monitor",
        required_fields=("blood_pressure", "heart_rate"),
        expected_lineage_nodes=("cache_vitals_1",),
    )

    disclosure = minimal_disclosure(
        task_dependency=task,
        current_purpose="care_summary",
        graph=clean_lineage_graph,
        context=SAMPLE_FULL_EHR_SUMMARY,
    )

    assert disclosure.status == STATUS_DISCLOSED
    assert disclosure.reason_code == REASON_MINIMAL_DISCLOSURE_OK
    assert disclosure.recomputation_required is False
    assert set(disclosure.disclosed_fields) == {"blood_pressure", "heart_rate"}

    # Withheld fields must contain everything else from the full EHR
    assert "active_diagnoses" in disclosure.withheld_fields
    assert "medications" in disclosure.withheld_fields
    assert "clinical_notes_summary" in disclosure.withheld_fields
    assert "billing_codes" in disclosure.withheld_fields
    assert len(disclosure.withheld_fields) > len(disclosure.disclosed_fields)

    # Disclosed payload only contains the minimal fields
    assert set(disclosure.disclosed_payload.keys()) == {"blood_pressure", "heart_rate"}
    assert "active_diagnoses" not in disclosure.disclosed_payload
    assert "active_diagnoses" in disclosure.withheld_payload


def test_positive_purpose_change_narrows_disclosure() -> None:
    """Changing purpose from clinical to self_care narrows the disclosed fields."""
    task = TaskDependency(
        task_id="task_patient_sync",
        required_fields=("blood_pressure", "active_diagnoses", "allergies"),
    )

    # Under 'clinical' purpose, diagnoses and allergies are authorized
    clinical_disclosure = minimal_disclosure(
        task_dependency=task,
        current_purpose="clinical",
        graph=LineageGraph(nodes=(), edges=()),
        context=SAMPLE_FULL_EHR_SUMMARY,
    )
    assert clinical_disclosure.status == STATUS_DISCLOSED
    assert "active_diagnoses" in clinical_disclosure.disclosed_fields
    assert "blood_pressure" in clinical_disclosure.disclosed_fields

    # Under 'self_care' purpose, active_diagnoses is NOT in the self_care allowlist
    self_care_disclosure = minimal_disclosure(
        task_dependency=task,
        current_purpose="self_care",
        graph=LineageGraph(nodes=(), edges=()),
        context=SAMPLE_FULL_EHR_SUMMARY,
    )
    assert self_care_disclosure.status == STATUS_DISCLOSED
    assert "blood_pressure" in self_care_disclosure.disclosed_fields
    assert "active_diagnoses" not in self_care_disclosure.disclosed_fields
    assert "active_diagnoses" in self_care_disclosure.withheld_fields
    # Narrowing verified: self_care disclosed set is strictly smaller
    assert len(self_care_disclosure.disclosed_fields) < len(clinical_disclosure.disclosed_fields)


def test_positive_select_fields_contract() -> None:
    """Target contract: select_fields(context, task) -> FieldSet."""
    field_set = select_fields(
        context=SAMPLE_FULL_EHR_SUMMARY,
        task=["blood_pressure", "heart_rate"],
        purpose="care_summary",
    )
    assert isinstance(field_set, FieldSet)
    assert field_set.fields == ("blood_pressure", "heart_rate")
    assert "medications" in field_set.withheld_fields
    assert "clinical_notes_summary" in field_set.withheld_fields
    assert field_set.purpose == "care_summary"

    d = field_set.to_dict()
    assert d["fields"] == ["blood_pressure", "heart_rate"]
    assert isinstance(d["withheld_fields"], list)


def test_positive_deterministic_json_serialization(
    clean_lineage_graph: LineageGraph,
) -> None:
    """Outputs are deterministic and serializable to JSON without loss."""
    task = TaskDependency(
        task_id="task_med_review",
        required_fields=("medications", "medication_schedule"),
        expected_lineage_nodes=("summary_meds_1",),
    )
    d1 = minimal_disclosure(task, "medication_review", clean_lineage_graph, SAMPLE_FULL_EHR_SUMMARY)
    d2 = minimal_disclosure(task, "medication_review", clean_lineage_graph, SAMPLE_FULL_EHR_SUMMARY)

    json1 = json.dumps(d1.to_dict(), sort_keys=True)
    json2 = json.dumps(d2.to_dict(), sort_keys=True)
    assert json1 == json2
    assert d1.version == MINIMAL_DISCLOSURE_VERSION


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_adversarial_unknown_graph_edge_forces_recomputation(
    clean_lineage_graph: LineageGraph,
) -> None:
    """When a required lineage node is unknown or unresolvable in the graph, fail closed to RECOMPUTATION."""
    task = TaskDependency(
        task_id="task_unlinked_dependency",
        required_fields=("blood_pressure",),
        # Node 'mystery_node_404' is not in clean_lineage_graph
        expected_lineage_nodes=("mystery_node_404",),
    )

    recomputed_called = False

    def recompute(task_id: str, purpose: str, nodes: tuple[str, ...]) -> dict[str, Any]:
        nonlocal recomputed_called
        recomputed_called = True
        return {"blood_pressure": "120/80 (freshly recomputed)"}

    disclosure = minimal_disclosure(
        task_dependency=task,
        current_purpose="care_summary",
        graph=clean_lineage_graph,
        context=SAMPLE_FULL_EHR_SUMMARY,
        recompute_fn=recompute,
    )

    assert disclosure.status == STATUS_RECOMPUTATION
    assert disclosure.reason_code == REASON_RECOMPUTATION_REQUIRED
    assert disclosure.recomputation_required is True
    assert "mystery_node_404" in disclosure.recomputation_fallback_nodes
    assert len(disclosure.unresolved_edges) > 0
    assert recomputed_called is True
    assert disclosure.disclosed_payload == {"blood_pressure": "120/80 (freshly recomputed)"}


def test_adversarial_purpose_incompatible_edge_forces_recomputation(
    clean_lineage_graph: LineageGraph,
) -> None:
    """When a node's derivation edge has purpose 'medication_review', requesting it under 'billing' forces recomputation."""
    task = TaskDependency(
        task_id="task_cross_purpose_lineage",
        required_fields=("medications",),
        expected_lineage_nodes=("summary_meds_1",),
    )

    disclosure = minimal_disclosure(
        task_dependency=task,
        current_purpose="billing",  # Edge summary_meds_1 has purpose medication_review
        graph=clean_lineage_graph,
        context=SAMPLE_FULL_EHR_SUMMARY,
    )

    assert disclosure.status == STATUS_RECOMPUTATION
    assert disclosure.reason_code == REASON_RECOMPUTATION_REQUIRED
    assert disclosure.recomputation_required is True
    assert "summary_meds_1" in disclosure.recomputation_fallback_nodes


def test_adversarial_full_summary_disclosure_refused_when_minimal_set_exists(
    clean_lineage_graph: LineageGraph,
) -> None:
    """Disclosing full summary refused when a minimal set exists."""
    task = TaskDependency(
        task_id="task_narrow_vitals",
        required_fields=("blood_pressure", "heart_rate"),
        expected_lineage_nodes=("cache_vitals_1",),
    )

    # Caller tries to force full summary disclosure with allow_full_summary=True
    disclosure = minimal_disclosure(
        task_dependency=task,
        current_purpose="care_summary",
        graph=clean_lineage_graph,
        context=SAMPLE_FULL_EHR_SUMMARY,
        allow_full_summary=True,
    )

    # Must be REFUSED!
    assert disclosure.status == STATUS_REFUSED
    assert disclosure.reason_code == REASON_FULL_SUMMARY_DISCLOSURE_REFUSED
    assert len(disclosure.disclosed_fields) == 0
    assert len(disclosure.withheld_fields) == len(SAMPLE_FULL_EHR_SUMMARY)
    assert disclosure.disclosed_payload == {}
    assert disclosure.withheld_payload == SAMPLE_FULL_EHR_SUMMARY


def test_adversarial_missing_graph_falls_back_to_recomputation() -> None:
    """When graph is None, fail closed and require recomputation."""
    task = TaskDependency(
        task_id="task_no_graph",
        required_fields=("blood_pressure",),
        expected_lineage_nodes=("node_1",),
    )
    disclosure = minimal_disclosure(
        task_dependency=task,
        current_purpose="care_summary",
        graph=None,
        context=SAMPLE_FULL_EHR_SUMMARY,
    )
    assert disclosure.status == STATUS_RECOMPUTATION
    assert disclosure.recomputation_required is True


def test_adversarial_malformed_inputs_raise_stable_reason_codes() -> None:
    """Invalid task or purpose inputs fail closed with stable reason codes."""
    with pytest.raises(MinimalDisclosureError, match=REASON_INVALID_PURPOSE):
        minimal_disclosure(
            task_dependency={"task_id": "t1", "required_fields": ["f1"]},
            current_purpose="",
            graph=None,
        )

    with pytest.raises(MinimalDisclosureError, match=REASON_INVALID_TASK):
        TaskDependency(task_id="", required_fields=("f1",))

    with pytest.raises(MinimalDisclosureError, match=REASON_INVALID_TASK):
        TaskDependency(task_id="t1", required_fields=())  # empty required fields

    with pytest.raises(MinimalDisclosureError, match=REASON_MALFORMED_CONTEXT):
        select_fields(context=12345, task=["f1"])
