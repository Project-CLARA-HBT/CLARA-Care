# Technical design

## Current architecture

`apps/web/app/layout.tsx` loads global CSS and mounts the client `AppShell`. `AppShell` hydrates `/auth/me`, profile context, onboarding, preferences, navigation, layout, and overlays. `navigation.config.ts` is both route registry and menu model. Domain routes directly call typed API clients in `apps/web/lib/*`. Safety/authorization contracts are server-side in `services/api` and `services/ml`; the UI is a presentation layer and must not become an authorization oracle.

## Proposed architecture

```text
RootLayout (server: metadata, locale, theme init)
└─ AppProviders
   ├─ AuthGate (one authoritative session request)
   ├─ ProfileProvider (active profile isolation)
   ├─ PreferenceProvider (theme/language only)
   ├─ WorkspaceProvider (role/flags → presentation context)
   └─ AuthenticatedShell
      ├─ DesktopSidebar
      │  ├─ WorkspaceSwitcher
      │  ├─ PrimaryNavigation (≤7)
      │  └─ MoreNavigation
      ├─ MobileNavigation (SideSheet + bottom ≤4 + More)
      ├─ AppTopbar (context/help/notifications/profile)
      └─ ContentFrame / ImmersiveContentFrame
```

Extraction is incremental. If providers would cause duplicate requests, retain a single controller hook and extract presentational components first. `AppShell` remains a compatibility facade until the new boundaries are proven.

## Registries and state ownership

Split the current config into typed modules without changing server RBAC. This is a required migration boundary, not an aspirational end state:

```ts
type WorkspaceId = "personal" | "clinical" | "research" | "admin";

interface RouteDefinition {
  id: string;
  href: string;
  match?: string[];
  public?: boolean;
  authenticatedUtility?: boolean;
  access: { roles: UserRole[]; flags?: string[] };
  canonicalWorkspace?: WorkspaceId;
  page?: PageMeta;
  aliasOf?: string;
}

interface NavigationItem {
  id: string;
  routeId: string;
  labelKey: UITranslationKey;
  icon: IconName;
  workspace: WorkspaceId;
  order: number;
  primary: boolean;
  mobilePrimary?: boolean;
}
```

`route-registry.ts` becomes authoritative for client presentation guards and classification; `workspace-navigation.ts` is presentation-only. `isRouteAllowedForRole` never imports primary navigation. Existing exported helpers remain as adapters during migration. More never bypasses server RBAC. Every page route must be classified and every alias must have a redirect test before the old model is removed.

State ownership:

- Server/session: role, consent, profile capability, route authorization, medical truth, safety results.
- Workspace provider: permitted presentation workspace, current route-derived workspace, versioned workspace ID.
- Route/controller: loading/error/form draft and view state for one flow.
- Shared primitives: focus, keyboard, visual state; no medical decisions.
- Browser storage: theme/language/sidebar collapse/workspace ID only; never tokens, PII, or health data.

## Routing and compatibility

Use current App Router routes and add focused URL-backed steps only when backend/state supports them. Keep all current aliases and query parameters. A compatibility adapter may render a redirect or shared component, but never bypasses auth/consent/CSRF/RBAC. Dynamic route changes require a redirect test and route inventory update.

## Responsive strategy

- `<640px`: one content column, bottom nav + More SideSheet, 44px targets.
- `640–1024px`: compact shell/drawer, two-column only for genuinely essential comparison.
- `≥1024px`: sidebar plus content; immersive workspaces may use a history SideSheet.
- `≥1280px`: readable content max 1120–1200px; clinical/admin data may be wider by explicit route contract.
- 200% zoom and 320px reflow are acceptance inputs, not optional polish.

## Chat architecture

Use AppShell as the only global shell. Chat header owns mode, history launcher, and contextual overflow. History/workspace are mutually exclusive SideSheets. Answer view-model orders urgent status, primary answer, action, uncertainty, canonical sources, concise rationale, then role-specific detail. Admin telemetry remains lazy and server-gated. Do not expose chain-of-thought or raw pipeline stages to consumers.

## Personal flow architecture

Reuse existing guided-flow primitives. LifeMap and Visit flows expose one step per decision group; drafts remain drafts until explicit review/commit. Family tabs use URL-backed `tab`. PHR hub delegates to existing section routes; until PATCH/ETag exists, save conflicts must be detected and surfaced rather than silently overwriting. Medicines preserves course/cabinet distinction and delegates normalization/DDI to server authority.

## Clinical architecture

Scribe derives one canonical stage from server session/note status. Consent precedes capture. `finalized` legacy draft is not `signed`; sign success is a separate audited transition. Council shares a case-context provider/view model across wizard/result; escalation and conflict precede metrics. Technical tabs remain compatibility routes or result disclosures with persistent context.

## Accessibility

Native semantics first. Use `aria-current`, real labels, `aria-invalid`, `aria-describedby`, `aria-live`, `aria-busy`, and focus management only where needed. Shared SideSheet/Modal makes background inert and restores trigger focus. Add axe scans but retain manual keyboard, zoom, reflow, reduced-motion, forced-colors, and Vietnamese typography checks.

## Performance and bundle

Keep history/message virtualization and lazy Mermaid/export/telemetry. Add a bundle-budget script based on clean build manifests, initially baseline +5%. Avoid a second icon library. Consider locale-specific catalog splitting only as a separately measured improvement; do not risk typed-key coverage during shell work.

## Migration sequence

1. Add docs, route inventory, explicit type-check, pinned runtime metadata.
2. Add semantic token aliases, typed Icon, hardened Field/Alert/SideSheet/ConfirmDialog tests.
3. Split route/access/navigation models and add workspace derivation tests.
4. Extract shell presentation, duplicate-action removal, mobile SideSheet, profile menu.
5. Migrate Today/LifeMap/Visits/Family/PHR/Medicines.
6. Migrate Chat/Evidence/Source Hub disclosure.
7. Migrate Council/Scribe semantics and shared shell.
8. Remove only proven-dead CSS/components; add visual/a11y/perf gates.

## Alternatives rejected

- Flat menu trimming: hides functionality and caused a prior failed redesign.
- New UI framework: unnecessary dependency and migration cost.
- Font-only icon fix: remains fragile under CSP/network; SVG abstraction is safer.
- One giant page per workspace: contradicts one-task-per-screen and worsens mobile.
- Client-only role/workspace authorization: unsafe; server remains authoritative.
- Merging medication records by name: loses provenance and confirmed/unconfirmed semantics.

## API contract readiness and migration notes

The UI must not present a local-only field as saved or resumable. Before implementing each flow, the owner records which values are server-backed today:

| Flow | Existing contract usable without migration | Conditional contract work |
|---|---|---|
| LifeMap | Existing guided-flow draft, title/goal/priority/review, episode/task commit, provenance/truth-state | Schedule recurrence, reminders, and supporter association require an approved API contract; otherwise render optional post-commit links and an explicit “not configured” state. |
| Visits | Existing visit, concerns, intake, documents, pack, share/revoke and Scribe consent endpoints | Server-resumable per-step fields may be added only if the current client cannot safely preserve them; no UI claim of persistence before proof. |
| PHR | Existing full-record read/PUT and provenance | PATCH/ETag or version conflict contract is required before claiming concurrent section saves are merged; until then detect conflict/reload rather than silently overwrite. |

If contract work is required, it becomes a separate task with schema/version, downgrade, round-trip tests, and feature flag. No UI milestone may fabricate support for a missing endpoint.
