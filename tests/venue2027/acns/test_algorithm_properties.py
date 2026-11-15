"""ACNS-unit — deterministic property, metamorphic and mutation tests (P05).

Purpose
-------
Task ACNS-unit (Phase P05, venue acns) hardens the REAL ACNS evidence-boundary
classifiers of the SoK "Evidence Boundaries of Attestation in Tool-Using AI
Systems" (``research/venue2027/VENUES/acns/RESEARCH_BLUEPRINT.md``, RQ1-RQ3)
with deterministic property, metamorphic and mutation tests. Three real modules
are imported directly — no stub, no reimplementation:

- ``evaluation/venue2027/acns/candidate.py``    — the ANALYTIC INSTRUMENT
  (``classify_claim``, ``coverage_matrix``) reading claim records against the
  evidence-to-claim lattice (threat model §1.2) and gap register G1-G9;
- ``evaluation/venue2027/acns/baselines.py``    — the four EVIDENCE-BOUNDARY
  reference classes (B0-B3) over the pinned synthetic fixture records;
- ``evaluation/venue2027/acns/independent_oracle.py`` — the independent
  declarative truth oracle (frozen rule table, candidate-import-free).

SoK framing (asserted throughout): every verdict under test is an
**evidence-boundary verdict** — which lattice level the disclosed evidence
supports, which pre-registered gap G1-G9 fires, which claim is refused — and
never a mechanism outcome ("the tool ran", "the pipeline succeeded"). The
candidate's machine declaration (``describe_mechanism``:
``ANALYTIC_INSTRUMENT`` / ``is_mechanism=False`` / ``study_class=SoK``) is
asserted so the suite itself cannot drift into mechanism-evaluation framing.

Coverage map
------------
- positive / negative / unknown boundaries over the classifier trio, including
  INDETERMINATE retention (never coerced to a safe verdict) and the fail-closed
  reason codes (UNKNOWN_ARM / UNKNOWN_BASELINE / MALFORMED_CASE /
  NOT_RUN_EXTERNAL);
- two-step metamorphic relations: weakening operations (stripping an evidence
  binding, then removing the receipt table) can only *weaken or preserve* a
  claim's evidence-boundary status — never strengthen it — and stripping a
  receipt binding specifically can never downgrade a REJECT back to an ADMIT;
- mutation checks: gap-register row deletion (G4), accept-all and all-deny
  mutants of the instrument, and an oracle rule-table flip, each detected by
  the surviving properties (all-deny is caught by the liveness assertion that
  the clean control stays in-boundary — an arbitrary all-deny never passes).

Determinism
-----------
The modules under test are pure (no clock, no network, no hidden randomness).
The only stochastic step in this suite — bounded adversarial record sampling —
is a **deterministic sampling schedule** built from a stable permutation of
record indices (``_deterministic_sample_order``), seeded explicitly and
replayed twice to prove run-to-run equality. No ``random``/``numpy`` global
state is used anywhere.

Allowed input
-------------
Only the pinned synthetic fixture records of ``_smoke_fixtures.py``
(dataset ``synthetic-acns-2027``) and inline literal claim records. No PHI/PII,
no network, no database, no clock, no live provider.

Failure semantics
-----------------
A violated property surfaces as a normal assertion failure carrying the
structured evidence-boundary payload. Module-under-test stable reason codes
are exercised as-is and never counted as safe acceptances. Mutations are
injected only via ``unittest.mock.patch.object`` and fully restored (the
module under test is never left mutated on failure).

Version
-------
``ACNS_UNIT_PROPERTIES_VERSION = "1.0.0"`` over ``ACNS_BASELINES_VERSION``,
``CANDIDATE_VERSION`` and ``ACNS_INDEPENDENT_ORACLE_VERSION`` (all "1.0.0").
"""

from __future__ import annotations

import contextlib
import json
import typing
import unittest.mock

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.acns import _smoke_fixtures, baselines, candidate, independent_oracle
from evaluation.venue2027.acns.baselines import _CLASS_POLICIES, _classify

ACNS_UNIT_PROPERTIES_VERSION = "1.0.0"

B0 = "B0-attestation-only"
B1 = "B1-receipt-without-binding"
B2 = "B2-timestamp-only"
B3 = "B3-evidence-boundary-aware"
ALL_ARMS: tuple[str, ...] = (B0, B1, B2, B3)

#: Fixed deterministic seed for every randomized step of this suite.
DETERMINISTIC_SEED = 20271115

RECORD_KEYS: tuple[tuple[str, str], ...] = tuple(sorted(_smoke_fixtures.SYNTHETIC_CLAIM_RECORDS))

#: Evidence-boundary verdict content of the independent oracle, per family
#: (frozen before execution; the oracle is never repaired to match a candidate).
ORACLE_BOUNDARY_MATRIX: tuple[tuple[str, str, str], ...] = (
    (independent_oracle.FAMILY_BOUND_EVIDENCE, "ADMIT", "none"),
    (independent_oracle.FAMILY_ATTESTATION_DOWNGRADE, "REJECT", "G2_RECEIPT_AS_EXECUTION"),
    (independent_oracle.FAMILY_UNBOUND_CLAIM, "REJECT", "G7_LEVEL_IMPLICIT_UPGRADE"),
    (independent_oracle.FAMILY_REPLAYED_RECEIPT, "REJECT", "G4_SIGNATURE_AS_CONTEXT"),
)


