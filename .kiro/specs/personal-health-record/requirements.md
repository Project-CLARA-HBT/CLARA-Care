# Requirements Document

## Introduction

This feature enhances the **existing, basic Personal Health Record (PHR)** capability in the CLARA-Care monorepo so it becomes fully functional, standards-aligned, and a first-class driver of medication safety and personalization. The current PHR is a single self-overwriting profile (`PhrProfile`) with free-text allergies, conditions, and medications, exposed through `GET/PUT /api/v1/phr/record` and a web editor at `apps/web/app/phr/page.tsx`. It is loosely structured, has no consent enforcement, no medical coding, no history/audit, no provenance, no import/export, no sharing, and no mobile screen. CareGuard/DDI ignores PHR data entirely and reads only the `MedicineCabinet`.

This work is **additive, feature-flagged, and back-compatible**: new behavior defaults off and preserves current behavior and existing medical-safety guardrails. The enhancement introduces structured and coded clinical data (RXCUI, ICD-10/SNOMED, coded allergies), provenance and verification flags, consent enforcement, immutable history/audit, OCR import with mandatory human confirmation, FHIR-aligned export, revocable read-only sharing plus an emergency summary card, medication reminders and refill tracking, stronger validation, a profile-completeness meter, and mobile parity.

CLARA-Care PHR is **self-declared, decision-support data only** — it is NOT an EMR/EHR or a medical device, is not legally binding, and is positioned as a complementary layer to Vietnam's national records (Sổ Sức Khỏe Điện Tử / VNeID). All decision support output directs the user to review with a clinician. The UI is Vietnamese-first with bilingual vi/en copy.

## Glossary

- **PHR (Personal Health Record)**: A self-declared, user-owned health record managed by the individual. In CLARA-Care it is decision-support only, not an official medical record.
- **EMR/EHR (Electronic Medical/Health Record)**: An official clinical record maintained by a healthcare provider or national system. CLARA-Care PHR is explicitly NOT an EMR/EHR.
- **FHIR (Fast Healthcare Interoperability Resources)**: An HL7 standard defining structured healthcare data resources (e.g., Patient, AllergyIntolerance, Condition, MedicationStatement, Observation, Immunization, Procedure, FamilyMemberHistory) and their exchange formats.
- **AllergyIntolerance**: The FHIR resource representing an allergy or intolerance, including coded substance, reaction, criticality/severity, and verificationStatus.
- **MedicationStatement**: The FHIR resource representing a record of medication a patient is taking; for self-declared meds the `informationSource` is the patient.
- **Provenance / informationSource**: Metadata describing the origin of a data entry. In this feature each entry is flagged as `self-declared`, `ocr`, or `imported`.
- **verificationStatus**: A status indicating whether a clinical entry is confirmed. Self-reported entries default to `unconfirmed`.
- **USCDI (United States Core Data for Interoperability)**: A standardized set of health data classes (Allergies, Medications, Problems, Immunizations, Procedures, Labs) used to guide PHR completeness.
- **RxNorm / RXCUI**: A normalized drug naming system; RXCUI is the concept identifier used to code medications and enable reliable drug-drug interaction (DDI) checks.
- **ICD-10**: An international diagnostic code system used to code conditions/problems.
- **SNOMED (SNOMED CT)**: A comprehensive clinical terminology used to code conditions, findings, and substances.
- **VnDrugMapping**: The existing CLARA-Care table mapping Vietnamese brand names to normalized names and RXCUI, reused for medication normalization.
- **MedicineCabinet / MedicineItem**: The existing structured medication store ("tủ thuốc") consumed by CareGuard/DDI; `MedicineItem` carries `rx_cui`, `normalized_name`, `source`, and `ocr_confidence`.
- **CareGuard / DDI**: The CLARA-Care drug-drug interaction and medication-safety checker.
- **Consent**: An explicit, revocable user authorization (modeled on FHIR Consent and the existing `UserConsent` table) gating PHR use in personalization, research, and sharing.
- **Audit**: An append-only, immutable log of edits to and accesses of PHR data.
- **Emergency summary card**: A user-controlled, shareable summary of critical health data (allergies, current medications, conditions, blood type, emergency contact).
- **Feature flag**: A configuration switch that enables new PHR behavior while defaulting to off to preserve current behavior.
- **PHR_System**: The backend service and data layer that stores, validates, and serves PHR data.
- **PHR_Web**: The web PHR interface at `apps/web/app/phr`.
- **PHR_Mobile**: The mobile PHR screen in `apps/mobile`.

