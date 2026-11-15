"""Tests for IFIP_SEC-baselines — baseline fidelity adapters.

Positive controls (each baseline runs end to end on synthetic cases):
- B0 bearer receipt: correctly signed, unexpired token is ACCEPTED end to end.
- B1 stateless purpose binding: matching purpose/tenant/actor/epoch claims
  are ACCEPTED; mismatched purpose/tenant are REJECTED with stable codes.
- B2 capability caveat chain: valid HMAC caveat chain verifies (parity
  round-trip succeeds); any tampered caveat byte fails verification.
- B3 nonce store: first presentation consumes the nonce and ADMITs; the
  consume-once set is really mutated.
- parity_check round-trips the macaroon construction (attenuate -> verify).

Adversarial controls:
- Unavailable external pinned arm -> NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE
  (never a toy substitution, never silently dropped from the denominator).
- Token-only B0 ACCEPTS a replayed request — the scientifically correct
  weakness this weak control exists to quantify (RQ1 lower bound), asserted
  explicitly rather than hidden.
- Tampered B2 caveat (purpose flipped, actor swapped, expiry rolled) is
  REJECTED with CAVEAT_VERIFICATION_FAILED.
- B3 rejects the replayed nonce with NONCE_REPLAYED (vs B0's acceptance).
- Unknown baseline id and short HMAC key fail closed with stable reason
  codes; constant-deny stubs are refused as baselines (STUB_PRESENTED_AS_
  BASELINE discipline from SH-baseline_registry): a registry entry declaring
  full-fidelity semantics must actually implement its declared decision
  semantics, which a constant-deny function does not.

Failure semantics: every adversarial result is a first-class Outcome, never
an unhandled exception miscounted as a safe rejection.
"""

from __future__ import annotations

import hashlib
import hmac

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.ifip_sec.baselines import (
    BASELINE_REGISTRY,
    BASELINES_VERSION,
    CAVEAT_KEYS,
    RC_BASELINE_UNAVAILABLE,
    RC_CAVEAT_VERIFICATION_FAILED,
    RC_CONTEXT_KEY_TOO_SHORT,
    RC_EPOCH_MISMATCH,
    RC_NONCE_MISSING,
    RC_NONCE_REPLAYED,
    RC_PARITY_OK,
    RC_PARITY_TAMPER_DETECTED,
    RC_PURPOSE_MISMATCH,
    RC_TENANT_MISMATCH,
    RC_TOKEN_SIGNATURE_INVALID,
    BaselineContext,
    BaselineError,
    build_caveat_chain,
    claims_from_case,
    issue_token,
    parity_check,
    run_baseline,
    synthetic_case,
    token_bytes,
    verify_caveat_chain,
)

KEY = b"ifip-sec-baselines-test-key-0123456789abcdef"
NOW = 1700000000
EXPIRY = 4102444800


def _ctx(nonce_store: set[str] | None = None) -> BaselineContext:
    return BaselineContext(
        hmac_key=KEY, nonce_store=nonce_store, now_epoch_seconds=NOW
    )


def _signed_case(**overrides: object) -> dict[str, object]:
    case = synthetic_case(**overrides)  # type: ignore[arg-type]
    case["expiry"] = EXPIRY
    claims = claims_from_case(case)
    case["token"] = issue_token(claims, _ctx())
    return case


# ---------------------------------------------------------------------------
# Positive controls — each baseline runs end to end.
# ---------------------------------------------------------------------------