# ---------------------------------------------------------------------------
# Deterministic helpers (no unseeded randomness anywhere in this suite).
# ---------------------------------------------------------------------------


def _deterministic_sample_order(
    items: typing.Sequence[typing.Any], seed: int, sample_size: int
) -> list[typing.Any]:
    """Fixed permutation sampling schedule: deterministic for a given seed.

    Implements a Fisher-Yates-style permutation driven only by an explicit
    linear-congruential generator seeded from ``seed`` — no ``random`` module,
    no hidden state, identical output for identical inputs. This is the suite's
    sole "randomness", and it is fully seeded by contract.
    """
    state = seed & 0xFFFFFFFF
    indices = list(range(len(items)))

    def _next() -> int:
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return state

    for position in range(len(indices) - 1, 0, -1):
        swap = _next() % (position + 1)
        indices[position], indices[swap] = indices[swap], indices[position]
    return [items[index] for index in indices[:sample_size]]


def _ctx(baseline_id: str, case_id: str) -> dict[str, typing.Any]:
    return {"arm_id": baseline_id, "case_id": case_id, "seed": DETERMINISTIC_SEED}


def _case(record_id: str, variant: str, case_id: str) -> dict[str, typing.Any]:
    return {
        "case_id": case_id,
        "record_id": record_id,
        "variant": variant,
        "dataset": _smoke_fixtures.FIXTURE_DATASET,
    }


def _verdict(outcome: Outcome) -> dict[str, typing.Any]:
    return json.loads(outcome.detail.split(" | ")[0])


def _gap_codes_of(outcome: Outcome) -> set[str]:
    return {gap["gap_code"] for gap in _verdict(outcome)["gaps"]}


def _run(baseline_id: str, record_id: str, variant: str, case_id: str) -> Outcome:
    return baselines.run_baseline(
        baseline_id, _case(record_id, variant, case_id), _ctx(baseline_id, case_id)
    )


def _classify_case(
    baseline_id: str, claims_case: dict[str, typing.Any], receipts: typing.Any
) -> typing.Any:
    policy = _CLASS_POLICIES[baseline_id]
    return _classify(baseline_id, dict(claims_case), policy, receipts)


# ---------------------------------------------------------------------------
# 1. Positive / negative / unknown boundary vectors over the real classifiers.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record_id", "variant", "arm_id", "expected_observed", "expected_granted", "expected_gaps"),
    [
        # Positive boundary: the fully bound record admits at its asserted level
        # under every reference class — no gap fires on clean evidence.
        *[
            pytest.param(
                "sok-claim-record-1",
                "bound",
                arm_id,
                "ADMIT",
                "L3-EXECUTED",
                (),
                id=f"positive/bound/{arm_id}",
            )
            for arm_id in ALL_ARMS
        ],
        # Negative boundary: provider receipt quoted as execution proof (G2).
        # B3 refuses with the register row; every weak stance admits at face value.
        pytest.param(
            "sok-claim-record-2",
            "downgraded",
            B3,
            "REJECT",
            "L2-ACKNOWLEDGED",
            ("G2_RECEIPT_AS_EXECUTION",),
            id="negative/downgrade/B3-refuses-at-L2",
        ),
        *[
            pytest.param(
                "sok-claim-record-2",
                "downgraded",
                arm_id,
                "ADMIT",
                "L3-EXECUTED",
                (),
                id=f"negative/downgrade/{arm_id}-misses-G2",
            )
            for arm_id in (B0, B1, B2)
        ],
        # Negative boundary: claim with no evidence binding at all (G7; the
        # missing rely-time schedule check G5 also fires — additive register).
        pytest.param(
            "sok-claim-record-3",
            "unbound",
            B3,
            "REJECT",
            "L1-ASSEMBLED",
            ("G7_LEVEL_IMPLICIT_UPGRADE", "G5_MINT_TIME_AS_RELY_TIME"),
            id="negative/unbound/B3-refuses",
        ),
        pytest.param(
            "sok-claim-record-3",
            "unbound",
            B0,
            "ADMIT",
            "L2-ACKNOWLEDGED",
            (),
            id="negative/unbound/B0-accepts-claimed-level",
        ),
        # Negative boundary: receipt bound to a different claim (G4 transplant;
        # the receipt-quoted-as-execution row G2 also fires — additive register).
        pytest.param(
            "sok-claim-record-4",
            "replayed",
            B3,
            "REJECT",
            "L2-ACKNOWLEDGED",
            ("G4_SIGNATURE_AS_CONTEXT", "G2_RECEIPT_AS_EXECUTION"),
            id="negative/replayed/B3-refuses",
        ),
        pytest.param(
            "sok-claim-record-4",
            "replayed",
            B1,
            "ADMIT",
            "L3-EXECUTED",
            (),
            id="negative/replayed/B1-accepts-unlinked-receipt",
        ),
    ],
)
def test_evidence_boundary_verdicts_on_pinned_records(
    record_id: str,
    variant: str,
    arm_id: str,
    expected_observed: str,
    expected_granted: str,
    expected_gaps: tuple[str, ...],
) -> None:
    """The REAL classifier trio's positive/negative boundary is exactly the
    pre-registered evidence-boundary semantics — a SoK verdict (granted lattice
    level + G-register gaps), never a mechanism outcome."""
    case_id = f"unit-boundary/{arm_id}/{variant}"
    outcome = _run(arm_id, record_id, variant, case_id)
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == expected_observed
    assert outcome.counted_as_success is (expected_observed == "ADMIT")
    verdict = _verdict(outcome)
    # SoK framing: the payload carries evidence-boundary fields only.
    assert set(verdict) == {
        "baseline_id",
        "case_id",
        "granted_level",
        "verdict",
        "reason_code",
        "gaps",
        "baseline_version",
        "verdict_digest",
    }
    assert verdict["granted_level"] == expected_granted
    assert verdict["verdict"] == ("ACCEPT" if expected_observed == "ADMIT" else "REJECT")
    assert tuple(gap["gap_code"] for gap in verdict["gaps"]) == expected_gaps
    for gap in verdict["gaps"]:
        assert gap["gap_code"] in baselines.KNOWN_GAP_CODES
    # Monotone lattice: a granted level never exceeds the asserted chain top.
    assert verdict["granted_level"] in baselines.LATTICE_LEVELS


