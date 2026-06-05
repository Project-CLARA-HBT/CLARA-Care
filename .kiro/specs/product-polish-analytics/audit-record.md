# Audit_Record — Product Polish & Analytics

Deliverable for Requirements 1.1 / 1.2. Produced by CLARA_Delivery.

This record enumerates, per Surface, the defects found and a severity rank
(`critical` | `high` | `medium` | `low`) based on **End_User impact**. It was
produced by a fresh deep-dive of the actual codebase (`apps/web`,
`services/api`, `services/ml`, `apps/mobile`) and cross-checking the
`context.md` known-issue seeds (DDI clarity, chat routing/timeout, telemetry
leakage, mobile session persistence, doc/config drift) against current source.
Where a seed has already been fixed in code, it is recorded as **Resolved
(verified)** so the task plan does not re-do landed work.

## How severity is assigned

- **critical** — blocks a core End_User outcome, leaks unsafe/incorrect medical
  signal, or breaks a safety/privacy guardrail.
- **high** — strongly degrades trust or usability on a primary path (raw
  errors/jargon shown to End_Users, telemetry leakage, broken persistence, or a
  missing core deliverable) but the surface still partly functions.
- **medium** — noticeable polish/consistency/accessibility gap that does not
  block the task.
- **low** — cosmetic or copy-level nit.

## Audit method and scope (this revision)

Every status below was re-verified by direct inspection of current source.
Notable confirmations from this pass:

- **Chat** — `resolveChatTransport(selectedResearchMode)` is exported from
  `apps/web/lib/research.ts` and is the branch actually used in
  `apps/web/app/chat/page.tsx` `onSubmit` (`=== "tier1_chat"` → `sendChatMessage`,
  else `executeResearchTier2Job`). The primary `onSubmit` catch now routes
  through `sanitizeUpstreamError(cause.message)`. The right-rail telemetry, by
  contrast, is gated by a **localStorage toggle only** (`isTelemetryPanelOpen`),
  with no `role === "admin"` check and no `TelemetryPanel` wrapper.
- **CareGuard ML** — `_risk_from_signals` applies the `medium` floor *after* the
  score thresholds; `_merge_drug_alerts` skips openFDA evidence when no existing
  pair (`if existing is None: continue`); `_sanitize_source_errors_for_output`
  hides `openfda http_400` while a non-openFDA signal remains.
- **CareGuard web** — `toDdiUserView`, `requiresTwoMedicines`, and the
  `DDI_RISK_GROUP_LOCALIZATION` map (bleeding, reduced clopidogrel efficacy,
  drowsiness/dizziness, hyperkalemia, myopathy) all exist in
  `apps/web/lib/careguard.ts`. `/selfmed/ddi` renders only the `userView`
  projection and guards `< 2` medicines. `/careguard` renders the main result
  via `toDdiUserView`/`displayedView`, **but** its "Tín hiệu vận hành" panel
  still renders `getModeBadgeLabel(displayedResult?.mode)` to all roles, outside
  the imported `TelemetryPanel`.
- **Council** — primary copy is Vietnamese/jargon-free via `cleanText`/
  `stripTelemetryLabels`; `CONVERGENCE_FAILURE_0x99` now sits inside
  `<TelemetryPanel role={role}>` (admin-only).
- **Analytics (API)** — `analytics.py` defines the schemas **and** the
  `AnalyticsAggregator` (with `_project_pii_free`, `_within_range`);
  `system.py` exposes `GET /system/analytics/product` and `/clinical`, both
  gated by `require_roles("admin")`, honoring `PRODUCT_ANALYTICS_ENABLED` /
  `CLINICAL_ANALYTICS_ENABLED` / `ANALYTICS_DEFAULT_RANGE_DAYS`. The web
  dashboards under `apps/web/app/admin/analytics` do **not** exist yet.
- **Analytics SDK** — the web facade (`apps/web/lib/analytics/index.ts`,
  `events.ts`) and the mobile facade (`apps/mobile/lib/core/analytics.dart`)
  both exist with consent/PII/pseudonymous guards. Neither is wired to any
  Surface page/screen yet (no `@/lib/analytics/events` import under
  `apps/web/app`; no `Analytics`/`getAnalyticsClient` call site under
  `apps/mobile/lib/screens`).
