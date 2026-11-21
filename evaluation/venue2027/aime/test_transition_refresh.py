"""Test the snapshot adapter at clinically conservative decision boundaries."""

from . import selective_refresh as sr
from .selective_refresh import plan_transition


def test_encounter_label_accompanies_medication_removal():
    before = {
        "consent": {"granted_purposes": ["audit"]},
        "medications": ["x"],
        "allergies": [],
        "notes": "previous",
    }
    after = before | {"medications": [], "notes": "current"}
    assert sr.refresh(after, "notes").mode == sr.MODE_PARTIAL
    assert plan_transition(before, after, "notes").mode == sr.MODE_FULL
    assert plan_transition(before, before | {"notes": "current"}, "notes").mode == sr.MODE_PARTIAL


def test_joint_removals_preserve_prior_review_boundary():
    before = {"consent": {"granted_purposes": ["audit"]}, "medications": ["x"], "allergies": ["y"]}
    after = {"consent": {"granted_purposes": []}, "medications": [], "allergies": []}
    assert plan_transition(before, after, "consent").mode == sr.MODE_CLINICIAN_REVIEW
    assert plan_transition({"medications": []}, after, "notes").mode == sr.MODE_FULL


def test_unknown_changed_section_forces_full():
    before = {"consent": {"granted_purposes": []}, "medications": [], "allergies": []}
    assert plan_transition(before, before | {"unknown": None}, "notes").mode == sr.MODE_FULL


def test_adapter_uses_optional_previous_snapshot():
    before = {"consent": {"granted_purposes": ["audit"]}, "medications": ["x"], "allergies": []}
    after = before | {"medications": []}
    options = {"changed_field": "notes", "declared_dependencies": list(sr.ALL_DEPENDENCIES)}
    assert sr.update_context(after, options).mode == sr.MODE_PARTIAL
    assert sr.update_context(after, options | {"previous_state": before}).mode == sr.MODE_FULL
    assert sr.update_context(after, options | {"previous_state": None}).mode == sr.MODE_FULL
