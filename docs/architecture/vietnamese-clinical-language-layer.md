# Vietnamese Clinical Language Layer v1

`clara_ml.nlp_vi` provides the shared typed `ClinicalUtterance` packet for
Vietnamese clinical text. It normalizes common variation and exposes bounded
cues for negation, experiencer, temporality, severity, lab shorthand,
allergy/adverse-effect wording, medication candidates, and emergency wording.

The current implementation is explicitly `deterministic_fallback_v1`; it is
not labelled an encoder, neural model, or calibrated clinical classifier. It
does not diagnose, prescribe, decide access, or confirm a record. The task
router uses its category/count projection only; free text does not enter
aggregate route telemetry.

An encoder SLM may replace individual extractors behind this contract after a
versioned dataset, offline evaluation, shadow comparison and release gate are
available. Deterministic emergency/legal/consent/DrugBank policy remains
authoritative regardless of that future model.
