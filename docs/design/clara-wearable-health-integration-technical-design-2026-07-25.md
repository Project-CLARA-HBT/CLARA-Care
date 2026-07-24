# CLARA Wearable and Health Data Integration

## Technical Design

Status: implementation-ready
Version: 1.0
Date: 2026-07-25
Applies to: CLARA Flutter mobile app and FastAPI platform
Parent specification:
[CLARA Viet Nam Personal Health Assistant](clara-vietnam-personal-health-assistant-unified-spec-2026-07-25.md)
Execution backlog:
[Wearable and Health Data Implementation Task List](clara-wearable-health-integration-task-list-2026-07-25.md)

## 1. Decision

CLARA will use a connector architecture, not a generic "Google Health" adapter.

| Integration | Role | First release |
|---|---|---|
| Android Health Connect | Read health and fitness history aggregated on the user's Android device | Yes |
| Huawei Health / Health Kit | Read Huawei Health and Huawei wearable data with user authorization | Yes, after scope approval |
| Fitbit Web API | Read Fitbit cloud history through user OAuth | Feature-flagged |
| Wear OS Health Services | Capture data for an approved CLARA watch-native experience | No; design-compatible only |
| Legacy Google Fit APIs | Legacy migration only | No new integration |

Health Connect is part of Android 14 and is an app dependency on older supported
Android versions. Its documentation recommends aggregated reads for cumulative
types such as steps to prevent double counting. Google states that Google Fit
APIs are supported only through the end of 2026, so CLARA must not create a new
dependency on them.

Huawei Health Kit supports Android, iOS, web and HarmonyOS access modes, but
availability varies by data type, device, country, developer status and approved
scope. The extended device-side service can read local Huawei Health data with
consent; some advanced types require an enterprise developer.

Wear OS Health Services is a sensor and exercise API for a watch app. It is not a
substitute for Health Connect history. CLARA will build a watch module only after
a specific consumer outcome justifies real-time or passive collection.

## 2. Goals

- Make wearable connection an optional, valuable part of Getting Started.
- Import real records with consent, provenance, freshness and revocation.
- Normalize sources without hiding device/origin differences.
- Prevent duplicate steps and mixed-source trend artifacts.
- Make a small set of signals available to LifeMap and the medical-answer
  harness safely.
- Support connector pause, disconnect, reauthorization and imported-data
  deletion.
- Degrade honestly when a device, permission, account or vendor is unavailable.

## 3. Non-goals

- Diagnosing from a wearable signal.
- Claiming continuous clinical monitoring.
- Reading all data types during onboarding.
- Writing data back to vendor platforms in the first release.
- Treating absence of a record as a normal value.
- Combining all providers into an opaque average.
- Building a watch app only to import historical data.
- Adding Google Fit as a new data source.

## 4. Current-system fit

Relevant implementation surfaces:

```text
apps/mobile/
  lib/core/
  lib/experience/
  lib/screens/
  android/app/src/main/

services/api/
  src/clara_api/api/v1/endpoints/
  src/clara_api/db/models.py
  src/clara_api/phr/
  src/clara_api/core/config.py
  alembic/versions/
  tests/
```

The Flutter app owns device capability detection, platform permission prompts and
device-side reads. FastAPI owns connector state, canonical validation,
provenance, idempotency, retention, LifeMap projection and AI-context release.
Fitbit OAuth and cloud synchronization are server-side.

## 5. Architecture

```text
Huawei Health              Health Connect
     |                           |
     +--> native Android adapter +
                 |
          Flutter connector SDK
                 |
        encrypted authenticated batch
                 |
                 v
CLARA API -> Connector Ingestion -> Canonical Validator -> Idempotency/Dedup
                                                        -> Observation Store
                                                        -> Aggregate Projector
                                                        -> LifeMap Projection
                                                        -> Decision Ledger

Fitbit OAuth -> CLARA callback -> encrypted token vault -> Fitbit sync worker
                                                     -> Connector Ingestion

Wear OS Health Services -> future watch module -> approved event/record contract
```

### 5.1 Module boundaries

Mobile:

```text
HealthSourceCapabilityService
ConnectorConsentController
HealthConnectAdapter
HuaweiHealthAdapter
ConnectorImportCoordinator
ConnectorStatusStore
ConnectedHealthScreen
GettingStartedHealthStep
```

Backend:

```text
connected_health/api.py
connected_health/schemas.py
connected_health/service.py
connected_health/providers/base.py
connected_health/providers/fitbit.py
connected_health/normalization.py
connected_health/deduplication.py
connected_health/aggregation.py
connected_health/projection.py
connected_health/retention.py
connected_health/audit.py
```

