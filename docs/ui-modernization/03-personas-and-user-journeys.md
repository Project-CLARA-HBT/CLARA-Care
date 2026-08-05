# Personas and user journeys

## Role-to-persona model

The server role remains authoritative. A workspace is a presentation context, never a role selector.

| Server role | Personas | Permitted workspaces |
|---|---|---|
| `normal` | Personal user, self-carer, family-supported user | Personal |
| `researcher` | Researcher who may also use personal care | Personal, Research |
| `doctor` | Clinician who may also use personal care/research | Personal, Clinical, Research |
| `admin` | Operator/governance user with other permitted capabilities | Personal, Clinical, Research, Administration |

## Needs and hazards

### Personal user

Needs plain language, the next safe action, a visible uncertainty boundary, and control of what is saved/shared. Hazards include interpreting absence of a DDI warning as absolute safety, assuming AI-confirmed LifeMap facts, and losing trust when technical labels or raw icons appear.

### Researcher

Needs traceable claims, source metadata, scope, applicability, and history. Does not need connector health or raw execution logs in the answer. Hazards include citation duplication and mistaking a verifier enum for clinical certainty.

### Clinician

Needs persistent case/session context, escalation before metrics, transcript/note control, and a clear signed/finalized distinction. Hazards include recording before consent, navigating away with unsaved content, and treating generated SOAP as signed documentation.

### Administrator

Needs operational status and diagnostic depth without contaminating consumer views. Hazards include exposing model/provider/PII data, changing release policy from the care flow, and losing access to secondary governance routes after menu simplification.

### Support recipient

Needs a bounded invitation preview and explicit scope/duration. Hazards include accepting an overbroad grant or assuming access remains after revocation/expiry.

## Core journeys

### Workspace resolution and direct link

```mermaid
flowchart TD
  A[Authenticated request] --> B[Load server role and flags]
  B --> C[Derive permitted workspaces]
  C --> D{Direct route?}
  D -- Yes --> E{Permitted?}
  E -- No --> F[Clear unauthorized state]
  E -- Yes --> G[Current or canonical workspace]
  D -- No --> H[Restore versioned workspace ID]
  H --> I{Still permitted?}
  I -- No --> J[Role-safe default]
  I -- Yes --> K[Workspace home]
  G --> L[≤7 primary destinations]
  J --> L
  K --> L
  L --> M[More and contextual capabilities]
```

### Empty Today to active journey

```mermaid
flowchart LR
  A[Empty Today] --> B[Create journey]
  B --> C[What to track]
  C --> D[Schedule]
  D --> E[Reminders/support]
  E --> F[Review]
  F -->|Explicit confirm| G[Episode created]
  G --> H[Today next action]
```

At every step Back preserves draft data; optional choices are labelled; no episode/truth-state mutation happens before confirmation.

### Visit preparation and optional Scribe

```mermaid
flowchart LR
  A[Visit information] --> B[Concerns]
  B --> C[Medicines/documents]
  C --> D[Questions]
  D --> E[Review]
  E --> F{User choice}
  F --> G[Keep private]
  F --> H[Export]
  F --> I[Share with scope/expiry]
  E --> J[Optional recording consent]
  J --> K[Scribe capture]
```

### Medicine onboarding

```mermaid
flowchart LR
  A[Add Vietnamese name/photo] --> B[Normalize candidates]
  B --> C{Identity resolved?}
  C -- No --> D[Clarify; no DDI conclusion]
  D --> B
  C -- Yes --> E[Confirm identity and dose]
  E --> F{At least two medicines?}
  F -- Yes --> G[DrugBank interaction check]
  F -- No --> H[Reminder setup]
  G --> I{Authority ready?}
  I -- No --> J[Fail-closed unavailable state]
  I -- Yes --> K[Warnings, source, next action]
  J --> H
  K --> H
  H --> L[Complete]
```

### Family share lifecycle

```mermaid
stateDiagram-v2
  [*] --> Recipient
  Recipient --> Scope
  Scope --> PermissionDuration
  PermissionDuration --> Purpose
  Purpose --> Review
  Review --> Invited: explicit confirmation
  Invited --> Active: recipient accepts
  Active --> Revoked
  Active --> Expired
  Active --> Renewed
```

### Chat and evidence disclosure

```mermaid
flowchart TD
  A[Choose mode] --> B[Ask]
  B --> C[Safety and evidence processing]
  C --> D[Urgent status if applicable]
  D --> E[Key answer]
  E --> F[What to do]
  F --> G[Uncertainty]
  G --> H[Sources]
  H --> I[User-safe rationale]
  C --> J{Authorized expert/admin?}
  J -- Yes --> K[Role-appropriate optional detail]
  J -- No --> L[No developer telemetry]
```

### Scribe clinician-control lifecycle

```mermaid
stateDiagram-v2
  [*] --> Capture
  Capture --> TranscriptReview: stop/upload succeeds
  TranscriptReview --> Capture: record more
  TranscriptReview --> SOAPReview: transcript saved
  SOAPReview --> TranscriptReview: correction needed
  SOAPReview --> Completion: clinician confirms content
  Completion --> Signed: sign succeeds
  Completion --> FinalizedDraft: legacy capability
  Signed --> Addendum
  Signed --> Exported
  Addendum --> Signed
```

## Journey-wide acceptance criteria

- Users always know the current task, current step, and safe exit.
- Back/refresh/re-auth preserve policy-allowed drafts.
- API errors do not clear accepted input.
- Critical safety messages are visible without opening a disclosure.
- Health mutations require explicit confirmation.
- Sharing shows data, recipient, permissions, duration, revocation, and latest access.
- Clinician signing and legacy finalization are never presented as equivalent.
- Keyboard focus follows the task and returns after overlays close.

