# IEEE v10 — số liệu đã chạy và các mục còn thiếu

Ngày chạy: 2026-08-09. Revision evaluator: `c6fa95c9081bd881059c24588701db504e7cc513`.
Worktree tại thời điểm chạy là **dirty** (`git_status_sha256`
`04f1fac15e30ca03cca5bfdd108e3a5720bf3db443756191feeb99746074d2d3`),
vì vậy đây là evidence có provenance rõ ràng nhưng chưa phải submission build
clean. Tất cả kết quả là **structural conformance**; không phải clinical
validation, clinical safety, diagnostic accuracy, hay hiệu quả trên bệnh nhân.

## Artifact gốc và khả năng tái lập

| Cohort/run | Artifact cuối | CSV/JSON gốc |
|---|---|---|
| Q2 synthetic | `artifacts/glhs-q2/2026-08-09-q2-frozen-c6fa95c9-synthetic/` | `cases.csv`, `outcomes.csv`, `per_run.csv`, `baseline_comparison.csv`, `cost_of_success.csv`, `summary.json` |
| MIMIC-IV Demo-derived | `artifacts/glhs-q2/2026-08-09-q2-frozen-c6fa95c9-mimic-iv-demo/` | `external_cases.csv`, `external_outcomes.csv`, `external_baseline_comparison.csv`, `summary.json` |
| MIMIC-IV-ED Demo-derived | `artifacts/glhs-q2/2026-08-09-q2-frozen-c6fa95c9-mimic-iv-ed-demo/` | cùng cấu trúc artifact |
| Synthea FHIR STU3-derived | `artifacts/glhs-q2/2026-08-09-q2-frozen-c6fa95c9-synthea-stu3/` | cùng cấu trúc artifact |
| Model arm | `artifacts/glhs-q2/2026-08-09-q2-model-arm-acd5bbe1/` | `model_per_run.csv`, `model_arm_contract.json`, `integrated/model_arm_by_experiment.csv`, `integrated/model_arm_summary.json` |

Mỗi artifact Q2 có `evidence-manifest.json`, policy/oracle/relevance/holdout
manifest, environment và figures SVG. Chạy lại bằng `make eval-glhs-q2`; model
arm chỉ được tích hợp khi contract có revision, hash runner, ba seed và xác nhận
không fallback/rollback.

## Protocol đã chạy

| Thành phần | Giá trị |
|---|---:|
| Synthetic subjects / cases | 200 / 400 |
| Direct / compositional / ambiguity | 100 / 240 / 60 |
| Sealed compositional split nội bộ | 60 case (`Q2-0281`–`Q2-0340`) |
| Episode mỗi subject | 8–30 |
| Comparator | LWW, Naive RAG, temporal/provenance resolver (TPR), no-GST, no-THSS, GLHS-full reference policy |
| Model structural arm | 120 ca stratified × 3 seed = 360 lượt |
| MIMIC-IV Demo-derived | 100 case / 100 tokenized subject |
| MIMIC-IV-ED Demo-derived | 64 case / 64 tokenized subject |
| Synthea STU3-derived toàn bộ selection policy | 15,877 case / 15,877 tokenized subject; archive scan 1,594,095 Patient bundles |
| Final benchmark score | **Không phát hành** |

## Kết quả comparative: synthetic development (n=400)

| System | State correct | Unauthorized disclosure | GST bypass |
|---|---:|---:|---:|
| LWW | 133/400 | 66/400 | 0/400 |
| Naive RAG | 133/400 | 66/400 | 0/400 |
| TPR | 334/400 | 66/400 | 66/400 |
| GLHS no-GST | 133/400 | 0/400 | 66/400 |
| GLHS no-THSS | 400/400 | 0/400 | 0/400 |
| GLHS-full reference policy | 400/400 | 0/400 | 0/400 |

`GLHS-full` và oracle dùng chung policy phát triển; 400/400 là expected
development conformance chứ không phải một superiority claim độc lập.

| Comparison (subject-cluster) | RD 95% CI | McNemar discordant; Holm p |
|---|---|---:|
| Full vs no-GST | +0.6675 [0.6225, 0.7100] | 183; 4.894e-55 |
| Full vs no-THSS | 0.0000 [0.0000, 0.0000] | 0; 1.0 |
| Full vs TPR | +0.1650 [0.1325, 0.1975] | 66; 5.421e-20 |

## Cost of success (synthetic development, n=400)

`cost_of_success.csv` được xuất trực tiếp từ cùng outcomes. P95 là
pure-Python state-layer simulation, context là proxy của profile THSS đóng
băng; review burden là số safe escalation, **không phải** số giờ review.

