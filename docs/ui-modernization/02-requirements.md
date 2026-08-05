# Traceable requirements

Priority: **Must**, **Should**, **Could**. “Related tests” are planned names until implemented and linked by the task matrix.

## Navigation, shell, and architecture

| ID | Statement and rationale | Priority / persona | Acceptance criteria | Routes | Related tests |
|---|---|---|---|---|---|
| FR-NAV-001 | Derive Personal, Clinical, Research, and Admin workspaces from authoritative role and flags so modules are not mixed. | Must / all | Exact role matrix; switcher never changes role or grants access. | authenticated | `workspace-config.test.ts` |
| FR-NAV-002 | Limit primary sidebar to seven and mobile to four plus More to reduce cognitive load. | Must / all | Counts hold for every role/flag combination. | authenticated | workspace property tests |
| FR-NAV-003 | Preserve every permitted capability outside primary navigation. | Must / all | Reachable via primary, More, context, or direct link; route access independent from menu visibility. | all active routes | capability reachability test |
| FR-NAV-004 | Direct permitted links select the canonical/current workspace; forbidden links show a clear state. | Must / all | No silent home redirect; server remains authoritative. | authenticated | direct-route E2E |
| FR-NAV-005 | Remember only a versioned workspace ID. | Should / professional | Invalid/stale values safely fall back; no role/profile/health data stored. | authenticated | provider unit tests |
| FR-NAV-006 | Preserve aliases and bookmarked URLs. | Must / all | Redirect matrix retains safe query/context. | `/selfmed*`, `/careguard`, `/research*`, admin aliases | compatibility E2E |
| FR-SHELL-001 | Provide one Ask CLARA entry and one profile trigger per viewport. | Must / all | No duplicate CTA/profile/logout. | authenticated | shell component/E2E |
| FR-SHELL-002 | Put account, preferences, active profile, and logout in one accessible profile menu. | Must / all | Keyboard operable; focus restored; logout remains reachable. | authenticated | profile-menu tests |
| FR-SHELL-003 | Keep page headings in pages and topbar limited to global/context controls. | Must / all | No duplicated `h1`/title presentation. | authenticated | semantic E2E |
| FR-SHELL-004 | Use 232–248 px expanded and 64–72 px collapsed desktop sidebar; persist collapse safely. | Should / desktop | One active state and no content jump. | authenticated | sidebar tests |
| FR-SHELL-005 | Mobile uses bottom navigation/drawer, never compressed desktop sidebar. | Must / mobile | ≤4 + More, 44 px targets, no overflow. | authenticated | mobile E2E |
| FR-SHELL-006 | Decompose session, profile, preferences, workspace, and rendering concerns incrementally. | Must / maintainers | One session request; no onboarding redirect loop; public routes remain shell-free. | all | provider/shell tests |

## Personal workspace

