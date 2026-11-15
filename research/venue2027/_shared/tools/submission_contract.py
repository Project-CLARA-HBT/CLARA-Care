"""CLARA-Care 2027 shared submission/funding contract.

Purpose
-------
Track the real submission prerequisites per venue: CFP URL, template, page
limit, fee/registration, waiver path, authorship/contribution, conflicts and
simultaneous-submission policy. No blanket "free" assumption and no unverified
waiver may be presented as guaranteed.

Allowed input
-------------
A venue ``submission/funding_and_author_check.md`` plus a machine registry of
the verification state.

Failure semantics
-----------------
Returns :class:`SubmissionResult` with ``ok=False`` when a required field is
absent, when a deadline/fee is marked CONFIRMED without a verification URL and
date, or when a waiver is claimed as guaranteed without evidence.

Version
-------
``SUBMISSION_CONTRACT_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from pathlib import Path

SUBMISSION_CONTRACT_VERSION = "1.0.0"

REQUIRED_FIELDS: tuple[str, ...] = (
    "cfp_url",
    "template",
    "page_limit",
    "fee_or_registration",
    "waiver_path",
    "authorship_and_contribution",
    "conflicts_policy",
    "simultaneous_submission_policy",
    "verification_status",
    "decision",
)

ALLOWED_VERIFICATION = ("CONFIRMED", "UNVERIFIED")
ALLOWED_DECISION = ("GO", "NO-GO", "HOLD")

_CONFIRMED_ROW_RE = re.compile(r"CONFIRMED", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclasses.dataclass(frozen=True)
class SubmissionResult:
    ok: bool
    reason_codes: tuple[str, ...]
    missing_fields: tuple[str, ...]
    violations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason_codes": list(self.reason_codes),
            "missing_fields": list(self.missing_fields),
            "violations": list(self.violations),
            "version": SUBMISSION_CONTRACT_VERSION,
        }


def validate_submission_check(text: str) -> SubmissionResult:
    """Validate a venue funding/author checklist document."""

    lower = text.lower()
    violations: list[str] = []
    reasons: list[str] = []

    missing_fields = tuple(f for f in REQUIRED_FIELDS if f not in lower)
    if missing_fields:
        reasons.append("MISSING_FIELD")

    # Any line that marks something CONFIRMED must carry a URL and an ISO date.
    for line in text.splitlines():
        if _CONFIRMED_ROW_RE.search(line):
            if not _URL_RE.search(line) or not _DATE_RE.search(line):
                reasons.append("CONFIRMED_WITHOUT_CITATION")
                violations.append(
                    f"CONFIRMED without verification URL+date: {line.strip()[:120]}"
                )

    # A guaranteed waiver claim needs an explicit evidence pointer.
    for line in text.splitlines():
        low = line.lower()
        if ("waiver" in low or "free" in low) and ("guarantee" in low or "will be free" in low):
            if not _URL_RE.search(line):
                reasons.append("UNVERIFIED_WAIVER_GUARANTEE")
                violations.append(f"waiver/free guarantee without source: {line.strip()[:120]}")

    # Double submission must be explicitly refused unless the venue allows it.
    if "double submission" not in lower and "simultaneous submission" not in lower:
        reasons.append("MISSING_SIMULTANEOUS_POLICY")

    return SubmissionResult(
        ok=not violations and not missing_fields,
        reason_codes=tuple(sorted(set(reasons))),
        missing_fields=missing_fields,
        violations=tuple(violations),
    )


def build_registry(venue: str, *, cfp_url: str, verification: str = "UNVERIFIED") -> dict[str, str]:
    if verification not in ALLOWED_VERIFICATION:
        raise ValueError(f"invalid verification status: {verification}")
    return {
        "venue": venue,
        "cfp_url": cfp_url,
        "verification_status": verification,
        "decision": "HOLD",
        "schema_version": SUBMISSION_CONTRACT_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 submission contract validator")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    result = validate_submission_check(Path(args.path).read_text(encoding="utf-8"))
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
