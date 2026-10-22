# Risk Register — PH07 A03 (D3 Transport Payload Digest Verifier)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A03-01 | Man-in-the-middle or HTTP proxy mutating outbound JSON bytes | Critical | Low | D3 digest computes SHA-256 over exact wire bytes post-serialization before socket dispatch. | Mitigated |
| RISK-PH07-A03-02 | Inadvertent disclosure of raw transport bytes in error logs | High | Low | Verification outcome emits only computed 64-character hex digests, never raw wire bytes. | Mitigated |
