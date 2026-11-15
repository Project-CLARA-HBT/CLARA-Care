"""AIME-candidate (Phase P04, venue ``aime``) — isolated candidate algorithm.

Purpose
-------
The B4 candidate arm of the AIME 2027 study "Counterfactual Clinical Workflow
Safety under Changing Consent and Medication Histories"
(``research/venue2027/VENUES/aime/RESEARCH_BLUEPRINT.md``; scenario matrix
``research/venue2027/VENUES/aime/CASE_MATRIX.md``; task contract
``research/venue2027/VENUES/aime/TASKS/AIME-candidate.md``): a
*counterfactual-history-aware* safety check that contrasts the task-start
snapshot against the current record and the event timeline, detects changed
consent / medication / allergy history, and blocks a hazardous recommendation
before any completion is counted.

Isolation contract
------------------
- This module imports **neither** the independent oracle
  (``independent_oracle.py`` / ``oracle_kernel``) nor any label/truth file;
  truth comparison happens only in the study runner. It also imports no
  candidate sibling (``baselines.py``, ``generate_dataset.py``,
  ``vignette_generator.py``).
- **No LLM/model call of any kind**: pure, deterministic, offline function.
  No clock, no randomness, no network, no database, no environment I/O.
- Synthetic vignettes only (``clara.venue2027.scenario.v1``-shaped records
  with structured medications / consent / timeline). PHI-like input fields
  are refused fail-closed (``research/venue2027/_shared/data_ethics_and_irb.md``
  items 1–4); synthetic action labels are systems/engineering outcomes, never
  clinical-efficacy evidence.

Allowed input
-------------
``run_candidate(case, ctx) -> Outcome`` over a JSON-serializable ``case``
mapping with ``case_id``, ``purpose``, ``snapshot`` (``medications`` list +
``consent`` mapping with ``granted_purposes`` and optional ``allergies``),
``current`` (same shape), ``timeline`` (ordered events with ``event_kind`` in
:data:`TIMELINE_EVENT_KINDS`), and ``task`` (``drug`` under discussion). The
injected :class:`CandidateContext` carries arm id, source SHA and step time;
nothing else is read.

Failure semantics
-----------------
Fail closed on unknown/ambiguous state -> ``INDETERMINATE`` with a stable
uppercase reason code (never an unhandled exception, never a silent safe
rejection): malformed input, PHI-like fields, missing fields, non-monotone
or unknown timeline events, snapshot/current inconsistency, unknown purposes
or unresolved evidence digests. Detected hazards (consent withdrawal, drug
interacting with a newly added medication, allergen now present, withdrawn
medication still anchoring the task) return ``UNSAFE`` (forbidden evidence in
play) or ``INDETERMINATE`` (review required) — never ``SAFE``. A stable
history with unchanged consent is admitted ``SAFE``.

Algorithm (pseudocode mapping to the blueprint)
-----------------------------------------------
::

    run_candidate(case, ctx):                         # B4 selective-consent-aware
      require CandidateContext(case) else INDETERMINATE(CONTEXT_MALFORMED)
      validate case shape else INDETERMINATE(VIGNETTE_*)   # fail-closed boundary
      if snapshot != project(current baseline)  # structural ambiguity
           -> INDETERMINATE(SNAPSHOT_CURRENT_INCONSISTENT)
      delta_consent := set(consent(snapshot)) - set(consent(current))   # axis A
      if purpose not in consent(current)
           -> UNSAFE(CONSENT_REVOKED_MID_TASK)                   # CASE-03
      delta_allergy := set(allergies(current)) - set(allergies(snapshot))
      if task.drug in delta_allergy or task.drug in allergies(current)
           -> UNSAFE(ALLERGEN_PRESENT_IN_TASK)                   # CASE-02 shape
      delta_withdrawn := set(meds(snapshot)) - set(meds(current))
      if task.drug in delta_withdrawn
           -> UNSAFE(WITHDRAWN_MEDICATION_IN_OUTPUT)             # CASE-02
      delta_added := set(meds(current)) - set(meds(snapshot))              # CASE-02 second med
      if delta_added interacts with task.drug per INJECTION_INTERACTION_TABLE
           -> INDETERMINATE(ADDITIONAL_MEDICATION_INTERACTION_HAZARD)  # review
      if delta_withdrawn or delta_added or delta_allergy (unrelated to task)
           -> INDETERMINATE(HISTORY_CHANGED_REVIEW_REQUIRED)     # conservative
      else -> SAFE(NO_DETECTED_HAZARD)                           # CASE-01/06

Version
-------
``CANDIDATE_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Any, Final

CANDIDATE_VERSION: Final[str] = "1.0.0"

#: Candidate arm id (blueprint §Strong baselines row B4).
CANDIDATE_ARM_ID: Final[str] = "C0-selective-consent-aware-context-regeneration"

#: Decisions (``INDETERMINATE`` first-class; never coerced to safe/unsafe).
DECISION_UNSAFE: Final[str] = "UNSAFE"
DECISION_SAFE: Final[str] = "SAFE"
DECISION_INDETERMINATE: Final[str] = "INDETERMINATE"
DECISIONS: Final[frozenset[str]] = frozenset(
    {DECISION_UNSAFE, DECISION_SAFE, DECISION_INDETERMINATE}
)


class Decision:
    """Typed namespace over the allowed decision values (contract alias)."""

    SAFE = DECISION_SAFE
    UNSAFE = DECISION_UNSAFE
    INDETERMINATE = DECISION_INDETERMINATE


#: Stable reason codes (all match :data:`REASON_CODE_RE`).
REASON_OK: Final[str] = "OK"
REASON_NO_HAZARD: Final[str] = "NO_DETECTED_HAZARD"
REASON_CONSENT_REVOKED: Final[str] = "CONSENT_REVOKED_MID_TASK"
REASON_WITHDRAWN_MEDICATION: Final[str] = "WITHDRAWN_MEDICATION_IN_OUTPUT"
REASON_ADDED_MEDICATION_INTERACTION: Final[str] = "ADDITIONAL_MEDICATION_INTERACTION_HAZARD"
REASON_ALLERGEN_PRESENT: Final[str] = "ALLERGEN_PRESENT_IN_TASK"
REASON_HISTORY_CHANGED_REVIEW: Final[str] = "HISTORY_CHANGED_REVIEW_REQUIRED"
REASON_MALFORMED: Final[str] = "VIGNETTE_MALFORMED"
REASON_MISSING_FIELD: Final[str] = "VIGNETTE_MISSING_FIELD"
REASON_BAD_TIMELINE: Final[str] = "VIGNETTE_BAD_TIMELINE"
REASON_BAD_CTX: Final[str] = "CONTEXT_MALFORMED"
REASON_SNAPSHOT_INCONSISTENT: Final[str] = "SNAPSHOT_CURRENT_INCONSISTENT"
REASON_EVIDENCE_UNRESOLVED: Final[str] = "EVIDENCE_DIGEST_UNRESOLVED"

REASON_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
SOURCE_SHA_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")
EVIDENCE_REF_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Timeline event kinds accepted by this candidate (unknown kinds fail closed).
TIMELINE_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "INITIAL_STATE",
        "MEDICATION_ADDED",
        "MEDICATION_WITHDRAWN",
        "CONSENT_GRANTED",
        "CONSENT_REVOKED",
        "UNRELATED_NOTE_EDIT",
        "ALLERGY_REPORTED",
    }
)

#: Deterministic pairwise interaction flags over synthetic drug names. This is
#: a frozen engineering lookup used ONLY to route added-medication cases to
#: review; it is not clinical knowledge and makes no clinical claim.
INJECTION_INTERACTION_TABLE: Final[frozenset[frozenset[str]]] = frozenset(
    {frozenset({"warfarin", "metformin"}), frozenset({"warfarin", "aspirin"})}
)

#: Allergy list key accepted inside ``snapshot/current`` consent/state records.
ALLERGY_KEY: Final[str] = "allergies"

_VIGNETTE_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "case_id",
    "purpose",
    "snapshot",
    "current",
    "timeline",
    "task",
)
_STATE_REQUIRED_FIELDS: Final[tuple[str, ...]] = ("medications", "consent")

#: PHI-like field names refused at the input boundary (data ethics item 3).
PHI_LIKE_FIELDS: Final[frozenset[str]] = frozenset(
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


# --------------------------------------------------------------------- types


@dataclasses.dataclass(frozen=True)
class CandidateContext:
    """Injected per-run context (no clock, no randomness, no environment I/O)."""

    arm_id: str
    source_sha: str
    step_logical_time: int
    purpose: str = "self_care"

    def __post_init__(self) -> None:
        if not isinstance(self.arm_id, str) or not self.arm_id:
            raise ValueError(f"{REASON_BAD_CTX}: arm_id must be a non-empty string")
        if not SOURCE_SHA_RE.match(self.source_sha):
            raise ValueError(f"{REASON_BAD_CTX}: source_sha must be 40 lowercase hex chars")
        if isinstance(self.step_logical_time, bool) or not isinstance(self.step_logical_time, int):
            raise ValueError(f"{REASON_BAD_CTX}: step_logical_time must be an integer")
        if self.step_logical_time < 0:
            raise ValueError(f"{REASON_BAD_CTX}: step_logical_time must be >= 0")
        if not isinstance(self.purpose, str) or not self.purpose:
            raise ValueError(f"{REASON_BAD_CTX}: purpose must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "source_sha": self.source_sha,
            "step_logical_time": self.step_logical_time,
            "purpose": self.purpose,
        }


@dataclasses.dataclass(frozen=True)
class Outcome:
    """One candidate decision on one synthetic vignette (JSON-serializable).

    ``decision=INDETERMINATE`` is first-class: it is never coerced into a safe
    rejection or a completion (blueprint falsification rule; CASE_MATRIX rule
    on ``MEASURE``/``INDETERMINATE``).
    """

    candidate_id: str
    decision: str
    reason_code: str
    detail: str
    input_sha256: str
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"OUTCOME_BAD_DECISION: {self.decision!r} not in {sorted(DECISIONS)}")
        if not REASON_CODE_RE.match(self.reason_code):
            raise ValueError(f"OUTCOME_BAD_REASON_CODE: {self.reason_code!r}")
        if not isinstance(self.detail, str):
            raise ValueError("OUTCOME_BAD_DETAIL: detail must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "input_sha256": self.input_sha256,
            "evidence": list(self.evidence),
            "version": CANDIDATE_VERSION,
        }


# ------------------------------------------------------------ input parsing


def digest_case(case: Any) -> str:
    """Stable SHA256 over the JSON-normalized case (observability only)."""

    payload = json.dumps(case, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_consent(consent: Any, where: str) -> str | None:
    if not isinstance(consent, dict):
        return f"{where}.consent"
    granted = consent.get("granted_purposes")
    if granted is None:
        return f"{where}.consent.granted_purposes"
    if isinstance(granted, str):
        return None
    if not isinstance(granted, list | tuple) or not all(isinstance(p, str) for p in granted):
        return f"{where}.consent.granted_purposes"
    return None


def parse_case(case: Any) -> tuple[dict[str, Any] | None, str, str]:
    """Validate the synthetic vignette; returns (normalized, reason_code, digest).

    Normalized ``None`` means fail closed with the returned reason code. The
    digest is always computed so observability keeps the input hash of refused
    inputs too.
    """
    digest = digest_case(case)
    if not isinstance(case, dict):
        return None, REASON_MALFORMED, digest
    phi_hits = sorted(set(case) & PHI_LIKE_FIELDS)
    if phi_hits:
        return None, f"{REASON_MALFORMED}:PHI_FIELDS:{','.join(phi_hits)}", digest
    missing = [field for field in _VIGNETTE_REQUIRED_FIELDS if field not in case]
    if missing:
        return None, f"{REASON_MISSING_FIELD}:{','.join(missing)}", digest
    if not isinstance(case["case_id"], str) or not case["case_id"]:
        return None, REASON_MALFORMED, digest
    if not isinstance(case["purpose"], str) or not case["purpose"]:
        return None, REASON_MALFORMED, digest
    task = case["task"]
    if not isinstance(task, dict):
        return None, REASON_MALFORMED, digest
    if not isinstance(task.get("drug"), str) or not task["drug"]:
        return None, REASON_MALFORMED, digest
    for label in ("snapshot", "current"):
        state = case[label]
        if not isinstance(state, dict):
            return None, REASON_MALFORMED, digest
        for field in _STATE_REQUIRED_FIELDS:
            if field not in state:
                return None, f"{REASON_MISSING_FIELD}:{label}.{field}", digest
        if not isinstance(state["medications"], list | tuple) or not all(
            isinstance(med, str) and med for med in state["medications"]
        ):
            return None, REASON_MALFORMED, digest
        bad_consent = _validate_consent(state["consent"], label)
        if bad_consent is not None:
            return None, REASON_MALFORMED, digest
        allergies = state.get(ALLERGY_KEY, [])
        if not isinstance(allergies, list | tuple) or not all(
            isinstance(a, str) and a for a in allergies
        ):
            return None, REASON_MALFORMED, digest
        for _key, value in state.items():
            if isinstance(value, str) and EVIDENCE_REF_RE.match(value) is None:
                return None, REASON_EVIDENCE_UNRESOLVED, digest
    timeline = case["timeline"]
    if not isinstance(timeline, list | tuple) or not timeline:
        return None, REASON_BAD_TIMELINE, digest
    last_order = -1
    last_time = -1
    for event in timeline:
        if not isinstance(event, dict):
            return None, REASON_BAD_TIMELINE, digest
        for field in ("order", "event_kind", "logical_time"):
            if field not in event:
                return None, f"{REASON_MISSING_FIELD}:timeline.{field}", digest
        if event["event_kind"] not in TIMELINE_EVENT_KINDS:
            return None, f"{REASON_BAD_TIMELINE}:{event['event_kind']!r}", digest
        if isinstance(event["order"], bool) or not isinstance(event["order"], int):
            return None, REASON_BAD_TIMELINE, digest
        if isinstance(event["logical_time"], bool) or not isinstance(event["logical_time"], int):
            return None, REASON_BAD_TIMELINE, digest
        if event["order"] <= last_order or event["logical_time"] < last_time:
            return None, REASON_BAD_TIMELINE, digest
        last_order = event["order"]
        last_time = event["logical_time"]
        payload = event.get("payload")
        if payload is not None and not isinstance(payload, dict):
            return None, REASON_BAD_TIMELINE, digest
    return dict(case), REASON_OK, digest


# ------------------------------------------------------------- state helpers


def _granted_purposes(state: dict[str, Any]) -> tuple[str, ...]:
    granted = state["consent"].get("granted_purposes", ())
    if isinstance(granted, str):
        return (granted,)
    return tuple(granted)


def _allergies(state: dict[str, Any]) -> tuple[str, ...]:
    return tuple(state.get(ALLERGY_KEY, ()) or ())


def _timeline_history(case: dict[str, Any]) -> dict[str, tuple[tuple[str, ...], ...]]:
    """Project timeline events into (added, withdrawn, allergies, revoked) tuples."""

    added: list[str] = []
    withdrawn: list[str] = []
    allergies: list[str] = []
    revoked: list[str] = []
    for event in case["timeline"]:
        kind = event["event_kind"]
        payload = event.get("payload") or {}
        name = payload.get("medication") if isinstance(payload, dict) else None
        purpose = payload.get("purpose") if isinstance(payload, dict) else None
        if kind == "MEDICATION_ADDED" and isinstance(name, str) and name:
            added.append(name)
        elif kind == "MEDICATION_WITHDRAWN" and isinstance(name, str) and name:
            withdrawn.append(name)
        elif kind == "ALLERGY_REPORTED" and isinstance(name, str) and name:
            allergies.append(name)
        elif kind == "CONSENT_REVOKED" and isinstance(purpose, str) and purpose:
            revoked.append(purpose)
    return {
        "added": tuple(added),
        "withdrawn": tuple(withdrawn),
        "allergies": tuple(allergies),
        "revoked": tuple(revoked),
    }


def _interacts_with(a: str, b: str) -> bool:
    return frozenset({a, b}) in INJECTION_INTERACTION_TABLE


# ------------------------------------------------------------------ candidate


def _outcome(
    decision: str, reason_code: str, detail: str, digest: str, evidence: tuple[str, ...] = ()
) -> Outcome:
    return Outcome(
        candidate_id=CANDIDATE_ARM_ID,
        decision=decision,
        reason_code=reason_code,
        detail=detail,
        input_sha256=digest,
        evidence=evidence,
    )


def decide(case: dict[str, Any], ctx: CandidateContext, digest: str) -> Outcome:
    """Core pure decision function over an already-validated synthetic vignette.

    Counterfactual contrast: snapshot (task start) vs current (step state) vs
    timeline events. See the module docstring pseudocode for the blueprint
    mapping (B4 selective consent-aware regeneration; RQ1 axis A/B).
    """
    snapshot = case["snapshot"]
    current = case["current"]
    task_drug = case["task"]["drug"]
    purpose = ctx.purpose or case["purpose"]

    # Structural ambiguity guard: the current state must be reachable from the
    # snapshot by the recorded timeline events, else the history is ambiguous
    # and the candidate fails closed to INDETERMINATE (never guesses).
    events = _timeline_history(case)
    snapshot_meds = set(snapshot["medications"])
    current_meds = set(current["medications"])
    replayed = (snapshot_meds - set(events["withdrawn"])) | set(events["added"])
    if replayed != current_meds:
        return _outcome(
            DECISION_INDETERMINATE,
            REASON_SNAPSHOT_INCONSISTENT,
            "current medication set is not reachable from the snapshot by the recorded "
            "timeline events; history is ambiguous and is never guessed",
            digest,
            evidence=("snapshot.medications", "current.medications", "timeline"),
        )

    # Axis A — consent epoch: any revocation of the requested purpose is an
    # unauthorized-data-use hazard (AIME-CASE-03) and blocks disclosure.
    if purpose not in _granted_purposes(current) or purpose in events["revoked"]:
        return _outcome(
            DECISION_UNSAFE,
            REASON_CONSENT_REVOKED,
            "consent for the requested purpose was withdrawn or is absent at the step's "
            "logical time; no further disclosure is authorized",
            digest,
            evidence=("current.consent", "timeline"),
        )

    # Axis B — allergy history: a newly reported (or pre-existing) allergen
    # equal to the task drug forbids continuing the recommendation
    # (AIME-CASE-02 allergy shape).
    new_allergies = tuple(sorted(set(_allergies(current)) - set(_allergies(snapshot))))
    allergen_hits = tuple(
        sorted(
            {
                a
                for a in set(new_allergies) | set(events["allergies"]) | set(_allergies(current))
                if a == task_drug
            }
        )
    )
    if allergen_hits:
        return _outcome(
            DECISION_UNSAFE,
            REASON_ALLERGEN_PRESENT,
            f"task drug {task_drug!r} is recorded as an allergen in the current history; "
            "continuing the recommendation would be a clinical-fact hazard",
            digest,
            evidence=("current.allergies", "timeline"),
        )

    # Axis B — withdrawn medication anchoring the task: the stale single-
    # snapshot recommendation is an action-eligibility hazard (AIME-CASE-02).
    withdrawn_meds = tuple(
        sorted((snapshot_meds - current_meds) | (set(events["withdrawn"]) & snapshot_meds))
    )
    if task_drug in withdrawn_meds:
        return _outcome(
            DECISION_UNSAFE,
            REASON_WITHDRAWN_MEDICATION,
            f"task drug {task_drug!r} was withdrawn after the task-start snapshot; a "
            "stale single-history recommendation is an action-eligibility hazard",
            digest,
            evidence=("current.medications", "timeline"),
        )

    # Axis B — added medication: interaction re-review required before any
    # completion is countable (AIME-CASE-02 second-medication shape).
    added_meds = tuple(
        sorted((current_meds - snapshot_meds) | (set(events["added"]) - snapshot_meds))
    )
    interacting = tuple(sorted({m for m in added_meds if _interacts_with(m, task_drug)}))
    if interacting:
        return _outcome(
            DECISION_INDETERMINATE,
            REASON_ADDED_MEDICATION_INTERACTION,
            f"medication(s) {interacting} added after the task-start snapshot interact "
            f"with the task drug {task_drug!r} per the frozen routing table; interaction "
            "re-review required before completion",
            digest,
            evidence=("current.medications", "timeline"),
        )

    # Conservative fallback: any other history change (non-interacting
    # addition, unrelated-to-task withdrawal, allergy unrelated to the task
    # drug) still requires review; only a fully stable history is admitted.
    if added_meds or withdrawn_meds or new_allergies or events["revoked"]:
        return _outcome(
            DECISION_INDETERMINATE,
            REASON_HISTORY_CHANGED_REVIEW,
            "history changed after the task-start snapshot without a classified hazard; "
            "conservative fallback routes the step to review rather than admitting",
            digest,
            evidence=("snapshot", "current", "timeline"),
        )

    return _outcome(
        DECISION_SAFE,
        REASON_NO_HAZARD,
        "counterfactual history check found no consent, medication or allergy delta; "
        "task-start snapshot is still current (AIME-CASE-01/06 shape)",
        digest,
        evidence=("snapshot", "current", "timeline"),
    )


# -------------------------------------------------------------- entry point


def run_candidate(case: Any, ctx: Any) -> Outcome:
    """Contract entry point: ``run_candidate(case, ctx) -> Outcome``.

    Runs the counterfactual-history-aware candidate over one **synthetic**
    clinical vignette. Never raises for input contents: malformed vignettes
    and malformed contexts fail closed to ``INDETERMINATE`` with a stable
    reason code and are never counted as safe rejections or completions.
    """
    digest = digest_case(case)
    if not isinstance(ctx, CandidateContext):
        return _outcome(
            DECISION_INDETERMINATE,
            REASON_BAD_CTX,
            f"ctx must be a CandidateContext, got {type(ctx).__name__}",
            digest,
        )
    normalized, reason, digest = parse_case(case)
    if normalized is None:
        code, _, extra = reason.partition(":")
        return _outcome(DECISION_INDETERMINATE, code, f"vignette refused: {extra or code}", digest)
    return decide(normalized, ctx, digest)


# ------------------------------------------------------- adversarial self-test


def refuse_constant_safe_stub(
    adapter: Any,
    *,
    source_sha: str,
) -> tuple[bool, str]:
    """Behaviour gate: refuse a constant-safe stub wearing the candidate name.

    Replays a hazard-free probe and a hazard-bearing probe (consent revoked
    mid-task) through ``adapter``. A genuine counterfactual-history-aware
    candidate must separate them; an adapter returning ``SAFE`` /
    ``NO_DETECTED_HAZARD`` for both is a toy and is refused with
    ``CONSTANT_SAFE_STUB_REFUSED`` (EXECUTION_CONTRACT rule 8). Returns
    ``(ok, reason_code)``.
    """

    def _probe_stable() -> dict[str, Any]:
        return {
            "case_id": "PROBE-STABLE",
            "purpose": "self_care",
            "snapshot": {
                "medications": ["metformin"],
                "consent": {"granted_purposes": ["self_care"]},
            },
            "current": {
                "medications": ["metformin"],
                "consent": {"granted_purposes": ["self_care"]},
            },
            "timeline": [
                {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            ],
            "task": {"drug": "metformin", "kind": "recommendation"},
        }

    def _probe_revoked() -> dict[str, Any]:
        case = _probe_stable()
        case["case_id"] = "PROBE-REVOKED"
        case["current"] = {
            "medications": ["metformin"],
            "consent": {"granted_purposes": []},
        }
        case["timeline"] = [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 3,
                "payload": {"purpose": "self_care"},
            },
        ]
        return case

    outcomes: list[Outcome] = []
    for probe in (_probe_stable(), _probe_revoked()):
        try:
            outcomes.append(
                adapter(
                    probe,
                    CandidateContext(
                        arm_id=CANDIDATE_ARM_ID, source_sha=source_sha, step_logical_time=1
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - any crash means the adapter is not the candidate
            return False, f"CONSTANT_SAFE_STUB_REFUSED:{type(exc).__name__}"
    stable, revoked = outcomes
    if (
        stable.decision == DECISION_SAFE
        and revoked.decision == DECISION_SAFE
        and stable.reason_code == REASON_NO_HAZARD
        and revoked.reason_code == REASON_NO_HAZARD
    ):
        return False, "CONSTANT_SAFE_STUB_REFUSED"
    return True, REASON_OK
