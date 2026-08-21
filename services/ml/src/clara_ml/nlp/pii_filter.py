from __future__ import annotations

import re
from dataclasses import dataclass

PHONE_RE = re.compile(r"\b(?:\+84|0)\d{9,10}\b")
ID_RE = re.compile(r"\b\d{9,12}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass
class PiiResult:
    redacted_text: str
    flags: dict[str, int]


def redact_pii(text: str) -> PiiResult:
    redacted = text
    flags = {"phone": 0, "id": 0, "email": 0}

    redacted, n_phone = PHONE_RE.subn("[REDACTED_PHONE]", redacted)
    redacted, n_id = ID_RE.subn("[REDACTED_ID]", redacted)
    redacted, n_email = EMAIL_RE.subn("[REDACTED_EMAIL]", redacted)

    flags["phone"] = n_phone
    flags["id"] = n_id
    flags["email"] = n_email
    return PiiResult(redacted_text=redacted, flags=flags)
