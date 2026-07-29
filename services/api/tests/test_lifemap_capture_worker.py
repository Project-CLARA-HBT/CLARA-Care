"""Capture worker validates checksums and ML draft-only output."""

from __future__ import annotations

import hashlib

import pytest

from clara_api.db.models import LifeMapCaptureArtifact, LifeMapCaptureSession
from clara_api.lifemap import capture_worker


class Store:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def get(self, *, storage_key: str) -> bytes:
        assert storage_key == "capture/source"
        return self.content


def _rows(content: bytes) -> tuple[LifeMapCaptureArtifact, LifeMapCaptureSession]:
    artifact = LifeMapCaptureArtifact(
        session_id=1,
        profile_id=1,
        storage_key="capture/source",
        media_type="text/plain",
        byte_size=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
        malware_status="clean",
        metadata_json={"filename": "label.txt"},
    )
    session = LifeMapCaptureSession(
        profile_id=1,
        input_kind="medication_label",
        schema_version="lifemap.capture.v1",
        locale="vi",
    )
    return artifact, session


def test_worker_accepts_only_draft_exact_checksum_extraction(monkeypatch) -> None:
    content = b"Paracetamol\n500 mg\noral"
    source = content.decode()
    source_checksum = hashlib.sha256(content).hexdigest()
    artifact, session = _rows(content)
    monkeypatch.setattr(
        capture_worker, "build_capture_artifact_store", lambda: Store(content)
    )
    monkeypatch.setattr(
        capture_worker,
        "proxy_ml_post",
        lambda *_args, **_kwargs: {
            "draft_only": True,
            "candidate": {
                "candidate_type": "medication_label",
                "field_path": "medication_label",
                "value": {
                    "medication_name": "Paracetamol",
                    "strength": "500 mg",
                    "route": "oral",
                },
                "confidence": 0.7,
                "field_confidence": {
                    "medication_name": 0.7,
                    "strength": 0.9,
                    "route": 0.9,
                },
                "source_span": {
                    "kind": "text_fields",
                    "fields": {
                        "medication_name": {"start": 0, "end": 11},
                        "strength": {"start": 12, "end": 18},
                        "route": {"start": 19, "end": 23},
                    },
                    "text_checksum": source_checksum,
                },
                "schema_version": "lifemap.capture.v1",
                "extractor_version": "worker-test",
                "security_findings": [],
            },
        },
    )
    candidates = capture_worker._extract(artifact, session)
    assert len(candidates) == 1
    assert candidates[0].value["medication_name"] == source[:11]
    assert candidates[0].field_confidence["strength"] == 0.9


def test_worker_rejects_tampered_artifact_before_ocr(monkeypatch) -> None:
    content = b"Paracetamol"
    artifact, session = _rows(content)
    monkeypatch.setattr(
        capture_worker,
        "build_capture_artifact_store",
        lambda: Store(b"tampered"),
    )
    with pytest.raises(ValueError, match="artifact_checksum"):
        capture_worker._extract(artifact, session)


def test_worker_runs_emergency_fast_path_before_ml(monkeypatch) -> None:
    content = b"Severe chest pain and cannot breathe"
    artifact, session = _rows(content)
    monkeypatch.setattr(
        capture_worker, "build_capture_artifact_store", lambda: Store(content)
    )
    called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("ML must not run")

    monkeypatch.setattr(capture_worker, "proxy_ml_post", fail_if_called)
    with pytest.raises(capture_worker.EmergencyCaptureDetected):
        capture_worker._extract(artifact, session)
    assert called is False
