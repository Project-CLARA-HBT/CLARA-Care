from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _extract_with_pypdf(pdf_path: Path, *, max_chars: int) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""

    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return ""

    chunks: list[str] = []
    total = 0
    for page in reader.pages:
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        if not text:
            continue
        remain = max_chars - total
        if remain <= 0:
            break
        if len(text) > remain:
            chunks.append(text[:remain])
            total = max_chars
            break
        chunks.append(text)
        total += len(text)
    return "\n".join(chunks).strip()


def _extract_with_pdftotext(pdf_path: Path, *, max_chars: int) -> str:
    binary = shutil.which("pdftotext")
    if not binary:
        return ""
    try:
        result = subprocess.run(
            [binary, "-q", str(pdf_path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    text = (result.stdout or "").strip()
    if not text:
        return ""
    return text[:max_chars]


def _extract_with_strings(pdf_path: Path, *, max_chars: int) -> str:
    binary = shutil.which("strings")
    if not binary:
        return ""
    try:
        result = subprocess.run(
            [binary, "-n", "8", str(pdf_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    text = (result.stdout or "").strip()
    if not text:
        return ""
    return text[:max_chars]


def extract_pdf_text(pdf_path: Path, *, max_chars: int = 12000) -> str:
    text = _extract_with_pypdf(pdf_path, max_chars=max_chars)
    if text:
        return text
    text = _extract_with_pdftotext(pdf_path, max_chars=max_chars)
    if text:
        return text
    text = _extract_with_strings(pdf_path, max_chars=max_chars)
    if text:
        return text
    return ""
