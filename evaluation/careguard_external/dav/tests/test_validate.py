import hashlib
import json
import sys
from pathlib import Path

import pytest

from evaluation.careguard_external.dav.core import Store, registration_numbers
from evaluation.careguard_external.dav.parse_attachments import parse
from evaluation.careguard_external.dav.status_reconstruction import reconstruct
from evaluation.careguard_external.dav.validate import validate


def test_retained_artifact_hash_and_url_are_validated(tmp_path: Path) -> None:
    store = Store(tmp_path, "2026-08-17")
    row = store.retain(
        bucket="attachments",
        url="https://dav.gov.vn/a.pdf",
        payload=b"Vietnam",
        content_type="application/pdf",
        status=200,
    )
    store.append("source_inventory.jsonl", row)
    assert validate(tmp_path, "2026-08-17")["valid"]
    assert row["sha256"] == hashlib.sha256(b"Vietnam").hexdigest()


@pytest.mark.parametrize(
    ("filename", "module", "dependency"),
    [("records.docx", "docx", "python-docx"), ("records.xlsx", "openpyxl", "openpyxl")],
)
def test_docx_and_xlsx_require_an_available_local_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str, module: str, dependency: str
) -> None:
    store = Store(tmp_path, "2026-08-17")
    row = store.retain(
        bucket="attachments",
        url=f"https://dav.gov.vn/{filename}",
        payload=b"not a document",
        content_type="application/octet-stream",
        status=200,
    )
    store.append("source_inventory.jsonl", row)
    monkeypatch.setitem(sys.modules, module, None)

    result = parse(tmp_path, "2026-08-17")

    assert result[0]["parse_status"] == "UNPARSED"
    assert result[0]["parse_error"] == f"parser_dependency_unavailable:{dependency}"


def test_empty_parsed_attachment_is_not_treated_as_extractable_evidence(tmp_path: Path) -> None:
    store = Store(tmp_path, "2026-08-17")
    row = store.retain(
        bucket="attachments",
        url="https://dav.gov.vn/records.csv",
        payload=b"",
        content_type="text/csv",
        status=200,
    )
    store.append("source_inventory.jsonl", row)

    result = parse(tmp_path, "2026-08-17")

    assert result[0]["parse_status"] == "PARSED_EMPTY"
    assert result[0]["parse_error"] == "no_extractable_text"
    assert validate(tmp_path, "2026-08-17")["valid"]


def test_validation_rejects_parse_records_without_matching_attachment(tmp_path: Path) -> None:
    store = Store(tmp_path, "2026-08-17")
    (store.manifests / "source_inventory.jsonl").write_text("", encoding="utf-8")
    (store.manifests / "attachment_parse.jsonl").write_text(
        json.dumps(
            {
                "raw_artifact_sha256": "missing",
                "source_url": "https://dav.gov.vn/missing.csv",
                "parse_status": "PARSED",
                "text": "VD-123",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="parse_record_not_in_attachment_inventory"):
        validate(tmp_path, "2026-08-17")


def test_reconstruction_rejects_events_without_verifiable_evidence(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="event_missing_evidence_document_id"):
        reconstruct(
            tmp_path, "2026-08-17", [{"registration_number": "VD-123", "event_type": "ISSUED"}], []
        )


def test_registration_numbers_are_canonicalized_before_event_grouping() -> None:
    assert registration_numbers("vd - 123  and VD-123") == ["VD-123"]