## Requirements

### Requirement 1: Schema Migration and Hardening

**User Story:** As a platform operator, I want the PHR schema and its new structures created by versioned migrations, so that database state is deterministic and free of schema drift.

#### Acceptance Criteria

1. THE PHR_System SHALL provide an Alembic migration that creates the `phr_profiles` table with all existing columns and the new structured columns introduced by this feature.
2. WHEN the Alembic migration is applied to a database that lacks the `phr_profiles` table, THE PHR_System SHALL create the table without relying on runtime `create_all` behavior.
3. WHEN the Alembic migration is applied to a database that already contains a `phr_profiles` table created by `create_all`, THE PHR_System SHALL preserve all existing PHR data.
4. THE PHR_System SHALL provide a reversible downgrade path for each new migration introduced by this feature.
5. IF a new migration fails during application, THEN THE PHR_System SHALL roll back the migration transaction and leave the prior schema state intact.

### Requirement 2: Consent Enforcement

**User Story:** As a PHR owner, I want my explicit consent to gate how my PHR data is used, so that my health information is only used for purposes I have authorized.

#### Acceptance Criteria

1. THE PHR_System SHALL record consent for PHR data use as a typed, versioned `UserConsent` entry distinguishing personalization use, research use, and sharing.
2. WHERE the PHR feature flag is enabled AND a personalization consent record is absent for the requesting user, THE PHR_System SHALL exclude PHR data from personalization context.
3. WHERE the PHR feature flag is enabled AND a research consent record is absent for the requesting user, THE PHR_System SHALL exclude PHR data from research personal-mode context.
4. WHEN a user revokes a previously granted PHR consent, THE PHR_System SHALL stop using PHR data for the revoked purpose on subsequent requests.
5. IF a sharing action is requested AND a sharing consent record is absent for the requesting user, THEN THE PHR_System SHALL reject the sharing action with a descriptive error.
6. THE PHR_System SHALL record the consent type, consent version, and timestamp for each consent grant and revocation.

### Requirement 3: Structured and Coded Medications

**User Story:** As a PHR owner, I want my medications stored with structured dose, frequency, and route plus an RXCUI code, so that interaction checks and personalization are reliable.

#### Acceptance Criteria

1. THE PHR_System SHALL store each PHR medication with structured fields for name, dose amount, dose unit, frequency, route, start date, and current-status.
2. WHEN a PHR medication name matches an entry in VnDrugMapping or the existing normalization path, THE PHR_System SHALL assign the corresponding normalized name and RXCUI to the medication.
3. WHERE a PHR medication name cannot be normalized to an RXCUI, THE PHR_System SHALL store the medication with an empty RXCUI and mark it as unnormalized.
4. WHEN two PHR medications resolve to the same RXCUI, THE PHR_System SHALL flag them as duplicates for reconciliation.
5. IF a medication dose unit is provided that is not in the supported unit set, THEN THE PHR_System SHALL reject the medication entry with a descriptive error identifying the invalid unit.

### Requirement 4: Coded Allergies

**User Story:** As a PHR owner, I want my allergies recorded with a coded substance, reaction, severity, and verification status, so that allergy-aware safety checks can run reliably.

#### Acceptance Criteria

1. THE PHR_System SHALL store each allergy with a substance, a reaction description, a severity of `mild`, `moderate`, `severe`, or `unknown`, and a verificationStatus.
2. WHEN an allergy substance matches a known coding entry, THE PHR_System SHALL assign the corresponding coded substance identifier to the allergy.
3. WHERE an allergy is created from self-declared input, THE PHR_System SHALL set the allergy verificationStatus to `unconfirmed`.
4. THE PHR_System SHALL accept allergy entries whose substance is uncoded by storing the free-text substance and marking the substance as uncoded.
5. IF an allergy severity value is provided that is outside the allowed severity set, THEN THE PHR_System SHALL reject the allergy entry with a descriptive error.

### Requirement 5: Coded Conditions

**User Story:** As a PHR owner, I want my conditions recorded with ICD-10 or SNOMED codes and a clinical status, so that my problem list is structured and interoperable.

#### Acceptance Criteria

1. THE PHR_System SHALL store each condition with a name, a clinical status of `active`, `resolved`, `monitoring`, or `unknown`, an optional diagnosed-on date, and optional ICD-10 and SNOMED codes.
2. WHEN a condition name matches a known coding entry, THE PHR_System SHALL offer the corresponding ICD-10 or SNOMED code for the condition.
3. WHERE a condition is uncoded, THE PHR_System SHALL store the free-text condition name and mark the condition as uncoded.
4. IF a condition clinical status value is provided that is outside the allowed status set, THEN THE PHR_System SHALL reject the condition entry with a descriptive error.

