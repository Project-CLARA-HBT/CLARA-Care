"""Encrypted artifact, media-sniffing, malware, and deletion contracts."""

from __future__ import annotations

import base64

import pytest

from clara_api.lifemap.capture_artifacts import (
    ArtifactSecurityError,
    EncryptedCaptureArtifactStore,
    sniff_media_type,
)


class MemoryObjects:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    def get_object(self, key: str) -> bytes:
        return self.objects[key]

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)


class Scanner:
    def __init__(self, verdict: str = "clean") -> None:
        self.verdict = verdict

    def scan(self, _data: bytes) -> str:
        return self.verdict


def _key() -> str:
    return base64.urlsafe_b64encode(b"k" * 32).decode()


def test_capture_artifact_is_sniffed_scanned_encrypted_and_deletable() -> None:
    objects = MemoryObjects()
    store = EncryptedCaptureArtifactStore(
        objects, encryption_key=_key(), scanner=Scanner()
    )
    raw = b"%PDF-1.7\nsensitive health artifact"
    stored = store.put(
        profile_public_id="profile-opaque",
        artifact_public_id="artifact-opaque",
        data=raw,
        declared_type="application/pdf",
    )
    encrypted = objects.objects[stored.storage_key]
    assert raw not in encrypted
    assert stored.media_type == "application/pdf"
    assert stored.byte_size == len(raw)
    assert stored.malware_status == "clean"
    assert store.get(storage_key=stored.storage_key) == raw
    store.delete(storage_key=stored.storage_key)
    assert stored.storage_key not in objects.objects


def test_capture_artifact_fails_closed_on_mismatch_malware_and_tampering() -> None:
    objects = MemoryObjects()
    clean = EncryptedCaptureArtifactStore(
        objects, encryption_key=_key(), scanner=Scanner()
    )
    with pytest.raises(ArtifactSecurityError, match="media types differ"):
        clean.put(
            profile_public_id="p",
            artifact_public_id="a",
            data=b"%PDF-1.7",
            declared_type="image/png",
        )
    infected = EncryptedCaptureArtifactStore(
        objects, encryption_key=_key(), scanner=Scanner("infected")
    )
    with pytest.raises(ArtifactSecurityError, match="malware"):
        infected.put(
            profile_public_id="p",
            artifact_public_id="b",
            data=b"plain text",
            declared_type="text/plain",
        )

    stored = clean.put(
        profile_public_id="p",
        artifact_public_id="c",
        data=b"plain text",
        declared_type="text/plain",
    )
    objects.objects[stored.storage_key] = objects.objects[stored.storage_key][:-1] + b"x"
    with pytest.raises(ArtifactSecurityError, match="authentication failed"):
        clean.get(storage_key=stored.storage_key)


def test_media_sniffer_rejects_unknown_binary() -> None:
    assert sniff_media_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    with pytest.raises(ArtifactSecurityError):
        sniff_media_type(b"\x00\xff\x00\xff")
