"""ACNS-oracle — independent evidence-boundary truth oracle (SoK reference).

Purpose
-------
Task ACNS-oracle (Phase P02, venue acns): the independent per-case truth oracle
for "SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems"
(``research/venue2027/VENUES/acns/RESEARCH_BLUEPRINT.md``, RQ1-RQ3). It derives
the frozen ``truth.json`` label for a case from a *declarative, locally
encoded* evidence-boundary rule table — never by importing or calling any
candidate implementation (``evaluation/venue2027/acns/baselines.py`` and every
other baseline module). The oracle expresses an **evidence-boundary verdict**
(which claim the frozen evidence supports, where the claimed implication breaks,
which pre-registered gap G1-G9 applies) — a SoK judgment about claim-vs-evidence
scope, **not** a mechanism outcome (never "the tool ran" / "the pipeline
succeeded"). Ground truth derives only from the frozen threat-model register
(``research/venue2027/acns/threat_model.md`` §2/§6, TC5/TC6): candidate-supplied
verdict fields inside a case cannot influence the label, so circular label
generation is impossible by construction.

Adjudication is delegated to the audited shared kernel
(:mod:`evaluation.venue2027._shared.oracle_kernel`); this module contributes
only the venue's rule table and independence verification
(``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rule 2: an
independent oracle must not import any candidate code).

Allowed input
-------------
``case``: a JSON-serializable mapping with a non-empty ``case_id``, a declared
evidence ``family`` (top-level or nested under ``payload``) and an optional
``evidence`` list of ``{"uri": ...}`` pointers carried through as
``evidence_refs``. Any extra fields (including candidate-supplied decision
fields) are ignored by design.

Rule table (pre-registered ACNS evidence-boundary families)
-----------------------------------------------------------
- ``bound_evidence``       -> ``ADMIT``  (clean control; claim stays within the
  boundary its bound, verified receipt supports)
- ``attestation_downgrade`` -> ``REJECT`` (gap G2: a provider receipt quoted as
  execution proof; absent TC3 the claim is capped at L2)
- ``unbound_claim``        -> ``REJECT`` (gap G7/G9: asserted level with no
  evidence binding on its dimension)
- ``replayed_receipt``     -> ``REJECT`` (gap G4: signature-valid,
  context-invalid transplanted receipt)
- anything else            -> ``INDETERMINATE`` (``UNMODELLED_FAMILY`` /
  ``NO_FAMILY_DECLARED``); never coerced to a safe verdict

Failure semantics (stable reason codes)
---------------------------------------
- ``MALFORMED_CASE`` — ``case`` is not a mapping; refused, never silently read.
- ``MISSING_CASE_ID`` — kernel refuses a case without ``case_id``.
- ``NO_FAMILY_DECLARED`` / ``UNMODELLED_FAMILY`` — ``INDETERMINATE`` outcome
  with ``gap_code=PENDING_ADJUDICATION``: a first-class outcome that is never
  counted as a safe rejection or a completion (false-zero ban).
- ``ORACLE_RULE_DRIFT`` — internal inconsistency between the kernel rule table
  and the boundary table (self-checks fail closed rather than emit a label).
- ``CANDIDATE_IMPORT`` — :func:`verify_independence` detected an import of a
  candidate baseline module (``acns.baselines`` / any ``baselines`` module) or
  an unresolvable dynamic import in this file.

Version
-------
``ACNS_INDEPENDENT_ORACLE_VERSION = "1.0.0"``. Output is JSON-serializable via
:meth:`OracleResult.to_dict` and :meth:`EvidenceBoundaryOracleVerdict.to_dict`.
"""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027._shared.oracle_kernel import (
    ORACLE_KERNEL_VERSION,
    OracleError,
    OracleOutcome,
    OracleResult,
)

ACNS_INDEPENDENT_ORACLE_VERSION: Final[str] = "1.0.0"

#: Stable oracle identity carried on every emitted verdict.
ORACLE_ID: Final[str] = "acns-evidence-boundary-reference"

