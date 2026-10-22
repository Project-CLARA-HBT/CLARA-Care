# Risk Register — PH40 A07 (Zero-Mock CI Detector & Fixture Tests)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH40-A07-01 | Regression re-introducing mock/stubbed clinical data into production endpoints | Critical | Low | Continuous integration detector `test_mock_and_synthetic_fixtures.py` asserts real handler classification and clean schema defaults. | Mitigated |
| RISK-PH40-A07-02 | Test fixtures mistaken for production clinical payloads | High | Low | Hermetic separation of test fixtures under dedicated `test_*.py` files without polluting API schemas. | Mitigated |