Provider adapters cannot directly update PHR/LifeMap tables. All inputs cross the
same canonical validation and release boundary.

## 6. Getting Started UX

### 6.1 Flow

```text
Goal selection
  -> capability scan
  -> "Kết nối dữ liệu sức khỏe" (optional)
  -> source choice
  -> benefit and data-type disclosure
  -> platform/vendor authorization
  -> first bounded import
  -> review imported categories and freshness
  -> first useful Hôm nay state
```

The source cards show:

- provider and account/device;
- categories requested;
- why CLARA needs each category;
- read-only status;
- expected history window;
- last synchronization;
- "Để sau" and "Tiếp tục không kết nối".

Partial authorization is a valid success state. Denial must return the user to the
flow without guilt language or repeated prompts.

### 6.2 First-value rules

- Import only data connected to the chosen goal.
- Default initial window is 30 days.
- Show one neutral observation such as a trend or data-coverage summary.
- Do not issue a medical recommendation merely because connection succeeded.
- If data is too sparse, say what was connected and wait for more data.

## 7. Platform adapters

### 7.1 Health Connect

Implement a small first-party Kotlin bridge under the Flutter Android host. A
first-party bridge is preferred to an unreviewed broad Flutter plugin because
CLARA needs exact control of permissions, metadata, change tokens and provenance.

Adapter responsibilities:

- check SDK and feature availability;
- expose supported record types;
- request only the approved read permissions;
- read granted permissions before every sync;
- use change-token/incremental synchronization where supported;
- use `aggregate()` for steps and other cumulative metrics;
- preserve Health Connect ID, client ID/version, data origin, device, recording
  method and time-zone offsets;
- expose deleted/upserted changes;
- never request write permissions in the initial release.

Android 14+ uses the framework module. Supported older Android devices use the
Health Connect app. Historical access beyond the default window requires the
separate history permission and a visible user need.

### 7.2 Huawei Health

Build a separate Kotlin HMS adapter with product-flavor-safe dependencies so
GMS-only builds remain testable. Before implementation commitment:

1. register/verify the Huawei developer organization;
2. create the application identity and signing configuration;
3. request the minimum Health Kit/Health Service scopes;
4. confirm Vietnam, device and Huawei Health version support;
5. document which requested types require enterprise review;
6. test on Huawei and non-Huawei Android phones.

The adapter exposes the same canonical interface as Health Connect but retains
Huawei record IDs, data type, device/source, timestamps and API version.
Limitations on background operation on third-party phones must appear as
connector status, not as a false "no change" signal.

### 7.3 Fitbit

Fitbit is a server-mediated OAuth connector:

1. mobile requests an authorization transaction;
2. backend creates signed `state`, PKCE when supported by the active vendor
   authorization profile, and a short-lived transaction;
3. system browser opens Fitbit consent;
4. callback validates state and exchanges the authorization code;
5. encrypted tokens are stored outside application logs;
6. worker performs bounded backfill and incremental sync;
7. revocation invalidates tokens and connector state.

Client Credentials is used only for Fitbit application-level API access where
documented; it cannot grant access to a consumer's data. Fitbit rate limits and
scope review drive the sync schedule. Direct Fitbit connection is not needed when
the required records already reach Health Connect and the user selects that
origin.

### 7.4 Wear OS

Do not build a watch module in the first connector milestone. Preserve an
interface for a future Wear OS module using:

- `PassiveMonitoringClient` for infrequent background signals;
- `MeasureClient` for short foreground measurement;
- `ExerciseClient` for CLARA-owned workout sessions.

A future module needs its own battery budget, watch UX, permissions, device
capability matrix, accuracy limits and clinical intended use. Raw sensor streams
must not be uploaded merely because they are available.

## 8. Canonical data contract

```json
{
  "schema_version": "1.0",
  "profile_id": "prof_...",
  "connector_id": "con_...",
  "provider": "health_connect|huawei_health|fitbit|wear_os",
  "provider_record_id": "opaque",
  "record_type": "steps|heart_rate|resting_heart_rate|sleep|weight|blood_pressure",
  "value": {"scalar": 72.0, "unit": "beats/min"},
  "observed_start": "2026-07-24T01:00:00Z",
  "observed_end": "2026-07-24T01:00:05Z",
  "zone_offset_start": "+07:00",
  "zone_offset_end": "+07:00",
  "data_origin": "package-or-vendor",
  "device": {"manufacturer": "string", "model": "string", "type": "watch"},
  "recording_method": "automatic|active|manual|unknown",
  "provider_updated_at": "timestamp-or-null",
  "ingested_at": "server timestamp",
  "quality": {"state": "source_asserted", "flags": []},
  "provenance": {"adapter_version": "string", "raw_hash": "sha256"}
}
```

