"""POPETS-oracle — independent revocation-reference truth oracle.

Purpose
-------
Task POPETS-oracle (Phase P02, venue popets): the independent per-case truth
oracle for "Revocation-Complete Future Disclosure for Cached Longitudinal AI
Contexts" (``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``,
RQ1-RQ3). It derives the frozen ``truth.json`` label for a case from a
*declarative, locally encoded* revocation rule table — never by importing or
calling any candidate implementation (``evaluation/venue2027/popets/baselines.py``,
``evaluation/venue2027/popets/revocation_model.py``, or any other baseline
module). The oracle expresses a **future-dispatch noninterference verdict**
under consent revocation: whether a post-revocation dispatch of cached
longitudinal context may leave the process (CASE_MATRIX POPETS-CASE-01..09),
**not** a candidate mechanism trace. Ground truth derives only from the frozen
scenario family of the case; candidate-supplied verdict fields inside a case
cannot influence the label, so circular label generation is impossible by
construction.

Adjudication is delegated to the audited shared kernel
(:mod:`evaluation.venue2027._shared.oracle_kernel`); this module contributes
only the venue's rule table and independence verification
(``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rule 2: an
independent oracle must not import any candidate code).

Allowed input
-------------
``case``: a JSON-serializable mapping with a non-empty ``case_id``, a declared
scenario ``family`` (top-level or nested under ``payload``) and an optional
``evidence`` list of ``{"uri": ...}`` pointers carried through as
``evidence_refs``. Any extra fields (including candidate-supplied decision
fields) are ignored by design.

Rule table (pre-registered POPETS scenario families)
----------------------------------------------------
- ``fresh``                 -> ``ADMIT``  (valid consent, purpose and version,
  no revocation: the authorized dispatch discloses exactly the authorized
  bytes — POPETS-CASE-01/04)
- ``revoked_then_dispatch`` -> ``REJECT`` (consent revoked before the retry/cached
  dispatch: no revoked synthetic canary may leave the process —
  POPETS-CASE-02/08)
- ``cross_purpose``         -> ``REJECT`` (context built for purpose A reused
  for purpose B: strict purpose and actor binding forbids cache confusion —
  POPETS-CASE-05)
- ``transitive_gap``        -> ``REJECT`` (derived cache with unknown ancestry /
  missing lineage edge: fail closed, force fresh authorized reconstruction —
  POPETS-CASE-03/07)
- anything else             -> ``INDETERMINATE`` (``UNMODELLED_FAMILY`` /
  ``NO_FAMILY_DECLARED``); never coerced to a safe verdict

Threat-precision note (POPETS-CASE-06): already-delivered bytes are
``OUT_OF_SCOPE_PAST`` — this oracle never asserts retroactive erasure; the
measure is preventable *future* disclosure only. Such cases carry no
post-revocation dispatch family and therefore fall to ``INDETERMINATE`` rather
than being coerced into ADMIT/REJECT.

Failure semantics (stable reason codes)
---------------------------------------
- ``MALFORMED_CASE`` — ``case`` is not a mapping; refused, never silently read.
- ``MISSING_CASE_ID`` — kernel refuses a case without ``case_id``.
- ``NO_FAMILY_DECLARED`` / ``UNMODELLED_FAMILY`` — ``INDETERMINATE`` outcome
  with ``gap_code=PENDING_ADJUDICATION``: a first-class outcome that is never
  counted as a safe rejection or a completion (false-zero ban).
- ``ORACLE_RULE_DRIFT`` — internal inconsistency between the kernel rule table
  and the noninterference table (self-checks fail closed rather than emit a
  label).
- ``CANDIDATE_IMPORT`` — :func:`verify_independence` detected an import of a
  candidate module (``popets.baselines`` / any ``baselines`` /
  ``revocation_model`` module) or an unresolvable dynamic import in this file.

Version
-------
``POPETS_INDEPENDENT_ORACLE_VERSION = "1.0.0"``. Output is JSON-serializable
via :meth:`OracleResult.to_dict` and :meth:`NoninterferenceOracleVerdict.to_dict`.
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

POPETS_INDEPENDENT_ORACLE_VERSION: Final[str] = "1.0.0"

#: Stable oracle identity carried on every emitted verdict.
ORACLE_ID: Final[str] = "popets-revocation-reference"

#: Pre-registered POPETS scenario families (kernel rule table; must equal the
#: ``popets`` row of ``dataset_kernel.VENUE_FAMILIES``, checked by self-scan).
FAMILY_FRESH: Final[str] = "fresh"
FAMILY_REVOKED_THEN_DISPATCH: Final[str] = "revoked_then_dispatch"
FAMILY_CROSS_PURPOSE: Final[str] = "cross_purpose"
FAMILY_TRANSITIVE_GAP: Final[str] = "transitive_gap"

#: Declarative family -> outcome rule table handed to the shared kernel.
#: Deliberately module-local: it is the frozen truth source, not derived from,
#: nor cross-checked against, any candidate classifier.
POPETS_NONINTERFERENCE_RULES: Final[Mapping[str, OracleOutcome]] = {
    FAMILY_FRESH: "ADMIT",
    FAMILY_REVOKED_THEN_DISPATCH: "REJECT",
    FAMILY_CROSS_PURPOSE: "REJECT",
    FAMILY_TRANSITIVE_GAP: "REJECT",
}

#: Basis rows of the pre-registered CASE_MATRIX (POPETS-CASE-01..09) that this
#: rule table adjudicates, restated locally (never imported from a candidate).
BASIS_NONE: Final[str] = "none"
BASIS_RETRY_LEAKAGE: Final[str] = "POPETS-CASE-02_RETRY_LEAKAGE"
BASIS_PURPOSE_BINDING: Final[str] = "POPETS-CASE-05_PURPOSE_BINDING"
BASIS_LINEAGE_COMPLETENESS: Final[str] = "POPETS-CASE-03/07_LINEAGE_COMPLETENESS"
BASIS_PENDING_ADJUDICATION: Final[str] = "PENDING_ADJUDICATION"


@dataclasses.dataclass(frozen=True)
class NoninterferenceRule:
    """One declarative row of the future-dispatch noninterference table.

    ``authorized_dispatch`` states what the frozen family allows to leave the
    process post-revocation, ``refused_dispatch`` names the leakage the rule
    refuses, ``basis_cases`` names the CASE_MATRIX rows the rule adjudicates,
    and ``observation_condition`` states the declared observation-model
    condition whose absence makes the dispatch noninterfering claim fail.
    """

    authorized_dispatch: str
    refused_dispatch: str
    basis_cases: str
    observation_condition: str


#: Noninterference table: family -> the revocation verdict content
#: (module-local, frozen before execution; never repaired to match any
#: candidate output).
NONINTERFERENCE_TABLE: Final[Mapping[str, NoninterferenceRule]] = {
    FAMILY_FRESH: NoninterferenceRule(
        authorized_dispatch=(
            "authorized bytes for the specified principal/purpose (scope-local "
            "recomputation preserves utility)"
        ),
        refused_dispatch="nothing: no revocation occurred in this family",
        basis_cases=BASIS_NONE,
        observation_condition=(
            "valid consent, purpose and version with no revocation event; the "
            "dispatch trace discloses exactly the authorized projection"
        ),
    ),
    FAMILY_REVOKED_THEN_DISPATCH: NoninterferenceRule(
        authorized_dispatch="nothing after the effective revocation time",
        refused_dispatch=(
            "any post-revocation dispatch of the cached context, retry payload "
            "or fallback transport carrying the revoked synthetic canary"
        ),
        basis_cases=BASIS_RETRY_LEAKAGE,
        observation_condition=(
            "reauthorize at every dispatch: epoch revalidated immediately "
            "prior to dispatch, so a stale cached context cannot leave the "
            "process after the effective revoke"
        ),
    ),
    FAMILY_CROSS_PURPOSE: NoninterferenceRule(
        authorized_dispatch="nothing derived from the purpose-A context",
        refused_dispatch=(
            "cache reuse across purposes: purpose-B request served from a "
            "context built for purpose A (cache confusion)"
        ),
        basis_cases=BASIS_PURPOSE_BINDING,
        observation_condition=(
            "strict purpose and actor binding on every dispatch; origin- and "
            "purpose-labeled artifacts never satisfy a different purpose"
        ),
    ),
    FAMILY_TRANSITIVE_GAP: NoninterferenceRule(
        authorized_dispatch="nothing from a cache artifact of unknown ancestry",
        refused_dispatch=(
            "any dispatch whose lineage is not provably closed: missing "
            "provenance edge on a derived artifact (field -> summary -> "
            "second summary)"
        ),
        basis_cases=BASIS_LINEAGE_COMPLETENESS,
        observation_condition=(
            "transitive closure must reach every derived cache artifact; an "
            "unknown ancestry fails closed and forces fresh authorized "
            "reconstruction"
        ),
    ),
}


@dataclasses.dataclass(frozen=True)
class NoninterferenceOracleVerdict:
    """JSON-serializable noninterference verdict wrapping the kernel result."""

    oracle_result: OracleResult
    authorized_dispatch: str
    refused_dispatch: str
    basis_cases: str
    observation_condition: str
    oracle_version: str = POPETS_INDEPENDENT_ORACLE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "oracle_result": self.oracle_result.to_dict(),
            "authorized_dispatch": self.authorized_dispatch,
            "refused_dispatch": self.refused_dispatch,
            "basis_cases": self.basis_cases,
            "observation_condition": self.observation_condition,
            "oracle_version": self.oracle_version,
        }


def adjudicate(case: Mapping[str, Any]) -> OracleResult:
    """Adjudicate ``case`` via the shared kernel and the POPETS rule table.

    Exact task contract ``adjudicate(case) -> OracleResult``. Delegation is
    mandatory: the verdict comes from :func:`oracle_kernel.adjudicate` with
    :data:`POPETS_NONINTERFERENCE_RULES`; an undeclared or unmodelled family is
    ``INDETERMINATE`` (never coerced), and a case without ``case_id`` fails
    closed with the kernel's stable ``MISSING_CASE_ID`` reason code.
    """
    if not isinstance(case, Mapping):
        raise OracleError("MALFORMED_CASE", f"case must be a mapping, got {type(case).__name__}")
    return oracle_kernel.adjudicate(
        dict(case), dict(POPETS_NONINTERFERENCE_RULES), oracle_id=ORACLE_ID
    )


def adjudicate_noninterference(case: Mapping[str, Any]) -> NoninterferenceOracleVerdict:
    """Adjudicate ``case`` and attach the noninterference verdict content.

    For ``INDETERMINATE`` outcomes the noninterference fields stay empty with
    ``basis_cases=PENDING_ADJUDICATION``: ambiguity is retained for human
    adjudication, never resolved into a safe-looking verdict.
    """
    result = adjudicate(case)
    if result.outcome == "INDETERMINATE":
        return NoninterferenceOracleVerdict(
            oracle_result=result,
            authorized_dispatch="",
            refused_dispatch="",
            basis_cases=BASIS_PENDING_ADJUDICATION,
            observation_condition=(
                "family is undeclared or unmodelled: retained as INDETERMINATE "
                "for human adjudication, never coerced to a safe verdict"
            ),
        )
    family = case.get("family", case.get("payload", {}).get("family"))
    rule = NONINTERFERENCE_TABLE.get(str(family))
    if rule is None:
        # The kernel accepted a family this module's noninterference table does
        # not describe: the two declarative tables drifted apart. Fail closed
        # instead of emitting a label with missing revocation semantics.
        raise OracleError(
            "ORACLE_RULE_DRIFT",
            f"family {family!r} adjudicated {result.outcome} without a noninterference rule",
        )
    return NoninterferenceOracleVerdict(
        oracle_result=result,
        authorized_dispatch=rule.authorized_dispatch,
        refused_dispatch=rule.refused_dispatch,
        basis_cases=rule.basis_cases,
        observation_condition=rule.observation_condition,
    )


def run_self_checks() -> tuple[NoninterferenceOracleVerdict, ...]:
    """Deterministic built-in correctness matrix over the rule table.

    Returns one verdict per rule-table family plus one unmodelled family;
    raises ``ORACLE_RULE_DRIFT`` if the outcomes ever stop matching the
    pre-registered matrix (``ADMIT, REJECT, REJECT, REJECT, INDETERMINATE``),
    which would mean the kernel table and the noninterference table drifted
    apart.
    """
    cases: tuple[dict[str, Any], ...] = (
        {"case_id": "selfcheck-fresh", "family": FAMILY_FRESH},
        {"case_id": "selfcheck-revoked", "family": FAMILY_REVOKED_THEN_DISPATCH},
        {"case_id": "selfcheck-cross-purpose", "family": FAMILY_CROSS_PURPOSE},
        {"case_id": "selfcheck-transitive-gap", "family": FAMILY_TRANSITIVE_GAP},
        {"case_id": "selfcheck-unmodelled", "family": "unmodelled_family"},
    )
    verdicts = tuple(adjudicate_noninterference(case) for case in cases)
    expected: tuple[str, ...] = ("ADMIT", "REJECT", "REJECT", "REJECT", "INDETERMINATE")
    actual = tuple(verdict.oracle_result.outcome for verdict in verdicts)
    if actual != expected:
        raise OracleError(
            "ORACLE_RULE_DRIFT", f"self-check matrix drifted: expected {expected}, got {actual}"
        )
    return verdicts


def verify_rule_table_alignment() -> None:
    """Fail closed if the frozen rule table drifts from the dataset registry.

    The POPETS scenario-family registry lives in the shared dataset kernel
    (``VENUE_FAMILIES["popets"]``); the oracle restates it locally so it never
    imports a candidate module. A copy that stops matching the registry would
    adjudicate generated cases as ``UNMODELLED_FAMILY`` — refuse that state
    here rather than emit drifting labels.
    """
    registry_families = ("fresh", "revoked_then_dispatch", "cross_purpose", "transitive_gap")
    if tuple(POPETS_NONINTERFERENCE_RULES) != registry_families:
        raise OracleError(
            "ORACLE_RULE_DRIFT",
            f"rule table {tuple(POPETS_NONINTERFERENCE_RULES)} != registry {registry_families}",
        )


# ---------------------------------------------------------------------------
# Independence verification (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 2)
# ---------------------------------------------------------------------------

#: Candidate modules this oracle must never import: the POPETS baseline
#: candidate (``evaluation.venue2027.popets.baselines`` / ``popets.baselines``)
#: and any other ``baselines`` module, plus the POPETS revocation model
#: (``evaluation.venue2027.popets.revocation_model`` / ``revocation_model``).
#: Matched exactly against whole import targets and dotted-path components —
#: never by substring.
CANDIDATE_BASENAMES: Final[tuple[str, ...]] = (
    "popets.baselines",
    "baselines",
    "popets.revocation_model",
    "revocation_model",
)

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
    similar-looking names such as ``baselines_suite`` or
    ``revocation_modeling``). Dynamic imports (``__import__(...)`` /
    ``importlib.import_module(...)``) are reported as the sentinel
    ``__dynamic__``: their target is not statically provable, so they are
    flagged for review rather than guessed safe.
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
    """Refuse any candidate import in this oracle module's source.

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
            "independent oracle imports candidate module(s) or unresolved "
            f"dynamic import(s): {sorted(found)}",
        )
    if source is None:
        oracle_kernel.assert_oracle_independence(str(Path(__file__).resolve()), ())


__all__ = [
    "BASIS_NONE",
    "BASIS_PENDING_ADJUDICATION",
    "CANDIDATE_BASENAMES",
    "DYNAMIC_IMPORT_SENTINEL",
    "FAMILY_CROSS_PURPOSE",
    "FAMILY_FRESH",
    "FAMILY_REVOKED_THEN_DISPATCH",
    "FAMILY_TRANSITIVE_GAP",
    "NONINTERFERENCE_TABLE",
    "ORACLE_ID",
    "ORACLE_KERNEL_VERSION",
    "OracleError",
    "OracleOutcome",
    "OracleResult",
    "POPETS_INDEPENDENT_ORACLE_VERSION",
    "POPETS_NONINTERFERENCE_RULES",
    "NoninterferenceOracleVerdict",
    "NoninterferenceRule",
    "adjudicate",
    "adjudicate_noninterference",
    "run_self_checks",
    "scan_for_candidate_imports",
    "verify_independence",
    "verify_rule_table_alignment",
]