- **Mobile** — `PersistentSessionStore` (secure-storage backed) is implemented
  and `SessionStore` is a `typedef` alias for it; `app.dart` `initState` calls
  `hydrate().catchError((_) => clear())`; `dashboard_screen.dart` `_signOut`
  calls `clear()`. `main.dart` still defaults the API base to
  `http://localhost:8000`.
- **Doc/config** — `CLAUDE.md` describes an "implemented polyglot monorepo";
  `.env.example` has no duplicate keys (`awk` scan) and contains every new
  analytics key; all 18 paths in `data/docs/index.md` resolve on disk.

---

## Surface: Chat (`/chat`)

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| CHAT-1 | critical | Fast_Mode queries were routed through the long tier2 research pipeline, leaving End_Users on a spinner for short questions. | `apps/web/lib/research.ts` exports pure `resolveChatTransport(mode)` (`fast → tier1_chat`, `deep`/`deep_beta → tier2_job`); `apps/web/app/chat/page.tsx` `onSubmit` (~line 1957) calls `resolveChatTransport(selectedResearchMode)` and only invokes `executeResearchTier2Job()` when the result is not `tier1_chat`. | **Resolved (verified)** — lock with Property 1 test (task 2.2). |
| CHAT-2 | high | The primary submit/answer path surfaced the **raw** error string to the End_User. | `apps/web/app/chat/page.tsx` `onSubmit` catch (~line 2106) now does `setError(cause instanceof Error ? sanitizeUpstreamError(cause.message) : ...)`; the local-fallback persist branch (~line 2070) also wraps with `sanitizeUpstreamError`. | **Resolved (verified)** — lock with the sanitized-timeout regression (tasks 2.8, 2.9). |
| CHAT-3 | high | The right-rail telemetry (confidence, **Tải suy luận**/Neural Load, **Luồng xử lý**/Logic Flow, **Nguồn**/Source Intel) is shown to **all** roles, gated only by the `isTelemetryPanelOpen` localStorage toggle — not by `role === "admin"`. `TelemetryPanel` is imported elsewhere but **not** used on this surface. | `apps/web/app/chat/page.tsx` right-rail aside (~lines 3712–3820) renders telemetry whenever `isTelemetryPanelOpen`; grep for `TelemetryPanel`/`role === "admin"` in the chat page returns no matches. | **Open** — wrap detailed telemetry in role-gated `TelemetryPanel` (task 9.1). |
| CHAT-4 | medium | Residual workspace-side handlers (folder/note/share/export/rename/bulk) still surface raw `cause.message` to the End_User, bypassing the sanitizer used on the primary answer path. | `apps/web/app/chat/page.tsx` numerous `setError(cause instanceof Error ? cause.message : ...)` in workspace mutation handlers (lines ~1368, 1483, 1670, 2133, 2147–2434). | **Open** — route secondary handlers through `sanitizeUpstreamError` (task 9.1). |
| CHAT-5 | medium | No shared four-state async handling (loading/empty/error/populated) for the answer/submit area; `AsyncSection` exists but is unused anywhere under `apps/web/app`. | `apps/web/components/ui/async-section.tsx` present; chat page uses ad-hoc `isSubmitting`/`error`/`notice` flags. | **Open** — adopt `AsyncSection` (Epic 8). |

**Fix ordering on Chat:** CHAT-1 (resolved) and CHAT-2 (resolved); remaining open high CHAT-3 precedes medium CHAT-4, CHAT-5.

---

## Surface: Research (`/research`)

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| RES-1 | low | `/research*` routes are permanent redirects into the Chat workspace, so the research surface is effectively the Chat surface; defects are tracked under Chat. | `apps/web/app/research/page.tsx` is `redirect("/chat")` (and `context.md` records the research→chat consolidation). | **Resolved (verified)** — no standalone research page to polish. |
| RES-2 | medium | Because Research is folded into Chat, the telemetry-strip / event-emit integration must still be applied to the Chat workspace components that render research telemetry (flow timeline, stage labels). | `apps/web/app/chat/page.tsx` logic-flow/flow-stage rendering in the telemetry rail. | **Open** — covered by Chat CHAT-3 and task 9.2. |

**Fix ordering on Research:** none critical/high; RES-2 (medium) handled with the Chat integration.

---

