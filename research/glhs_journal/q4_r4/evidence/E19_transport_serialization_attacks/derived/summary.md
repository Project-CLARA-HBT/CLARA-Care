# E19 Transport Serialization Attack Resistance Summary

- **Total Mutated Transport Schedules Executed against SUT:** 256 across 8 patterns (32 schedules per pattern)
- **Transport Mutation Rejection Rate:** 256/256 (100.0%)
- **Rejection Reason Code:** 100% `proposal_envelope_digest_mismatch` / `transport_digest_mismatch`
- **Projection Digest (H_proj) Invariance Rate:** 100.0%
- **Two-Digest Transport Independence Invariant (I18):** VERIFIED.
