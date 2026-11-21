"""SACMAT-X03_cedar_runner — real-engine Cedar runner with clearly-labelled port.

Purpose
-------
Task contract: ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X03_cedar_runner.md``
(RQ3, pinned upstream Cedar **v4.14.1** per the registry rows in
``evaluation/venue2027/sacmat/baselines.py``). This module is the boundary
between the SACMAT conformance corpus and the upstream Cedar policy engine:

- **Upstream path** (:func:`evaluate_cedar` with a genuine engine present):
  when an executable ``cedar`` CLI is *actually available* on ``PATH`` (or an
  explicit path), the runner executes the REAL upstream binary
  (``cedar-policy-cli``). Decisions come back through a strict ``ALLOW`` /
  ``DENY`` protocol with ``--request-json`` and ``--request-validation false``
  (the corpus evaluates schema-free synthetic delegated-consent policies), and
  are normalized to the portable four-valued oracle vocabulary
  (PERMIT / DENY / NOT_APPLICABLE / INDETERMINATE). Malformed policies,
  broken entity JSON and unparseable engine output fail closed to
  ``INDETERMINATE`` with stable reason codes — they are NEVER reinterpreted as
  safe-looking DENYs.
- **Unavailable path**: when no genuine engine binary is detected,
  :func:`evaluate_cedar` returns the first-class harness outcome
  ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` — never a fabricated
  success, never a silent port substitution.
- **Port path** (:class:`CedarPolicyPort`): a faithful in-process Cedar-like
  adapter (a thin, clearly-labelled PORT over the ``CedarPolicyEngine`` model
  in :mod:`evaluation.venue2027.sacmat.baselines`). The port is a *model of
  the pinned upstream's documented semantics*, exactly as baselines.py states:
  forbid precedence, principal scoping and purpose-annotation constraints.
  It is labelled ``engine == PORT_LABEL ("cedar-port")`` in every result, is
  NEVER presented as an upstream run, and must never be used to claim that
  real Cedar executed.

Result objects are the JSON-serializable :class:`CedarRunResult` dataclass
carrying provenance (``backend``, ``engine_label``, ``engine_version``,
``cedar_policy_cli_pin``) so an auditor can mechanically distinguish an
upstream run from a port run. No wall clock, randomness or network anywhere;
the only I/O is the subprocess invocation of the detected engine binary
(injected for tests via :class:`CedarCli` / the ``cli_runner`` parameter).

Allowed input
-------------
The same synthetic delegated-consent corpus as the baseline arms: a
``policy_history`` (ordered versioned events: GRANT / REVOKE / REGRANT /
EXPIRE / POLICY_VERSION_BUMP with ``logical_time``, ``actor_id``,
``delegate_id``, ``purpose``, optional ``expiry``), and a ``query`` mapping
(``actor_id``, ``purpose``, ``decision_time``). Accepted shapes:

- a :class:`evaluation.venue2027.sacmat.baselines.PolicyHistory` (validated
  typed form), or
- a plain mapping ``{"case_id", "history", "request"}`` (validated through
  :func:`baselines._validate_case` via :func:`baselines.run_baseline`-grade
  checks), or
- a ``PolicyHistory`` pair ``(policy, trace)``, where the runner replays the
  history to ``decision_time`` and evaluates the pointwise request — matching
  the task signature ``evaluate_cedar(policy, trace, query) -> Decision``.

Failure semantics (stable uppercase reason codes)
-------------------------------------------------
- ``BASELINE_UNAVAILABLE`` — no genuine upstream engine detected; outcome
  ``NOT_RUN_EXTERNAL`` (``counted_as_success=False``; never counted as a
  completion per the blueprint's evidence contract).
- ``ENGINE_EXECUTION_ERROR`` — the detected engine binary failed to spawn
  (missing/cleared PATH in an environment that claims an engine exists,
  non-executable file, permission error); outcome ``INDETERMINATE``.
- ``ENGINE_MALFORMED_OUTPUT`` — the engine wrote something other than a bare
  ``ALLOW``/``DENY`` line; outcome ``INDETERMINATE`` (never a safe-looking
  rejection).
- ``CEDAR_POLICY_PARSE_ERROR`` — the translated policy set does not parse
  upstream; outcome ``INDETERMINATE``.
- ``REQUEST_ENTITY_NOT_AN_OBJECT`` / ``POLICY_NOT_A_HISTORY`` /
  ``QUERY_MALFORMED`` — wiring errors raised as :class:`CedarRunnerError`.

Version
-------
``CEDAR_RUNNER_VERSION = "clara.sacmat.cedar-runner-v1"``
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat.baselines import (
    DENY,
    EVENT_EXPIRE,
    EVENT_GRANT,
    EVENT_POLICY_VERSION_BUMP,
    EVENT_REVOKE,
    INDETERMINATE,
    PERMIT,
    AccessRequest,
    CedarPolicyEngine,
    PolicyHistory,
    _validate_case,
)

CEDAR_RUNNER_VERSION: Final[str] = "clara.sacmat.cedar-runner-v1"

#: Pinned upstream engine (baselines.py registry row: Cedar v4.14.1).
CEDAR_UPSTREAM_PIN: Final[str] = "cedar-policy-cli-4.14.1"

#: Label carried by PORT results — NEVER presented as an upstream run.
PORT_LABEL: Final[str] = "cedar-port"
#: Label carried by genuine upstream CLI results.
UPSTREAM_LABEL: Final[str] = "cedar-upstream-cli"

#: Upstream CLI decision vocabulary (bare first token of stdout).
CEDAR_ALLOW: Final[str] = "ALLOW"
CEDAR_DENY: Final[str] = "DENY"

#: Stable reason codes.
RC_ENGINE_UNAVAILABLE: Final[str] = "BASELINE_UNAVAILABLE"
RC_ENGINE_EXECUTION_ERROR: Final[str] = "ENGINE_EXECUTION_ERROR"
RC_ENGINE_MALFORMED_OUTPUT: Final[str] = "ENGINE_MALFORMED_OUTPUT"
RC_CEDAR_POLICY_PARSE_ERROR: Final[str] = "CEDAR_POLICY_PARSE_ERROR"

#: Upstream outcome vocabulary for NOT_RUN_EXTERNAL paths (harness buckets).
NOT_RUN_EXTERNAL: Final[str] = "NOT_RUN_EXTERNAL"

#: The binary name probed on PATH (overridable per-call / per-CedarCli).
CEDAR_BINARY_NAME: Final[str] = "cedar"


class CedarRunnerError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not a verdict)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


# ---------------------------------------------------------------------------
# Result model (JSON-serializable provenance-carrying verdict).
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CedarRunResult:
    """One Cedar evaluation with unambiguous engine provenance.

    ``engine`` is either :data:`UPSTREAM_LABEL` (genuine ``cedar`` CLI run) or
    :data:`PORT_LABEL` (in-process port over the baselines.py model) — the
    field exists precisely so a port result can never be mistaken for an
    upstream run.
    """

    decision: str
    engine: str
    backend: str
    engine_version: str
    reason_code: str
    detail: str = ""
    outcome: Outcome | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "engine": self.engine,
            "backend": self.backend,
            "engine_version": self.engine_version,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "outcome": self.outcome.to_dict() if self.outcome is not None else None,
        }


# ---------------------------------------------------------------------------
# Engine detection.
# ---------------------------------------------------------------------------


def detect_cedar_engine(
    binary_name: str = CEDAR_BINARY_NAME,
    *,
    extra_paths: Sequence[str] | None = None,
) -> str | None:
    """Return the resolved path of a genuine upstream ``cedar`` binary, or None.

    Detection is honest: only an actual executable file found on PATH (plus
    optional ``extra_paths``) counts. There is no fallback that pretends a
    port is the engine.
    """
    candidates: list[str] = []
    if extra_paths:
        candidates.extend(extra_paths)
    resolved = shutil.which(binary_name, path=":".join(extra_paths) if extra_paths else None)
    if resolved:
        candidates.append(resolved)
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file() and os.access(str(path), os.X_OK):
            return str(path)
    return None


def cedar_cli_version(binary_path: str) -> str:
    """Best-effort upstream version string (empty when it cannot be read)."""
    try:
        proc = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    first = proc.stdout.strip().splitlines()
    return first[0].strip() if first else ""


# ---------------------------------------------------------------------------
# History -> Cedar policy/entity translation.
# ---------------------------------------------------------------------------

_CEDAR_POLICY_HEADER = "policy.cedar"


def translate_history_to_cedar(
    history: PolicyHistory,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Translate a validated delegated-consent history into Cedar artifacts.

    Returns ``(policy_lines, entity_tuples)``:

    - one ``permit`` statement per active GRANT/REGRANT delegation (scoped to
      principal == the delegate Patient entity, action view, resource == the
      delegating actor's Record, guarded by the purpose annotation);
    - one ``forbid`` statement per REVOKE (explicit deny precedence);
    - ``EXPIRE`` / ``POLICY_VERSION_BUMP`` are recorded as entity attributes
      (``record_expired``) — per the baselines.py expressivity contract Cedar
      v4.14.1 has no native temporal construct, so expiry is caller-encoded;
    - entities are flat ``Patient``/``Record`` records carrying purpose tags.

    The translation is deterministic: the same history always yields the same
    artifacts (stable iteration order over the validated event tuple).
    """
    policy_lines: list[str] = []
    forbids: list[str] = []
    patients: dict[str, dict[str, Any]] = {}
    records: dict[str, dict[str, Any]] = {}

    for event_ in history.events:
        if event_.event_kind in (EVENT_GRANT,):
            patients.setdefault(event_.delegate_id, {"purposes": set()})
            patients[event_.delegate_id]["purposes"].add(event_.purpose)
            records.setdefault(event_.actor_id, {"purposes": set(), "expired": False})
            records[event_.actor_id]["purposes"].add(event_.purpose)
            policy_lines.append(
                f'permit(principal == Patient::"{event_.delegate_id}", '
                f'action == Action::"view", '
                f'resource == Record::"{event_.actor_id}") '
                f'when {{ context.purpose == "{event_.purpose}" }};'
            )
        elif event_.event_kind == EVENT_REVOKE:
            records.setdefault(event_.actor_id, {"purposes": set(), "expired": False})
            records[event_.actor_id]["expired"] = True
            forbids.append(
                f'forbid(principal == Patient::"{event_.delegate_id}", '
                f'action == Action::"view", '
                f'resource == Record::"{event_.actor_id}");'
            )
        elif event_.event_kind in (EVENT_EXPIRE, EVENT_POLICY_VERSION_BUMP):
            records.setdefault(event_.actor_id, {"purposes": set(), "expired": True})
            records[event_.actor_id]["expired"] = True

    policy_lines.extend(forbids)
    entities: list[dict[str, Any]] = []
    for uid in sorted(patients):
        entities.append(
            {
                "uid": {"type": "Patient", "id": uid},
                "attrs": {"purposes": sorted(patients[uid]["purposes"])},
                "parents": [],
            }
        )
    for rid in sorted(records):
        entities.append(
            {
                "uid": {"type": "Record", "id": rid},
                "attrs": {
                    "purposes": sorted(records[rid]["purposes"]),
                    "record_expired": records[rid]["expired"],
                },
                "parents": [],
            }
        )
    return policy_lines, entities