Provider record IDs are opaque and unique only within provider/origin. The server
rejects unknown schema versions and impossible intervals/units. Raw payloads are
retained only when explicitly required for replay and under a short,
documented retention policy.

## 9. Persistence

New tables:

```text
connector_accounts
connector_consents
connector_sync_cursors
connector_import_batches
wearable_observations
wearable_observation_versions
wearable_aggregate_contributions
wearable_daily_aggregates
connector_audit_events
oauth_authorization_transactions
```

Key constraints:

- every row has user, profile and connector scope;
- `(connector_id, data_origin, provider_record_id, version)` is unique;
- batches have an idempotency key and payload hash;
- tokens are envelope-encrypted and never returned by APIs;
- deletes are tombstoned for replay, then purged under retention policy;
- aggregate rows list contributing observation IDs/origin policy;
- PHR projections reference wearable source rows rather than copying
  unattributed values.

## 10. Synchronization and deduplication

### 10.1 State machine

```text
available -> authorizing -> connected -> syncing -> healthy
                                      -> partial
                                      -> stale
                                      -> needs_reauth
                                      -> paused
                                      -> revoked
                                      -> error
```

### 10.2 Import protocol

- Mobile creates a batch with idempotency key.
- Server validates authorization and purpose.
- Records are schema-validated and unit-normalized.
- Upserts and tombstones are applied transactionally per page.
- Cursor advances only after durable commit.
- Projection jobs run through an outbox.
- Partial pages return a resumable cursor.

### 10.3 Duplicate-origin policy

Exact provider IDs are idempotent. Fallback fingerprints are advisory and contain
record type, origin, device, interval and normalized value. Similar records from
different origins are not deleted.

For daily cumulative metrics:

1. prefer the provider's supported aggregation API;
2. otherwise select one configured primary origin per metric/day;
3. never sum overlapping totals from multiple apps;
4. record contributing origin and coverage;
5. let the user change the preferred source;
6. recompute affected aggregates deterministically.

For point/series measurements, preserve all samples and label origin. Trend
rendering may select a stable source but must not imply that other sources were
equivalent.

## 11. API design

```text
GET    /api/v1/connectors/capabilities
GET    /api/v1/connectors
POST   /api/v1/connectors/device
POST   /api/v1/connectors/{id}/imports
POST   /api/v1/connectors/{id}/sync
POST   /api/v1/connectors/{id}/pause
POST   /api/v1/connectors/{id}/resume
DELETE /api/v1/connectors/{id}
DELETE /api/v1/connectors/{id}/imported-data

POST   /api/v1/connectors/fitbit/authorizations
GET    /api/v1/connectors/fitbit/callback

GET    /api/v1/profiles/{profile_id}/wearable-observations
GET    /api/v1/profiles/{profile_id}/wearable-aggregates
PUT    /api/v1/profiles/{profile_id}/wearable-source-preferences
```

Device import requests include profile, connector, schema version, batch cursor
and records. Responses return accepted/rejected counts, per-record safe errors,
next cursor and projection status. They never return provider secrets or raw
internal diagnostics.

## 12. Consent, deletion and security

- Connector consent is separate from CLARA terms and AI-context consent.
- Data types and purposes are versioned.
- Using wearable data for Ask CLARA requires the corresponding active purpose.
- Revocation blocks new reads immediately.
- Disconnect and delete are separate, clearly explained actions.
- Imported-data deletion removes projections, aggregates and cached context, then
  records an audit tombstone.
- OAuth tokens use envelope encryption and least-privilege scopes.
- Mobile secrets use platform secure storage; vendor client secrets never ship in
  the app.
- Connector payloads are excluded from analytics, crash logs and model-training
  data by default.
- Background jobs re-check profile access and consent before every page.
- Support tooling shows metadata and state, not raw health values by default.

Health Connect integration must complete Google Play Data Safety and Health apps
declarations, provide the same privacy policy from the platform permission
rationale, and justify every requested type with a visible feature.

## 13. Medical-answer harness integration

Connected data enters the context compiler only through typed facts:

```text
metric
value/range
source
device/origin
observed interval
freshness
coverage
recording method
quality flags
personal baseline comparison
```

The compiler must:

- retrieve only metrics relevant to the active question;
- prefer trends over isolated consumer-device values;
- expose missing days and source switches;
- reject stale or ambiguous-time intervals from decisive use;
- prevent absence-of-data from becoming a negative finding;
- label wearable observations as non-diagnostic;
- require corroboration for material clinical recommendations;
- log every used observation/aggregate in the Decision Ledger.

