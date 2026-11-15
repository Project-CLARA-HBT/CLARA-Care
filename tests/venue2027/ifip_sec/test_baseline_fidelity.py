"""Baseline conformance suite for IFIP_SEC-baseline_tests (phase P03).

Purpose
-------
One UPSTREAM POSITIVE vector and one ADVERSARIAL NEGATIVE vector for EACH
implemented ``ifip_sec`` baseline arm in
``evaluation/venue2027/ifip_sec/baselines.py`` (BASELINES_VERSION 1.1.0),
imported as the REAL module — never a reimplementation, stub or toy
substitution (execution contract rule 8):

- ``B0``  bearer-signed-receipt (weak control; registry
          ``bearer-signed-receipt``) — HMAC-signed bearer token, signature +
          expiry only.
- ``B1``  stateless purpose binding (registry ``macaroon-hmac-caveats``) —
          pointwise claim binding (purpose/tenant/actor/epochs), nonce
          checked for form only, never consumed.
- ``B2``  capability/macaron-style HMAC caveat chain (registry
          ``zanzibar-openfga`` in-process row) — real ``hmac``/``hashlib``
          attenuation chain over ``CAVEAT_KEYS`` (actor, purpose, task,
          expiry, nonce, parent), pointwise satisfaction at presentation.
- ``B3``  nonce-store replay rejection (registry
          ``cedar-opa-policy-decision-nonce-registry``) — real injected
          consume-once set.
- ``B2_INPROCESS_ZANZIBAR`` (task IFIP_SEC-X06 additive row; published
          Zanzibar Sec. 2.3-2.4 snapshot semantics) — driven through
          ``run_baseline`` with the injected :class:`ZanzibarStore` and a
          zookie under the task contract
          ``check_with_revision(principal, resource, token) -> Verdict``.

Allowed input
-------------
Synthetic, deterministic cases built from ``synthetic_case`` /
``issue_token`` / ``build_caveat_chain`` with the injected
:class:`BaselineContext` (fixed HMAC key, frozen clock, explicit nonce
store). No network, no database, no hidden clock or randomness, no PII, no
provider calls — pure in-process reference behaviour.

Positive vectors assert the documented guarantee of each arm on the
canonical legitimate upstream scenario (valid receipt ADMITs). Negative
vectors assert the declared behaviour under the blueprint replay attack:
B3 and the fresh-token Zanzibar arm REJECT the replay with their stable
reason codes, while B0, B1 and B2 — per their PUBLISHED, faithful
semantics — ADMIT the replay within validity. Those honest weaknesses are
asserted explicitly (never hidden, never silently converted into
rejections) because they are the RQ1 measurement signal the study exists
to quantify. Wiring errors still raise :class:`BaselineError`; arm faults
are always first-class ``Outcome`` values with stable uppercase reason
codes, never unhandled exceptions miscounted as safe rejections.

Failure semantics
-----------------
Any assertion failure fails the vector loudly. A baseline whose behaviour
drifts from its declared semantics (e.g. B3 accepting a replay, or a
tampered B2 caveat verifying) blocks the experiment per the task's
negative-control contract ("known spec example mismatch -> block
experiment").

Version
-------
``BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"``
"""

from __future__ import annotations

import base64
import json
import pathlib
import sys

import pytest

BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.venue2027._shared.harness import Outcome  # noqa: E402
from evaluation.venue2027.ifip_sec.baselines import (  # noqa: E402
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B2_INPROCESS_ZANZIBAR,
    BASELINE_B3,
    BASELINE_REGISTRY,
    BASELINES_VERSION,
    RC_CAVEAT_VERIFICATION_FAILED,
    RC_NONCE_REPLAYED,
    RC_TOKEN_EXPIRED,
    BaselineContext,
    BaselineError,
    ZanzibarStore,
    build_caveat_chain,
    claims_from_case,
    issue_token,
    run_baseline,
    synthetic_case,
)  # noqa: E402
from evaluation.venue2027.ifip_sec.consistency_token_adapter import (  # noqa: E402
    RC_RELATION_PRESENT,
    RC_RELATION_REVOKED,
)

