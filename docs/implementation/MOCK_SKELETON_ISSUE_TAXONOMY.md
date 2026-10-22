# Mock, Skeleton & False-Success Issue Taxonomy (PH40)

## Taxonomy Framework

To establish a clear map of real platform capabilities and eliminate false-success behavior without regressing legitimate safety guardrails, all candidate items are triaged according to this standardized taxonomy:

| Category Code | Description | Architectural Meaning | Disposition & Treatment |
|---|---|---|---|
| `HARDCODED_TELEMETRY` | Fixed numeric KPI values (e.g. 21500 reqs, 99.98% uptime) | Misleading metric representation | **P0 Defect:** Replace with live metric aggregation or explicit `UNAVAILABLE` |
| `TRUE_DEFAULT_ON_FETCH_FAILURE` | Falling back to `{status: "ok"}` on network exception | False-success oracle | **P0 Defect:** Replace with fail-closed error propagation or degraded tone |
| `UI_DEMO_FIXTURE` | Simulated data in landing page demonstrations | Public marketing showcase | **Valid Architecture:** Verify strict isolation from authenticated patient state |
| `INERT_OR_DISABLED_FLOW` | UI placeholder shown when unauthenticated or unconsented | Fail-closed safety invariant | **Valid Security Gate:** Retain; never bypass without genuine verified consent |
| `BASE_CLASS_ABSTRACT` | Abstract base class raising `NotImplementedError` | Python interface definition | **Valid Architecture:** Expected object-oriented contract |
| `FLAG_DEFAULT_DISABLED` | Configuration setting initialized to `False` | Dark safety launch | **Operational Gate:** Retain until downstream DAG phase completes verification |

## Exact Source Anchors & User Stories

### Story 1: Accurate Operational Observability
- **As an** SRE or Platform Administrator,
- **I want** the system health dashboard to display true degraded or offline states when services fail,
- **So that** incidents are detected immediately rather than masked by synthetic 99.98% uptime numbers.
- **Anchor:** `apps/web/lib/admin-system.ts:463-505`

### Story 2: Fail-Closed Clinical Consent Protection
- **As a** Patient or End User,
- **I want** AI medical chats to remain inert until I explicitly accept the AI transparency notice,
- **So that** my personal health queries are never processed without informed consent.
- **Anchor:** `apps/mobile/lib/widgets/ai_transparency_notice_gate.dart:110-130`

### Story 3: Segregated Public Demonstration Fixtures
- **As a** Compliance Officer,
- **I want** landing page demonstration medicines to never cross into real electronic health records,
- **So that** synthetic demo data does not contaminate patient clinical dossiers.
- **Anchor:** `apps/web/components/landing/v7/landing-data-v7.ts:1-180`
