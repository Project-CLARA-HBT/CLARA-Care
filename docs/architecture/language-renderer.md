# Structured language renderer and fidelity gate

`services/ml/src/clara_ml/language_renderer/` is the shared wording boundary
for health responses. It is deliberately downstream of deterministic policy,
DrugBank/FIDES checks and claim verification: it cannot create a clinical fact,
change urgency, authorize access, prescribe, or confirm a LifeMap record.

## Contract and release path

`RenderingInput` has bounded `severity` and action codes, mandatory warnings,
uncertainty state and source labels. The current renderer is deterministic and
uses Vietnamese plain-language templates for `lay_vi`/`caregiver_vi`, with
separate clinician/researcher and English audiences. It does not pass raw
model prose into a patient explanation.

`verify_fidelity` is independent deterministic code. It rejects a missing
emergency signal, a missing mandatory warning, softened high uncertainty,
dose text, and unapproved prescribing wording. If a future generative renderer
fails that gate, the service must return the deterministic template with
`fallback_used=true`; it must not release the candidate or invent a quality
score. Prompt contract version is `language-renderer-contract-v1`.

`medical_answer_v2` now includes `rendered_explanation` generated from the
released semantic contract. Existing `answer`, evidence, emergency and
CareGuard fields remain the authoritative API payload for backwards
compatibility.

## Operational controls and rollback

The deterministic renderer does not call an external provider and has no model
or personal-data telemetry. To roll back this additive payload, deploy the
prior application commit. Do not remove the underlying policy, evidence,
DrugBank or emergency gates. Any future model-backed renderer must be routed
through the model registry, expose a versioned task contract, be feature gated,
and be evaluated with the `wording_usability` CLARA-Eval track before release.

## Validation

```bash
PYTHONPATH=services/ml/src services/api/.venv/bin/python -m pytest -q \
  services/ml/tests/test_language_renderer.py \
  services/ml/tests/test_medical_answer_v2.py
PYTHONPATH=services/ml/src services/api/.venv/bin/python -m mypy \
  services/ml/src/clara_ml/language_renderer \
  services/ml/src/clara_ml/medical_answer_v2.py
```
