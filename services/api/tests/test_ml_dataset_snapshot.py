from datetime import UTC, datetime, timedelta

import pytest

from clara_api.ml_governance.dataset_snapshot import (
    DatasetSnapshotError,
    audit_split_leakage,
    build_snapshot_manifest,
    validate_snapshot_record,
)


def _record(subject: str = "person-a", household: str = "house-a") -> dict:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "subject_ref": subject,
        "household_ref": household,
        "site_ref": f"site-{household}",
        "source_ref": f"source-{subject}",
        "device_ref": f"device-{subject}",
        "window_start": start.isoformat(),
        "window_end": (start + timedelta(days=7)).isoformat(),
        "purpose": "pattern_research",
        "consent_active": True,
        "features": {"coverage": 0.9, "median": 12.0, "missing": [False, True]},
    }


def test_snapshot_is_purpose_consent_filtered_and_reproducible() -> None:
    rows, manifest = build_snapshot_manifest(
        [_record()],
        dataset_id="lifemap-pattern",
        version="1",
        purpose="pattern_research",
        secret_salt=b"test-split-secret-at-least-16-bytes",
    )
    again, second_manifest = build_snapshot_manifest(
        [_record()],
        dataset_id="lifemap-pattern",
        version="1",
        purpose="pattern_research",
        secret_salt=b"test-split-secret-at-least-16-bytes",
    )
    assert rows == again
    assert manifest["sha256"] == second_manifest["sha256"]
    assert manifest["contains_direct_identifiers"] is False
    assert manifest["split_audit"]["status"] == "passed"


@pytest.mark.parametrize("field", ["name", "email", "free_text", "document_text"])
def test_snapshot_rejects_direct_or_content_fields(field: str) -> None:
    with pytest.raises(DatasetSnapshotError, match="snapshot_forbidden"):
        validate_snapshot_record(
            {**_record(), field: "must not enter a training snapshot"},
            purpose="pattern_research",
        )


def test_snapshot_rejects_revoked_consent_and_wrong_purpose() -> None:
    with pytest.raises(DatasetSnapshotError, match="purpose_or_consent"):
        validate_snapshot_record(
            {**_record(), "consent_active": False},
            purpose="pattern_research",
        )
    with pytest.raises(DatasetSnapshotError, match="purpose_or_consent"):
        validate_snapshot_record(_record(), purpose="different-purpose")


def test_leakage_audit_rejects_person_household_site_source_and_device_overlap() -> None:
    for dimension in (
        "subject_ref",
        "household_ref",
        "site_ref",
        "source_ref",
        "device_ref",
    ):
        first = {**_record(), "split": "train"}
        second = {**_record("person-b", "house-b"), "split": "test"}
        second[dimension] = first[dimension]
        with pytest.raises(DatasetSnapshotError, match=f"split_leakage:{dimension}"):
            audit_split_leakage([first, second])
