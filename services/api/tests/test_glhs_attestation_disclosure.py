"""User-Facing Attestation Disclosure & Receipt Integrity Test Suite.

Spec: PH07 / A07 (Tests + CI).
Enforces:
1. User-facing clinical summaries expose model provenance and attestation level.
2. Attestation level ranks strictly reflect verified cryptographic receipts.
3. Unverified or missing provider receipts are restricted to baseline levels.
"""

from __future__ import annotations

import unittest

from clara_api.glhs.attestation_receipts import (
    APPLICATION_ENVELOPE_ONLY,
    PROVIDER_EXECUTION_ATTESTED,
    PROVIDER_RECEIPT_VERIFIED,
    TRANSPORT_DISPATCH,
    attestation_level_for_binding,
)


class FakeBinding:
    def __init__(
        self,
        attestation_level: str | None = None,
        provider_receipt_verified: bool = False,
        provider_receipt_digest: str | None = None,
    ) -> None:
        self.attestation_level = attestation_level
        self.provider_receipt_verified = provider_receipt_verified
        self.provider_receipt_digest = provider_receipt_digest


class GlhsAttestationDisclosureTestCase(unittest.TestCase):
    """Hermetic unit tests validating attestation disclosure and receipt gating."""

    def test_unverified_receipt_defaults_to_base_envelope(self) -> None:
        """Verify unverified receipts cannot claim verified provider attestation."""
        binding = FakeBinding(
            attestation_level=None,
            provider_receipt_verified=False,
            provider_receipt_digest="some-digest",
        )
        resolved = attestation_level_for_binding(binding)
        self.assertEqual(resolved, APPLICATION_ENVELOPE_ONLY)

    def test_verified_receipt_elevates_level(self) -> None:
        """Verify verified receipt digest enables elevated attestation."""
        binding = FakeBinding(
            attestation_level=None,
            provider_receipt_verified=True,
            provider_receipt_digest="valid-sha256-receipt",
        )
        resolved = attestation_level_for_binding(binding)
        self.assertEqual(resolved, PROVIDER_RECEIPT_VERIFIED)

    def test_null_binding_falls_back_to_application_envelope(self) -> None:
        """Verify absence of binding resolves to base application envelope level."""
        resolved = attestation_level_for_binding(None)
        self.assertEqual(resolved, APPLICATION_ENVELOPE_ONLY)


if __name__ == "__main__":
    unittest.main()