| ID | Statement and rationale | Priority / persona | Acceptance criteria | Routes | Related tests |
|---|---|---|---|---|---|
| FR-OVR-001 | Overview shows real attention/next-action data and never fabricated fallback metrics or confidence. | Must / professional/admin | Missing data renders honest empty/unavailable states. | `/dashboard` | dashboard regression |
| FR-TODAY-001 | Empty Today has one journey CTA and one Ask CLARA text action. | Must / personal | No zero stat cards or competing action grid. | `/today` | Today state tests |
| FR-TODAY-002 | Populated Today prioritizes the next task and pending confirmations. | Must / personal | AI-unconfirmed state explained in text; task links unchanged. | `/today`, task detail | Today E2E |
| FR-LIFE-001 | LifeMap creation uses Track → Schedule → Reminders/support → Review. | Must / personal | URL-addressable, resumable, explicit confirmation; no episode write before review. | `/lifemap/new/*` | wizard tests |
| FR-LIFE-002 | Empty LifeMap does not show add-task before an episode exists. | Must / personal | One creation CTA; error/loading/archive states supported. | `/lifemap` | state tests |
| FR-LIFE-003 | Episode experience prioritizes today progress, next step, timeline, and one add-task action. | Must / personal | Replay, baseline, Ask, disputes, revisions are contextual/tabs and lazy. | `/lifemap*` | episode E2E |
| FR-LIFE-004 | Preserve revision, provenance, truth-state, disputes, and explicit human confirmation. | Must / all | Unknown/stale/disputed never appears confirmed; AI cannot confirm. | `/lifemap*` | safety invariant tests |
| FR-VISIT-001 | Visit preparation uses Info → Concerns → Medicines/documents → Questions → Review/share. | Must / personal | Resumable focused steps; prior data survives failures/back. | `/visits*` | visit flow E2E |
| FR-VISIT-002 | Recording consent/Scribe appears only after visit creation and in context. | Must / personal/clinical | Explicit grant/revoke; no pre-creation recording control. | `/visits*` | consent flow tests |
| FR-FAM-001 | Family uses “Tôi chia sẻ”, “Được chia sẻ với tôi”, and “Nhật ký truy cập” tabs. | Must / personal | URL state, keyboard tabs, independent async/error states. | `/family` | Family tabs tests |
| FR-FAM-002 | Invitation flow explicitly shows recipient, scope, actions, purpose, duration, and review. | Must / personal | Acceptance secondary; revoke/expiry/latest access visible; tokens excluded from telemetry. | `/family/invite`, `/family/accept` | invite integration/E2E |
| FR-PHR-001 | PHR hub is a progress list linking focused sections. | Must / personal | Six grouped sections, meaningful completion state, compact disclaimer/consent. | `/phr`, `/phr/[section]` | PHR hub tests |
| FR-PHR-002 | PHR uses typed bundled SVG icons and never raw ligature text. | Must / all | Safe fallback; works with external fonts blocked. | `/phr*`, shell/shared first | icon tests/E2E |
| FR-PHR-003 | Focused forms preserve labels, validation, provenance, review-before-confirm, and save recovery. | Must / personal | Dirty-state/error announcement; no silent concurrent overwrite. | `/phr/[section]` | section integration tests |
| FR-MED-001 | Medicines retains distinct My medicines, Cabinet, and Interaction safety models. | Must / personal | Copy explains distinction; confirmed/unconfirmed state preserved. | `/medicines` | model presentation tests |
| FR-MED-002 | First run is Add → Confirm identity/dose → Interaction check → Reminder → Complete. | Must / personal | No user-facing DrugBank ID; unresolved identity requests clarification. | `/medicines/add*` | medicine flow E2E |
| FR-MED-003 | One Add medicine action per viewport and one canonical DDI surface. | Must / personal | List links selected IDs to Safety; no duplicate panel/CTA. | `/medicines` | CTA tests |
| FR-MED-004 | Preserve DrugBank authority, fail-closed state, sources, escalation, and clinician guidance. | Must / all | No all-clear when unavailable; no LLM substitution or dose advice. | `/medicines` | CareGuard safety tests |

## Chat, evidence, clinical, and administration

| ID | Statement and rationale | Priority / persona | Acceptance criteria | Routes | Related tests |
|---|---|---|---|---|---|
| FR-CHAT-001 | Chat shows at most two major columns including the global shell. | Must / all | History is collapsible drawer; no nested global app menu. | `/chat` | layout E2E |
| FR-CHAT-002 | Support Nhanh, Phân tích, Nghiên cứu modes without a redundant Research page. | Must / all | Legacy Research redirects remain; workspace may set safe initial mode. | `/chat`, `/research*` | mode/redirect tests |
| FR-CHAT-003 | Answer precedes technical progress and diagnostics. | Must / all | Emergency → key point → action → uncertainty → sources → rationale. | `/chat` | hierarchy tests |
| FR-CHAT-004 | Consolidate citations into one inspectable source disclosure. | Must / all | Inline anchors and canonical list agree; safety/provenance retained. | `/chat`, `/evidence` | citation tests |
| FR-CHAT-005 | Gate diagnostics by server-authorized role and lazy-load admin telemetry. | Must / all | Consumer DOM excludes policy enums, raw logs, provider/model details, CoT, and PII. | `/chat` | role/bundle tests |
| FR-EVID-001 | Living Evidence uses Question → Confirm → Run → Results, with sources/applicability/uncertainty. | Should / personal/research | Explicit confirm and safe-stop retained; subscriptions secondary. | `/evidence` | flow tests |
| FR-RES-001 | Source Hub separates browse and sync operations. | Should / research/admin | Connector warnings role-gated; canonical route preserved. | `/research/source-hub` | role tests |
| FR-COUNCIL-001 | Council keeps one case context and a focused multi-route wizard. | Must / doctor/admin | Resume/dirty-state/ownership handled; no duplicate workspace nav in wizard. | `/council/new/*` | Council wizard E2E |
| FR-COUNCIL-002 | Results lead with escalation, recommendation, disagreement, uncertainty, and clinician action. | Must / doctor/admin | Metrics/pipeline/model detail secondary; one new-case CTA. | `/council/result`, detail aliases | result hierarchy tests |
| FR-COUNCIL-003 | Preserve handoff, oversight, evidence IDs, conflict, DrugBank, and no-CoT invariants. | Must / doctor/admin | Confirmed/audited actions; raw model IDs only when authorized and flagged. | `/council*` | safety/UI tests |
| FR-SCRIBE-001 | Scribe follows Capture → Transcript review → SOAP review → Completion. | Must / doctor/admin | One canonical server-derived stage; history/analysis secondary. | `/scribe` | stage reducer/E2E |
| FR-SCRIBE-002 | Consent is explicit before capture when policy requires it. | Must / doctor/admin | Missing capability never appears captured; UI never bypasses server. | `/scribe` | consent tests |
| FR-SCRIBE-003 | Signed, finalized legacy draft, exported, and amended states are distinct. | Must / doctor/admin | Failed sign never sets signed UI; signed note locks and addendum remains audited. | `/scribe` | sign semantics tests |
| FR-ADMIN-001 | Admin primary nav is Overview, Knowledge, Answer Flow, Monitoring, Analytics. | Must / admin | Secondary compliance/audit/RAG tools remain in More; no fake Settings route. | `/admin/*` | admin workspace tests |

