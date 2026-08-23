# CLARA Care — Spatial Editorial Health v4 Architectural Decisions (ADRs)

**Specification:** `CLARA_Care_Spatial_Editorial_Health_Spec_v4.md`  
**Date:** 2026-08-23  

---

### ADR-01: Removal of the Permanent Global Sidebar as Default Shell
* **Status:** Accepted & Implemented
* **Context:** Prior versions mounted a persistent left sidebar on all pages, causing excessive chrome and SaaS dashboard feel.
* **Decision:** Replace the global left sidebar with a 5-layer spatial model:
  1. `L4 TRANSIENT`: Command palette, bottom sheets, context modals.
  2. `L3 ADAPTIVE`: Floating Primary Dock (bottom/rail) & Global Context Bar (top).
  3. `L2 TASK OBJECTS`: HeroObject, active consultation/session cards.
  4. `L1 EDITORIAL`: Continuous reading column, flowing timeline, structured findings.
  5. `L0 AMBIENT`: Subtle background atmospheric glow ($\le 10\%$).

---

### ADR-02: 5 Adaptive Shell Modes
* **Status:** Accepted & Implemented
* **Context:** Different medical tasks require drastically different cognitive density and chrome visibility.
* **Decision:** Implement 5 discrete shell modes via `ShellModeProvider`:
  - `EXPLORE`: Full Floating Dock and Context Bar (e.g. Today, LifeMap, Medicines, Profile).
  - `FOCUS`: Compact chrome and local task tools (e.g. PHR editing, Visit prep, Council setup).
  - `IMMERSIVE`: Fullscreen canvas with receding navigation (e.g. Scribe audio capture, full Chat).
  - `READ`: Single-column editorial layout with prominent citations and uncertainty (e.g. Council result, Living Evidence).
  - `DENSE`: High-density tables, filters, and monitoring rails (e.g. Admin overview, RAG telemetry, Observability).

---

### ADR-03: Decoupled Multi-Track Onboarding
* **Status:** Accepted & Implemented
* **Context:** Previously, clinicians logging in were blocked by consumer biometric PHR onboarding questions (height, weight, blood type).
* **Decision:** Decouple onboarding into 4 independent tracks:
  1. Global first-run (Welcome, language, legal disclaimer, versioned consent; no biometrics).
  2. Optional Personal Health Setup (skippable PHR inputs for consumers).
  3. Professional Orientation (direct clinical tools introduction for doctors/researchers/admins).
  4. Just-in-Time Tool Consent (point-of-use consent for Scribe and Family sharing).
  *Rule:* Professional roles (`doctor`, `researcher`, `admin`) are strictly exempt from PHR redirects.

---

### ADR-04: Single Source of Truth for Cross-Platform Design Tokens
* **Status:** Accepted & Implemented
* **Context:** Manual CSS-to-Dart color synchronization led to drift between Web and Mobile palettes.
* **Decision:** Maintain `packages/design-tokens/clara.tokens.json` as the sole canonical source. `generate.js` deterministically outputs `clara.tokens.css` (Web) and `clara_tokens.g.dart` (Mobile).

---

### ADR-05: Non-PII Telemetry and Zero-CoT Privacy Invariants
* **Status:** Accepted & Implemented
* **Context:** AI interactions must protect patient privacy and comply with GDPR/PDPD.
* **Decision:**
  - Strip all internal reasoning traces (`<think>`, `scratchpad:`, `let's think step by step`) before rendering in consumer DOM.
  - Telemetry and analytics must never transmit prompts, transcripts, SOAP notes, diagnoses, or medication names.
