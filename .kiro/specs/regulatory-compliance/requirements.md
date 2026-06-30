# Requirements Document

## Introduction

This feature operationalizes CLARA-Care's compliance with the two Vietnamese
legal frameworks that govern an AI medical assistant: the **Law on Artificial
Intelligence No. 134/2025/QH15** (adopted 10 December 2025, effective 1 March
2026) and **Decree No. 13/2023/NĐ-CP on Personal Data Protection** (PDPD). It is
**additive, feature-flagged, and back-compatible**: it does not change existing
clinical behavior, and it preserves every existing safety guardrail (RBAC,
consent gating, emergency fast-path, FIDES verification, no-PII telemetry, CSRF).

The work makes CLARA's *already-strong* safety architecture **legally legible**:
it documents and enforces the obligations that attach to a **high-risk AI system**
in the health domain, gives data subjects the rights the PDPD grants them
(access, correction, deletion, withdrawal of consent, portability), produces the
records a regulator or auditor would request (AI system transparency notice,
data-processing record, risk-management file, incident log), and adds the
runtime controls (data-subject-request handling, cross-border-transfer gating,
retention enforcement, model/version disclosure) that turn policy into product.

CLARA-Care is **decision-support software, self-declared data, not a medical
device and not an EMR/EHR**. Nothing in this feature changes that positioning;
rather, it records and surfaces it consistently so the product's legal status is
unambiguous to users, clinicians, and regulators. All copy is Vietnamese-first
with bilingual vi/en where a legal term of art requires it.

## Glossary

- **AI Law / Luật 134/2025**: Law on Artificial Intelligence No. 134/2025/QH15, the first comprehensive, risk-based AI statute in Vietnam (effective 1 March 2026).
- **PDPD / NĐ13**: Decree No. 13/2023/NĐ-CP on Personal Data Protection — Vietnam's baseline personal-data-protection regime.
- **High-Risk AI System**: An AI system whose use may materially affect health, safety, or fundamental rights. A clinical decision-support assistant is treated as high-risk for the purposes of this feature.
- **AI Transparency Notice**: A user-facing disclosure that the user is interacting with an AI system, what it does, its limitations, the model/version in use, and that it does not replace a clinician.
- **Sensitive Personal Data / Dữ liệu cá nhân nhạy cảm**: Per PDPD Article 2(4), includes health data. CLARA's PHR, medicine cabinet, allergies, conditions, and clinical queries are sensitive personal data.
- **Data Subject / Chủ thể dữ liệu**: The natural person to whom personal data relates (the CLARA end user).
- **Data Controller / Bên Kiểm soát dữ liệu**: The party that determines the purpose and means of processing (the CLARA operator).
- **Data Processor / Bên Xử lý dữ liệu**: A third party processing data on the controller's behalf (e.g., the LLM/embedding provider).
- **DSAR (Data Subject Access Request)**: A request by a data subject to exercise a PDPD right (access, correction, deletion, restriction, portability, consent withdrawal).
- **DPIA / Hồ sơ đánh giá tác động xử lý dữ liệu cá nhân**: The data-processing-impact assessment dossier the PDPD requires controllers of sensitive data to maintain.
- **Risk-Management File**: The AI-Law artifact recording the system's intended purpose, risk classification, identified risks, mitigations, human-oversight design, and evaluation results.
- **Cross-Border Transfer / Chuyển dữ liệu xuyên biên giới**: Transfer of personal data outside Vietnam (e.g., sending query text to an offshore LLM endpoint), which the PDPD regulates and which requires a Transfer Impact Assessment.
- **Human Oversight / Giám sát của con người**: The AI-Law requirement that a high-risk system keep a human in/over the loop; in CLARA this is the "review with a clinician" directive plus clinician-facing review surfaces.
- **Consent Ledger**: The versioned, append-only record of consent grants and withdrawals (the existing `UserConsent` model, extended).
- **No-PII Telemetry**: The existing invariant that metrics, flow events, and analytics exclude PII; reaffirmed and made auditable here.
- **Compliance_System**: The backend service/data layer that records compliance artifacts, processes DSARs, and enforces transfer/retention controls.
- **Compliance_Web**: The web surfaces for the transparency notice, consent center, DSAR self-service, and legal pages.
- **Feature flag**: A configuration switch enabling new compliance behavior while defaulting to a state that preserves current behavior.

