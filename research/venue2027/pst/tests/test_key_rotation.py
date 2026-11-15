"""Tests for PST-X06_key_rotation — retention epoch and pseudonym key lifecycle.

Purpose
-------
Verify the HKDF-derived ``(tenant, purpose, epoch)`` scope-key lifecycle of
``evaluation/venue2027/pst/epoch_keys.py`` (task contract
``research/venue2027/VENUES/pst/TASKS/PST-X06_key_rotation.md``, phase P04;
threat model T2/T3, S2, X2, PST-CASE-07 discipline).

Positive vectors prove the governed lifecycle: deterministic derivation
(same scope+epoch derives the same key reference), epoch separation (a new
epoch derives a cryptographically independent key), tenant/purpose domain
separation (no scope tuple aliases another), rotation manifest recording
(closed epoch with destroyed timestamp + fresh epoch registered), RFC 5869
HKDF test-vector conformance, and JSON-serializable PHI-free artifacts.

Adversarial vectors prove fail-closed security: a destroyed epoch derives
nothing (``EPOCH_ALREADY_DESTROYED``) and is reported ``IRREVERSIBLE`` for
authorized-audit reconstruction; destruction of a legal-hold scope is
refused (``DESTROY_NOT_PERMITTED``) and stays ``REVERSIBLE``; unknown
tenants/epochs/purposes and malformed scope identifiers fail closed with
stable reason codes; and raw key material NEVER appears in the manifest
serialization (key references only), including a round-trip leak scan over
every derived key in every artifact and error message.

Allowed input
-------------
The module under test, imported from the repository checkout, with injected
synthetic root secrets and logical timestamps. No network, no clock, no
randomness, no database, no real PHI, no production secrets. Failure
semantics: every violation is an ordinary pytest assertion failure or a
stable-reason-code :class:`epoch_keys.EpochKeyError`; nothing is silently
skipped. Version: 1.0.0.
"""

from __future__ import annotations

import hmac
import json
import pathlib
import sys

import pytest

EVAL_ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(EVAL_ROOT))

from evaluation.venue2027.pst import epoch_keys as ek  # noqa: E402

ROOT = "synthetic-root-secret-pst-2027"
TENANT = "tenant-alpha"
TENANT_B = "tenant-beta"
PURPOSE = "pseudonym"
HELD_PURPOSE = "authorization"

MANIFEST_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / "pst" / ".." / ".." / ".." / "evaluation"
)


def _fresh_manifest() -> ek.KeyRotationManifest:
    """Manifest with one live registered scope (tenant-alpha/pseudonym/e1)."""

    manifest = ek.KeyRotationManifest()
    okm, ref = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
    manifest.register(TENANT, PURPOSE, "e1", created_at=1, key_ref=ref)
    return manifest


# ---------------------------------------------------------------------------
# Positive vectors — the governed lifecycle
# ---------------------------------------------------------------------------


class TestDeterministicDerivation:
    """Same scope+epoch always derives the same key (pure, no randomness)."""

    def test_same_scope_and_epoch_derives_same_key_ref(self) -> None:
        okm1, ref1 = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        okm2, ref2 = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        assert okm1 == okm2
        assert ref1 == ref2

    def test_derivation_is_deterministic_across_root_forms(self) -> None:
        okm_str, ref_str = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        okm_bytes, ref_bytes = ek.derive_key(ROOT.encode("utf-8"), TENANT, PURPOSE, "e1")
        assert okm_str == okm_bytes
        assert ref_str == ref_bytes

    def test_derived_key_is_32_bytes(self) -> None:
        okm, _ = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        assert len(okm) == 32

    def test_key_ref_is_stable_sha256_reference(self) -> None:
        okm, ref = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        expected = ek.key_ref(okm)
        assert ref == expected
        assert len(ref) == 64
        int(ref, 16)  # must be hex

    def test_verify_token_proves_possession_without_disclosure(self) -> None:
        okm, _ = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        token1 = ek.verify_token(okm, "audit-verify")
        token2 = ek.verify_token(okm, "audit-verify")
        assert token1 == token2
        assert len(token1) == 64

    def test_hkdf_rfc5869_test_vector_case1(self) -> None:
        """Conformance: RFC 5869 Appendix A, Test Case 1 (SHA-256)."""

        ikm = bytes.fromhex("0b" * 22)
        salt = bytes.fromhex("000102030405060708090a0b0c")
        info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
        prk = ek._hkdf_extract(salt, ikm)
        assert prk.hex() == ("077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5")
        okm = ek._hkdf_expand(prk, info, length=42)
        assert okm.hex() == (
            "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
            "34007208d5b887185865"
        )


