"""CLARA-Care 2027 shared independent-oracle kernel.

Purpose
-------
Every venue's ``independent_oracle.py`` must adjudicate cases WITHOUT importing
any candidate implementation, and must classify ambiguous outcomes as
``INDETERMINATE`` rather than coercing them to a decision. This kernel provides
the audited base so all nine oracles share one independence guarantee.

Allowed input
-------------
A case record (dict) and a declarative reference rule table local to the venue.

Failure semantics
-----------------
- An oracle module that imports a candidate module is refused by
  :func:`assert_oracle_independence` (stable ``CANDIDATE_IMPORT``).
- Unknown/ambiguous cases return ``INDETERMINATE``; never a silent safe verdict.

Version
-------
``ORACLE_KERNEL_VERSION = "1.0.0"``
"""

from __future__ import annotations

import ast
import dataclasses
from typing import Any, Literal

ORACLE_KERNEL_VERSION = "1.0.0"

OracleOutcome = Literal["ADMIT", "REJECT", "INDETERMINATE"]


class OracleError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class OracleResult:
    case_id: str
    outcome: OracleOutcome
    reason_code: str
    evidence_refs: tuple[str, ...] = ()
    oracle_id: str = "reference"

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "evidence_refs": list(self.evidence_refs),
            "oracle_id": self.oracle_id,
            "kernel_version": ORACLE_KERNEL_VERSION,
        }


def adjudicate(case: dict[str, Any], rules: dict[str, OracleOutcome], *, oracle_id: str) -> OracleResult:
    """Adjudicate ``case`` using a declarative family->outcome rule table.

    A case whose ``family`` is not in ``rules`` is ``INDETERMINATE`` so an
    unmodelled situation can never be silently treated as safe.
    """

    case_id = str(case.get("case_id", ""))
    family = case.get("family", case.get("payload", {}).get("family"))
    if not case_id:
        raise OracleError("MISSING_CASE_ID", "case has no case_id")
    if family is None:
        return OracleResult(
            case_id=case_id,
            outcome="INDETERMINATE",
            reason_code="NO_FAMILY_DECLARED",
            oracle_id=oracle_id,
        )
    outcome = rules.get(str(family))
    if outcome is None:
        return OracleResult(
            case_id=case_id,
            outcome="INDETERMINATE",
            reason_code="UNMODELLED_FAMILY",
            oracle_id=oracle_id,
        )
    evidence = tuple(
        str(e.get("uri", "")) for e in case.get("evidence", []) if isinstance(e, dict)
    )
    return OracleResult(
        case_id=case_id,
        outcome=outcome,
        reason_code=f"RULE_{family.upper()}",
        evidence_refs=evidence,
        oracle_id=oracle_id,
    )


def assert_oracle_independence(oracle_path: str, candidate_module_names: tuple[str, ...]) -> None:
    """Parse ``oracle_path`` and refuse any import of a candidate module.

    Uses ``ast`` so aliases and ``from x import y`` forms are caught. Dynamic
    imports are flagged for human review rather than silently allowed.
    """

    from pathlib import Path

    source = Path(oracle_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=oracle_path)
    forbidden = {"candidate", *candidate_module_names}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden:
                    raise OracleError("CANDIDATE_IMPORT", f"oracle imports {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in forbidden:
                raise OracleError("CANDIDATE_IMPORT", f"oracle imports from {node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", getattr(func, "id", ""))
            if name in {"__import__", "import_module"}:
                raise OracleError(
                    "DYNAMIC_IMPORT_UNRESOLVABLE",
                    "dynamic import prevents independence verification",
                )
