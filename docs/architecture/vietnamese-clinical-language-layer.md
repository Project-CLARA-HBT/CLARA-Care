# Vietnamese Clinical Language Layer v1

`services/ml/src/clara_ml/nlp/vietnamese_clinical.py` is a deterministic,
auditable pre-processing layer for Vietnamese clinical text. It retains the
original text and emits normalized/folded text plus non-authoritative language
cues: negation, experiencer, temporality, severity phrasing, units and a small
medication-alias candidate set.

It is deliberately **not** described as an SLM, neural model or clinical
classifier. It must not diagnose, prescribe, choose access rights, write
confirmed LifeMap state, replace DrugBank, or override the emergency fast-path.
The existing router uses the same accent/stroke folding helper to prevent a
Vietnamese spelling such as `đột quỵ` from bypassing deterministic emergency
matching.

Medication candidates are only an input to later clarification/DrugBank
normalization. They are not a verified ingredient or DDI result. Ambiguous
inputs remain unresolved and must be confirmed through the authoritative
CareGuard source.

Run the focused tests:

```bash
PYTHONPATH=services/ml/src pytest -q \
  services/ml/tests/test_vietnamese_clinical.py \
  services/ml/tests/test_router.py
```
