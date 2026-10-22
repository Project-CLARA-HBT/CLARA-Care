# PHI-Minimized Event Payload Security & Telemetry Architecture (PH09)

## Executive Summary
This research specification formalizes the data minimization principles, cryptographic tokenization, and schema invariants applied to all transactional outbox events in The CLARA Care.

## Invariant 1: Complete Elimination of Raw PHI
In accordance with PDPD Vietnam (Decree 13/2023/ND-CP) and HIPAA Safe Harbor guidance:
- Outbox event payloads must **never** contain plaintext patient identifiers (names, phone numbers, CCCD / Citizen ID, physical addresses, emails).
- Raw medical observation transcripts or unredacted clinical consultation audio are strictly prohibited from event payloads.

## Invariant 2: Pseudonymized UUID Reference Architecture
Events emit strictly pseudonymized identifiers:
- `profile_public_id`: Random UUIDv4 identifying the patient profile without revealing account details.
- `aggregate_id`: UUIDv4 referencing the modified domain entity (e.g. `commitment_public_id`).
- `event_type`: Categorical action string (e.g. `medications.course.created`).

## Downstream Consumer Ingestion Contract
When an external or background subscriber (such as an analytics pipeline or ML vector backfill job) processes an event:
1. It reads the public UUID from the event payload.
2. It authorizes itself with an internal service token and queries the API Gateway through authenticated, role-scoped, and audit-logged read routes.
3. It never receives unconsented or ambient data leakage through the message queue.
