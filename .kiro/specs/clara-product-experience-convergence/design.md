# Design — CLARA Product Experience Convergence

The requirement and phase mapping is maintained in
[`traceability.md`](traceability.md).

## 1. Architecture

```text
Feature hub / reader
        |
        v
Guided-flow route registry
        |
        +--> server draft + revision
        +--> step validation
        +--> readiness / consent / RBAC
        |
        v
Focused step route -> review route -> idempotent command
        |
        v
Result / canonical reader / correction route
```

The application shell remains stable. Task flows are nested routes rendered in
a shared focused shell; readers and workspaces keep navigation context.

## 2. Web components

Add under `apps/web/components/guided-flow/`:

- `GuidedFlowShell`: title, rationale, progress, save state, error summary,
  content landmark, and sticky action footer;
- `StepProgress`: accessible ordered list for wide screens and compact progress
  for mobile;
- `StepActions`: Back, optional Skip, Save/Exit, and one primary Next/Confirm;
- `ReviewSection`: source, entered, AI draft, unknown/conflict, and edit link;
- `FlowGuard`: auth, role, consent, capability, draft revision, and step-order
  guard; and
- `FeatureReadinessCard`: actionable missing prerequisite without raw config.

Flow metadata lives in a typed registry:

```ts
type FlowStep = {
  id: string;
  path: string;
  title: LocalizedText;
  optional: boolean;
  authority: "draft" | "review" | "commit";
};
```

The route, not a large local conditional tree, is the durable step identity.
Non-sensitive UI state may use query parameters; health/input values remain in
server drafts or current component memory under existing privacy rules.

## 3. Mobile components

Add matching Flutter primitives:

- `ClaraFlowScaffold`;
- `ClaraStepProgress`;
- `ClaraFlowActions`;
- `ClaraReviewSection`;
- `FlowRouteState`; and
- `FeatureReadinessTile`.

Introduce declarative route state compatible with the unified root, then
migrate the audited ad-hoc `MaterialPageRoute` flows incrementally. Phone uses
one card and bottom actions. Tablet may show a step rail plus the same single
main card, never additional unrelated forms. Back navigation warns only when
current values are genuinely unsaved.

## 4. Draft API

Introduce a generic envelope only where an existing domain draft does not
already exist:

```json
{
  "flow_id": "medicine-add",
  "draft_id": "opaque",
  "revision": 3,
  "current_step": "schedule",
  "completed_steps": ["method", "identity", "details"],
  "expires_at": "RFC3339",
  "status": "draft"
}
```

Domain payloads remain typed domain resources. Commands require idempotency and
expected revision. The API validates step order only for authority-bearing
flows; clients cannot skip consent, review, or confirmation by navigating
directly.

## 5. Route blueprint

### Consumer web

| Hub | Focused routes |
| --- | --- |
| `/welcome` | `/welcome/start`, `/basics`, `/measurements`, `/context`, `/consent`, `/review` |
| `/lifemap` | `/new/type`, `/new/episode`, `/new/details`, `/new/review`; `/capture/source`, `/capture/upload`, `/capture/processing`, `/capture/review`, `/capture/normalize`, `/capture/confirm`; `/ask`, `/summaries`, `/replay`, `/findings` |
| `/medicines` | `/add/method`, `/identity`, `/details`, `/schedule`, `/source`, `/review`; `/interactions/mode`, `/select`, `/context`, `/review`, `/result` |
| `/visits` | `/new/basics`, `/concerns`, `/intake`, `/documents`, `/review`; `/{id}/instructions`, `/pack/select`, `/pack/review`, `/share` |
| `/family` | `/invite/recipient`, `/relationship`, `/data`, `/actions`, `/expiry`, `/review`; `/grants/{id}`, `/renew`, `/revoke` |
| `/phr` | `/edit/category`, `/edit/{category}/item`, `/provenance`, `/review`; category readers |
| `/evidence` | `/new/topic`, `/pico/*`, `/episode`, `/review`, `/run/{id}`, `/subscription`, `/subscription/review` |
| `/account` | focused consent and data-right request/review/status flows |

