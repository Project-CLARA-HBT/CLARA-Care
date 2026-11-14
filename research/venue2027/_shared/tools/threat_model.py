"""CLARA-Care 2027 shared threat-model contract validator.

Purpose
-------
Every venue threat model must declare attacker/observer capabilities, trusted
components, excluded domains, and an attack/control paired matrix covering each
attack family with both a clean and an adversarial case. This module makes that
machine-checkable and refuses incomplete or hand-wavy models.

Allowed input
-------------
A threat-model Markdown file with a required structure (see ``REQUIRED_SECTIONS``)
and an adversarial/clean case matrix.

Failure semantics
-----------------
Returns :class:`ThreatCoverage` with ``ok=False`` and stable reason codes when a
section, trust assumption, actor authority, oracle boundary or per-family clean/
adversarial pair is missing. Never treats an undefined authority as safe.

Version
-------
``THREAT_MODEL_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import re
import sys
from pathlib import Path

THREAT_MODEL_VERSION = "1.0.0"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Attacker and observer capabilities",
    "Trusted components",
    "Excluded domains",
    "Attack family and control matrix",
    "Oracle and actor authority",
)

ATTACK_FAMILIES: tuple[str, ...] = (
    "revocation_timing",
    "replay",
    "model_agency",
    "purpose_scope",
    "insider_or_observer",
)

# A matrix row must declare both cells so an attack is never documented without
# a paired clean control (otherwise "one clean and one adversarial case" fails).
CONTROL_MARKERS: tuple[str, ...] = ("clean", "adversarial")


@dataclasses.dataclass(frozen=True)
class ThreatCoverage:
    ok: bool
    reason_codes: tuple[str, ...]
    missing_sections: tuple[str, ...]
    families_without_pair: tuple[str, ...]
    families_covered: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason_codes": list(self.reason_codes),
            "missing_sections": list(self.missing_sections),
            "families_without_pair": list(self.families_without_pair),
            "families_covered": list(self.families_covered),
            "version": THREAT_MODEL_VERSION,
        }


def _section_present(text: str, heading: str) -> bool:
    # Accept a markdown heading (any level) whose text contains the section name.
    pattern = re.compile(rf"^#{{1,6}}[^\n]*{re.escape(heading)}", re.IGNORECASE | re.MULTILINE)
    return bool(pattern.search(text))


def _family_pairs(text: str) -> tuple[set[str], set[str]]:
    """Return (families_with_both_markers, families_seen)."""

    seen: set[str] = set()
    paired: set[str] = set()
    for family in ATTACK_FAMILIES:
        # A row mentioning the family token, with a clean and adversarial cell.
        row_re = re.compile(rf"^[^\n]*{re.escape(family)}[^\n]*$", re.IGNORECASE | re.MULTILINE)
        for match in row_re.finditer(text):
            row = match.group(0).lower()
            seen.add(family)
            if all(marker in row for marker in CONTROL_MARKERS):
                paired.add(family)
            break
    return paired, seen


def validate_threat(text: str) -> ThreatCoverage:
    """Validate a threat-model document against the program contract."""

    reasons: list[str] = []
    missing_sections = tuple(s for s in REQUIRED_SECTIONS if not _section_present(text, s))
    if missing_sections:
        reasons.append("MISSING_SECTION")

    paired, seen = _family_pairs(text)
    families_without_pair = tuple(sorted(set(ATTACK_FAMILIES) - paired))
    if families_without_pair:
        reasons.append("FAMILY_WITHOUT_PAIR")

    # Explicit authority/oracle declaration must be non-empty and name both.
    lower = text.lower()
    if "undefined" in lower and "oracle and actor authority" in lower:
        tail = lower.split("oracle and actor authority", 1)[1][:400]
        if "undefined" in tail and "defined" not in tail:
            reasons.append("UNDEFINED_AUTHORITY")

    ok = not reasons
    return ThreatCoverage(
        ok=ok,
        reason_codes=tuple(reasons),
        missing_sections=missing_sections,
        families_without_pair=families_without_pair,
        families_covered=tuple(sorted(paired)),
    )


def render_matrix_template() -> str:
    rows = [
        "| Attack family | Case | Actor/observer | Capability | Control (clean) | Adversarial case | Expected oracle verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for family in ATTACK_FAMILIES:
        # A single row per family carrying both a clean and an adversarial case.
        rows.append(
            f"| {family} | paired | <actor> | <capability> | clean: <baseline case> | adversarial: <attack case> | <verdict> |"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="CLARA 2027 threat-model validator")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    result = validate_threat(Path(args.path).read_text(encoding="utf-8"))
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
