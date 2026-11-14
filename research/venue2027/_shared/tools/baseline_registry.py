"""CLARA-Care 2027 shared task SH-baseline_registry.

Purpose
-------
Machine-checkable provenance registry for every strong-baseline comparator
used across the nine venue studies. Backed by
``research/venue2027/_shared/baselines/registry.yaml``.

The registry enforces EXECUTION_CONTRACT.md rule 8: *never replace an
unavailable baseline with a custom toy and keep the same name*. Honesty is a
hard property: any entry that mislabels a stub as a full baseline, ports
without parity fixtures, claims verification without a pinned revision, or
omits a license must FAIL the audit — never pass silently.

Allowed input
-------------
A YAML document (mapping) with a ``baselines`` list, either loaded from disk
by :func:`load_registry` or built in memory as ``Entry`` objects via
:func:`register_baseline`. No network access, no clock, no randomness; all
I/O is caller-injected (path argument).

Failure semantics
-----------------
:func:`audit_registry` returns :class:`Findings`; it never raises for
contents of the registry. Each violation carries a stable ``reason_code``:

- ``STUB_PRESENTED_AS_BASELINE``   — an entry declares a full/original or
  faithful implementation but its notes/config disclose stub semantics
  (constant deny, no-op, toy) or it is flagged as such via
  ``declared_stub=True``.
- ``FAITHFUL_PORT_WITHOUT_FIXTURE`` — a ``FAITHFUL_PORT`` entry lacks a
  parity fixture reference.
- ``VERIFIED_FIDELITY_UNAVAILABLE_REVISION`` — a ``FAITHFUL_PORT`` or
  ``ORIGINAL_UPSTREAM`` entry whose ``upstream_revision`` is ``UNAVAILABLE``.
- ``MISSING_LICENSE`` — no license declared (empty or placeholder) while
  claiming to be runnable.
- ``UNKNOWN_FIDELITY_STATUS`` / ``MISSING_FIELD`` — schema violations.

Version
-------
``BASELINE_REGISTRY_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Literal

BASELINE_REGISTRY_VERSION = "1.0.0"

REVISION_UNAVAILABLE = "UNAVAILABLE"

FidelityStatus = Literal["ORIGINAL_UPSTREAM", "FAITHFUL_PORT", "UNAVAILABLE_NOT_RUN"]
ALLOWED_FIDELITY_STATUSES: tuple[str, ...] = (
    "ORIGINAL_UPSTREAM",
    "FAITHFUL_PORT",
    "UNAVAILABLE_NOT_RUN",
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "name",
    "venues",
    "upstream_url",
    "upstream_revision",
    "license",
    "algorithm_class",
    "config",
    "data_rights",
    "parity_fixture",
    "exec_command",
    "fidelity_status",
)

ReasonCode = Literal[
    "OK",
    "MISSING_FIELD",
    "UNKNOWN_FIDELITY_STATUS",
    "STUB_PRESENTED_AS_BASELINE",
    "FAITHFUL_PORT_WITHOUT_FIXTURE",
    "VERIFIED_FIDELITY_UNAVAILABLE_REVISION",
    "MISSING_LICENSE",
    "DUPLICATE_BASELINE_NAME",
]

# Words that disclose stub/toy semantics. If any of them appears in the
# notes/config of an entry that pretends to be a full baseline
# (ORIGINAL_UPSTREAM / FAITHFUL_PORT), the entry is a mislabelled stub.
_STUB_DISCLOSURE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"\bconstant deny\b",
        r"\bconstant-deny\b",
        r"\balways (?:return|returns|deny|denies|reject)\b",
        r"\breturn[s]? a constant\b",
        r"\bno-?op (?:implementation|baseline|stub)\b",
        r"\bstub (?:implementation|baseline)\b",
        r"\btoy (?:implementation|baseline|replacement|substitute|stand-?in)\b",
        r"\btoy replacement\b",
        r"\breplacement (?:implementation|baseline)\b",
        r"\bplaceholder implementation\b",
        r"\bnot (?:actually )?implemented\b",
        r"\bmerely returns\b",
    )
)

_LICENSE_PLACEHOLDERS = ("", "tbd", "todo", "n/a", "unknown", "none")


@dataclasses.dataclass(frozen=True)
class Entry:
    """One registered baseline comparator (JSON-serializable)."""

    name: str
    venues: tuple[str, ...]
    upstream_url: str
    upstream_revision: str
    license: str
    algorithm_class: str
    config: str
    data_rights: str
    parity_fixture: str
    exec_command: str
    fidelity_status: FidelityStatus
    notes: str = ""
    declared_stub: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "venues": list(self.venues),
            "upstream_url": self.upstream_url,
            "upstream_revision": self.upstream_revision,
            "license": self.license,
            "algorithm_class": self.algorithm_class,
            "config": self.config,
            "data_rights": self.data_rights,
            "parity_fixture": self.parity_fixture,
            "exec_command": self.exec_command,
            "fidelity_status": self.fidelity_status,
            "notes": self.notes,
            "declared_stub": self.declared_stub,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclasses.dataclass(frozen=True)
class Finding:
    reason_code: ReasonCode
    baseline: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "baseline": self.baseline,
            "detail": self.detail,
        }


@dataclasses.dataclass(frozen=True)
class Findings:
    """Audit result: ``ok=False`` iff any violation was found."""

    ok: bool
    reason_code: ReasonCode
    findings: tuple[Finding, ...]
    entries_audited: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason_code": self.reason_code,
            "entries_audited": self.entries_audited,
            "findings": [f.to_dict() for f in self.findings],
            "version": BASELINE_REGISTRY_VERSION,
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class BaselineRegistryError(ValueError):
    """Raised only for caller programming errors (bad argument types)."""

    def __init__(self, reason_code: ReasonCode, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _coerce_venues(venues: Sequence[str] | str) -> tuple[str, ...]:
    if isinstance(venues, str):
        venues = [venues]
    if not venues:
        raise BaselineRegistryError("MISSING_FIELD", "venues must be non-empty")
    return tuple(str(v) for v in venues)


def register_baseline(
    name: str,
    revision: str,
    *,
    venues: Sequence[str] | str,
    upstream_url: str,
    license: str,  # noqa: A002 - registry field name is "license"
    algorithm_class: str,
    config: str,
    data_rights: str,
    parity_fixture: str,
    exec_command: str,
    fidelity_status: FidelityStatus,
    notes: str = "",
    declared_stub: bool = False,
) -> Entry:
    """Create one registry ``Entry`` (pure function; no I/O).

    ``revision`` is the pinned upstream revision, or the literal
    ``"UNAVAILABLE"`` when none could be verified. Nothing else is accepted
    as "unknown": callers must never guess a hash.
    """
    if not name or not str(name).strip():
        raise BaselineRegistryError("MISSING_FIELD", "name is required")
    if fidelity_status not in ALLOWED_FIDELITY_STATUSES:
        raise BaselineRegistryError(
            "UNKNOWN_FIDELITY_STATUS",
            f"fidelity_status must be one of {ALLOWED_FIDELITY_STATUSES}, got {fidelity_status!r}",
        )
    if revision != REVISION_UNAVAILABLE and not str(revision).strip():
        raise BaselineRegistryError(
            "MISSING_FIELD",
            "revision must be a non-empty pinned identifier or the literal 'UNAVAILABLE'",
        )
    return Entry(
        name=str(name).strip(),
        venues=_coerce_venues(venues),
        upstream_url=str(upstream_url or ""),
        upstream_revision=str(revision).strip(),
        license=str(license or ""),
        algorithm_class=str(algorithm_class or ""),
        config=str(config or ""),
        data_rights=str(data_rights or ""),
        parity_fixture=str(parity_fixture or ""),
        exec_command=str(exec_command or ""),
        fidelity_status=fidelity_status,
        notes=str(notes or ""),
        declared_stub=bool(declared_stub),
    )


def _looks_like_stub(entry: Entry) -> bool | None:
    """Three-valued stub detection.

    Returns True when the entry is provably a stub presented as a full
    baseline, None when it honestly labels itself as not-yet-run, and the
    value of ``entry.declared_stub`` otherwise.
    """
    if entry.fidelity_status == "UNAVAILABLE_NOT_RUN":
        # Honest non-claim: cannot be "presented as" a full baseline.
        return None
    if entry.declared_stub:
        return True
    haystack = " ".join((entry.config, entry.notes, entry.algorithm_class))
    return any(p.search(haystack) for p in _STUB_DISCLOSURE_PATTERNS)


def _license_is_missing(license_field: str) -> bool:
    return license_field.strip().lower() in _LICENSE_PLACEHOLDERS


def audit_registry(entries: Iterable[Entry]) -> Findings:
    """Audit entries against the honesty invariants. Pure; never raises.

    Fails on:
    - a stub/constant-deny implementation labelled as a full baseline,
    - a ``FAITHFUL_PORT`` without a parity fixture reference,
    - a VERIFIED fidelity (``FAITHFUL_PORT``/``ORIGINAL_UPSTREAM``) with an
      ``UNAVAILABLE`` revision,
    - a missing license on an entry that claims runnable fidelity.
    """
    findings: list[Finding] = []
    seen_names: dict[str, str] = {}
    audited = 0
    for entry in entries:
        if not isinstance(entry, Entry):  # defensive: reject foreign objects
            findings.append(
                Finding(
                    "MISSING_FIELD",
                    "<non-entry>",
                    f"object of type {type(entry).__name__} is not an Entry",
                )
            )
            continue
        audited += 1

        if not entry.name:
            findings.append(Finding("MISSING_FIELD", "<unnamed>", "entry has no name"))
            continue

        if entry.name in seen_names:
            findings.append(
                Finding(
                    "DUPLICATE_BASELINE_NAME",
                    entry.name,
                    f"duplicate of entry first seen for venue(s) {seen_names[entry.name]}",
                )
            )
        else:
            seen_names[entry.name] = ",".join(entry.venues)

        stub = _looks_like_stub(entry)
        if stub is True:
            findings.append(
                Finding(
                    "STUB_PRESENTED_AS_BASELINE",
                    entry.name,
                    "entry claims full fidelity but discloses stub/constant-deny/toy semantics",
                )
            )

        if entry.fidelity_status == "FAITHFUL_PORT" and not entry.parity_fixture.strip():
            findings.append(
                Finding(
                    "FAITHFUL_PORT_WITHOUT_FIXTURE",
                    entry.name,
                    "FAITHFUL_PORT requires a parity fixture reference",
                )
            )

        if (
            entry.fidelity_status in ("FAITHFUL_PORT", "ORIGINAL_UPSTREAM")
            and entry.upstream_revision == REVISION_UNAVAILABLE
        ):
            findings.append(
                Finding(
                    "VERIFIED_FIDELITY_UNAVAILABLE_REVISION",
                    entry.name,
                    "verified fidelity claims require a pinned upstream revision",
                )
            )

        if entry.fidelity_status in ("FAITHFUL_PORT", "ORIGINAL_UPSTREAM") and _license_is_missing(
            entry.license
        ):
            findings.append(
                Finding(
                    "MISSING_LICENSE",
                    entry.name,
                    "runnable baseline entries must declare a license",
                )
            )

        if entry.fidelity_status not in ALLOWED_FIDELITY_STATUSES:
            findings.append(
                Finding(
                    "UNKNOWN_FIDELITY_STATUS",
                    entry.name,
                    f"fidelity_status {entry.fidelity_status!r} not in {ALLOWED_FIDELITY_STATUSES}",
                )
            )

    ok = not findings
    return Findings(
        ok=ok,
        reason_code="OK" if ok else findings[0].reason_code,
        findings=tuple(findings),
        entries_audited=audited,
    )


def entry_from_mapping(raw: dict[str, Any]) -> Entry:
    """Build an Entry from a YAML mapping, tolerating missing optional keys."""
    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise BaselineRegistryError(
            "MISSING_FIELD",
            f"entry {raw.get('name', '<unnamed>')!r} missing fields: {missing}",
        )
    return Entry(
        name=str(raw["name"]).strip(),
        venues=_coerce_venues(raw["venues"]),
        upstream_url=str(raw["upstream_url"] or ""),
        upstream_revision=str(raw["upstream_revision"]).strip(),
        license=str(raw["license"] or ""),
        algorithm_class=str(raw["algorithm_class"] or ""),
        config=str(raw["config"] or ""),
        data_rights=str(raw["data_rights"] or ""),
        parity_fixture=str(raw["parity_fixture"] or ""),
        exec_command=str(raw["exec_command"] or ""),
        fidelity_status=raw["fidelity_status"],  # type: ignore[arg-type]
        notes=str(raw.get("notes", "") or ""),
        declared_stub=bool(raw.get("declared_stub", False)),
    )


def load_registry(path: str | Path) -> list[Entry]:
    """Load and validate entries from the registry YAML file.

    Fails closed: malformed entries raise :class:`BaselineRegistryError` with
    a stable reason code rather than being silently skipped.
    """
    import yaml  # local import: dependency is optional for pure-function use

    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("baselines"), list):
        raise BaselineRegistryError(
            "MISSING_FIELD", "registry must be a mapping with a 'baselines' list"
        )
    return [entry_from_mapping(raw) for raw in payload["baselines"]]


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="CLARA 2027 SH-baseline_registry auditor",
    )
    parser.add_argument(
        "--registry",
        default="research/venue2027/_shared/baselines/registry.yaml",
        help="Path to registry.yaml (default: shared registry)",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write the audit result JSON",
    )
    args = parser.parse_args(argv)

    entries = load_registry(args.registry)
    result = audit_registry(entries)
    payload = result.to_dict()
    payload["registry"] = str(args.registry)
    if args.json_out:
        Path(args.json_out).write_text(result.to_json() + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
