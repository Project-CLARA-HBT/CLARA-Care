# CLARA Council AI Upgrade - Deep Research, Analysis, and Implementation Plan (2026-04-02)

## 1) Product Goal
- Build an upgraded AI consultation workflow with fewer user steps, modern multi-page review experience, richer clinical insights, and better safety/accuracy controls.

## 2) Competitive + Best-Practice Research (Deep Dive)

### A. Similar products and interaction patterns
1. OpenEvidence positioning emphasizes fast clinical Q&A with cited, peer-reviewed grounding, HCP verification, and high-frequency point-of-care usage.
2. Isabel focuses minimal-input triage/diagnostic expansion with very short guided flows.
3. Glass Health positioning centers differential diagnosis + assessment/plan generation with evidence-backed reasoning.

### B. AI multidisciplinary board patterns
1. Recent review literature on AI in MDT/tumor boards reports common agreement ranges with MDT decisions while stressing human review, bias risk, and external validation gaps.
2. Practical pattern: AI should speed synthesis and standardization, but final decision remains clinician-owned.

### C. Safety/regulatory patterns to follow
1. FDA CDS guidance (January 29, 2026) highlights that clinicians should be able to independently review the basis for recommendations.
2. WHO AI-for-health guidance stresses transparency, oversight, and harm minimization.

## 3) Key Design Decisions for CLARA
1. Reduce friction to one primary case-building page (intake + edit + run).
2. Split high-information output into focused pages to avoid a single overloaded result page:
   - Analyze
   - Details
   - Citations
   - Research
   - Deep Dive
3. Add confidence + data quality + missing-info workflow so low-information cases do not produce false reassurance.
4. Add negation-aware symptom handling (e.g., "no chest pain") to reduce rule false positives.
5. Add evidence-like structured citations and sectioned output for traceability.

## 4) Detailed Implementation Plan (Built and Executed)

### Workstream A - ML council engine accuracy/safety
- Add insufficient-data gate and follow-up questions.
- Add confidence and data-quality scoring.
- Add negation-aware symptom matching + negated red-flag tracking.
- Expand output schema with structured sections: analyze/details/citations/research/deepdive.
- Preserve legacy output fields for compatibility.

### Workstream B - Intake contract upgrade
- Keep transcript/audio extraction.
- Add `missing_fields`, `field_confidence`, and canonical `council_payload` for downstream run.
- Add richer intake sections to support multi-page UX.

### Workstream C - API hardening and orchestration
- Add typed council run request model.
- Add `/api/v1/council/consult` (proxy for one-shot flow).
- Upgrade intake proxy to async HTTP client.
- Add intake upload guards: content type and file-size checks.
- Align role capability summary for admin council access.

### Workstream D - Web UX/UI rebuild for Council
- Rebuild `/council` landing as workspace navigator.
- Rebuild `/council/new` as reduced-flow one-page case builder.
- Rebuild `/council/result` as summary hub.
- Add focused pages:
  - `/council/analyze`
  - `/council/details`
  - `/council/citations`
  - `/council/research`
  - `/council/deepdive`
- Add council view adapter to transform snapshot/raw payload into UI-ready sections.

### Workstream E - Test strategy
- ML: council-focused API tests for new schema and consult flow.
- API: council proxy + mobile summary role consistency tests.
- Web: lint + TS compile checks.

## 5) Research Sources
- FDA CDS Guidance (Jan 2026): https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
- FDA Guidance PDF: https://www.fda.gov/media/109618/download
- WHO AI for Health ethics/governance: https://www.who.int/publications/i/item/9789240029200
- iScience review (AI in multidisciplinary tumor boards): https://www.sciencedirect.com/science/article/pii/S2589004225023430
- Isabel Healthcare: https://www.isabelhealthcare.com/
- OpenEvidence App listing details: https://apps.apple.com/us/app/openevidence/id6612007783
- Glass Health info: https://www.replyglass.health/info

## 6) Current Delivery Status
- Plan implemented end-to-end in ML/API/Web council surfaces with backward compatibility maintained for existing core response fields.
