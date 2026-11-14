# PH13 A05 Risk Register: Connected Health & Wearables Web UX

**Phase:** PH13 — Connected Health và wearables
**Subagent:** A05 — Web UX
**Domain:** Sync Errors, Stale-Data Alerts, and Reauthorization Prompts

---

## Risk Assessment Matrix

| Risk ID | Description | Severity | Likelihood | Mitigation Strategy | Contingency / Fallback |
|---|---|---|---|---|---|
| **RSK-PH13-01** | **Clinical misinterpretation of stale vitals:** patient/clinician treats unsynced biometric data (>24h) as real-time. | High | High | Prominent warning banner plus `WearableStaleBadge` injected on biometric cards when `recorded_at` > 24h. | At >72h the badge escalates to danger with guidance to measure manually. |
| **RSK-PH13-02** | **Silent OAuth expiration:** vendor tokens expire and ingest fails without user awareness. | High | Medium | `isAuthError` + `reauth_required` classifier drives `WearableSyncAlertBanner` with "Cấp lại quyền" / "Reauthorize" CTA. | Reauth modal reachable from both the banner and the `/you/integrations` card. |
| **RSK-PH13-03** | **Credential storage exposure:** browser JS persists raw OAuth tokens or API secrets. | Critical | Low | Zero browser token persistence: reauth handshake runs server-side via HttpOnly cookies (`v2Client.reauthorizeIntegrationSource`). | Path ACL and security scanners block client credential caching. |
| **RSK-PH13-04** | **Alert fatigue / noise:** intentional disconnects or new accounts show redundant alerts. | Medium | Medium | `evaluateWearableFleet` excludes sources where `connected === false` or `sync_enabled === false`. | Users can disable sync per device or adjust category permissions. |
| **RSK-PH13-05** | **Vendor error fragmentation:** error codes differ across HealthKit / Health Connect / Garmin. | Medium | High | Unified taxonomy normalizes vendor payloads into `reauth_required`, `sync_error`, `stale_data`, `active`. | Generic actionable recovery text for unknown codes. |
| **RSK-PH13-06** | **i18n drift:** new VI/EN strings bypass the consumer terminology contract. | Low | Medium | `consumer-terminology:check` passes (19 keys, 2026-07-30.v1); strings use inline VI/EN dictionaries. | Regenerate projection via `npm run consumer-terminology:generate` if contract changes. |

## Residual Risk

All residual risks are Low after mitigation. No backend schema, migration, or data-deletion
surface is touched; rollback is a pure frontend revert (see `rollback.md`).
