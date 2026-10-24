# Test Report — PH11 A07 (Tests + CI: Mobile Consented FHIR Share)

## Environment
- Phase: `PH11` — FHIR R4 interoperability production profiles
- Base commit SHA: `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
- Branch: `phase/ph11-a07`
- Worktree: `/dev/shm/clara_worktrees/PH11_A07`
- Python: `3.12.3` / `uv`
- OS: Linux x86_64

## Verification Commands and Results

### 1. Mobile Consented FHIR Share Test Suite
```bash
DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db AUTH_AUTO_PROVISION_USERS=true AUTH_BOOTSTRAP_ADMIN_ENABLED=true uv run pytest -v tests/test_mobile_consented_fhir_share.py
```
Exit Code: `0`

Output:
```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
hypothesis profile 'default'
rootdir: /dev/shm/clara_worktrees/PH11_A07/services/api
configfile: pyproject.toml
plugins: anyio-4.14.2, asyncio-1.4.0, hypothesis-6.167.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 18 items

tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_mobile_share_end_to_end_flow PASSED [  5%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_mobile_share_care_coordination_purpose PASSED [ 11%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_consent_gating_unconsented_rejected_with_428 PASSED [ 16%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_consent_revocation_invalidates_export PASSED [ 22%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_unsupported_purpose_rejected_with_422 PASSED [ 27%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_unauthenticated_request_rejected_with_401 PASSED [ 33%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_cross_user_idor_blocked_with_404 PASSED [ 38%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_admin_direct_access_blocked_without_break_glass PASSED [ 44%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_family_delegate_expired_grant_rejected PASSED [ 50%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_family_delegate_revoked_grant_rejected PASSED [ 55%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_family_delegate_missing_action_rejected PASSED [ 61%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_family_delegate_missing_dataclass_rejected PASSED [ 66%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_family_delegate_authorized_export_succeeds PASSED [ 72%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_feature_flag_disabled_returns_404 PASSED [ 77%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_ips_overclaim_protection_returns_409 PASSED [ 83%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_conformance_statement_declares_non_general_server PASSED [ 88%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_minimum_necessary_demographic_minimization PASSED [ 94%]
tests/test_mobile_consented_fhir_share.py::TestMobileConsentedFhirShareIntegration::test_draft_and_unconfirmed_records_excluded PASSED [100%]

======================== 18 passed, 1 warning in 38.43s ========================
```

### 2. Code Linting & Style Check
```bash
ruff check services/api/tests/test_mobile_consented_fhir_share.py
```
Exit Code: `0`
Output: `All checks passed!`

### 3. Path Lane Isolation Check
```bash
python3 ./scripts/ci/check_agent_path_acl.py -a A07 -p PH11
```
Exit Code: `0`
Output:
```
================================================================================
PATH ACL CHECKER — PASSED (Agent: A07, Phase: PH11)
================================================================================
Evaluated Files : 5
Allowed Lanes   : 8
  - services/api/tests/
  - services/ml/tests/
  - apps/web/e2e/
  - .github/workflows/
  - artifacts/PH11/A07/change_manifest.json
  - artifacts/PH11/A07/test_report.md
  - artifacts/PH11/A07/risk_register.md
  - artifacts/PH11/A07/

Result: All touched files conform strictly to the designated path lane.
```

## Test Scenario Breakdown
1. `test_mobile_share_end_to_end_flow`: Validates complete mobile share workflow exporting Patient (with profile ID), Observation (with UCUM code and unit), MedicationStatement (with dosage and SNOMED code), Consent (with permit and clinician_handoff purpose), AuditEvent, and Provenance records.
2. `test_mobile_share_care_coordination_purpose`: Validates export under `care_coordination` purpose.
3. `test_consent_gating_unconsented_rejected_with_428`: Validates fail-closed HTTP 428 when user has not accepted medical disclaimer consent.
4. `test_consent_revocation_invalidates_export`: Validates that consent revocation in append-only ledger immediately blocks export with HTTP 428.
5. `test_unsupported_purpose_rejected_with_422`: Validates rejection with HTTP 422 `unsupported_export_purpose` when purpose outside allowed set is requested.
6. `test_unauthenticated_request_rejected_with_401`: Validates unauthenticated calls return HTTP 401.
7. `test_cross_user_idor_blocked_with_404`: Validates User A attempting to export User B's profile via `X-CLARA-Profile-Context` is denied with HTTP 404 `scope_forbidden`.
8. `test_admin_direct_access_blocked_without_break_glass`: Validates administrator role does not grant automatic access to clinical records, failing with HTTP 404.
9. `test_family_delegate_expired_grant_rejected`: Validates delegate with expired grant is denied (HTTP 404).
10. `test_family_delegate_revoked_grant_rejected`: Validates delegate with revoked grant is denied (HTTP 404).
11. `test_family_delegate_missing_action_rejected`: Validates delegate with grant missing `export` action is denied (HTTP 404).
12. `test_family_delegate_missing_dataclass_rejected`: Validates delegate requesting `medications` when grant only allows `lifemap` is denied (HTTP 404).
13. `test_family_delegate_authorized_export_succeeds`: Validates delegate with active, valid grant and matching data classes successfully exports.
14. `test_feature_flag_disabled_returns_404`: Validates disabling `lifemap_fhir_export_enabled` returns HTTP 404 `feature_disabled`.
15. `test_ips_overclaim_protection_returns_409`: Validates anti-overclaim guard on `/v2/export/ips` returning HTTP 409 `ips_conformance_not_approved`.
16. `test_conformance_statement_declares_non_general_server`: Validates machine-readable conformance boundary declares `general_fhir_server: False`.
17. `test_minimum_necessary_demographic_minimization`: Validates omitting `demographics` strips `name`, `birthDate`, and `gender` while keeping structural patient reference.
18. `test_draft_and_unconfirmed_records_excluded`: Validates that unconfirmed/draft observations and medications are completely omitted from the export.
