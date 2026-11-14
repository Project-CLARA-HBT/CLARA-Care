"""CLARA-Care 2027 shared task SH-literature_hardening.

Purpose
-------
Lock the strongest Q1/A/A* comparators from primary sources and record, for each,
whether the guarantee was actually verified (not inferred from a URL/venue name).

The ledger distinguishes:
- ``VERIFIED_BASELINE`` — primary source read AND runnable code located.
- ``PRIMARY_READ_CODE_ABSENT`` — primary source read, no code available (cannot
  be claimed as a runnable baseline).
- ``UNVERIFIED`` — not yet read; may not be cited as a strong baseline.

Allowed input
-------------
A literature registry (JSON) of citation records.

Failure semantics
-----------------
A record that explicitly declares a runnable/verified baseline claim
(``claims_verified_baseline=True``) but has no usable code URL (empty or
whitespace-only) yields ``ok=False`` with
``reason_code=INVALID_BASELINE_CLAIM``. Reading a source that simply has no
public code is *not* an error: it is honestly classified
``PRIMARY_READ_CODE_ABSENT``. Unverified records are counted and surfaced but
never silently presented as strong comparators.

Version
-------
``LITERATURE_LEDGER_VERSION = "1.1.0"``
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import sys
from pathlib import Path

LITERATURE_LEDGER_VERSION = "1.1.0"

VERIFIED_BASELINE = "VERIFIED_BASELINE"
PRIMARY_READ_CODE_ABSENT = "PRIMARY_READ_CODE_ABSENT"
UNVERIFIED = "UNVERIFIED"

FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "venue",
    "doi_or_url",
    "version",
    "primary_source_read",
    "code_url",
    "status",
    "guarantee",
    "relevance",
    "reproduced",
)


@dataclasses.dataclass(frozen=True)
class LiteratureRecord:
    id: str
    title: str
    venue: str
    doi_or_url: str
    version: str = ""
    primary_source_read: bool = False
    code_url: str = ""
    guarantee: str = ""
    relevance: str = ""
    reproduced: bool = False
    claims_verified_baseline: bool = False

    def classify(self) -> str:
        if not self.primary_source_read:
            return UNVERIFIED
        if self.code_url.strip():
            return VERIFIED_BASELINE
        return PRIMARY_READ_CODE_ABSENT

    def to_row(self) -> dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "venue": self.venue,
            "doi_or_url": self.doi_or_url,
            "version": self.version,
            "primary_source_read": str(self.primary_source_read).lower(),
            "code_url": self.code_url,
            "status": self.classify(),
            "guarantee": self.guarantee,
            "relevance": self.relevance,
            "reproduced": str(self.reproduced).lower(),
        }


@dataclasses.dataclass(frozen=True)
class LedgerResult:
    ok: bool
    reason_code: str
    rows: tuple[LiteratureRecord, ...]
    counts: dict[str, int]
    violations: tuple[str, ...]

    def to_csv(self) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(FIELDS))
        writer.writeheader()
        for row in self.rows:
            writer.writerow(row.to_row())
        return buffer.getvalue()


def verify_sources(records: list[LiteratureRecord]) -> LedgerResult:
    """Classify each record and flag impossible baseline claims."""

    violations: list[str] = []
    counts = {VERIFIED_BASELINE: 0, PRIMARY_READ_CODE_ABSENT: 0, UNVERIFIED: 0}
    for record in records:
        status = record.classify()
        counts[status] += 1
        if not record.doi_or_url.strip():
            violations.append(f"{record.id}: missing DOI/URL (cannot be a primary source)")
        if record.reproduced and status != VERIFIED_BASELINE:
            violations.append(
                f"{record.id}: marked reproduced but status is {status} (no runnable code)"
            )
        # Enforce the documented gate: an explicit runnable-baseline claim with
        # no usable code URL is an impossible baseline claim.
        if record.claims_verified_baseline and not record.code_url.strip():
            violations.append(
                f"{record.id}: VERIFIED_BASELINE claimed without a code URL"
            )
    ok = not violations
    return LedgerResult(
        ok=ok,
        reason_code="OK" if ok else "INVALID_BASELINE_CLAIM",
        rows=tuple(records),
        counts=counts,
        violations=tuple(violations),
    )


def load_registry(path: str | Path) -> list[LiteratureRecord]:
    """Load either a list, a ``{"sources": [...]}`` object, or the dict-keyed
    ``MANIFESTS/literature_registry.json`` (``{id: {title, url, code, ...}}``).

    ``primary_source_read`` is only True when the record explicitly asserts it;
    the registry's presence of a URL is metadata, not proof of full-text review.
    """

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "sources" in payload:
        raw = payload["sources"]
    elif isinstance(payload, dict):
        raw = []
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            entry = dict(value)
            entry.setdefault("id", key)
            raw.append(entry)
    else:
        raw = payload

    records: list[LiteratureRecord] = []
    for e in raw:
        records.append(
            LiteratureRecord(
                id=str(e.get("id", "")),
                title=str(e.get("title", "")),
                venue=str(e.get("venue", "")),
                doi_or_url=str(e.get("doi_or_url") or e.get("url") or ""),
                version=str(e.get("version") or e.get("year") or ""),
                primary_source_read=bool(e.get("primary_source_read", False)),
                code_url=str(e.get("code_url") or e.get("code") or ""),
                guarantee=str(e.get("guarantee") or e.get("relation") or ""),
                relevance=str(e.get("relevance") or e.get("class_") or ""),
                reproduced=bool(e.get("reproduced", False)),
            )
        )
    return records


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 SH-literature_hardening")
    parser.add_argument(
        "--registry", default="research/venue2027/MANIFESTS/literature_registry.json"
    )
    parser.add_argument(
        "--out", default="research/venue2027/_shared/literature_validity_ledger.csv"
    )
    args = parser.parse_args(argv)

    records = load_registry(args.registry)
    result = verify_sources(records)
    Path(args.out).write_text(result.to_csv(), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": result.ok,
                "reason_code": result.reason_code,
                "counts": result.counts,
                "violations": list(result.violations),
                "out": args.out,
                "version": LITERATURE_LEDGER_VERSION,
            },
            indent=2,
        )
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
