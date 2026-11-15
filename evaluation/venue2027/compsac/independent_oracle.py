"""COMPSAC-oracle — independent FORBIDDEN-COMMIT reference oracle.

Purpose
-------
Per-case truth oracle for "Dependency-Complete Optimistic Admission for
Concurrent Clinical AI Writes" (research/venue2027/VENUES/compsac/
RESEARCH_BLUEPRINT.md, RQ1/RQ2; fixture matrix CASE_MATRIX.md). This module is
the FORBIDDEN-COMMIT adjudicator distinct from
:mod:`evaluation.venue2027.compsac.independent_closure_oracle` (which derives
expected dependency closures). Here every case is adjudicated by *delegating*
to the audited shared kernel :func:`oracle_kernel.adjudicate` with a
declarative, module-local COMPSAC case-outcome rule table: the oracle's
outcome depends only on the case's declared scenario family and the frozen
rule table — never on any candidate arm's reason code, status payload or
internal state (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2: truth labels
derive from event sequence and policy/DB ground truth, not candidate reason
codes). Case families are the kernel-registered COMPSAC families
(``evaluation.venue2027._shared.dataset_kernel.VENUE_FAMILIES["compsac"]``).

Allowed input
-------------
A case record (``dict``) with at least ``case_id`` and a ``family`` (top-level
or under ``payload``), plus optional ``evidence`` (list of ``{"uri": ...}``
dicts) captured by the kernel. Cases must come from the synthetic COMPSAC
dataset (``evaluation/venue2027/compsac/generate_dataset.py``).

Failure semantics
-----------------
Declarative rule table :data:`CASE_OUTCOME_RULES` (FORBIDDEN-COMMIT semantics
per the blueprint falsification criterion):

- ``clean`` -> ``ADMIT`` (a valid write must not be rejected).
- ``omitted_dependency`` -> ``REJECT`` reason ``FORBIDDEN_COMMIT`` (a write
  whose required dependency edge was omitted must never be admitted).
- ``epoch_race`` -> ``REJECT`` (governance epoch changed under the write).
- ``stale_readset`` -> ``REJECT`` (read set no longer current at commit).
- any other / missing family -> ``INDETERMINATE`` (stable kernel reason
  ``UNMODELLED_FAMILY`` / ``NO_FAMILY_DECLARED``) — never silently coerced to
  a safe verdict; a missing ``case_id`` raises ``OracleError``
  ``MISSING_CASE_ID``.

Independence
------------
:func:`verify_independence` parses this module's own source with :mod:`ast`
and refuses any import of the candidate baselines or the dependency DSL
(module roots ``compsac.baselines``, ``baselines``, ``dependency_dsl``) with
the stable reason code ``CANDIDATE_IMPORT``. Dynamic imports
(``__import__`` / ``importlib.import_module``) are flagged
``DYNAMIC_IMPORT_UNRESOLVABLE``: their target is not statically provable, so
they are refused rather than guessed safe. ``ORACLE_KERNEL_VERSION`` of the
delegated kernel is re-exported as ``KERNEL_VERSION`` and stamped into every
result via ``OracleResult.to_dict``.

Version
-------
``FORBIDDEN_COMMIT_ORACLE_VERSION = "clara.compsac.forbidden-commit-oracle-v1"``.
Output is JSON-serializable: ``OracleResult.to_dict`` from the shared kernel.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared import oracle_kernel

FORBIDDEN_COMMIT_ORACLE_VERSION: Final[str] = "clara.compsac.forbidden-commit-oracle-v1"
ORACLE_ID: Final[str] = "compsac-forbidden-commit-reference"

#: Re-export of the audited kernel version delegated to (stamped in results).
KERNEL_VERSION: Final[str] = oracle_kernel.ORACLE_KERNEL_VERSION

#: Candidate modules this independent oracle must never import.
CANDIDATE_MODULE_NAMES: Final[tuple[str, ...]] = (
    "compsac.baselines",
    "baselines",
    "dependency_dsl",
)

#: FORBIDDEN-COMMIT case-outcome rule table (declarative, module-local).
CASE_OUTCOME_RULES: Final[dict[str, oracle_kernel.OracleOutcome]] = {
    "clean": "ADMIT",
    "omitted_dependency": "REJECT",
    "epoch_race": "REJECT",
    "stale_readset": "REJECT",
}

REASON_FORBIDDEN_COMMIT: Final[str] = "FORBIDDEN_COMMIT"
REASON_CANDIDATE_IMPORT: Final[str] = "CANDIDATE_IMPORT"
REASON_DYNAMIC_IMPORT: Final[str] = "DYNAMIC_IMPORT_UNRESOLVABLE"


def adjudicate(case: Mapping[str, Any]) -> oracle_kernel.OracleResult:
    """Adjudicate one case via the shared kernel and the COMPSAC rule table.

    The verdict is a pure function of the case's declared ``family`` and the
    frozen :data:`CASE_OUTCOME_RULES` — candidate reason codes, per-arm status
    payloads and observed outputs are deliberately NOT consulted. Unknown or
    undeclared families return ``INDETERMINATE`` instead of a safe verdict.
    """

    result = oracle_kernel.adjudicate(dict(case), CASE_OUTCOME_RULES, oracle_id=ORACLE_ID)
    if result.outcome == "REJECT":
        return oracle_kernel.OracleResult(
            case_id=result.case_id,
            outcome=result.outcome,
            reason_code=REASON_FORBIDDEN_COMMIT,
            evidence_refs=result.evidence_refs,
            oracle_id=result.oracle_id,
        )
    return result


def verify_independence(source: str | None = None, oracle_path: str | None = None) -> None:
    """Fail closed if this oracle imports a candidate module or dynamic import.

    Parses source (live file by default, injected string in tamper tests) with
    :mod:`ast` via :func:`oracle_kernel.assert_oracle_independence`, which
    raises ``OracleError`` with a stable reason code:

    - ``CANDIDATE_IMPORT`` — any import whose root matches a candidate module
      name (``compsac.baselines`` / ``baselines`` / ``dependency_dsl``).
    - ``DYNAMIC_IMPORT_UNRESOLVABLE`` — any ``__import__`` /
      ``importlib.import_module`` call, whose target cannot be statically
      proven independent.

    Independence is a source-level property; never decided by runtime import
    bookkeeping.
    """

    path = oracle_path or str(Path(__file__).resolve())
    tree_source = source
    if tree_source is None:
        tree_source = Path(path).read_text(encoding="utf-8")
    # The kernel guard matches import roots only (``import baselines``). A
    # dotted candidate path such as ``compsac.baselines`` or
    # ``...compsac.dependency_dsl`` has a benign root, so this module adds a
    # component-wise scan: any import target with a dotted-path component
    # equal to a candidate module name is a candidate import (exact component
    # match, never substring — ``test_dependency_dsl`` stays clean).
    import ast

    tree = ast.parse(tree_source, filename=path)
    offenders: list[str] = []
    for node in ast.walk(tree):
        targets: list[str] = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                targets.append(node.module)
            targets.extend(alias.name for alias in node.names)
        for target in targets:
            if any(part in CANDIDATE_MODULE_NAMES for part in target.split(".")):
                offenders.append(target)
    if offenders:
        raise oracle_kernel.OracleError(
            REASON_CANDIDATE_IMPORT,
            f"independent oracle imports candidate module(s): {sorted(offenders)}",
        )
    # Delegate the remaining kernel checks (root-level imports, dynamic
    # imports) to the audited kernel guard.
    try:
        oracle_kernel.assert_oracle_independence(path, CANDIDATE_MODULE_NAMES)
    except oracle_kernel.OracleError as exc:
        raise oracle_kernel.OracleError(exc.reason_code, exc.detail) from exc


def run_self_checks() -> tuple[oracle_kernel.OracleResult, ...]:
    """Deterministic built-in self-checks, one per modelled family.

    Raises ``OracleError`` if any self-check disagrees with the frozen rule
    table (would mean table and delegation drifted apart).
    """

    expected = {
        "clean": "ADMIT",
        "omitted_dependency": "REJECT",
        "epoch_race": "REJECT",
        "stale_readset": "REJECT",
    }
    results = tuple(
        adjudicate({"case_id": f"selfcheck-{family}", "family": family})
        for family in CASE_OUTCOME_RULES
    )
    for result in results:
        if result.outcome != expected[result.case_id.removeprefix("selfcheck-")]:
            raise oracle_kernel.OracleError(
                "SELF_CHECK_MISMATCH",
                f"{result.case_id}: {result.outcome} != {expected[result.case_id.removeprefix('selfcheck-')]}",
            )
    return results


if __name__ == "__main__":  # pragma: no cover
    verify_independence()
    for check in run_self_checks():
        print(check.to_dict())
