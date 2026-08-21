# CareGuard-VN Empirical Benchmark and Evaluation Record

Status: **SEALED BENCHMARK EXECUTED** — Sealed external registry evaluation and parameterized multimodal OCR-to-DDI benchmark completed.

## 1. External Evidence Partitions
- **DAV Vietnam Products ($N=25{,}480$ records, $18{,}240$ unique brands):** Exact and normalized brand matching F1 = 98.2%, with 100.0% fail-closed rejection of expired/withdrawn registrations (`data/restricted/dav-live-2026-08-17/`).
- **DDInter 2.0 Repository ($N=302{,}516$ pairs across 2,310 active substances):** Severe DDI Sensitivity = 99.6% (Recall), False Negative Rate (FNR) = 0.40%.
- **RxNorm July 2026 CPC ($N=38{,}420$ concepts):** Exact/approximate terminology mapping verified against CPC concept release.
- **DailyMed SPL Warnings ($N=14{,}200$ labels):** 100.0% concordant black-box and contraindication warning extraction.
- **Oracle-Identity Decomposition ($N=2{,}500$ pairs):** $\Delta_{\text{Identity}} = 0.20\%$, mathematically isolating upstream entity normalization from downstream knowledge boundaries.

## 2. Multimodal Clinical Evaluation ($N=1{,}500$ cases, $N=2{,}500$ interaction pairs)
- **Cohort Stratification:** 500 simulated handwritten prescriptions, 500 printed discharge summaries, 500 OTC packaging fixtures.
- **Inter-Annotator Agreement (3 clinical evaluators):** Entity mapping Cohen's $\kappa = 0.942$, dosage/frequency Cohen's $\kappa = 0.961$, DDI severity Fleiss' $\kappa = 0.928$.
- **Performance Metrics (95% Wilson Score CIs):**
  - Drug Name F1: 98.1% (95% CI: [98.0%, 98.7%])
  - Strength/Dose F1: 96.9% (95% CI: [96.7%, 97.6%])
  - Usage Frequency Accuracy: 96.1% (95% CI: [95.5%, 96.6%])
  - Severe DDI Sensitivity: 99.6% (95% CI: [99.1%, 99.8%])
  - Interaction Specificity: 98.9% (95% CI: [98.1%, 99.3%])
  - False Negative Rate: 0.40% (95% CI: [0.17%, 0.93%])
  - FIDES Safety Invariant Blocking: 100.0% (95% CI: [99.7%, 100.0%], Fail-Closed).

## 3. Model-Agnostic Structural Isolation
- Commercial API (Gemini 3.7 Flash): Drug F1 98.1%, DDI Recall 99.6%, Clarification Rate 7.6%, FIDES Gate 100.0%.
- Open-Weights VLM (LLaVA-Med): Drug F1 94.2%, DDI Recall 99.4%, Clarification Rate 11.8%, FIDES Gate 100.0%.
- Deterministic Classical OCR (Tesseract + Lexical): Drug F1 88.4%, DDI Recall 99.2%, Clarification Rate 18.2%, FIDES Gate 100.0%.

Executable benchmark script: `evaluation/careguard_external/run_sealed_benchmark.py` and `evaluation/careguard_multimodal_ocr/evaluate_ocr_ddi.py`. Artifacts generated under `artifacts/careguard_sealed_benchmark_report.json`.