## Requirements

### Requirement 1: AI System Transparency and Disclosure (AI Law Art. on transparency)

**User Story:** As a user, I want to be clearly told I am interacting with an AI medical assistant and what its limits are, so that I can use it safely and give informed consent.

#### Acceptance Criteria

1. THE Compliance_System SHALL present an AI Transparency Notice that states the user is interacting with an AI system, the system's intended purpose, its limitations, and that it does not replace a licensed clinician.
2. WHEN a user first reaches any medical content surface, THE Compliance_System SHALL ensure the AI Transparency Notice has been presented at least once and recorded as acknowledged before medical content is served.
3. THE Compliance_System SHALL disclose, in a machine-readable and user-visible form, the AI model family and version used to generate a given response.
4. WHERE a response is produced by the local deterministic fallback rather than the primary model, THE Compliance_System SHALL label the response as a degraded/fallback answer.
5. THE Compliance_System SHALL classify and record CLARA as a high-risk AI system in the health domain within its risk-management file.
6. THE AI Transparency Notice SHALL be versioned, and a new version SHALL require re-acknowledgement on next access.

### Requirement 2: Lawful Basis and Granular Consent for Sensitive Data (PDPD Arts. 11, 13, 17)

**User Story:** As a data subject, I want to give specific, informed, revocable consent for each distinct use of my health data, so that my sensitive data is processed only as I authorize.

#### Acceptance Criteria

1. THE Compliance_System SHALL record a typed, versioned consent for each distinct processing purpose: core service, personalization, research use, third-party/cross-border model processing, and sharing.
2. THE Compliance_System SHALL treat health data, clinical queries, PHR, medicine cabinet, allergies, and conditions as sensitive personal data subject to explicit consent.
3. WHEN consent for a purpose is absent or withdrawn, THE Compliance_System SHALL exclude the data subject's data from that purpose on all subsequent requests.
4. THE Compliance_System SHALL record, for each consent grant and withdrawal, the purpose, the policy version consented to, and the timestamp.
5. WHERE the AI Law requires it for a high-risk system, THE Compliance_System SHALL obtain explicit, separately-toggleable consent before sending a user's sensitive data to a third-party or offshore model processor.
6. THE Compliance_System SHALL make consent withdrawal at least as easy as granting it, exposed through a self-service consent center.

### Requirement 3: Data Subject Rights / DSAR (PDPD Arts. 9, 14–16)

**User Story:** As a data subject, I want to access, correct, export, and delete my personal data, so that I retain control over my information as the law guarantees.

#### Acceptance Criteria

1. THE Compliance_System SHALL allow an authenticated data subject to request a machine-readable export of all personal data CLARA holds about them.
2. THE Compliance_System SHALL allow an authenticated data subject to request correction of their personal data.
3. THE Compliance_System SHALL allow an authenticated data subject to request deletion of their personal data, subject to lawful retention exceptions which SHALL be disclosed.
4. THE Compliance_System SHALL allow an authenticated data subject to request restriction of processing or withdrawal of consent for any purpose.
5. WHEN a DSAR is submitted, THE Compliance_System SHALL record the request type, timestamp, and resolution status in an append-only DSAR log without storing unnecessary additional PII.
6. THE Compliance_System SHALL acknowledge a DSAR immediately and SHALL track it against the statutory response window.
7. WHEN a deletion request is fulfilled, THE Compliance_System SHALL remove or irreversibly anonymize the subject's personal data while preserving append-only audit/compliance records that themselves contain no PII.

### Requirement 4: Cross-Border Transfer Control (PDPD Arts. 25–27)

**User Story:** As a data controller, I want every transfer of personal data outside Vietnam to be assessed, gated by consent, and logged, so that offshore model processing is lawful.

#### Acceptance Criteria

