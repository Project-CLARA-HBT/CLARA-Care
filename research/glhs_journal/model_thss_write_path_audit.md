# GLHS model-originated THSS write-path audit

Status: **implementation-conformance audit; not PostgreSQL TOCTOU evidence**.

Audit scope: production API source under `services/api/src/clara_api` and its
direct gateway admission function `propose_assertion`.

| Surface | Can a model-originated proposal persist through it? | THSS binding result | Evidence |
| --- | --- | --- | --- |
| Generic assertion gateway | No. `process_kind == "model"` is rejected with `model_cannot_write_assertion` before an assertion is persisted. | There is no model-originated base-version-only fallback on this surface. | `services/api/src/clara_api/glhs/gateway.py`; `services/api/tests/test_glhs_mandatory_thss_binding.py` |
| Generic user/clinical/connector adapters | Yes for their own non-model source records only. | They do not represent model-derived THSS proposals; treating them as such would require an explicit proposal-origin change and the mandatory binding contract. | `services/api/src/clara_api/glhs/adapters.py` call sites |
| Public commitment proposal API | The route creates a human-governed proposal with `origin="user"`; its request schema requires both snapshot ID and digest. | No unbound THSS input is admitted, and a foreign-profile snapshot is rejected. | `services/api/src/clara_api/api/v1/endpoints/commitments.py`; `services/api/tests/test_commitment_endpoints_integration.py` |
| Commitment review API | Reviews a pre-existing human-governed proposal. | It does not create an alternative model-originated proposal route. | `services/api/src/clara_api/api/v1/endpoints/commitments.py` |

The generic assertion contract separately rejects an input that explicitly
declares `proposal_consumed_thss=true` while omitting its snapshot binding.
This audit does not prove every future route will preserve the invariant: any
new model-derived persistent-write route must either remain prohibited or use
the explicit binding contract and receive direct gateway plus API tests.
