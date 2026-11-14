"""CLARA-Care 2027 shared task SH-venue_formats.

Purpose
-------
Provide the program-wide venue submission checklist consumed by every
``<VENUE>-funding`` and ``<VENUE>-paper`` task. :func:`check_venue` returns the
template family, page limits, anonymity/artifact policy, registration/fee
status, and conflicts policy for one venue as of one date, loaded from the
machine registry ``research/venue2027/_shared/venue_checklist.json``.

Honesty semantics
-----------------
Every deadline/cost-bearing field carries a ``VerificationStatus``. The only
statuses are ``VERIFIED`` (must cite ``verification_url`` +
``verification_date``) and ``UNVERIFIED`` (default). :func:`audit_checklist`
implements the negative control from the task spec: any deadline or cost
presented as CONFIRMED (``VERIFIED``) without a verification URL and date is a
hard audit failure, and any venue required by the program that is missing from
the registry is a hard audit failure. Nothing in this repository may present an
external CFP fact as confirmed without such a citation.

Allowed input
-------------
``venue``: one of the nine program venues (see ``VENUES``).
``date``: ISO-8601 string (e.g. ``2026-11-15``) used for staleness context.
Registry JSON path for the audit/render entry points.

Failure semantics
-----------------
Unknown venue or malformed registry raise :class:`VenueChecklistError` with a
stable ``reason_code`` (never a bare exception, never silently empty output).
All errors are fail-closed: an entry whose facts cannot be attributed to an
official source stays ``UNVERIFIED`` and downstream tasks must re-verify at
conversion time.

Version
-------
``VENUE_CHECKLIST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

VENUE_CHECKLIST_VERSION = "1.0.0"

DEFAULT_REGISTRY = "research/venue2027/_shared/venue_checklist.json"
DEFAULT_MARKDOWN = "research/venue2027/_shared/submission_venue_checklist.md"

ReasonCode = Literal[
    "OK",
    "UNKNOWN_VENUE",
    "INVALID_DATE",
    "REGISTRY_MALFORMED",
    "CONFIRMED_WITHOUT_CITATION",
    "MISSING_VENUE",
    "MISSING_REQUIRED_FIELD",
]

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"

#: Every venue the nine-study program must cover; the audit fails if any is absent.
VENUES: tuple[str, ...] = (
    "dsn",
    "popets",
    "ifip_sec",
    "acns",
    "compsac",
    "aime",
    "sacmat",
    "dimva",
    "pst",
)

TEMPLATE_FAMILIES: tuple[str, ...] = ("ACM", "IEEE", "Springer", "arXiv", "PoPETs")

UNVERIFIED_REASON = "live CFP not fetched; must be re-verified at conversion time"


class VenueChecklistError(ValueError):
    """Raised on unknown venue, malformed registry, or invalid date."""

    def __init__(self, reason_code: ReasonCode, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class Fact:
    """A single external CFP fact plus its honest verification status."""

    value: str
    status: Literal["VERIFIED", "UNVERIFIED"]
    verification_url: str = ""
    verification_date: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, str]:
        out: dict[str, str] = {"value": self.value, "status": self.status}
        if self.verification_url:
            out["verification_url"] = self.verification_url
        if self.verification_date:
            out["verification_date"] = self.verification_date
        if self.reason:
            out["reason"] = self.reason
        return out


@dataclasses.dataclass(frozen=True)
class Checklist:
    """Per-venue submission checklist. JSON-serializable via :meth:`to_dict`."""

    venue: str
    date: str
    cfp_url: Fact
    template_family: Fact
    page_limit: Fact
    anonymity_policy: Fact
    artifact_policy: Fact
    registration_fee: Fact
    conflicts_policy: Fact
    author_contributions: Fact
    status: Literal["UNVERIFIED", "VERIFIED", "MIXED"] = "UNVERIFIED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "date": self.date,
            "status": self.status,
            "cfp_url": self.cfp_url.to_dict(),
            "template_family": self.template_family.to_dict(),
            "page_limit": self.page_limit.to_dict(),
            "anonymity_policy": self.anonymity_policy.to_dict(),
            "artifact_policy": self.artifact_policy.to_dict(),
            "registration_fee": self.registration_fee.to_dict(),
            "conflicts_policy": self.conflicts_policy.to_dict(),
            "author_contributions": self.author_contributions.to_dict(),
        }


#: Fields that carry a deadline or cost; being claimed VERIFIED requires citation.
DEADLINE_OR_COST_FIELDS: tuple[str, ...] = ("registration_fee", "cfp_url")

#: Fields every checklist row must define.
REQUIRED_FACT_FIELDS: tuple[str, ...] = (
    "cfp_url",
    "template_family",
    "page_limit",
    "anonymity_policy",
    "artifact_policy",
    "registration_fee",
    "conflicts_policy",
    "author_contributions",
)


def _fact(raw: dict[str, Any], field: str, venue: str) -> Fact:
    if field not in raw:
        raise VenueChecklistError("MISSING_REQUIRED_FIELD", f"venue {venue!r} lacks fact {field!r}")
    entry = raw[field]
    if not isinstance(entry, dict) or "value" not in entry or "status" not in entry:
        raise VenueChecklistError(
            "REGISTRY_MALFORMED",
            f"venue {venue!r} fact {field!r} must be an object with value+status",
        )
    status = entry["status"]
    if status not in (VERIFIED, UNVERIFIED):
        raise VenueChecklistError(
            "REGISTRY_MALFORMED",
            f"venue {venue!r} fact {field!r} has illegal status {status!r}",
        )
    return Fact(
        value=str(entry["value"]),
        status=status,
        verification_url=str(entry.get("verification_url", "")),
        verification_date=str(entry.get("verification_date", "")),
        reason=str(entry.get("reason", "")),
    )


def _fact_from_row(row: dict[str, Any], field: str) -> Fact:
    entry = row[field]
    return Fact(
        value=str(entry.get("value", "")),
        status=entry.get("status", UNVERIFIED),
        verification_url=str(entry.get("verification_url", "")),
        verification_date=str(entry.get("verification_date", "")),
        reason=str(entry.get("reason", "")),
    )


def _validate_date(date: str) -> None:
    if not date or not isinstance(date, str):
        raise VenueChecklistError("INVALID_DATE", f"date={date!r} is not an ISO-8601 string")


def check_venue(
    venue: str, date: str, *, registry_path: str | Path = DEFAULT_REGISTRY
) -> Checklist:
    """Return the submission checklist for ``venue`` as of ``date``.

    Raises :class:`VenueChecklistError` with ``UNKNOWN_VENUE`` for a venue
    outside ``VENUES`` and ``INVALID_DATE`` for a non-ISO date string.
    """

    _validate_date(date)
    if venue not in VENUES:
        raise VenueChecklistError(
            "UNKNOWN_VENUE", f"{venue!r} not in program venues {list(VENUES)}"
        )
    entries = load_registry(registry_path)
    raw = entries[venue]
    facts = {f: _fact(raw, f, venue) for f in REQUIRED_FACT_FIELDS}
    statuses = {f.status for f in facts.values()}
    row_status: Literal["UNVERIFIED", "VERIFIED", "MIXED"]
    if statuses == {VERIFIED}:
        row_status = "VERIFIED"
    elif statuses == {UNVERIFIED}:
        row_status = "UNVERIFIED"
    else:
        row_status = "MIXED"
    return Checklist(venue=venue, date=date, status=row_status, **facts)  # type: ignore[arg-type]


@dataclasses.dataclass(frozen=True)
class AuditFinding:
    venue: str
    field: str
    reason_code: ReasonCode
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "venue": self.venue,
            "field": self.field,
            "reason_code": self.reason_code,
            "detail": self.detail,
        }


@dataclasses.dataclass(frozen=True)
class AuditResult:
    ok: bool
    reason_code: ReasonCode
    findings: tuple[AuditFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason_code": self.reason_code,
            "schema_version": VENUE_CHECKLIST_VERSION,
            "finding_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


def _finding_from_entry(venue: str, field: str, entry: Any) -> AuditFinding | None:
    """Negative control: a CONFIRMED (VERIFIED) deadline/cost without
    verification URL + date must fail the audit; illegal/malformed fact
    objects fail closed."""

    if not isinstance(entry, dict) or "value" not in entry or "status" not in entry:
        return AuditFinding(
            venue=venue,
            field=field,
            reason_code="REGISTRY_MALFORMED",
            detail=f"{venue}.{field} must be an object with value+status",
        )
    status = entry.get("status")
    if status not in (VERIFIED, UNVERIFIED):
        return AuditFinding(
            venue=venue,
            field=field,
            reason_code="REGISTRY_MALFORMED",
            detail=f"{venue}.{field} has illegal status {status!r}",
        )
    if status != VERIFIED:
        return None
    url = str(entry.get("verification_url", "")).strip()
    date = str(entry.get("verification_date", "")).strip()
    if not url or not date:
        return AuditFinding(
            venue=venue,
            field=field,
            reason_code="CONFIRMED_WITHOUT_CITATION",
            detail=(
                f"{venue}.{field} is presented as {VERIFIED} without both a "
                "verification_url and verification_date"
            ),
        )
    return None


def audit_checklist(
    entries: dict[str, dict[str, Any]] | None = None,
    *,
    required_venues: Sequence[str] = VENUES,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> AuditResult:
    """Audit the registry.

    FAILs when any venue in ``required_venues`` is missing, when a
    deadline/cost field is presented as CONFIRMED (``VERIFIED``) without a
    verification URL+date, or when the registry is malformed. UNVERIFIED rows
    are expected and never fail the audit by themselves.
    """

    if entries is None:
        entries = load_registry(registry_path)

    findings: list[AuditFinding] = []
    for venue in required_venues:
        if venue not in entries:
            findings.append(
                AuditFinding(
                    venue=venue,
                    field="*",
                    reason_code="MISSING_VENUE",
                    detail=f"required venue {venue!r} absent from registry",
                )
            )
            continue
        raw = entries[venue]
        if not isinstance(raw, dict):
            findings.append(
                AuditFinding(
                    venue=venue,
                    field="*",
                    reason_code="REGISTRY_MALFORMED",
                    detail=f"venue {venue!r} entry is not an object",
                )
            )
            continue
        for field in REQUIRED_FACT_FIELDS:
            if field not in raw:
                findings.append(
                    AuditFinding(
                        venue=venue,
                        field=field,
                        reason_code="MISSING_REQUIRED_FIELD",
                        detail=f"venue {venue!r} lacks fact {field!r}",
                    )
                )
                continue
            finding = _finding_from_entry(venue, field, raw[field])
            if finding is not None:
                findings.append(finding)

    blocked = any(f.reason_code != "OK" for f in findings)
    return AuditResult(
        ok=not blocked,
        reason_code="OK" if not blocked else "CONFIRMED_WITHOUT_CITATION",
        findings=tuple(findings),
    )


def load_registry(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load and validate the machine registry; malformed input fails closed."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VenueChecklistError("REGISTRY_MALFORMED", f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict) or "venues" not in payload:
        raise VenueChecklistError(
            "REGISTRY_MALFORMED", f"{path} must be an object with a 'venues' mapping"
        )
    venues = payload["venues"]
    if not isinstance(venues, dict):
        raise VenueChecklistError("REGISTRY_MALFORMED", "'venues' must be an object")
    return venues


def to_markdown(checklists: Sequence[Checklist], *, audit: AuditResult) -> str:
    """Render the human checklist with an explicit VERIFICATION STATUS column."""

    lines = [
        "# CLARA-Care 2027 — submission venue checklist (SH-venue_formats)",
        "",
        f"Data schema version: `{VENUE_CHECKLIST_VERSION}` · "
        f"Machine registry: `_shared/venue_checklist.json` · "
        f"Audit ok: `{str(audit.ok).lower()}`",
        "",
        "**Honesty rule:** every external CFP fact below is UNVERIFIED until a human "
        "re-checks the official CFP at conversion time. Rows marked VERIFIED require "
        "both a verification URL and date. No deadline or fee is confirmed by this file.",
        "",
        "| Venue | CFP URL | Template | Page limit | Anonymity | Artifact | Fee/registration | Conflicts | Author contributions | VERIFICATION STATUS |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in checklists:
        lines.append(
            f"| {c.venue} | {_cell(c.cfp_url)} | {_cell(c.template_family)} | "
            f"{_cell(c.page_limit)} | {_cell(c.anonymity_policy)} | {_cell(c.artifact_policy)} | "
            f"{_cell(c.registration_fee)} | {_cell(c.conflicts_policy)} | "
            f"{_cell(c.author_contributions)} | {c.status} |"
        )
    lines += [
        "",
        "## Unverified-fact reason",
        "",
        f"Unless a row states otherwise: {UNVERIFIED_REASON}.",
        "",
        "## Per-venue detail",
        "",
    ]
    for c in checklists:
        lines.append(f"### {c.venue} (as of {c.date}) — row status {c.status}")
        for field in REQUIRED_FACT_FIELDS:
            fact = getattr(c, field)
            suffix = ""
            if fact.status == VERIFIED:
                suffix = f" — verified {fact.verification_date} via {fact.verification_url}"
            elif fact.reason:
                suffix = f" — {fact.reason}"
            lines.append(f"- `{field}` ({fact.status}): {fact.value}{suffix}")
        lines.append("")
    if audit.findings:
        lines += ["## Audit findings", ""]
        for f in audit.findings:
            lines.append(f"- `{f.reason_code}` {f.venue}.{f.field}: {f.detail}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _cell(fact: Fact) -> str:
    text = fact.value.replace("|", "\\|")
    if fact.status == VERIFIED:
        return f"{text} ✔"
    return text


def _sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 SH-venue_formats checklist")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--out", default=DEFAULT_MARKDOWN)
    parser.add_argument("--date", required=True, help="ISO-8601 date the checklist is compiled for")
    args = parser.parse_args(argv)

    checklists = [check_venue(v, args.date, registry_path=args.registry) for v in VENUES]
    audit = audit_checklist(registry_path=args.registry)
    Path(args.out).write_text(to_markdown(checklists, audit=audit), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": audit.ok,
                "reason_code": audit.reason_code,
                "venue_count": len(checklists),
                "finding_count": len(audit.findings),
                "out": args.out,
                "version": VENUE_CHECKLIST_VERSION,
            },
            indent=2,
        )
    )
    return 0 if audit.ok else 1


if __name__ == "__main__":
    sys.exit(main())
