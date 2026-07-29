# Scribe safety presentation

The Scribe interface does not infer diagnosis/procedure codes from transcript
keywords and does not assign fallback `R69`. It also no longer renders a
synthetic percentage derived from SOAP field coverage or session statistics as
“AI confidence”.

The interface instead makes the review boundary explicit: clinicians or other
authorized users must verify the transcript, warnings and draft SOAP, then
select any code in the appropriate clinical workflow. ASR/provider confidence,
when available, remains internal quality evidence and is not a calibrated
clinical-confidence score for end users.

Regression coverage: `apps/web/lib/scribe-safety-ui.test.ts` asserts that the
removed auto-code and fabricated-confidence paths cannot be reintroduced
silently.
