# PH04 / A07 — Risk Register: Mobile Org Switch & Deep-Link Test Suite

**Phase:** PH04 (Multi-tenant organizations và workspaces)
**Subagent:** A07 (Tests + CI)
**Role:** Tests + CI
**Frozen HEAD SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`
**Branch:** `phase/ph04-a07`
**Date:** October 21, 2026
**Status:** COMPLETE / PASSED

---

## 1. Overview

This risk register evaluates operational, security, and privacy risks associated with mobile and web deep links, organization context switching, invitation capability processing, and multi-tenant workspace isolation.

---

## 2. Risk Matrix & Mitigations

### RISK-ORG-01: Capability Leakage via URL Path Logging
- **Category:** Security / Information Disclosure (P0)
- **Description:**
  If invitation or authorization tokens are accepted via URL path parameters (e.g., `POST /api/v1/invitations/{token}/accept`), web proxies, CDN access logs, browser history, and APM tools will capture the secret token in plaintext.
- **Compensating Controls:**
  1. The API permanently deprecates URL path acceptance: `POST /invitations/{token}/accept` immediately returns HTTP `410 Gone` without parsing or echoing the secret.
  2. Tokens must be transmitted via JSON request bodies or custom headers (`X-Organization-Invitation-Token`, `X-Family-Invitation-Token`).
  3. Verified by `TestInvitationAcceptanceCapabilityContracts.test_invitation_capability_never_processed_from_url_path`.

---

### RISK-ORG-02: Open Redirect and Deep Link Scheme Hijacking
- **Category:** Security / Phishing & Intent Hijacking (P1)
- **Description:**
  Malicious intents or crafted links (such as `http://`, `javascript:`, or spoofed domains like `https://evil-theclaracare.com`) could trick mobile intake into routing tokens to external attacker endpoints or executing unintended scripts.
- **Compensating Controls:**
  1. Intake parser strictly enforces an allowlist of approved schemes (`https`, `clara`) and canonical hosts (`theclaracare.com`, `www.theclaracare.com`).
  2. Rejects path traversals (`..`), double slashes, and null byte injections (`%00`).
  3. Verified by `TestDeepLinkIntakeAndSanitization` tests (`test_reject_insecure_or_unapproved_schemes`, `test_reject_untrusted_foreign_hosts`, `test_reject_path_traversal_and_malformed_uris`).

---

### RISK-ORG-03: Multi-Tenant Cache Poisoning on Organization Switch
- **Category:** Privacy / Cross-Tenant Data Leakage (P0)
- **Description:**
  When a user switches between organizations or profiles, intermediary caches (browsers, corporate HTTP proxies) might cache organization-specific data under a generic URL (such as `/profiles/context` or `/workspace/summary`) and serve it to a different organization context.
- **Compensating Controls:**
  1. Context-dependent routes MUST emit `Cache-Control: no-store, private`.
  2. Context-dependent routes MUST declare `Vary: Authorization, X-CLARA-Profile-Context, X-CLARA-Org-Context`.
  3. Verified by `TestCrossOrganizationContextAndSwitching.test_context_resolution_security_and_cache_headers`.

---

### RISK-ORG-04: Confused Deputy via Client Presentation Mode Tampering
- **Category:** Security / Privilege Escalation (P0)
- **Description:**
  A client could attempt to set headers indicating a privileged presentation mode (e.g. `X-CLARA-Presentation-Mode: clinical` or `admin`) to bypass role checks on clinician or administrative endpoints.
- **Compensating Controls:**
  1. Invariant: Presentation mode modifies ONLY client layout and navigation. Server-side RBAC dependencies (`require_roles(...)`) evaluate strictly against cryptographically signed JWT tokens or session cookies.
  2. A normal user sending clinical or admin presentation headers is denied with HTTP 403 on protected routes.
  3. Verified by `TestMobileOrgSwitchingAndSummaryContracts.test_presentation_mode_does_not_mutate_backend_rbac`.

---

### RISK-ORG-05: Cross-Tenant Resource Enumeration and IDOR
- **Category:** Security / Insecure Direct Object Reference (P1)
- **Description:**
  A tenant attempting to read, update, or delete another tenant's workspace folder, channel, or note could discover entity existence if the API returns 403 Forbidden instead of 404 Not Found.
- **Compensating Controls:**
  1. Database queries filter by owner/tenant ID before returning results (`user_id == current_user.id`).
  2. Non-owned or foreign-tenant resources return HTTP 404 Not Found, treating them as non-existent to prevent enumeration.
  3. Verified by `TestMultiTenantWorkspaceAndOrgIsolation.test_workspace_folders_and_channels_isolated_per_tenant_user` and `test_workspace_notes_cross_tenant_isolation`.