## Surface: SelfMed / CareGuard (`/selfmed`, `/selfmed/ddi`, `/careguard`)

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| CG-1 | critical | A single `medium` `drug_drug` interaction was aggregated down to overall `risk.level = low` (e.g. clopidogrel+omeprazole, ibuprofen+prednisone, paracetamol+warfarin), under-warning End_Users. | `services/ml/src/clara_ml/agents/careguard.py` `_risk_from_signals` applies a `medium` floor after the score thresholds: `if has_medium_risk_ddi and _SEVERITY_RANK[level] < _SEVERITY_RANK["medium"]: return max(score, 1), "medium"`. | **Resolved (verified)** — lock with Property 7 test (task 4.3). |
| CG-2 | high | openFDA-only co-occurrence produced a standalone synthetic alert, duplicating/noising the DDI output. | `careguard.py` `_merge_drug_alerts`: openFDA evidence only attaches to an **existing** pair (`if existing is None: continue`), never creates a new alert. | **Resolved (verified)** — lock with Property 6 test (task 4.2). |
| CG-3 | high | `/selfmed/ddi` leaked `mode`, `fallback`, `source_errors`, and raw connector errors (`openfda http_400`) to End_Users. | `apps/web/lib/careguard.ts` `toDdiUserView` projects only `{ riskLevel, alerts, recommendations, sources }`; `apps/web/app/selfmed/ddi/page.tsx` renders the `userView` projection only. Backend `_sanitize_source_errors_for_output` hides `openfda http_400` while another signal exists. | **Resolved (verified)** — lock with Properties 5/9 (tasks 4.6, 4.7). |
| CG-4 | high | The **`/careguard`** page still surfaces a runtime/telemetry badge ("Cách đối chiếu" / mode = "Bên ngoài + cục bộ" / "Chỉ cục bộ") to **all** roles. The main result already uses the `toDdiUserView`/`displayedView` projection, but the "Tín hiệu vận hành" panel renders `getModeBadgeLabel(displayedResult?.mode)` **outside** the imported `TelemetryPanel`, so the internal mode leaks. | `apps/web/app/careguard/page.tsx` (~lines 1002–1010): `getModeBadgeLabel(displayedResult?.mode ?? null)` in the "Tín hiệu vận hành" article; `TelemetryPanel` and `userRole` are imported/tracked but not applied to this panel. | **Open** — wrap the operational-signal panel in role-gated `TelemetryPanel` (or drop `mode` from the End_User view) (task 9.3). |
| CG-5 | high | DDI check could run with fewer than two medicines on some entry points. | `apps/web/lib/careguard.ts` `requiresTwoMedicines` (distinct count `< 2`); `/selfmed/ddi` guards `onRunDdi` (`if (needsMoreMedicines) { setError(...); return; }`) and disables the button; `/careguard` imports the same guard. | **Resolved (verified)** — lock with Property 8 test (task 4.9). |
| CG-6 | medium | DDI alert/recommendation copy needed Vietnamese coverage for the common risk groups; previously localization lived only in the ML layer. | `apps/web/lib/careguard.ts` now defines `DDI_RISK_GROUP_LOCALIZATION` + `DDI_RISK_GROUP_PATTERNS` + `DDI_RISK_GROUP_ORDER` for bleeding, reduced clopidogrel efficacy, drowsiness/dizziness, hyperkalemia, and myopathy, merged into `toDdiUserView` recommendations. | **Resolved (verified)** — lock with the risk-group example test (task 4.11). |
| CG-7 | medium | `/careguard` uses bespoke loading/empty/error handling (`autoError`, `manualError`, `cabinetLoading`) rather than the shared `AsyncSection`, so async states are inconsistent with other surfaces. | `apps/web/app/careguard/page.tsx` ad-hoc state flags; `AsyncSection` unused. | **Open** — adopt `AsyncSection` (Epic 8). |

**Fix ordering on SelfMed/CareGuard:** critical CG-1 and high CG-2, CG-3, CG-5 are resolved; the still-open **high CG-4** must precede the medium CG-7 on the same surface (CG-6 resolved).

---

