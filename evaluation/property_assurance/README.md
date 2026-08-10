# Property assurance

`test_glhs_gateway_properties.py` now exercises actual gateway idempotence and
stale-base-version rejection with Hypothesis against transient SQLite. Existing
`services/api/tests/test_glhs_gateway.py` covers temporal reconstruction and
conflict preservation. The same property module now covers provenance closure
and canonical-ledger durability after deleting derived snapshot rows.
It also verifies a superseded assertion is absent from the following THSS
snapshot, a stale THSS cannot create a persisted proposal, and a constructed
read-only scope cannot commit a GST transition. The same suite reconstructs an
authorized decision from its stored snapshot digest and proposal linkage.
Record Hypothesis seeds and counterexamples in any frozen run.

This work stream is not external clinical validation.
