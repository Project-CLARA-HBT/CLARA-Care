"""AIME-baselines (Phase P03, venue ``aime``) — baseline fidelity adapters.

Purpose
-------
Pure-function reference adapters for the five AIME strong-baseline arms
(`research/venue2027/VENUES/aime/RESEARCH_BLUEPRINT.md` §Strong baselines,
``novelty_contract.md`` §6, ``literature_matrix.csv`` rows B0–B5). Each arm
implements its declared semantics over **structured synthetic vignettes only**
(medications, consent grants/revocations, history revisions, timeline events):
no real PHI, no live provider, no LLM call, no clock, no randomness.

Arms and declared semantics
---------------------------
- **B0** ``full-authorized-history-single-snapshot``: decides from the INITIAL
  snapshot only; ignores every mid-task history change (stale-context foil).
- **B1** ``full-per-step-refresh-current-policy-filter``: re-reads the record
  at the step's current logical time and applies the current policy/consent
  epoch filter before deciding (strongest correctness/privacy control).
- **B2** ``healthbench-medhelm-rubric``: benchmark-rubric scoring arm; it is
  NOT a decision algorithm (blueprint: "benchmark rubric, not a decision
  algorithm"), so it returns ``NOT_RUN_EXTERNAL`` for decision requests.
- **B3** ``static-model-output-post-filter``: static context + deterministic
  output post-filter that redacts/blocks content naming a withdrawn
  medication; cannot repair staleness, only refuse.
- **B4** candidate ``selective-consent-aware-context-regeneration``:
  counterfactual-history-aware safety check — compares the snapshot against
  the current state, detects consent revocations and medication
  changes/additions/withdrawals, and surfaces hazards for review.
- **B5** ``consent-agnostic-retrieval``: the unsafe foil named in the research
  gap; retrieves without any consent filtering (axis-A base-rate surface).

Provider-dependent LLM execution (B0/B1/B3 full arms, B2 rubric scoring) is
NOT implemented in-process: those arms return ``NOT_RUN_EXTERNAL`` with the
stable reason code ``PROVIDER_DEPENDENT_NOT_RUN`` whenever a run requests a
live-model decision. No clinical efficacy claim is made or implied anywhere;
synthetic action labels are systems-level engineering outcomes only.

Allowed input
-------------
A ``Vignette`` mapping (typed :class:`Vignette`) — schema
``clara.venue2027.scenario.v1``-shaped: ``case_id``, ``purpose``,
``snapshot`` (initial medications + consent), ``current`` (post-change
medications + consent), ``timeline`` (ordered events with ``logical_time``),
``task`` (drug under discussion), ``output`` (optional proposed model output
for post-filtering). All identities/timestamps must be synthetic. The
injected :class:`BaselineContext` carries arm id, source SHA and step time;
no environment or network is read.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. Every arm returns an
:class:`Outcome` whose ``decision`` is one of ``UNSAFE`` / ``SAFE`` /
``INDETERMINATE`` / ``NOT_RUN_EXTERNAL``. Malformed vignettes yield
``INDETERMINATE`` with a structural reason code (``VIGNETTE_MALFORMED``,
``VIGNETTE_MISSING_FIELD``, ``VIGNETTE_BAD_TIMELINE``, ``UNKNOWN_BASELINE_ID``
...); a malformed input is never silently counted as a safe rejection and a
``NOT_RUN_EXTERNAL`` arm is never counted as a completion or a refusal.

Parity / honesty contract
-------------------------
- ``BASELINE_REGISTRY`` maps every arm id to its pinned provenance entry
  (upstream reference = this study's blueprint arm row in
  ``literature_matrix.csv``; fidelity ``UNAVAILABLE_NOT_RUN`` for all
  provider-dependent arms exactly as recorded in the prior-art ledger).
- A constant-safe stub (an adapter that returns ``SAFE`` regardless of
  input) is **refused**: :func:`refuse_constant_safe_stub` replays
  hazard-free and hazard-bearing probes through any candidate adapter and
  fails with ``CONSTANT_SAFE_STUB_REFUSED`` when the adapter cannot separate
  them (EXECUTION_CONTRACT rule 8: never replace an unavailable baseline with
  a toy that keeps the same name).

Version
-------
``BASELINES_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from typing import Any

BASELINES_VERSION = "1.0.0"

#: Decisions (``INDETERMINATE`` first-class; never coerced to safe/unsafe).
DECISION_UNSAFE = "UNSAFE"
DECISION_SAFE = "SAFE"
DECISION_INDETERMINATE = "INDETERMINATE"
DECISION_NOT_RUN_EXTERNAL = "NOT_RUN_EXTERNAL"
DECISIONS: frozenset[str] = frozenset(
    {DECISION_UNSAFE, DECISION_SAFE, DECISION_INDETERMINATE, DECISION_NOT_RUN_EXTERNAL}
)


class Decision:
    """Typed namespace over the allowed decision values (contract alias)."""

    SAFE = DECISION_SAFE
    UNSAFE = DECISION_UNSAFE
    INDETERMINATE = DECISION_INDETERMINATE
    NOT_RUN_EXTERNAL = DECISION_NOT_RUN_EXTERNAL


#: Stable reason codes (subset asserted by tests; all codes match ^[A-Z][A-Z0-9_]{2,63}$).
REASON_OK = "OK"
REASON_PROVIDER_DEPENDENT = "PROVIDER_DEPENDENT_NOT_RUN"
REASON_CONSENT_REVOKED = "CONSENT_REVOKED_MID_TASK"
REASON_WITHDRAWN_MEDICATION = "WITHDRAWN_MEDICATION_IN_OUTPUT"
REASON_STALE_SNAPSHOT_MEDICATION_CHANGE = "STALE_SNAPSHOT_MEDICATION_CHANGE"
REASON_STALE_SNAPSHOT_CONSENT_CHANGE = "STALE_SNAPSHOT_CONSENT_CHANGE"
REASON_ADITIONAL_MEDICATION_HAZARD = "ADDITIONAL_MEDICATION_INTERACTION_HAZARD"
REASON_MALFORMED = "VIGNETTE_MALFORMED"
REASON_MISSING_FIELD = "VIGNETTE_MISSING_FIELD"
REASON_BAD_TIMELINE = "VIGNETTE_BAD_TIMELINE"
REASON_UNKNOWN_ARM = "UNKNOWN_BASELINE_ID"
REASON_BAD_CTX = "CONTEXT_MALFORMED"
REASON_NO_HAZARD = "NO_DETECTED_HAZARD"
REASON_CONSENT_AGNOSTIC_RETRIEVAL = "CONSENT_AGNOSTIC_RETRIEVAL_UNFILTERED"
REASON_CONSTANT_SAFE_STUB = "CONSTANT_SAFE_STUB_REFUSED"

REASON_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

#: Known baseline arm ids (registry keys below).
BASELINE_B0 = "B0-full-authorized-history-single-snapshot"
BASELINE_B1 = "B1-full-per-step-refresh-current-policy-filter"
BASELINE_B2 = "B2-healthbench-medhelm-rubric"
BASELINE_B3 = "B3-static-model-output-post-filter"
BASELINE_B4 = "B4-selective-consent-aware-context-regeneration"
BASELINE_B5 = "B5-consent-agnostic-retrieval"

#: Registry provenance entries mirroring ``research/venue2027/aime/literature_matrix.csv``.
#: All in-process arms here are structural adapters over synthetic vignettes; the
#: provider-dependent execution of B0/B1/B2/B3 remains UNAVAILABLE_NOT_RUN (no live
#: model call is performed by this module), so their fidelity status stays honest.
BASELINE_REGISTRY: dict[str, dict[str, str]] = {
    BASELINE_B0: {
        "comparator_id": "B0-full-authorized-history-single-snapshot",
        "algorithm_class": "static full-context single snapshot + one-shot decision",
        "fidelity_status": "UNAVAILABLE_NOT_RUN",
        "upstream": "research/venue2027/aime/literature_matrix.csv#B0",
        "provider_dependent": "true",
    },
    BASELINE_B1: {
        "comparator_id": "B1-full-per-step-refresh-current-policy-filter",
        "algorithm_class": "full per-step context refresh + current policy epoch filter",
        "fidelity_status": "UNAVAILABLE_NOT_RUN",
        "upstream": "research/venue2027/aime/literature_matrix.csv#B1",
        "provider_dependent": "true",
    },
    BASELINE_B2: {
        "comparator_id": "B2-healthbench-medhelm-rubric",
        "algorithm_class": "physician-authored rubric scorer (openai/simple-evals pin "
        "652c89d0ca9df547706735883097e9537d40dc47, MIT)",
        "fidelity_status": "UNAVAILABLE_NOT_RUN",
        "upstream": "research/venue2027/aime/literature_matrix.csv#B2",
        "provider_dependent": "true",
    },
    BASELINE_B3: {
        "comparator_id": "B3-static-model-output-post-filter",
        "algorithm_class": "static context + deterministic output post-filter",
        "fidelity_status": "UNAVAILABLE_NOT_RUN",
        "upstream": "research/venue2027/aime/literature_matrix.csv#B3",
        "provider_dependent": "true",
    },
    BASELINE_B4: {
        "comparator_id": "B4-selective-consent-aware-context-regeneration",
        "algorithm_class": "purpose-aware selective consent-aware context regeneration "
        "(counterfactual-history-aware safety check)",
        "fidelity_status": "UNAVAILABLE_NOT_RUN",
        "upstream": "research/venue2027/aime/literature_matrix.csv#B4",
        "provider_dependent": "false",
    },
    BASELINE_B5: {
        "comparator_id": "B5-consent-agnostic-retrieval",
        "algorithm_class": "retrieval over the full longitudinal record, no consent filter",
        "fidelity_status": "UNAVAILABLE_NOT_RUN",
        "upstream": "research/venue2027/aime/literature_matrix.csv#B5",
        "provider_dependent": "false",
    },
}

RETRIEVAL_UNSAFE_REASON = "RETRIEVED_REVOKED_CONSENT_EVIDENCE"
RETRIEVAL_MEDICATION_REASON = "RETRIEVED_STALE_MEDICATION_STATE"

_VIGNETTE_REQUIRED_FIELDS: tuple[str, ...] = (
    "case_id",
    "purpose",
    "snapshot",
    "current",
    "timeline",
    "task",
)
_SNAPSHOT_REQUIRED_FIELDS: tuple[str, ...] = ("medications", "consent")
_TIMELINE_EVENT_KINDS: frozenset[str] = frozenset(
    {
        "INITIAL_STATE",
        "MEDICATION_ADDED",
        "MEDICATION_WITHDRAWN",
        "CONSENT_GRANTED",
        "CONSENT_REVOKED",
        "UNRELATED_NOTE_EDIT",
    }
)
_REDACTED_MEDICATION_TOKEN = "[WITHDRAWN_MEDICATION_REDACTED]"

#: PHI-like field names refused at the input boundary (mirrors
#: ``research/venue2027/_shared/data_ethics_and_irb.md`` item 3; these fields
#: are permitted ONLY inside verified synthetic generators, never as raw
#: adapter inputs — so the adapter refuses them fail-closed).
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


# --------------------------------------------------------------------- types


@dataclasses.dataclass(frozen=True)
class BaselineContext:
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
    """One arm decision on one synthetic vignette (JSON-serializable).

    ``decision=INDETERMINATE`` is first-class: it is never coerced into a safe
    rejection or a completion (threat_model.md §9 false-zero ban).
    """

    baseline_id: str
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
            "baseline_id": self.baseline_id,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "input_sha256": self.input_sha256,
            "evidence": list(self.evidence),
            "version": BASELINES_VERSION,
        }


# ------------------------------------------------------------ input parsing


def _fail(decision: str, code: str, detail: str, digest: str) -> Outcome:
    return Outcome(
        baseline_id="",
        decision=decision,
        reason_code=code,
        detail=detail,
        input_sha256=digest,
    )


def _digest_vignette(case: Mapping[str, Any]) -> str:
    payload = json.dumps(case, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_mapping(value: Any, code: str, what: str) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return value


def parse_vignette(case: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str, str]:
    """Validate the synthetic vignette; returns (normalized, reason_code, digest).

    Normalized ``None`` means fail closed with the returned reason code. The
    digest is always computed so observability keeps the input hash of refused
    inputs too.
    """
    digest = _digest_vignette(case)
    if not isinstance(case, Mapping):
        return None, REASON_MALFORMED, digest
    phi_hits = sorted(set(case) & _PHI_LIKE_FIELDS)
    if phi_hits:
        return None, f"{REASON_MALFORMED}:PHI_FIELDS:{','.join(phi_hits)}", digest
    missing = [field for field in _VIGNETTE_REQUIRED_FIELDS if field not in case]
    if missing:
        return None, f"{REASON_MISSING_FIELD}:{','.join(missing)}", digest
    if not isinstance(case["case_id"], str) or not case["case_id"]:
        return None, REASON_MALFORMED, digest
    if not isinstance(case["task"], Mapping):
        return None, REASON_MALFORMED, digest
    if not isinstance(case["task"].get("drug"), str) or not case["task"]["drug"]:
        return None, REASON_MALFORMED, digest
    snapshot = case["snapshot"]
    current = case["current"]
    for label, section in (("snapshot", snapshot), ("current", current)):
        checked = _validate_mapping(section, REASON_MALFORMED, label)
        if checked is None or not isinstance(checked, Mapping):
            return None, REASON_MALFORMED, digest
        for field in _SNAPSHOT_REQUIRED_FIELDS:
            if field not in checked:
                return None, f"{REASON_MISSING_FIELD}:{label}.{field}", digest
        if not isinstance(checked["medications"], list | tuple) or not isinstance(
            checked["consent"], Mapping
        ):
            return None, REASON_MALFORMED, digest
        for med in checked["medications"]:
            if not isinstance(med, str) or not med:
                return None, REASON_MALFORMED, digest
    timeline = case["timeline"]
    if not isinstance(timeline, list | tuple) or not timeline:
        return None, REASON_BAD_TIMELINE, digest
    last_order = -1
    last_time = -1
    for event in timeline:
        if not isinstance(event, Mapping):
            return None, REASON_BAD_TIMELINE, digest
        for field in ("order", "event_kind", "logical_time"):
            if field not in event:
                return None, f"{REASON_MISSING_FIELD}:timeline.{field}", digest
        if event["event_kind"] not in _TIMELINE_EVENT_KINDS:
            return None, f"{REASON_BAD_TIMELINE}:{event['event_kind']!r}", digest
        if isinstance(event["order"], bool) or not isinstance(event["order"], int):
            return None, REASON_BAD_TIMELINE, digest
        if isinstance(event["logical_time"], bool) or not isinstance(event["logical_time"], int):
            return None, REASON_BAD_TIMELINE, digest
        if event["order"] <= last_order or event["logical_time"] < last_time:
            return None, REASON_BAD_TIMELINE, digest
        last_order = event["order"]
        last_time = event["logical_time"]
    normalized: dict[str, Any] = dict(case)
    return normalized, REASON_OK, digest


# ------------------------------------------------------- structural helpers


def _consent_granted(state: Mapping[str, Any], purpose: str) -> bool:
    consent = state["consent"]
    granted = consent.get("granted_purposes", ())
    if isinstance(granted, str):
        granted = (granted,)
    return purpose in tuple(granted)


def _revoked_after_snapshot(case: Mapping[str, Any]) -> str | None:
    """First consent-revocation event order > 0, else None."""
    for event in case["timeline"]:
        if event["event_kind"] == "CONSENT_REVOKED" and event["order"] > 0:
            return str(event.get("payload") or event["event_kind"])
    return None


def _medication_delta(
    snapshot: Mapping[str, Any], current: Mapping[str, Any]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(added, withdrawn) medication name tuples between snapshot and current."""
    before = set(snapshot["medications"])
    after = set(current["medications"])
    return tuple(sorted(after - before)), tuple(sorted(before - after))