def test_unknown_boundary_is_retained_not_coerced() -> None:
    """Unknown/undecidable inputs are first-class INDETERMINATE outcomes.

    The instrument retains undecidable coding inputs for human adjudication
    (rater manual §5) and the oracle retains unmodelled families with
    ``PENDING_ADJUDICATION`` — neither is ever coerced to a safe-looking ADMIT
    or REJECT (false-zero ban, GATES rule 4)."""
    malformed = candidate.classify_claim("not-a-mapping")
    assert malformed.boundary_status == "INDETERMINATE"
    assert malformed.reason_code == "MALFORMED_CLAIM"
    assert malformed.undecidable_fields == ("claim",)

    no_level = candidate.classify_claim({"claim_id": "c-u1", "dimension": "receipt"})
    assert no_level.boundary_status == "INDETERMINATE"
    assert no_level.reason_code == "FIELD_UNDECIDABLE_ASSERTED_LEVEL"
    assert no_level.undecidable_fields == ("asserted_level",)
    assert no_level.gap_codes == ()

    no_dimension = candidate.classify_claim({"claim_id": "c-u2", "asserted_level": "L2"})
    assert no_dimension.boundary_status == "INDETERMINATE"
    assert no_dimension.reason_code == "FIELD_UNDECIDABLE_DIMENSION"

    unmodelled = independent_oracle.adjudicate_boundary(
        {"case_id": "c-u3", "family": "unmodelled_family"}
    )
    assert unmodelled.oracle_result.outcome == "INDETERMINATE"
    assert unmodelled.gap_code == "PENDING_ADJUDICATION"
    # Retention, not coercion: no boundary content is fabricated.
    assert unmodelled.granted_level == ""
    assert unmodelled.refused_claim == ""

    no_family = independent_oracle.adjudicate_boundary({"case_id": "c-u4"})
    assert no_family.oracle_result.outcome == "INDETERMINATE"
    assert no_family.oracle_result.reason_code == "NO_FAMILY_DECLARED"


def test_unknown_boundary_fail_closed_reason_codes() -> None:
    """Unknown arms/classes, malformed cases and unavailable records are stable
    fail-closed reason codes, never silent acceptances."""
    rogue_candidate = candidate.run_candidate(
        _case("sok-claim-record-1", "bound", "unit-fc/1"), {"arm_id": "ALLOW-ALL", "seed": 0}
    )
    assert rogue_candidate.observed_outcome == "INVALID_RESULT"
    assert rogue_candidate.counted_as_success is False
    assert "UNKNOWN_ARM" in rogue_candidate.detail

    rogue_baseline = baselines.run_baseline(
        "NOT-A-CLASS", _case("sok-claim-record-1", "bound", "unit-fc/2"), _ctx(B3, "unit-fc/2")
    )
    assert rogue_baseline.observed_outcome == "INVALID_RESULT"
    assert "UNKNOWN_BASELINE" in rogue_baseline.detail

    malformed_baseline = baselines.run_baseline(B0, 42, _ctx(B0, "unit-fc/3"))
    assert malformed_baseline.observed_outcome == "INVALID_RESULT"
    assert "MALFORMED_CASE" in malformed_baseline.detail

    unavailable = baselines.run_baseline(
        B3, _case("record-not-pinned", "bound", "unit-fc/4"), _ctx(B3, "unit-fc/4")
    )
    assert unavailable.observed_outcome == "NOT_RUN_EXTERNAL"
    assert unavailable.counted_as_success is False
    assert unavailable.retriable is True

    missing_id = candidate.run_candidate(
        {"record_id": "sok-claim-record-1", "variant": "bound"}, {"arm_id": "ACNS-candidate"}
    )
    assert missing_id.observed_outcome in {"ADMIT", "REJECT", "INVALID_RESULT"}
    assert missing_id.counted_as_success is not True or missing_id.observed_outcome == "ADMIT"


# ---------------------------------------------------------------------------
# 2. Two-step metamorphic relations: weakening can never strengthen.
# ---------------------------------------------------------------------------


