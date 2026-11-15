"""DIMVA-oracle — independent campaign-truth reference oracle (detection venue).

Purpose
-------
Task DIMVA-oracle (Phase P02, venue ``dimva``): the independent per-case truth
oracle for "GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing
from Minimal Agent Events" (``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``;
scenario matrix ``research/venue2027/VENUES/dimva/CASE_MATRIX.md``; task contract
``research/venue2027/VENUES/dimva/TASKS/DIMVA-oracle.md``). Every adjudication is
delegated to the audited shared kernel
:func:`evaluation.venue2027._shared.oracle_kernel.adjudicate` driven by the
module-local declarative DIMVA detection rule table :data:`DIMVA_DETECTION_RULES`.
The oracle NEVER imports or calls any candidate implementation (detector arms in
``evaluation/venue2027/dimva/baselines.py`` or any other baseline module), and it
NEVER consults a candidate's detection decision, alarm flag, score or reason code:
ground truth derives only from the case's declared scenario family and the frozen
rule table (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 2), so circular label
generation is impossible by construction.

LABEL SEMANTICS — DETECTION VENUE (read carefully)
--------------------------------------------------
DIMVA is a *detection* venue, so this oracle's outcome axis encodes **campaign
truth membership**, not an alarm decision:

- ``ADMIT``   — the case IS malicious: the campaign **IS** a probing attack
  (admitted into the attack-campaign class; oracle truth label ``ATTACK``).
- ``REJECT``  — the case is NOT an attack: rejected from the attack-campaign
  class as a benign session (oracle truth label ``BENIGN``).
- ``INDETERMINATE`` — the family is unmodelled/undeclared: retained for
  independent human adjudication (truth label ``PENDING_ADJUDICATION``), never
  silently coerced to "not an attack".

This axis is deliberately inverted with respect to the detector arms' harness
outcome vocabulary (where a detector ``DETECT`` alarm is recorded as a
``REJECT`` outcome): the oracle labels what the campaign IS, not what a
detector said. :data:`CAMPAIGN_TRUTH_LABELS` and :func:`campaign_truth_label`
make the mapping machine-checkable; :data:`LABEL_SEMANTICS` carries the frozen
prose statement.

DIMVA detection rule table (frozen at module import)
----------------------------------------------------
- ``benign_session``          -> ``REJECT`` ("not an attack"; legitimate retry,
  care-team handoff, ordinary exploration — specificity control).
- ``low_and_slow``            -> ``ADMIT`` ("is a probing attack"; long sparse
  horizon with escalating lineage reuse, paced under fixed windows).
- ``cross_tool_obfuscation``  -> ``ADMIT`` ("is a probing attack"; denials
  spread across many tools / renamed tools to defeat signatures).
- ``burst_probe``             -> ``ADMIT`` ("is a probing attack"; compressed
  inter-arrival probing bursts).
- anything else               -> ``INDETERMINATE`` (``UNMODELLED_FAMILY`` /
  ``NO_FAMILY_DECLARED``) — an unmodelled situation is never silently treated
  as "not an attack" (that would be a false-safe label on a detection venue).

Allowed input
-------------
``case``: a JSON-serializable mapping with a non-empty ``case_id`` and a
declared scenario ``family`` (top-level or nested under ``payload``), plus an
optional ``evidence`` list of ``{"uri": ...}`` pointers carried through as
``evidence_refs``. Any extra fields — including candidate-supplied decision
fields — are ignored by design. No network, no database, no provider, no
hidden clock, no randomness; synthetic fixtures only, no real PHI/PII.

Failure semantics (stable reason codes)
---------------------------------------
- ``MALFORMED_CASE`` — ``case`` is not a mapping; refused, never silently read.
- ``MISSING_CASE_ID`` — kernel refuses a case without ``case_id``.
- ``NO_FAMILY_DECLARED`` / ``UNMODELLED_FAMILY`` — ``INDETERMINATE`` outcome
  (truth label ``PENDING_ADJUDICATION``): a first-class outcome never counted
  as a safe "not an attack" label or a completion (false-zero ban).
- ``ORACLE_RULE_DRIFT`` — the rule table drifted from the frozen family
  registry / self-check matrix (self-checks fail closed rather than emit a
  mislabeled truth).
- ``CANDIDATE_IMPORT`` — :func:`verify_independence` detected an import of a
  candidate baseline module (``dimva.baselines`` / any ``baselines`` module)
  or an unresolvable dynamic import in the scanned oracle source.

Version
-------
``CAMPAIGN_TRUTH_ORACLE_VERSION = "clara.dimva.campaign-truth-oracle-v1"``.
Output is JSON-serializable via :meth:`oracle_kernel.OracleResult.to_dict`
(kernel version stamped on every verdict).
"""

from __future__ import annotations

import ast
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

CAMPAIGN_TRUTH_ORACLE_VERSION: Final[str] = "clara.dimva.campaign-truth-oracle-v1"

#: Stable oracle identity carried on every emitted verdict (task contract).
ORACLE_ID: Final[str] = "dimva-campaign-truth-reference"

