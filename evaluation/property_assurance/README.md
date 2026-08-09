# Property assurance

`test_glhs_gateway_properties.py` now exercises actual gateway idempotence and
stale-base-version rejection with Hypothesis against transient SQLite. Existing
`services/api/tests/test_glhs_gateway.py` covers temporal reconstruction and
conflict preservation. The same property module now covers provenance closure
and canonical-ledger durability after deleting derived snapshot rows.
It also verifies a superseded assertion is absent from the following THSS
snapshot. Production-facing GLHS tests still need explicit state-machine
coverage for policy-version invalidation.
Record Hypothesis seeds and counterexamples in any frozen run.

This work stream is not external clinical validation.