class TestEpochSeparation:
    """A new epoch must derive a cryptographically independent key."""

    def test_new_epoch_differs_from_old(self) -> None:
        okm_old, ref_old = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        okm_new, ref_new = ek.derive_key(ROOT, TENANT, PURPOSE, "e2")
        assert okm_old != okm_new
        assert ref_old != ref_new

    def test_tenant_separation(self) -> None:
        _, ref_a = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        _, ref_b = ek.derive_key(ROOT, TENANT_B, PURPOSE, "e1")
        assert ref_a != ref_b

    def test_purpose_separation(self) -> None:
        _, ref_p = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        _, ref_q = ek.derive_key(ROOT, TENANT, HELD_PURPOSE, "e1")
        assert ref_p != ref_q

    def test_length_prefix_blocks_scope_aliasing(self) -> None:
        """('ab', 'c') must never alias ('a', 'bc') thanks to length prefixes."""

        info_1 = ek._scope_info("ab", "c", "e1")
        info_2 = ek._scope_info("a", "bc", "e1")
        assert info_1 != info_2


class TestRotationManifest:
    """Rotation is recorded: closed epoch + destruction instant + new epoch."""

    def test_rotation_closes_old_and_creates_new_epoch(self) -> None:
        manifest = _fresh_manifest()
        new_epoch, scope = ek.rotate(TENANT, PURPOSE, manifest, root=ROOT, destroyed_at=10)
        assert new_epoch == "e2"
        assert scope.epoch == "e2"
        old = manifest.entry_for(TENANT, PURPOSE, "e1")
        assert old is not None and old.destroyed is True
        assert old.destroyed_at == 10

    def test_rotation_manifest_records_the_change(self) -> None:
        manifest = _fresh_manifest()
        snapshot_before = json.loads(manifest.dumps())
        assert len(snapshot_before["entries"]) == 1
        ek.rotate(TENANT, PURPOSE, manifest, root=ROOT, destroyed_at=10)
        snapshot_after = json.loads(manifest.dumps())
        entries = snapshot_after["entries"]
        assert len(entries) == 2
        by_epoch = {e["epoch"]: e for e in entries}
        assert by_epoch["e1"]["destroyed"] is True
        assert by_epoch["e1"]["destroyed_at"] == 10
        assert by_epoch["e2"]["destroyed"] is False
        assert by_epoch["e2"]["created_at"] == 10
        # The two epochs derive independent key references.
        assert by_epoch["e1"]["key_ref"] != by_epoch["e2"]["key_ref"]

    def test_rotated_epoch_key_differs_and_is_registered(self) -> None:
        manifest = _fresh_manifest()
        _, ref_old = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        new_epoch, scope = ek.rotate(TENANT, PURPOSE, manifest, root=ROOT, destroyed_at=10)
        okm_new, ref_new = ek.derive_key(ROOT, TENANT, PURPOSE, new_epoch, manifest=manifest)
        assert ref_new == scope.key_ref
        assert ref_new != ref_old
        assert okm_new != ek.derive_key(ROOT, TENANT, PURPOSE, "e1")[0]

    def test_register_is_idempotent_for_identical_scope(self) -> None:
        manifest = _fresh_manifest()
        _, ref = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        entry = manifest.register(TENANT, PURPOSE, "e1", created_at=99, key_ref=ref)
        assert entry.created_at == 1  # original kept; retry collapsed

    def test_manifest_is_json_serializable(self) -> None:
        manifest = _fresh_manifest()
        ek.rotate(TENANT, PURPOSE, manifest, root=ROOT, destroyed_at=10)
        payload = manifest.to_dict()
        assert payload["schema_version"] == ek.SCHEMA_VERSION
        assert payload["epoch_keys_version"] == ek.EPOCH_KEYS_VERSION
        round_trip = json.loads(json.dumps(payload))
        assert round_trip == payload

    def test_scope_key_id_is_stable_logical_operation_id(self) -> None:
        _, ref = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        manifest = ek.KeyRotationManifest()
        manifest.register(TENANT, PURPOSE, "e1", created_at=1, key_ref=ref)
        entry = manifest.entry_for(TENANT, PURPOSE, "e1")
        assert entry is not None
        assert entry.to_dict()["scope_key_id"] == f"{TENANT}/{PURPOSE}/e1"