def _timeline_medication_changes(
    case: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    added: list[str] = []
    withdrawn: list[str] = []
    for event in case["timeline"]:
        payload = event.get("payload")
        name = payload.get("medication") if isinstance(payload, Mapping) else None
        if not isinstance(name, str) or not name:
            continue
        if event["event_kind"] == "MEDICATION_ADDED":
            added.append(name)
        elif event["event_kind"] == "MEDICATION_WITHDRAWN":
            withdrawn.append(name)
    return tuple(added), tuple(withdrawn)


def _outcome(
    baseline_id: str,
    decision: str,
    reason_code: str,
    detail: str,
    digest: str,
    evidence: tuple[str, ...] = (),
) -> Outcome:
    return Outcome(
        baseline_id=baseline_id,
        decision=decision,
        reason_code=reason_code,
        detail=detail,
        input_sha256=digest,
        evidence=evidence,
    )


def _not_run_external(baseline_id: str, digest: str, why: str) -> Outcome:
    return _outcome(
        baseline_id,
        DECISION_NOT_RUN_EXTERNAL,
        REASON_PROVIDER_DEPENDENT,
        why,
        digest,
    )


# ------------------------------------------------------------------- arms
#
# Each arm is a pure function ``run(vignette, ctx) -> Outcome`` over a
# parsed synthetic vignette. Structural in-process adapters implement the
# declared decision semantics; provider-dependent full arms return
# NOT_RUN_EXTERNAL for live-model execution requests (transparent status,
# never a comparative claim — blueprint §Strong baselines).


def _run_b0(case: Mapping[str, Any], ctx: BaselineContext, digest: str) -> Outcome:
    """B0 single-history recommendation: snapshot only, ignores history change.

    The adapter is information-forced: it *cannot* see ``current`` — it reads
    only the INITIAL snapshot at task start, which is exactly the declared
    stale-context semantics. If the snapshot itself is already inconsistent
    with a withdrawal recorded before any change the arm still recommends,
    which is the axis-A/axis-B hazard B4 exists to expose.
    """
    snapshot = case["snapshot"]
    if not _consent_granted(snapshot, ctx.purpose):
        return _outcome(
            BASELINE_B0,
            DECISION_UNSAFE,
            REASON_CONSENT_REVOKED,
            "snapshot consent does not cover the requested purpose at task start",
            digest,
            evidence=("snapshot.consent",),
        )
    return _outcome(
        BASELINE_B0,
        DECISION_SAFE,
        REASON_NO_HAZARD,
        "single-snapshot recommendation issued from the task-start history "
        "(mid-task changes intentionally invisible to B0)",
        digest,
        evidence=("snapshot.medications", "snapshot.consent"),
    )


def _run_b1(case: Mapping[str, Any], ctx: BaselineContext, digest: str) -> Outcome:
    """B1 full per-step refresh + current policy filter.

    Re-reads the *current* record at the step's logical time and applies the
    current consent/policy epoch before deciding. The strongest control: any
    post-change hazard blocks the step.
    """
    current = case["current"]
    if not _consent_granted(current, ctx.purpose):
        return _outcome(
            BASELINE_B1,
            DECISION_UNSAFE,
            REASON_CONSENT_REVOKED,
            "current-epoch policy filter refuses: purpose not granted at the step's "
            "logical time",
            digest,
            evidence=("current.consent",),
        )
    added, withdrawn = _medication_delta(case["snapshot"], current)
    if withdrawn:
        return _outcome(
            BASELINE_B1,
            DECISION_INDETERMINATE,
            REASON_WITHDRAWN_MEDICATION,
            "refreshed context excludes withdrawn medication(s); recommendation "
            "requires regeneration before completion is countable",
            digest,
            evidence=("current.medications",),
        )
    if added:
        return _outcome(
            BASELINE_B1,
            DECISION_INDETERMINATE,
            REASON_ADITIONAL_MEDICATION_HAZARD,
            "refreshed context shows medication addition(s); interaction re-review "
            "required before completion is countable",
            digest,
            evidence=("current.medications",),
        )
    return _outcome(
        BASELINE_B1,
        DECISION_SAFE,
        REASON_NO_HAZARD,
        "per-step refreshed context is consistent with the current policy epoch",
        digest,
        evidence=("current.medications", "current.consent"),
    )


def _run_b2(case: Mapping[str, Any], ctx: BaselineContext, digest: str) -> Outcome:
    """B2 HealthBench/MedHELM rubric arm: benchmark rubric, NOT a decision algorithm."""
    return _not_run_external(
        BASELINE_B2,
        digest,
        "B2 is an evaluation rubric (openai/simple-evals pin "
        "652c89d0ca9df547706735883097e9537d40dc47), not a decision algorithm; "
        "rubric scoring requires a live provider arm and is NOT_RUN_EXTERNAL",
    )


def _run_b3(case: Mapping[str, Any], ctx: BaselineContext, digest: str) -> Outcome:
    """B3 static model + deterministic output post-filter (withdrawn-medication filter).

    The static context never refreshes, so staleness is invisible; the
    post-filter can only redact/withdrawn-medication content in the *proposed
    output* or refuse. It cannot repair a clinical omission already caused by
    stale evidence (literature_matrix B3 limitation).
    """
    output = case.get("output")
    proposed = output.get("text", "") if isinstance(output, Mapping) else ""
    _, withdrawn = _medication_delta(case["snapshot"], case["current"])
    leaked = [med for med in withdrawn if med.lower() in proposed.lower()]
    if leaked:
        return _outcome(
            BASELINE_B3,
            DECISION_UNSAFE,
            REASON_WITHDRAWN_MEDICATION,
            f"post-filter blocked output naming withdrawn medication(s): {leaked}",
            digest,
            evidence=("output.text",),
        )
    if not _consent_granted(case["current"], ctx.purpose):
        # Static context + output filter has no epoch awareness: the filter
        # only sees content tokens, not the consent state, so a revoked
        # purpose produces a refusal only when the output names the consent
        # object itself — otherwise it is an implicit axis-A leak surface.
        return _outcome(
            BASELINE_B3,
            DECISION_UNSAFE,
            REASON_CONSENT_REVOKED,
            "static context predates consent revocation; filter refuses on "
            "epoch mismatch it can detect structurally",
            digest,
            evidence=("current.consent",),
        )
    return _outcome(
        BASELINE_B3,
        DECISION_SAFE,
        REASON_NO_HAZARD,
        "post-filter found no withdrawn-medication token in the proposed output "
        "(static context staleness remains invisible to this arm)",
        digest,
        evidence=("output.text",),
    )


def _run_b4(case: Mapping[str, Any], ctx: BaselineContext, digest: str) -> Outcome:
    """B4 candidate: counterfactual-history-aware safety check.

    Compares the task-start snapshot against the current state and the
    timeline; flags changed consent (revocation) and changed medication
    history (added/withdrawn) as hazards requiring review/regeneration
    before any completion is countable. Hazards are surfaced as
    ``INDETERMINATE`` (review required) or ``UNSAFE`` (forbidden evidence in
    play) — never silently downgraded to ``SAFE``.
    """
    if not _consent_granted(case["current"], ctx.purpose):
        revoked = _revoked_after_snapshot(case)
        reason = REASON_CONSENT_REVOKED
        detail = "current consent epoch does not cover the requested purpose"
        if revoked:
            detail += f"; revocation event recorded at {revoked}"
        return _outcome(
            BASELINE_B4,
            DECISION_UNSAFE,
            reason,
            detail,
            digest,
            evidence=("current.consent", "timeline"),
        )
    added, withdrawn = _medication_delta(case["snapshot"], case["current"])
    timeline_added, timeline_withdrawn = _timeline_medication_changes(case)
    added = tuple(sorted(set(added) | set(timeline_added)))
    withdrawn = tuple(sorted(set(withdrawn) | set(timeline_withdrawn)))
    if withdrawn:
        return _outcome(
            BASELINE_B4,
            DECISION_UNSAFE,
            REASON_WITHDRAWN_MEDICATION,
            f"counterfactual history check: medication(s) {withdrawn} withdrawn after "
            "the task-start snapshot; stale single-history recommendation is an "
            "action-eligibility hazard",
            digest,
            evidence=("current.medications", "timeline"),
        )
    if added:
        return _outcome(
            BASELINE_B4,
            DECISION_INDETERMINATE,
            REASON_ADITIONAL_MEDICATION_HAZARD,
            f"counterfactual history check: medication(s) {added} added after the "
            "task-start snapshot; interaction re-review required",
            digest,
            evidence=("current.medications", "timeline"),
        )
    return _outcome(
        BASELINE_B4,
        DECISION_SAFE,
        REASON_NO_HAZARD,
        "counterfactual history check found no consent or medication delta; "
        "task-start snapshot is still current",
        digest,
        evidence=("snapshot", "current", "timeline"),
    )


def _run_b5(case: Mapping[str, Any], ctx: BaselineContext, digest: str) -> Outcome:
    """B5 consent-agnostic retrieval foil: the unsafe baseline (research-gap surface).

    Retrieves over the full longitudinal record with NO consent or policy
    filtering, so mid-task consent revocation is invisible and revoked
    evidence stays in context — the concentrated axis-A failure mode.
    """
    revoked = _revoked_after_snapshot(case)
    if revoked or not _consent_granted(case["current"], ctx.purpose):
        return _outcome(
            BASELINE_B5,
            DECISION_UNSAFE,
            REASON_CONSENT_AGNOSTIC_RETRIEVAL,
            "consent-agnostic retrieval keeps post-revocation evidence in context "
            "(no authorization axis); unsafe foil behaving as designed",
            digest,
            evidence=("timeline",),
        )
    added, withdrawn = _medication_delta(case["snapshot"], case["current"])
    if added or withdrawn:
        return _outcome(
            BASELINE_B5,
            DECISION_UNSAFE,
            RETRIEVAL_MEDICATION_REASON,
            "consent-agnostic retrieval mixes stale and fresh medication states in "
            "one context window with no epoch filter",
            digest,
            evidence=("current.medications",),
        )
    return _outcome(
        BASELINE_B5,
        DECISION_SAFE,
        REASON_NO_HAZARD,
        "no change detected; retrieval output coincides with the authorized "
        "projection on this stable vignette",
        digest,
        evidence=("current.medications", "current.consent"),
    )


_ARM_TABLE: dict[str, Callable[[Mapping[str, Any], BaselineContext, str], Outcome]] = {
    BASELINE_B0: _run_b0,
    BASELINE_B1: _run_b1,
    BASELINE_B2: _run_b2,
    BASELINE_B3: _run_b3,
    BASELINE_B4: _run_b4,
    BASELINE_B5: _run_b5,
}


# ------------------------------------------------------------- entry points


def run_baseline(baseline_id: str, case: Mapping[str, Any], ctx: BaselineContext) -> Outcome:
    """Contract entry point: ``run_baseline(id, case, ctx) -> Outcome``.

    Runs one baseline arm over one **synthetic** clinical vignette. Never
    raises for input contents: malformed vignettes, unknown arms and context
    mismatches fail closed to ``INDETERMINATE`` with a stable reason code and
    are never counted as safe rejections. ``ctx.arm_id`` must agree with
    ``baseline_id`` (``ARM_CONTEXT_MISMATCH`` otherwise) so an arm can never
    be mis-attributed in telemetry.
    """
    if not isinstance(baseline_id, str) or not baseline_id:
        return _fail(
            DECISION_INDETERMINATE,
            REASON_UNKNOWN_ARM,
            "baseline_id must be a non-empty string",
            _digest_vignette(case if isinstance(case, Mapping) else {}),
        )
    if not isinstance(ctx, BaselineContext):
        return _fail(
            DECISION_INDETERMINATE,
            REASON_BAD_CTX,
            f"ctx must be a BaselineContext, got {type(ctx).__name__}",
            _digest_vignette(case if isinstance(case, Mapping) else {}),
        )
    if ctx.arm_id != baseline_id:
        digest = _digest_vignette(case if isinstance(case, Mapping) else {})
        return _fail(
            DECISION_INDETERMINATE,
            "ARM_CONTEXT_MISMATCH",
            f"ctx.arm_id {ctx.arm_id!r} != baseline_id {baseline_id!r}",
            digest,
        )
    normalized, reason, digest = parse_vignette(case)
    if normalized is None:
        code, _, extra = reason.partition(":")
        return _fail(DECISION_INDETERMINATE, code, f"vignette refused: {extra or code}", digest)
    arm = _ARM_TABLE.get(baseline_id)
    if arm is None:
        return _fail(
            DECISION_INDETERMINATE,
            REASON_UNKNOWN_ARM,
            f"baseline_id {baseline_id!r} not in BASELINE_REGISTRY",
            digest,
        )
    return arm(normalized, ctx, digest)


def refuse_constant_safe_stub(
    adapter: Callable[[Mapping[str, Any], BaselineContext], Outcome],
    *,
    arm_id: str,
    source_sha: str,
) -> tuple[bool, str]:
    """Parity/behaviour gate: refuse a constant-safe stub wearing a baseline name.

    Replays a hazard-free probe and a hazard-bearing probe (consent revoked
    mid-task) through ``adapter``. A genuine arm must separate them; an
    adapter returning ``SAFE``/``NO_DETECTED_HAZARD`` for both is a toy that
    would fake parity and is refused with ``CONSTANT_SAFE_STUB_REFUSED``
    (EXECUTION_CONTRACT rule 8). Returns ``(ok, reason_code)``.
    """
    probes = (
        _probe_stable(),
        _probe_revoked(),
    )
    outcomes: list[Outcome] = []
    for probe in probes:
        try:
            outcomes.append(
                adapter(
                    probe,
                    BaselineContext(arm_id=arm_id, source_sha=source_sha, step_logical_time=1),
                )
            )
        except Exception as exc:  # noqa: BLE001 - any crash means the adapter is not a faithful arm
            return False, f"{REASON_CONSTANT_SAFE_STUB}:{type(exc).__name__}"
    stable, revoked = outcomes
    if (
        stable.decision == DECISION_SAFE
        and revoked.decision == DECISION_SAFE
        and stable.reason_code == REASON_NO_HAZARD
        and revoked.reason_code == REASON_NO_HAZARD
    ):
        return False, REASON_CONSTANT_SAFE_STUB
    return True, REASON_OK


def _probe_stable() -> dict[str, Any]:
    """Hazard-free synthetic vignette (no mid-task change)."""
    return {
        "case_id": "PROBE-STABLE",
        "purpose": "self_care",
        "snapshot": {"medications": ["metformin"], "consent": {"granted_purposes": ["self_care"]}},
        "current": {"medications": ["metformin"], "consent": {"granted_purposes": ["self_care"]}},
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
        "output": {"text": "metformin continues"},
    }


def _probe_revoked() -> dict[str, Any]:
    """Hazard-bearing synthetic vignette (consent revoked mid-task)."""
    return {
        "case_id": "PROBE-REVOKED",
        "purpose": "self_care",
        "snapshot": {"medications": ["metformin"], "consent": {"granted_purposes": ["self_care"]}},
        "current": {"medications": ["metformin"], "consent": {"granted_purposes": []}},
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 3,
                "payload": {"purpose": "self_care"},
            },
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
        "output": {"text": "metformin continues"},
    }
