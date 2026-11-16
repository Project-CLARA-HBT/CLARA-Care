"""Tests for IFIP_SEC-X05_macaroons_strong — genuine caveat-bound capability baseline.

Positive controls:
- Creation and attenuation of macaroons via HMAC-SHA256 caveat chain.
- Valid macaroon with purpose, epoch, and proposal lineage caveats verifies cleanly.
- Offline vs online check is explicitly distinguished (online_checked flag).
- Online checking with online-required caveat succeeds in online mode.
- Exact target contract authorize(token, caveats, tx) -> Verdict succeeds.
- Serialization and deserialization round-trip preserving byte fidelity.
- Interop with baselines.py B2 caveat chain construction.

Adversarial controls:
- Tampered caveat fails HMAC verification (CAVEAT_VERIFICATION_FAILED).
- Tampered signature fails HMAC verification (CAVEAT_VERIFICATION_FAILED).
- Expired caveat fails expiry check (TOKEN_EXPIRED).
- Lineage hash mismatch fails proposal binding (LINEAGE_HASH_MISMATCH).
- Offline check rejects online-required caveats (ONLINE_CHECK_REQUIRED).
- Purpose mismatch fails context binding (PURPOSE_MISMATCH).
- Tenant mismatch fails context binding (TENANT_MISMATCH).
- Epoch mismatch fails context binding (EPOCH_MISMATCH).
- Actor mismatch fails context binding (ACTOR_MISMATCH).
- Online revocation check fails revoked tokens (REVOKED).
- Online checker failure rejects with ONLINE_CHECK_FAILED.
- Short root key fails closed (CONTEXT_KEY_TOO_SHORT).
- Malformed token fails closed (TOKEN_MALFORMED).
"""

from __future__ import annotations

import hashlib

import pytest

from evaluation.venue2027.ifip_sec.macaroon_adapter import (
    MACAROON_ADAPTER_VERSION,
    RC_ACTOR_MISMATCH,
    RC_CAVEAT_MALFORMED,
    RC_CAVEAT_VERIFICATION_FAILED,
    RC_CONTEXT_KEY_TOO_SHORT,
    RC_EPOCH_MISMATCH,
    RC_LINEAGE_HASH_MISMATCH,
    RC_OK,
    RC_ONLINE_CHECK_FAILED,
    RC_ONLINE_CHECK_REQUIRED,
    RC_PURPOSE_MISMATCH,
    RC_REVOKED,
    RC_TASK_MISMATCH,
    RC_TENANT_MISMATCH,
    RC_TOKEN_EXPIRED,
    RC_TOKEN_MALFORMED,
    RC_TOKEN_MISSING,
    Macaroon,
    MacaroonAdapter,
    MacaroonVerificationResult,
    add_first_party_caveat,
    authorize,
    bind_proposal_lineage,
    create_macaroon,
    parse_caveat,
    verify_macaroon,
)

ROOT_KEY = b"super-secret-root-key-32-bytes!!"
IDENTIFIER = "macaroon-test-credential-001"
LOCATION = "https://clara.care/api/v1"


@pytest.fixture
def base_macaroon() -> Macaroon:
    return create_macaroon(ROOT_KEY, IDENTIFIER, LOCATION)


# ===========================================================================
# Positive Controls
# ===========================================================================


def test_macaroon_version_and_creation(base_macaroon: Macaroon) -> None:
    """Verify version string, initial Macaroon structure and initial signature."""
    assert MACAROON_ADAPTER_VERSION == "1.0.0"
    assert base_macaroon.identifier == IDENTIFIER
    assert base_macaroon.location == LOCATION
    assert len(base_macaroon.signature) == 64
    assert base_macaroon.caveats == ()


