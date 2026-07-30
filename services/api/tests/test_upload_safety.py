"""Regression coverage for shared untrusted-upload safety checks."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from clara_api.core.upload_safety import (
    UploadMalwareScannerUnavailable,
    UploadSafetyError,
    read_upload_bytes_with_limit,
    verify_upload,
)


class _CleanScanner:
    def scan(self, data: bytes) -> str:
        assert data
        return "clean"


class _UnavailableScanner:
    def scan(self, _data: bytes) -> str:
        raise UploadMalwareScannerUnavailable("scanner unavailable")


class _ChunkedUpload:
    def __init__(self, chunks: list[bytes]):
        self._chunks = iter(chunks)

    async def read(self, _size: int = -1) -> bytes:
        return next(self._chunks, b"")


def test_accepts_matching_pdf_magic_and_generic_browser_mime() -> None:
    verified = verify_upload(
        filename="visit-note.pdf",
        content_type="application/octet-stream",
        data=b"%PDF-1.7\nexample",
        fallback_filename="upload.pdf",
    )

    assert verified.filename == "visit-note.pdf"
    assert verified.media_type == "application/pdf"
    assert verified.malware_scanned is False


def test_rejects_filename_or_declared_type_that_disagrees_with_bytes() -> None:
    with pytest.raises(UploadSafetyError):
        verify_upload(
            filename="medical-note.pdf",
            content_type="application/pdf",
            data=b"not really a pdf",
            fallback_filename="upload.pdf",
        )

    with pytest.raises(UploadSafetyError):
        verify_upload(
            filename="payload.exe",
            content_type="text/plain",
            data=b"plain text disguised as executable",
            fallback_filename="upload.txt",
        )


def test_required_scanner_has_no_fail_open_path() -> None:
    with pytest.raises(UploadMalwareScannerUnavailable):
        verify_upload(
            filename="note.txt",
            content_type="text/plain",
            data=b"noi dung an toan",
            fallback_filename="upload.txt",
            malware_scan_required=True,
            scanner=_UnavailableScanner(),
        )

    verified = verify_upload(
        filename="note.txt",
        content_type="text/plain",
        data=b"noi dung an toan",
        fallback_filename="upload.txt",
        malware_scan_required=True,
        scanner=_CleanScanner(),
    )
    assert verified.malware_scanned is True


def test_read_limit_rejects_before_collecting_an_oversized_body() -> None:
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            read_upload_bytes_with_limit(_ChunkedUpload([b"abc", b"def"]), max_bytes=5)
        )

    assert raised.value.status_code == 413