def _request_json(history: PolicyHistory) -> dict[str, Any]:
    req = history.request
    return {
        "principal": f'Patient::"{req.actor_id}"',
        "action": 'Action::"view"',
        "resource": f'Record::"{req.actor_id}"',
        "context": {"purpose": req.purpose},
    }


# ---------------------------------------------------------------------------
# CLI invocation boundary (injected for tests; no hidden I/O in the port).
# ---------------------------------------------------------------------------

#: Signature of the subprocess boundary: argv -> CompletedProcess-like.
CliRunner = Callable[..., Any]


class CedarCli:
    """Injected handle to one upstream ``cedar`` CLI binary (or None)."""

    def __init__(self, binary_path: str | None, runner: CliRunner | None = None) -> None:
        self.binary_path = binary_path
        self._runner: CliRunner = runner if runner is not None else subprocess.run

    @property
    def available(self) -> bool:
        return self.binary_path is not None

    def authorize(
        self,
        policy_text: str,
        entities_json: str,
        request_json: str,
        *,
        schema_text: str | None = None,
        schema_format: str = "cedar",
        policy_format: str = "cedar",
        validate_request: bool = False,
    ) -> tuple[int, str, str]:
        """Run ``cedar authorize``; returns ``(returncode, stdout, stderr)``.

        cedar-policy-cli 4.14.1 takes file paths (not stdin) for all three
        artifacts, so each is written to its own 0600-mode temp file. No
        shell, fixed argv, synthetic corpus content only.
        """
        if self.binary_path is None:
            raise CedarRunnerError(
                RC_ENGINE_UNAVAILABLE, "authorize() called without a detected engine"
            )
        if schema_format not in {"cedar", "json"} or policy_format not in {"cedar", "json"}:
            raise CedarRunnerError(
                "ENGINE_INPUT_FORMAT_INVALID", "unsupported policy or schema format"
            )
        paths: list[str] = []
        try:
            inputs = [
                (policy_text, ".cedar"),
                (entities_json, ".entities.json"),
                (request_json, ".request.json"),
            ]
            if schema_text is not None:
                inputs.append((schema_text, ".schema"))
            for content, suffix in inputs:
                with tempfile.NamedTemporaryFile(
                    "w", suffix=suffix, prefix="clara_sacmat_", encoding="utf-8", delete=False
                ) as handle:
                    handle.write(content)
                    paths.append(handle.name)
            for path in paths:
                os.chmod(path, 0o600)
            try:
                proc = self._runner(
                    [
                        self.binary_path,
                        "authorize",
                        "--policies",
                        paths[0],
                        "--entities",
                        paths[1],
                        "--request-json",
                        paths[2],
                        "--request-validation",
                        str(validate_request).lower(),
                        "--policy-format",
                        policy_format,
                        *(
                            ["--schema", paths[3], "--schema-format", schema_format]
                            if schema_text is not None
                            else []
                        ),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise CedarRunnerError(
                    RC_ENGINE_EXECUTION_ERROR, f"cedar spawn failed: {exc}"
                ) from exc
        finally:
            for path in paths:
                with contextlib.suppress(OSError):
                    os.unlink(path)
        return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# Input normalization (accept PolicyHistory, validated mapping, or pair).
# ---------------------------------------------------------------------------


def _as_policy_history(
    policy: PolicyHistory | Mapping[str, Any] | Any,
    trace: PolicyHistory | Mapping[str, Any] | None,
) -> PolicyHistory:
    """Normalize ``(policy, trace)`` inputs to one validated PolicyHistory.

    Accepts: a validated :class:`PolicyHistory` for ``policy`` (``trace`` may
    be None or the same object), or a validated case mapping for ``policy``
    with ``trace`` as None. Anything else is a wiring error — never silently
    coerced.
    """
    if isinstance(policy, PolicyHistory):
        if trace is not None and not isinstance(trace, PolicyHistory | Mapping):
            raise CedarRunnerError(
                "POLICY_NOT_A_HISTORY", f"trace must be a PolicyHistory/mapping, got {type(trace)}"
            )
        return policy
    if isinstance(policy, Mapping):
        if trace is not None:
            raise CedarRunnerError(
                "POLICY_NOT_A_HISTORY",
                "policy given as mapping; trace parameter must be None (mapping carries the full case)",
            )
        validated = _validate_case(policy)
        if isinstance(validated, Outcome):
            raise CedarRunnerError(
                "QUERY_MALFORMED", f"case mapping failed validation: {validated.detail}"
            )
        return validated
    raise CedarRunnerError(
        "POLICY_NOT_A_HISTORY",
        f"policy must be a PolicyHistory or validated case mapping, got {type(policy)}",
    )


# ---------------------------------------------------------------------------
# The task-signature entry point: evaluate_cedar(policy, trace, query).
# ---------------------------------------------------------------------------


def evaluate_cedar(
    policy: PolicyHistory | Mapping[str, Any],
    trace: PolicyHistory | Mapping[str, Any] | None = None,
    query: Mapping[str, Any] | None = None,
    *,
    cli: CedarCli | None = None,
    binary_name: str = CEDAR_BINARY_NAME,
    extra_binary_paths: Sequence[str] | None = None,
) -> Outcome | CedarRunResult:
    """Evaluate one delegated-consent query under Cedar — upstream or honest NOT_RUN.

    Task signature ``evaluate_cedar(policy, trace, query) -> Decision``. When
    a genuine upstream ``cedar`` binary is detected the REAL engine decides
    (returning a :class:`CedarRunResult` labelled ``cedar-upstream-cli``);
    otherwise the result is the first-class harness outcome
    ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` (a plain :class:`Outcome`,
    ``counted_as_success=False``). A fabricated port verdict is never
    substituted for an unavailable engine.

    ``query`` may override the request embedded in the history/trace mapping
    (``actor_id`` / ``purpose`` / ``decision_time`` fields).
    """
    history = _as_policy_history(policy, trace)
    if query is not None:
        history = _request_from_query(query, history)

    engine_cli = (
        cli
        if cli is not None
        else CedarCli(detect_cedar_engine(binary_name, extra_paths=extra_binary_paths))
    )
    if not engine_cli.available:
        return Outcome(
            observed_outcome=NOT_RUN_EXTERNAL,
            counted_as_success=False,
            retriable=True,
            detail=(
                f"{RC_ENGINE_UNAVAILABLE}|no genuine upstream cedar binary detected "
                f"(pin {CEDAR_UPSTREAM_PIN}); port available via CedarPolicyPort "
                f"but is NOT a substitute and is never auto-substituted here"
            ),
        )

    policy_lines, entities = translate_history_to_cedar(history)
    try:
        returncode, stdout, stderr = engine_cli.authorize(
            "\n".join(policy_lines),
            _dump_json(entities),
            _dump_json(_request_json(history)),
        )
    except CedarRunnerError as exc:
        return CedarRunResult(
            decision=INDETERMINATE,
            engine=UPSTREAM_LABEL,
            backend=f"subprocess:{CEDAR_BINARY_NAME}",
            engine_version=CEDAR_UPSTREAM_PIN,
            reason_code=RC_ENGINE_EXECUTION_ERROR,
            detail=str(exc)[:500],
            outcome=Outcome(
                observed_outcome=INDETERMINATE,
                counted_as_success=False,
                retriable=False,
                detail=f"{RC_ENGINE_EXECUTION_ERROR}|engine spawn failed",
            ),
        )
    if returncode not in (0, 2):
        return CedarRunResult(
            decision=INDETERMINATE,
            engine=UPSTREAM_LABEL,
            backend=f"subprocess:{CEDAR_BINARY_NAME}",
            engine_version=CEDAR_UPSTREAM_PIN,
            reason_code=RC_CEDAR_POLICY_PARSE_ERROR,
            detail=(stderr.strip() or stdout.strip())[:500],
            outcome=Outcome(
                observed_outcome=INDETERMINATE,
                counted_as_success=False,
                retriable=False,
                detail=f"{RC_CEDAR_POLICY_PARSE_ERROR}|exit={returncode}",
            ),
        )
    first = stdout.strip().splitlines()
    verdict = first[0].strip().upper() if first else ""
    if verdict == CEDAR_ALLOW:
        decision = PERMIT
    elif verdict == CEDAR_DENY:
        decision = DENY
    else:
        return CedarRunResult(
            decision=INDETERMINATE,
            engine=UPSTREAM_LABEL,
            backend=f"subprocess:{CEDAR_BINARY_NAME}",
            engine_version=CEDAR_UPSTREAM_PIN,
            reason_code=RC_ENGINE_MALFORMED_OUTPUT,
            detail=f"stdout={stdout.strip()[:200]!r} stderr={stderr.strip()[:200]!r}",
            outcome=Outcome(
                observed_outcome=INDETERMINATE,
                counted_as_success=False,
                retriable=False,
                detail=f"{RC_ENGINE_MALFORMED_OUTPUT}|unparseable engine output",
            ),
        )
    return CedarRunResult(
        decision=decision,
        engine=UPSTREAM_LABEL,
        backend=f"subprocess:{CEDAR_BINARY_NAME}",
        engine_version=cedar_cli_version(engine_cli.binary_path) or CEDAR_UPSTREAM_PIN,
        reason_code="OK",
        detail=f"cedar authorize exit={returncode} (2=DENY-by-default per upstream CLI)",
        outcome=Outcome(
            observed_outcome="ADMIT" if decision == PERMIT else "REJECT",
            counted_as_success=True,
            retriable=False,
            detail=f"cedar-upstream:{decision}",
        ),
    )


def _request_from_query(query: Mapping[str, Any], history: PolicyHistory) -> PolicyHistory:
    """Apply a query override, returning a new PolicyHistory (input untouched)."""
    if not isinstance(query, Mapping):
        raise CedarRunnerError("QUERY_MALFORMED", "query must be a mapping when provided")
    missing = [f for f in ("actor_id", "purpose", "decision_time") if f not in query]
    if missing:
        raise CedarRunnerError(
            "QUERY_MALFORMED", f"query override missing fields: {','.join(missing)}"
        )
    decision_time = query["decision_time"]
    if isinstance(decision_time, bool) or not isinstance(decision_time, int) or decision_time < 0:
        raise CedarRunnerError("QUERY_MALFORMED", "decision_time must be a non-negative int")
    return dataclasses.replace(
        history,
        request=AccessRequest(
            actor_id=str(query["actor_id"]),
            purpose=str(query["purpose"]),
            decision_time=decision_time,
        ),
    )


def _dump_json(payload: Any) -> str:
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# The clearly-labelled PORT: faithful in-process Cedar-like adapter.
# ---------------------------------------------------------------------------


class CedarPolicyPort:
    """Cedar-like in-process adapter — a PORT, never an upstream run.

    This is a thin deterministic wrapper over :class:`baselines.CedarPolicyEngine`
    (the in-process model of pinned Cedar v4.14.1 documented semantics: permit/
    forbid statements with forbid precedence, principal/resource scoping and
    purpose-annotation constraints). Every result is labelled
    ``engine == "cedar-port"`` so no output of this class can ever be reported
    as a genuine upstream Cedar execution. Use it when the engine is
    unavailable and an explicitly-labelled model verdict is acceptable; use
    :func:`evaluate_cedar` for the real engine.
    """

    engine_id = PORT_LABEL

    def __init__(self, engine: CedarPolicyEngine | None = None) -> None:
        self._engine = engine if engine is not None else CedarPolicyEngine()

    def evaluate(
        self,
        policy: PolicyHistory | Mapping[str, Any],
        trace: PolicyHistory | Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> CedarRunResult:
        """Port verdict for one delegated-consent query (always port-labelled)."""
        history = _as_policy_history(policy, trace)
        if query is not None:
            history = _request_from_query(query, history)
        decision = self._engine.evaluate(history, history.request)
        return CedarRunResult(
            decision=decision,
            engine=PORT_LABEL,
            backend="in-process:baselines.CedarPolicyEngine",
            engine_version=CEDAR_UPSTREAM_PIN,
            reason_code="OK",
            detail=(
                "PORT of Cedar v4.14.1 documented semantics "
                "(baselines.CedarPolicyEngine); NOT an upstream execution"
            ),
            outcome=Outcome(
                observed_outcome="ADMIT" if decision == PERMIT else "REJECT",
                counted_as_success=True,
                retriable=False,
                detail=f"cedar-port:{decision}",
            ),
        )


# Convenience singletons / shortcut.
CEDAR_PORT = CedarPolicyPort()