## Surface: Council (`/council`)

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| COU-1 | high | The result view previously showed heavy engineering jargon (`CONVERGENCE_FAILURE_0x99`, `Protocol Level 4 Active`, `Conflict Logic Diagram`, `Risk Escalation: Conflict Detected`) to End_Users. | `apps/web/app/council/page.tsx`: primary copy now runs through `cleanText`/`stripTelemetryLabels` with Vietnamese fallbacks (consensus/divergence framing); the only residual internal token `CONVERGENCE_FAILURE_0x99` is rendered **inside** `<TelemetryPanel role={role}>` (admin-only, ~lines 437–459). The other jargon strings no longer appear (grep returns no matches). | **Resolved (verified)** — lock telemetry-panel visibility with Property 11 (task 3.7) and council integration (task 9.4). |
| COU-2 | medium | Specialist node labels and metric captions were English; now Vietnamized via `cleanText(... "Chuyên khoa 1/2")`, "Tóm tắt hội chẩn", "Điểm cần lưu ý". A few neutral mono-format timestamps/time captions remain. | `apps/web/app/council/page.tsx` `cardiologyNode`/`pharmNode`/`consensusText`/`escalationText`. | **Resolved (verified, minor)** — Vietnamese task-oriented labels in place; any remaining caption polish folds into task 8.6. |
| COU-3 | medium | Empty/loading states are partial: the page renders an empty state when no analyzed case exists, but `loadError` is surfaced only inside that empty state and there is no distinct loading state while fetching. | `apps/web/app/council/page.tsx` (`loadError` via `CouncilEmptyState`); `AsyncSection` unused. | **Open** — adopt `AsyncSection` four states (Epic 8). |

**Fix ordering on Council:** COU-1 (high) resolved; remaining COU-3 (medium) is polish.

---

## Surface: Scribe (`/scribe`)

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| SCR-1 | medium | Engineering branding/jargon shown to End_Users: `ScribeOS v2.4`, plus English section labels (`Live Audio`, `Assessment Signal`, `Plan Draft`, `Safety Warning`, `Transcript Captured`). No role gating exists on the surface (`TelemetryPanel`/`getRole` are not imported). | `apps/web/app/scribe/page.tsx` header (`ScribeOS v2.4`, ~line 708) + `buildLiveInsights` titles (~lines 89, 151, 158, 165, 173) + `Live Audio` tab (~line 719). | **Open** — strip jargon, Vietnamize labels, role-gate any telemetry (tasks 8.6, 9.5). |
| SCR-2 | medium | Live errors are shown raw via `setError(cause.message)` across load/transcribe/record/regenerate/finalize handlers; should pass through the sanitizer for End_User copy. | `apps/web/app/scribe/page.tsx` multiple `setError(cause instanceof Error ? cause.message : ...)` (~lines 341, 374, 408, 465, 572, 599, 621, 642, 668, 686). | **Open** — route through `sanitizeUpstreamError` (task 9.5). |
| SCR-3 | low | Derived clinical codes (e.g. `K80.20`, `47562`) are heuristic keyword matches surfaced as if authoritative; acceptable for a doctor-facing tool but should be visually marked as draft. | `apps/web/app/scribe/page.tsx` `deriveClinicalCodes`. | **Open** — copy/visual nit (Epic 8). |
| SCR-4 | low | The scribe analytics summary must be preserved (not removed) when the new Clinical_Analytics page is added. | `services/api/.../scribe.py` `GET /analytics/summary` (doctor-gated) is intact and separate from the new `/system/analytics/*`; web `/scribe` consumes the summary. | **Watch** — regression-test that the summary stays intact (task 6.3, Requirement 8.5). |

**Fix ordering on Scribe:** no critical/high; SCR-1, SCR-2 (medium) precede SCR-3, SCR-4 (low).

---

