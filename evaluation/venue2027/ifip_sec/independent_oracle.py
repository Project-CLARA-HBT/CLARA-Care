"""IFIP_SEC-oracle — independent per-case truth oracle (phase P02).

Purpose
-------
Reference truth source for "Replay-Closed Authorization Across Purpose,
Delegation, and AI Proposal Lineage" (research/venue2027/VENUES/ifip_sec/
RESEARCH_BLUEPRINT.md, RQ1-RQ3). It adjudicates a replay/lineage case into
``ADMIT`` / ``REJECT`` / ``INDETERMINATE`` by DELEGATING to the shared
audited kernel :func:`evaluation.venue2027._shared.oracle_kernel.adjudicate`
with a module-local, declarative IFIP reference rule table — never by calling
the candidate mechanism (task IFIP_SEC-candidate, not yet implemented) or any
baseline adapter in this package
(``evaluation.venue2027.ifip_sec.baselines`` /
``evaluation.venue2027.ifip_sec.consistency_token_adapter``). Ground truth
derives only from the frozen event sequence and the declared scenario family
(CASE_MATRIX.md), never from candidate verifier output or candidate reason
codes (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2).

Reference rule table (frozen, IFIP_SEC-CASE-01..09)
---------------------------------------------------
- ``fresh_accept`` -> ``ADMIT`` (CASE-01 legitimate same-purpose execution).
- ``cross_purpose_replay`` -> ``REJECT`` (CASE-02 purpose-domain separation).
- ``delegation_replay`` -> ``REJECT`` (consumed-once invariant; a delegated,
  refreshed or replayed nonce after consumption is never re-admitted).
- ``lineage_splice`` -> ``REJECT`` (provenance binding; splicing an unverified
  parent into a delegated proposal chain breaks ancestry verification).
- Anything else — including the CASE-08 key-rotation family whose
  interpretation is ``DECIDE_BY_SPEC`` — is NOT in the table and therefore
  returns ``INDETERMINATE`` (kernel ``UNMODELLED_FAMILY``): an unmodelled or
  semantically uncertain situation is never silently coerced into a safe
  verdict.

Allowed input
-------------
A JSON-serializable ``case`` dict: ``case_id`` (required, non-empty),
``family`` (top-level or inside ``payload``; required else kernel
``NO_FAMILY_DECLARED``), optional ``evidence`` list of ``{"uri": ...}``
pointers captured verbatim into ``OracleResult.evidence_refs``. No network, no
database, no live provider, no hidden clock or randomness.

Failure semantics
-----------------
- Missing ``case_id`` raises :class:`oracle_kernel.OracleError` with stable
  reason code ``MISSING_CASE_ID`` (a wiring error, not an outcome).
- Unknown/undeclared family returns ``INDETERMINATE`` with ``UNMODELLED_FAMILY``
  or ``NO_FAMILY_DECLARED`` — never a silent safe rejection.
- :func:`verify_independence` parses THIS module's source with :mod:`ast` and
  raises ``OracleError(CANDIDATE_IMPORT)`` if any import targets a candidate
  module (``ifip_sec.baselines`` / ``baselines`` /
  ``consistency_token_adapter``) or performs an unresolvable dynamic import.

Version
-------
``IFIP_INDEPENDENT_ORACLE_VERSION = "clara.ifip_sec.independent-oracle-v1"``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared.oracle_kernel import (
    OracleError,
    OracleResult,
)
from evaluation.venue2027._shared.oracle_kernel import (
    adjudicate as _kernel_adjudicate,
)

IFIP_INDEPENDENT_ORACLE_VERSION: Final[str] = "clara.ifip_sec.independent-oracle-v1"

ORACLE_ID: Final[str] = "ifip-sec-reference"

#: Candidate modules this independent oracle must never import
#: (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2). Dotted candidate paths and
#: their bare basenames are both listed so relative-style imports and
#: ``from <candidate> import x`` alias binds are caught by basename matching.
CANDIDATE_MODULE_NAMES: Final[tuple[str, ...]] = (
    "ifip_sec.baselines",
    "ifip_sec.consistency_token_adapter",
    "baselines",
    "consistency_token_adapter",
)

DYNAMIC_IMPORT_SENTINEL: Final[str] = "__dynamic__"

#: Declarative IFIP reference rule table: scenario family -> outcome.
#: Frozen against CASE_MATRIX.md; deliberately NOT derived from, nor consulted
#: against, any baseline adapter or candidate mechanism. Families absent from
#: this table (e.g. key rotation under CASE-08, whose expected label is
#: ``DECIDE_BY_SPEC``) fall through to ``INDETERMINATE``.
IFIP_REFERENCE_RULES: Final[dict[str, str]] = {
    "fresh_accept": "ADMIT",
    "cross_purpose_replay": "REJECT",
    "delegation_replay": "REJECT",
    "lineage_splice": "REJECT",
}


def adjudicate_case(case: dict[str, Any]) -> OracleResult:
    """Adjudicate ``case`` via the shared kernel and the IFIP rule table.

    Thin venue adapter: all decision logic lives in
    ``evaluation.venue2027._shared.oracle_kernel.adjudicate`` so every venue
    oracle shares one independence guarantee. Unknown families return
    ``INDETERMINATE``; missing ``case_id`` raises ``OracleError``
    (``MISSING_CASE_ID``).
    """
    return _kernel_adjudicate(case, IFIP_REFERENCE_RULES, oracle_id=ORACLE_ID)


# The task contract names the entry point ``adjudicate(case) -> OracleResult``;
# expose the kernel-delegating adapter under that exact symbol.
adjudicate = adjudicate_case


def scan_source_for_candidate_imports(source: str | None = None) -> frozenset[str]:
    """Parse this module's source with ast; return candidate imports found.

    An import is a candidate import if any dotted path component equals a
    candidate basename (``baselines`` / ``consistency_token_adapter``, the
    distinguishing leaf of every entry in :data:`CANDIDATE_MODULE_NAMES`) —
    matching by component (never substring) so look-alike names of unrelated
    modules (``my_baseline_labels``) and this oracle's own package path
    (``evaluation.venue2027.ifip_sec.independent_oracle``) do not trip it.
    Dynamic imports
    (``__import__(...)`` / ``importlib.import_module(...)``) are reported as
    the sentinel ``__dynamic__``: their target is not statically provable, so
    they are flagged for review rather than guessed safe.
    """
    if source is None:
        source = Path(__file__).resolve().read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(__file__))
    forbidden = {name.split(".")[-1] for name in CANDIDATE_MODULE_NAMES}
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(part in forbidden for part in alias.name.split(".")):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # ``from pkg import baselines`` binds the candidate via an alias
            # name; the from-module and every alias are both targets.
            targets = [node.module or ""] + [alias.name for alias in node.names]
            for target in targets:
                if any(part in forbidden for part in target.split(".")):
                    found.add(target)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                found.add(DYNAMIC_IMPORT_SENTINEL)
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "importlib"
            ):
                found.add(DYNAMIC_IMPORT_SENTINEL)
    return frozenset(found)


def verify_independence(source: str | None = None) -> None:
    """Refuse any import of a candidate module in this oracle module.

    Scans this module's *source* (live file by default, injected string in
    tests) with :mod:`ast` — never ``sys.modules`` introspection, so
    independence stays a source-level property independent of import side
    effects. Raises :class:`OracleError` with ``CANDIDATE_IMPORT`` naming
    every offending import target (dynamic imports surface as the
    ``__dynamic__`` sentinel).
    """
    found = scan_source_for_candidate_imports(source)
    if found:
        raise OracleError(
            "CANDIDATE_IMPORT",
            "independent oracle imports candidate module(s) or unresolved "
            f"dynamic import(s): {sorted(found)}",
        )


def run_self_checks() -> tuple[OracleResult, ...]:
    """Deterministic built-in self-checks (one per rule-table row + unknown).

    Returns one :class:`OracleResult` per table row plus one unknown-family
    probe; raises only on internal inconsistency between the frozen rule
    table and the kernel delegation (which would mean the table drifted).
    """
    results = (
        adjudicate_case({"case_id": "selfcheck-fresh", "family": "fresh_accept"}),
        adjudicate_case({"case_id": "selfcheck-purpose", "family": "cross_purpose_replay"}),
        adjudicate_case({"case_id": "selfcheck-delegation", "family": "delegation_replay"}),
        adjudicate_case({"case_id": "selfcheck-lineage", "family": "lineage_splice"}),
        adjudicate_case({"case_id": "selfcheck-unknown", "family": "key_rotation"}),
    )
    expected = ("ADMIT", "REJECT", "REJECT", "REJECT", "INDETERMINATE")
    for result, outcome in zip(results, expected, strict=True):
        if result.outcome != outcome:
            raise OracleError(
                "SELF_CHECK_FAILED",
                f"family {result.case_id!r} adjudicated {result.outcome}, expected {outcome}",
            )
    return results
