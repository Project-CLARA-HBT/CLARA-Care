"""PST-oracle — independent per-case truth oracle for the PST venue.

Purpose
-------
Reference oracle for "ReceiptMin: Measuring Forensic Reconstructability under
Purpose-Bound Audit Minimization" (``research/venue2027/VENUES/pst/
RESEARCH_BLUEPRINT.md``, RQ1-RQ3; task contract
``research/venue2027/VENUES/pst/TASKS/PST-oracle.md``). It adjudicates each
synthetic audit-receipt case by DELEGATING to the audited shared kernel
:func:`evaluation.venue2027._shared.oracle_kernel.adjudicate` with a
PST-local declarative rule table. Truth derives ONLY from the case's declared
scenario family — the ground truth encoded by the dataset generator
(``evaluation/venue2027/pst/generate_dataset.py`` over the audited
``evaluation/venue2027/_shared/dataset_kernel.py`` families) — never from any
candidate or baseline arm's output, reason codes or observed artifacts. This
module must NOT import the PST candidate-side machinery
(``evaluation/venue2027/pst/baselines.py`` B0-B4 arms, ``candidate.py`` C0
arm) or any other candidate implementation;
:func:`verify_independence` machine-checks that invariant (stable reason code
``CANDIDATE_IMPORT``) by scanning this module's source with :mod:`ast` via
:func:`oracle_kernel.assert_oracle_independence`.

PST rule table
--------------
The dataset kernel's four registered PST families are the ground-truth signal
(``evaluation/venue2027/_shared/dataset_kernel.py``
VENUE_FAMILIES['pst'] = (full_evidence, minimized_omission, receipt_anchored,
linkability_leak)), mapped to the CASE_MATRIX sentinel semantics:

- ``full_evidence``       -> ADMIT   (legitimate bounded forensic reconstruction
                                       succeeds: complete evidence answers the
                                       declared ex-ante query — PST-CASE-01)
- ``minimized_omission``  -> REJECT  (over-redaction: the minimized receipt
                                       omitted a load-bearing field needed for
                                       valid review; audit incompleteness is
                                       reported as failure, never false
                                       success — PST-CASE-05)
- ``receipt_anchored``    -> ADMIT   (commitment/consent-epoch proofs present
                                       and anchored: tamper-evident witness
                                       validates — PST-CASE-04)
- ``linkability_leak``    -> REJECT  (purpose tag / metadata joins across
                                       extracts disclose attributes —
                                       unlinkability violated — PST-CASE-02/06)
- anything else / undeclared -> INDETERMINATE (kernel: UNMODELLED_FAMILY /
  NO_FAMILY_DECLARED — an unmodelled or key-custody-ambiguous situation
  (PST-CASE-07) is never silently treated as safe)

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
``PST_ORACLE_VERSION = "1.0.0"``.
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

PST_ORACLE_VERSION: Final[str] = "1.0.0"

ORACLE_ID: Final[str] = "pst-forensic-reference"

#: Candidate modules this oracle must never import (the B0-B4 baseline arms in
#: ``baselines.py``, the C0 candidate arm in ``candidate.py``). The scanner
#: matches every dotted-path component exactly, so package-qualified and
#: bare-module import forms are both covered.
FORBIDDEN_MODULE_NAMES: Final[tuple[str, ...]] = (
    "pst.baselines",
    "baselines",
    "candidate",
)

#: Declarative PST forensic reference rule table: registered ground-truth
#: family -> kernel outcome. Module-local by design; deliberately NOT derived
#: from nor cross-checked against any candidate/baseline implementation.
PST_RULES: Final[dict[str, oracle_kernel.OracleOutcome]] = {
    "full_evidence": "ADMIT",
    "minimized_omission": "REJECT",
    "receipt_anchored": "ADMIT",
    "linkability_leak": "REJECT",
}


def adjudicate(case: dict[str, Any]) -> OracleResult:
    """Adjudicate one PST audit-receipt case via the shared kernel.

    Delegates the entire decision to :func:`oracle_kernel.adjudicate` with
    :data:`PST_RULES` and :data:`ORACLE_ID`. Cases whose declared family is
    absent or unmodelled return ``INDETERMINATE`` (kernel reason codes
    ``NO_FAMILY_DECLARED`` / ``UNMODELLED_FAMILY``) — never a silent safe
    verdict. A missing ``case_id`` raises :class:`OracleError` with
    ``MISSING_CASE_ID`` (kernel wiring error).
    """
    return oracle_kernel.adjudicate(case, PST_RULES, oracle_id=ORACLE_ID)


def verify_independence(source: str | None = None) -> None:
    """Refuse any candidate import in this oracle module (fail closed).

    Two layered :mod:`ast` scans, both on ``source`` (the live module by
    default, injected text or a temp-oracle file's text in tests):

    1. The audited kernel contract :func:`oracle_kernel.assert_oracle_independence`
       — root-component matching plus dynamic-import refusal
       (``DYNAMIC_IMPORT_UNRESOLVABLE``).
    2. A module-local full-target scan that additionally matches every dotted
       import path component (and ``from <module> import <name>`` alias binds)
       against :data:`FORBIDDEN_MODULE_NAMES`, closing the package-qualified
       form (``from evaluation.venue2027.pst import baselines``) whose root
       the kernel-level scan legitimately cannot name without forbidding this
       repo's own package root. Matching is exact per dotted component — never
       a substring — so ``pst_baseline_helpers``-style names do not trip it.

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
    tree = ast.parse(source, filename="<pst.independent_oracle>")
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
    "PST_ORACLE_VERSION",
    "PST_RULES",
    "OracleError",
    "OracleResult",
    "adjudicate",
    "verify_independence",
]