#: Injected HMAC key (>= 16 bytes; synthetic test material, not a secret).
KEY = b"ifip-sec-fidelity-suite-key-0123456789abcdef"
#: Frozen verification clock (no hidden time reads anywhere in the suite).
NOW = 1_700_000_000
#: Fixed far-future expiry shared by every valid fixture.
EXPIRY = 4_102_444_800


def _ctx(nonce_store: set[str] | None = None) -> BaselineContext:
    return BaselineContext(hmac_key=KEY, nonce_store=nonce_store, now_epoch_seconds=NOW)


def _signed_case(**overrides: object) -> dict[str, object]:
    """Deterministic legitimate receipt: case + HMAC-signed token."""
    case = synthetic_case(expiry=EXPIRY, **overrides)  # type: ignore[arg-type]
    case["token"] = issue_token(claims_from_case(case), _ctx())
    return case


def _caveat_case() -> tuple[dict[str, object], dict[str, str]]:
    """Deterministic legitimate B2 fixture: full caveat set + honest signature."""
    case = synthetic_case(expiry=EXPIRY)
    caveats: dict[str, str] = {
        "actor": str(case["actor_id"]),
        "purpose": str(case["purpose"]),
        "task": str(case["task_id"]),
        "expiry": str(EXPIRY),
        "nonce": str(case["nonce"]),
        "parent": str(case["parent_ref"]),
    }
    case["caveats"] = caveats
    case["caveat_signature"] = build_caveat_chain(caveats, _ctx())
    return case, caveats


# ---------------------------------------------------------------------------
# 1. B0 — bearer-signed-receipt (weak control).
# ---------------------------------------------------------------------------


