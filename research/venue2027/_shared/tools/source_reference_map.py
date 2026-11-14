"""CLARA-Care 2027 shared task SH-source_reference_map.

Purpose
-------
Produce a machine-generated map of every path referenced by the 2027 task
manifest to one of three provenance classes:

- ``VERIFIED_EXISTING`` — the file exists in the checkout (real anchor).
- ``NEW_PROPOSED`` — the path does not exist and must be created by its task.
- ``MISSING_REQUIRED`` — the path is claimed as existing by
  ``MANIFESTS/source_verified.json`` but is absent (hard failure).

This replaces guesswork about "conceptual" APIs with introspection of the real
checkout, as required by the execution contract.

Allowed input
-------------
Repository root plus ``MANIFESTS/tasks.json`` and ``MANIFESTS/source_verified.json``.

Failure semantics
-----------------
A file listed as verified-but-absent yields ``ok=False`` with
``reason_code=MISSING_REQUIRED``; the map is still returned for diagnosis.

Version
-------
``SOURCE_REFERENCE_MAP_VERSION = "1.0.0"``
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import sys
from pathlib import Path

SOURCE_REFERENCE_MAP_VERSION = "1.0.0"

VERIFIED_EXISTING = "VERIFIED_EXISTING"
NEW_PROPOSED = "NEW_PROPOSED"
MISSING_REQUIRED = "MISSING_REQUIRED"


@dataclasses.dataclass(frozen=True)
class SourceRefRow:
    task_id: str
    venue: str
    phase: str
    path: str
    classification: str
    symbol_or_contract: str

    def to_row(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "venue": self.venue,
            "phase": self.phase,
            "path": self.path,
            "classification": self.classification,
            "symbol_or_contract": self.symbol_or_contract,
        }


@dataclasses.dataclass(frozen=True)
class SourceMap:
    ok: bool
    reason_code: str
    rows: tuple[SourceRefRow, ...]
    counts: dict[str, int]
    missing_verified: tuple[str, ...]

    def to_csv(self) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "task_id",
                "venue",
                "phase",
                "path",
                "classification",
                "symbol_or_contract",
            ],
        )
        writer.writeheader()
        for row in self.rows:
            writer.writerow(row.to_row())
        return buffer.getvalue()


def _confined(root: Path, path: str) -> Path | None:
    """Resolve a manifest path inside ``root``; None on escape (auditor F8)."""

    candidate = Path(path)
    if candidate.is_absolute():
        return None
    try:
        resolved_root = root.resolve()
        resolved = (resolved_root / candidate).resolve()
    except (OSError, RuntimeError):
        return None
    if resolved != resolved_root and resolved_root not in resolved.parents:
        return None
    return resolved


def _classify(root: Path, path: str, verified: dict[str, str]) -> str:
    resolved = _confined(root, path)
    exists = resolved is not None and resolved.is_file()
    if path in verified:
        return VERIFIED_EXISTING if exists else MISSING_REQUIRED
    return VERIFIED_EXISTING if exists else NEW_PROPOSED


def map_source(
    repo: str | Path, *, tasks_path: str | Path, verified_path: str | Path
) -> SourceMap:
    """Build the provenance map for every path in the task manifest."""

    root = Path(repo).resolve()
    tasks = json.loads(Path(tasks_path).read_text(encoding="utf-8"))
    verified_payload = json.loads(Path(verified_path).read_text(encoding="utf-8"))
    verified: dict[str, str] = dict(verified_payload.get("paths", {}))

    rows: list[SourceRefRow] = []
    missing: list[str] = []
    counts = {VERIFIED_EXISTING: 0, NEW_PROPOSED: 0, MISSING_REQUIRED: 0}

    for task in tasks:
        symbol = task.get("signature", "") or task.get("title", "")
        for path in task.get("files", []):
            classification = _classify(root, path, verified)
            counts[classification] += 1
            if classification == MISSING_REQUIRED:
                missing.append(path)
            rows.append(
                SourceRefRow(
                    task_id=task["id"],
                    venue=task["venue"],
                    phase=task["phase"],
                    path=path,
                    classification=classification,
                    symbol_or_contract=symbol,
                )
            )

    # Any verified anchor not referenced by a task is still a real anchor and
    # must be reported so the map is complete.
    referenced = {row.path for row in rows}
    for path in verified:
        if path in referenced:
            continue
        classification = _classify(root, path, verified)
        counts[classification] += 1
        if classification == MISSING_REQUIRED:
            missing.append(path)
        rows.append(
            SourceRefRow(
                task_id="(source_verified)",
                venue="shared",
                phase="P00",
                path=path,
                classification=classification,
                symbol_or_contract=verified[path],
            )
        )

    rows.sort(key=lambda r: (r.task_id, r.path))
    ok = not missing
    return SourceMap(
        ok=ok,
        reason_code="OK" if ok else "MISSING_REQUIRED",
        rows=tuple(rows),
        counts=counts,
        missing_verified=tuple(sorted(set(missing))),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 SH-source_reference_map")
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--manifest", default="research/venue2027/MANIFESTS/tasks.json"
    )
    parser.add_argument(
        "--verified", default="research/venue2027/MANIFESTS/source_verified.json"
    )
    parser.add_argument(
        "--out", default="research/venue2027/_shared/source_reference_map.csv"
    )
    args = parser.parse_args(argv)

    result = map_source(args.repo, tasks_path=args.manifest, verified_path=args.verified)
    out = Path(args.repo).resolve() / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.to_csv(), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": result.ok,
                "reason_code": result.reason_code,
                "counts": result.counts,
                "missing_verified": list(result.missing_verified),
                "out": args.out,
                "rows": len(result.rows),
                "version": SOURCE_REFERENCE_MAP_VERSION,
            },
            indent=2,
        )
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