def test_valid_macaroon_with_purpose_epoch_lineage(base_macaroon: Macaroon) -> None:
    """Positive control: valid macaroon with purpose, epoch, and lineage caveats verifies cleanly."""
    lineage_digest = "sha256:" + hashlib.sha256(b"proposal-step-1-to-2").hexdigest()

    m = add_first_party_caveat(base_macaroon, "purpose = self_care")
    m = add_first_party_caveat(m, "epoch = epoch-7")
    m = bind_proposal_lineage(m, lineage_digest)

    assert len(m.caveats) == 3
    assert m.caveats[0] == "purpose = self_care"
    assert m.caveats[1] == "epoch = epoch-7"
    assert m.caveats[2] == f"lineage_hash = {lineage_digest}"

    ctx = {
        "purpose": "self_care",
        "epoch": "epoch-7",
        "lineage_hash": lineage_digest,
    }

    result = verify_macaroon(m, ROOT_KEY, ctx)
    assert result.valid is True
    assert result.allowed is True
    assert result.reason_code == RC_OK
    assert result.caveats_verified == 3


def test_distinguish_offline_vs_online_check(base_macaroon: Macaroon) -> None:
    """Positive control: offline vs online verification mode is explicitly distinguished."""
    lineage_digest = "sha256:" + hashlib.sha256(b"proposal-step-1").hexdigest()

    m = add_first_party_caveat(base_macaroon, "purpose = research")
    m = add_first_party_caveat(m, "epoch = epoch-4")
    m = bind_proposal_lineage(m, lineage_digest)

    ctx = {
        "purpose": "research",
        "epoch": "epoch-4",
        "lineage_hash": lineage_digest,
    }

    # 1. Online verification mode (default)
    online_adapter = MacaroonAdapter(mode="online")
    res_online = online_adapter.verify_macaroon(m, ROOT_KEY, ctx)
    assert res_online.valid is True
    assert res_online.reason_code == RC_OK
    assert res_online.online_checked is True

    # 2. Offline verification mode (ablation)
    offline_adapter = MacaroonAdapter(mode="offline")
    res_offline = offline_adapter.verify_macaroon(m, ROOT_KEY, ctx)
    assert res_offline.valid is True
    assert res_offline.reason_code == RC_OK
    assert res_offline.online_checked is False

    # 3. Via verify_macaroon keyword argument
    res_kw_offline = verify_macaroon(m, ROOT_KEY, ctx, offline_only=True)
    assert res_kw_offline.valid is True
    assert res_kw_offline.online_checked is False

    res_kw_online = verify_macaroon(m, ROOT_KEY, ctx, offline_only=False)
    assert res_kw_online.valid is True
    assert res_kw_online.online_checked is True


def test_online_check_with_online_required_caveat_succeeds_in_online_mode(
    base_macaroon: Macaroon,
) -> None:
    """Positive control: an online-required caveat verifies cleanly in online mode."""
    m = add_first_party_caveat(base_macaroon, "check = online")
    m = add_first_party_caveat(m, "purpose = clinical_review")

    called_with = []

    def mock_checker(caveat: str, context: dict) -> bool:
        called_with.append(caveat)
        return True

    ctx = {
        "purpose": "clinical_review",
        "online_checker": mock_checker,
    }

    adapter = MacaroonAdapter(mode="online")
    res = adapter.verify_macaroon(m, ROOT_KEY, ctx)
    assert res.valid is True
    assert res.reason_code == RC_OK
    assert res.online_checked is True
    assert "check = online" in called_with


def test_authorize_contract_target_signature(base_macaroon: Macaroon) -> None:
    """Positive control: authorize(token, caveats, tx) -> Verdict contract."""
    serialized = base_macaroon.serialize()
    tx = {
        "root_key": ROOT_KEY,
        "tenant": "hospital-central",
        "purpose": "triage",
        "policy_epoch": "epoch-10",
        "now_epoch_seconds": 1000,
    }

    extra_caveats = [
        "tenant = hospital-central",
        "purpose = triage",
        "policy_epoch = epoch-10",
        "expiry = 2000",
    ]

    verdict = authorize(serialized, caveats=extra_caveats, tx=tx)
    assert isinstance(verdict, MacaroonVerificationResult)
    assert verdict.allowed is True
    assert verdict.reason_code == RC_OK
    assert verdict.caveats_verified == 4