| Comparison | Failure reduction | P95 delta (µs) | Context-proxy delta | Safe-escalation delta |
|---|---:|---:|---:|---:|
| Full vs no-GST | 267/400 | -0.06985 | 0 | +133 (199 vs 66) |
| Full vs no-THSS | 0/400 | -0.21600 | -60 (60 vs 120) | 0 (199 vs 199) |
| Full vs TPR | 66/400 | -0.07115 | NR | 0 (199 vs 199) |

Không diễn giải các delta này thành production latency hoặc human-review cost.

## Cohort derived: báo cáo tách riêng, không gộp headline

Các manifest external chỉ đưa perturbation structural đã tiền xử lý, tokenized;
không đưa clinical text/raw record vào evaluator output. MIMIC là de-identified
structural cohort, Synthea là synthetic. Không cohort nào là sealed independent
holdout hay clinical ground truth.

| Cohort | LWW | TPR | GLHS-full | Điều kiện dùng |
|---|---:|---:|---:|---|
| MIMIC-IV Demo-derived (n=100) | 33/100 | 84/100 | 100/100 | development structural |
| MIMIC-IV-ED Demo-derived (n=64) | 21/64 | 54/64 | 64/64 | development structural |
| Synthea FHIR STU3-derived (n=15,877) | 5,293/15,877 | 13,231/15,877 | 15,877/15,877 | synthetic development |

## Model-backed structural arm

Đây là prompt-following cho nhãn opaque structural, không có dữ liệu bệnh
nhân, citation hay quyết định y khoa. Transport là governed direct task client;
contract ghi `fallback_model=""` và `rollback_applied=false`.

| Metric | Result |
|---|---:|
| Configured model / runtime reported | `antigravity/claude-sonnet-4-6` / `claude-sonnet-4-6` |
| Completed; provider/runtime errors | 360/360; 0/360 |
| JSON valid | 360/360 |
| State correct | 249/360 (69.17%) |
| Direct / compositional / ambiguity | 60/90; 149/216; 40/54 |
| Seed 20260808 / 20260809 / 20260810 | 83/120; 81/120; 85/120 |
| Latency P50 / P95 | 194.35 / 281.88 ms |
| Degraded/fallback indication | 0/360 |

Không có token usage/cost trong provider response contract, vì vậy không được
tự suy diễn chi phí. Giá trị latency này là direct task-client latency, không
phải End_User E2E latency.

## Metrics/figure đã có

`baseline-comparison.svg`, `thss-privacy-utility.svg`, `error-breakdown.svg`,
`latency.svg`, `scalability.svg`, cùng các CSV `thss_ablation.csv`,
`error_analysis.csv`, `operational_metrics.csv`, `cost_of_success.csv`, `scalability.csv` đã được tạo
trong từng artifact. State-layer latency (microseconds) chỉ là simulation,
không được ghi thành database/production latency.

## Quality-gate audit tại thời điểm report

| Gate | Evidence | Trạng thái |
|---|---|---|
| Q2 evaluator/unit | `evaluation/glhs_q2/test_run.py` | 10 passed (gồm resume checkpoint và external stream uniqueness) |
| Q2/Q3 preparer regression | `evaluation/glhs_q2/test_run.py` + `evaluation/glhs_q3/test_run.py` | 18 passed |
| GLHS API focused | gateway, migration, connected/visit adapter tests | 5 passed (2 FastAPI deprecation warnings) |
| Web lint | `npm run lint` | exit 0; 6 Hook-dependency warnings |
| Web production build | `npm run build` | exit 0 |
| Mobile full suite | `flutter test` | 476 passed, 11 failed; failures ở consent/DSAR/Today finder/locale contracts, chưa được che giấu |
| Root Python lint | `make lint` | fail: 647 existing violations across repo; Q2/Q3 scope lint sạch |
| Root Python type check | `make type-check` | fail: 336 existing mypy errors/43 files; không diễn giải thành GLHS/Q2 green |
| Full API/ML suite | `make test` (mỗi service chạy từ working directory riêng) | chưa có kết quả hoàn chỉnh sau thay đổi Q2 mới nhất. Không dùng `pytest` từ repo root với API venv: nó tạo 20 import-collision khi collect ML tests và không phải quality gate hợp lệ. |

`Makefile` đã được sửa để `make lint` và `make type-check` dùng venv dự án khi
có, nên các failure trên là kết quả công cụ thật chứ không phải `command not
found`.

## Full Synthea run status

