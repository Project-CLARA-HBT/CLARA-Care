# LifeMap Living Evidence monitor

Owner: Platform/SRE

Clinical owner: Clinical Safety

Status: deployable dark worker; default OFF

## Safety contract

`evidence-monitor` runs only when `LIFEMAP_EVIDENCE_MONITOR_ENABLED=true`.
Before enabling it, migration `20260729_0039` must be current and the Phase
10.8 citation-validity, contradiction-sensitivity, applicability-precision,
notification-usefulness, and stale-evidence evaluations must be approved.

The worker never turns new search results directly into a consumer
notification. It records stable source checkpoints and a versioned change
assessment. A doctor or admin must accept a candidate material change while
the owner subscription and medical consent are still active. The notification
contains only opaque references and bounded safe copy.

## Operations

The worker runs `python -m clara_api.lifemap.evidence_worker` every 30 seconds.
It uses leased `FOR UPDATE SKIP LOCKED` claims, hour-bucket dedupe, five bounded
attempts, exponential backoff, and a terminal dead-letter state. Revoking a
subscription cancels pending, retry, and processing jobs; consent is rechecked
at scheduling, claim, and notification time.

Monitor only aggregate counts by status, oldest due age, expired leases,
attempt distribution, cycle duration, and accepted/rejected assessment counts.
Never log question text, profile facts, citation excerpts, names, emails, or
medication lists.

## Staged enablement

1. Keep the flag OFF and deploy migration, API, web/mobile clients, and worker.
2. Verify the worker remains idle and subscriptions show the dark-state label.
3. Run the Phase 10.8 frozen evaluation set in a non-production environment.
4. Obtain Clinical Safety and SRE approval, record rule/model versions, then
   enable for an internal cohort.
5. Confirm dedupe, lease recovery, reviewer queue latency, notification
   usefulness, and absence of PII in logs before expanding.

## Incident response and rollback

Set `LIFEMAP_EVIDENCE_MONITOR_ENABLED=false` first. This stops new scheduling
without deleting subscriptions, checkpoints, assessments, or notifications.
Allow processing leases to expire or scale the worker to zero if stopping
immediately is safer. Do not truncate or rewrite monitor tables.

For a dead letter, record only its opaque job reference and failure code.
Restore the dependency or deploy the fix before any bounded replay. If consent
or authorization is unavailable, cancel rather than replay. Rollback of the
application does not require migration downgrade; retain the durable ledger.