### Requirement 6: Provenance and Verification

**User Story:** As a PHR owner, I want every entry tagged with where it came from and whether it is verified, so that I and the system can judge how much to trust each entry.

#### Acceptance Criteria

1. THE PHR_System SHALL tag each allergy, condition, and medication entry with an informationSource of `self-declared`, `ocr`, or `imported`.
2. WHEN an entry is created through manual editing, THE PHR_System SHALL set the entry informationSource to `self-declared`.
3. WHEN an entry is created through OCR import, THE PHR_System SHALL set the entry informationSource to `ocr`.
4. WHEN an entry is created through a structured import, THE PHR_System SHALL set the entry informationSource to `imported`.
5. THE PHR_Web SHALL display the informationSource and verificationStatus for each entry.
6. WHERE PHR data is used in DDI or personalization output, THE PHR_System SHALL hedge the output to indicate it is based on user-entered information.

### Requirement 7: Unified Medication Reconciliation and Allergy-Aware DDI

**User Story:** As a PHR owner, I want my PHR medications and allergies reconciled with the medicine cabinet and used by CareGuard, so that interaction checks reflect everything I take and am allergic to.

#### Acceptance Criteria

1. WHERE the PHR feature flag is enabled, THE PHR_System SHALL provide CareGuard with a reconciled medication set combining PHR medications and MedicineCabinet items keyed by RXCUI.
2. WHEN PHR medications and MedicineCabinet items resolve to the same RXCUI, THE PHR_System SHALL present them as a single reconciled medication while retaining both source records.
3. WHERE the PHR feature flag is enabled AND personalization consent is present, THE PHR_System SHALL provide CareGuard with the user's coded allergies for allergy-aware interaction checking.
4. WHEN an allergy-aware check finds a conflict between a reconciled medication and a recorded allergy, THE PHR_System SHALL include the allergy conflict in the CareGuard result.
5. WHILE the PHR feature flag is disabled, THE PHR_System SHALL provide CareGuard with only the MedicineCabinet data, preserving current behavior.
6. THE PHR_System SHALL preserve both the PHR medication store and the MedicineCabinet store without deleting data from either during reconciliation.

### Requirement 8: History, Versioning, and Audit

**User Story:** As a PHR owner, I want an immutable history of changes to and accesses of my record, so that I can trust the record and review what changed and who viewed it.

#### Acceptance Criteria

1. WHEN a PHR profile or entry is created, updated, or deleted, THE PHR_System SHALL append an immutable audit record capturing the actor, action, timestamp, and the affected field or entry.
2. THE PHR_System SHALL store a version snapshot of the PHR record on each committed change rather than only retaining the latest `updated_at`.
3. WHEN PHR data is read through sharing or by a non-owner, THE PHR_System SHALL append an access audit record capturing the accessor, timestamp, and scope of data accessed.
4. THE PHR_System SHALL prevent modification or deletion of existing audit records.
5. WHEN the owner requests their change history, THE PHR_System SHALL return the recorded version snapshots in reverse chronological order.
6. WHERE an update modifies only specific entries or fields, THE PHR_System SHALL apply the change at the entry or field level rather than overwriting the entire profile wholesale.

### Requirement 9: OCR Import with Mandatory Human Confirmation

**User Story:** As a PHR owner, I want to import prescriptions and labs via OCR but confirm the extracted data before it is saved, so that imperfect OCR never silently corrupts my record.

#### Acceptance Criteria

1. WHEN a user submits a prescription or lab document for OCR import, THE PHR_System SHALL return extracted candidate entries without committing them to the PHR.
2. THE PHR_System SHALL require an explicit user confirmation step before committing OCR-extracted entries to the PHR.
3. WHILE reviewing OCR-extracted entries, THE PHR_Web SHALL allow the user to edit, accept, or discard each candidate entry.
4. WHEN OCR-extracted entries are confirmed, THE PHR_System SHALL store them with informationSource `ocr` and retain the per-entry OCR confidence.
5. IF a user abandons the OCR review without confirming, THEN THE PHR_System SHALL discard the candidate entries without modifying the PHR.
6. THE PHR_System SHALL reuse the existing OCR bridge used by the MedicineCabinet for document extraction.

### Requirement 10: Structured Lab and Observation Capture

