# Route and Surface Audit — CLARA Product Experience Convergence

Audit date: 2026-07-29. This inventory classifies active product surfaces by
primary job and migration disposition. “Guided” means a URL-addressable web
flow and equivalent named mobile steps. “Reader” means progressive disclosure,
not artificial wizard steps. Research remains part of Chat.
The audit supplies baseline evidence for R1 and R6; downstream implementation
and acceptance evidence are mapped in [`traceability.md`](traceability.md).

## Web

| Surface | Primary job | Class | Owner | Disposition |
| --- | --- | --- | --- | --- |
| `/`, auth, verification, reset | Enter CLARA safely | Task/status | Web/Auth | Keep focused; converge light tokens |
| `/welcome/*` | Complete first-run setup | Guided | Web/PHR | Migrated to short server-saved steps |
| `/today` | Complete the next safe action | Reader/task | LifeMap | Keep concise; add focused detail routes |
| `/lifemap` | Understand the health timeline | Workspace | LifeMap | Split create/capture/ask/replay from overview |
| `/phr` | Review the longitudinal record | Reader | PHR | Split category/item/provenance/edit/import flows |
| `/medicines` | Review medicines and safety | Hub | Medicines | Keep hub; move add/DDI/import/correct to guided flows |
| `/selfmed/add` | Add medicine evidence | Guided | Medicines | Replace dense page with method-to-review steps |
| `/visits` | Prepare and review visits | Workspace | Visits | Add focused visit/intake/document/pack/share routes |
| `/family` | Manage delegated care | Workspace | Family | Split invite, authority, expiry, revoke, and logs |
| `/chat` | Ask and understand an answer | Conversation | Chat/RAG | Canonical research entry; progressive advanced controls |
| `/research*` | Legacy research entry | Redirect/adapter | Chat/RAG | Redirect to Chat; no second primary experience |
| `/evidence` | Manage a living evidence question | Guided/reader | Evidence | Split scope, confirm, run, result, subscription |
| `/council/new/*` | Submit a Council case | Guided | Council | Standardize on shared flow primitives |
| `/council/result`, detail tabs | Review Council output | Reader | Council | Keep progressive sections; remove duplicate canvas |
| `/scribe` | Capture and review a clinical note | Guided/workspace | Scribe | Split consent, input, transcript, SOAP, export |
| `/community` | Read or publish community content | Reader/guided | Social | Split audience, body, safety review, publish |
| `/account/consent` | Manage consent | Guided/status | Compliance | Split selection, consequence, confirmation, receipt |
| `/account/data` | Exercise data rights | Guided/status | Compliance | Split request, consequence, confirmation, receipt |
| `/dashboard*` | Read operational/clinical state | Reader | Clinical/Admin | Progressive drill-down; do not wizardize dashboards |
| `/admin/knowledge-sources` | Govern evidence sources | Workspace/guided | RAG Admin | Split source, credentials/readiness, review, release |
| `/admin/rag-ingestion` | Run ingestion | Guided | RAG Admin | Split configure, preflight, run, result |
| `/admin/rag-eval` | Review RAG evidence | Reader/task | RAG Admin | Immutable run detail and promotion review |
| `/admin/dsar` | Process a data-rights request | Guided | Compliance | Add scoped action, consequence, approval, receipt |
| `/admin/community-moderation` | Moderate reported content | Reader/task | Social Admin | Focused case review; retain fail-closed moderation |
| `/admin/observability`, analytics | Diagnose system quality | Reader | Platform | Progressive filters/detail, content-free telemetry |
| `/admin/answer-flow`, control tower | Configure governed behavior | Workspace | Platform/RAG | Split destructive configuration into reviewable tasks |
| `/admin`, alias routes | Enter admin tools | Redirect/hub | Platform | Keep one canonical destination per capability |

The largest active overload hotspots at audit time were LifeMap (1,678 lines),
Council (1,507), Scribe (1,229), Knowledge Sources (1,233), PHR (1,061),
Control Tower (779), Dashboard (773), RAG ingestion (725), and medicine add
(639). Landing, Knowledge Sources, Council, Dashboard, and Scribe also contain
the highest hard-coded light-theme color concentrations and are Phase 2
priorities.

## Mobile

| Surface | Primary job | Class | Owner | Disposition |
| --- | --- | --- | --- | --- |
| Unified root/shell | Reach primary care tasks | Shell | Mobile | Keep Today/LifeMap/Medicines/Chat/Profile destinations |
| First-run onboarding | Establish minimum profile and consent | Guided | Mobile/PHR | Split basics and preserve server-backed resume |
| Today | Complete next action | Reader/task | Mobile/LifeMap | Keep concise |
| LifeMap | Review timeline | Workspace | Mobile/LifeMap | Decompose the 2,595-line surface into named flows |
| Medicines | Review medicine cabinet | Hub | Mobile/Medicines | Replace long edit modal with named add/edit steps |
| Chat | Ask and review evidence | Conversation | Mobile/Chat | Keep canonical research experience |
| Profile hub | Choose profile/account task | Hub | Mobile | Remove embedded 55%-height PHR editor |
| PHR editor | Edit a record category | Guided | Mobile/PHR | One category/item flow; explicit save/review |
| Visits list/detail | Prepare a visit | Reader/guided | Mobile/Visits | Replace all-in-one detail canvas with named steps |
| Family | Manage delegated access | Reader/guided | Mobile/Family | Named invite/revoke/log flows |
| Council/Scribe/admin-role tools | Complete professional task | Guided/reader | Mobile Clinical | Reuse shared flow/readiness components where exposed |
| Legacy V2/V3 entries | Compatibility only | Adapter | Mobile Platform | No primary entry; retire after parity and rollback window |

Mobile currently relies on ad-hoc `MaterialPageRoute` navigation and has no
central typed restoration registry. Phase 1.3 introduces named typed routes
before further flow migration.

## Cross-platform disposition rules

1. Keep one canonical primary entry for each capability.
2. A legacy surface is a redirect, compatibility adapter, shared component, or
   retired artifact; it is never a second primary product.
3. Creation and setup use guided steps; overview and analytics use progressive
   readers.
4. Drafts contain no secrets in URLs, analytics, or local plaintext.
5. Destructive, clinical, consent, and sharing commits always retain a review
   or consequence boundary.
