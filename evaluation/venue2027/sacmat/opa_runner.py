"""SACMAT-X05 OPA runner — real-binary adapter with a clearly-labelled port.

Purpose
-------
Task ``SACMAT-X05_opa_runner`` (phase P03, RQ3) for the SACMAT 2027 study
"PolicyTrace: Temporal Conformance Testing of Delegated Consent across
Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``). RQ3 asks: across
Cedar, OpenFGA and OPA, which semantics are faithfully expressible, and where
do adapters necessarily diverge? This module is the OPA side of that mapping.

It has exactly two execution backends, always labelled in every verdict:

- ``opa-binary`` — the REAL pinned upstream binary (OPA {OPA_PINNED_VERSION}),
  detected with :func:`shutil.which`. When the binary is present, the runner
  shells out to ``opa eval`` with a compiled Rego policy bundle plus an input
  document and reports the binary's actual verdict. When the binary is
  ABSENT, the runner returns ``NOT_RUN_EXTERNAL`` with reason code
  ``BASELINE_UNAVAILABLE`` — never a fabricated decision, never silently
  counted as a completion (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4).
  The task contract is ``evaluate_opa(module, input) -> Decision``: the
  four-valued decision is the ``verdict`` field of :class:`OpaVerdict`, and
  :func:`evaluate_opa` returns that Decision directly.
- ``xacml-port`` — a faithful in-process PORT of the XACML-like engine model
  ``XacmlPolicyEngine`` from ``evaluation/venue2027/sacmat/baselines.py``
  (deny-overrides rule combining over the compiled final policy state), made
  available here as :func:`evaluate_xacml_port`. It is explicitly labelled a
  PORT: an in-process model of documented XACML 3.0 combining semantics, NOT
  the upstream OPA binary and NOT an upstream OPA run. Its roles are (a)
  parity checking against the real binary when the binary runs and (b) an
  executable decision source for callers who explicitly accept the port's
  semantics. Every detail string produced by this module names the backend
  that produced each decision.

The compiled Rego encoding is generated deterministically from the validated
``(policy history, request)`` case (same shape as the baseline arms in
``baselines.py``): the final policy state is compiled into deny/permit pair
sets with deny-overrides precedence, mirroring the labelled port. The
encoding's limitations are declared in ``KNOWN_ENCODING_LIMITATIONS`` (the
final-state encoding does not compile temporal expiry — that is exactly the
portability surface RQ3 measures, so it is labelled, never hidden).

Allowed input
-------------
A JSON-serializable ``case`` mapping shaped like the blueprint scenario
records: ``case_id``, ordered ``history`` of versioned policy events
(GRANT / REVOKE / REGRANT / EXPIRE / POLICY_VERSION_BUMP with ``logical_time``
and grant payload), and ``request`` (``actor_id``, ``purpose``,
``decision_time``). ``ctx`` is the harness-injected
:class:`~evaluation.venue2027.sacmat.baselines.SacmatContext`. For
:func:`evaluate_opa` the inputs are a Rego ``module`` string and a
JSON-serializable ``input`` document. All timestamps are non-negative ints in
monotonic logical time. No network, no hidden clock, no randomness.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes, never unhandled exceptions
miscounted as safe rejections:

- ``BASELINE_UNAVAILABLE`` — real OPA binary absent (or caller-declared
  unavailable via ``simulate_unavailable_upstream``): outcome
  ``NOT_RUN_EXTERNAL``, ``counted_as_success=False``, retriable.
- ``OPA_EXECUTION_ERROR`` / ``OPA_TIMEOUT`` / ``OPA_INVALID_OUTPUT`` — the
  real binary failed, exceeded its budget, or returned an unparseable
  document: outcome ``INDETERMINATE`` (never PERMIT/DENY, never counted).
- Malformed case (missing/empty/non-list history, unknown event kinds, bad
  types, non-monotonic times, missing request fields) — outcome
  ``INDETERMINATE`` with the baselines reason code in the detail.
- ``UNSAFE_POLICY_IDENTIFIER`` — a case field that does not match the safe
  identifier allowlist is refused (no Rego injection): outcome
  ``INDETERMINATE``.
- Wiring errors (non-mapping case, non-``SacmatContext`` ctx, missing
  contract argument) raise :class:`SacmatOpaRunnerError` with a stable
  reason code.

Honesty invariant: this module NEVER reports a real OPA run unless the real
binary was detected AND the subprocess completed; a verdict from the port is
always labelled ``xacml-port``. Absence of the binary is a transparent
``NOT_RUN_EXTERNAL``, which prevents unsupported comparative claims per the
blueprint ("``NOT_RUN_EXTERNAL`` is permitted as a transparent status but
prevents unsupported comparative claims").

Version
-------
``OPA_RUNNER_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat import baselines
from evaluation.venue2027.sacmat.baselines import (
    EVENT_GRANT,
    EVENT_REGRANT,
    PolicyHistory,
    SacmatContext,
    XacmlPolicyEngine,
)

OPA_RUNNER_VERSION = "1.0.0"

#: Pinned upstream (registry row: OPA v1.22.4 / XACML 3.0 combining semantics).
OPA_PINNED_VERSION = "v1.22.4"

#: Rego package + entrypoint query for the compiled delegated-consent policy.
REGO_PACKAGE = "clara.sacmat.delegated_consent"
OPA_QUERY = f"data.{REGO_PACKAGE}.decision"

#: Subprocess budget for a single ``opa eval`` invocation.
OPA_TIMEOUT_SECONDS = 30.0

#: Backend labels (always carried in verdicts/details; never interchangeable).
OPA_BINARY_BACKEND_PREFIX = "opa-binary"
XACML_PORT_BACKEND = "xacml-port:in-process-port-of-baselines.XacmlPolicyEngine"
XACML_PORT_LABEL = (
    "PORT: in-process port of the XACML-like engine model from "
    "evaluation/venue2027/sacmat/baselines.py (deny-overrides over the compiled "
    "final policy state); NOT the upstream OPA binary and NOT an OPA run."
)

#: Declared, labelled limitations of the compiled Rego encoding (RQ3 surface).
KNOWN_ENCODING_LIMITATIONS: tuple[str, ...] = (
    "final-state compiled encoding: temporal expiry is NOT compiled into the "
    "Rego rules (identical to the labelled XACML port's compiled view); the "
    "input document carries decision_time for callers and future encodings",
    "delegation keys are (actor, purpose) pairs; the delegate identity is not "
    "encoded (matches the XACML port's compiled permit/deny pairs)",
)

#: Verdict values (four-valued portable oracle + the transparent non-run).
VERDICT_VALUES: frozenset[str] = frozenset(
    {
        baselines.PERMIT,
        baselines.DENY,
        baselines.NOT_APPLICABLE,
        baselines.INDETERMINATE,
        "NOT_RUN_EXTERNAL",
    }
)

#: Stable reason codes (uppercase, machine-checkable).
RC_BASELINE_UNAVAILABLE = baselines.RC_BASELINE_UNAVAILABLE
RC_OPA_EXECUTION_ERROR = "OPA_EXECUTION_ERROR"
RC_OPA_TIMEOUT = "OPA_TIMEOUT"
RC_OPA_INVALID_OUTPUT = "OPA_INVALID_OUTPUT"
RC_UNSAFE_POLICY_IDENTIFIER = "UNSAFE_POLICY_IDENTIFIER"
RC_OPA_PORT_AGREEMENT = "OPA_PORT_AGREEMENT"
RC_OPA_PORT_DISAGREEMENT = "OPA_PORT_DISAGREEMENT"
RC_CASE_NOT_AN_OBJECT = "CASE_NOT_AN_OBJECT"
RC_CONTEXT_MALFORMED = baselines.RC_CONTEXT_MALFORMED

#: Safe identifier allowlist for anything interpolated into the Rego module.
_SAFE_IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)
_SAFE_IDENTIFIER_MAX_LEN = 64


class SacmatOpaRunnerError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not an outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class OpaVerdict:
    """Typed, JSON-serializable verdict of one OPA evaluation.

    ``verdict`` is the portable decision (``PERMIT`` / ``DENY`` /
    ``NOT_APPLICABLE`` / ``INDETERMINATE``) or the transparent non-run value
    ``NOT_RUN_EXTERNAL``. ``backend`` always names the engine that produced
    the verdict; a real binary verdict carries
    ``opa-binary:<version-probe>`` and a port verdict carries the
    ``xacml-port`` label — the two are never conflated.
    """

    verdict: str
    reason_code: str
    detail: str
    backend: str
    opa_version: str = "unknown"
    exit_code: int | None = None

    def __post_init__(self) -> None:
        if self.verdict not in VERDICT_VALUES:
            raise SacmatOpaRunnerError(
                "VERDICT_UNKNOWN", f"verdict {self.verdict!r} not in {sorted(VERDICT_VALUES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "backend": self.backend,
            "opa_version": self.opa_version,
            "exit_code": self.exit_code,
        }


# ---------------------------------------------------------------------------
# Binary detection and execution (real OPA only; no substitutes).
# ---------------------------------------------------------------------------


def detect_opa(binary_name: str = "opa") -> str | None:
    """Return the real OPA binary path from PATH, or None when absent."""
    return shutil.which(binary_name)


def _sanitize(text: str, limit: int = 200) -> str:
    collapsed = " ".join(str(text).split())
    return collapsed[:limit]


def _probe_opa_version(binary: str) -> str:
    """Best-effort real version probe of the detected binary (never faked)."""
    for argv in ([binary, "version", "--format=json"], [binary, "version"]):
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, timeout=5.0, check=False
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode != 0:
            continue
        try:
            payload = json.loads(completed.stdout)
            version = str(payload.get("Version", "")).strip()
            if version:
                return version
        except json.JSONDecodeError:
            pass
        first_line = completed.stdout.strip().splitlines()
        if first_line:
            return _sanitize(first_line[0], 80)
    return "unknown"


def run_opa_eval(
    module: str,
    opa_input: Mapping[str, Any],
    *,
    opa_binary: str | None = None,
    timeout_seconds: float = OPA_TIMEOUT_SECONDS,
) -> OpaVerdict:
    """Evaluate one Rego module + input document with the REAL OPA binary.

    Writes the module and input to a private temp directory, invokes
    ``opa eval --format=json`` and maps the binary's output onto the portable
    four-valued oracle: a defined string decision passes through; ``true`` /
    ``false`` boolean policies map to ``PERMIT`` / ``DENY``; OPA "undefined"
    (no result) maps to ``NOT_APPLICABLE``; execution failures, timeouts and
    unparseable output are ``INDETERMINATE`` with stable reason codes. When
    the binary is absent the verdict is ``NOT_RUN_EXTERNAL`` /
    ``BASELINE_UNAVAILABLE`` — the run is transparently not executed.
    """
    binary = opa_binary if opa_binary is not None else detect_opa()
    if binary is None:
        return OpaVerdict(
            verdict="NOT_RUN_EXTERNAL",
            reason_code=RC_BASELINE_UNAVAILABLE,
            detail=f"real OPA binary not found on PATH (pinned upstream {OPA_PINNED_VERSION})",
            backend=OPA_BINARY_BACKEND_PREFIX,
        )
    version = _probe_opa_version(binary)
    backend = f"{OPA_BINARY_BACKEND_PREFIX}:{version}"
    try:
        with tempfile.TemporaryDirectory(prefix="sacmat-x05-opa-") as tmp:
            module_path = Path(tmp) / "policy.rego"
            input_path = Path(tmp) / "input.json"
            module_path.write_text(module, encoding="utf-8")
            input_path.write_text(json.dumps(dict(opa_input)), encoding="utf-8")
            argv = [
                binary,
                "eval",
                "--format=json",
                "--data",
                str(module_path),
                "--input",
                str(input_path),
                OPA_QUERY,
            ]
            completed = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout_seconds, check=False
            )
    except subprocess.TimeoutExpired:
        return OpaVerdict(
            verdict=baselines.INDETERMINATE,
            reason_code=RC_OPA_TIMEOUT,
            detail=f"opa eval exceeded {timeout_seconds}s budget",
            backend=backend,
            opa_version=version,
        )
    except OSError as err:
        return OpaVerdict(
            verdict=baselines.INDETERMINATE,
            reason_code=RC_OPA_EXECUTION_ERROR,
            detail=f"opa eval failed to execute: {_sanitize(str(err))}",
            backend=backend,
            opa_version=version,
        )
    if completed.returncode != 0:
        return OpaVerdict(
            verdict=baselines.INDETERMINATE,
            reason_code=RC_OPA_EXECUTION_ERROR,
            detail=f"exit={completed.returncode} stderr={_sanitize(completed.stderr)}",
            backend=backend,
            opa_version=version,
            exit_code=completed.returncode,
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return OpaVerdict(
            verdict=baselines.INDETERMINATE,
            reason_code=RC_OPA_INVALID_OUTPUT,
            detail=f"stdout is not JSON: {_sanitize(completed.stdout)}",
            backend=backend,
            opa_version=version,
            exit_code=completed.returncode,
        )
    results = payload.get("result")
    if not results:
        return OpaVerdict(
            verdict=baselines.NOT_APPLICABLE,
            reason_code=baselines.NOT_APPLICABLE,
            detail="OPA evaluated the query as undefined (no result set)",
            backend=backend,
            opa_version=version,
            exit_code=completed.returncode,
        )
    try:
        value = results[0]["expressions"][0]["value"]
    except (KeyError, IndexError, TypeError):
        return OpaVerdict(
            verdict=baselines.INDETERMINATE,
            reason_code=RC_OPA_INVALID_OUTPUT,
            detail=f"unrecognized result shape: {_sanitize(json.dumps(payload))}",
            backend=backend,
            opa_version=version,
            exit_code=completed.returncode,
        )
    if isinstance(value, str) and value in VERDICT_VALUES:
        return OpaVerdict(
            verdict=value,
            reason_code=value,
            detail="string decision from data.clara.sacmat.delegated_consent.decision",
            backend=backend,
            opa_version=version,
            exit_code=completed.returncode,
        )
    if value is True:
        mapped = baselines.PERMIT
    elif value is False:
        mapped = baselines.DENY
    else:
        return OpaVerdict(
            verdict=baselines.INDETERMINATE,
            reason_code=RC_OPA_INVALID_OUTPUT,
            detail=f"unmapped decision value: {_sanitize(repr(value))}",
            backend=backend,
            opa_version=version,
            exit_code=completed.returncode,
        )
    return OpaVerdict(
        verdict=mapped,
        reason_code=mapped,
        detail="boolean policy result mapped onto the four-valued oracle",
        backend=backend,
        opa_version=version,
        exit_code=completed.returncode,
    )


def evaluate_opa(
    module: str,
    opa_input: Mapping[str, Any],
    *,
    opa_binary: str | None = None,
    timeout_seconds: float = OPA_TIMEOUT_SECONDS,
) -> str:
    """Task-contract adapter: ``evaluate_opa(module, input) -> Decision``.

    Thin wrapper over :func:`run_opa_eval` returning the portable Decision
    (``PERMIT`` / ``DENY`` / ``NOT_APPLICABLE`` / ``INDETERMINATE``), or the
    transparent sentinel ``NOT_RUN_EXTERNAL`` when the real binary is absent.
    Use :func:`run_opa_eval` when the reason code / backend / version provenance
    of the decision is needed.
    """
    return run_opa_eval(
        module, opa_input, opa_binary=opa_binary, timeout_seconds=timeout_seconds
    ).verdict


# ---------------------------------------------------------------------------
# Labelled in-process PORT of the XACML-like baseline engine.
# ---------------------------------------------------------------------------


def evaluate_xacml_port(history: PolicyHistory, req: Any = None) -> str:
    """PORT of ``baselines.XacmlPolicyEngine`` (labelled, in-process only).

    This is a faithful in-process port of the XACML-like deny-overrides model
    already implemented in ``evaluation/venue2027/sacmat/baselines.py``; it
    exists so parity checks and binary-absent callers have an executable,
    clearly-labelled decision source. It is NOT the upstream OPA binary and
    NEVER reported as a real OPA run (see ``XACML_PORT_LABEL``).
    """
    request = req if req is not None else history.request
    return XacmlPolicyEngine().evaluate(history, request)


# ---------------------------------------------------------------------------
# Deterministic Rego compilation from a validated case.
# ---------------------------------------------------------------------------


def _safe_identifier(value: str, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _SAFE_IDENTIFIER_MAX_LEN
        or not set(value) <= _SAFE_IDENTIFIER_CHARS
    ):
        raise SacmatOpaRunnerError(
            RC_UNSAFE_POLICY_IDENTIFIER,
            f"{field} {value!r} does not match the safe identifier allowlist",
        )
    return value


def build_opa_input(history: PolicyHistory) -> dict[str, Any]:
    """JSON-serializable input document for the compiled policy."""
    req = history.request
    return {
        "actor_id": _safe_identifier(req.actor_id, "request.actor_id"),
        "purpose": _safe_identifier(req.purpose, "request.purpose"),
        "decision_time": req.decision_time,
    }


def compile_rego_module(history: PolicyHistory) -> str:
    """Compile the case's final policy state into a deterministic Rego bundle.

    Deny-overrides over (actor, purpose) pairs, mirroring the labelled XACML
    port: deny pairs from REVOKE/EXPIRE final events, permit pairs from
    GRANT/REGRANT final events, DENY wins, otherwise the ``default`` yields
    ``NOT_APPLICABLE``. Deterministic: identical histories compile
    byte-identically (sorted emission, no clock, no randomness).
    """
    permits: set[tuple[str, str]] = set()
    denies: set[tuple[str, str]] = set()
    for key, final_event in history.final_state().items():
        pair = (key[0], key[2])
        _safe_identifier(pair[0], "history.actor_id")
        _safe_identifier(pair[1], "history.purpose")
        if final_event.event_kind in (EVENT_GRANT, EVENT_REGRANT):
            permits.add(pair)
        else:
            denies.add(pair)

    lines: list[str] = [
        "# Generated by evaluation/venue2027/sacmat/opa_runner.py"
        f" (SACMAT-X05_opa_runner, {OPA_RUNNER_VERSION}).",
        "# Encoding: final-state compiled delegated-consent policy,"
        " deny-overrides precedence.",
        f"# Limitations: {'; '.join(KNOWN_ENCODING_LIMITATIONS)}",
        "import rego.v1",
        "",
        f"package {REGO_PACKAGE}",
        "",
        'default decision := "NOT_APPLICABLE"',
        "",
    ]

    def pair_set_lines(name: str, pairs: set[tuple[str, str]]) -> list[str]:
        body = ",\n".join(
            f'\t{{"actor": "{actor}", "purpose": "{purpose}"}}'
            for actor, purpose in sorted(pairs)
        )
        return [f"{name} := {{\n{body},\n}}", ""]

    def match_rule(name: str, pairs_name: str) -> list[str]:
        return [
            f"{name} if {{",
            f"\tsome pair in {pairs_name}",
            "\tpair.actor == input.actor_id",
            "\tpair.purpose == input.purpose",
            "}",
            "",
        ]

    if denies:
        lines += pair_set_lines("_deny_pairs", denies)
        lines += match_rule("deny_match", "_deny_pairs")
    if permits:
        lines += pair_set_lines("_permit_pairs", permits)
        lines += match_rule("permit_match", "_permit_pairs")
    if denies and permits:
        lines += ['decision := "DENY" if deny_match', ""]
        lines += ["decision := \"PERMIT\" if {", "\tpermit_match", "\tnot deny_match", "}", ""]
    elif denies:
        lines += ['decision := "DENY" if deny_match', ""]
    elif permits:
        lines += ['decision := "PERMIT" if permit_match', ""]
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Harness adapter.
# ---------------------------------------------------------------------------


def _not_run_external(reason: str) -> Outcome:
    return Outcome(
        observed_outcome="NOT_RUN_EXTERNAL",
        counted_as_success=False,
        retriable=True,
        detail=f"{RC_BASELINE_UNAVAILABLE}|{reason}",
    )


def _indeterminate(reason_code: str, detail: str) -> Outcome:
    return Outcome(
        observed_outcome=baselines.INDETERMINATE,
        counted_as_success=False,
        retriable=False,
        detail=f"{reason_code}|{detail}",
    )


def run_opa_runner(case: Mapping[str, Any], ctx: SacmatContext) -> Outcome:
    """Evaluate one ``(policy history, request)`` case with the real OPA binary.

    Returns a first-class harness :class:`Outcome`:
    - real binary present: OPA's verdict is compared with the clearly-labelled
      ``xacml-port`` verdict — agreement is ``ADMIT``
      (``OPA_PORT_AGREEMENT``), disagreement is ``REJECT``
      (``OPA_PORT_DISAGREEMENT``); both carry ``counted_as_success=True`` and
      name both backends in the detail.
    - real binary absent (or ``ctx.simulate_unavailable_upstream``):
      ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` — never a fake success.
    - binary failure/timeout/invalid output or malformed case:
      ``INDETERMINATE`` with a stable reason code, never counted.
    - wiring errors (non-mapping case, non-SacmatContext) raise
      :class:`SacmatOpaRunnerError`.
    """
    if not isinstance(case, Mapping):
        raise SacmatOpaRunnerError(
            RC_CASE_NOT_AN_OBJECT, f"case must be a mapping, got {type(case)}"
        )
    if not isinstance(ctx, SacmatContext):
        raise SacmatOpaRunnerError(
            RC_CONTEXT_MALFORMED, f"ctx must be a SacmatContext, got {type(ctx)}"
        )
    validated = baselines._validate_case(case)
    if isinstance(validated, Outcome):
        return validated
    if ctx.simulate_unavailable_upstream:
        return _not_run_external(
            "OPA binary replay requires the pinned upstream binary; caller declared it unavailable"
        )
    try:
        module = compile_rego_module(validated)
        opa_input = build_opa_input(validated)
    except SacmatOpaRunnerError as err:
        return _indeterminate(err.reason_code, err.detail)
    opa_path = detect_opa()
    if opa_path is None:
        return _not_run_external(
            f"real OPA binary not found on PATH (pinned upstream {OPA_PINNED_VERSION})"
        )
    verdict = run_opa_eval(
        module, opa_input, opa_binary=opa_path, timeout_seconds=ctx.deadline_seconds
    )
    if verdict.verdict == "NOT_RUN_EXTERNAL":
        return _not_run_external(verdict.detail)
    if verdict.verdict == baselines.INDETERMINATE:
        return _indeterminate(verdict.reason_code, verdict.detail)
    port_decision = evaluate_xacml_port(validated)
    detail = (
        f"opa={verdict.verdict} backend={verdict.backend} version={verdict.opa_version} | "
        f"port={port_decision} backend={XACML_PORT_BACKEND} | {XACML_PORT_LABEL}"
    )
    if verdict.verdict == port_decision:
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            retriable=False,
            detail=f"{RC_OPA_PORT_AGREEMENT}|{detail}",
        )
    return Outcome(
        observed_outcome="REJECT",
        counted_as_success=True,
        retriable=False,
        detail=f"{RC_OPA_PORT_DISAGREEMENT}|{detail}",
    )
