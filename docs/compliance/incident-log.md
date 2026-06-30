# Incident Log — CLARA-Care

**Document status:** Living record · version-controlled
**Legal basis:** Law on Artificial Intelligence No. 134/2025/QH15 (serious-incident reporting); Decree 13/2023/NĐ-CP (PDPD) breach handling
**Last reviewed:** 2026-03

> Nhật ký sự cố. This log records serious incidents and safety events with
> severity, timestamp, and remediation status (Req 6.5). It is the human-readable
> companion to the append-only, PII-free `compliance_events` table (event type
> `incident`). **No entry in this log may contain personal data** — describe
> incidents by category, severity, and remediation only, referencing affected
> records by opaque/aggregate counts (Req 6.3, 7.4).

## Severity scale

| Severity | Meaning |
|---|---|
| `critical` | Patient-safety impact, confirmed data breach, or unlawful cross-border transfer |
| `high` | Guardrail bypass attempt, verification failure reaching a user, or significant availability loss |
| `medium` | Degraded behavior with a working safeguard (e.g. fallback engaged) |
| `low` | Minor anomaly, no user impact |

## Status values

`open` → `investigating` → `mitigated` → `resolved` (or `false_positive`).

## Recording procedure

1. On detection, append a row to the table below with a unique id (`INC-YYYY-NNN`), UTC timestamp, severity, category, a PII-free description, and the initial status.
2. Record a matching PII-free `compliance_events` row (`event_type=incident`, `severity=...`) via `ComplianceService.record_event`.
3. For `critical`/`high` incidents involving personal data, assess regulator-notification obligations under PDPD and AI Law 134/2025.
4. Update the status and remediation as the incident progresses; never delete a row (append-only spirit).

## Incident categories (reference)

- `guardrail` — legal hard-guard / emergency fast-path / FIDES CRITICAL block behavior
- `cross_border` — offshore transfer gating or consent-gate anomaly
- `data_protection` — suspected PII exposure in logs/telemetry, or DSAR mishandling
- `availability` — model/provider outage, fallback engagement
- `access_control` — RBAC / CSRF / authentication anomaly

## Log

| ID | Timestamp (UTC) | Severity | Category | Description (no PII) | Status | Remediation |
|---|---|---|---|---|---|---|
| — | — | — | — | _No incidents recorded._ | — | — |

<!--
Append new rows above this comment. Example shape:
| INC-2026-001 | 2026-03-15T08:42:00Z | high | cross_border | Outbound LLM call attempted without cross_border consent while gating enabled; blocked by guard, degraded to local fallback for N sessions | resolved | Confirmed gate behaved correctly; added monitoring alert |
-->

## Review schedule

Reviewed monthly and after any `critical`/`high` incident. The open-incident
count is surfaced to authorized admins only via the compliance records manifest;
end users never see this log (Req 6.6).