## Surface: Admin Control Tower (`/admin/*`, `/dashboard/control-tower`)

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| ADM-1 | high | The Product_Analytics and Clinical_Analytics admin **web dashboards** do not exist yet (`apps/web/app/admin/analytics` is absent). The backing API has fully landed: `analytics.py` defines the schemas **and** `AnalyticsAggregator` (with `_project_pii_free`/`_within_range`), and `system.py` exposes `GET /system/analytics/product` and `/system/analytics/clinical`, both gated by `require_roles("admin")` and honoring the `PRODUCT_ANALYTICS_ENABLED`/`CLINICAL_ANALYTICS_ENABLED`/`ANALYTICS_DEFAULT_RANGE_DAYS` settings. This is a missing core deliverable for the Admin_User (ranked high) but does not block existing End_User flows. | `file_search apps/web/app/admin/analytics` → no files; `services/api/src/clara_api/api/v1/endpoints/analytics.py` (`AnalyticsAggregator`, `product_metrics`, `clinical_metrics`); `services/api/src/clara_api/api/v1/endpoints/system.py` (`@router.get("/analytics/product")`, `@router.get("/analytics/clinical")`, `_resolve_analytics_range`); `core/config.py` analytics settings. | **Open** — schemas + aggregator + both endpoints + settings done (tasks 5.1, 5.2, 5.5, 5.6, 5.9); the two **web pages** remain (tasks 6.1–6.3). |
| ADM-2 | medium | Admin observability/flow panels render detailed telemetry directly and are not yet routed through the shared role-aware `TelemetryPanel` wrapper, so the admin-only invariant relies on route guards rather than the component contract. | `apps/web/components/admin/admin-observability-panel.tsx`, `admin-flow-visualizer.tsx`. | **Open** — standardize via `TelemetryPanel` (task 9.6). |
| ADM-3 | low | Some admin sub-panels lack the four explicit async states. | `apps/web/components/admin/*`. | **Open** — `AsyncSection` adoption (Epic 8). |

**Fix ordering on Admin:** ADM-1 (high) precedes ADM-2 (medium) and ADM-3 (low). RBAC on the new endpoints already returns 403 for non-admin (Requirement 7.2) via `require_roles("admin")` and is locked by tasks 5.8 / 11.2.

---

## Surface: Dashboard (`/dashboard`)

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| DASH-1 | medium | Runtime/operational telemetry is shown to **all** roles in the sources banner: `API: {healthStatus} • ML: {mlStatus}`, alongside request/error-derived counts, without role gating. These are internal health signals that should be admin-only on a primary End_User view. | `apps/web/app/dashboard/page.tsx` (~line 538): `Tổng nguồn: ... • API: {healthStatus.toUpperCase()} • ML: {mlStatus.toUpperCase()}`; `requestCount`/`errorCount` state feed derived figures. | **Open** — gate operational telemetry behind `TelemetryPanel`/admin role (task 9.6). |
| DASH-2 | medium | Dashboard load errors are surfaced as a generic Vietnamese alert rather than a raw error string. | `apps/web/app/dashboard/page.tsx` `refreshDashboard` catch: `setAlerts(["Không thể tải dữ liệu dashboard tổng hợp."])` (no raw `cause.message`). | **Resolved (verified)** — generic copy already shown. |
| DASH-3 | low | Async states partially handled with bespoke flags; adopt `AsyncSection` for consistency. | `apps/web/app/dashboard/page.tsx`. | **Open** — Epic 8. |

**Fix ordering on Dashboard:** DASH-1 (medium, open) precedes DASH-3 (low); DASH-2 resolved.

---

## Surface: Mobile (`apps/mobile`)

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| MOB-1 | critical | Session previously did not persist across app restarts because `hydrate()` was never called on launch. | `apps/mobile/lib/core/session_store.dart` implements `PersistentSessionStore` (secure-storage backed: `hydrate`/`setSession`/`clear`/`isExpired`, with `SessionStore` as a `typedef` alias); `apps/mobile/lib/app.dart` `initState` calls `widget.sessionStore.hydrate().catchError((_) => widget.sessionStore.clear())`, so a valid token restores the session and an expired/invalid one clears + routes to login. | **Resolved (verified)** — lock with the session round-trip + expired-token tests (tasks 10.3, 10.4). |
| MOB-2 | high | The mobile analytics facade `Analytics` (consent + PII strip + pseudonymous id) is implemented but **never instantiated or wired** to any screen, so no mobile product events are emitted (Requirement 9.2 unmet at runtime). | `apps/mobile/lib/core/analytics.dart` (facade + `getAnalyticsClient` present); grep for `Analytics`/`getAnalyticsClient`/`capture`/`track` under `apps/mobile/lib/screens` returns no matches. | **Open** — initialize + emit named screen events, connect consent (task 7.6 wiring). |
| MOB-3 | high | Sign-out clear lifecycle. | `apps/mobile/lib/screens/dashboard_screen.dart` `_signOut` calls `await widget.sessionStore.clear()`, removing all stored credentials (Requirement 10.5). | **Resolved (verified)** — lock with the clear-on-sign-out test (task 10.3). |
| MOB-4 | medium | Screen parity is incomplete vs web (login, dashboard, research, careguard, council exist as starters); functional parity within mobile-supported actions still pending. | `apps/mobile/lib/screens/*` (starter screens). | **Open** — parity work (task 10.5). |
| MOB-5 | low | `main.dart` default API base URL is `http://localhost:8000` while the documented API port is `8100`; minor config drift for local dev. | `apps/mobile/lib/main.dart` `_defaultApiBaseUrl` default `http://localhost:8000`; `context.md` ports note API at `8100`. | **Open** — config nit. |