Full-archive preparation với `selection_modulus=1` đã hoàn tất tại
`artifacts/glhs-q2/2026-08-09-synthea-stu3-full-preparation/`, sau đó external
stream đã hoàn tất tại `artifacts/glhs-q2/2026-08-09-synthea-stu3-full/`.
Manifest ghi nhận 1.594.095 FHIR patient bundle, 1.594.095 tokenized structural
case và 0 invalid/non-patient bundle. Raw artifact có `external_cases.csv`
(251.120.772 byte), `external_outcomes.csv` (2.060.096.606 byte),
`summary.json`, `source-manifest.json` và `publication-validation.json`.
Không được diễn giải dữ liệu này ngoài **synthetic development structural
conformance**; nó không là final score, holdout độc lập hay clinical result.
Preparer dùng checkpoint SQLite chỉ chứa salted token và episode count, WAL và
commit định kỳ; evaluator dùng uniqueness index tạm trên đĩa thay vì giữ toàn
bộ token trong RAM.

Trước khi lấy số liệu từ artifact hoàn chỉnh vào manuscript, chạy
`make eval-glhs-q2-validate ARTIFACT=<artifact-dir>`. Publication gate này
đọc CSV/JSON theo streaming, kiểm tra đủ comparator row/mẫu số, summary hash
và release boundary development. External-stream artifact tự chứa
`source-manifest.json` (chỉ checksum/count/token policy), được hash-verified;
gate không chạy lại hay tune policy.

## Các số vẫn chưa thể điền trung thực — và việc cần làm

1. **Final score / external holdout:** cần curator độc lập tạo external manifest
   `partition=sealed_holdout`, attestation độc lập, perturbations và oracle
   checksum-locked trước khi evaluator chạy. Split 60 Q2 nội bộ không thay thế.
2. **Clean reproducibility build:** commit toàn bộ implementation/protocol đang
   dùng, checkout clean SHA, chạy lại rồi thay artifact này.
3. **Provider cost/token và End_User E2E latency:** thêm telemetry aggregate
   không PII vào task-client contract; không đoán từ latency.
4. **Clinical, usability, clinician review, calibration, security/pentest,
   multi-institutional validation:** chưa thực hiện. Không mô tả như đã có.
5. **MIMIC-on-FHIR / eICU:** chưa chạy. Chỉ triển khai khi đã có lawful access,
   frozen selection/perturbation/oracle protocol và tách cohort khỏi headline.
6. **DDI independent benchmark:** strict DrugBank source-conformance không phải
   independent DDI accuracy benchmark; cần dataset/reference standard độc lập.
7. **Repository/mobile quality gates:** sửa hoặc cập nhật contract đúng các 11
   mobile test fail và 647 lint/336 mypy debt trước khi mô tả full repository
   gate là passed.

## Câu chữ có thể dùng trong manuscript

“We evaluated structural conformance under a frozen developer-authored Q2
protocol and pre-derived de-identified/synthetic structural perturbations. The
reference-policy result is a development conformance check, not clinical
validation or an independently released benchmark score. A model-backed opaque
label stress arm completed 360/360 requests without fallback, with 176/360
state matches; it does not establish clinical model performance.”

## Clean model-backed arm — Gemini 3.6 Flash High

Artifact: `artifacts/glhs-q2/2026-08-09-q2-clean-03f67117-model-integrated-gemini36high/`.
The frozen source revision was `03f671171078603bae51b88d98620f6d2dec074a`.

| Measure | Result |
|---|---:|
| Frozen grid | 120 synthetic cases × 3 seeds = 360 runs |
| Completion / errors | 360 / 360; 0 errors |
| Valid JSON | 360 / 360 |
| State correct | 176 / 360 (48.9%) |
| p50 / p95 latency | 2,223.6505 / 4,473.77715 ms |
| Fallback or degraded indication | 0 / 360 |

All 360 responses reported `gemini-3.6-flash-high`; the contract fixes
temperature at 0, records an empty fallback model and has rollback disabled.
This is an opaque-label synthetic structural prompt-following experiment only.
The low state-correct count is reported as a failure-to-meet target requiring
prompt/decoder evaluation; it must not be presented as medical safety,
clinical performance, or model superiority.

<!-- FULL_SYNTHEA_MACHINE_RESULTS:START -->
## Full Synthea FHIR STU3 result (machine-rendered)

Artifact: `artifacts/glhs-q2/2026-08-09-synthea-stu3-full-clean-03f67117/`; validation: `publication-validation.json`.

- Source FHIR patient bundles scanned: **1,594,095**
- Selected tokenized structural cases / evaluated subjects: **1,594,095 / 1,594,095**
- Partition: **development**; synthetic structural conformance only; no final score or clinical-validation claim.

| Comparator | State correct |
|---|---:|
| LWW | 531,365/1,594,095 |
| Temporal/provenance resolver | 1,328,413/1,594,095 |
| GLHS-full reference policy | 1,594,095/1,594,095 |

The values above are rendered directly from checksum-validated machine artifacts. They are not pooled with MIMIC, are not a sealed external holdout, and do not establish clinical effectiveness or safety.
<!-- FULL_SYNTHEA_MACHINE_RESULTS:END -->
