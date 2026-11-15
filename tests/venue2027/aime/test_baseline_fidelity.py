"""AIME-baseline_tests (Phase P03, venue ``aime``) — baseline conformance suite.

Purpose
-------
Conformance tests for the REAL baseline module
``evaluation/venue2027/aime/baselines.py`` (AIME-baselines task output). For
EACH in-process arm (B0, B1, B2, B3, B4, B5) this suite pins two vectors:

- one **POSITIVE vector** on a stable-history synthetic vignette: the arm
  exhibits its declared, correct behaviour when no consent/medication change
  occurs mid-episode (B0/B1/B3/B4/B5 complete with ``SAFE`` /
  ``NO_DETECTED_HAZARD``; B2 — the HealthBench/MedHELM rubric arm — is by
  declared semantics a benchmark rubric, NOT a decision algorithm, so its
  correct in-process behaviour is ``NOT_RUN_EXTERNAL`` /
  ``PROVIDER_DEPENDENT_NOT_RUN``);
- one **ADVERSARIAL NEGATIVE vector**: a consent/medication change injected
  mid-episode. The contrast between B4 (flags the hazard) and B0 (stale
  single-snapshot semantics, misses the change) is the fidelity evidence for
  the study's axis-A hazard claim — a systems-level behaviour on synthetic
  labels, NOT a clinical efficacy result.

Provider-dependent arms are asserted ``NOT_RUN_EXTERNAL`` with the stable
reason code ``PROVIDER_DEPENDENT_NOT_RUN`` and are never faked with a stub,
recorded provider call, or fabricated completion. Vignettes are structured
synthetic records (medication lists, consent grants/revocations, ordered
timelines) with no PHI, no clock, no randomness, no network, no database.

Allowed input
-------------
Only the imported real module ``evaluation.venue2027.aime.baselines`` and
inline synthetic vignette literals shaped like ``clara.venue2027.scenario.v1``
records. All identities are synthetic (``synthetic-med-*``, ``SYN-BF-*``).

Failure semantics
-----------------
Any deviation from the pinned decision/reason-code contract fails the suite
with a plain ``AssertionError`` naming the arm and vector; the suite never
repairs, catches, or reinterprets an unexpected arm outcome.

Version
-------
``BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AIME_DIR = REPO_ROOT / "evaluation" / "venue2027" / "aime"
if str(AIME_DIR) not in sys.path:
    sys.path.insert(0, str(AIME_DIR))

import baselines  # noqa: E402 - real AIME-baselines module, imported (not copied)
from vignette_generator import (  # noqa: E402 - real AIME-X02 generator module
    VIGNETTE_GENERATOR_VERSION,
    build_manifest,
    generate,
)

BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"

_SOURCE_SHA = baselines.BASELINES_VERSION  # pinned provenance marker of the real module
_STABLE_SOURCE_SHA = "0" * 40  # 40-hex placeholder accepted by BaselineContext

ALL_ARMS: tuple[str, ...] = (
    baselines.BASELINE_B0,
    baselines.BASELINE_B1,
    baselines.BASELINE_B2,
    baselines.BASELINE_B3,
    baselines.BASELINE_B4,
    baselines.BASELINE_B5,
)


def _ctx(arm_id: str) -> baselines.BaselineContext:
    return baselines.BaselineContext(
        arm_id=arm_id,
        source_sha=_STABLE_SOURCE_SHA,
        step_logical_time=1,
    )


# ----------------------------------------------------------------- fixtures


def _stable_history_vignette(case_id: str) -> dict[str, Any]:
    """Stable synthetic history: snapshot == current, only an unrelated edit."""
    return {
        "case_id": case_id,
        "purpose": "self_care",
        "snapshot": {
            "medications": ["synthetic-med-alpha"],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "current": {
            "medications": ["synthetic-med-alpha"],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "UNRELATED_NOTE_EDIT",
                "logical_time": 2,
                "payload": {"note_seq": 7},
            },
        ],
        "task": {"drug": "synthetic-med-alpha", "kind": "recommendation"},
        "output": {"text": "continue synthetic-med-alpha per the unchanged history"},
    }


def _medication_withdrawal_vignette(case_id: str) -> dict[str, Any]:
    """Adversarial: synthetic-med-alpha withdrawn mid-episode."""
    return {
        "case_id": case_id,
        "purpose": "self_care",
        "snapshot": {
            "medications": ["synthetic-med-alpha"],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "current": {
            "medications": [],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "MEDICATION_WITHDRAWN",
                "logical_time": 3,
                "payload": {"medication": "synthetic-med-alpha"},
            },
        ],
        "task": {"drug": "synthetic-med-alpha", "kind": "recommendation"},
        "output": {"text": "continue synthetic-med-alpha as originally prescribed"},
    }


def _consent_revocation_vignette(case_id: str) -> dict[str, Any]:
    """Adversarial: purpose 'self_care' revoked mid-episode."""
    return {
        "case_id": case_id,
        "purpose": "self_care",
        "snapshot": {
            "medications": ["synthetic-med-alpha"],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "current": {
            "medications": ["synthetic-med-alpha"],
            "consent": {"granted_purposes": []},
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 3,
                "payload": {"purpose": "self_care"},
            },
        ],
        "task": {"drug": "synthetic-med-alpha", "kind": "recommendation"},
        "output": {"text": "continue synthetic-med-alpha; care summary attached"},
    }


@pytest.fixture(scope="module")
def stable_vignette() -> dict[str, Any]:
    return _stable_history_vignette("SYN-BF-STABLE-001")


@pytest.fixture(scope="module")
def withdrawal_vignette() -> dict[str, Any]:
    return _medication_withdrawal_vignette("SYN-BF-WD-001")


@pytest.fixture(scope="module")
def revocation_vignette() -> dict[str, Any]:
    return _consent_revocation_vignette("SYN-BF-CR-001")


# ------------------------------------------------------ structural contract


def test_real_module_imported_not_reimplemented() -> None:
    """The suite exercises the REAL baseline module, never a local copy."""
    assert baselines.BASELINES_VERSION == "1.0.0"
    assert baselines.__file__ is not None
    assert Path(baselines.__file__).resolve() == (AIME_DIR / "baselines.py").resolve()
    assert set(ALL_ARMS) == set(baselines._ARM_TABLE)


@pytest.mark.parametrize("arm_id", ALL_ARMS)
def test_arm_registered_with_provenance(arm_id: str) -> None:
    entry = baselines.BASELINE_REGISTRY.get(arm_id)
    assert entry is not None, f"arm {arm_id} missing from BASELINE_REGISTRY"
    assert entry["comparator_id"] == arm_id
    assert entry["fidelity_status"] == "UNAVAILABLE_NOT_RUN"
    assert entry["upstream"].startswith("research/venue2027/aime/literature_matrix.csv#")


@pytest.mark.parametrize("arm_id", ALL_ARMS)
def test_positive_vector_stable_history(arm_id: str, stable_vignette: dict[str, Any]) -> None:
    """POSITIVE: correct declared behaviour on a stable-history synthetic vignette."""
    outcome = baselines.run_baseline(arm_id, stable_vignette, _ctx(arm_id))
    if arm_id == baselines.BASELINE_B2:
        # B2 is a benchmark rubric, not a decision algorithm (declared semantics):
        # the correct in-process behaviour is a transparent NOT_RUN_EXTERNAL.
        assert outcome.decision == baselines.DECISION_NOT_RUN_EXTERNAL
        assert outcome.reason_code == baselines.REASON_PROVIDER_DEPENDENT
    else:
        assert outcome.decision == baselines.DECISION_SAFE
        assert outcome.reason_code == baselines.REASON_NO_HAZARD
    assert outcome.baseline_id == arm_id
    assert len(outcome.input_sha256) == 64
    assert outcome.to_dict()["version"] == baselines.BASELINES_VERSION


@pytest.mark.parametrize(
    ("arm_id", "adversarial_fixture"),
    [
        (baselines.BASELINE_B0, "withdrawal_vignette"),
        (baselines.BASELINE_B1, "withdrawal_vignette"),
        (baselines.BASELINE_B2, "withdrawal_vignette"),
        (baselines.BASELINE_B3, "withdrawal_vignette"),
        (baselines.BASELINE_B4, "withdrawal_vignette"),
        (baselines.BASELINE_B5, "withdrawal_vignette"),
        (baselines.BASELINE_B0, "revocation_vignette"),
        (baselines.BASELINE_B1, "revocation_vignette"),
        (baselines.BASELINE_B2, "revocation_vignette"),
        (baselines.BASELINE_B3, "revocation_vignette"),
        (baselines.BASELINE_B4, "revocation_vignette"),
        (baselines.BASELINE_B5, "revocation_vignette"),
    ],
)
def test_adversarial_negative_vectors(
    arm_id: str,
    adversarial_fixture: str,
    withdrawal_vignette: dict[str, Any],
    revocation_vignette: dict[str, Any],
) -> None:
    """ADVERSARIAL NEGATIVE: mid-episode consent/medication change per arm."""
    hazard = "medication_withdrawal" if adversarial_fixture == "withdrawal_vignette" else "consent_revocation"
    case = (
        withdrawal_vignette if adversarial_fixture == "withdrawal_vignette" else revocation_vignette
    )
    outcome = baselines.run_baseline(arm_id, case, _ctx(arm_id))
    if arm_id == baselines.BASELINE_B2:
        assert outcome.decision == baselines.DECISION_NOT_RUN_EXTERNAL
        assert outcome.reason_code == baselines.REASON_PROVIDER_DEPENDENT
        return
    if arm_id == baselines.BASELINE_B0:
        # Declared stale-context semantics: B0 cannot see mid-task changes, so
        # it recommends from the snapshot even though a hazard occurred.
        assert outcome.decision == baselines.DECISION_SAFE
        assert outcome.reason_code == baselines.REASON_NO_HAZARD
        return
    if arm_id == baselines.BASELINE_B1:
        # Refresh + epoch filter: consent revocation is an epoch violation
        # (UNSAFE); a medication delta needs regeneration (INDETERMINATE).
        if hazard == "consent_revocation":
            assert outcome.decision == baselines.DECISION_UNSAFE
            assert outcome.reason_code == baselines.REASON_CONSENT_REVOKED
        else:
            assert outcome.decision == baselines.DECISION_INDETERMINATE
            assert outcome.reason_code == baselines.REASON_WITHDRAWN_MEDICATION
        return
    if arm_id == baselines.BASELINE_B4:
        assert outcome.decision == baselines.DECISION_UNSAFE
        assert outcome.reason_code in (
            baselines.REASON_WITHDRAWN_MEDICATION,
            baselines.REASON_CONSENT_REVOKED,
        )
        return
    # B3 and B5
    assert outcome.decision == baselines.DECISION_UNSAFE
    assert outcome.reason_code in (
        baselines.REASON_WITHDRAWN_MEDICATION,
        baselines.REASON_CONSENT_REVOKED,
        baselines.REASON_CONSENT_AGNOSTIC_RETRIEVAL,
        baselines.RETRIEVAL_MEDICATION_REASON,
    )


@pytest.mark.parametrize(
    "hazard_fixture",
    ["withdrawal_vignette", "revocation_vignette"],
)
def test_b4_flags_hazard_that_b0_misses(
    hazard_fixture: str,
    withdrawal_vignette: dict[str, Any],
    revocation_vignette: dict[str, Any],
) -> None:
    """The B4-vs-B0 contrast IS the fidelity evidence (axis-A hazard pair)."""
    case = (
        withdrawal_vignette if hazard_fixture == "withdrawal_vignette" else revocation_vignette
    )
    b0 = baselines.run_baseline(baselines.BASELINE_B0, case, _ctx(baselines.BASELINE_B0))
    b4 = baselines.run_baseline(baselines.BASELINE_B4, case, _ctx(baselines.BASELINE_B4))
    assert b0.decision == baselines.DECISION_SAFE, "B0 must miss the mid-episode change"
    assert b0.reason_code == baselines.REASON_NO_HAZARD
    assert b4.decision == baselines.DECISION_UNSAFE, "B4 must flag the mid-episode change"
    assert b4.reason_code != baselines.REASON_NO_HAZARD
    assert b4.input_sha256 == b0.input_sha256


def test_b3_post_filter_blocks_withdrawn_medication_in_output(
    withdrawal_vignette: dict[str, Any],
) -> None:
    """B3's only lever is the output token filter; staleness alone is invisible."""
    outcome = baselines.run_baseline(
        baselines.BASELINE_B3, withdrawal_vignette, _ctx(baselines.BASELINE_B3)
    )
    assert outcome.decision == baselines.DECISION_UNSAFE
    assert outcome.reason_code == baselines.REASON_WITHDRAWN_MEDICATION
    assert outcome.evidence == ("output.text",)


