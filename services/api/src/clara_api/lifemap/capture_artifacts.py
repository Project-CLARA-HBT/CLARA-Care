"""Encrypted Universal Capture artifacts with fail-closed malware scanning."""

from __future__ import annotations

import base64
import hashlib
import socket
import struct
from dataclasses import dataclass
from secrets import token_bytes
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from clara_api.core.config import get_settings
from clara_api.core.research_upload_store import (
    ObjectStoreClient,
    build_object_store_client,
)

ALLOWED_MEDIA_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
}


class ArtifactSecurityError(ValueError):
    pass


class MalwareScannerUnavailable(RuntimeError):
    pass


class MalwareScanner(Protocol):
    def scan(self, data: bytes) -> str: ...


class ClamAvScanner:
    """Minimal ClamAV INSTREAM client; any ambiguity fails closed."""

    def __init__(self, host: str, port: int = 3310, timeout_seconds: float = 10.0):
        self._host = host.strip()
        self._port = port
        self._timeout = timeout_seconds

    def scan(self, data: bytes) -> str:
        if not self._host:
            raise MalwareScannerUnavailable("Malware scanner is not configured")
        try:
            with socket.create_connection(
                (self._host, self._port), timeout=self._timeout
            ) as connection:
                connection.sendall(b"zINSTREAM\0")
                for offset in range(0, len(data), 64 * 1024):
                    chunk = data[offset : offset + 64 * 1024]
                    connection.sendall(struct.pack(">I", len(chunk)))
                    connection.sendall(chunk)
                connection.sendall(struct.pack(">I", 0))
                response = connection.recv(4096).decode("utf-8", errors="replace")
        except OSError as error:
            raise MalwareScannerUnavailable("Malware scanner is unavailable") from error
        if "FOUND" in response:
            return "infected"
        if "OK" in response:
            return "clean"
        raise MalwareScannerUnavailable("Malware scanner returned an invalid verdict")


def sniff_media_type(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ArtifactSecurityError("Unsupported artifact media type") from error
    return "text/plain"


@dataclass(frozen=True)
class StoredCaptureArtifact:
    storage_key: str
    media_type: str
    byte_size: int
    checksum: str
    malware_status: str
    encryption_version: str = "aesgcm-v1"


class EncryptedCaptureArtifactStore:
    def __init__(
        self,
        client: ObjectStoreClient,
        *,
        encryption_key: str,
        scanner: MalwareScanner,
        max_bytes: int = 10_000_000,
    ) -> None:
        try:
            key = base64.urlsafe_b64decode(encryption_key.encode())
        except Exception as error:  # noqa: BLE001 - normalize secret format failures
            raise ArtifactSecurityError("Invalid capture encryption key") from error
        if len(key) != 32:
            raise ArtifactSecurityError("Capture encryption key must decode to 32 bytes")
        self._client = client
        self._aes = AESGCM(key)
        self._scanner = scanner
        self._max_bytes = max_bytes

    def put(
        self, *, profile_public_id: str, artifact_public_id: str, data: bytes, declared_type: str
    ) -> StoredCaptureArtifact:
        if not data or len(data) > self._max_bytes:
            raise ArtifactSecurityError("Artifact size is outside the allowed range")
        detected = sniff_media_type(data)
        if detected not in ALLOWED_MEDIA_TYPES or declared_type != detected:
            raise ArtifactSecurityError("Declared and detected media types differ")
        verdict = self._scanner.scan(data)
        if verdict != "clean":
            raise ArtifactSecurityError("Artifact failed malware screening")
        storage_key = f"lifemap-capture/{profile_public_id}/{artifact_public_id}"
        nonce = token_bytes(12)
        encrypted = nonce + self._aes.encrypt(nonce, data, storage_key.encode())
        self._client.put_object(storage_key, encrypted)
        return StoredCaptureArtifact(
            storage_key=storage_key,
            media_type=detected,
            byte_size=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
            malware_status="clean",
        )

    def get(self, *, storage_key: str) -> bytes:
        encrypted = self._client.get_object(storage_key)
        if len(encrypted) < 13:
            raise ArtifactSecurityError("Encrypted artifact is invalid")
        nonce, ciphertext = encrypted[:12], encrypted[12:]
        try:
            return self._aes.decrypt(nonce, ciphertext, storage_key.encode())
        except Exception as error:  # noqa: BLE001 - do not expose crypto internals
            raise ArtifactSecurityError("Encrypted artifact authentication failed") from error

    def delete(self, *, storage_key: str) -> None:
        self._client.delete_object(storage_key)


def build_capture_artifact_store() -> EncryptedCaptureArtifactStore:
    """Build the shared API/worker store without performing network I/O."""

    settings = get_settings()
    if (
        not settings.lifemap_capture_object_store_url.strip()
        or not settings.lifemap_capture_encryption_key.strip()
        or not settings.lifemap_capture_clamav_host.strip()
    ):
        raise ArtifactSecurityError("Capture artifact store is not configured")
    return EncryptedCaptureArtifactStore(
        build_object_store_client(settings.lifemap_capture_object_store_url),
        encryption_key=settings.lifemap_capture_encryption_key,
        scanner=ClamAvScanner(
            settings.lifemap_capture_clamav_host,
            settings.lifemap_capture_clamav_port,
        ),
        max_bytes=settings.lifemap_capture_max_artifact_bytes,
    )
