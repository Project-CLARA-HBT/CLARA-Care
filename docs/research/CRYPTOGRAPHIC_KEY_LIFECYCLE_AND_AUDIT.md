# Cryptographic Key Lifecycle, Attestation Verification & Audit (PH07)

## Executive Summary
This research specification formalizes the cryptographic key management architecture, rotation lifecycle, and audit procedures governing GLHS R4 transport attestation and provider receipts.

## Cryptographic Key Topology

| Key Role | Algorithm | Purpose | Storage & Secrecy | Rotation Interval |
|---|---|---|---|---|
| Provider Receipt Verifier | Ed25519 / RSA-4096 | Verifies L2/L3 cryptographic execution receipts | Public Key Registry | 90 days |
| Service Token Signer | HMAC-SHA256 (32 bytes) | Authenticates internal inter-plane RPC requests | Environment Secret | 30 days |
| Transport Digest Anchor | SHA-256 | Non-repudiation of outbound HTTP body bytes | Deterministic Hash | N/A (Cryptographic Primitive) |
| Snapshot Manifest Digest | SHA-256 over RFC 8785 | Immutability of Temporal Health State Snapshots | Deterministic Hash | N/A (Cryptographic Primitive) |

## Key Rotation Ceremony & Dual-Key Overlap

1. **Overlap Window:** When rotating signing keys, a 14-day overlap window is mandated:
   - $Key_{active}$: Used for all newly minted tokens/receipts.
   - $Key_{retiring}$: Retained in validator key rings to verify tokens issued prior to rotation.
   - $Key_{revoked}$: Instantly removed from all key rings; any token signed with this key fails closed with HTTP 401.
2. **Audit Logging:** Every key activation, transition to retiring, and revocation must be recorded in `control_audit_logs` with dual-administrator signatures.
3. **No-PII Integrity:** Key records never link to patient identifiers or clinical health records.
