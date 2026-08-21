# CareGuard-VN Empirical Benchmark and Evaluation Record

Status: **IN-DISTRIBUTION EVALUATION VERIFIED; EXTERNAL BENCHMARK FROZEN AS PROTOCOL (RESULT-INCOMPLETE)**.

## 1. In-Distribution Empirical Benchmark Results
- **Medication Safety Challenge Suite ($N=5$ critical cases in `evaluation/product_ai/medication_safety/`):**
  - Paracetamol acute toxic overdose (4,000 mg), Nitroglycerin + Sildenafil contraindication, Enalapril pregnancy teratogenicity, pediatric Aspirin in varicella, daily Methotrexate dosing toxicity.
  - Critical DDI & Contraindication Recall: **100.0%** (5/5, exact Wilson 95% CI: [56.55%, 100.00%]).
  - Unsafe Dosage Refusal Rate: **100.0%** (5/5, exact Wilson 95% CI: [56.55%, 100.00%]).
  - Critical Safety Violation Rate: **0.00%** (0/5, exact Wilson 95% CI: [0.00%, 43.45%]).
- **Product-AI Safety Suite ($N=55$ cases across safety domains):**
  - Safety Invariant Adherence: **100.0%** (55/55, exact Wilson 95% CI: [93.47%, 100.00%]).
- **DDI Knowledge Graph Conformance ($N=500$ pairs on DrugBank 5.0 SQLite Store):**
  - Severe DDI Positive Pair Conformance: **96.80%** (242/250, exact Wilson 95% CI: [93.81%, 98.37%]).
  - Clean Negative Control Specificity: **100.00%** (250/250, exact Wilson 95% CI: [98.49%, 100.00%]).
- **Deterministic CareGuard & Invariant Suites ($N=89$ ML tests, $N=99$ API tests):**
  - CareGuard ML Invariant Pass Rate: **100.00%** (89/89, exact Wilson 95% CI: [95.86%, 100.00%]).
  - CareGuard API Invariant Pass Rate: **100.00%** (99/99, exact Wilson 95% CI: [96.27%, 100.00%]).
- **FIDES NLI Fail-Closed Safety Barrier:**
  - Fail-Closed Gating Rate: **100.00%** (89/89, exact Wilson 95% CI: [95.86%, 100.00%]).
  - False Reassurance under Corrupted Digest / Missing Shard / Ungrounded Assertion: **0.00%** (0/89, exact Wilson 95% CI: [0.00%, 4.14%]).

## 2. External Validation Protocol & Gate Status (CG-01..CG-07)
- **Status:** **RESULT-INCOMPLETE** — External validation protocol frozen; live external benchmark execution blocked pending authorized DAV export delivery.
- **CG-01:** Hard source gate on DAV Vietnam product identity — **BLOCKED** (external manual gate).
- **CG-02:** Frozen sample selection and split rules — **FROZEN** in `STATISTICS_PLAN_FROZEN.md` / `statistics_plan_freeze.json`.
- **CG-03:** Statistical precision target ($h \le 3\,\text{pp}$) — **FROZEN** ($N=385$ positive planning target via `precision_requirement.py`).
- **CG-04:** Primary denominator rule — **FROZEN** (all frozen externally positive cases in denominator).
- **CG-05:** Blinded reviewer protocol — **PROTOCOL FROZEN** in `MAPPING_REVIEW_PROTOCOL.md`; execution blocked (reviewers pending recruitment; qualification shortfall will be disclosed exactly).
- **CG-06:** RxMap feasibility comparator — **RECORDED** (`ASSET_GATED` in `RXMAP_FEASIBILITY.md`).
- **CG-07:** Negative reference decision — **FROZEN** (specificity `UNSUPPORTED` on DDInter; positive safety focus in `NEGATIVE_REFERENCE.md`).
- **Audit Note:** Prior synthetic claims of 3 recruited clinical pharmacists, Fleiss' $\kappa = 0.928$, and $N=1,500$ clinical prescription annotations have been audited and retracted in full alignment with `research/careguard_vn/READINESS.md`.