#: Pre-registered ACNS evidence-boundary families (kernel rule table).
FAMILY_BOUND_EVIDENCE: Final[str] = "bound_evidence"
FAMILY_ATTESTATION_DOWNGRADE: Final[str] = "attestation_downgrade"
FAMILY_UNBOUND_CLAIM: Final[str] = "unbound_claim"
FAMILY_REPLAYED_RECEIPT: Final[str] = "replayed_receipt"

#: Declarative family -> outcome rule table handed to the shared kernel.
#: Deliberately module-local: it is the frozen truth source (TC6), not derived
#: from, nor cross-checked against, any candidate classifier.
ACNS_EVIDENCE_BOUNDARY_RULES: Final[Mapping[str, OracleOutcome]] = {
    FAMILY_BOUND_EVIDENCE: "ADMIT",
    FAMILY_ATTESTATION_DOWNGRADE: "REJECT",
    FAMILY_UNBOUND_CLAIM: "REJECT",
    FAMILY_REPLAYED_RECEIPT: "REJECT",
}

#: Gap codes of the pre-registered evidence-boundary register (threat model §6,
#: G1-G9) used by this rule table, restated locally (never imported from a
#: candidate module). "none" marks the clean control.
GAP_NONE: Final[str] = "none"
GAP_G2_RECEIPT_AS_EXECUTION: Final[str] = "G2_RECEIPT_AS_EXECUTION"
GAP_G4_SIGNATURE_AS_CONTEXT: Final[str] = "G4_SIGNATURE_AS_CONTEXT"
GAP_G7_LEVEL_IMPLICIT_UPGRADE: Final[str] = "G7_LEVEL_IMPLICIT_UPGRADE"
GAP_PENDING_ADJUDICATION: Final[str] = "PENDING_ADJUDICATION"

REGISTERED_GAP_CODES: Final[frozenset[str]] = frozenset(
    {
        GAP_NONE,
        GAP_G2_RECEIPT_AS_EXECUTION,
        GAP_G4_SIGNATURE_AS_CONTEXT,
        GAP_G7_LEVEL_IMPLICIT_UPGRADE,
        GAP_PENDING_ADJUDICATION,
    }
)


@dataclasses.dataclass(frozen=True)
class BoundaryRule:
    """One declarative row of the evidence-boundary table (SoK semantics).

    ``granted_level`` is the highest lattice level (threat model §1.2) the
    frozen evidence supports for the family, ``refused_claim`` names the claim
    the evidence does *not* support (the boundary), ``gap_code`` is the
    pre-registered register entry (or ``none``), and ``boundary_condition``
    states the trust assumption whose absence makes the implication fail.
    """

    granted_level: str
    refused_claim: str
    gap_code: str
    boundary_condition: str


#: Evidence-boundary table: family -> the SoK verdict content (module-local,
#: frozen before execution; never repaired to match any candidate output).
BOUNDARY_TABLE: Final[Mapping[str, BoundaryRule]] = {
    FAMILY_BOUND_EVIDENCE: BoundaryRule(
        granted_level="L2-ACKNOWLEDGED",
        refused_claim="the model executed the tool",
        gap_code=GAP_NONE,
        boundary_condition=(
            "TC2 full check chain (pinned-root signature, digest binding, "
            "nonce/context, purpose scope, verification-time schedule) passes; "
            "the bound receipt supports only the acknowledged-receipt claim"
        ),
    ),
    FAMILY_ATTESTATION_DOWNGRADE: BoundaryRule(
        granted_level="L2-ACKNOWLEDGED",
        refused_claim="the model executed the tool",
        gap_code=GAP_G2_RECEIPT_AS_EXECUTION,
        boundary_condition=(
            "absent TC3 TEE attestation the execution claim is capped at L2: "
            "the provider receipt is quoted as execution proof"
        ),
    ),
    FAMILY_UNBOUND_CLAIM: BoundaryRule(
        granted_level="L0-ASSUMED",
        refused_claim="the claim is supported by disclosed evidence",
        gap_code=GAP_G7_LEVEL_IMPLICIT_UPGRADE,
        boundary_condition=(
            "no evidence binding on the claim dimension: the asserted level "
            "floats free of the lattice (G7/G9)"
        ),
    ),
    FAMILY_REPLAYED_RECEIPT: BoundaryRule(
        granted_level="L1-ASSEMBLED",
        refused_claim="the receipt proves this request in this context",
        gap_code=GAP_G4_SIGNATURE_AS_CONTEXT,
        boundary_condition=(
            "signature validity is not context validity: nonce/digest/purpose "
            "binding must fail closed at verification time"
        ),
    ),
}