def test_serialization_and_deserialization_fidelity(base_macaroon: Macaroon) -> None:
    """Positive control: serialize and deserialize preserve byte-exact signatures and caveats."""
    m = add_first_party_caveat(base_macaroon, "tenant = test-tenant")
    m = add_first_party_caveat(m, "actor = test-user")

    serialized = m.serialize()
    assert isinstance(serialized, str)
    assert m.token_bytes == len(serialized.encode("utf-8"))

    restored = Macaroon.deserialize(serialized)
    assert restored.identifier == m.identifier
    assert restored.location == m.location
    assert restored.signature == m.signature
    assert restored.caveats == m.caveats

    # Round-trip JSON dict
    restored_json = Macaroon.deserialize(
        str(restored.to_dict()).replace("'", '"')
    )
    assert restored_json.signature == m.signature


def test_attenuation_chain_depth(base_macaroon: Macaroon) -> None:
    """Positive control: sequential attenuations fold correctly into HMAC chain."""
    current = base_macaroon
    expected_caveats = []
    for i in range(10):
        cav = f"step_{i} = val_{i}"
        current = add_first_party_caveat(current, cav)
        expected_caveats.append(cav)

    assert len(current.caveats) == 10
    assert list(current.caveats) == expected_caveats

    ctx = {f"step_{i}": f"val_{i}" for i in range(10)}
    res = verify_macaroon(current, ROOT_KEY, ctx)
    assert res.valid is True
    assert res.caveats_verified == 10


def test_from_baseline_caveats_interop() -> None:
    """Positive control: wrap baselines.py B2 caveat chain into Macaroon."""
    caveats = {
        "actor": "clinician-42",
        "purpose": "treatment",
        "task": "task-review",
        "expiry": "4102444800",
        "nonce": "nonce-xyz",
        "parent": "root",
    }
    m = MacaroonAdapter.from_baseline_caveats(ROOT_KEY, caveats, identifier="b2-token")
    assert m.identifier == "b2-token"
    assert len(m.caveats) == 6

    ctx = {
        "actor": "clinician-42",
        "purpose": "treatment",
        "task": "task-review",
        "now_epoch_seconds": 1000,
        "nonce": "nonce-xyz",
        "parent": "root",
    }
    res = verify_macaroon(m, ROOT_KEY, ctx)
    assert res.valid is True
    assert res.reason_code == RC_OK


def test_to_outcome_conversion(base_macaroon: Macaroon) -> None:
    """Positive control: MacaroonVerificationResult converts to harness Outcome."""
    res = verify_macaroon(base_macaroon, ROOT_KEY, {})
    outcome = res.to_outcome()
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.detail == RC_OK
    assert outcome.counted_as_success is True


# ===========================================================================
# Adversarial Controls
# ===========================================================================


def test_tampered_caveat_fails(base_macaroon: Macaroon) -> None:
    """Adversarial control: tampering with any caveat byte breaks the HMAC chain."""
    m = add_first_party_caveat(base_macaroon, "purpose = self_care")
    m = add_first_party_caveat(m, "tenant = tenant-alpha")

    # Attacker alters the caveat text in transit without re-signing
    tampered_caveats = ("purpose = emergency", "tenant = tenant-alpha")
    tampered_macaroon = Macaroon(
        location=m.location,
        identifier=m.identifier,
        signature=m.signature,
        caveats=tampered_caveats,
    )

    ctx = {"purpose": "emergency", "tenant": "tenant-alpha"}
    res = verify_macaroon(tampered_macaroon, ROOT_KEY, ctx)
    assert res.valid is False
    assert res.allowed is False
    assert res.reason_code == RC_CAVEAT_VERIFICATION_FAILED
    assert res.caveats_verified == 0


def test_tampered_signature_fails(base_macaroon: Macaroon) -> None:
    """Adversarial control: invalid or tampered signature is rejected."""
    m = add_first_party_caveat(base_macaroon, "purpose = self_care")
    corrupted_sig = "a" * 64

    corrupted_macaroon = Macaroon(
        location=m.location,
        identifier=m.identifier,
        signature=corrupted_sig,
        caveats=m.caveats,
    )

    res = verify_macaroon(corrupted_macaroon, ROOT_KEY, {"purpose": "self_care"})
    assert res.valid is False
    assert res.reason_code == RC_CAVEAT_VERIFICATION_FAILED


