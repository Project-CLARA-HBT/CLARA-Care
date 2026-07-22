# CLARA Care Fluent Experience Redesign

Status: implementation baseline

Date: 2026-07-22

Scope: CLARA Web public, patient, clinical, research, and administration surfaces

## 1. Product intent

CLARA should feel calm, credible, and task-oriented. The interface must help a person understand what needs attention, what CLARA knows, what remains uncertain, and what action is safe to take next. It must not resemble a trading terminal, imply diagnosis through decoration, or expose internal telemetry as primary patient content.

The visual direction follows Fluent 2 principles: semantic tokens, neutral layered surfaces, restrained brand use, a 4 px spacing grid, Segoe UI typography, clear state changes, and accessible platform-native interaction. “Fluent-inspired” means the system follows these rules without forcing a risky whole-application dependency migration.

## 2. Research and audit findings

The existing product contains three competing visual systems: a blue glass shell, cyan “futuristic” dashboard/research surfaces, and a more restrained chat workspace. The inconsistency is structural rather than a lack of polish. Large feature pages also combine data loading, workflow state, and presentation, so a shared foundation has the highest immediate reach with the lowest behavior risk.

Research sources:

- [Fluent 2 design tokens](https://fluent2.microsoft.design/design-tokens)
- [Fluent 2 color](https://fluent2.microsoft.design/color)
- [Fluent 2 layout](https://fluent2.microsoft.design/layout)
- [Fluent 2 typography](https://fluent2.microsoft.design/typography)
- [Fluent 2 accessibility](https://fluent2.microsoft.design/accessibility)
- [WCAG 2 overview](https://www.w3.org/WAI/standards-guidelines/wcag/glance/)
- [AHRQ health-literacy universal precautions](https://www.ahrq.gov/health-literacy/improve/precautions/index.html)
- [ONC patient engagement playbook](https://playbook.healthit.gov/playbook/pe/chapter-3/)

## 3. Users and jobs

### Patient and caregiver

- Ask a health question and understand the answer, evidence, uncertainty, and next safe action.
- Maintain a health record and medicine cabinet without losing entered data.
- Recognize urgent safety guidance separately from routine information.
- Review medicine interactions with plain-language explanations and provenance.

### Clinician

- Capture a visit, review a structured note, and confirm before export.
- Start and follow a council case through intake, analysis, evidence, and result.
- Move between a central work canvas and contextual evidence without losing state.

### Researcher and administrator

- Run research at the intended depth and see progress, sources, and verification.
- Find operational exceptions quickly, then disclose detail progressively.
- Configure sources and workflows without mixing destructive actions into routine views.

## 4. Functional requirements

1. The authenticated product uses one responsive app shell with persistent desktop navigation, a compact rail, and a modal mobile drawer.
2. Navigation selection is conveyed by text, icon treatment, and a visible indicator—not color alone.
3. Every page has a consistent title region, optional description/context, primary action position, and content width.
4. Patient and clinical pages order content as: next action, safety/attention, summary, detail, provenance.
5. Workspaces use a command region, central canvas, and optional contextual rail. Secondary controls use progressive disclosure.
6. Status includes a label/icon and, where relevant, timestamp, source, owner, and next action.
7. Loading, empty, error, stale/offline, permission-denied, and completed states are visually and semantically distinct.
8. Consequential medication, consent, sharing, and deletion actions name the object, action, and consequence before confirmation.
9. Input values survive recoverable failures. Validation is adjacent to the field and announced to assistive technology.
10. Light, dark, forced-color, reduced-motion, Vietnamese, and English preferences remain supported.

## 5. Design system

### Tokens

Use global primitives only to construct semantic aliases. Components consume aliases such as canvas, surface 1–3, foreground 1–3, neutral stroke, brand background/foreground, status background/foreground, control rest/hover/pressed, shadow, radius, and motion. Raw status colors must not carry clinical meaning by themselves.

### Layout

- Base spacing unit: 4 px.
- Control/internal spacing: 4, 8, 12, 16 px.
- Group/section spacing: 20, 24, 32, 40, 48 px.
- Minimum interactive target: 44 × 44 px.
- Standard content maximum: 1,440 px; immersive workspaces may use available width.
- Cards use 8–12 px radii. Pills are reserved for compact tags and statuses.

### Typography

Segoe UI is primary, followed by native system fonts. Default body is 14/20 or 16/24. Captions never fall below 12/16 for meaningful content. Page titles use 28–32 px with semibold weight. Labels use sentence case and remain visible; placeholders are examples, never labels.

### Color and elevation

Neutral surfaces establish hierarchy. Brand blue is used for identity, selection, links, and the primary action. Success, warning, and danger colors are reserved for real states. Most regions use a stroke or a low elevation; dialogs/drawers use higher elevation. Decorative glow, glass blur, dot grids, and perpetual pulses are removed from authenticated workflows.

### Motion

Micro-interactions use 100–200 ms; panels use 200–300 ms. Animate opacity and transform only when it clarifies state. `prefers-reduced-motion` disables nonessential animation and smooth scrolling.

## 6. Information architecture

- Core: Chat, Overview, Personal Health Record, Community.
- Medication: Medicine Cabinet, Interaction Check.
- Research: Source Hub and evidence tools for permitted roles.
- Clinical: Council and Medical Scribe for clinicians/admins.
- Administration: overview first, then knowledge, answer flow, observability, moderation, and analytics.

Desktop presents these as labeled navigation groups. Mobile keeps a small bottom set for frequent destinations and uses the drawer for the complete hierarchy. Account, theme, language, help, and sign-out are separated from product destinations.

## 7. Accessibility requirements

- WCAG 2.2 AA target: 4.5:1 normal text, 3:1 large text and UI boundaries.
- Keyboard access for every action, visible 2 px focus indicator, logical DOM order, skip link, and focus restoration.
- Closed dialogs/drawers are absent from the accessibility tree; open modal surfaces trap focus and close with Escape where safe.
- Reflow at 320 CSS px / 400% zoom and text resize to 200% without lost content.
- Status never uses color alone. Icon-only controls have accessible names.
- Tables retain header associations; charts provide a textual summary and accessible data alternative.
- Live loading/streaming/error changes use appropriate live regions without excessive announcements.

## 8. Technical design

The first implementation layer keeps application behavior intact and changes presentation through:

1. A semantic token contract in `styles/globals.css` for light/dark themes.
2. Shared page and surface primitives under `components/ui`.
3. A unified `AppShell`, navigation rail/drawer, mobile command bar, and bottom navigation.
4. Compatibility mappings for legacy `chrome`, `glass`, research, dashboard, and feature-panel classes so every route adopts the new system immediately.
5. Incremental page decomposition after the shared foundation, starting with safety-sensitive patient workflows, without changing API contracts.

No medical guardrail, RBAC, consent, emergency fast-path, citation, verification, or telemetry-sanitization behavior may be weakened by visual work.

## 9. Responsive behavior

- Mobile (320–767): single content column, 16 px gutters, top command bar, compact bottom navigation, full-height modal drawer.
- Tablet (768–1023): wider single column or two-pane workspaces where content permits.
- Desktop (1024+): persistent navigation, responsive canvas, optional contextual rail.
- Very wide screens: content remains readable; dashboards may expand grids while prose maintains line length.

## 10. Verification and definition of done

- Unit/component tests pass.
- ESLint, TypeScript production build, design-token, contrast, and focus checks pass.
- Primary routes are checked at mobile, tablet, and desktop widths in light and dark modes.
- Keyboard-only navigation, reduced motion, loading/error states, and public/auth scrolling are manually checked.
- No unrelated files or secrets are committed.
- Deployment uses a rollback-tagged frontend image, local and public health checks, route smokes, and log inspection.

## 11. Delivery sequence

1. Foundation and responsive shell.
2. Shared surfaces, controls, and state patterns.
3. Patient workflows: PHR, medicine cabinet, CareGuard, community.
4. Research, council, and scribe workspaces.
5. Dashboard and administration density/table patterns.
6. Public, auth, help, and legal refinement.
7. Remove legacy styles/components only after route parity and visual baselines exist.