@dataclasses.dataclass(frozen=True)
class EvidenceBoundaryOracleVerdict:
    """JSON-serializable evidence-boundary verdict wrapping the kernel result."""

    oracle_result: OracleResult
    granted_level: str
    refused_claim: str
    gap_code: str
    boundary_condition: str
    oracle_version: str = ACNS_INDEPENDENT_ORACLE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "oracle_result": self.oracle_result.to_dict(),
            "granted_level": self.granted_level,
            "refused_claim": self.refused_claim,
            "gap_code": self.gap_code,
            "boundary_condition": self.boundary_condition,
            "oracle_version": self.oracle_version,
        }


def adjudicate(case: Mapping[str, Any]) -> OracleResult:
    """Adjudicate ``case`` via the shared kernel and the ACNS rule table.

    Exact task contract ``adjudicate(case) -> OracleResult``. Delegation is
    mandatory: the verdict comes from :func:`oracle_kernel.adjudicate` with
    :data:`ACNS_EVIDENCE_BOUNDARY_RULES`; an undeclared or unmodelled family is
    ``INDETERMINATE`` (never coerced), and a case without ``case_id`` fails
    closed with the kernel's stable ``MISSING_CASE_ID`` reason code.
    """
    if not isinstance(case, Mapping):
        raise OracleError("MALFORMED_CASE", f"case must be a mapping, got {type(case).__name__}")
    return oracle_kernel.adjudicate(
        dict(case), dict(ACNS_EVIDENCE_BOUNDARY_RULES), oracle_id=ORACLE_ID
    )


def adjudicate_boundary(case: Mapping[str, Any]) -> EvidenceBoundaryOracleVerdict:
    """Adjudicate ``case`` and attach the evidence-boundary verdict content.

    For ``INDETERMINATE`` outcomes the boundary fields stay empty with
    ``gap_code=PENDING_ADJUDICATION``: ambiguity is retained for human
    adjudication (TC5), never resolved into a safe-looking verdict.
    """
    result = adjudicate(case)
    if result.outcome == "INDETERMINATE":
        return EvidenceBoundaryOracleVerdict(
            oracle_result=result,
            granted_level="",
            refused_claim="",
            gap_code=GAP_PENDING_ADJUDICATION,
            boundary_condition=(
                "family is undeclared or unmodelled: retained as INDETERMINATE "
                "for human adjudication, never coerced to a safe verdict"
            ),
        )
    family = case.get("family", case.get("payload", {}).get("family"))
    rule = BOUNDARY_TABLE.get(str(family))
    if rule is None:
        # The kernel accepted a family this module's boundary table does not
        # describe: the two declarative tables drifted apart. Fail closed
        # instead of emitting a label with missing boundary semantics.
        raise OracleError(
            "ORACLE_RULE_DRIFT",
            f"family {family!r} adjudicated {result.outcome} without a boundary rule",
        )
    return EvidenceBoundaryOracleVerdict(
        oracle_result=result,
        granted_level=rule.granted_level,
        refused_claim=rule.refused_claim,
        gap_code=rule.gap_code,
        boundary_condition=rule.boundary_condition,
    )


def run_self_checks() -> tuple[EvidenceBoundaryOracleVerdict, ...]:
    """Deterministic built-in correctness matrix over the rule table.

    Returns one verdict per rule-table family plus one unmodelled family;
    raises ``ORACLE_RULE_DRIFT`` if the outcomes ever stop matching the
    pre-registered matrix (``ADMIT, REJECT, REJECT, REJECT, INDETERMINATE``),
    which would mean the kernel table and the boundary table drifted apart.
    """
    cases: tuple[dict[str, Any], ...] = (
        {"case_id": "selfcheck-bound", "family": FAMILY_BOUND_EVIDENCE},
        {"case_id": "selfcheck-downgrade", "family": FAMILY_ATTESTATION_DOWNGRADE},
        {"case_id": "selfcheck-unbound", "family": FAMILY_UNBOUND_CLAIM},
        {"case_id": "selfcheck-replayed", "family": FAMILY_REPLAYED_RECEIPT},
        {"case_id": "selfcheck-unmodelled", "family": "unmodelled_family"},
    )
    verdicts = tuple(adjudicate_boundary(case) for case in cases)
    expected: tuple[str, ...] = ("ADMIT", "REJECT", "REJECT", "REJECT", "INDETERMINATE")
    actual = tuple(verdict.oracle_result.outcome for verdict in verdicts)
    if actual != expected:
        raise OracleError(
            "ORACLE_RULE_DRIFT", f"self-check matrix drifted: expected {expected}, got {actual}"
        )
    return verdicts


