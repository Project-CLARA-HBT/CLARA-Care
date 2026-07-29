# Runbook: LifeMap ML drift, provider and artifact incidents

## Immediate fail-closed triggers

Pause the affected use-case flag and select its deterministic fallback when an
artifact signature/checksum fails, a provider alias resolves differently, the
provider reports an unexpected model ID, schema compatibility fails, consent or
grant context cannot compile, OOD/abstention exceeds its approved threshold,
calibration becomes invalid, or a no-PII telemetry invariant fails.

Do not auto-retrain, auto-promote, silently change providers, or weaken the
validator.

## Triage

1. Identify the stable use-case, deployment, model, feature-schema and dataset
   versions from immutable manifests.
2. Stop cohort expansion; for a critical safety signal, disable the flag.
3. Preserve content-free operational evidence and the access-controlled private
   lineage manifest. Never paste health content into incident chat or metrics.
4. Verify artifact bytes/signature/key status and provider-reported identity.
5. Compare schema, missingness, source/device/language/population/temporal
   distribution, OOD, abstention, calibration, safety blocks, overrides,
   latency and dependency errors with the approved baseline.
6. Open privacy/security/clinical review according to the affected risk class.

## Recovery

Prefer the last signed, approved immutable champion. If it is implicated, use
the deterministic fallback or mark the capability unavailable. Re-enable only
after the triggering condition is understood, the required frozen evaluations
pass, the hazard/change record is updated, and accountable owners approve a
bounded cohort.

## Recall and withdrawal

Mark the deployment/artifact `recalled` by appending a new registry record;
never rewrite history. Invalidate derived projections and notifications by
their dependency links, preserve audit evidence, apply dataset
withdrawal/deletion lineage, and determine whether retraining or artifact
retirement is required.
