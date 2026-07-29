# LifeMap Capture evaluation v1

Run date: 2026-07-29

Suite: `lifemap-capture-eval-v1`

Suite SHA-256:
`38cff9b2947849508943bb141b8b5cc246536211ff974d9c1fcc1307adf6289a`

## Scope

This is a frozen synthetic contract evaluation of the deterministic
`grounded-ocr-baseline-v1` extractor and the API emergency fast path. It covers
Vietnamese and English medication labels, visit documents, degraded missing
fields, prompt-injection text, positive emergency wording, and nearby
non-emergency wording.

It measures the deployed pure functions; it does not evaluate Google Vision,
Tesseract image quality, the configured OCR bridge, real-world handwriting,
camera artifacts, clinical outcomes, or user comprehension. It grants no model
promotion or clinical approval.

## Reproduce

```bash
PYTHONPATH=services/api/src:services/ml/src \
  services/api/.venv/bin/python scripts/lifemap_capture_eval.py \
  --suite services/ml/tests/fixtures/lifemap_capture_eval_v1.json
```

The cross-service test
`services/api/tests/test_lifemap_capture_eval_integration.py` runs the same
production extractor and emergency detector in CI.

## Recorded result

| Metric | Result | Gate |
| --- | ---: | ---: |
| Field precision | 1.000 | ≥ 0.950 |
| Field recall | 1.000 | ≥ 0.800 |
| Critical-field miss rate | 0.050 | ≤ 0.250 |
| Wrong-medication rate | 0.000 | = 0 |
| Source-span validity | 1.000 | = 1 |
| Emergency sensitivity | 1.000 | = 1 |
| Emergency specificity | 1.000 | = 1 |
| Confirmation actions / extraction case | 0.625 | ≤ 1.000 |
| Emergency p95 latency | < 1 ms | ≤ 25 ms |
| Extraction p95 latency | < 1 ms | ≤ 25 ms |

All contract gates passed. `eligible_for_promotion` remains hard-coded `false`.

## Remaining evidence before Task 4.9 can close

- a sufficiently powered, independently reviewed Vietnamese/English corpus;
- real OCR sources across camera, scan, print, handwriting, blur, crop, and
  layout degradation;
- stratified medication-name and strength confusions;
- end-to-end worker/network/object-store emergency latency;
- observed confirmation burden and comprehension from usability testing; and
- clinical-safety and privacy review of the locked report.