Chat keeps `/chat`; source/mode configuration uses a drawer/sheet and sources
open in focused detail. Council retains `/council/new/*`. Scribe gains
`/scribe/new/purpose`, `/consent`, `/input`, `/processing`, `/transcript`,
`/soap/{section}`, and `/review`.

### Administration

Add `/admin/setup` with dependency detail routes. Split knowledge/RAG into:

- `/admin/rag/sources`;
- `/admin/rag/sources/new/*`;
- `/admin/rag/ingestion/new/*`;
- `/admin/rag/evaluations/new/*`;
- `/admin/rag/releases/{id}/review`; and
- `/admin/rag/monitoring`.

Dashboards remain readers with drill-down routes.

## 6. Visual system

Semantic layers:

```text
canvas -> shell -> surface -> raised surface -> popover
```

Light palette targets:

- canvas `#f4f6fb`;
- shell `#f8faff`;
- surface `#ffffff`;
- subtle surface `#f6f8fc`;
- primary text near `#172033`;
- secondary text near `#46556a`;
- border near `#dfe5ef`;
- brand blue/indigo with contrast-tested on-colors.

All feature styles consume semantic variables. A visual-regression matrix
captures landing, auth, Today, Chat, LifeMap, Medicines, PHR, Council, Scribe,
admin setup, and representative flows at desktop, Pixel-class phone, tablet,
dark/light, 200% zoom/text scale, and reduced motion.

## 7. Chat/RAG design

```text
intent + emergency/legal policy
          |
authorized corpus/profile scope
          |
hybrid lexical+dense retrieval
          |
rerank + diversity + time/source policy
          |
context quality gate
     | low                | sufficient
source-only/abstain       v
                    bounded synthesis
                          |
        claim/citation/entailment/time/conflict/FIDES
                          |
             release or safe abstention
```

Each stage emits no-content metrics under an immutable pipeline/model/corpus
manifest. Frozen evaluation selects retrieval strategy and top-k. LLM-as-judge
may assist triage but cannot replace clinician/human adjudication. Provider
aliases resolve to immutable allowlisted IDs; “newest” means the newest version
that passed CLARA's exact evaluation and rollout gates, not the provider's
floating latest alias.

The leading retrieval candidate is BM25 plus a pinned multilingual dense
retriever with deterministic reciprocal-rank fusion. It is not production-
approved by design alone. Frozen ablations compare sparse, dense, and hybrid
retrieval; rewrite and reranker on/off; history lengths `0/2/5/10/20`; and at
least `k={3,5,8,10,16}` for each major intent/risk class. Low context quality
returns clarification, source-only output, a deterministic safety response, or
abstention.

The immutable release manifest pins provider/exact model revision, decoding
and tools, prompt/policy/router hashes, retriever/reranker/embedding/NLI/guard
versions, source allowlist, corpus and index snapshot hashes, parser/chunker,
fusion and context policy, evaluator/dataset versions, approvals, predecessor,
and rollback identity. Any change creates a candidate release and reruns the
applicable gates.

The dated evidence map and exact CLARA decisions are maintained in
`docs/research/clara-chat-rag-evidence-2026-07-29.md`. Proposed numerical gates
in that document are CLARA policy candidates, not constants reported by the
literature.

## 8. Migration

1. Build primitives without changing domain behavior.
2. Convert one representative low-risk flow (onboarding) and one health draft
   flow (medicine add).
3. Convert LifeMap/Capture, Visits, Family, PHR, Evidence, and Scribe.
4. Split admin setup/RAG workflows.
5. Remove old in-page creation forms only after route parity, telemetry, E2E,
   and rollback windows.
6. Keep compatibility redirects, not duplicate navigation entries.

Feature-specific server flags remain unchanged. Client flow flags are temporary
and independent on web/mobile.

## 9. Testing

- contract/property tests for step order, idempotency, revision conflicts,
  optional branches, resume, cancellation, and authority;
- component tests for progress semantics, focus, errors, review labels, and
  save state;
- route E2E for every happy path plus back/resume/network failure;
- screenshots and computed contrast/reflow checks in light/dark;
- screen reader and keyboard/manual device matrices;
- clean-install operator setup rehearsal; and
- stage-aware Chat/RAG offline, red-team, shadow, pilot, monitoring, and rollback
  evidence.