**Fix ordering on Mobile:** MOB-1 (critical) and MOB-3 (high) resolved; remaining open **high MOB-2** precedes medium MOB-4 and low MOB-5.

---

## Cross-cutting: Documentation & Configuration drift (Requirement 12)

Not a user Surface, but audited here because they were `context.md` seeds.

| ID | Severity | Defect | Evidence | Status |
|----|----------|--------|----------|--------|
| DOC-1 | medium | `CLAUDE.md` described the repo as documentation-only. | `CLAUDE.md` Project Overview now reads "**implemented polyglot monorepo** ... no longer documentation-only" across web/API/ML/mobile. | **Resolved (verified)** — Requirement 12.1. |
| DOC-2 | medium | `.env.example` had a duplicated `DEEP_BETA_REPORT_MIN_WORDS` and was missing the new analytics keys. | `awk` duplicate-key scan of `.env.example` returns no duplicates; all of `ANALYTICS_SDK_PROVIDER/KEY/HOST`, `NEXT_PUBLIC_ANALYTICS_SDK_*`, `PRODUCT_ANALYTICS_ENABLED`, `CLINICAL_ANALYTICS_ENABLED`, `ANALYTICS_DEFAULT_RANGE_DAYS` present. | **Resolved (verified)** — Requirements 12.2, 12.4. |
| DOC-3 | low | `data/docs/index.md` referenced stale paths. | All 18 referenced paths (proposal, architecture, implementation-plan, research, research/data, devops, archive) resolve on disk (checked individually). | **Resolved (verified)** — Requirement 12.3. |

---

## Summary by severity (open items drive task ordering)

- **Critical (open):** none.
- **Critical (resolved/verified):** CHAT-1 (fast routing), CG-1 (medium-DDI severity floor), MOB-1 (mobile session hydrated on launch).
- **High (open):** CHAT-3, CG-4, ADM-1 (web dashboards only), MOB-2.
- **High (resolved/verified):** CHAT-2, CG-2, CG-3, CG-5, COU-1, MOB-3.
- **Medium (open):** CHAT-4, CHAT-5, RES-2, CG-7, COU-3, SCR-1, SCR-2, ADM-2, ADM-3, DASH-1, MOB-4.
- **Medium (resolved/verified):** CG-6, COU-2, DASH-2, DOC-1, DOC-2.
- **Low (open):** SCR-3, SCR-4 (watch), MOB-5, DASH-3.
- **Low (resolved/verified):** DOC-3.

## Task-ordering rule (Requirement 1.2)

For every Surface, fix tasks for its `critical`/`high` defects are sequenced
**before** its `medium`/`low` defects. Concretely, in the implementation plan:

- **Chat:** CHAT-3 (open high; task 9.1) before CHAT-4/CHAT-5 polish (tasks 9.1, Epic 8).
- **SelfMed/CareGuard:** CG-1..CG-3, CG-5 (critical/high, resolved) and the open high **CG-4** (task 9.3) before CG-7 (Epic 8); CG-6 already resolved.
- **Council:** COU-1 (high, resolved via task 9.4 pattern) before COU-3 (Epic 8).
- **Scribe:** SCR-1/SCR-2 (medium; task 9.5) before SCR-3/SCR-4 (low).
- **Admin:** ADM-1 (high; backend done, web pages via Epics 5 & 6) before ADM-2/ADM-3 (task 9.6, Epic 8).
- **Dashboard:** DASH-1 (medium) before DASH-3 (low); DASH-2 resolved.
- **Mobile:** MOB-1 (critical) and MOB-3 (high) resolved; open high **MOB-2** (task 7.6 wiring) before MOB-4 (task 10.5) and MOB-5.

This ordering is consistent with the Task Dependency Graph in `tasks.md`
(shared modules built first, then per-surface integration in Epic 9), and no
`medium`/`low` fix on a Surface is scheduled ahead of an open `critical`/`high`
fix on that same Surface.
