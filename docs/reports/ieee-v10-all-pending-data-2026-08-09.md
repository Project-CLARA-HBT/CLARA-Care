# IEEE v10 — số liệu đã chạy và các mục còn thiếu

Ngày chạy: 2026-08-09. Revision evaluator: `f612962d90c818fd1a4bbb78f711016d9e60c284`.
Worktree tại thời điểm chạy là **dirty** (`git_status_sha256`
`ceb15e4c5bc3bc3cebe9bba6bd005647ca9eccd67dc93ff8abca9f7847c86445`),
vì vậy đây là evidence có provenance rõ ràng nhưng chưa phải submission build
clean. Tất cả kết quả là **structural conformance**; không phải clinical
validation, clinical safety, diagnostic accuracy, hay hiệu quả trên bệnh nhân.

## Artifact gốc và khả năng tái lập

| Cohort/run | Artifact cuối | CSV/JSON gốc |
|---|---|---|
| Q2 synthetic | `artifacts/glhs-q2/2026-08-09-q2-frozen-f612962d-synthetic/` | `cases.csv`, `outcomes.csv`, `per_run.csv`, `baseline_comparison.csv`, `summary.json` |
| MIMIC-IV Demo-derived | `artifacts/glhs-q2/2026-08-09-q2-frozen-f612962d-mimic-iv-demo/` | `external_cases.csv`, `external_outcomes.csv`, `external_baseline_comparison.csv`, `summary.json` |
| MIMIC-IV-ED Demo-derived | `artifacts/glhs-q2/2026-08-09-q2-frozen-f612962d-mimic-iv-ed-demo/` | cùng cấu trúc artifact |
| Synthea FHIR STU3-derived | `artifacts/glhs-q2/2026-08-09-q2-frozen-f612962d-synthea-stu3/` | cùng cấu trúc artifact |
| Model arm | `artifacts/glhs-q2/2026-08-09-q2-model-arm-f612962d/` | `model_per_run.csv`, `model_arm_contract.json`, `integrated/model_arm_by_experiment.csv`, `integrated/model_arm_summary.json` |

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
| Latency P50 / P95 | 203.90 / 404.04 ms |
| Degraded/fallback indication | 0/360 |

Không có token usage/cost trong provider response contract, vì vậy không được
tự suy diễn chi phí. Giá trị latency này là direct task-client latency, không
phải End_User E2E latency.

## Metrics/figure đã có

`baseline-comparison.svg`, `thss-privacy-utility.svg`, `error-breakdown.svg`,
`latency.svg`, `scalability.svg`, cùng các CSV `thss_ablation.csv`,
`error_analysis.csv`, `operational_metrics.csv`, `scalability.csv` đã được tạo
trong từng artifact. State-layer latency (microseconds) chỉ là simulation,
không được ghi thành database/production latency.

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

## Câu chữ có thể dùng trong manuscript

“We evaluated structural conformance under a frozen developer-authored Q2
protocol and pre-derived de-identified/synthetic structural perturbations. The
reference-policy result is a development conformance check, not clinical
validation or an independently released benchmark score. A model-backed opaque
label stress arm completed 360/360 requests without fallback, with 249/360
state matches; it does not establish clinical model performance.”