#: Re-export of the audited kernel version delegated to (stamped in results).
KERNEL_VERSION: Final[str] = oracle_kernel.ORACLE_KERNEL_VERSION

#: Pre-registered DIMVA scenario families (CASE_MATRIX / dataset kernel registry),
#: restated locally — never imported from a candidate or generator module.
FAMILY_BENIGN_SESSION: Final[str] = "benign_session"
FAMILY_LOW_AND_SLOW: Final[str] = "low_and_slow"
FAMILY_CROSS_TOOL_OBFUSCATION: Final[str] = "cross_tool_obfuscation"
FAMILY_BURST_PROBE: Final[str] = "burst_probe"

REGISTERED_FAMILIES: Final[frozenset[str]] = frozenset(
    {
        FAMILY_BENIGN_SESSION,
        FAMILY_LOW_AND_SLOW,
        FAMILY_CROSS_TOOL_OBFUSCATION,
        FAMILY_BURST_PROBE,
    }
)

#: Declarative family -> outcome rule table handed to the shared kernel.
#: DETECTION-venue semantics: ADMIT = the campaign IS a probing attack;
#: REJECT = not an attack (benign session). Deliberately module-local: it is
#: the frozen truth source, not derived from, nor cross-checked against, any
#: candidate detector's output.
DIMVA_DETECTION_RULES: Final[Mapping[str, OracleOutcome]] = {
    FAMILY_BENIGN_SESSION: "REJECT",
    FAMILY_LOW_AND_SLOW: "ADMIT",
    FAMILY_CROSS_TOOL_OBFUSCATION: "ADMIT",
    FAMILY_BURST_PROBE: "ADMIT",
}

#: Frozen prose statement of the detection-venue label semantics (asserted by
#: tests so the documentation cannot silently drift from the rule table).
LABEL_SEMANTICS: Final[str] = (
    "DIMVA is a detection venue: ADMIT means the campaign IS malicious (a "
    "probing attack); REJECT means the case is not an attack (benign session); "
    "INDETERMINATE is retained for human adjudication. The oracle labels "
    "campaign truth, never a detector arm's alarm decision."
)

#: Oracle outcome -> campaign-truth label (machine-checkable semantics).
CAMPAIGN_TRUTH_LABELS: Final[Mapping[str, str]] = {
    "ADMIT": "ATTACK",
    "REJECT": "BENIGN",
    "INDETERMINATE": "PENDING_ADJUDICATION",
}

#: Frozen self-check matrix: one outcome per modelled family plus one
#: unmodelled family (drift guard, fail closed).
SELF_CHECK_MATRIX: Final[Mapping[str, str]] = {
    FAMILY_BENIGN_SESSION: "REJECT",
    FAMILY_LOW_AND_SLOW: "ADMIT",
    FAMILY_CROSS_TOOL_OBFUSCATION: "ADMIT",
    FAMILY_BURST_PROBE: "ADMIT",
    "unmodelled_family": "INDETERMINATE",
}


def campaign_truth_label(outcome: str) -> str:
    """Map an oracle outcome to its campaign-truth label.

    ``ADMIT`` -> ``ATTACK`` (the campaign IS malicious), ``REJECT`` ->
    ``BENIGN`` (not an attack), ``INDETERMINATE`` -> ``PENDING_ADJUDICATION``.
    Any other outcome is refused fail-closed (``UNKNOWN_OUTCOME``) rather than
    guessed.
    """
    label = CAMPAIGN_TRUTH_LABELS.get(outcome)
    if label is None:
        raise OracleError("UNKNOWN_OUTCOME", f"outcome {outcome!r} has no campaign-truth label")
    return label


def campaign_truth(result: OracleResult) -> str:
    """Return the campaign-truth label for an :class:`OracleResult`."""
    return campaign_truth_label(result.outcome)


def adjudicate(case: Mapping[str, Any]) -> OracleResult:
    """Adjudicate ``case`` via the shared kernel and the DIMVA detection rules.

    Exact task contract ``adjudicate(case) -> OracleResult``. Delegation is
    mandatory: the verdict comes from :func:`oracle_kernel.adjudicate` with
    :data:`DIMVA_DETECTION_RULES`; an undeclared or unmodelled family is
    ``INDETERMINATE`` (never coerced to "not an attack"), and a case without
    ``case_id`` fails closed with the kernel's stable ``MISSING_CASE_ID``
    reason code. Candidate-supplied fields inside the case are ignored.
    """
    if not isinstance(case, Mapping):
        raise OracleError("MALFORMED_CASE", f"case must be a mapping, got {type(case).__name__}")
    return oracle_kernel.adjudicate(dict(case), dict(DIMVA_DETECTION_RULES), oracle_id=ORACLE_ID)