**User Story:** As a PHR owner, I want to record lab results and observations as structured data, so that my record covers USCDI lab data and supports interoperability.

#### Acceptance Criteria

1. THE PHR_System SHALL store each observation with a name, value, unit, and observation date.
2. WHEN an observation is created, THE PHR_System SHALL tag it with an informationSource of `self-declared`, `ocr`, or `imported`.
3. IF an observation value is non-numeric for a unit that requires a numeric value, THEN THE PHR_System SHALL reject the observation with a descriptive error.
4. THE PHR_System SHALL include recorded observations in the FHIR-aligned export as Observation resources.

### Requirement 11: FHIR-Aligned Export and Portability

**User Story:** As a PHR owner, I want to export my record in a FHIR-aligned format, so that my data is portable and ready for future Sổ Sức Khỏe Điện Tử / VNeID interchange.

#### Acceptance Criteria

1. WHEN the owner requests an export, THE PHR_System SHALL produce a FHIR-aligned bundle containing Patient, AllergyIntolerance, Condition, MedicationStatement, and Observation resources reflecting the PHR data.
2. THE PHR_System SHALL set the `informationSource` of exported self-declared resources to the patient.
3. THE PHR_System SHALL support exporting a single record type and exporting the full bundle.
4. WHEN an export is produced, THE PHR_System SHALL provide it as a structured downloadable file.
5. WHERE an entry carries a verificationStatus, THE PHR_System SHALL include that verificationStatus in the corresponding exported resource.

### Requirement 12: Read-Only Sharing and Access Logging

**User Story:** As a PHR owner, I want to grant revocable read-only access to a caregiver or clinician, so that they can view my record while I retain control and visibility.

#### Acceptance Criteria

1. WHEN the owner creates a share, THE PHR_System SHALL generate a revocable read-only share link reusing the workspace share mechanism.
2. WHILE a share link is active, THE PHR_System SHALL grant read-only access to the shared PHR data and reject any modification attempt through the share.
3. WHEN the owner revokes a share link, THE PHR_System SHALL deny subsequent access through that link.
4. WHEN PHR data is accessed through a share link, THE PHR_System SHALL append an access audit record capturing the accessor, timestamp, and scope.
5. WHERE a share is created with an expiry, THE PHR_System SHALL deny access through the share after the expiry time.
6. IF sharing consent is absent for the owner, THEN THE PHR_System SHALL reject creation of a share link with a descriptive error.

### Requirement 13: Emergency Summary Card

**User Story:** As a PHR owner, I want a user-controlled emergency summary card, so that critical health data can be shared quickly in an emergency.

#### Acceptance Criteria

1. THE PHR_System SHALL generate an emergency summary card containing allergies, current medications, conditions, blood type, and emergency contact.
2. WHEN the owner shares the emergency summary card, THE PHR_System SHALL append an access audit record for each access to the card.
3. THE PHR_System SHALL allow the owner to control which fields are included in the emergency summary card.
4. WHILE no current medications, allergies, or conditions are recorded, THE PHR_System SHALL render the corresponding emergency card section as empty rather than failing.
5. THE PHR_System SHALL render the emergency summary card with the persistent self-declared, decision-support-only disclaimer.

### Requirement 14: Medication Reminders and Refill Tracking

**User Story:** As a PHR owner, I want medication reminders and refill tracking with an optional caregiver missed-dose nudge, so that I take medications on schedule and caregivers can help.

#### Acceptance Criteria

1. WHERE a medication is marked current with a defined frequency, THE PHR_System SHALL allow the owner to configure reminders for that medication.
2. WHEN a configured reminder time is reached, THE PHR_System SHALL issue a medication reminder to the owner.
3. THE PHR_System SHALL track remaining supply and refill due dates for medications with a recorded quantity.
4. WHEN a tracked medication's remaining supply reaches the refill threshold, THE PHR_System SHALL issue a refill reminder.
5. WHERE the owner has enabled a caregiver missed-dose nudge AND a caregiver share is active, IF a dose is not marked taken within the configured window, THEN THE PHR_System SHALL notify the designated caregiver.

### Requirement 15: Validation and Data Sanity

**User Story:** As a PHR owner, I want my entries validated for sanity, so that my record stays accurate and free of impossible or duplicate data.

#### Acceptance Criteria

