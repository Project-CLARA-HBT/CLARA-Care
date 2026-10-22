# Runbook: Consent Policy Management & Owner Approval Workflow (PH05)

## 1. Overview
This runbook governs the publication, version bumping, and clinical owner approval required before modifying statutory consent policies in The CLARA Care.

## 2. Policy Version Bumping Protocol
When a policy update is required (e.g. adding a new AI model provider, updating medical warning disclaimers, or broadening data sharing scopes):
1. **Drafting Policy Text:** Draft bilingual Vietnamese and English text.
2. **Hash Computation:** Compute SHA-256 digest of policy body.
3. **Clinical Owner Approval:** Requires dual sign-off from Chief Medical Officer (CMO) and Data Protection Officer (DPO).
4. **Publish Snapshot:** Insert row into `consent_policy_snapshots` with `is_active=True` and updated `policy_version`.
5. **Config Update:** Update `MEDICAL_DISCLAIMER_VERSION` in central configuration to enforce client reconsent.

## 3. Immediate Client Enforcement
- Existing user sessions encountering the updated version requirement receive HTTP 403 on medical endpoints.
- Mobile and Web UX prompt user with `ConsentExplanationSheet` highlighting delta in terms.
- Prior grants remain in the append-only ledger (`UserConsent`) for historical compliance proof.