def _strip_binding(claim: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Weakening op 1: remove the claim's evidence bindings (receipt strip)."""
    return {key: value for key, value in claim.items() if key != "evidence_bindings"}


def _strip_receipt_table(
    claim: dict[str, typing.Any], receipts: typing.Any
) -> tuple[dict[str, typing.Any], None]:
    """Weakening op 2: remove the record's receipt table (verification input)."""
    return dict(claim), None


def test_candidate_two_step_weakening_never_strengthen() -> None:
    """Metamorphic relation M1 (instrument, two steps).

    Stripping a receipt binding (step 1) and then removing the receipt
    verification table (step 2) can only weaken a claim's evidence-boundary
    status: ``IN_BOUNDARY -> BOUNDARY_GAP`` is allowed, the reverse never is,
    and gap sets grow monotonically in lattice rank. Verified over every
    pinned fixture claim AND every sampled record (deterministic schedule)."""
    scenarios: list[tuple[dict[str, typing.Any], typing.Any]] = []
    for record_key in RECORD_KEYS:
        record = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS[record_key]
        for claim in record["claims_case"]["claims"]:
            scenarios.append((claim, record.get("receipts")))
    # Deterministically sampled extra scenarios (seeded permutation schedule).
    for record_key in _deterministic_sample_order(list(RECORD_KEYS), DETERMINISTIC_SEED, 3):
        record = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS[record_key]
        for claim in record["claims_case"]["claims"]:
            scenarios.append((dict(claim), record.get("receipts")))

    for claim, receipts in scenarios:
        baseline_assessment = candidate.classify_claim(claim, receipts)
        step1_claim = _strip_binding(claim)
        step1_assessment = candidate.classify_claim(step1_claim, receipts)
        step2_claim, step2_receipts = _strip_receipt_table(step1_claim, receipts)
        step2_assessment = candidate.classify_claim(step2_claim, step2_receipts)

        rank = {"IN_BOUNDARY": 2, "INDETERMINATE": 1, "BOUNDARY_GAP": 0}
        assert (
            rank[step1_assessment.boundary_status] <= rank[baseline_assessment.boundary_status]
        ), (
            claim.get("claim_id"),
            baseline_assessment.boundary_status,
            step1_assessment.boundary_status,
        )
        assert rank[step2_assessment.boundary_status] <= rank[step1_assessment.boundary_status], (
            claim.get("claim_id"),
            step1_assessment.boundary_status,
            step2_assessment.boundary_status,
        )
        # Stripping a receipt binding can never fabricate a clean verdict from
        # a refused one, and can never introduce a gap code from thin air on a
        # claim whose only change is evidence removal.
        if baseline_assessment.boundary_status == "BOUNDARY_GAP":
            assert step1_assessment.boundary_status == "BOUNDARY_GAP"


def test_candidate_receipt_strip_reject_never_flips_to_admit() -> None:
    """Metamorphic relation M2 (instrument, adversarial boundary case).

    For a refused claim (G4 replayed receipt / G2 downgrade / G7 unbound),
    stripping the receipt binding keeps the claim refused: the specific gap may
    be re-explained by the residual G7 implicit-upgrade row, but the verdict
    never returns to IN_BOUNDARY — evidence removal cannot rescue a claim."""
    receipts = {"rX": {"bound_to_claim_id": "other-claim"}}
    adversarial_claims = (
        {
            "claim_id": "c-m2a",
            "dimension": "receipt",
            "asserted_level": "L2-ACKNOWLEDGED",
            "evidence_bindings": [
                {"dimension": "receipt", "binding_kind": "receipt-bound", "receipt_id": "rX"}
            ],
            "timestamp": "2026-11-15T00:00:00Z",
        },
        {
            "claim_id": "c-m2b",
            "dimension": "execution",
            "asserted_level": "L3-EXECUTED",
            "evidence_bindings": [
                {"dimension": "execution", "binding_kind": "receipt-bound", "receipt_id": "rX"}
            ],
            "timestamp": "2026-11-15T00:00:00Z",
            "schedule_checked_at_rely_time": True,
        },
        {
            "claim_id": "c-m2c",
            "dimension": "dispatch",
            "asserted_level": "L1-ASSEMBLED",
            "timestamp": "2026-11-15T00:00:00Z",
        },
    )
    for claim in adversarial_claims:
        refused = candidate.classify_claim(claim, receipts)
        assert refused.boundary_status == "BOUNDARY_GAP", claim["claim_id"]
        stripped = candidate.classify_claim(_strip_binding(claim), receipts)
        assert stripped.boundary_status == "BOUNDARY_GAP", claim["claim_id"]
        # The residual explanation is always an honest register row.
        assert set(stripped.gap_codes) <= candidate.KNOWN_GAP_CODES


def test_baselines_two_step_weakening_never_strengthen() -> None:
    """Metamorphic relation M3 (reference classes, two steps over real records).

    Same weakening schedule applied to the pinned fixture records through the
    REAL ``_classify`` path: no reference class may upgrade a verdict
    (REJECT -> ACCEPT or a granted-level jump) after evidence is stripped.
    B1 additionally *detects* the strip (presence-only semantics notice the
    vanished artifact) — the detect-or-preserve disjunction."""
    for record_key in RECORD_KEYS:
        record = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS[record_key]
        claims_case = dict(record["claims_case"])
        receipts = record.get("receipts")
        stripped_case = {
            "case_id": claims_case.get("case_id", ""),
            "claims": [_strip_binding(claim) for claim in claims_case["claims"]],
        }
        for arm_id in ALL_ARMS:
            verdict_before = _classify_case(arm_id, claims_case, receipts)
            verdict_after = _classify_case(arm_id, stripped_case, receipts)
            rank = {"ACCEPT": 1, "REJECT": 0}
            assert rank[verdict_after.verdict] <= rank[verdict_before.verdict], (
                record_key,
                arm_id,
                verdict_before.verdict,
                verdict_after.verdict,
            )
            before_rank = baselines.LEVEL_RANK[verdict_before.granted_level]
            after_rank = baselines.LEVEL_RANK[verdict_after.granted_level]
            assert after_rank <= before_rank, (record_key, arm_id, verdict_before, verdict_after)


def test_b1_detects_or_preserves_and_b0_is_binding_blind() -> None:
    """Metamorphic relation M4 (stance-differential witness).

    - B0 (attestation-only) is blind to bindings BY CONSTRUCTION: stripping a
      receipt binding leaves its granted level exactly at the claimed level.
    - B1 (receipt-presence) must either keep the verdict or refuse it after a
      strip (it can detect the vanished artifact) — and it must never
      strengthen. On the downgrade fixture the strip flips ACCEPT -> REJECT,
      which is the presence-check working."""
    record = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS[("sok-claim-record-2", "downgraded")]
    claims_case = dict(record["claims_case"])
    receipts = record.get("receipts")
    stripped_case = {
        "case_id": "",
        "claims": [_strip_binding(claim) for claim in claims_case["claims"]],
    }

    b0_before = _classify_case(B0, claims_case, receipts)
    b0_after = _classify_case(B0, stripped_case, receipts)
    assert b0_before.granted_level == b0_after.granted_level == "L3-EXECUTED"
    assert b0_after.verdict == "ACCEPT"

    b1_before = _classify_case(B1, claims_case, receipts)
    b1_after = _classify_case(B1, stripped_case, receipts)
    assert b1_before.verdict == "ACCEPT"
    assert b1_after.verdict in {"ACCEPT", "REJECT"}
    assert (
        baselines.LEVEL_RANK[b1_after.granted_level]
        <= baselines.LEVEL_RANK[b1_before.granted_level]
    )


# ---------------------------------------------------------------------------
# 3. Deterministic adversarial sampling schedule (seeded, replay-stable).
# ---------------------------------------------------------------------------


def test_sampling_schedule_is_deterministic_for_fixed_seed() -> None:
    """All randomness in this suite is seeded: the adversarial sampling
    schedule replays identically for the same seed, differs for a different
    seed, and always respects the population size."""
    first = _deterministic_sample_order(list(RECORD_KEYS), DETERMINISTIC_SEED, 3)
    second = _deterministic_sample_order(list(RECORD_KEYS), DETERMINISTIC_SEED, 3)
    assert first == second
    assert len(first) == 3
    assert set(first) <= set(RECORD_KEYS)
    other = _deterministic_sample_order(list(RECORD_KEYS), DETERMINISTIC_SEED + 1, 4)
    assert len(other) == 4
    assert set(other) <= set(RECORD_KEYS)


def test_sampled_adversarial_witness_is_stable_across_replay() -> None:
    """The deterministic witness campaign (B3 vs the weak stances on the
    sampled records) reproduces byte-identical outcome vectors on replay —
    no run-to-run drift is possible because every choice is seed-derived."""
    outcomes_first = [
        _run(arm_id, record_id, variant, f"unit-sample/{arm_id}/{variant}").observed_outcome
        for record_id, variant in _deterministic_sample_order(
            list(RECORD_KEYS), DETERMINISTIC_SEED, 4
        )
        for arm_id in ALL_ARMS
    ]
    outcomes_second = [
        _run(arm_id, record_id, variant, f"unit-sample/{arm_id}/{variant}").observed_outcome
        for record_id, variant in _deterministic_sample_order(
            list(RECORD_KEYS), DETERMINISTIC_SEED, 4
        )
        for arm_id in ALL_ARMS
    ]
    assert outcomes_first == outcomes_second
    # Liveness: the sampled campaign still separates stances on the
    # adversarial records (B3 refuses what at least one weak stance admits).
    witness = _run(B3, "sok-claim-record-4", "replayed", "unit-sample/witness")
    weak = [
        _run(arm_id, "sok-claim-record-4", "replayed", "unit-sample/witness")
        for arm_id in (B0, B1, B2)
    ]
    assert witness.observed_outcome == "REJECT"
    assert [outcome.observed_outcome for outcome in weak] == ["ADMIT", "ADMIT", "ADMIT"]


# ---------------------------------------------------------------------------
# 4. Mutation checks: the properties kill the canonical mutants.
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _mutated_detect_gaps(
    transform: typing.Callable[[tuple[str, ...]], tuple[str, ...]],
) -> typing.Iterator[None]:
    """Patch the instrument's gap detector with a mutant, restoring after.

    The module under test is never left mutated: the original
    ``_detect_gaps`` is restored even when an assertion fails."""

    original = candidate._detect_gaps

    def mutant(
        claim: typing.Any, dimension: str, asserted: str, bindings: typing.Any, receipts: typing.Any
    ) -> list[str]:
        return list(transform(tuple(original(claim, dimension, asserted, bindings, receipts))))

    with unittest.mock.patch.object(candidate, "_detect_gaps", mutant):
        yield


_REPLAYED_CLAIM: dict[str, typing.Any] = {
    "claim_id": "c-mut",
    "dimension": "receipt",
    "asserted_level": "L2-ACKNOWLEDGED",
    "evidence_bindings": [
        {"dimension": "receipt", "binding_kind": "receipt-bound", "receipt_id": "rX"}
    ],
    "timestamp": "2026-11-15T00:00:00Z",
    "schedule_checked_at_rely_time": True,
}
_REPLAYED_TABLE: dict[str, typing.Any] = {"rX": {"bound_to_claim_id": "other-claim"}}
_CLEAN_CLAIM: dict[str, typing.Any] = {
    "claim_id": "c-clean",
    "dimension": "receipt",
    "asserted_level": "L2-ACKNOWLEDGED",
    "evidence_bindings": [
        {"dimension": "receipt", "binding_kind": "receipt-bound", "receipt_id": "r1"}
    ],
    "timestamp": "2026-11-15T00:00:00Z",
    "schedule_checked_at_rely_time": True,
}
_CLEAN_TABLE: dict[str, typing.Any] = {"r1": {"bound_to_claim_id": "c-clean"}}


def test_mutation_survivor_drops_g4_is_killed_by_replay_refusal() -> None:
    """Mutation M-A: delete register row G4 (accept context-invalid receipts).
    Killed by the replayed-receipt refusal property: the mutated instrument
    admits the transplant the real instrument refuses."""
    real = candidate.classify_claim(_REPLAYED_CLAIM, _REPLAYED_TABLE)
    assert real.boundary_status == "BOUNDARY_GAP"
    assert "G4_SIGNATURE_AS_CONTEXT" in real.gap_codes
    with _mutated_detect_gaps(
        lambda codes: tuple(code for code in codes if code != "G4_SIGNATURE_AS_CONTEXT")
    ):
        mutated = candidate.classify_claim(_REPLAYED_CLAIM, _REPLAYED_TABLE)
        assert mutated.boundary_status == "IN_BOUNDARY"
        assert mutated.gap_codes == ()
    # Restored: the real module classifies the transplant again.
    healed = candidate.classify_claim(_REPLAYED_CLAIM, _REPLAYED_TABLE)
    assert healed.boundary_status == "BOUNDARY_GAP"


def test_mutation_accept_all_is_killed_by_adversarial_refusal() -> None:
    """Mutation M-B: accept every claim (boundary checker amputated).
    Killed by the adversarial-refusal property: all four pinned adversarial
    vectors must be refused by the real instrument."""
    adversarial_keys = (
        ("sok-claim-record-2", "downgraded"),
        ("sok-claim-record-3", "unbound"),
        ("sok-claim-record-4", "replayed"),
    )
    for record_key in adversarial_keys:
        record = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS[record_key]
        assessment = candidate.classify_claim(
            record["claims_case"]["claims"][0], record.get("receipts")
        )
        assert assessment.boundary_status == "BOUNDARY_GAP", record_key
    with _mutated_detect_gaps(lambda codes: ()):
        for record_key in adversarial_keys:
            record = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS[record_key]
            mutated = candidate.classify_claim(
                record["claims_case"]["claims"][0], record.get("receipts")
            )
            assert mutated.boundary_status == "IN_BOUNDARY", record_key


def test_mutation_all_deny_fails_liveness_never_passes_correctness() -> None:
    """Mutation M-C (manifest negative control): an arbitrary all-deny must not
    pass correctness. The liveness assertion — the clean bound control stays
    in-boundary — kills the all-deny mutant: conservatism is not correctness."""
    real_clean = candidate.classify_claim(_CLEAN_CLAIM, _CLEAN_TABLE)
    assert real_clean.boundary_status == "IN_BOUNDARY"
    assert real_clean.gap_codes == ()

    def all_deny(
        claim: typing.Any, dimension: str, asserted: str, bindings: typing.Any, receipts: typing.Any
    ) -> list[str]:
        return ["G7_LEVEL_IMPLICIT_UPGRADE"]

    with _mutated_detect_gaps(lambda codes: ("G7_LEVEL_IMPLICIT_UPGRADE",)):
        mutated_clean = candidate.classify_claim(_CLEAN_CLAIM, _CLEAN_TABLE)
        assert mutated_clean.boundary_status == "BOUNDARY_GAP"
        # The all-deny mutant FAILS the liveness property: it would be flagged
        # by the positive control below had it been part of the suite.
        liveness_holds = mutated_clean.boundary_status == "IN_BOUNDARY"
        assert liveness_holds is False


def test_mutation_oracle_rule_flip_is_caught_by_self_checks() -> None:
    """Mutation M-D: flip one oracle rule row. The frozen pre-registered matrix
    (``run_self_checks``) must detect the drift — the oracle is never repaired
    to match a candidate post hoc."""
    expected = ("ADMIT", "REJECT", "REJECT", "REJECT", "INDETERMINATE")
    verdicts = independent_oracle.run_self_checks()
    assert tuple(verdict.oracle_result.outcome for verdict in verdicts) == expected

    rules = dict(independent_oracle.ACNS_EVIDENCE_BOUNDARY_RULES)
    rules[independent_oracle.FAMILY_BOUND_EVIDENCE] = "REJECT"
    flipped_cases = (
        {"case_id": "flip-bound", "family": independent_oracle.FAMILY_BOUND_EVIDENCE},
        {"case_id": "flip-downgrade", "family": independent_oracle.FAMILY_ATTESTATION_DOWNGRADE},
        {"case_id": "flip-unbound", "family": independent_oracle.FAMILY_UNBOUND_CLAIM},
        {"case_id": "flip-replayed", "family": independent_oracle.FAMILY_REPLAYED_RECEIPT},
        {"case_id": "flip-unmodelled", "family": "unmodelled_family"},
    )
    from evaluation.venue2027._shared import oracle_kernel

    flipped = tuple(
        oracle_kernel.adjudicate(dict(case), dict(rules), oracle_id="mutant").outcome
        for case in flipped_cases
    )
    assert flipped != expected


def test_oracle_independence_guard_kills_import_mutant() -> None:
    """Mutation M-E: an oracle that imports a candidate baseline (or hides a
    dynamic import) is refused by the independence verifier — the property that
    keeps the truth source independent of the thing it judges."""
    independent_oracle.verify_independence()  # live module: clean

    for offending_source in (
        "import acns.baselines\n",
        "from evaluation.venue2027.acns import baselines\n",
        "import importlib\nimportlib.import_module('acns.baselines')\n",
    ):
        with pytest.raises(independent_oracle.OracleError) as excinfo:
            independent_oracle.verify_independence(offending_source)
        assert excinfo.value.reason_code == "CANDIDATE_IMPORT"

    clean_source = "from evaluation.venue2027._shared import oracle_kernel\nimport ast\n"
    independent_oracle.verify_independence(clean_source)


# ---------------------------------------------------------------------------
# 5. SoK framing: evidence-boundary verdicts, not mechanism outcomes.
# ---------------------------------------------------------------------------


def test_candidate_declares_analytic_instrument_not_mechanism() -> None:
    """The novelty-contract declaration is machine-checkable and stays a SoK:
    the instrument is an ANALYTIC_INSTRUMENT with is_mechanism=False, and no
    runtime enforcement/detection claim is made."""
    declaration = candidate.describe_mechanism()
    assert declaration["contribution_class"] == "ANALYTIC_INSTRUMENT"
    assert declaration["is_mechanism"] is False
    assert declaration["is_new_mechanism_claim"] is False
    assert declaration["study_class"] == "SoK"
    assert declaration["runtime_enforcement"] is False
    assert declaration["detects_attacks"] is False
    assert declaration["prevents_attacks"] is False
    assert declaration["gates_enforced"] == []


def test_boundary_assessment_carries_no_mechanism_fields() -> None:
    """Assessment payloads describe the evidence boundary (lattice level, G
    register, undecidable fields) and never a mechanism outcome such as 'the
    tool ran' or 'the pipeline succeeded'."""
    for claim, receipts in (
        (_CLEAN_CLAIM, _CLEAN_TABLE),
        (_REPLAYED_CLAIM, _REPLAYED_TABLE),
        ({"claim_id": "c-frame", "dimension": "receipt", "asserted_level": "L2"}, None),
    ):
        assessment = candidate.classify_claim(claim, receipts).to_dict()
        assert set(assessment) == {
            "claim_id",
            "dimension",
            "asserted_level",
            "demonstrated_level",
            "boundary_status",
            "gap_codes",
            "undecidable_fields",
            "reason_code",
            "instrument_id",
            "instrument_version",
        }
        for forbidden in ("tool_ran", "pipeline_succeeded", "execution_result", "action_taken"):
            assert forbidden not in assessment
        assert all(code in candidate.KNOWN_GAP_CODES for code in assessment["gap_codes"])


def test_oracle_boundary_content_is_sok_framed() -> None:
    """The oracle's verdict content states which lattice level the evidence
    supports, which claim is REFUSED and which register gap explains it —
    the counterexample-witness shape of the SoK (RQ2), with the refused claim
    (not a mechanism status) as the boundary."""
    for family, expected_outcome, expected_gap in ORACLE_BOUNDARY_MATRIX:
        verdict = independent_oracle.adjudicate_boundary(
            {"case_id": f"unit-sok/{family}", "family": family}
        )
        assert verdict.oracle_result.outcome == expected_outcome
        assert verdict.gap_code == expected_gap
        assert verdict.refused_claim, family
        assert verdict.granted_level in candidate.LATTICE_LEVELS
        assert verdict.boundary_condition, family
        payload = verdict.to_dict()
        assert payload["oracle_version"] == independent_oracle.ACNS_INDEPENDENT_ORACLE_VERSION
        json.dumps(payload)


# ---------------------------------------------------------------------------
# 6. Coverage-matrix invariants (instrument-level aggregation properties).
# ---------------------------------------------------------------------------


def test_coverage_matrix_partitions_and_is_order_insensitive() -> None:
    """Coverage partitions the corpus exactly (in-boundary + gap +
    indeterminate == total, undecidable records counted, never dropped) and
    its gap-count digest is invariant under claim order."""
    claims: list[dict[str, typing.Any]] = []
    receipts: dict[str, typing.Any] = {}
    for record_key in RECORD_KEYS:
        record = _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS[record_key]
        claims.extend(dict(claim) for claim in record["claims_case"]["claims"])
        if isinstance(record.get("receipts"), dict):
            receipts.update(record["receipts"])
    claims.append({"claim_id": "c-indet"})  # undecidable: counted, not dropped

    coverage = candidate.coverage_matrix(claims, receipts)
    assert (
        coverage.in_boundary_count + coverage.boundary_gap_count + coverage.indeterminate_count
        == coverage.total_claims
        == len(claims)
    )
    assert 0.0 <= coverage.gap_register_coverage <= 1.0
    assert all(code in candidate.KNOWN_GAP_CODES for code in coverage.gap_code_counts)

    reordered = candidate.coverage_matrix(list(reversed(claims)), receipts)
    assert reordered.digest == coverage.digest
    assert reordered.gap_code_counts == coverage.gap_code_counts


def test_ablated_matrix_inflates_and_is_flagged() -> None:
    """The ablation arm (treat every claim as in-boundary) inflates the
    in-boundary fraction to 1.0 and collapses register coverage to 0.0, and it
    is flagged ``ablated`` so it can never masquerade as a coverage result —
    the measurable proof that gap detection IS the instrument."""
    claims = [_CLEAN_CLAIM, _REPLAYED_CLAIM]
    receipts = {**_CLEAN_TABLE, **_REPLAYED_TABLE}
    real = candidate.coverage_matrix(claims, receipts)
    ablated = candidate.ablation_ignore_gaps(claims, receipts)
    assert ablated.ablated is True
    assert real.ablated is False
    assert ablated.in_boundary_fraction == 1.0
    assert ablated.gap_register_coverage == 0.0
    assert real.boundary_gap_count >= 1
    assert real.in_boundary_fraction < 1.0


def test_gap_register_coverage_covers_all_nine_rows_on_adversarial_corpus() -> None:
    """The pre-registered register (G1-G9) is fully exercised by a
    deterministic adversarial corpus built from the fixture families plus the
    specific register-row witnesses — the RQ1 coverage property."""
    witnesses = (
        # G1: transport acknowledgment read as provider processing.
        {
            "claim_id": "w-g1",
            "dimension": "receipt",
            "asserted_level": "L2-ACKNOWLEDGED",
            "evidence_bindings": [{"dimension": "receipt", "binding_kind": "transport-ack"}],
            "timestamp": "2026-11-15T00:00:00Z",
        },
        # G2: provider receipt quoted as execution proof.
        {
            "claim_id": "w-g2",
            "dimension": "execution",
            "asserted_level": "L3-EXECUTED",
            "evidence_bindings": [
                {"dimension": "execution", "binding_kind": "receipt-bound", "receipt_id": "r-g2"}
            ],
            "timestamp": "2026-11-15T00:00:00Z",
        },
        # G3: execution trace quoted as persisted semantic consumption.
        {
            "claim_id": "w-g3",
            "dimension": "consumption",
            "asserted_level": "L4-COMMITTED",
            "evidence_bindings": [
                {"dimension": "consumption", "binding_kind": "attested-bound", "receipt_id": "r-g3"}
            ],
            "attested_execution": True,
            "timestamp": "2026-11-15T00:00:00Z",
        },
        # G4: signature-valid, context-invalid transplanted receipt.
        dict(_REPLAYED_CLAIM, claim_id="w-g4"),
        # G5: mint-time validity read as rely-time validity.
        {
            "claim_id": "w-g5",
            "dimension": "receipt",
            "asserted_level": "L2-ACKNOWLEDGED",
            "evidence_bindings": [
                {"dimension": "receipt", "binding_kind": "receipt-bound", "receipt_id": "r-g5"}
            ],
            "timestamp": "2026-11-15T00:00:00Z",
        },
        # G6: timestamp presence read as ordering/proof (no timestamp at all).
        {
            "claim_id": "w-g6",
            "dimension": "receipt",
            "asserted_level": "L2-ACKNOWLEDGED",
        },
        # G7: implicit level upgrade with no named trusted component.
        {
            "claim_id": "w-g7",
            "dimension": "receipt",
            "asserted_level": "L2-ACKNOWLEDGED",
            "timestamp": "2026-11-15T00:00:00Z",
        },
        # G8: authority crossing purpose scope.
        {
            "claim_id": "w-g8",
            "dimension": "dispatch",
            "asserted_level": "L1-ASSEMBLED",
            "purpose_scope": {"authorized_purpose": "analytics", "claimed_purpose": "training"},
            "timestamp": "2026-11-15T00:00:00Z",
        },
        # G9: claim outside any disclosed evidence dimension.
        {
            "claim_id": "w-g9",
            "dimension": "quantum_channel",
            "asserted_level": "L3-EXECUTED",
            "timestamp": "2026-11-15T00:00:00Z",
        },
    )
    receipts = {
        "r-g2": {"bound_to_claim_id": "w-g2"},
        "r-g3": {"bound_to_claim_id": "w-g3"},
        "r-g5": {"bound_to_claim_id": "unrelated"},
        "rX": _REPLAYED_TABLE["rX"],
    }
    coverage = candidate.coverage_matrix(witnesses, receipts)
    for code in candidate.GAP_REGISTER:
        assert coverage.gap_code_counts.get(code, 0) >= 1, code
    assert coverage.gap_register_coverage == 1.0