class TestControlledDestruction:
    """Controlled destruction where permitted; legal hold stays live."""

    def test_destroy_marks_entry_destroyed(self) -> None:
        manifest = _fresh_manifest()
        entry = ek.destroy(TENANT, PURPOSE, "e1", manifest, destroyed_at=20)
        assert entry.destroyed is True
        assert entry.destroyed_at == 20

    def test_destroyed_scope_records_irreversible(self) -> None:
        manifest = _fresh_manifest()
        ek.destroy(TENANT, PURPOSE, "e1", manifest, destroyed_at=20)
        assert manifest.reversibility(TENANT, PURPOSE, "e1") == "IRREVERSIBLE"

    def test_live_scope_records_reversible(self) -> None:
        manifest = _fresh_manifest()
        assert manifest.reversibility(TENANT, PURPOSE, "e1") == "REVERSIBLE"

    def test_legal_hold_scope_cannot_be_destroyed(self) -> None:
        manifest = ek.KeyRotationManifest()
        _, ref = ek.derive_key(ROOT, TENANT, HELD_PURPOSE, "e1")
        manifest.register(TENANT, HELD_PURPOSE, "e1", created_at=1, key_ref=ref, destroyable=False)
        with pytest.raises(ek.EpochKeyError) as excinfo:
            ek.destroy(TENANT, HELD_PURPOSE, "e1", manifest, destroyed_at=20)
        assert excinfo.value.reason_code == ek.REASON_DESTROY_NOT_PERMITTED
        # The legal-hold scope stays live and reversible.
        assert manifest.entry_for(TENANT, HELD_PURPOSE, "e1").destroyed is False
        assert manifest.reversibility(TENANT, HELD_PURPOSE, "e1") == "REVERSIBLE"


# ---------------------------------------------------------------------------
# Adversarial vectors — fail-closed discipline
# ---------------------------------------------------------------------------


class TestDestroyedEpochUnusable:
    """A destroyed epoch derives nothing and is reported IRREVERSIBLE."""

    def test_destroyed_epoch_key_is_unusable(self) -> None:
        manifest = _fresh_manifest()
        ek.destroy(TENANT, PURPOSE, "e1", manifest, destroyed_at=20)
        with pytest.raises(ek.EpochKeyError) as excinfo:
            ek.derive_key(ROOT, TENANT, PURPOSE, "e1", manifest=manifest)
        assert excinfo.value.reason_code == ek.REASON_EPOCH_DESTROYED

    def test_destroyed_epoch_reconstruction_is_irreversible(self) -> None:
        manifest = _fresh_manifest()
        ek.destroy(TENANT, PURPOSE, "e1", manifest, destroyed_at=20)
        verdict = manifest.reversibility(TENANT, PURPOSE, "e1")
        assert verdict == "IRREVERSIBLE"
        assert verdict in (ek.REVERSIBLE, ek.IRREVERSIBLE)

    def test_destroy_is_refused_twice(self) -> None:
        manifest = _fresh_manifest()
        ek.destroy(TENANT, PURPOSE, "e1", manifest, destroyed_at=20)
        with pytest.raises(ek.EpochKeyError) as excinfo:
            ek.destroy(TENANT, PURPOSE, "e1", manifest, destroyed_at=21)
        assert excinfo.value.reason_code == ek.REASON_EPOCH_DESTROYED

    def test_re_register_destroyed_scope_refused(self) -> None:
        manifest = _fresh_manifest()
        ek.destroy(TENANT, PURPOSE, "e1", manifest, destroyed_at=20)
        with pytest.raises(ek.EpochKeyError) as excinfo:
            manifest.register(TENANT, PURPOSE, "e1", created_at=21, key_ref="0" * 64)
        assert excinfo.value.reason_code == ek.REASON_EPOCH_DESTROYED

    def test_rotate_without_live_epoch_fails_closed(self) -> None:
        manifest = ek.KeyRotationManifest()
        with pytest.raises(ek.EpochKeyError) as excinfo:
            ek.rotate(TENANT, PURPOSE, manifest, root=ROOT, destroyed_at=10)
        assert excinfo.value.reason_code == ek.REASON_EPOCH_DESTROYED

    def test_derive_against_unknown_manifest_scopes_fails_closed(self) -> None:
        manifest = _fresh_manifest()
        with pytest.raises(ek.EpochKeyError) as unknown_epoch:
            ek.derive_key(ROOT, TENANT, PURPOSE, "e9", manifest=manifest)
        assert unknown_epoch.value.reason_code == ek.REASON_UNKNOWN_EPOCH
        with pytest.raises(ek.EpochKeyError) as unknown_tenant:
            ek.derive_key(ROOT, TENANT_B, PURPOSE, "e1", manifest=manifest)
        assert unknown_tenant.value.reason_code == ek.REASON_UNKNOWN_TENANT


