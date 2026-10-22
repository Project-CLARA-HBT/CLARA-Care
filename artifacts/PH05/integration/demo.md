# PH05 Demonstration Scenarios

## Scenario 1: Append-Only Consent Ledger and Immediate Revocation Gating
Execute the consent ledger test suite proving that consent withdrawal immediately gates processing while preserving prior audit rows:
```bash
python3 -m unittest services/api/tests/test_consent_gates_and_revocation.py
```
**Expected Output:**
```text
Ran 3 tests in 1.226s
OK
```
This confirms that granting establishes active consent, revocation appends a row with `revoked_at` timestamp, and `has_consent` immediately evaluates to `False`.

## Scenario 2: Mobile Consent Statutory Rights Explanation Bottom Sheet
Execute the Flutter widget test suite proving that the explanation sheet renders bilingual statutory disclosures and dismisses cleanly:
```bash
flutter test --no-pub apps/mobile/test/consent_explanation_ux_test.dart
```
**Expected Output:**
```text
00:14 +2: All tests passed!
```
This demonstrates patient transparency regarding Decree 13/2023/ND-CP statutory rights and informed choice.