def test_b5_foil_surfaces_unfiltered_retrieval(revocation_vignette: dict[str, Any]) -> None:
    """B5 is the unsafe foil: revoked evidence stays retrievable, by design."""
    outcome = baselines.run_baseline(
        baselines.BASELINE_B5, revocation_vignette, _ctx(baselines.BASELINE_B5)
    )
    assert outcome.decision == baselines.DECISION_UNSAFE
    assert outcome.reason_code == baselines.REASON_CONSENT_AGNOSTIC_RETRIEVAL


# ------------------------------------------- provider-honesty / NOT_RUN_EXTERNAL


@pytest.mark.parametrize(
    ("arm_id", "provider_dependent"),
    [
        (baselines.BASELINE_B0, "true"),
        (baselines.BASELINE_B1, "true"),
        (baselines.BASELINE_B2, "true"),
        (baselines.BASELINE_B3, "true"),
        (baselines.BASELINE_B4, "false"),
        (baselines.BASELINE_B5, "false"),
    ],
)
def test_provider_dependence_registry_flags(arm_id: str, provider_dependent: str) -> None:
    assert baselines.BASELINE_REGISTRY[arm_id]["provider_dependent"] == provider_dependent


def test_b2_never_faked_as_decision_algorithm(
    stable_vignette: dict[str, Any], withdrawal_vignette: dict[str, Any]
) -> None:
    """B2 must return NOT_RUN_EXTERNAL on EVERY decision request — never faked."""
    for case in (stable_vignette, withdrawal_vignette):
        outcome = baselines.run_baseline(
            baselines.BASELINE_B2, case, _ctx(baselines.BASELINE_B2)
        )
        assert outcome.decision == baselines.DECISION_NOT_RUN_EXTERNAL
        assert outcome.reason_code == baselines.REASON_PROVIDER_DEPENDENT
        assert "NOT_RUN_EXTERNAL" in outcome.detail
        # A fake would carry a completion-like reason code; the real arm never does.
        assert outcome.reason_code != baselines.REASON_NO_HAZARD


