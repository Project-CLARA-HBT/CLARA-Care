"""SACMAT-oracle — independent per-case truth oracle for the SACMAT venue.

Purpose
-------
Reference oracle for "PolicyTrace: Temporal Conformance Testing of Delegated
Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ1-RQ3; task
contract ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-oracle.md``). It
adjudicates each synthetic delegated-consent case by DELEGATING to the audited
shared kernel :func:`evaluation.venue2027._shared.oracle_kernel.adjudicate`
with a SACMAT-local declarative rule table. Truth derives ONLY from the
case's declared conformance family — the policy/consent ground truth encoded
by the dataset generator — never from any candidate arm's output or reason
codes. This module must NOT import the SACMAT candidate-side machinery
(``evaluation/venue2027/sacmat/baselines.py`` engine models, B0-B3 arms) nor
the temporal DSL (``evaluation/venue2027/sacmat/policy_trace_dsl.py``);
:func:`verify_independence` machine-checks that invariant (stable reason code
``CANDIDATE_IMPORT``) by scanning this module's source with :mod:`ast` via
:func:`oracle_kernel.assert_oracle_independence`.

SACMAT rule table
-----------------
The dataset kernel's four registered families are the ground-truth signal
(``evaluation/venue2027/_shared/dataset_kernel.py`` VENUE_FAMILIES['sacmat'],
conditioned per ``evaluation/venue2027/sacmat/generate_dataset.py``):

- ``conformant``          -> ADMIT   (grant in force, no skew, no obligation fault)
- ``expiry_divergence``   -> REJECT  (delegation lapsed before the decision time)
- ``policy_skew``         -> REJECT  (policy version at decision time != decision-time version)
- ``obligation_mismatch`` -> REJECT  (purpose/obligation bound to a different grant)
- anything else / undeclared -> INDETERMINATE (kernel: UNMODELLED_FAMILY /
  NO_FAMILY_DECLARED — an unmodelled situation is never silently safe)

Allowed input
-------------
A case ``dict`` carrying ``case_id`` and either a ``family`` or a
``payload.family`` key (kernel contract), plus optional ``evidence`` entries
(``{"uri": ...}``) captured into :attr:`OracleResult.evidence_refs`.

Failure semantics
-----------------
- ``MISSING_CASE_ID`` — kernel raises :class:`oracle_kernel.OracleError` for a
  case without ``case_id`` (wiring error, not an arm outcome).
- ``INDETERMINATE`` — first-class outcome for any undeclared or unknown
  family (kernel reason codes ``NO_FAMILY_DECLARED`` / ``UNMODELLED_FAMILY``);
  never coerced to ADMIT or REJECT.
- ``CANDIDATE_IMPORT`` — :func:`verify_independence` refuses this module if
  its source ever imports a candidate module.

Version
-------
``SACMAT_ORACLE_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027._shared.oracle_kernel import (
    OracleError,
    OracleResult,
)

SACMAT_ORACLE_VERSION: Final[str] = "1.0.0"

ORACLE_ID: Final[str] = "sacmat-conformance-reference"

#: Candidate modules this oracle must never import (baselines arm B0-B3 with
#: the in-process engine models, and the temporal policy-trace DSL). The
#: scanner matches every dotted-path component exactly, so package-qualified
#: and bare-module import forms are both covered.
FORBIDDEN_MODULE_NAMES: Final[tuple[str, ...]] = (
    "sacmat.baselines",
    "baselines",
    "policy_trace_dsl",
)

#: Declarative SACMAT conformance rule table: registered ground-truth family
#: -> kernel outcome. Module-local by design; deliberately NOT derived from
#: nor cross-checked against any candidate/baseline implementation.
SACMAT_RULES: Final[dict[str, oracle_kernel.OracleOutcome]] = {
    "conformant": "ADMIT",
    "expiry_divergence": "REJECT",
    "policy_skew": "REJECT",
    "obligation_mismatch": "REJECT",
}


def adjudicate(case: dict[str, Any]) -> OracleResult:
    """Adjudicate one SACMAT delegated-consent case via the shared kernel.

    Delegates the entire decision to :func:`oracle_kernel.adjudicate` with
    :data:`SACMAT_RULES` and :data:`ORACLE_ID`. Cases whose declared family is
    absent or unmodelled return ``INDETERMINATE`` (kernel reason codes
    ``NO_FAMILY_DECLARED`` / ``UNMODELLED_FAMILY``) — never a silent safe
    verdict. A missing ``case_id`` raises :class:`OracleError` with
    ``MISSING_CASE_ID`` (kernel wiring error).
    """
    return oracle_kernel.adjudicate(case, SACMAT_RULES, oracle_id=ORACLE_ID)


def verify_independence(source: str | None = None) -> None:
    """Refuse any candidate import in this oracle module (fail closed).

    Two layered :mod:`ast` scans, both on ``source`` (the live module by
    default, injected text in tests):

    1. The audited kernel contract :func:`oracle_kernel.assert_oracle_independence`
       — root-component matching plus dynamic-import refusal
       (``DYNAMIC_IMPORT_UNRESOLVABLE``).
    2. A module-local full-target scan that additionally matches every dotted
       import path component (and ``from <module> import <name>`` alias binds)
       against :data:`FORBIDDEN_MODULE_NAMES`, closing the package-qualified
       form (``from evaluation.venue2027.sacmat import baselines``) whose root
       the kernel-level scan legitimately cannot name without forbidding this
       repo's own package root. Matching is exact per dotted component — never
       a substring — so ``sacmat_baseline_helpers``-style names do not trip it.

    Raises :class:`OracleError` with ``CANDIDATE_IMPORT`` naming every
    offending import target.
    """
    if source is None:
        source = Path(__file__).resolve().read_text(encoding="utf-8")
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(source)
        scanned_path = handle.name
    oracle_kernel.assert_oracle_independence(scanned_path, FORBIDDEN_MODULE_NAMES)
    tree = ast.parse(source, filename="<sacmat.independent_oracle>")
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                targets.add(node.module)
            targets.update(alias.name for alias in node.names)
    hits = sorted(
        target for target in targets if any(f in target.split(".") for f in FORBIDDEN_MODULE_NAMES)
    )
    if hits:
        raise OracleError(
            "CANDIDATE_IMPORT",
            f"independent oracle imports candidate module(s): {hits}",
        )


__all__ = [
    "FORBIDDEN_MODULE_NAMES",
    "ORACLE_ID",
    "SACMAT_ORACLE_VERSION",
    "SACMAT_RULES",
    "OracleError",
    "OracleResult",
    "adjudicate",
    "verify_independence",
]