# ---------------------------------------------------------------------------
# Independence verification (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 2)
# ---------------------------------------------------------------------------

#: Candidate modules this oracle must never import: the ACNS baseline candidate
#: (``evaluation.venue2027.acns.baselines`` / ``acns.baselines``) and any other
#: ``baselines`` module. Matched exactly against whole import targets and
#: dotted-path components — never by substring.
CANDIDATE_BASENAMES: Final[tuple[str, ...]] = ("acns.baselines", "baselines")

DYNAMIC_IMPORT_SENTINEL: Final[str] = "__dynamic__"


def _ast_import_targets(tree: ast.AST) -> set[str]:
    """Collect every module path this file's AST imports (import/from-import)."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
            targets.update(alias.name for alias in node.names)
    return targets


def scan_for_candidate_imports(source: str | None = None) -> frozenset[str]:
    """Parse this module's source with :mod:`ast` and return candidate imports.

    An import is a candidate import if the whole target or any dotted-path
    component equals a :data:`CANDIDATE_BASENAMES` entry (exact component
    match closes the relative-import/alias escape hatch without tripping
    similar-looking names such as ``baselines_suite``). Dynamic imports
    (``__import__(...)`` / ``importlib.import_module(...)``) are reported as
    the sentinel ``__dynamic__``: their target is not statically provable, so
    they are flagged for review rather than guessed safe.
    """
    if source is None:
        source = Path(__file__).resolve().read_text(encoding="utf-8")
    tree = ast.parse(source, filename=__file__)
    found: set[str] = set()
    for target in _ast_import_targets(tree):
        parts = target.split(".")
        if target in CANDIDATE_BASENAMES or any(part in CANDIDATE_BASENAMES for part in parts):
            found.add(target)
    for node in ast.walk(tree):
        dynamic = False
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "__import__":
                dynamic = True
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
                and isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
            ):
                dynamic = True
        if dynamic:
            found.add(DYNAMIC_IMPORT_SENTINEL)
    return frozenset(found)


def verify_independence(source: str | None = None) -> None:
    """Refuse any candidate-baseline import in this oracle module's source.

    Scans the oracle *source* (live file by default, injected string in tests)
    with :mod:`ast` — never via ``sys.modules`` introspection, so independence
    stays a source-level property independent of import side effects. Raises
    :class:`OracleError` with ``CANDIDATE_IMPORT`` naming every offending
    import target. For the live file the audited kernel's own guard
    (:func:`oracle_kernel.assert_oracle_independence`) runs as well.
    """
    found = scan_for_candidate_imports(source)
    if found:
        raise OracleError(
            "CANDIDATE_IMPORT",
            "independent oracle imports candidate baseline module(s) or "
            f"unresolved dynamic import(s): {sorted(found)}",
        )
    if source is None:
        oracle_kernel.assert_oracle_independence(str(Path(__file__).resolve()), ())


__all__ = [
    "ACNS_EVIDENCE_BOUNDARY_RULES",
    "ACNS_INDEPENDENT_ORACLE_VERSION",
    "BOUNDARY_TABLE",
    "CANDIDATE_BASENAMES",
    "EvidenceBoundaryOracleVerdict",
    "ORACLE_ID",
    "ORACLE_KERNEL_VERSION",
    "OracleError",
    "OracleOutcome",
    "OracleResult",
    "REGISTERED_GAP_CODES",
    "adjudicate",
    "adjudicate_boundary",
    "run_self_checks",
    "scan_for_candidate_imports",
    "verify_independence",
]