def test_expired_caveat_fails(base_macaroon: Macaroon) -> None:
    """Adversarial control: expired caveat fails verification with TOKEN_EXPIRED."""
    m = add_first_party_caveat(base_macaroon, "purpose = triage")
    m = add_first_party_caveat(m, "expiry = 1500")

    # Current clock is past expiry
    ctx = {
        "purpose": "triage",
        "now_epoch_seconds": 1600,
    }

    res = verify_macaroon(m, ROOT_KEY, ctx)
    assert res.valid is False
    assert res.reason_code == RC_TOKEN_EXPIRED
    assert "now 1600 > expiry 1500" in res.detail


def test_lineage_hash_mismatch_fails(base_macaroon: Macaroon) -> None:
    """Adversarial control: mismatched proposal lineage hash fails with LINEAGE_HASH_MISMATCH."""
    honest_hash = "sha256:" + hashlib.sha256(b"proposal-step-1-to-2").hexdigest()
    attacker_hash = "sha256:" + hashlib.sha256(b"spliced-proposal-step-x").hexdigest()

    m = bind_proposal_lineage(base_macaroon, honest_hash)

    # Context presents an unauthorized or spliced lineage
    ctx = {"lineage_hash": attacker_hash}
    res = verify_macaroon(m, ROOT_KEY, ctx)
    assert res.valid is False
    assert res.reason_code == RC_LINEAGE_HASH_MISMATCH
    assert "Lineage hash mismatch" in res.detail


def test_offline_check_rejects_online_required_caveat(base_macaroon: Macaroon) -> None:
    """Adversarial control: offline mode rejects online-required caveats (ablation gate)."""
    m = add_first_party_caveat(base_macaroon, "check = online")
    m = add_first_party_caveat(m, "purpose = self_care")

    ctx = {"purpose": "self_care"}

    # In offline mode, the presence of 'check = online' MUST fail closed
    offline_adapter = MacaroonAdapter(mode="offline")
    res = offline_adapter.verify_macaroon(m, ROOT_KEY, ctx)
    assert res.valid is False
    assert res.reason_code == RC_ONLINE_CHECK_REQUIRED
    assert res.online_checked is False

    # Also test with 'online = true' variant
    m2 = add_first_party_caveat(base_macaroon, "online = true")
    res2 = verify_macaroon(m2, ROOT_KEY, ctx, offline_only=True)
    assert res2.valid is False
    assert res2.reason_code == RC_ONLINE_CHECK_REQUIRED


def test_purpose_mismatch_fails(base_macaroon: Macaroon) -> None:
    """Adversarial control: cross-purpose presentation is rejected."""
    m = add_first_party_caveat(base_macaroon, "purpose = clinical_research")

    ctx = {"purpose": "marketing_analytics"}
    res = verify_macaroon(m, ROOT_KEY, ctx)
    assert res.valid is False
    assert res.reason_code == RC_PURPOSE_MISMATCH


def test_tenant_mismatch_fails(base_macaroon: Macaroon) -> None:
    """Adversarial control: cross-tenant presentation is rejected."""
    m = add_first_party_caveat(base_macaroon, "tenant = tenant-hospital-a")

    ctx = {"tenant": "tenant-hospital-b"}
    res = verify_macaroon(m, ROOT_KEY, ctx)
    assert res.valid is False
    assert res.reason_code == RC_TENANT_MISMATCH


def test_epoch_mismatch_fails(base_macaroon: Macaroon) -> None:
    """Adversarial control: presentation across epoch change is rejected."""
    m = add_first_party_caveat(base_macaroon, "epoch = epoch-5")

    ctx = {"epoch": "epoch-6"}
    res = verify_macaroon(m, ROOT_KEY, ctx)
    assert res.valid is False
    assert res.reason_code == RC_EPOCH_MISMATCH


