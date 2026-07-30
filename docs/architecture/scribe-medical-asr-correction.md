# Medical-ASR correction (review-only)

`SCRIBE_MEDICAL_CORRECTION_ENABLED=false` is the default. When explicitly
enabled, the ML transcription endpoint calls the governed
`scribe_asr_correction` task contract only after it has a transcript. It emits
source-spanned correction proposals; it never alters the transcript, SOAP
draft, medication list, clinical code, or any confirmed record.

The correction contract accepts only bounded term candidates. Each proposal
must reference an exact transcript substring, cannot contain a numeric dose,
and is labelled `suggested_requires_clinician_review`. Invalid provider output,
timeouts, malformed JSON, absent source text, or disabled configuration result
in an empty/unavailable response—not an automatic heuristic rewrite.

This feature processes potentially sensitive transcript text. It is therefore
feature-gated, routed solely through the model registry, and must only be
enabled behind the existing Scribe consent gate. The endpoint returns no raw
provider exception and emits no transcript text to aggregate telemetry.

Rollback: set `SCRIBE_MEDICAL_CORRECTION_ENABLED=false`, restart the ML service,
and retain the original transcript. No migration or data repair is necessary
because correction suggestions are not persisted or applied automatically.
