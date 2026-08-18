"""W6 actual context builders (fixes AUD-050).

AUD-050 (BLOCKER) recorded that the previous router grid only changed a text
label such as ``Context condition: thss_strict`` while keeping the same scenario
text, which is not a valid context comparison.  This module replaces that with a
real context-builder abstraction: for a given ``(task, condition)`` it renders
the **actual context bytes/text** a model would see, together with the source
IDs that contributed, a deterministic token estimate, and a frozen SHA-256 of
those exact bytes.

Every condition must differ by ACTUAL CONTENT, not a label:

- ``thss_strict`` - includes the full governed disclosure block (the governed
  content disclosed under current consent) plus the co-versioned binding
  coordinates (consent/policy/state versions) and the state version.  This is
  the complete THSS context (maps to the GLHS_STRICT arm).
- ``thss_bound`` - co-versioned binding only: the consent/policy/state version
  coordinates are bundled as one co-versioned snapshot binding, but the full
  governed disclosure narrative text is NOT included (maps to the
  SNAPSHOT_BOUND_STATE_ONLY arm semantics).
- ``state_only`` - the state version coordinate only, no consent/policy
  coordinates and no governed disclosure content (maps to STATE_VERSION_ONLY).
- ``unbound`` - no governance context at all: only the scenario text (maps to
  UNBOUND).  It deliberately carries no version/disclosure content and no
  governance source IDs.

Task schema (plain mapping, synthetic/non-clinical):

- ``task_id``: str, unique case identifier.
- ``scenario``: str, the case scenario text shown to the model.
- ``state_version``: str, current governed state version coordinate.
- ``consent_version``: str, current consent version coordinate.
- ``policy_version``: str, current policy version coordinate.
- ``governed_disclosure_block``: str, the full governed disclosure block text
  (used by ``thss_strict`` only).
- ``source_ids``: tuple[str, ...], source IDs of the governed disclosure
  evidence (used by ``thss_strict`` only).

All builders are pure and deterministic: the same ``(task, condition)`` always
yields the same bytes, the same SHA-256, and the same token estimate.  The token
estimate is a deterministic length heuristic (``len(text) // 4``); the frozen
W6 run must record the provider-reported token counts and must not treat the
heuristic as a provider measurement.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

CONDITIONS = ("thss_strict", "thss_bound", "state_only", "unbound")

_GOVERNED_MARKER = "GOVERNED_DISCLOSURE"
_COVERSIONED_MARKER = "COVERSIONED_BINDING"
_STATE_MARKER = "STATE_VERSION"


@dataclass(frozen=True)
class BuiltContext:
    """Rendered context for one (task, condition) with integrity metadata."""

    condition: str
    task_id: str
    text: str
    source_ids: tuple[str, ...]
    token_estimate: int
    sha256: str
    content_bytes: bytes


class ContextBuilder(Protocol):
    """Builds the actual context content for one condition."""

    condition: str

    def build(self, task: Mapping[str, object]) -> BuiltContext: ...


def token_estimate(text: str) -> int:
    """Deterministic token-count heuristic (chars per token), never zero."""
    return max(1, len(text) // 4)


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require(task: Mapping[str, object], key: str) -> object:
    if key not in task:
        raise ValueError(f"task missing required field {key!r}")
    return task[key]


def _require_str(task: Mapping[str, object], key: str) -> str:
    value = _require(task, key)
    if not isinstance(value, str):
        raise TypeError(
            f"task field {key!r} must be a string, got {type(value).__name__}"
        )
    return value


def _source_ids(task: Mapping[str, object]) -> tuple[str, ...]:
    value = task.get("source_ids", ())
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


class _Unbound:
    """No governance context: scenario only. Maps to the UNBOUND arm."""

    condition = "unbound"

    def build(self, task: Mapping[str, object]) -> BuiltContext:
        scenario = _require_str(task, "scenario")
        text = f"Scenario: {scenario}"
        return BuiltContext(
            condition=self.condition,
            task_id=_require_str(task, "task_id"),
            text=text,
            source_ids=(),
            token_estimate=token_estimate(text),
            sha256=content_sha256(text),
            content_bytes=text.encode("utf-8"),
        )


class _StateOnly:
    """State version coordinate only; no consent/policy or disclosure content."""

    condition = "state_only"

    def build(self, task: Mapping[str, object]) -> BuiltContext:
        scenario = _require_str(task, "scenario")
        state_version = _require_str(task, "state_version")
        text = (
            f"Scenario: {scenario}\n"
            f"[{_STATE_MARKER}] current state version: {state_version}"
        )
        return BuiltContext(
            condition=self.condition,
            task_id=_require_str(task, "task_id"),
            text=text,
            source_ids=(f"state_version:{state_version}",),
            token_estimate=token_estimate(text),
            sha256=content_sha256(text),
            content_bytes=text.encode("utf-8"),
        )


class _ThssBound:
    """Co-versioned binding: consent/policy/state versions bundled; no disclosure narrative."""

    condition = "thss_bound"

    def build(self, task: Mapping[str, object]) -> BuiltContext:
        scenario = _require_str(task, "scenario")
        state_version = _require_str(task, "state_version")
        consent_version = _require_str(task, "consent_version")
        policy_version = _require_str(task, "policy_version")
        text = (
            f"Scenario: {scenario}\n"
            f"[{_COVERSIONED_MARKER}] snapshot binding co-versions: "
            f"consent={consent_version}, policy={policy_version}, state={state_version}"
        )
        return BuiltContext(
            condition=self.condition,
            task_id=_require_str(task, "task_id"),
            text=text,
            source_ids=(
                f"consent_version:{consent_version}",
                f"policy_version:{policy_version}",
                f"state_version:{state_version}",
            ),
            token_estimate=token_estimate(text),
            sha256=content_sha256(text),
            content_bytes=text.encode("utf-8"),
        )


class _ThssStrict:
    """Full governed disclosure block plus co-versioned binding and state version."""

    condition = "thss_strict"

    def build(self, task: Mapping[str, object]) -> BuiltContext:
        scenario = _require_str(task, "scenario")
        state_version = _require_str(task, "state_version")
        consent_version = _require_str(task, "consent_version")
        policy_version = _require_str(task, "policy_version")
        disclosure = _require_str(task, "governed_disclosure_block")
        evidence_ids = _source_ids(task)
        text = (
            f"Scenario: {scenario}\n"
            f"[{_GOVERNED_MARKER}] full governed disclosure block:\n{disclosure}\n"
            f"[{_COVERSIONED_MARKER}] snapshot binding co-versions: "
            f"consent={consent_version}, policy={policy_version}, state={state_version}\n"
            f"[{_STATE_MARKER}] current state version: {state_version}"
        )
        return BuiltContext(
            condition=self.condition,
            task_id=_require_str(task, "task_id"),
            text=text,
            source_ids=(
                *evidence_ids,
                f"consent_version:{consent_version}",
                f"policy_version:{policy_version}",
                f"state_version:{state_version}",
            ),
            token_estimate=token_estimate(text),
            sha256=content_sha256(text),
            content_bytes=text.encode("utf-8"),
        )


BUILDERS: dict[str, ContextBuilder] = {
    builder.condition: builder()
    for builder in (_Unbound, _StateOnly, _ThssBound, _ThssStrict)
}


def build_context(task: Mapping[str, object], condition: str) -> BuiltContext:
    """Render the actual context for ``(task, condition)``.

    Raises ValueError for an unknown condition or a task missing a required
    field, so a malformed grid fails loudly instead of silently swapping in a
    label-only prompt.
    """
    if condition not in CONDITIONS:
        raise ValueError(f"unknown context condition {condition!r}; expected one of {CONDITIONS}")
    return BUILDERS[condition].build(task)


def hash_context(task: Mapping[str, object], condition: str) -> str:
    """Frozen context hash per (task, condition); stable across calls."""
    return build_context(task, condition).sha256