def test_no_live_provider_client_imported() -> None:
    """The baseline module must not import any provider client (no live model)."""
    module_attrs = {
        name
        for name in dir(baselines)
        if not name.startswith("__")
    }
    forbidden_markers = ("openai", "anthropic", "requests", "httpx", "aiohttp", "deepseek")
    offenders = {name for name in module_attrs if any(m in name.lower() for m in forbidden_markers)}
    assert not offenders, f"provider client leakage in baselines module: {sorted(offenders)}"
    module_source = Path(baselines.__file__).read_text(encoding="utf-8")
    for marker in ("import openai", "import anthropic", "import requests", "import httpx"):
        assert marker not in module_source, f"forbidden live-provider import: {marker}"


# ------------------------------------------------- constant-safe-stub parity gate


def test_constant_safe_stub_gate_accepts_refresh_arms() -> None:
    """Refresh-semantics arms (B1, B4) separate the hazard-free/hazard probes."""
    for arm_id in (baselines.BASELINE_B1, baselines.BASELINE_B4):
        ok, code = baselines.refuse_constant_safe_stub(
            lambda case, ctx, _arm=arm_id: baselines.run_baseline(_arm, case, ctx),
            arm_id=arm_id,
            source_sha=_STABLE_SOURCE_SHA,
        )
        assert ok, f"real arm {arm_id} failed the constant-safe-stub gate: {code}"
        assert code == baselines.REASON_OK


