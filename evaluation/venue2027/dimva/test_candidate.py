"""Tests for DIMVA-candidate — GovernanceTrace adaptive probing detector.

Positive controls:
- A crafted low-and-slow cross-tool campaign (many denials spread over
  distinct tools, long sparse horizon, max denials per window under the
  static fixed-window operating point, bounded gaps) DETECTs with
  CAMPAIGN_STRUCTURE_DETECTED and every structural criterion met.
- The same campaign DETECTs through the ``run_candidate(case, ctx) -> Outcome``
  adapter as a REJECT alarm (counted_as_success=True) and through
  ``detect(events) -> Detection`` with identical score (two boundaries, one
  mechanism).
- Benign sessions are NOT flagged at the frozen threshold: a legitimate
  single retry, an authorized care-team handoff (delegated role changes in a
  second scope) and a same-scope denied burst (which a count alarm would
  flag) all return NO_DETECT / ADMIT.
- Tool-rename evasion: renaming every denied tool still DETECTs (entropy +
  distinct-tool linkage), and pacing the same denials densely inside one
  window removes the evasion signal (score drops, NO_DETECT via criterion).

Adversarial controls:
- Malformed inputs (non-list, empty, non-mapping events, unknown fields,
  leak-safe reason-code fields, missing fields, bad types, non-monotonic ts,
  mixed actors) yield first-class INDETERMINATE detections with stable reason
  codes — never silently a safe rejection, never an unhandled exception.
- Adapter: malformed case / non-mapping case -> INDETERMINATE (never
  counted); unregistered arm -> INVALID_RESULT / UNKNOWN_ARM; malformed
  DetectionParams raise CandidateError (wiring error).
- Determinism: repeated detections are byte-identical (to_dict equality).
- Independence: the candidate module source imports neither the independent
  truth oracle nor any label file — asserted with ``ast`` over the live
  source (imports are matched on whole dotted-path components, dynamic
  imports are flagged), so the detector stays adjudicable by the oracle
  without circularity (blueprint falsification rule).

No DB, no network, no clock, no randomness; synthetic minimal events only.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dimva.candidate import (
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    DEFAULT_PARAMS,
    DETECT,
    INDETERMINATE,
    NO_DETECT,
    RC_CAMPAIGN_STRUCTURE_DETECTED,
    RC_CASE_EVENTS_MISSING,
    RC_CASE_EVENTS_NOT_A_LIST,
    RC_EVENT_BAD_TYPE,
    RC_EVENT_MISSING_FIELD,
    RC_EVENT_NOT_AN_OBJECT,
    RC_EVENT_REASON_CODE_FORBIDDEN,
    RC_EVENT_SEQUENCE_EMPTY,
    RC_EVENT_TS_NOT_MONOTONIC,
    RC_EVENT_UNKNOWN_FIELD,
    RC_EVENTS_NOT_A_LIST,
    RC_MALFORMED_CASE,
    RC_NO_ALARM,
    RC_SESSION_MIXED_ACTORS,
    RC_UNKNOWN_ARM,
    CandidateError,
    DetectionParams,
    describe_mechanism,
    detect,
    run_candidate,
)

# ---------------------------------------------------------------------------
# Fixture sessions (synthetic minimal events; oracle labels by construction).
# ---------------------------------------------------------------------------


def _event(actor_id: str, tool: str, scope: str, allowed: bool, ts: int) -> dict[str, object]:
    return {
        "actor_id": actor_id,
        "tool": tool,
        "scope": scope,
        "allowed": allowed,
        "ts": ts,
    }


def _low_and_slow_campaign() -> dict[str, object]:
    """Crafted low-and-slow cross-tool campaign (oracle: ATTACK by construction).

    9 denials over 9 distinct denied tools across ~8h logical time, max 1
    denial per probe window (pacing under the static fixed-window operating
    point: 3700s gaps > the 3600s window), bounded inter-denial gaps: one
    linked campaign, not one-offs.
    """
    events = [
        _event("actor-adv-2", f"probe_tool_{i:02d}", "self_care", False, 1000 + 3700 * i)
        for i in range(9)
    ]
    events.append(_event("actor-adv-2", "med_read", "self_care", True, 1500))
    events.sort(key=lambda e: e["ts"])  # type: ignore[arg-type, return-value]
    return {"case_id": "DIMVA-CASE-03", "events": events}


def _benign_retry() -> dict[str, object]:
    """Single legitimate retry after a transient failure (oracle: BENIGN)."""
    return {
        "case_id": "DIMVA-CASE-01",
        "events": [
            _event("actor-clean", "med_schedule_read", "self_care", False, 100),
            _event("actor-clean", "med_schedule_read", "self_care", True, 160),
            _event("actor-clean", "vitals_read", "self_care", True, 300),
        ],
    }


def _benign_handoff() -> dict[str, object]:
    """Authorized care-team handoff: delegated role change, second scope, no denials."""
    return {
        "case_id": "DIMVA-CASE-04",
        "events": [
            _event("actor-clinician", "med_schedule_read", "self_care", True, 100),
            _event("actor-clinician", "care_plan_read", "care_team_handoff", True, 200),
            _event("actor-clinician", "care_plan_write", "care_team_handoff", True, 300),
            _event("actor-clinician", "vitals_read", "self_care", True, 400),
        ],
    }


def _benign_burst() -> dict[str, object]:
    """Same-scope denied burst: a count alarm trips, the candidate must not."""
    events = [
        _event(
            "actor-clean-busy",
            "med_schedule_read" if i % 2 == 0 else "vitals_read",
            "self_care",
            i % 2 == 1,
            5000 + 2 * i,
        )
        for i in range(10)
    ]
    return {"case_id": "DIMVA-CASE-08", "events": events}


def _renamed_campaign() -> dict[str, object]:
    """Tool-rename evasion: same campaign shape, every denied tool renamed."""
    events = [
        _event("actor-adv-3", f"renamed_{i:02d}_v2", "self_care", False, 1000 + 3300 * i)
        for i in range(9)
    ]
    events.sort(key=lambda e: e["ts"])  # type: ignore[arg-type, return-value]
    return {"case_id": "DIMVA-CASE-07", "events": events}


# ---------------------------------------------------------------------------
# Positive controls — crafted low-and-slow campaign is detected.
# ---------------------------------------------------------------------------


class TestLowAndSlowCampaignDetected:
    def test_detect_flags_crafted_low_and_slow_campaign(self) -> None:
        case = _low_and_slow_campaign()
        detection = detect(case["events"])  # type: ignore[arg-type]
        assert detection.decision == DETECT
        assert detection.reason == RC_CAMPAIGN_STRUCTURE_DETECTED
        assert 0.0 <= detection.score <= 1.0
        assert detection.score >= DEFAULT_PARAMS.detect_threshold
        assert detection.evidence["criteria_met"] == detection.evidence["criteria_total"]
        assert detection.evidence["total_denials"] == 9
        assert detection.evidence["distinct_denied_tools"] == 9
        assert detection.evidence["max_window_denials"] == 1
        assert detection.evidence["max_window_denials"] < DEFAULT_PARAMS.probe_window_threshold

    def test_all_structural_criteria_hold_on_campaign(self) -> None:
        detection = detect(_low_and_slow_campaign()["events"])  # type: ignore[arg-type]
        criteria = detection.evidence["criteria"]
        assert criteria["enough_denials"] is True
        assert criteria["cross_tool_obfuscation"] is True
        assert criteria["long_horizon_span"] is True
        assert criteria["evades_fixed_window"] is True
        assert criteria["activity_continuity"] is True

    def test_adapter_maps_campaign_to_reject_alarm(self) -> None:
        outcome = run_candidate(_low_and_slow_campaign(), {"arm_id": CANDIDATE_ID})
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is True
        assert RC_CAMPAIGN_STRUCTURE_DETECTED in outcome.detail

    def test_detect_and_adapter_agree_on_score(self) -> None:
        case = _low_and_slow_campaign()
        detection = detect(case["events"])  # type: ignore[arg-type]
        outcome = run_candidate(case, {"arm_id": CANDIDATE_ID})
        score_fragment = outcome.detail.split("score=")[1]
        assert float(score_fragment) == pytest.approx(detection.score)

    def test_tool_rename_evasion_still_detected(self) -> None:
        detection = detect(_renamed_campaign()["events"])  # type: ignore[arg-type]
        assert detection.decision == DETECT
        assert detection.reason == RC_CAMPAIGN_STRUCTURE_DETECTED

    def test_dense_pacing_removes_evasion_signal(self) -> None:
        # Same denials, densely packed inside one window: the low-and-slow
        # pacing criterion fails, so no campaign alarm (a count alarm WOULD
        # fire here — different mechanism, complementary coverage).
        events = [
            _event("actor-adv-4", f"tool_{i:02d}", "self_care", False, 1000 + i) for i in range(9)
        ]
        detection = detect(events)
        assert detection.decision == NO_DETECT
        assert detection.evidence["criteria"]["evades_fixed_window"] is False
        assert detection.evidence["max_window_denials"] >= DEFAULT_PARAMS.probe_window_threshold


# ---------------------------------------------------------------------------
# Positive controls — benign sessions are not flagged at the threshold.
# ---------------------------------------------------------------------------


class TestBenignNotFlagged:
    @pytest.mark.parametrize(
        ("name", "case_builder"),
        [
            ("single_retry", _benign_retry),
            ("care_team_handoff", _benign_handoff),
            ("same_scope_burst", _benign_burst),
        ],
    )
    def test_benign_sessions_admit(self, name: str, case_builder: object) -> None:
        case = case_builder()  # type: ignore[operator]
        detection = detect(case["events"])  # type: ignore[arg-type]
        assert detection.decision == NO_DETECT
        assert detection.reason == RC_NO_ALARM
        assert detection.score < DEFAULT_PARAMS.detect_threshold

    def test_benign_outcomes_through_adapter(self) -> None:
        for case in (_benign_retry(), _benign_handoff(), _benign_burst()):
            outcome = run_candidate(case, {"arm_id": CANDIDATE_ID})
            assert outcome.observed_outcome == "ADMIT"
            assert outcome.counted_as_success is True
            assert RC_NO_ALARM in outcome.detail

    def test_burst_score_below_campaign_score(self) -> None:
        # The burst has volume but no pacing evasion / horizon; the campaign
        # score must dominate.
        burst = detect(_benign_burst()["events"])  # type: ignore[arg-type]
        campaign = detect(_low_and_slow_campaign()["events"])  # type: ignore[arg-type]
        assert campaign.score > burst.score


# ---------------------------------------------------------------------------
# Adversarial controls — fail closed to INDETERMINATE on malformed events.
# ---------------------------------------------------------------------------


class TestMalformedFailClosed:
    def test_events_not_a_list(self) -> None:
        detection = detect("not-a-list")  # type: ignore[arg-type]
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENTS_NOT_A_LIST
        assert detection.score == 0.0

    def test_empty_sequence(self) -> None:
        detection = detect([])
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_SEQUENCE_EMPTY

    def test_event_not_an_object(self) -> None:
        detection = detect(["nope"])
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_NOT_AN_OBJECT

    def test_unknown_field(self) -> None:
        events = [dict(_event("a", "t", "s", True, 1), extra=1)]
        detection = detect(events)  # type: ignore[arg-type]
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_UNKNOWN_FIELD

    @pytest.mark.parametrize("leak_key", ["reason_code", "reject_reason", "why"])
    def test_reason_code_field_forbidden(self, leak_key: str) -> None:
        events = [dict(_event("a", "t", "s", True, 1), **{leak_key: "POLICY_DENIAL"})]
        detection = detect(events)  # type: ignore[arg-type]
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_REASON_CODE_FORBIDDEN

    def test_missing_field(self) -> None:
        detection = detect([{"actor_id": "a", "tool": "t", "allowed": True, "ts": 1}])
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_MISSING_FIELD

    @pytest.mark.parametrize(
        ("overrides",),
        [
            ({"actor_id": ""},),
            ({"tool": ""},),
            ({"scope": ""},),
            ({"allowed": "yes"},),
            ({"ts": -1},),
            ({"ts": True},),
            ({"ts": 1.5},),
        ],
    )
    def test_bad_types(self, overrides: dict[str, object]) -> None:
        events = [dict(_event("a", "t", "s", True, 1), **overrides)]
        detection = detect(events)  # type: ignore[arg-type]
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_BAD_TYPE

    def test_non_monotonic_ts(self) -> None:
        events = [
            _event("a", "t1", "s", True, 500),
            _event("a", "t2", "s", True, 100),
        ]
        detection = detect(events)
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_TS_NOT_MONOTONIC

    def test_mixed_actors(self) -> None:
        events = [
            _event("actor-a", "t1", "s", True, 1),
            _event("actor-b", "t2", "s", True, 2),
        ]
        detection = detect(events)
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_SESSION_MIXED_ACTORS


# ---------------------------------------------------------------------------
# Adapter boundary: run_candidate(case, ctx) -> Outcome.
# ---------------------------------------------------------------------------


class TestRunCandidateAdapter:
    def test_malformed_case_not_a_mapping(self) -> None:
        outcome = run_candidate("nope", {"arm_id": CANDIDATE_ID})  # type: ignore[arg-type]
        assert outcome.observed_outcome == INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == RC_MALFORMED_CASE

    def test_case_events_missing(self) -> None:
        outcome = run_candidate({"case_id": "x"}, {"arm_id": CANDIDATE_ID})
        assert outcome.observed_outcome == INDETERMINATE
        assert outcome.detail == RC_CASE_EVENTS_MISSING

    def test_case_events_not_a_list(self) -> None:
        outcome = run_candidate({"case_id": "x", "events": "bad"}, {"arm_id": CANDIDATE_ID})
        assert outcome.observed_outcome == INDETERMINATE
        assert outcome.detail == RC_CASE_EVENTS_NOT_A_LIST

    def test_unknown_arm_refused(self) -> None:
        outcome = run_candidate(_low_and_slow_campaign(), {"arm_id": "B0_IMPERSONATOR"})
        assert outcome.observed_outcome == "INVALID_RESULT"
        assert outcome.counted_as_success is False
        assert RC_UNKNOWN_ARM in outcome.detail

    def test_ctx_defaults_and_object_arm(self) -> None:
        # No ctx at all and a RunContext-shaped object both bind the default arm.
        by_default = run_candidate(_low_and_slow_campaign(), None)
        assert by_default.observed_outcome == "REJECT"

        class _Ctx:
            arm_id = CANDIDATE_ID

        by_object = run_candidate(_low_and_slow_campaign(), _Ctx())
        assert by_object.observed_outcome == "REJECT"

    def test_never_counts_indeterminate_as_success(self) -> None:
        outcome = run_candidate(
            {"case_id": "x", "events": [{"actor_id": "a"}]}, {"arm_id": CANDIDATE_ID}
        )
        assert outcome.observed_outcome == INDETERMINATE
        assert outcome.counted_as_success is False


# ---------------------------------------------------------------------------
# Operating point and determinism.
# ---------------------------------------------------------------------------


class TestParamsAndDeterminism:
    def test_malformed_params_raise_candidate_error(self) -> None:
        with pytest.raises(CandidateError):
            DetectionParams(min_denials=0)
        with pytest.raises(CandidateError):
            DetectionParams(detect_threshold=0.0)
        with pytest.raises(CandidateError):
            DetectionParams(probe_window_threshold=True)  # type: ignore[arg-type]

    def test_detect_refuses_non_params_object(self) -> None:
        with pytest.raises(CandidateError):
            detect(_low_and_slow_campaign()["events"], params="fast")  # type: ignore[arg-type]

    def test_determinism_byte_identical_outputs(self) -> None:
        events = _low_and_slow_campaign()["events"]  # type: ignore[union-attr]
        first = detect(events)  # type: ignore[arg-type]
        for _ in range(5):
            assert detect(events) == first  # type: ignore[arg-type]
        assert first.to_dict() == first.to_dict()

    def test_typed_outputs_json_serializable(self) -> None:
        import json

        case = _low_and_slow_campaign()
        payload = json.dumps(detect(case["events"]).to_dict())  # type: ignore[arg-type]
        assert CAMPAIGN_JSON_SENTINEL in payload or "CAMPAIGN_STRUCTURE_DETECTED" in payload

    def test_mechanism_record_shape(self) -> None:
        record = describe_mechanism()
        assert record["candidate_id"] == CANDIDATE_ID
        assert record["candidate_version"] == CANDIDATE_VERSION
        assert record["venue"] == "dimva"
        assert record["task_id"] == "DIMVA-candidate"
        assert "none:" in record["label_usage"]
        assert sorted(record["input_surface"]) == [
            "actor_id",
            "allowed",
            "scope",
            "tool",
            "ts",
        ]


CAMPAIGN_JSON_SENTINEL = "CAMPAIGN_STRUCTURE_DETECTED"


# ---------------------------------------------------------------------------
# Independence: the candidate imports neither the oracle nor label files.
# ---------------------------------------------------------------------------


#: Modules the candidate must never import: the DIMVA truth oracle, its
#: kernel helpers, and any scenario/label-generating module. Matched exactly
#: against whole import targets and dotted-path components — never by
#: substring, so ``candidate`` itself or similar-looking names are untouched.
FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {
        "evaluation.venue2027.dimva.independent_oracle",
        "evaluation.venue2027.dimva.generate_dataset",
        "evaluation.venue2027.dimva.campaign_generator",
        "evaluation.venue2027.dimva.benign_fault_generator",
        "evaluation.venue2027.dimva.group_split",
    }
)
FORBIDDEN_BASENAMES: frozenset[str] = frozenset(
    {"independent_oracle", "generate_dataset", "campaign_generator", "group_split"}
)
DYNAMIC_IMPORT_SENTINEL = "__dynamic__"


def _candidate_source() -> str:
    return Path(
        __import__("evaluation.venue2027.dimva.candidate", fromlist=["__file__"]).__file__
    ).read_text(encoding="utf-8")


def _import_targets(tree: ast.AST) -> set[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
            targets.update(alias.name for alias in node.names)
    return targets


def _scan_candidate_imports(source: str) -> frozenset[str]:
    """AST-scan candidate source for oracle/label-file imports.

    Whole dotted-path components are matched (closes alias/relative escape
    hatches); dynamic imports (``__import__`` / ``importlib.import_module``)
    are reported as the ``__dynamic__`` sentinel: their target is not
    statically provable, so they are flagged rather than guessed safe.
    """
    tree = ast.parse(source)
    found: set[str] = set()
    for target in _import_targets(tree):
        parts = target.split(".")
        if target in FORBIDDEN_IMPORTS or any(part in FORBIDDEN_BASENAMES for part in parts):
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


class TestIndependence:
    def test_candidate_does_not_import_oracle_or_label_files(self) -> None:
        found = _scan_candidate_imports(_candidate_source())
        assert (
            found == frozenset()
        ), f"candidate module imports forbidden oracle/label modules: {sorted(found)}"

    def test_scan_flags_rogue_candidate_importing_oracle(self) -> None:
        rogue = (
            "import evaluation.venue2027.dimva.independent_oracle\n"
            "from evaluation.venue2027.dimva import generate_dataset\n"
        )
        found = _scan_candidate_imports(rogue)
        assert "evaluation.venue2027.dimva.independent_oracle" in found
        assert "generate_dataset" in found

    def test_scan_flags_dynamic_imports(self) -> None:
        rogue = "import importlib\nimportlib.import_module('evaluation.venue2027.dimva.independent_oracle')\n"
        assert DYNAMIC_IMPORT_SENTINEL in _scan_candidate_imports(rogue)

    def test_scan_ignores_lookalike_names(self) -> None:
        clean = (
            "from evaluation.venue2027._shared.harness import Outcome\n"
            "import dataclasses\n"
            "import independent_oracle_helpers_unrelated\n"
        )
        assert _scan_candidate_imports(clean) == frozenset()

    def test_no_label_oracle_names_in_candidate_namespace(self) -> None:
        import evaluation.venue2027.dimva.candidate as candidate_module

        forbidden = {
            "adjudicate",
            "independent_oracle",
            "oracle_kernel",
            "generate",
            "FAMILY_SPECS",
            "campaign_label",
            "DIMVA_DETECTION_RULES",
        }
        exported = set(vars(candidate_module))
        assert exported.isdisjoint(forbidden)
