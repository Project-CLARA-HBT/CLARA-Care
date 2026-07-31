"""Shared safety boundary for untrusted user-uploaded documents.

This module deliberately performs only deterministic checks.  It never tries
to classify medical content and it never sends a file to an LLM.  Optional
ClamAV scanning is an operational control: when it is required, an unavailable
scanner rejects the upload rather than silently weakening the boundary.
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from pathlib import PurePath
from typing import Protocol

from fastapi import HTTPException, status


class UploadSafetyError(ValueError):
    """The file is not a permitted, internally consistent upload."""


class UploadMalwareScannerUnavailable(RuntimeError):
    """A policy-required malware scanner could not return a safe verdict."""


class MalwareScanner(Protocol):
    def scan(self, data: bytes) -> str: ...


class UploadReader(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


class ClamAvScanner:
    """Minimal ClamAV INSTREAM client with an explicit fail-closed contract."""

    def __init__(self, host: str, port: int = 3310, timeout_seconds: float = 10.0):
        self._host = host.strip()
        self._port = port
        self._timeout = timeout_seconds

    def scan(self, data: bytes) -> str:
        if not self._host:
            raise UploadMalwareScannerUnavailable("Malware scanner is not configured")
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
            raise UploadMalwareScannerUnavailable("Malware scanner is unavailable") from error
        if "FOUND" in response:
            return "infected"
        if "OK" in response:
            return "clean"
        raise UploadMalwareScannerUnavailable("Malware scanner returned an invalid verdict")


_TEXT_EXTENSIONS = frozenset(
    {".csv", ".json", ".log", ".markdown", ".md", ".txt", ".xml", ".yaml", ".yml"}
)
_IMAGE_TYPES_BY_EXTENSION = {
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}
_TEXT_CONTENT_TYPES = frozenset(
    {"application/json", "application/xml", "application/x-yaml", "text/csv", "text/plain", "text/xml", "text/yaml"}
)
_GENERIC_CONTENT_TYPES = frozenset({"", "application/octet-stream"})


@dataclass(frozen=True)
class VerifiedUpload:
    filename: str
    media_type: str
    byte_size: int
    malware_scanned: bool


async def read_upload_bytes_with_limit(file: UploadReader, *, max_bytes: int) -> bytes:
    """Read an ASGI upload incrementally, rejecting oversized bodies early."""

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File vượt quá giới hạn {max_bytes // (1024 * 1024)}MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def sanitize_upload_filename(filename: str | None, *, fallback: str) -> str:
    """Keep presentation metadata safe and portable; uploads are never path inputs."""

    candidate = (filename or "").replace("\\", "/").split("/")[-1].strip()
    if not candidate or candidate in {".", ".."} or "\x00" in candidate:
        return fallback
    if len(candidate) > 180:
        suffix = PurePath(candidate).suffix[:16]
        candidate = f"upload{suffix}"
    return candidate


def _extension(filename: str) -> str:
    return PurePath(filename).suffix.lower()


def sniff_media_type(data: bytes) -> str:
    """Identify only the narrow set of formats accepted by document uploads."""

    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if b"\x00" in data:
        raise UploadSafetyError("Unsupported binary upload type")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UploadSafetyError("Unsupported upload media type") from error
    return "text/plain"


def _declared_type_matches(
    *, filename: str, declared_type: str, detected_type: str
) -> bool:
    declared = declared_type.lower().split(";", 1)[0].strip()
    extension = _extension(filename)
    if detected_type == "text/plain":
        return (
            (not extension or extension in _TEXT_EXTENSIONS)
            and (declared in _GENERIC_CONTENT_TYPES or declared.startswith("text/") or declared in _TEXT_CONTENT_TYPES)
        )
    if detected_type == "application/pdf":
        return extension == ".pdf" and declared in (
            _GENERIC_CONTENT_TYPES | {"application/pdf"}
        )
    return (
        _IMAGE_TYPES_BY_EXTENSION.get(extension) == detected_type
        and declared in (_GENERIC_CONTENT_TYPES | {detected_type})
    )


def verify_upload(
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    fallback_filename: str,
    malware_scan_required: bool = False,
    clamav_host: str = "",
    clamav_port: int = 3310,
    scanner: MalwareScanner | None = None,
) -> VerifiedUpload:
    """Verify content type, filename alignment and the optional malware verdict.

    A generic or missing browser MIME is acceptable only when the extension and
    bytes agree.  Conversely, a supplied ``image/*`` or PDF MIME never makes a
    text/binary payload acceptable.
    """

    if not data:
        raise UploadSafetyError("Empty file upload")
    safe_filename = sanitize_upload_filename(filename, fallback=fallback_filename)
    detected_type = sniff_media_type(data)
    if not _declared_type_matches(
        filename=safe_filename,
        declared_type=content_type or "",
        detected_type=detected_type,
    ):
        raise UploadSafetyError("Declared filename, media type and file bytes differ")

    malware_scanned = False
    if malware_scan_required:
        active_scanner = scanner or ClamAvScanner(clamav_host, clamav_port)
        verdict = active_scanner.scan(data)
        if verdict != "clean":
            raise UploadSafetyError("Upload failed malware screening")
        malware_scanned = True

    return VerifiedUpload(
        filename=safe_filename,
        media_type=detected_type,
        byte_size=len(data),
        malware_scanned=malware_scanned,
    )