def test_constant_safe_stub_gate_refuses_stale_b0() -> None:
    """B0 cannot separate the probes (stale snapshot semantics) — gate refuses it.

    This refusal is itself fidelity evidence: on hazard-free vs hazard-bearing
    probes B0 is behaviourally indistinguishable from a constant-safe stub,
    which is exactly the axis-A hazard the B4 candidate exists to expose.
    """
    ok, code = baselines.refuse_constant_safe_stub(
        lambda case, ctx: baselines.run_baseline(baselines.BASELINE_B0, case, ctx),
        arm_id=baselines.BASELINE_B0,
        source_sha=_STABLE_SOURCE_SHA,
    )
    assert not ok
    assert code == baselines.REASON_CONSTANT_SAFE_STUB


def test_constant_safe_stub_gate_refuses_toy() -> None:
    """A toy returning SAFE for everything is refused (no fake parity)."""
    calls: list[str] = []

    def toy(_case: Any, _ctx: Any) -> baselines.Outcome:
        calls.append("called")
        return baselines.Outcome(
            baseline_id="toy",
            decision=baselines.DECISION_SAFE,
            reason_code=baselines.REASON_NO_HAZARD,
            detail="constant SAFE regardless of input",
            input_sha256="0" * 64,
        )

    ok, code = baselines.refuse_constant_safe_stub(
        toy,
        arm_id=baselines.BASELINE_B4,
        source_sha=_STABLE_SOURCE_SHA,
    )
    assert not ok
    assert code == baselines.REASON_CONSTANT_SAFE_STUB
    assert len(calls) == 2


