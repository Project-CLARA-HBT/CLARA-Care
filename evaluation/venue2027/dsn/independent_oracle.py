"""DSN-oracle — independent per-case truth oracle (declarative reference table).

Purpose
-------
Reference oracle for task ``DSN-oracle`` (P02, venue dsn): "Recoverable Safety
Journals for Crash-Consistent AI-Mediated Health-State Mutations"
(research/venue2027/VENUES/dsn/RESEARCH_BLUEPRINT.md, RQ1-RQ3). It maps a case
record's scenario family to exactly one recoverable outcome — ``ADMIT``,
``REJECT`` or ``INDETERMINATE`` — through a *declarative, locally encoded*
reference rule table, delegating adjudication to the audited shared kernel
``evaluation.venue2027._shared.oracle_kernel`` so all venues share one
independence guarantee.

Independence (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2)
------------------------------------------------------------
This module NEVER imports the candidate DSN state machine
(``evaluation/venue2027/dsn/state_machine.py``). :func:`verify_independence`
runs the kernel's AST scan on THIS file for the candidate module names
``('dsn.state_machine', 'state_machine')`` and refuses any static import
(stable reason code ``CANDIDATE_IMPORT``) or any dynamic import call
(``DYNAMIC_IMPORT_UNRESOLVABLE``).

Reference rule table (frozen for the venue)
-------------------------------------------
- ``clean_recovery``  -> ``ADMIT`` — the joint clinical row, decision receipt
  and outbox record agree on one committed operation (DSN-CASE-01).
- ``torn_write``      -> ``REJECT`` — durable evidence proves no consistent
  committed row exists; the reference table refuses phantom user-visible
  success rather than coercing the torn window into a decision (DSN-CASE-02).
- ``duplicate_retry`` -> ``ADMIT`` (idempotent) — a retry keyed by the immutable
  operation ID re-discovers the single committed effect; redelivery never
  doubles the durable effect (DSN-CASE-04/08).
- ``fsync_failure``   -> ``INDETERMINATE`` — a durable failure record alone is
  not reconcilable ground truth for the joint state; fail closed until an
  independent reconciliation exists (DSN-CASE-06 semantics).
- anything else       -> ``INDETERMINATE`` (kernel ``UNMODELLED_FAMILY``) — an
  unmodelled family is never silently treated as safe.

Version
-------
``DSN_ORACLE_VERSION = "clara.dsn.independent-oracle-v1"``. Deterministic and
pure: no clock, no randomness, no I/O beyond reading this module's own source
for the independence scan, no candidate imports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027._shared.oracle_kernel import OracleOutcome, OracleResult

DSN_ORACLE_VERSION: Final[str] = "clara.dsn.independent-oracle-v1"

ORACLE_ID: Final[str] = "dsn-reference"

CANDIDATE_MODULES: Final[tuple[str, ...]] = ("dsn.state_machine", "state_machine")

DSN_RULES: Final[dict[str, OracleOutcome]] = {
    "clean_recovery": "ADMIT",
    "torn_write": "REJECT",
    "duplicate_retry": "ADMIT",
    "fsync_failure": "INDETERMINATE",
}


def adjudicate(case: dict[str, Any]) -> OracleResult:
    """Adjudicate one DSN case record against the frozen reference rule table.

    Delegates to :func:`oracle_kernel.adjudicate`: an unknown family returns
    ``INDETERMINATE`` with ``UNMODELLED_FAMILY`` (a case declaring no family
    returns ``NO_FAMILY_DECLARED``), a case without ``case_id`` raises
    :class:`oracle_kernel.OracleError` with ``MISSING_CASE_ID``, and evidence
    ``uri`` refs are carried into ``OracleResult.evidence_refs``. Pure and
    deterministic: identical inputs always yield an equal result.
    """

    return oracle_kernel.adjudicate(case, DSN_RULES, oracle_id=ORACLE_ID)


def verify_independence() -> None:
    """Refuse any candidate import in THIS oracle module's source.

    Runs the kernel's AST-based
    :func:`oracle_kernel.assert_oracle_independence` on this file for the DSN
    candidate module names; raises :class:`oracle_kernel.OracleError` with
    ``CANDIDATE_IMPORT`` (static import of a candidate module) or
    ``DYNAMIC_IMPORT_UNRESOLVABLE`` (an ``__import__`` / ``import_module``
    call whose target cannot be statically proven safe).
    """

    oracle_kernel.assert_oracle_independence(str(Path(__file__).resolve()), CANDIDATE_MODULES)