class TestNoKeyMaterialDisclosure:
    """Raw key material must never appear in the manifest, artifacts or logs."""

    def test_manifest_stores_references_not_material(self) -> None:
        manifest = _fresh_manifest()
        okm, _ = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        ek.rotate(TENANT, PURPOSE, manifest, root=ROOT, destroyed_at=10)
        serialized = manifest.dumps() + json.dumps(manifest.to_dict())
        # The manifest never carries the derived bytes or the root secret.
        assert okm.hex() not in serialized
        assert bytes(okm).decode("latin-1") not in serialized
        assert ROOT not in serialized

    def test_every_artifact_is_free_of_key_material(self) -> None:
        manifest = _fresh_manifest()
        okm1, _ = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        new_epoch, scope = ek.rotate(TENANT, PURPOSE, manifest, root=ROOT, destroyed_at=10)
        okm2, _ = ek.derive_key(ROOT, TENANT, PURPOSE, new_epoch)
        scope_dict = json.dumps(scope.to_dict())
        for secret in (okm1, okm2, ROOT.encode("utf-8")):
            assert secret.hex() not in serialized_text(manifest, scope_dict)
            assert secret.decode("latin-1") not in serialized_text(manifest, scope_dict)

    def test_error_messages_never_contain_key_material(self) -> None:
        manifest = _fresh_manifest()
        okm, _ = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        ek.destroy(TENANT, PURPOSE, "e1", manifest, destroyed_at=20)
        try:
            ek.derive_key(ROOT, TENANT, PURPOSE, "e1", manifest=manifest)
        except ek.EpochKeyError as err:
            message = str(err)
        assert okm.hex() not in message
        assert okm.decode("latin-1") not in message

    def test_key_ref_cannot_recover_material(self) -> None:
        """The recorded reference is a one-way commitment, not truncated OKM."""

        okm, ref = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        assert okm.hex() != ref  # not the material itself
        assert okm[:32].hex() != ref  # not a truncation of the material

    def test_verify_token_is_not_the_key(self) -> None:
        okm, _ = ek.derive_key(ROOT, TENANT, PURPOSE, "e1")
        token = ek.verify_token(okm, "audit-verify")
        assert token != okm.hex()
        assert hmac.compare_digest(token, ek.verify_token(okm, "audit-verify"))


def serialized_text(manifest: ek.KeyRotationManifest, extra: str) -> str:
    """Every textual artifact the lifecycle produces for one lifecycle run."""

    return manifest.dumps() + json.dumps(manifest.to_dict()) + extra


class TestFailClosedScopeValidation:
    """Malformed scope identifiers and unknown purposes fail closed."""

    @pytest.mark.parametrize(
        ("tenant", "purpose", "epoch"),
        [
            ("", PURPOSE, "e1"),
            (None, PURPOSE, "e1"),
            (TENANT, "", "e1"),
            (TENANT, PURPOSE, ""),
            (TENANT, PURPOSE, None),
        ],
    )
    def test_malformed_scope_refused(self, tenant: object, purpose: object, epoch: object) -> None:
        with pytest.raises(ek.EpochKeyError) as excinfo:
            ek.derive_key(ROOT, tenant, purpose, epoch)  # type: ignore[arg-type]
        assert excinfo.value.reason_code in (
            ek.REASON_MALFORMED_SCOPE,
            ek.REASON_UNKNOWN_PURPOSE,
        )

    def test_unknown_purpose_refused(self) -> None:
        with pytest.raises(ek.EpochKeyError) as excinfo:
            ek.derive_key(ROOT, TENANT, "diagnosis_freeform", "e1")
        assert excinfo.value.reason_code == ek.REASON_UNKNOWN_PURPOSE

    def test_empty_root_refused(self) -> None:
        with pytest.raises(ek.EpochKeyError) as excinfo:
            ek.derive_key("", TENANT, PURPOSE, "e1")
        assert excinfo.value.reason_code == ek.REASON_MALFORMED_SCOPE

    def test_unknown_purpose_list_is_closed_vocabulary(self) -> None:
        assert set(ek.PURPOSES) == {
            "authorization",
            "pseudonym",
            "receipt_content",
            "investigation",
        }


class TestManifestIntegrity:
    """Manifest history cannot be rewritten and stays PHI-free."""

    def test_re_register_with_different_material_refused(self) -> None:
        manifest = _fresh_manifest()
        with pytest.raises(ek.EpochKeyError) as excinfo:
            manifest.register(TENANT, PURPOSE, "e1", created_at=5, key_ref="f" * 64)
        assert excinfo.value.reason_code == ek.REASON_MALFORMED_SCOPE

    def test_no_phi_markers_in_manifest_vocabulary(self) -> None:
        manifest = _fresh_manifest()
        ek.rotate(TENANT, PURPOSE, manifest, root=ROOT, destroyed_at=10)
        text = manifest.dumps()
        for marker in ("patient", "name", "email", "mrn", "ssn", "diagnosis"):
            assert marker not in text.lower()
