"""CLARA-Care 2027 shared overlap-audit contract.

Purpose
-------
Enforce the anti-salami firewall at document level: every venue's
``overlap_audit.md`` must compare against all nine sibling venues and the
historical corpus (GLHS R4, GovRed, GovMut, CareGuard, HEALTHINF), explicitly
refuse reuse of frozen E15-E22 evidence, and end with a single decision.

Allowed input
-------------
A venue ``overlap_audit.md`` plus the canonical list of siblings/historical ids.

Failure semantics
-----------------
Returns :class:`OverlapAuditResult` with ``ok=False`` and stable reason codes.
A missing sibling or a missing archive refusal is never treated as non-overlap.

Version
-------
``OVERLAP_AUDIT_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from pathlib import Path

OVERLAP_AUDIT_VERSION = "1.0.0"

ALL_VENUES: tuple[str, ...] = (
    "compsac",
    "popets",
    "aime",
    "ifip_sec",
    "sacmat",
    "acns",
    "dsn",
    "dimva",
    "pst",
)

# Human-facing labels that may appear in prose instead of the slug.
VENUE_LABELS: dict[str, tuple[str, ...]] = {
    "compsac": ("compsac",),
    "popets": ("popets", "pets"),
    "aime": ("aime",),
    "ifip_sec": ("ifip sec", "ifip_sec", "ifipsec", "sec 2027"),
    "sacmat": ("sacmat",),
    "acns": ("acns",),
    "dsn": ("dsn",),
    "dimva": ("dimva",),
    "pst": ("pst",),
}

HISTORICAL_IDS: tuple[str, ...] = (
    "glhs",
    "govred",
    "govmut",
    "careguard",
    "healthinf",
)

FROZEN_MARKERS: tuple[str, ...] = ("e15", "e22", "e15-e22", "e15–e22")

DECISION_RE = re.compile(r"^\s*decision\s*:\s*(pass|merge-alternative|no-go)\b", re.IGNORECASE | re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class OverlapAuditResult:
    ok: bool
    reason_codes: tuple[str, ...]
    missing_venues: tuple[str, ...]
    missing_historical: tuple[str, ...]
    has_frozen_refusal: bool
    has_decision: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason_codes": list(self.reason_codes),
            "missing_venues": list(self.missing_venues),
            "missing_historical": list(self.missing_historical),
            "has_frozen_refusal": self.has_frozen_refusal,
            "has_decision": self.has_decision,
            "version": OVERLAP_AUDIT_VERSION,
        }


def _mentions(text: str, labels: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(label in lower for label in labels)


def audit_overlap_document(text: str, *, venue: str) -> OverlapAuditResult:
    """Validate one venue overlap audit against the program firewall."""

    reasons: list[str] = []
    lower = text.lower()

    siblings = [v for v in ALL_VENUES if v != venue]
    missing_venues = tuple(v for v in siblings if not _mentions(text, VENUE_LABELS[v]))
    if missing_venues:
        reasons.append("MISSING_SIBLING_VENUE")

    missing_historical = tuple(h for h in HISTORICAL_IDS if h not in lower)
    if missing_historical:
        reasons.append("MISSING_HISTORICAL_COMPARISON")

    has_frozen_refusal = any(marker in lower for marker in FROZEN_MARKERS) and (
        "not reuse" in lower
        or "not reused" in lower
        or "refus" in lower
        or "not presented" in lower
    )
    if not has_frozen_refusal:
        reasons.append("MISSING_FROZEN_REFUSAL")

    has_decision = bool(DECISION_RE.search(text))
    if not has_decision:
        reasons.append("MISSING_DECISION")

    return OverlapAuditResult(
        ok=not reasons,
        reason_codes=tuple(sorted(set(reasons))),
        missing_venues=missing_venues,
        missing_historical=missing_historical,
        has_frozen_refusal=has_frozen_refusal,
        has_decision=has_decision,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 overlap audit validator")
    parser.add_argument("path")
    parser.add_argument("--venue", required=True)
    args = parser.parse_args(argv)
    result = audit_overlap_document(Path(args.path).read_text(encoding="utf-8"), venue=args.venue)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
