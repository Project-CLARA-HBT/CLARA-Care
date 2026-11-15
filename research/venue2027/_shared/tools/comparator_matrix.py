"""CLARA-Care 2027 shared comparator-matrix contract.

Purpose
-------
Every venue must map its claimed novelty against the strongest *actual* paper or
implementation, with an official source link, the guarantee each comparator
provides, its limitations relative to the candidate, whether runnable code
exists, and a fidelity status. This module makes that machine-checkable and
refuses the two failure modes the execution contract forbids:

1. labelling a competing method "weak" without mechanism analysis, and
2. citing an implementation that does not exist.

Allowed input
-------------
A venue ``literature_matrix.csv`` plus the shared literature registry.

Failure semantics
-----------------
Returns :class:`MatrixResult` with ``ok=False`` and stable reason codes. Never
treats a missing code URL as "available".

Version
-------
``COMPARATOR_MATRIX_VERSION = "1.0.0"``
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import sys
from pathlib import Path

COMPARATOR_MATRIX_VERSION = "1.0.0"

REQUIRED_COLUMNS: tuple[str, ...] = (
    "comparator_id",
    "title",
    "venue",
    "doi_or_url",
    "code_url",
    "algorithm_class",
    "supported_guarantee",
    "limitations_vs_candidate",
    "available_code",
    "fidelity_status",
    "mechanism_analysis",
)

FIDELITY_STATUSES: tuple[str, ...] = (
    "ORIGINAL_UPSTREAM",
    "FAITHFUL_PORT",
    "UNAVAILABLE_NOT_RUN",
)

AVAILABLE_CODE_VALUES: tuple[str, ...] = ("yes", "no", "UNAVAILABLE")

MIN_MECHANISM_CHARS = 40


@dataclasses.dataclass(frozen=True)
class MatrixResult:
    ok: bool
    reason_codes: tuple[str, ...]
    row_count: int
    violations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason_codes": list(self.reason_codes),
            "row_count": self.row_count,
            "violations": list(self.violations),
            "version": COMPARATOR_MATRIX_VERSION,
        }


def load_registry_ids(path: str | Path) -> set[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "sources" in payload:
        return {str(e.get("id", "")) for e in payload["sources"]}
    if isinstance(payload, dict):
        return {str(k) for k, v in payload.items() if isinstance(v, dict)}
    return {str(e.get("id", "")) for e in payload}


def parse_matrix(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def validate_matrix(
    text: str,
    *,
    known_registry_ids: set[str] | None = None,
    allowed_arm_prefix: str = "B",
    min_rows: int = 3,
) -> MatrixResult:
    """Validate a venue comparator matrix.

    ``known_registry_ids`` gates fabricated citations: a comparator id must be a
    real registry id or a local arm id prefixed by ``allowed_arm_prefix``.
    """

    violations: list[str] = []
    reasons: list[str] = []

    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing_cols:
        return MatrixResult(
            False, ("MISSING_COLUMN",), 0, tuple(f"missing column: {c}" for c in missing_cols)
        )

    rows = parse_matrix(text)
    if len(rows) < min_rows:
        reasons.append("TOO_FEW_ROWS")
        violations.append(f"expected at least {min_rows} comparators, found {len(rows)}")

    for index, row in enumerate(rows, start=2):
        cid = (row.get("comparator_id") or "").strip()
        if not cid:
            violations.append(f"row {index}: empty comparator_id")
            continue

        if known_registry_ids is not None:
            is_arm = cid.startswith(allowed_arm_prefix)
            if cid not in known_registry_ids and not is_arm:
                reasons.append("UNKNOWN_COMPARATOR_ID")
                violations.append(
                    f"row {index}: '{cid}' is neither a registry id nor a {allowed_arm_prefix}* arm"
                )

        if not (row.get("doi_or_url") or "").strip():
            reasons.append("MISSING_SOURCE_LINK")
            violations.append(f"row {index} ({cid}): missing doi_or_url")

        mechanism = (row.get("mechanism_analysis") or "").strip()
        if len(mechanism) < MIN_MECHANISM_CHARS:
            reasons.append("MECHANISM_ANALYSIS_MISSING")
            violations.append(
                f"row {index} ({cid}): mechanism_analysis shorter than {MIN_MECHANISM_CHARS} chars"
            )

        available = (row.get("available_code") or "").strip()
        if available not in AVAILABLE_CODE_VALUES:
            reasons.append("INVALID_AVAILABLE_CODE")
            violations.append(f"row {index} ({cid}): available_code {available!r} invalid")
        if available == "yes" and not (row.get("code_url") or "").strip():
            reasons.append("AVAILABLE_CODE_WITHOUT_URL")
            violations.append(f"row {index} ({cid}): available_code=yes requires code_url")

        fidelity = (row.get("fidelity_status") or "").strip()
        if fidelity not in FIDELITY_STATUSES:
            reasons.append("INVALID_FIDELITY_STATUS")
            violations.append(f"row {index} ({cid}): fidelity_status {fidelity!r} invalid")
        if fidelity == "ORIGINAL_UPSTREAM" and available != "yes":
            reasons.append("UPSTREAM_WITHOUT_CODE")
            violations.append(
                f"row {index} ({cid}): ORIGINAL_UPSTREAM requires available_code=yes"
            )
        if fidelity == "FAITHFUL_PORT" and not (row.get("code_url") or "").strip():
            reasons.append("PORT_WITHOUT_CODE")
            violations.append(f"row {index} ({cid}): FAITHFUL_PORT requires code_url")

    unique_reasons = tuple(sorted(set(reasons)))
    return MatrixResult(ok=not violations, reason_codes=unique_reasons, row_count=len(rows), violations=tuple(violations))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 comparator matrix validator")
    parser.add_argument("matrix")
    parser.add_argument(
        "--registry", default="research/venue2027/MANIFESTS/literature_registry.json"
    )
    parser.add_argument("--allow-local-arms", action="store_true", default=True)
    args = parser.parse_args(argv)
    known = load_registry_ids(args.registry) if Path(args.registry).is_file() else None
    result = validate_matrix(
        Path(args.matrix).read_text(encoding="utf-8"), known_registry_ids=known
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