def run_self_checks() -> tuple[OracleResult, ...]:
    """Deterministic built-in correctness matrix over the detection rule table.

    Returns one result per modelled family plus one unmodelled family; raises
    ``ORACLE_RULE_DRIFT`` if the outcomes ever stop matching the frozen matrix
    (``REJECT, ADMIT, ADMIT, ADMIT, INDETERMINATE``), which would mean the rule
    table or the label semantics drifted from the pre-registration.
    """
    if set(DIMVA_DETECTION_RULES) != set(REGISTERED_FAMILIES):
        raise OracleError(
            "ORACLE_RULE_DRIFT",
            "DIMVA_DETECTION_RULES drifted from the frozen DIMVA family registry",
        )
    if set(CAMPAIGN_TRUTH_LABELS) != {"ADMIT", "REJECT", "INDETERMINATE"}:
        raise OracleError(
            "ORACLE_RULE_DRIFT",
            "CAMPAIGN_TRUTH_LABELS drifted from the outcome vocabulary",
        )
    results = tuple(
        adjudicate({"case_id": f"selfcheck-{family}", "family": family})
        for family in (*DIMVA_DETECTION_RULES, "unmodelled_family")
    )
    expected = tuple(SELF_CHECK_MATRIX[name] for name in SELF_CHECK_MATRIX)
    actual = tuple(result.outcome for result in results)
    if actual != expected:
        raise OracleError(
            "ORACLE_RULE_DRIFT", f"self-check matrix drifted: expected {expected}, got {actual}"
        )
    return results


# ---------------------------------------------------------------------------
# Independence verification (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 2)
# ---------------------------------------------------------------------------

#: Candidate modules this oracle must never import: the DIMVA detector-arm
#: candidate (``evaluation.venue2027.dimva.baselines`` / ``dimva.baselines``)
#: and any other ``baselines`` module. Matched exactly against whole import
#: targets and dotted-path components — never by substring.
CANDIDATE_BASENAMES: Final[tuple[str, ...]] = ("dimva.baselines", "baselines")

DYNAMIC_IMPORT_SENTINEL: Final[str] = "__dynamic__"


def _ast_import_targets(tree: ast.AST) -> set[str]:
    """Collect every module path an AST imports (import / from-import)."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
            targets.update(alias.name for alias in node.names)
    return targets


def scan_for_candidate_imports(source: str | None = None) -> frozenset[str]:
    """Parse oracle source with :mod:`ast` and return candidate imports.

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


def verify_independence(source: str | None = None, oracle_path: str | None = None) -> None:
    """Refuse any candidate-baseline import in the scanned oracle source.

    Scans oracle *source* with :mod:`ast` — never via ``sys.modules``
    introspection, so independence stays a source-level property independent
    of import side effects. The default scans this live module; tests inject
    rogue sources or point ``oracle_path`` at an on-disk rogue oracle file.
    Raises :class:`OracleError` with ``CANDIDATE_IMPORT`` naming every
    offending import target (or the ``__dynamic__`` sentinel). When the
    source is read from disk (``source is None``), the audited kernel's own
    guard (:func:`oracle_kernel.assert_oracle_independence`) runs as well.
    """
    path = str(Path(oracle_path)) if oracle_path else str(Path(__file__).resolve())
    if source is None:
        source = Path(path).read_text(encoding="utf-8")
        live_scan = True
    else:
        live_scan = False
    found = scan_for_candidate_imports(source)
    if found:
        raise OracleError(
            "CANDIDATE_IMPORT",
            "independent oracle imports candidate baseline module(s) or "
            f"unresolved dynamic import(s): {sorted(found)}",
        )
    if live_scan:
        oracle_kernel.assert_oracle_independence(path, CANDIDATE_BASENAMES)


def self_scan() -> dict[str, Any]:
    """Run the built-in self-checks (independence + rule-table shape).

    Returns a JSON-serializable audit summary; raises
    :class:`OracleError` fail-closed on any refusal.
    """
    verify_independence()
    results = run_self_checks()
    return {
        "oracle_id": ORACLE_ID,
        "oracle_version": CAMPAIGN_TRUTH_ORACLE_VERSION,
        "kernel_version": KERNEL_VERSION,
        "independence": "CLEAN",
        "candidate_basenames": list(CANDIDATE_BASENAMES),
        "rule_table": dict(DIMVA_DETECTION_RULES),
        "campaign_truth_labels": dict(CAMPAIGN_TRUTH_LABELS),
        "self_check_outcomes": [result.outcome for result in results],
        "llm_calls": 0,
        "model_imports": 0,
    }


__all__ = [
    "CAMPAIGN_TRUTH_LABELS",
    "CAMPAIGN_TRUTH_ORACLE_VERSION",
    "CANDIDATE_BASENAMES",
    "DIMVA_DETECTION_RULES",
    "KERNEL_VERSION",
    "LABEL_SEMANTICS",
    "ORACLE_ID",
    "ORACLE_KERNEL_VERSION",
    "OracleError",
    "OracleOutcome",
    "OracleResult",
    "REGISTERED_FAMILIES",
    "adjudicate",
    "campaign_truth",
    "campaign_truth_label",
    "run_self_checks",
    "scan_for_candidate_imports",
    "self_scan",
    "verify_independence",
]


if __name__ == "__main__":  # pragma: no cover - manual audit helper
    import json

    print(json.dumps(self_scan(), indent=2, sort_keys=True))