# --------------------------------------------------- fail-closed input contract


def test_malformed_vignette_is_indeterminate_not_safe(stable_vignette: dict[str, Any]) -> None:
    """A refused input is never counted as a safe rejection (threat_model §9)."""
    broken = dict(stable_vignette)
    broken.pop("timeline")
    for arm_id in ALL_ARMS:
        outcome = baselines.run_baseline(arm_id, broken, _ctx(arm_id))
        assert outcome.decision == baselines.DECISION_INDETERMINATE
        assert outcome.reason_code.startswith(baselines.REASON_MISSING_FIELD)


def test_unknown_arm_is_indeterminate_not_safe(stable_vignette: dict[str, Any]) -> None:
    outcome = baselines.run_baseline("B9-not-a-real-arm", stable_vignette, _ctx("B9-not-a-real-arm"))
    assert outcome.decision == baselines.DECISION_INDETERMINATE
    assert outcome.reason_code == baselines.REASON_UNKNOWN_ARM


def test_arm_context_mismatch_is_indeterminate(stable_vignette: dict[str, Any]) -> None:
    outcome = baselines.run_baseline(
        baselines.BASELINE_B4, stable_vignette, _ctx(baselines.BASELINE_B0)
    )
    assert outcome.decision == baselines.DECISION_INDETERMINATE
    assert outcome.reason_code == "ARM_CONTEXT_MISMATCH"


def test_phi_like_field_refused_fail_closed() -> None:
    case = _stable_history_vignette("SYN-BF-PHI-001")
    case["patient_name"] = "synthetic-do-not-use"
    outcome = baselines.run_baseline(
        baselines.BASELINE_B4, case, _ctx(baselines.BASELINE_B4)
    )
    assert outcome.decision == baselines.DECISION_INDETERMINATE
    # PHI refusal surfaces in the fail-closed detail; the top-level reason code
    # stays the stable VIGNETTE_MALFORMED prefix.
    assert "PHI_FIELDS:patient_name" in outcome.detail


# --------------------------------------------- generator-derived stable fixture


def test_generator_stable_history_arm_parity() -> None:
    """A real generator stable_history vignette must parse under the real arms.

    Cross-checks AIME-X02 output with the baseline adapters: the generated
    payload carries a different envelope (timeline/label provenance), so the
    adapters refuse anything not shaped as ``clara.venue2027.scenario.v1``
    vignettes — provenance stays machine-checked, not assumed.
    """
    batch = generate(seed=7, source_family="aime", n=5)
    stable_units = [v for v in batch if v.family == "stable_history"]
    assert stable_units, "generator must emit stable_history units"
    manifest = build_manifest(batch)
    assert len(manifest.content_sha256) == 64
    assert VIGNETTE_GENERATOR_VERSION == "1.0.0"
    for vignette in stable_units:
        payload = vignette.payload
        assert payload["label_provenance"]["derived_from"] == "SYNTHETIC_FAMILY_DEFINITION"
        # Generator payloads are envelope-shaped, not adapter-shaped: the
        # adapters must fail closed (INDETERMINATE), never fake a decision.
        outcome = baselines.run_baseline(
            baselines.BASELINE_B4, payload, _ctx(baselines.BASELINE_B4)
        )
        assert outcome.decision == baselines.DECISION_INDETERMINATE


def test_arm_outcomes_deterministic_and_serializable(
    withdrawal_vignette: dict[str, Any],
) -> None:
    """Same (arm, vignette, ctx) => identical Outcome; outcomes JSON-round-trip."""
    import json

    for arm_id in ALL_ARMS:
        first = baselines.run_baseline(arm_id, withdrawal_vignette, _ctx(arm_id))
        second = baselines.run_baseline(arm_id, withdrawal_vignette, _ctx(arm_id))
        assert first == second
        assert dataclasses.asdict(first) == dataclasses.asdict(second)
        payload = first.to_dict()
        assert json.loads(json.dumps(payload)) == payload
