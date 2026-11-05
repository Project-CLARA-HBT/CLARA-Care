# Wearable Vendor Integration Boundaries & Interoperability Data Flows

- **Phase ID**: PH13 (Connected Health và wearables)
- **Agent ID**: A09
- **Role**: Docs + research evidence
- **Target Subsystem**: `services/api/src/clara_api/connected_health/` & `contracts/`
- **Applicable Standards**: FHIR R4 (HL7), Decree 13/2023/ND-CP, LOINC, UCUM
- **Status**: **ACTIVE INTEROPERABILITY SPECIFICATION**

---

## 1. System Integration Boundaries

To maintain rigorous clinical safety and data integrity, external vendor data sources must never bypass CLARA's canonical normalization boundary:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       INTEROPERABILITY BOUNDARY MAP                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  VENDOR ECOSYSTEMS                                                          │
│  • Google Health Connect (Android Health API)                               │
│  • Huawei Health Kit (HMS Core Health Service)                              │
│  • Fitbit Web API (Google Cloud REST API)                                   │
│  • Apple HealthKit (iOS HKHealthStore)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                      │                                      │
│                                      ▼                                      │
│  CANONICAL NORMALIZATION GATEWAY (clara_api.connected_health.schemas)        │
│  • Format translation to CanonicalHealthRecord                              │
│  • UTC timestamp and time-zone normalization (+07:00 default)               │
│  • UCUM unit translation (e.g. kcal -> J, lbs -> kg, mg/dL -> mmol/L)       │
│  • Immutability and payload hash (sha256) registration                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                      │                                      │
│                                      ▼                                      │
│  DEDUPLICATION & PRECEDENCE ENGINE (clara_api.connected_health.projection)   │
│  • Cross-origin step deduplication (Watch primary over Phone)               │
│  • Resolution of temporal overlap across simultaneous trackers              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                      │                                      │
│                                      ▼                                      │
│  CLARA HEALTH GRAPH (LifeMap & FHIR R4 Export)                              │
│  • Projection into LifeMap longitudinal timeline                            │
│  • HL7 FHIR R4 Observation & Device mapping                                 │
│  • Decision Ledger registration before Clinical Decision Support context    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Canonical Data Contract & Vendor Record Mapping

CLARA standardizes all incoming biometric observations into a uniform JSON schema (`CanonicalHealthRecord`).

### 2.1 Supported Record Types & Physiological Bounds

| `HealthRecordType` | Canonical Unit | Valid Value Range | Physiological Bounds Invariant |
|---|---|---|---|
| `steps` | `count` | 1 to 50,000 / batch | Non-negative integer scalar; duration >= 0s |
| `activity` | `kcal` | 0.0 to 5,000.0 | Active energy burned; requires interval |
| `heart_rate` | `beats/min` | 20.0 to 300.0 | Instantaneous or short-window average |
| `resting_heart_rate` | `beats/min` | 30.0 to 200.0 | Daily resting metric; single point/day |
| `sleep` | `minutes` | 0.0 to 1,440.0 | Deep, light, REM, or awake sleep session |
| `weight` | `kg` | 1.0 to 500.0 | Body mass; converted from lbs if needed |
| `body_fat` | `percent` | 1.0 to 75.0 | Percentage of total body mass |
| `blood_pressure` | `mmHg` | Systolic: 50-300<br>Diastolic: 30-200 | Compound measurement (`systolic`, `diastolic`) |
| `blood_glucose` | `mmol/L` | 1.0 to 45.0 | Converted from mg/dL if provided |
| `oxygen_saturation` | `percent` | 50.0 to 100.0 | Peripheral capillary SpO2 |
| `body_temperature` | `degC` | 30.0 to 45.0 | Core or skin temperature in Celsius |

### 2.2 Vendor Type Translation Matrix

| CLARA Record Type | Android Health Connect | Huawei Health Kit | Fitbit Web API | Apple HealthKit | LOINC Code |
|---|---|---|---|---|---|
| `steps` | `StepsRecord` | `DT_CONTINUOUS_STEPS_TOTAL` | `activities/steps` | `HKQuantityTypeIdentifierStepCount` | `55423-8` |
| `heart_rate` | `HeartRateRecord` | `DT_INSTANTANEOUS_HEART_RATE` | `activities/heart` | `HKQuantityTypeIdentifierHeartRate` | `8867-4` |
| `resting_heart_rate`| `RestingHeartRateRecord`| `DT_RESTING_HEART_RATE` | `activities/heart (resting)`| `HKQuantityTypeIdentifierRestingHeartRate` | `40443-4` |
| `sleep` | `SleepSessionRecord` | `DT_CONTINUOUS_SLEEP` | `sleep` | `HKCategoryTypeIdentifierSleepAnalysis` | `93832-4` |
| `weight` | `WeightRecord` | `DT_BASIC_WEIGHT` | `body/weight` | `HKQuantityTypeIdentifierBodyMass` | `29463-7` |
| `blood_pressure` | `BloodPressureRecord` | `DT_INSTANTANEOUS_BLOOD_PRESSURE` | `body/bp` | `HKCorrelationTypeIdentifierBloodPressure` | `85354-9` |
| `oxygen_saturation`| `OxygenSaturationRecord`| `DT_INSTANTANEOUS_SPO2` | `spo2` | `HKQuantityTypeIdentifierOxygenSaturation` | `59408-5` |