1. IF a date of birth is in the future, THEN THE PHR_System SHALL reject the profile update with a descriptive error.
2. IF a condition diagnosed-on date or a medication start date is in the future, THEN THE PHR_System SHALL reject the entry with a descriptive error.
3. THE PHR_System SHALL assign and verify entry identifiers on the server rather than trusting client-generated identifiers.
4. WHEN a new entry duplicates an existing entry within the same category, THE PHR_System SHALL flag the entry as a duplicate.
5. THE PHR_System SHALL enforce length and range limits on profile and entry fields and reject values outside those limits with a descriptive error.

### Requirement 16: Profile Completeness Meter

**User Story:** As a PHR owner, I want to see how complete my record is, so that I am encouraged to add the data that improves safety checks and personalization.

#### Acceptance Criteria

1. THE PHR_System SHALL compute a completeness score for the PHR record based on the presence of USCDI-aligned data classes.
2. WHEN the owner views the PHR, THE PHR_Web SHALL display the completeness score and the data classes that are missing.
3. WHEN the owner adds data to a previously missing data class, THE PHR_System SHALL increase the completeness score on the next computation.
4. THE PHR_System SHALL exclude PHR PII from any telemetry emitted while computing or displaying the completeness score.

### Requirement 17: Mobile Parity

**User Story:** As a mobile user, I want a PHR screen on mobile, so that I can view and edit my record from my phone.

#### Acceptance Criteria

1. THE PHR_Mobile SHALL provide a screen to view the PHR profile, allergies, conditions, and medications.
2. THE PHR_Mobile SHALL allow the owner to edit profile fields and entries subject to the same validation enforced by the PHR_System.
3. THE PHR_Mobile SHALL display the informationSource and verificationStatus for each entry.
4. THE PHR_Mobile SHALL render the persistent self-declared, decision-support-only disclaimer.
5. THE PHR_Mobile SHALL present PHR interface text Vietnamese-first with bilingual vi/en copy.

### Requirement 18: Guardrails, Back-Compatibility, and Privacy Preservation

**User Story:** As a platform owner, I want the enhancements to preserve existing behavior, guardrails, and privacy, so that the rollout is safe and reversible.

#### Acceptance Criteria

1. WHILE the PHR feature flag is disabled, THE PHR_System SHALL preserve the current `GET/PUT /api/v1/phr/record` behavior and existing response shape.
2. THE PHR_System SHALL preserve RBAC requiring roles `normal`, `researcher`, `doctor`, or `admin` for PHR access.
3. THE PHR_System SHALL restrict PHR write and full-read access to the owning user, except where the owner has granted an explicit share.
4. THE PHR_Web and PHR_Mobile SHALL display a persistent disclaimer stating the PHR is self-declared, decision-support only, not an EMR/EHR, and not legally binding.
5. WHERE DDI output is produced from PHR data, THE PHR_System SHALL include guidance to review the result with a clinician.
6. THE PHR_System SHALL exclude PHR PII from telemetry and analytics and SHALL de-identify PHR data before any analytics use.
7. THE PHR_System SHALL present PHR interface text and generated output Vietnamese-first with bilingual vi/en copy.

### Requirement 19: Regulatory Compliance Integration (AI Law 134/2025 + PDPD 13/2023)

**User Story:** As a data subject, I want my PHR — which is sensitive health data — to be covered by the platform's data-subject rights and cross-border controls, so that my most sensitive information is handled lawfully.

This requirement aligns the PHR with the `regulatory-compliance` spec; it is additive and feature-flagged, and where compliance flags are off the PHR behaves exactly as defined by Requirements 1–18.

#### Acceptance Criteria

1. THE PHR_System SHALL classify all PHR data (profile, allergies, conditions, medications, labs/observations) as sensitive personal data under PDPD Article 2(4).
2. WHEN a data subject exercises a DSAR export (`regulatory-compliance` Req 3), THE PHR_System SHALL include the requesting user's complete PHR data in the machine-readable export.
3. WHEN a data subject's deletion DSAR is fulfilled, THE PHR_System SHALL delete or irreversibly anonymize their PHR data while preserving the no-PII compliance/audit records.
4. WHERE cross-border-processing consent is absent AND PHR data would be sent to an offshore model processor, THE PHR_System SHALL exclude identifiable PHR data from that outbound call (`regulatory-compliance` Req 4).
5. THE PHR_System SHALL surface the PHR sharing and personalization consents through the unified Consent Center rather than a PHR-only toggle, using the shared `UserConsent` purpose ledger.
6. THE PHR_System SHALL ensure PHR-derived decision support carries the AI transparency disclosure (model/version, not-a-clinician) consistent with `regulatory-compliance` Req 1 when that flag is enabled.