class TestB0BearerSignedReceipt:
    def test_positive_valid_signed_receipt_is_admitted(self) -> None:
        """Upstream positive: a correctly HMAC-signed, unexpired bearer
        receipt runs end to end and is ADMITted (the weak control's only
        documented guarantee: signature + expiry hold)."""
        assert BASELINE_REGISTRY[BASELINE_B0].runnable_in_process is True
        outcome = run_baseline(BASELINE_B0, _signed_case(), _ctx())
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True
        assert outcome.detail == "BEARER_SIGNATURE_VALID"

    def test_negative_expired_bearer_receipt_is_rejected(self) -> None:
        """Adversarial negative: an expired bearer receipt is REJECTed with
        TOKEN_EXPIRED — the expiry half of B0's declared check."""
        stale = synthetic_case(expiry=NOW - 10)
        stale["token"] = issue_token(claims_from_case(stale), _ctx())
        outcome = run_baseline(BASELINE_B0, stale, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_TOKEN_EXPIRED

    def test_honest_weakness_bearer_replay_is_admitted(self) -> None:
        """Asserted honest weakness (RQ1 lower bound, never hidden): the same
        valid bearer receipt replays successfully — B0 has no caveat binding
        and no consume-once state, so the replay is ADMITted. This is the
        scientifically correct behaviour of the weak control; a "fix" here
        would falsify the baseline."""
        case = _signed_case()
        assert run_baseline(BASELINE_B0, case, _ctx()).observed_outcome == "ADMIT"
        replay = run_baseline(BASELINE_B0, case, _ctx())
        assert replay.observed_outcome == "ADMIT"
        assert replay.detail == "BEARER_SIGNATURE_VALID"


# ---------------------------------------------------------------------------
# 2. B1 — stateless purpose binding (pointwise caveats, no replay closure).
# ---------------------------------------------------------------------------


class TestB1StatelessPurposeBinding:
    def test_positive_matching_purpose_binding_is_admitted(self) -> None:
        """Upstream positive: a receipt whose purpose/tenant/actor/epoch
        claims all match the request context is ADMITted
        (PURPOSE_BOUND_STATELESS) — the arm's documented guarantee."""
        assert BASELINE_REGISTRY[BASELINE_B1].runnable_in_process is True
        outcome = run_baseline(BASELINE_B1, _signed_case(), _ctx())
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == "PURPOSE_BOUND_STATELESS"

    def test_negative_purpose_mismatch_is_rejected(self) -> None:
        """Adversarial negative: a request context that disagrees with the
        receipt's purpose claim is REJECTed with PURPOSE_MISMATCH (and a
        forged claim mutation is caught by the HMAC signature check)."""
        # (a) honest signed receipt presented for a different purpose.
        case = _signed_case(purpose="research_secondary")
        case["purpose"] = "self_care"  # attacker-changed request context
        outcome = run_baseline(BASELINE_B1, case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == "PURPOSE_MISMATCH"
        # (b) attacker mutates the claim itself: signature breaks fail-closed.
        forged = _signed_case()
        payload = json.loads(
            base64.urlsafe_b64decode(str(forged["token"]) + "=" * (-len(str(forged["token"])) % 4))
        )
        payload["claims"]["purpose"] = "evil-purpose"
        forged["token"] = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        outcome = run_baseline(BASELINE_B1, forged, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == "TOKEN_SIGNATURE_INVALID"

    def test_honest_weakness_stateless_replay_within_expiry_is_admitted(self) -> None:
        """Asserted honest weakness (published Macaroon-style stateless
        per-presentation semantics): the nonce caveat is satisfied by form
        only and NEVER consumed, so the identical valid receipt replays
        successfully within expiry even though a nonce store was available."""
        store: set[str] = {"nonce-0001"}
        case = _signed_case()
        first = run_baseline(BASELINE_B1, case, _ctx(store))
        replay = run_baseline(BASELINE_B1, case, _ctx(store))
        assert first.observed_outcome == "ADMIT"
        assert replay.observed_outcome == "ADMIT"
        assert replay.detail == "PURPOSE_BOUND_STATELESS"
        assert store == {"nonce-0001"}, "B1 must NOT consume the nonce (stateless arm)"


# ---------------------------------------------------------------------------
# 3. B2 — capability/macaron-style HMAC caveat chain (real crypto).
# ---------------------------------------------------------------------------


class TestB2MacaroonCaveatChain:
    def test_positive_valid_caveat_chain_is_admitted(self) -> None:
        """Upstream positive: a real HMAC attenuation chain over the full
        CAVEAT_KEYS set verifies end to end and is ADMITted
        (CAVEAT_CHAIN_VALID) — the published Macaroons construction."""
        assert BASELINE_REGISTRY[BASELINE_B2].runnable_in_process is True
        case, _caveats = _caveat_case()
        outcome = run_baseline(BASELINE_B2, case, _ctx())
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == "CAVEAT_CHAIN_VALID"

    def test_negative_tampered_caveat_byte_fails_chain(self) -> None:
        """Adversarial negative: flipping a single caveat byte (purpose)
        against the honest signature breaks the chain; the arm REJECTs with
        CAVEAT_VERIFICATION_FAILED (byte binding holds)."""
        case, caveats = _caveat_case()
        tampered = dict(caveats)
        tampered["purpose"] = "research_secondary"  # attacker flips one caveat
        case["caveats"] = tampered
        outcome = run_baseline(BASELINE_B2, case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_CAVEAT_VERIFICATION_FAILED

    def test_honest_weakness_replay_within_expiry_is_admitted(self) -> None:
        """Asserted honest weakness (published pointwise-satisfaction
        semantics): caveat satisfaction is checked per presentation and the
        nonce caveat is never consumed, so the identical valid capability
        replays successfully within expiry — exactly the strong-token
        baseline gap the candidate must beat (RQ1)."""
        case, _caveats = _caveat_case()
        first = run_baseline(BASELINE_B2, case, _ctx({"nonce-0001"}))
        replay = run_baseline(BASELINE_B2, case, _ctx({"nonce-0001"}))
        assert first.observed_outcome == "ADMIT"
        assert replay.observed_outcome == "ADMIT"
        assert replay.detail == "CAVEAT_CHAIN_VALID"


# ---------------------------------------------------------------------------
# 4. B3 — nonce-store replay rejection (consume-once set).
# ---------------------------------------------------------------------------


class TestB3NonceStoreReplayRejection:
    def test_positive_first_presentation_consumes_nonce_and_admits(self) -> None:
        """Upstream positive: the first presentation of a valid receipt
        atomically consumes its nonce and ADMITs (NONCE_CONSUMED_ONCE); the
        injected consume-once store is really mutated."""
        assert BASELINE_REGISTRY[BASELINE_B3].runnable_in_process is True
        store: set[str] = {"nonce-0001"}
        outcome = run_baseline(BASELINE_B3, _signed_case(), _ctx(store))
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == "NONCE_CONSUMED_ONCE"
        assert store == set(), "consume-once store must really be mutated"

    def test_negative_replayed_nonce_is_rejected(self) -> None:
        """Adversarial negative: the SECOND presentation of the same receipt
        finds the nonce already consumed and is REJECTed with
        NONCE_REPLAYED — the consume-once guarantee (the paired B0-vs-B3
        divergence is asserted: identical replay, opposite decisions)."""
        case = _signed_case()
        b0_first = run_baseline(BASELINE_B0, case, _ctx())
        b0_replay = run_baseline(BASELINE_B0, case, _ctx())
        assert (b0_first.observed_outcome, b0_replay.observed_outcome) == ("ADMIT", "ADMIT")
        store: set[str] = {str(case["nonce"])}
        b3_first = run_baseline(BASELINE_B3, case, _ctx(store))
        b3_replay = run_baseline(BASELINE_B3, case, _ctx(store))
        assert b3_first.observed_outcome == "ADMIT"
        assert b3_replay.observed_outcome == "REJECT"
        assert b3_replay.detail == RC_NONCE_REPLAYED


# ---------------------------------------------------------------------------
# 5. B2_INPROCESS_ZANZIBAR — consistency-token reference (task X06 row).
# ---------------------------------------------------------------------------


class TestB2InprocessZanzibar:
    def test_positive_fresh_token_sees_granted_relation(self) -> None:
        """Upstream positive (published Zanzibar snapshot semantics): a
        FRESH zookie evaluates at the current head revision, so a
        just-granted relation is visible and the check ADMITs with
        RELATION_PRESENT."""
        assert BASELINE_REGISTRY[BASELINE_B2_INPROCESS_ZANZIBAR].runnable_in_process is True
        store = ZanzibarStore(store_id="fidelity-fresh", hmac_key=KEY)
        store.write("document:case7", "viewer", "alice")
        case = {
            "case_id": "IFIP_SEC-FIDELITY-ZAN-01",
            "zanzibar_store": store,
            "principal": "alice",
            "resource": "document:case7",
            "zookie": store.issue_token(),
        }
        outcome = run_baseline(BASELINE_B2_INPROCESS_ZANZIBAR, case, _ctx())
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == RC_RELATION_PRESENT

    def test_negative_replayed_request_rejected_under_fresh_token(self) -> None:
        """Adversarial negative: after the relation is revoked, a replayed
        pre-revocation request carrying a FRESH token evaluates the current
        snapshot and is REJECTed with RELATION_REVOKED — the strong
        consistency guarantee."""
        store = ZanzibarStore(store_id="fidelity-revoke", hmac_key=KEY)
        store.write("document:case7", "viewer", "alice")
        store.delete("document:case7", "viewer", "alice")
        case = {
            "case_id": "IFIP_SEC-FIDELITY-ZAN-02",
            "zanzibar_store": store,
            "principal": "alice",
            "resource": "document:case7",
            "zookie": store.issue_token(),
        }
        outcome = run_baseline(BASELINE_B2_INPROCESS_ZANZIBAR, case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_RELATION_REVOKED

    def test_honest_weakness_stale_token_admits_replay_inside_window(self) -> None:
        """Asserted honest weakness (published bounded-staleness boundary,
        never hidden): the identical replay with the PRE-REVOCATION zookie
        evaluates the earlier snapshot and is ADMITted inside the
        bounded-staleness window — the RQ1 gap this comparator measures."""
        store = ZanzibarStore(store_id="fidelity-stale", hmac_key=KEY)
        store.write("document:case7", "viewer", "alice")
        pre_revoke_token = store.issue_token()
        store.delete("document:case7", "viewer", "alice")
        case = {
            "case_id": "IFIP_SEC-FIDELITY-ZAN-03",
            "zanzibar_store": store,
            "principal": "alice",
            "resource": "document:case7",
            "zookie": pre_revoke_token,
        }
        outcome = run_baseline(BASELINE_B2_INPROCESS_ZANZIBAR, case, _ctx())
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == RC_RELATION_PRESENT


# ---------------------------------------------------------------------------
# 6. Cross-arm conformance invariants (module wiring, fail-closed hygiene).
# ---------------------------------------------------------------------------


class TestModuleConformance:
    def test_real_module_version_and_registry_rows(self) -> None:
        """The suite runs against the REAL imported module (no reimplementation):
        version 1.1.0 and every implemented arm is runnable in-process with
        provenance rows; external pinned arms stay honestly NOT_RUN_EXTERNAL."""
        assert BASELINES_VERSION == "1.1.0"
        for arm in (
            BASELINE_B0,
            BASELINE_B1,
            BASELINE_B2,
            BASELINE_B3,
            BASELINE_B2_INPROCESS_ZANZIBAR,
        ):
            spec = BASELINE_REGISTRY[arm]
            assert spec.runnable_in_process is True, arm
            assert spec.registry_name and spec.upstream_url, arm
        outcome = run_baseline("B2_OPENFGA", _signed_case(), _ctx())
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.detail == "BASELINE_UNAVAILABLE"
        assert outcome.counted_as_success is False
        assert outcome.retriable is True

    def test_outcomes_are_first_class_never_raised(self) -> None:
        """Arm faults (missing/unparseable token) are first-class REJECT
        Outcomes with stable codes for every implemented arm — never unhandled
        exceptions miscounted as safe rejections."""
        for arm, missing_code in (
            (BASELINE_B0, "TOKEN_MISSING"),
            (BASELINE_B1, "TOKEN_MISSING"),
            (BASELINE_B2, "CAVEAT_VERIFICATION_FAILED"),
            (BASELINE_B3, "TOKEN_MISSING"),
        ):
            outcome = run_baseline(arm, {"case_id": "fidelity-edge"}, _ctx({"n1"}))
            assert isinstance(outcome, Outcome), arm
            assert outcome.observed_outcome == "REJECT", arm
            assert outcome.detail == missing_code, arm
        with pytest.raises(BaselineError) as excinfo:
            run_baseline(BASELINE_B3, _signed_case(), _ctx(None))
        assert excinfo.value.reason_code == "CONTEXT_STORE_MISSING"

    def test_external_pinned_arms_declared_in_registry(self) -> None:
        """The external pinned rows (OpenFGA server / Cedar PDP) remain
        declared with provenance and pinned revisions, so the fidelity suite
        never silently widens coverage beyond the in-process arms."""
        for external in ("B2_OPENFGA", "B3_CEDAR"):
            spec = BASELINE_REGISTRY[external]
            assert spec.runnable_in_process is False, external
            assert spec.upstream_revision and spec.upstream_url, external

    def test_suite_version_recorded(self) -> None:
        assert BASELINE_FIDELITY_TESTS_VERSION == "1.0.0"