class TestPositiveControls:
    def test_registry_covers_blueprint_arms(self) -> None:
        assert set(BASELINE_REGISTRY) >= {"B0", "B1", "B2", "B3", "B2_OPENFGA", "B3_CEDAR"}
        for spec in BASELINE_REGISTRY.values():
            assert spec.registry_name and spec.title and spec.upstream_url

    def test_b0_accepts_valid_signed_receipt(self) -> None:
        outcome = run_baseline("B0", _signed_case(), _ctx())
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True

    def test_b1_accepts_matching_purpose_binding(self) -> None:
        outcome = run_baseline("B1", _signed_case(), _ctx())
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == "PURPOSE_BOUND_STATELESS"

    def test_b1_rejects_purpose_mismatch(self) -> None:
        case = _signed_case(purpose="research_secondary")
        case["purpose"] = "self_care"  # request context differs from receipt
        outcome = run_baseline("B1", case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_PURPOSE_MISMATCH

    def test_b1_rejects_tenant_and_epoch_mismatch(self) -> None:
        tenant_case = _signed_case(tenant_id="tenant-B")
        tenant_case["tenant_id"] = "tenant-A"
        assert run_baseline("B1", tenant_case, _ctx()).detail == RC_TENANT_MISMATCH
        epoch_case = _signed_case(policy_epoch="epoch-9")
        epoch_case["policy_epoch"] = "epoch-7"
        assert run_baseline("B1", epoch_case, _ctx()).detail == RC_EPOCH_MISMATCH

    def test_b2_valid_caveat_chain_verifies_end_to_end(self) -> None:
        case = synthetic_case(expiry=EXPIRY)
        caveats = {
            "actor": case["actor_id"],
            "purpose": case["purpose"],
            "task": case["task_id"],
            "expiry": str(EXPIRY),
            "nonce": case["nonce"],
            "parent": case["parent_ref"],
        }
        case["caveats"] = caveats
        case["caveat_signature"] = build_caveat_chain(caveats, _ctx())
        outcome = run_baseline("B2", case, _ctx())
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == "CAVEAT_CHAIN_VALID"

    def test_b2_caveat_verify_direct_round_trip(self) -> None:
        caveats = {key: f"value-{key}" for key in CAVEAT_KEYS}
        signature = build_caveat_chain(caveats, _ctx())
        assert verify_caveat_chain(caveats, signature, _ctx()) is True

    def test_b3_first_presentation_consumes_nonce(self) -> None:
        store: set[str] = {"nonce-0001"}
        outcome = run_baseline("B3", _signed_case(), _ctx(store))
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == "NONCE_CONSUMED_ONCE"
        assert store == set(), "consume-once store must really be mutated"

    def test_parity_check_round_trip_succeeds(self) -> None:
        caveats = {
            "actor": "synthetic-actor",
            "purpose": "self_care",
            "task": "task-medication-review",
            "expiry": str(EXPIRY),
            "nonce": "nonce-parity",
            "parent": "root",
        }
        outcome = parity_check(caveats, _ctx())
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == RC_PARITY_OK

    def test_determinism_same_inputs_same_token(self) -> None:
        case = synthetic_case(expiry=EXPIRY)
        claims = claims_from_case(case)
        first = issue_token(claims, _ctx())
        second = issue_token(claims, _ctx())
        assert first == second
        assert token_bytes(first) > 0


# ---------------------------------------------------------------------------
# Adversarial controls.
# ---------------------------------------------------------------------------


class TestAdversarialControls:
    def test_unavailable_external_arm_is_not_run_external(self) -> None:
        outcome = run_baseline("B2_OPENFGA", _signed_case(), _ctx())
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False
        assert outcome.retriable is True
        assert outcome.detail == RC_BASELINE_UNAVAILABLE
        assert run_baseline("B3_CEDAR", _signed_case(), _ctx()).detail == (
            RC_BASELINE_UNAVAILABLE
        )

    def test_token_only_b0_accepts_replayed_request(self) -> None:
        """The scientifically correct weakness: B0 admits replay (RQ1 lower bound).

        The same signed receipt is presented twice for two different purposes;
        signature+expiry-only checking cannot tell the replay from the
        original, so B0 ACCEPTS the replayed request. Asserted explicitly as
        the measured weak-control behaviour — never hidden.
        """
        case_first = _signed_case(purpose="self_care")
        case_replay = _signed_case(purpose="self_care")
        assert run_baseline("B0", case_first, _ctx()).observed_outcome == "ADMIT"
        replay = run_baseline("B0", case_replay, _ctx())
        assert replay.observed_outcome == "ADMIT"
        # And even a cross-purpose reuse of the same signed token is admitted:
        cross = _signed_case()
        cross["purpose"] = "research_secondary"  # attacker-changed request context
        assert run_baseline("B0", cross, _ctx()).observed_outcome == "ADMIT"

    def test_b1_stateless_binding_admits_replay_within_expiry(self) -> None:
        """Faithful stateless semantics: form-only nonce check, no consume.

        B1 binds purpose correctly but never consumes the nonce, so the same
        valid receipt replays successfully within expiry — exactly the
        published pointwise-satisfaction gap the candidate must beat.
        """
        store_unused: set[str] = {"nonce-0001"}
        case = _signed_case()
        first = run_baseline("B1", case, _ctx(store_unused))
        second = run_baseline("B1", case, _ctx(store_unused))
        assert first.observed_outcome == "ADMIT"
        assert second.observed_outcome == "ADMIT"
        assert store_unused == {"nonce-0001"}, "B1 must NOT consume the nonce"

    def test_b2_tampered_purpose_caveat_fails_verification(self) -> None:
        case = synthetic_case(expiry=EXPIRY)
        caveats = {
            "actor": case["actor_id"],
            "purpose": "self_care",
            "task": case["task_id"],
            "expiry": str(EXPIRY),
            "nonce": case["nonce"],
            "parent": case["parent_ref"],
        }
        case["caveats"] = caveats
        case["caveat_signature"] = build_caveat_chain(caveats, _ctx())
        tampered = dict(caveats)
        tampered["purpose"] = "research_secondary"  # attacker flips one caveat
        case["caveats"] = tampered
        outcome = run_baseline("B2", case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_CAVEAT_VERIFICATION_FAILED

    def test_b2_tampered_actor_and_expiry_fail(self) -> None:
        caveats = {key: f"value-{key}" for key in CAVEAT_KEYS}
        signature = build_caveat_chain(caveats, _ctx())
        for key in ("actor", "expiry", "nonce", "parent"):
            tampered = dict(caveats)
            tampered[key] = f"evil-{key}"
            assert verify_caveat_chain(tampered, signature, _ctx()) is False, key

    def test_b2_tampered_signature_fails(self) -> None:
        caveats = {key: f"value-{key}" for key in CAVEAT_KEYS}
        signature = build_caveat_chain(caveats, _ctx())
        flipped = ("0" if signature[0] != "0" else "1") + signature[1:]
        assert verify_caveat_chain(caveats, flipped, _ctx()) is False

    def test_b2_expired_caveat_rejected(self) -> None:
        case = synthetic_case()
        caveats = {
            "actor": case["actor_id"],
            "purpose": case["purpose"],
            "task": case["task_id"],
            "expiry": str(NOW - 10),
            "nonce": case["nonce"],
            "parent": case["parent_ref"],
        }
        case["caveats"] = caveats
        case["caveat_signature"] = build_caveat_chain(caveats, _ctx())
        outcome = run_baseline("B2", case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == "TOKEN_EXPIRED"

    def test_b3_rejects_replayed_nonce(self) -> None:
        store: set[str] = {"nonce-0001"}
        case = _signed_case()
        assert run_baseline("B3", case, _ctx(store)).observed_outcome == "ADMIT"
        replay = run_baseline("B3", case, _ctx(store))
        assert replay.observed_outcome == "REJECT"
        assert replay.detail == RC_NONCE_REPLAYED

    def test_b3_vs_b0_replay_divergence_is_measured(self) -> None:
        """Paired control: identical replay ADMITted by B0, REJECTed by B3."""
        case = _signed_case()
        b0_first = run_baseline("B0", case, _ctx())
        b0_replay = run_baseline("B0", case, _ctx())
        assert (b0_first.observed_outcome, b0_replay.observed_outcome) == ("ADMIT", "ADMIT")
        store: set[str] = {case["nonce"]}  # type: ignore[arg-type]
        b3_first = run_baseline("B3", case, _ctx(store))
        b3_replay = run_baseline("B3", case, _ctx(store))
        assert (b3_first.observed_outcome, b3_replay.observed_outcome) == ("ADMIT", "REJECT")

    def test_b3_rejects_forged_signature_and_missing_nonce(self) -> None:
        case = _signed_case()
        # Forge a *parseable* token with a wrong MAC: re-serialize the real
        # claims with a mutated field, keep the original MAC.
        import base64
        import json as jsonlib

        raw = base64.urlsafe_b64decode(case["token"] + "=" * 2)  # type: ignore[operator]
        payload = jsonlib.loads(raw)
        payload["claims"]["purpose"] = "evil-purpose"  # attacker mutation
        forged_body = base64.urlsafe_b64encode(
            jsonlib.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        case["token"] = forged_body
        assert run_baseline("B3", case, _ctx({"nonce-0001"})).detail == (
            RC_TOKEN_SIGNATURE_INVALID
        )
        claims = claims_from_case(synthetic_case(expiry=EXPIRY))
        claims.pop("nonce")
        case_no_nonce = synthetic_case(expiry=EXPIRY)
        case_no_nonce["token"] = issue_token(claims, _ctx())
        outcome = run_baseline("B3", case_no_nonce, _ctx({"nonce-0001"}))
        assert outcome.detail == RC_NONCE_MISSING

    def test_b1_rejects_forged_token(self) -> None:
        case = _signed_case()
        import base64
        import json as jsonlib

        raw = base64.urlsafe_b64decode(case["token"] + "=" * 2)  # type: ignore[operator]
        payload = jsonlib.loads(raw)
        payload["claims"]["nonce"] = "attacker-nonce"  # attacker mutation
        forged_body = base64.urlsafe_b64encode(
            jsonlib.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        case["token"] = forged_body
        outcome = run_baseline("B1", case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_TOKEN_SIGNATURE_INVALID

    def test_b1_rejects_missing_nonce_form(self) -> None:
        claims = claims_from_case(synthetic_case(expiry=EXPIRY))
        claims.pop("nonce")
        case = synthetic_case(expiry=EXPIRY)
        case["token"] = issue_token(claims, _ctx())
        outcome = run_baseline("B1", case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_NONCE_MISSING

    def test_unknown_baseline_id_fails_closed(self) -> None:
        with pytest.raises(BaselineError) as excinfo:
            run_baseline("B9_CONSTANT_DENY", _signed_case(), _ctx())
        assert excinfo.value.reason_code == "BASELINE_UNKNOWN_ID"

    def test_short_hmac_key_refused(self) -> None:
        with pytest.raises(BaselineError) as excinfo:
            BaselineContext(hmac_key=b"short", now_epoch_seconds=NOW)
        assert excinfo.value.reason_code == RC_CONTEXT_KEY_TOO_SHORT

    def test_missing_token_rejected_not_raised(self) -> None:
        for baseline_id in ("B0", "B1", "B2", "B3"):
            outcome = run_baseline(baseline_id, {"case_id": "x"}, _ctx({"n1"}))
            assert isinstance(outcome, Outcome)
            assert outcome.observed_outcome == "REJECT"

    def test_b3_requires_injected_store(self) -> None:
        with pytest.raises(BaselineError) as excinfo:
            run_baseline("B3", _signed_case(), _ctx(None))
        assert excinfo.value.reason_code == "CONTEXT_STORE_MISSING"

    def test_parity_check_detects_tampered_variant(self) -> None:
        caveats = {key: f"value-{key}" for key in CAVEAT_KEYS}
        honest = dict(caveats)
        tampered = dict(caveats)
        tampered["purpose"] = "evil-purpose"
        outcome = parity_check(honest, _ctx(), tamper={"variants": [tampered]})
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == RC_PARITY_OK

    def test_parity_check_fails_if_tamper_verifies(self) -> None:
        """If a tampered variant ever verified against the honest signature,
        parity must fail loudly with PARITY_TAMPER_DETECTED (byte binding is
        broken). Proved by forcing the failure path via a monkeypatched
        verifier, the only way to simulate a broken construction."""
        caveats = {key: f"value-{key}" for key in CAVEAT_KEYS}
        tampered = dict(caveats)
        tampered["nonce"] = "forged-nonce"
        broken_ctx = _ctx()
        original = verify_caveat_chain

        def broken_verify(cavs: object, sig: object, ctx: object, **kw: object) -> bool:
            if cavs == tampered:
                return True  # simulate a construction that lost byte binding
            return original(cavs, sig, ctx, **kw)  # type: ignore[arg-type]

        import evaluation.venue2027.ifip_sec.baselines as baselines_module

        assert original(tampered, build_caveat_chain(caveats, broken_ctx), broken_ctx) is False
        monkeyed = baselines_module.verify_caveat_chain
        baselines_module.verify_caveat_chain = broken_verify  # type: ignore[assignment]
        try:
            outcome = parity_check(caveats, broken_ctx, tamper={"variants": [tampered]})
        finally:
            baselines_module.verify_caveat_chain = monkeyed  # type: ignore[assignment]
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_PARITY_TAMPER_DETECTED

    def test_constant_deny_stub_is_not_a_registry_baseline(self) -> None:
        """STUB_PRESENTED_AS_BASELINE discipline: no constant-deny entry exists.

        A naive constant-deny function always REJECTs — which would fake
        perfect replay security. The registry must contain no such arm, and
        the honest in-process arms must be distinguishable from one by their
        ADMIT behaviour on legitimate controls.
        """

        def constant_deny(case: object, ctx: object) -> Outcome:
            return Outcome(
                observed_outcome="REJECT", counted_as_success=True, detail="DENY_ALWAYS"
            )

        # (1) no registry entry declares constant-deny semantics
        for spec in BASELINE_REGISTRY.values():
            assert "constant" not in spec.algorithm_class.lower()
            assert "deny" not in spec.algorithm_class.lower()
        # (2) the stub is not a registered baseline id
        assert "B9_CONSTANT_DENY" not in BASELINE_REGISTRY
        with pytest.raises(BaselineError):
            run_baseline("B9_CONSTANT_DENY", _signed_case(), _ctx())
        # (3) the stub cannot reproduce the honest arms' paired behaviour:
        # a real arm ADMITs the legitimate control, the stub never does.
        legitimate = _signed_case()
        assert run_baseline("B0", legitimate, _ctx()).observed_outcome == "ADMIT"
        assert constant_deny(legitimate, _ctx()).observed_outcome == "REJECT"

    def test_hmac_key_material_is_not_secret_logger(self) -> None:
        """Key hygiene: signatures never leak the raw key bytes."""
        case = _signed_case()
        token = case["token"]  # type: ignore[index]
        assert KEY not in token.encode("utf-8")
        assert KEY.hex().encode("utf-8") not in token.encode("utf-8")

    def test_version_pin(self) -> None:
        assert BASELINES_VERSION == "1.0.0"


# ---------------------------------------------------------------------------
# Oracle-independence smoke: baselines module must not import oracle code.
# ---------------------------------------------------------------------------


class TestModuleHygiene:
    def test_baselines_module_imports_no_oracle(self) -> None:
        import ast
        import pathlib

        source = (
            pathlib.Path(__file__)
            .resolve()
            .parents[3]
            .joinpath("evaluation/venue2027/ifip_sec/baselines.py")
            .read_text(encoding="utf-8")
        )
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any("oracle" in name for name in imported), imported

    def test_key_derivation_matches_reference_recipe(self) -> None:
        """Documented construction: HMAC-SHA256 over canonical JSON claims."""
        claims = {"nonce": "n", "purpose": "p"}
        canonical = '{"nonce":"n","purpose":"p"}'
        expected = hmac.new(KEY, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        from evaluation.venue2027.ifip_sec.baselines import _sign

        assert _sign(KEY, claims) == expected