## Non-functional requirements

| ID | Requirement | Priority | Acceptance criteria | Related tests/evidence |
|---|---|---|---|---|
| NFR-A11Y-001 | Meet WCAG 2.2 AA applicable success criteria. | Must | Contrast, focus, semantics, names, errors, status, reflow, zoom, targets, reduced motion checked. | axe + manual matrix |
| NFR-A11Y-002 | Overlays trap focus, make background inert, close with Escape, and restore focus. | Must | Shared Modal/SideSheet/ConfirmDialog behavior. | component + E2E |
| NFR-A11Y-003 | Use native semantics first and typed labels for icons/forms/status. | Must | No placeholder-only control; `aria-invalid`/descriptions for errors. | component/axe |
| NFR-RESP-001 | Support 1440×900, 1280×800, tablet, 390×844, 320px reflow, 200% zoom. | Must | No horizontal overflow; touch targets 44px where practical. | responsive E2E/screenshots |
| NFR-PERF-001 | Maintain or improve bundle/hydration behavior. | Must | No second icon lib; lazy Mermaid/export/admin detail; baseline +5% budget. | build budget script |
| NFR-PERF-002 | Do not render hidden high-cost panels. | Should | Route/lazy boundaries for replay, diagnostics, diagrams, history. | network/chunk tests |
| NFR-THEME-001 | One semantic token system supports coherent light/dark themes. | Must | No new raw colors outside audited visualization allowlist. | token/contrast/visual tests |
| NFR-I18N-001 | VI default, VI/EN typed keys for visible text, errors, aria, empty/loading/status. | Must | Missing/unused check; shared terminology contract remains synchronized. | i18n/terminology CI |
| NFR-SEC-001 | UI changes preserve RBAC, consent, CSRF, profile isolation, and public-share boundaries. | Must | UI hiding never authorizes; public shares remain shell/analytics-free. | API contracts + E2E |
| NFR-SAFE-001 | Preserve emergency, FIDES, DrugBank, disclaimers, provenance, and no-autonomous-confirm rules. | Must | Critical warnings never collapsed; safety suites pass. | invariant tests |
| NFR-PRIV-001 | No PII/secrets in telemetry, screenshots, fixtures, or client persistence. | Must | Synthetic data only; workspace storage contains ID only. | privacy/static checks |
| NFR-AUDIT-001 | Sensitive share/sign/delete/override actions remain attributable and reviewable. | Must | Confirmation, result receipt, audit state visible. | integration tests |
| NFR-COMPAT-001 | Backward-compatible routes and rollback paths remain functional. | Must | Redirect matrix and legacy Chat flag tested. | compatibility E2E |
| NFR-MAINT-001 | Shared concerns have clear ownership and production components remain typed/tested. | Must | Route/access/navigation separated; AppShell responsibility reduced. | architecture review |