1. THE Compliance_System SHALL maintain a Transfer Impact Assessment record for each third-party processor that receives personal data outside Vietnam, including the LLM and embedding providers.
2. WHERE cross-border-processing consent is absent for a user, THE Compliance_System SHALL NOT transmit that user's identifiable sensitive data to an offshore processor and SHALL either use an in-country path or degrade gracefully.
3. THE Compliance_System SHALL minimize personal data in any outbound model request, transmitting only what is necessary for the inference and excluding direct identifiers where feasible.
4. THE Compliance_System SHALL record, per outbound processing event, the processor identity, purpose, and a no-PII event reference, without logging the transmitted content.
5. THE Compliance_System SHALL expose the list of third-party processors and their jurisdictions in the privacy policy.

### Requirement 5: Human Oversight and Decision-Support Boundaries (AI Law human-oversight obligations)

**User Story:** As a regulator, I want assurance that a human remains responsible for clinical decisions, so that the AI never operates as an autonomous medical authority.

#### Acceptance Criteria

1. THE Compliance_System SHALL preserve the existing legal hard-guard that blocks prescribing, definitive diagnosis, and personal-dosage outputs.
2. THE Compliance_System SHALL preserve the existing emergency fast-path that directs the user to emergency services without diagnostic reasoning.
3. THE Compliance_System SHALL ensure every medical response carries a directive to review with a licensed clinician.
4. THE Compliance_System SHALL preserve FIDES CRITICAL-claim blocking for failed drug-dosage and DDI verification.
5. THE Compliance_System SHALL record, for high-risk outputs, the verification verdict and whether human-review escalation was advised.

### Requirement 6: Record-Keeping, Risk Management, and Auditability (AI Law documentation duties)

**User Story:** As a compliance officer, I want the statutory records maintained automatically, so that an audit can be satisfied without reconstructing history.

#### Acceptance Criteria

1. THE Compliance_System SHALL maintain a versioned Risk-Management File describing intended purpose, risk classification, identified risks, mitigations, human-oversight design, and evaluation summary.
2. THE Compliance_System SHALL maintain a Data-Processing Record (ROPA) enumerating processing activities, purposes, data categories, recipients, retention, and legal basis.
3. THE Compliance_System SHALL maintain an append-only compliance event log for consent changes, DSARs, transfer assessments, and incidents, containing no PII.
4. THE Compliance_System SHALL maintain a DPIA dossier for sensitive-data processing.
5. WHERE a serious incident or safety event occurs, THE Compliance_System SHALL record it in an incident log with severity, timestamp, and remediation status.
6. THE Compliance_System SHALL expose these records to authorized admin roles only, never to end users.

### Requirement 7: Retention and Data Minimization (PDPD data-minimization principle)

**User Story:** As a data subject, I want my data kept no longer than necessary, so that my exposure is minimized.

#### Acceptance Criteria

1. THE Compliance_System SHALL define a retention period per data category in the Data-Processing Record.
2. WHEN data exceeds its retention period, THE Compliance_System SHALL delete or anonymize it through a scheduled, auditable process.
3. THE Compliance_System SHALL exclude PII from telemetry, metrics, flow events, and analytics, reaffirming the existing no-PII invariant.
4. THE Compliance_System SHALL retain append-only audit and compliance records longer where required for legal defensibility, provided those records contain no PII.

### Requirement 8: Guardrails, Back-Compatibility, and Privacy Preservation

**User Story:** As a platform operator, I want compliance features to default safely and never regress existing behavior, so that adoption carries no clinical or operational risk.

#### Acceptance Criteria

1. THE Compliance_System SHALL gate all new enforcing behavior behind feature flags whose defaults preserve current behavior.
2. WHERE all compliance flags are off, THE Compliance_System SHALL behave equivalently to the pre-feature system.
3. THE Compliance_System SHALL NOT introduce PII into any telemetry, log, or analytics surface.
4. THE Compliance_System SHALL enforce RBAC so compliance-admin surfaces are reachable only by authorized roles.
5. THE Compliance_System SHALL preserve CSRF protection on all new cookie-authenticated mutating endpoints.
6. THE Compliance_System SHALL keep all new admin/compliance endpoints behind authentication and owner/role scoping.
