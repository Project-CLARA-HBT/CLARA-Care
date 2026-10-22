# PH06 Demonstration Scenarios

## Scenario 1: GLHS Proposal Admission Lifecycle & Rejection Blocking
Execute the proposal lifecycle integration test suite proving that model recommendations initialize as PENDING and rejected proposals fail closed:
```bash
PYTHONPATH="services/api/src" python3 -m unittest services/api/tests/test_thss_pending_proposal_state.py
```
**Expected Output:**
```text
Ran 2 tests in 0.789s
OK
```
This confirms that proposals default to PENDING, cannot execute without explicit admission, and terminal REJECTED states block execution permanently.

## Scenario 2: Mobile Reviewer Explicit Proposal Decision UX
Execute the Flutter widget test suite proving that clinicians review model provenance and execute explicit onAdmit/onReject actions:
```bash
flutter test --no-pub apps/mobile/test/proposal_decision_ux_test.dart
```
**Expected Output:**
```text
00:12 +2: All tests passed!
```
This demonstrates transparent clinical supervision over AI recommendations.
