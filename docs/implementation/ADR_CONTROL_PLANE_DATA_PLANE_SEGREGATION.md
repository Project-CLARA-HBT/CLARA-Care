# Architecture Decision Record (ADR): Control-Plane vs Data-Plane Segregation (PH41)

## Status
**ACCEPTED** (2026-10-22)

## Context
Previously, administrative functionality (tenant management, audit view, system metrics) was co-located in `services/api/` and rendered inside the consumer Next.js application (`apps/web/app/admin/`). This created architectural and security risks:
1. **Risk of PHI Exposure:** Admin queries could join patient clinical tables unintentionally.
2. **False Operational Status:** When health metrics endpoints failed, UI fallbacks used hardcoded numbers (21500 reqs, 99.98% uptime).
3. **Session Cookie Collision:** Admin sessions shared the same cookie and origin as consumer health sessions.

## Decision
We formally decouple the administrative **Control Plane** from the clinical **Data Plane**:

```text
[ Browser: apps/admin ] ──(HTTPS/Port 8200)──> [ Control Plane Gateway (FastAPI) ]
                                                       │
                                                       ├──> [ Control DB (clara_control) ]
                                                       │
                                                       └──(Internal RPC: HMAC Token)──> [ API Gateway Adapter ]
                                                                                               │
[ Browser: apps/web   ] ──(HTTPS/Port 8000)──> [ API Gateway (clara_api)       ] ───────────────┤
                                                       │                                       │
                                                       ├──> [ Clinical DB (clara_api)   ] ◄────┘ (Zero direct link)
                                                       │
                                                       └──(Internal: Key)──> [ ML Engine (Port 8010) ]
```

1. **Independent Control Gateway (`services/control-plane`):** Runs on port 8200, connects solely to `DATABASE_CONTROL_URL`, and has zero credentials or network route to clinical patient databases.
2. **Dedicated Admin Web App (`apps/admin`):** Separate Next.js application bound to host-only cookies (`__Host-clara_admin_session`) and restricted to port 8200 ingress.
3. **Internal Telemetry Bridge:** Control plane queries API Gateway health via `GET /system/telemetry/metrics` carrying signed HMAC service tokens (`X-Control-Service-Token`). Response is verified `zero_phi_certified`.

## Consequences
- **Positive:** Full physical data segregation; eliminating clinical breach risk via administrative compromise; compliant with Vietnam PDPD Article 13/17.
- **Negative:** Requires running and deploying two separate web and API processes.
