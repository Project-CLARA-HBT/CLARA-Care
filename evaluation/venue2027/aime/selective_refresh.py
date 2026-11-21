"""AIME-X06_selective_refresh (Phase P04, venue ``aime``) — selective clinical re-generation.

Purpose
-------
Reference implementation of the purpose-aware **selective consent-aware context
regeneration** candidate (blueprint arm B4,
``research/venue2027/VENUES/aime/RESEARCH_BLUEPRINT.md`` §Strong baselines; task
contract ``research/venue2027/VENUES/aime/TASKS/AIME-X06_selective_refresh.md``).
When one field of a longitudinal clinical workflow state changes, the refresh
operator rebuilds ONLY the evidence/purpose dependencies the changed field can
actually affect — instead of paying the full per-step re-derivation that the
strict comparator (blueprint arm B1, ``evaluation/venue2027/aime/baselines.py``)
pays at every step.

Safety-first decision relation (deterministic; no clock, no randomness, no I/O):

- ``PARTIAL`` — only for a change proven unable to touch medication, allergy or
  consent interpretation (an unrelated note edit): recompute exactly the
  affected dependencies and carry every other dependency over unchanged.
- ``FULL`` — any consent/purpose change (the authorization epoch co-determines
  every dependency), any medication or allergy change that could not be proven
  non-entangled, an unknown/undeclared changed field, a malformed or incomplete
  state, or a declared dependency the caller does not actually hold. The FULL
  path re-derives every dependency and never silently drops a missing one.
- ``CLINICIAN_REVIEW`` — the failure-proof path: when medication and allergy
  contexts are BOTH clinically populated (or one side is unverifiable) a change
  to either side is clinically ENTANGLED — a change to one affects the
  interpretation of the other through the shared drug–allergy interaction
  screen — so no automatic partial refresh may run: the plan routes to blinded
  clinician review instead. Conflicting observations route here too.

Entanglement detection (:func:`is_entangled`, :func:`pair_entangled`) is
structural and deterministic: two changed fields are entangled when they share
a dependency in :data:`DEPENDENCY_GRAPH`; the concrete clinical instance is the
``medications``/``allergies`` pair sharing ``purpose_ddi_screen``. The
automatic no-partial protection routes the medication/allergy pair to
``CLINICIAN_REVIEW``; consent/purpose changes are already ``FULL`` by the
consent rule regardless.

This module is pure and self-contained (stdlib only): the decision relation
imports no candidate/baseline/oracle module at runtime. Cross-checks against
the real B1 adapter and the independent oracle live in the test layer
(``evaluation/venue2027/aime/test_selective_refresh.py``).

Allowed input
-------------
A JSON-serializable ``state`` mapping with synthetic content only: required
sections ``medications`` (list of non-empty strings) and ``consent`` (mapping
with ``granted_purposes``); optional ``allergies`` (list of non-empty strings),
``notes``, ``task`` and a boolean ``conflicting_observations`` flag.
PHI-like field names (``patient_name``, ``email``, ``mrn``, ...) are refused
fail-closed. ``changed_field`` is a section name; unknown names fail closed to
FULL. No network, no database, no provider, no clock, no randomness: the
module is a pure function of its inputs.

Failure semantics
-----------------
Every refusal is a stable uppercase reason code on a :class:`RefreshPlan` with
mode ``FULL`` or ``CLINICIAN_REVIEW`` — a malformed, incomplete, unverifiable
or out-of-scope input is NEVER answered with a silent partial refresh and
never counted as a safe completion. ``PARTIAL`` requires positive proof of
non-entanglement and a fully-populated, well-typed state. The
``input_sha256`` is an observability digest of the canonical input only; it is
never used as clinical reasoning proof.

Version
-------
``SELECTIVE_REFRESH_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

SELECTIVE_REFRESH_VERSION = "1.0.0"

#: Refresh modes (``RefreshPlan.mode``). ``CLINICIAN_REVIEW`` is first-class:
#: it is never coerced into an automatic PARTIAL or a silent completion.
MODE_PARTIAL = "PARTIAL"
MODE_FULL = "FULL"
MODE_CLINICIAN_REVIEW = "CLINICIAN_REVIEW"
REFRESH_MODES: frozenset[str] = frozenset({MODE_PARTIAL, MODE_FULL, MODE_CLINICIAN_REVIEW})

#: Stable reason codes (all match ``REASON_CODE_RE``).
REASON_PARTIAL_OK = "PARTIAL_REFRESH_OK"
REASON_CONSENT_FULL = "CONSENT_CHANGE_FULL_REFRESH"
REASON_MEDICATION_FULL = "MEDICATION_CHANGE_FULL_REFRESH"
REASON_ALLERGY_FULL = "ALLERGY_CHANGE_FULL_REFRESH"
REASON_ENTANGLED = "MEDICATION_ALLERGY_ENTANGLED"
REASON_CONFLICTING = "CONFLICTING_OBSERVATIONS_CLINICIAN_REVIEW"
REASON_UNKNOWN_FIELD = "UNKNOWN_CHANGED_FIELD_FULL_REFRESH"
REASON_UNKNOWN_DEPENDENCY = "UNKNOWN_DEPENDENCY_FULL_REFRESH"
REASON_MISSING_DEPENDENCIES = "MISSING_DEPENDENCIES_FULL_REFRESH"
REASON_MALFORMED = "REFRESH_STATE_MALFORMED"
REASON_MISSING_FIELD = "REFRESH_MISSING_FIELD"
REASON_PHI_FIELDS = "REFRESH_STATE_PHI_FIELDS"

REASON_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Dependency graph: dependency name -> the changed fields that can affect it.
#: ``purpose_ddi_screen`` is the shared drug–allergy interaction screen: it is
#: affected by BOTH medication and allergy changes, which is exactly why the
#: pair is clinically entangled.
DEPENDENCY_GRAPH: dict[str, frozenset[str]] = {
    "purpose_scope": frozenset({"consent", "purpose"}),
    "evidence_authorization": frozenset({"consent"}),
    "evidence_medication_list": frozenset({"medications"}),
    "evidence_allergy_list": frozenset({"allergies"}),
    "purpose_ddi_screen": frozenset({"medications", "allergies"}),
    "evidence_note_summary": frozenset({"notes"}),
}

#: The clinically entangled pair named by the task contract: a change to one
#: side affects the interpretation of the other. Never eligible for PARTIAL.
ENTANGLED_FIELDS: frozenset[str] = frozenset({"medications", "allergies"})

#: Field-name synonyms accepted at the input boundary (normalized silently).
_FIELD_SYNONYMS: dict[str, str] = {
    "medication": "medications",
    "drug": "medications",
    "allergy": "allergies",
    "allergic_reaction": "allergies",
    "consent_grant": "consent",
    "consent_revocation": "consent",
    "note": "notes",
    "observation_note": "notes",
    "unrelated_note": "notes",
}

_CONSENT_FIELDS: frozenset[str] = frozenset({"consent", "purpose"})
_MEDICATION_FIELDS: frozenset[str] = frozenset({"medications"})
_ALLERGY_FIELDS: frozenset[str] = frozenset({"allergies"})
#: The only field class eligible for an automatic partial refresh.
_PARTIAL_ELIGIBLE_FIELDS: frozenset[str] = frozenset({"notes"})

_STATE_REQUIRED_FIELDS: tuple[str, ...] = ("medications", "consent")

#: PHI-like field names refused at the input boundary (mirrors
#: ``research/venue2027/_shared/data_ethics_and_irb.md`` item 3).
_PHI_LIKE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "full_name",
        "patient_name",
        "email",
        "phone",
        "address",
        "national_id",
        "passport",
        "mrn",
        "insurance_id",
        "dob",
        "date_of_birth",
        "face_image",
    }
)

ALL_DEPENDENCIES: tuple[str, ...] = tuple(sorted(DEPENDENCY_GRAPH))


# --------------------------------------------------------------------- types


@dataclasses.dataclass(frozen=True)
class RefreshPlan:
    """Deterministic refresh decision for one changed field (JSON-serializable).

    ``mode=PARTIAL`` carries the exact dependency partition:
    ``recompute_dependencies`` are rebuilt from source, everything else
    (``carried_over_dependencies``) is reused unchanged. ``mode=FULL``
    recomputes every dependency (``full_rebuild=True``). ``mode=FULL`` and
    ``mode=CLINICIAN_REVIEW`` never run an automatic partial refresh.
    """

    mode: str
    reason_code: str
    detail: str
    changed_field: str
    input_sha256: str
    recompute_dependencies: tuple[str, ...] = ()
    carried_over_dependencies: tuple[str, ...] = ()
    entangled: bool = False
    full_rebuild: bool = False
    version: str = SELECTIVE_REFRESH_VERSION

    def __post_init__(self) -> None:
        if self.mode not in REFRESH_MODES:
            raise ValueError(f"PLAN_BAD_MODE: {self.mode!r} not in {sorted(REFRESH_MODES)}")
        if not REASON_CODE_RE.match(self.reason_code):
            raise ValueError(f"PLAN_BAD_REASON_CODE: {self.reason_code!r}")
        if not isinstance(self.detail, str):
            raise ValueError("PLAN_BAD_DETAIL: detail must be a string")
        if not isinstance(self.changed_field, str):
            raise ValueError("PLAN_BAD_CHANGED_FIELD: changed_field must be a string")
        if not SHA256_RE.match(self.input_sha256):
            raise ValueError("PLAN_BAD_DIGEST: input_sha256 must be 64 lowercase hex chars")
        for name, value in (
            ("recompute_dependencies", self.recompute_dependencies),
            ("carried_over_dependencies", self.carried_over_dependencies),
        ):
            if not isinstance(value, tuple) or any(not isinstance(d, str) for d in value):
                raise ValueError(f"PLAN_BAD_DEPS: {name} must be a tuple of strings")
        if (
            isinstance(self.entangled, bool) is False
            or isinstance(self.full_rebuild, bool) is False
        ):
            raise ValueError("PLAN_BAD_FLAGS: entangled/full_rebuild must be booleans")
        if self.mode == MODE_FULL and not self.full_rebuild:
            raise ValueError("PLAN_BAD_FLAGS: FULL plans must set full_rebuild=True")
        if self.mode == MODE_PARTIAL and self.full_rebuild:
            raise ValueError("PLAN_BAD_FLAGS: PARTIAL plans must not set full_rebuild")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "changed_field": self.changed_field,
            "input_sha256": self.input_sha256,
            "recompute_dependencies": list(self.recompute_dependencies),
            "carried_over_dependencies": list(self.carried_over_dependencies),
            "entangled": self.entangled,
            "full_rebuild": self.full_rebuild,
            "version": self.version,
        }


# ------------------------------------------------------------- pure helpers


def _sha256_state(state: Any) -> str:
    """Canonical observability digest (sort_keys; never a clinical proof)."""
    payload = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_field(changed_field: Any) -> str | None:
    """Normalize a changed-field name; ``None`` when unknown/undeclared."""
    if not isinstance(changed_field, str):
        return None
    field = changed_field.strip().lower()
    field = _FIELD_SYNONYMS.get(field, field)
    known: set[str] = set().union(*DEPENDENCY_GRAPH.values()) | _PARTIAL_ELIGIBLE_FIELDS
    return field if field in known else None


def affected_dependencies(changed_field: Any) -> tuple[str, ...]:
    """Dependencies affected by ``changed_field`` (empty when unknown)."""
    field = _normalize_field(changed_field)
    if field is None:
        return ()
    return tuple(sorted(dep for dep, fields in DEPENDENCY_GRAPH.items() if field in fields))


def pair_entangled(field_a: Any, field_b: Any) -> bool:
    """General structural predicate: two distinct fields sharing a dependency.

    The concrete clinical instance is ``pair_entangled("medications",
    "allergies")`` (shared ``purpose_ddi_screen``).
    """
    fa = _normalize_field(field_a)
    fb = _normalize_field(field_b)
    if fa is None or fb is None or fa == fb:
        return False
    return any(fa in deps and fb in deps for deps in DEPENDENCY_GRAPH.values())


def is_entangled(state: Mapping[str, Any], changed_field: Any) -> bool:
    """Detect the clinically entangled medication/allergy pair for this state.

    True when ``changed_field`` is a medication/allergy field AND the
    counterpart clinical context is populated. If the counterpart section is
    absent or unreadable the entanglement cannot be ruled out, so the check
    fails closed to True (an unverifiable state must never produce a partial
    refresh). Unknown/non-clinical fields are never entangled; they are
    refused to FULL by the unknown-field rule instead.
    """
    field = _normalize_field(changed_field)
    if field is None or field not in ENTANGLED_FIELDS:
        return False
    other = "allergies" if field == "medications" else "medications"
    if other not in state:
        return True
    counterpart = state[other]
    if not isinstance(counterpart, list | tuple) or any(
        not isinstance(item, str) or not item for item in counterpart
    ):
        return True
    return bool(counterpart)


def _plan(
    mode: str,
    reason_code: str,
    detail: str,
    changed_field: str,
    digest: str,
    *,
    recompute: tuple[str, ...] = (),
    carried: tuple[str, ...] = (),
    entangled: bool = False,
) -> RefreshPlan:
    return RefreshPlan(
        mode=mode,
        reason_code=reason_code,
        detail=detail,
        changed_field=changed_field,
        input_sha256=digest,
        recompute_dependencies=recompute,
        carried_over_dependencies=carried,
        entangled=entangled,
        full_rebuild=mode == MODE_FULL,
    )


def _full_plan(reason_code: str, detail: str, changed_field: str, digest: str) -> RefreshPlan:
    return _plan(
        MODE_FULL,
        reason_code,
        detail,
        changed_field,
        digest,
        recompute=ALL_DEPENDENCIES,
    )


def _validate_state(state: Mapping[str, Any]) -> str | None:
    """Return a refusal detail string, or ``None`` when the state is sound."""
    phi_hits = sorted(set(state) & _PHI_LIKE_FIELDS)
    if phi_hits:
        return f"PHI-like field names refused: {','.join(phi_hits)}"
    missing = [field for field in _STATE_REQUIRED_FIELDS if field not in state]
    if missing:
        return f"missing required state sections: {','.join(missing)}"
    medications = state["medications"]
    if not isinstance(medications, list | tuple) or any(
        not isinstance(med, str) or not med for med in medications
    ):
        return "medications must be a list of non-empty strings"
    consent = state["consent"]
    if not isinstance(consent, Mapping):
        return "consent must be a mapping"
    if "granted_purposes" not in consent:
        return "missing required state sections: consent.granted_purposes"
    purposes = consent["granted_purposes"]
    if not isinstance(purposes, list | tuple) or any(
        not isinstance(p, str) or not p for p in purposes
    ):
        return "consent.granted_purposes must be a list of non-empty strings"
    if "allergies" in state:
        allergies = state["allergies"]
        if not isinstance(allergies, list | tuple) or any(
            not isinstance(a, str) or not a for a in allergies
        ):
            return "allergies must be a list of non-empty strings"
    return None


# -------------------------------------------------------------- entry points


def refresh(state: Mapping[str, Any], changed_field: Any) -> RefreshPlan:
    """Contract entry point: ``refresh(state, changed_field) -> RefreshPlan``.

    Decides the refresh mode for one changed field over one synthetic workflow
    state. Never raises for input contents: malformed, incomplete or
    out-of-scope inputs fail closed to ``FULL`` (or ``CLINICIAN_REVIEW`` when
    the medication/allergy pair is entangled or observations conflict) with a
    stable reason code. Deterministic: identical inputs yield identical plans.
    """
    digest = _sha256_state(state)
    if not isinstance(state, Mapping):
        return _full_plan(
            REASON_MALFORMED,
            f"state must be a mapping, got {type(state).__name__}",
            "",
            digest,
        )
    invalid = _validate_state(state)
    if invalid is not None:
        return _full_plan(
            REASON_PHI_FIELDS
            if invalid.startswith("PHI-like")
            else REASON_MALFORMED
            if "must be" in invalid or "mapping" in invalid
            else REASON_MISSING_FIELD,
            invalid,
            "",
            digest,
        )
    if state.get("conflicting_observations") is True:
        return _plan(
            MODE_CLINICIAN_REVIEW,
            REASON_CONFLICTING,
            "conflicting observations declared on the state; no automatic "
            "refresh may resolve source precedence — blinded clinician "
            "review required",
            "",
            digest,
        )
    field = _normalize_field(changed_field)
    if field is None:
        raw = changed_field if isinstance(changed_field, str) else type(changed_field).__name__
        return _full_plan(
            REASON_UNKNOWN_FIELD,
            f"changed_field {raw!r} is unknown/undeclared; scope of the change "
            "cannot be proven narrow, so the full context is re-derived",
            "",
            digest,
        )
    if is_entangled(state, field):
        return _plan(
            MODE_CLINICIAN_REVIEW,
            REASON_ENTANGLED,
            "medication and allergy contexts are clinically entangled (shared "
            "drug-allergy interaction screen): a change to one affects the "
            "interpretation of the other, so no automatic partial refresh may "
            "run — blinded clinician review required",
            field,
            digest,
            entangled=True,
        )
    if field in _CONSENT_FIELDS:
        return _full_plan(
            REASON_CONSENT_FULL,
            "consent/purpose change re-derives the authorization epoch that "
            "co-determines every dependency; full refresh forced",
            field,
            digest,
        )
    if field in _MEDICATION_FIELDS:
        return _full_plan(
            REASON_MEDICATION_FULL,
            "medication change re-derives the full clinical context "
            "(medication evidence feeds the interaction screen); full "
            "refresh forced",
            field,
            digest,
        )
    if field in _ALLERGY_FIELDS:
        return _full_plan(
            REASON_ALLERGY_FULL,
            "allergy change re-derives the full clinical context (allergy "
            "evidence feeds the interaction screen); full refresh forced",
            field,
            digest,
        )
    if field in _PARTIAL_ELIGIBLE_FIELDS:
        recompute = affected_dependencies(field)
        carried = tuple(sorted(set(ALL_DEPENDENCIES) - set(recompute)))
        return _plan(
            MODE_PARTIAL,
            REASON_PARTIAL_OK,
            "unrelated note change cannot touch medication, allergy or "
            "consent interpretation; only the affected dependencies are "
            "rebuilt",
            field,
            digest,
            recompute=recompute,
            carried=carried,
        )
    return _full_plan(
        REASON_UNKNOWN_FIELD,
        f"changed_field {field!r} has no proven-narrow dependency scope; full refresh forced",
        "",
        digest,
    )


def plan_transition(
    previous: Mapping[str, Any], current: Mapping[str, Any], hint: str
) -> RefreshPlan:
    """Scope a refresh using two complete, authenticated same-subject research snapshots.

    Review obligations at either endpoint survive other simultaneous edits.
    The caller is responsible for same-subject binding and snapshot integrity.
    """
    digest = _sha256_state([previous, current, hint])
    for state in (previous, current):
        if not isinstance(state, Mapping) or _validate_state(state) or "allergies" not in state:
            return _full_plan(
                REASON_MALFORMED, "Complete structured snapshots required.", "", digest
            )
    fields = sorted(
        k
        for k in previous.keys() | current.keys()
        if k not in previous or k not in current or previous[k] != current[k]
    )
    selected = refresh(current, hint)
    for field in dict.fromkeys([hint, *fields]):
        # Evaluate both ends: simultaneous removals can make the after-state
        # alone conceal an entangled dependency present before the edit.
        for state in (previous, current):
            plan = refresh(state, field)
            if plan.mode == MODE_CLINICIAN_REVIEW:
                return dataclasses.replace(plan, input_sha256=digest)
            if plan.mode == MODE_FULL:
                selected = plan
    return dataclasses.replace(selected, input_sha256=digest)


def update_context(current: Mapping[str, Any], dependencies: Any) -> RefreshPlan:
    """Task-spec contract: ``update_context(current, dependencies) -> RefreshPlan``.

    ``dependencies`` is a mapping with:
    - ``changed_field``: the section that changed (see :func:`refresh`);
    - ``previous_state``: optional complete prior snapshot for multi-section updates;
    - ``declared_dependencies``: the dependency names the caller currently
      holds (non-empty; unknown names fail closed to FULL).

    Soundness rule (never silently drop a missing dependency): a ``PARTIAL``
    plan is only returned when EVERY dependency the partial path would rebuild
    is actually held by the caller; otherwise the plan is escalated to FULL
    with ``REFRESH_MISSING_FIELD``. ``FULL``/``CLINICIAN_REVIEW`` plans pass
    through unchanged.
    """
    digest = _sha256_state(current)
    if not isinstance(current, Mapping):
        return _full_plan(
            REASON_MALFORMED,
            f"current must be a mapping, got {type(current).__name__}",
            "",
            digest,
        )
    if not isinstance(dependencies, Mapping):
        return _full_plan(
            REASON_MALFORMED,
            f"dependencies must be a mapping, got {type(dependencies).__name__}",
            "",
            digest,
        )
    declared_raw = dependencies.get("declared_dependencies")
    if (
        not isinstance(declared_raw, list | tuple)
        or not declared_raw
        or isinstance(declared_raw, str | bytes)
    ):
        return _full_plan(
            REASON_MISSING_DEPENDENCIES,
            "declared_dependencies must be a non-empty list of known dependency "
            "names; the caller's held context is unknown, so nothing may be "
            "silently carried over or dropped",
            "",
            digest,
        )
    declared: list[str] = []
    for dep in declared_raw:
        if not isinstance(dep, str) or dep not in DEPENDENCY_GRAPH:
            return _full_plan(
                REASON_UNKNOWN_DEPENDENCY,
                f"unknown declared dependency {dep!r}; cannot verify the held "
                "context, full refresh forced",
                "",
                digest,
            )
        if dep not in declared:
            declared.append(dep)
    if "previous_state" in dependencies:
        plan = plan_transition(
            dependencies["previous_state"], current, dependencies.get("changed_field")
        )
    else:
        plan = refresh(current, dependencies.get("changed_field"))
    if plan.mode != MODE_PARTIAL:
        return plan
    missing = sorted(set(plan.recompute_dependencies) - set(declared))
    if missing:
        return _full_plan(
            REASON_MISSING_FIELD,
            f"partial refresh refused: affected dependencies not held by the "
            f"caller: {','.join(missing)}",
            plan.changed_field,
            digest,
        )
    carried = tuple(sorted(set(declared) - set(plan.recompute_dependencies)))
    return dataclasses.replace(plan, carried_over_dependencies=carried)


__all__ = [
    "ALL_DEPENDENCIES",
    "DEPENDENCY_GRAPH",
    "ENTANGLED_FIELDS",
    "MODE_CLINICIAN_REVIEW",
    "MODE_FULL",
    "MODE_PARTIAL",
    "REFRESH_MODES",
    "REASON_CODE_RE",
    "REASON_PARTIAL_OK",
    "SELECTIVE_REFRESH_VERSION",
    "RefreshPlan",
    "affected_dependencies",
    "is_entangled",
    "pair_entangled",
    "plan_transition",
    "refresh",
    "update_context",
]