---

## 3. Multi-Source Deduplication & Step Overlap Resolution

A common flaw in consumer wearable platforms is step inflation resulting from simultaneous recording by both an Android smartphone (in pocket) and a connected smartwatch (on wrist). CLARA resolves this through deterministic origin precedence:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                   DEDUPLICATION ALGORITHM (projection.py)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Collect all step observations for a 24-hour UTC window.                  │
│ 2. Sort observations chronologically by observed_start.                     │
│ 3. Partition into overlapping temporal clusters where intervals intersect.  │
│ 4. For each cluster:                                                        │
│    • Priority 1: Smartwatch / Dedicated Wearable (device.type == "watch").  │
│    • Priority 2: Health Connect Aggregated Platform Record.                 │
│    • Priority 3: Smartphone Sensor (device.type == "phone").                │
│ 5. Select the primary observation for the cluster; discard duplicates.      │
│ 6. Sum non-overlapping contributions into WearableDailyAggregate.           │
│ 7. Record contributing IDs in WearableAggregateContribution for provenance. │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Idempotency Invariants
- Provider record IDs are unique within `(connector_id, data_origin, provider_record_id, version)`.
- Resubmitting an identical batch payload yields `HTTP 200 OK` with `accepted_count = 0` and `rejected_count = 0` (replay safe).
- Tombstones (`ConnectorRecordTombstone`) mark remote deletions and prevent resurrected values during subsequent backfills.

---

## 4. HL7 FHIR R4 Interoperability Mapping

When exported via the FHIR interoperability gateway, wearable observations are transformed into standard FHIR R4 resources:

### 4.1 FHIR R4 `Observation` Mapping

```json
{
  "resourceType": "Observation",
  "id": "wearable-obs-40912",
  "meta": {
    "profile": [
      "http://hl7.org/fhir/StructureDefinition/vitalsigns"
    ]
  },
  "status": "final",
  "category": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/observation-category",
          "code": "vital-signs",
          "display": "Vital Signs"
        }
      ]
    }
  ],
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "8867-4",
        "display": "Heart rate"
      }
    ]
  },
  "subject": {
    "reference": "Patient/pat-user-101"
  },
  "effectivePeriod": {
    "start": "2026-10-24T08:00:00+07:00",
    "end": "2026-10-24T08:00:05+07:00"
  },
  "valueQuantity": {
    "value": 72.0,
    "unit": "beats/minute",
    "system": "http://unitsofmeasure.org",
    "code": "/min"
  },
  "device": {
    "reference": "Device/dev-huawei-gt4"
  },
  "derivedFrom": [
    {
      "reference": "Provenance/prov-connector-501"
    }
  ]
}
```

### 4.2 FHIR R4 `Device` Resource

Each external hardware device is tracked via a minimal FHIR `Device` resource recording manufacturer and model while omitting direct hardware serial numbers (protecting against device fingerprinting and PII leakage):

```json
{
  "resourceType": "Device",
  "id": "dev-huawei-gt4",
  "manufacturer": "Huawei",
  "modelNumber": "Watch GT 4",
  "type": {
    "coding": [
      {
        "system": "http://snomed.info/sct",
        "code": "467178001",
        "display": "Wearable activity monitor"
      }
    ]
  }
}
```

---

## 5. Security & Provenance Boundaries

1. **Digital Provenance Verification**: Every imported batch records `raw_hash` (SHA-256) and `adapter_version`. This allows verification that data was processed by an authorized adapter version without tampering.
2. **Context Compilation Firewall**: Wearable metrics passed into the LLM context compiler are strictly typed facts:
   - Must contain: metric name, value, source, observation interval, freshness, quality state.
   - Must NOT contain: raw user identifiers, device hardware serials, location GPS coordinates.
3. **Vietnamese Language Labeling**: UI layers present source-attributed badges to the consumer (e.g. `Đồng bộ từ Health Connect`, `Đồng hồ thông minh Huawei`, `Không dùng để chẩn đoán y khoa`), fulfilling Vietnamese consumer transparency requirements under Decree 13/2023/ND-CP and Law 15/2023/QH15.