No raw time series is inserted wholesale into an LLM prompt. Deterministic
aggregation and anomaly characterization run first; the model explains the
bounded artifact.

## 14. Reliability and observability

Initial SLOs:

- connector control-plane API availability: 99.9%;
- accepted import batch durability: 99.99%;
- idempotent replay produces no duplicate canonical records: 100%;
- revocation enforcement for new reads: under 60 seconds;
- healthy device connector freshness: under 24 hours after app opportunity;
- Fitbit sync freshness: under 6 hours when vendor service and token are healthy;
- user-visible connector state reflects a detected failure: under 15 minutes.

Metrics contain no raw values:

- authorization completion/denial;
- permission category counts;
- batch latency and rejection class;
- cursor age;
- records by type/provider;
- duplicate/upsert/tombstone counts;
- aggregate recomputation;
- stale and reauthorization rates;
- downstream recommendations using connected data;
- corrections and safety incidents.

Alerts:

- sync failure or authorization failure spike;
- cursor stalled;
- vendor schema/data-type change;
- duplicate rate change;
- implausible unit/value rejection spike;
- revocation job lag;
- projection drift between source and LifeMap.

## 15. Testing

### 15.1 Automated

- adapter contract tests;
- schema and unit property tests;
- batch idempotency/replay;
- overlapping-step deduplication;
- source-preference recomputation;
- time-zone and daylight-saving boundaries;
- permission partial/deny/revoke;
- cross-profile authorization;
- token encryption and log-redaction;
- deletion cascade and DSAR export;
- context compiler excludes stale/unauthorized records.

Synthetic platform records are allowed only in automated/non-production tests and
must be labeled. Production E2E uses consenting test accounts and real devices.

### 15.2 Device matrix

Minimum:

- Android 14+ device with framework Health Connect;
- supported pre-Android 14 device with Health Connect app;
- Huawei phone with Huawei Health and HMS;
- non-Huawei Android phone with Huawei Health;
- at least one Huawei wearable;
- at least one Wear OS device writing through a compatible app to Health Connect;
- Fitbit test account/device when the cloud connector is enabled.

Test empty, sparse, overlapping, revoked, stale, manual and auto-recorded data.

### 15.3 Safety scenarios

- elevated consumer-device heart rate without symptom context;
- source switch that creates a false step/sleep change;
- missing synchronization mistaken for inactivity;
- manually entered blood pressure mixed with device readings;
- time-zone travel;
- duplicated Huawei data also present in Health Connect;
- connector revoked while an answer job is running.

## 16. Rollout

Feature flags:

```text
clara_connected_health_ui
clara_health_connect_read
clara_huawei_health_read
clara_fitbit_oauth
clara_wearable_lifemap_projection
clara_wearable_answer_context
clara_wear_os_companion
```

Rollout sequence:

1. internal capability detection;
2. import shadow store without user-facing recommendations;
3. staff real-device pilot;
4. LifeMap read-only projection;
5. Hôm nay trends;
6. answer-context shadow evaluation;
7. small consumer cohort;
8. wider release after safety and policy approval.

Rollback stops new reads and projections but preserves user control, audit,
revocation and deletion.

## 17. External gates

The following are blocking dependencies, not engineering assumptions:

- Huawei developer organization and approved scopes;
- production signing identities registered with Huawei;
- Google Play Health apps declaration and data-type approval;
- public privacy policy matching in-app disclosures;
- Fitbit app registration, redirect URIs and approved scopes;
- legal decision on retention and cross-border processing;
- clinical intended-use approval for each use of wearable data;
- real test devices and consenting test accounts.

If a gate is missing, the connector remains unavailable or shadow-only. CLARA
must not emulate a vendor response or substitute fake production data.

## 18. Primary references

- [Huawei Health Kit](https://developer.huawei.com/consumer/en/hms/huaweihealth/)
- [Huawei extended Health Service capabilities](https://developer.huawei.com/consumer/en/doc/HMSCore-Guides/extended-introduction-0000001050060843)
- [Health Connect getting started](https://developer.android.com/health-and-fitness/health-connect/get-started)
- [Health Connect data types](https://developer.android.com/health-and-fitness/health-connect/data-types)
- [Publishing a Health Connect app](https://developer.android.com/health-and-fitness/health-connect/publish)
- [Google Play health-permission policy](https://support.google.com/googleplay/android-developer/answer/16558241)
- [Wear OS Health Services](https://developer.android.com/health-and-fitness/health-services)
- [Fitbit Web API authorization](https://dev.fitbit.com/build/reference/web-api/authorization/)
- [Fitbit Web API explorer](https://dev.fitbit.com/build/reference/web-api/explore/)