def test_actor_and_task_mismatch_fail(base_macaroon: Macaroon) -> None:
    """Adversarial control: mismatched actor and task are rejected."""
    m = add_first_party_caveat(base_macaroon, "actor = dr-smith")
    m = add_first_party_caveat(m, "task = discharge-summary")

    res_actor = verify_macaroon(
        m, ROOT_KEY, {"actor": "dr-evil", "task": "discharge-summary"}
    )
    assert res_actor.valid is False
    assert res_actor.reason_code == RC_ACTOR_MISMATCH

    res_task = verify_macaroon(
        m, ROOT_KEY, {"actor": "dr-smith", "task": "prescribe-medication"}
    )
    assert res_task.valid is False
    assert res_task.reason_code == RC_TASK_MISMATCH


def test_online_revocation_store_rejects(base_macaroon: Macaroon) -> None:
    """Adversarial control: online verification checks against revocation store."""
    m = add_first_party_caveat(base_macaroon, "check = online")

    revoked_set = {IDENTIFIER}
    ctx = {
        "revocation_store": revoked_set,
    }

    res = verify_macaroon(m, ROOT_KEY, ctx, offline_only=False)
    assert res.valid is False
    assert res.reason_code == RC_REVOKED
    assert res.online_checked is True


def test_online_checker_failure_rejects(base_macaroon: Macaroon) -> None:
    """Adversarial control: online checker returning False causes rejection."""
    m = add_first_party_caveat(base_macaroon, "check = online")

    ctx = {
        "online_checker": lambda cav, ctx: False,
    }

    res = verify_macaroon(m, ROOT_KEY, ctx, offline_only=False)
    assert res.valid is False
    assert res.reason_code == RC_ONLINE_CHECK_FAILED


def test_short_root_key_fails_closed(base_macaroon: Macaroon) -> None:
    """Adversarial control: root key shorter than 16 bytes fails closed."""
    short_key = b"short-key"
    res = verify_macaroon(base_macaroon, short_key, {})
    assert res.valid is False
    assert res.reason_code == RC_CONTEXT_KEY_TOO_SHORT

    with pytest.raises(ValueError, match="root_key must be bytes of length >="):
        create_macaroon(short_key, IDENTIFIER, LOCATION)


def test_malformed_token_fails_closed() -> None:
    """Adversarial control: malformed or unparseable token strings fail closed."""
    res_garbage = verify_macaroon("not-a-valid-token-string!@#", ROOT_KEY, {})
    assert res_garbage.valid is False
    assert res_garbage.reason_code == RC_TOKEN_MALFORMED

    res_auth = authorize(None, tx={"root_key": ROOT_KEY})
    assert res_auth.valid is False
    assert res_auth.reason_code == RC_TOKEN_MISSING

    res_missing_key = authorize(
        create_macaroon(ROOT_KEY, IDENTIFIER, LOCATION).serialize(), tx={}
    )
    assert res_missing_key.valid is False
    assert res_missing_key.reason_code == RC_CONTEXT_KEY_TOO_SHORT


def test_malformed_caveat_syntax() -> None:
    """Adversarial control: caveat with invalid expiry number fails with CAVEAT_MALFORMED."""
    m = create_macaroon(ROOT_KEY, IDENTIFIER, LOCATION)
    m = add_first_party_caveat(m, "expiry = not-a-number")

    res = verify_macaroon(m, ROOT_KEY, {"now_epoch_seconds": 100})
    assert res.valid is False
    assert res.reason_code == RC_CAVEAT_MALFORMED


def test_parse_caveat_delimiters() -> None:
    """Unit test for predicate delimiter parsing."""
    k, op, v = parse_caveat("purpose = self_care")
    assert (k, op, v) == ("purpose", "=", "self_care")

    k, op, v = parse_caveat("expiry < 12345")
    assert (k, op, v) == ("expiry", "<", "12345")

    k, op, v = parse_caveat("actor: user1")
    assert (k, op, v) == ("actor", ":", "user1")
