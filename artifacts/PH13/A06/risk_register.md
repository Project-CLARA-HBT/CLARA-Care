# Risk Register — PH13 A06 (Connected Health và wearables — Mobile)

## Scope

Mobile Connected Health surface: supported wearable/provider catalog (Health Connect, Huawei Health, Fitbit, Garmin), manual sync trigger, sync pause/resume toggle, connect flow via `POST /api/v1/connectors/device`, plus sync status display and error surfacing.

## Risks

| ID | Severity | Risk | Mitigation | Residual |
|---|---|---|---|---|
| R1 | Medium | Connect flow sends `external_subject_ref` derived from provider id (`<provider>-mobile-ref`) rather than a native account identifier; could create duplicate connectors if a user re-connects from another install. | Server-side connector dedupe/consent gate remains authoritative; UI re-fetches the source list after connect and hides already-connected providers from the catalog. | Low–Medium |
| R2 | Medium | `_connectProvider` triggers real connector creation with the default `consent_version` (`1.0`) and `personal_health_assistance` purpose; a stale consent version will surface as `ApiException` message to the user. | Error message is surfaced via snackbar; no silent success. Consent version must be kept aligned with the API contract. | Low |
| R3 | Low | Manual sync button is disabled while paused or already syncing, but rapid repeated taps across multiple cards could issue parallel sync requests. | Per-connector `_syncingIds` guard prevents duplicate in-flight sync for the same connector; backend lease/lock semantics protect the rest. | Low |
| R4 | Low | Provider availability is inferred by lower-casing `provider` strings from the API; an unknown provider value will not match the catalog and will not be filtered. | Unknown providers still render as source cards; catalog matching is best-effort presentation only. | Low |
| R5 | Low | Localization: new provider descriptions and button labels are inline vi/en strings rather than centralized terminology keys, which may drift from `ConsumerTerminology`. | Titles/actions inherited from existing terminology remain; follow-up should migrate new strings into the terminology contract. | Low |
| R6 | Low | Widget tests use `MockClient`; they validate client-side wiring, not real device/cloud authorization behavior. | Existing API/contract tests cover server behavior; native bridge authorization is exercised elsewhere. | Low |
| R7 | Info | `flutter pub get` rewrote `pubspec.lock` (sky_engine marker) in the worktree; reverted before commit. | Lockfile diff excluded from commit; no dependency drift introduced. | None |

## Safety Invariants

- No change to consent gate ordering: the screen still lists sources only after authenticated session; connect actions require an access token.
- No PII added to telemetry; sync messages use display labels already present in the API response.
- No change to RBAC, emergency fast-path, FIDES, or legal hard-guard paths (mobile-only client changes).
