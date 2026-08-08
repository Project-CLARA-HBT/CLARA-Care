# CLARA-Care — audit khoa học, revision manuscript và gói đánh giá

Ngày: 07/08/2026
Revision mã được khóa: `524907ccc59ff1677e22e48990620fd014810d13`
Trạng thái submission: **chưa sẵn sàng cho claim hiệu năng/lâm sàng**

## 1. Kết luận điều hành

CLARA-Care hiện có thể được mô tả một cách khoa học là **nguyên mẫu phần mềm y tế tích hợp, có các cơ chế kiểm soát và các kiểm tra kỹ thuật tái lập được**. Repository không cung cấp bằng chứng cho độ chính xác y khoa, an toàn lâm sàng, lợi ích workflow, giảm biến cố bất lợi, giảm chi phí, khả năng mở rộng, hay tổng quát hóa tiếng Việt trong thực tế.

Revision manuscript đã loại bỏ cách diễn giải quá mức: unit/contract test, fixture tổng hợp, local rule, hay kiến trúc fail-closed không được gọi là clinical validation. Kết quả mới tái lập được trong checkout này chỉ là **toàn vẹn manifest fixture tổng hợp: 9/9**; đây là kết quả quản trị artifact, không phải benchmark chất lượng sản phẩm.

## 2. Deliverables đã tạo/cập nhật

| Deliverable | Đường dẫn | Trạng thái và giới hạn |
|---|---|---|
| Manuscript revision | `THT FINAL _ CLARA Care - scientific-revision.docx` | Được sinh lại từ bản nguồn bằng script dưới đây; chỉ thay narrative/table XML, không tự tạo dữ liệu hay kết quả lâm sàng. |
| Script revision | `scripts/docs/revise_manuscript_scientific_validity.py` | Có thể chạy lại với source/output DOCX; fail nếu heading/table nguồn thay đổi. |
| Evaluation runner | `evaluation/clara_eval/run.py` | Runner stdlib-first sinh JSON/CSV/HTML/Markdown và ghi `not_measured` khi chưa có tập dữ liệu hoặc trace hợp lệ. |
| Dataset manifest + schemas | `evaluation/clara_eval/datasets/manifest.json`, `evaluation/clara_eval/schemas/` | 9 fixture tổng hợp; mô tả nguồn, checksum, split, hạn chế và metric không được đo. |
| Suite configs | `evaluation/configs/{smoke,nightly,release,judge_demo}.yaml` | Tách smoke/development/release-locked; live execution chỉ được bật khi có manifest đã phê duyệt. |
| Kết quả smoke | `artifacts/clara-eval-vn/smoke/` | JSON/CSV/HTML, manifest model/retrieval, CI, ablation template, latency-cost template và trace live; không có product-quality result. |
| DrugBank runtime conformance | `scripts/evaluation/run_drugbank_runtime_conformance.py` | Chỉ so runtime với sample xác định lấy từ **chính artifact DrugBank runtime**; không phải external benchmark. |
| Báo cáo DrugBank chi tiết | `docs/reports/drugbank-ddi-deployment-and-benchmark-2026-08-07.md` | Có provenance/version/hash, protocol, số đếm, lỗi và release gate. |
| Claim/evidence + peer-review audit | `docs/reports/manuscript-scientific-evidence-audit-2026-08-07.md` | Matrix 10 điểm phản biện, ranh giới claim, thiếu hụt và phương án evidence. |

## 3. Phạm vi khoa học đã thu hẹp

### 3.1 Intended use chính của nghiên cứu này

Nghiên cứu này chỉ đánh giá **hành vi kỹ thuật của nguyên mẫu CareGuard khi tra cứu tương tác thuốc hai thành phần từ artifact DrugBank đã cấp license, ở strict mode, nhằm hỗ trợ người dùng đưa thông tin cho dược sĩ/bác sĩ rà soát**. Nó không đánh giá quyết định điều trị, liều cá thể hóa, kê đơn hay tư vấn chẩn đoán; cũng không chứng minh người dùng cuối, bác sĩ hoặc dược sĩ dùng hệ thống tốt hơn.

Primary user population trong claim tương lai phải là **dược sĩ/bác sĩ review output**, không phải đồng thời bệnh nhân, caregiver, sinh viên, trường học, cơ sở y tế, quản trị viên và đối tác thương mại. Hiện không có participant nào thuộc nhóm này trong evaluation.

### 3.2 Câu hỏi nghiên cứu chính

| RQ | Câu hỏi | Trạng thái evidence |
|---|---|---|
| RQ1 | Với artifact DrugBank đã khóa checksum, runtime strict có trả được cặp tương tác đúng và không phát “all clear” khi dependency không sẵn sàng không? | **Conformance kỹ thuật**, có thể chạy lại; không phải accuracy lâm sàng. |
| RQ2 | Các guard backend có block/refuse/fail-closed theo hợp đồng đối với mutation, consent/RBAC và dependency failure không? | **Contract/integration evidence**, cần run có trace tách riêng; chưa có báo cáo aggregate publishable trong checkout này. |

Research RAG, citation grounding, prompt injection, Council, Scribe, PHR/LifeMap, UX, cost, latency và multi-user safety chỉ là **secondary/exploratory modules**. Không module nào hiện có bằng chứng outcome đủ để làm endpoint chính hoặc claim superiority.

## 4. Kết quả thực sự được phép báo cáo

### 4.1 Smoke integrity được chạy lại trong checkout

Lệnh đã chạy:

```bash
python3 -m evaluation.clara_eval.run \
  --config evaluation/configs/smoke.yaml \
  --output artifacts/clara-eval-vn/smoke
python3 -m evaluation.clara_eval.datasets.validate \
  --manifest evaluation/clara_eval/datasets/manifest.json \
  --repository-root .
```

Kết quả: **9/9 dataset fixture**, tổng **12 record synthetic**, có checksum/count hợp lệ. Wilson 95% CI của tỷ lệ *manifest integrity* là **0,701–1,000**. Đây không phải CI cho accuracy, safety, recall, specificity, citation quality, latency, cost hoặc usability. Smoke report ghi trung thực **28 metric product-quality là `not_measured`**.

### 4.2 DrugBank runtime conformance đã được ghi nhận

Artifact production được mô tả trong `drugbank-ddi-deployment-and-benchmark-2026-08-07.md` là DrugBank **5.0**, XML export **2017-12-20**, SHA-256 XML `36ec574eccdc2ed085b7510e166e8fa80255f4910bb1fcda5beebb4555e3bcf1`; ingest thành **357.839** cặp DDI và **34.344** dictionary records. Đây là release cũ, không được gọi là “DrugBank mới nhất”.

Lần conformance runtime đã ghi nhận trên VPS dùng seed `20260807`:

| Chỉ số conformance | Numerator/denominator | Diễn giải đúng |
|---|---:|---|
| Positive pair lookup | **242/250** | 8 cặp có trong artifact không được runtime trả đúng; chưa đạt release gate. |
| Negative pair lookup | **250/250** | Không có alert DrugBank ở negative sample sinh từ cùng artifact. Không được gọi là specificity. |
| Positive p50 / p95 / max | 50,281 / 64,117 / 135,842 ms | Chỉ là latency deployment/run này, không có repeated-run CI hay cost. |
| Negative p50 / p95 / max | 50,161 / 60,468 / 163,305 ms | Cùng giới hạn như trên. |

Positive/negative test đều được lấy từ artifact runtime; do đó có **source-index leakage theo thiết kế**. Kết quả chỉ kiểm tra ingest/index/normalization/API. Nó không đo clinical DDI sensitivity/specificity, severity handling, Vietnamese brand-name generalization hoặc patient safety. Tám miss phải được sửa tại strict medication identity rồi rerun; không được chọn lọc hay làm tròn thành 100%.

### 4.3 GLHS structural protocol checkpoint (không lâm sàng)

Lệnh đã chạy sau khi thêm GLHS/GST/THSS additive migration:

```bash
python3 -m evaluation.glhs_q3.run \
  --output artifacts/glhs-q3/2026-08-08-run4
```

Đây là **300 history developer-authored synthetic trên 150 subject synthetic**
(seed `20260808`), không chứa dữ liệu bệnh nhân. Test so sánh ba state-selection
protocol đã định nghĩa trước: last-write-wins (LWW), naive recency retrieval và
GLHS protocol, trên bốn scenario cân bằng: ordinary latest, late duplicate,
unresolved conflict và authorization revocation. Kết quả artifact SHA-256
`1ac9fc7e4eafce2775eb267cc7dc1cc39260d48179e65321666add2f4493069e`:

| Protocol | State-correct numerator/denominator | Wilson 95% CI |
|---|---:|---:|
| LWW | 75/300 | 0,204–0,302 |
| Naive recency retrieval | 75/300 | 0,204–0,302 |
| GLHS protocol | 300/300 | 0,987–1,000 |

Artifact còn khóa Git revision cùng SHA-256 của runner, gateway, adapter, model
và migration. Tuy vậy, expected state và cả ba output đều do protocol synthetic
quy định; kết quả chứng minh **conformance của state-machine test**, không chứng
minh độ chính xác lâm sàng, hiệu năng trên bệnh nhân, độ an toàn thực tế, superiority
so với hệ thống lâm sàng, hoặc generalization tiếng Việt. Không đưa bảng này vào
abstract/conclusion như một clinical benchmark.

## 5. Dataset, reference standard và leakage control

| Track | Dataset đang có | Split / standard | Có thể kết luận | Không thể kết luận |
|---|---|---|---|---|
| Vietnamese understanding | 2 synthetic routing fixture | smoke; không annotator/expert standard | Manifest/contract có thể validate | Vietnamese clinical understanding, regional/literacy/specialty/age generalization |
| Medical QA | 1 synthetic safety fixture | smoke; không clinician adjudication | Fixture được khóa checksum | Patient communication quality, safe medical advice |
| RAG | 1 synthetic fixture | không gold passages/claims/retrieval snapshot | Runner nhận diện thiếu evidence | retrieval/citation/grounding accuracy |
| CareGuard | 1 synthetic smoke fixture; production artifact DrugBank licensed | no independent locked test; runtime same-source conformance | Artifact integrity và lookup path | DDI clinical accuracy/severity recall/specificity |
| Scribe | 1 synthetic fixture | không consented audio, transcript gold, clinician edit | Contract fixture | WER, SOAP accuracy, edit-time reduction |
| LifeMap/Council/wording/router | 1–2 synthetic fixture mỗi track | no humans/reference standard | Artifact integrity | longitudinal accuracy, Council safety, usability, cost/latency |

Không có independent external test set, prospective/multisite sample, patient data, clinician-led validation, real-world usability study, subgroup analysis hoặc reference standard độc lập. Toàn bộ synthetic fixtures phải được gọi là **developer-authored regression/safety fixtures**, không phải clinical validation.

### Bắt buộc trước performance paper

1. Đóng băng development, regression và locked final-test sets khác nhau; hash, version, license và access control riêng.
2. Có inclusion/exclusion, sampling frame, regional Vietnamese terminology, prescription formats, specialties, age/health-literacy strata.
3. Gold labels phải do reviewer độc lập tạo; nêu expertise, adjudication, agreement và conflict policy.
4. Cấm tune prompt/rule/retrieval theo locked final test; log query/case ID, prompt/policy revision và all failed/incomplete runs.
5. DDI benchmark độc lập cần positive/negative đóng băng, severity-stratified, dược sĩ review; không lấy từ index release đang chấm.

## 6. Baseline, ablation, statistics và kết quả còn thiếu

| Thành phần | Baseline/ablation cần có | Thống kê cần báo cáo | Trạng thái hiện tại |
|---|---|---|---|
| Hybrid retrieval | BM25-only vs vector-only vs hybrid; fixed corpus/query set | P@k, Recall@k, MRR/nDCG; paired bootstrap CI/effect size | Chưa chạy |
| Reranking | hybrid without/with reranker | paired delta + CI; all errors | Chưa chạy |
| GraphRAG | declared graph config vs no graph | same locked queries/labels | Chưa chạy |
| Claim verification | answer generation without/with verifier | unsupported claim rate, citation precision/recall, paired comparison | Chưa chạy |
| CareGuard | strict DrugBank vs dependency-unavailable; no local fallback conclusion | exact counts, abstention/clarification, severity strata, Wilson CI where valid | Conformance partial; independent benchmark chưa có |
| Safety rules/fallback | policy on/off chỉ trong sandbox, no unsafe production mode | blocked/refused/escalated/error counts; transport failure separately | Chưa có aggregated result artifact |
| Scribe | structured flow/baseline documentation with consented study | WER, factual omission, clinician edits/time, harms; paired design | Chưa chạy |

`evaluation/clara_eval/run.py` đã có Wilson interval cho binary observations và cấu trúc artifact cho confidence intervals, ablations, critical errors, latency/cost. Nó không thay thế statistical analysis khi input chưa có valid label/reference standard. Không phần trăm nào được báo cáo thiếu numerator/denominator.

## 7. An toàn, bảo mật và degraded mode

Code có các invariant cần được giữ: RBAC route gate, medical-consent gate, cookie-CSRF cho mutation, emergency fast path, legal hard guard, FIDES verification và no-PII telemetry. Đây là **implemented safeguards**, không phải demonstrated safety.

| Kịch bản cần đánh giá | Trạng thái | Requirement để claim |
|---|---|---|
| Prompt/file injection, jailbreak, unsupported medical claim | Fixture/unit coverage có thể tồn tại nhưng chưa có systematic benchmark/report | Versioned adversarial set, source, false allow/block counts, repeated runs |
| Unsafe treatment/dosage/prescribing | Backend policy/guard tồn tại | End-to-end backend tests + exact pass/fail artifact; independent review trước clinical claim |
| Ambiguous drug/alias | Conformance phát hiện 8 miss liên quan normalization | Strict DrugBank candidate clarification + regression + rerun 0 miss gate |
| Malformed input/dependency unavailable | Fail-closed / fail-soft paths được thiết kế | Fault-injection run với status, no-all-clear assertion, trace |
| Cross-profile, consent, RBAC, CSRF | Mechanisms implemented | Scaled authorization/negative test matrix and penetration/security review |
| Privacy leakage, telemetry, penetration | Không có independent audit | Dedicated security protocol, external review and remediation evidence |
| Calibration, clinical review, prospective monitoring | Không có | Pre-specified clinical study; cannot be inferred from architecture |

Fail-closed nghĩa là strict DrugBank unavailable/integrity mismatch phải trả `unavailable` / no conclusion, không chuyển thành “không có tương tác”. Fail-soft phải nói rõ degraded limitation, không ngầm dùng một internal DDI set làm equivalent source.

## 8. Reproducibility manifest và một lệnh thực thi

Run foundation offline:

```bash
python3 -m evaluation.clara_eval.run \
  --config evaluation/configs/smoke.yaml \
  --output artifacts/clara-eval-vn/smoke
```

Kết quả liên kết config, dataset manifest, checksum, code revision, task-contract snapshot, metrics JSON/CSV, CI, latency-cost placeholder và output HTML/Markdown. Các path chính:

```text
evaluation/configs/smoke.yaml
evaluation/clara_eval/datasets/manifest.json
artifacts/clara-eval-vn/smoke/{summary.json,metrics.json,confidence-intervals.json,
  ablations.csv,critical-errors.csv,latency-cost.json,model-manifest.json,
  retrieval-snapshot.json,live-execution.json,index.html}
```

Tuy nhiên manifest hiện ghi rõ provider/model execution, embedding model, reranker, temperature/top-p/max tokens, retrieval index, chunking, `k`, corpus snapshot/retrieval date, seeds for model calls, hardware/image digest, token usage và per-query cost là **unobserved/unavailable** nếu không có live execution manifest được phê duyệt. Manuscript phải không điền các giá trị này bằng giả định; mỗi claim measured cần bind đến output run cụ thể và commit.

## 9. Sửa manuscript đã áp dụng

`scripts/docs/revise_manuscript_scientific_validity.py` đã tạo lại `THT FINAL _ CLARA Care - scientific-revision.docx` và thực hiện các thay đổi chính sau:

- Abstract/summary giới hạn CLARA-Care là nguyên mẫu tích hợp; bỏ ngụ ý clinical validation.
- Chuyển “novelty” thành contribution thiết kế/hypothesis; broad commercial product categories chỉ là context, không baseline.
- Đổi các RQ hiệu năng thành pre-specified/not-measured khi chưa có dữ liệu/standard/execution.
- Chèn phạm vi thực nghiệm hẹp; tách product scope rộng khỏi study claim.
- Thay bảng “internal results” bằng evidence table có raw count, artifact integrity và các gap rõ ràng.
- Bổ sung limitation về external validity, Vietnamese subgroup, injection/privacy/cross-profile/penetration/calibration và independent review.
- Đưa deployment, market, operational scalability về future/proposed scenarios; conclusion chỉ nói implementation + technical verification.

## 10. Claim-to-evidence matrix để dùng khi sửa tiếp

| Claim dự kiến | Evidence hiện có | Cách viết hợp lệ | Cách viết không hợp lệ |
|---|---|---|---|
| Hệ thống có RBAC/consent/CSRF/emergency/FIDES guard | source + tests/contracts | “cơ chế được implement và kiểm tra ở mức phần mềm” | “an toàn lâm sàng đã được chứng minh” |
| Smoke suite hoạt động | 9/9 synthetic fixture checksum/count | “manifest integrity 9/9 (CI nêu rõ)” | “độ chính xác/safety 100%” |
| DrugBank trong runtime | version/hash/artifact + conformance report | “DrugBank 5.0 strict runtime conformance 242/250 positive, 250/250 negative same-source sample” | “96,8% clinical accuracy” / “100% specificity” |
| Chat/RAG/Council/Scribe/PHR features | code route/components | “implemented prototype capability” | “improves diagnosis, documentation, coordination or outcomes” |
| Market/scale/cost benefit | none | “future hypothesis” | “ready, cost-saving, scalable deployment” |
| Vietnamese performance | no independent clinical set | “not evaluated across regions/formats/specialties/literacy” | “generalizes for Vietnamese users” |

## 11. Final audit: unresolved limitations before journal submission

### Blocking for any clinical/performance/real-world claim

1. Không external held-out data, independent expert reference, participant study hoặc prospective/multisite evaluation.
2. Không benchmark retrieval/citation/DDI/Scribe/UX với reproducible baseline and ablation.
3. DrugBank conformance có 8/250 positive misses; strict identity/normalization chưa đạt zero-miss technical gate.
4. Không systematic injection, privacy leakage, scaled cross-profile, penetration, calibration hoặc independent security/clinical review.
5. Không frozen runtime trace gồm model/provider/embedding/reranker/prompt/policy/index/chunking/top-k/corpus/hardware/cost/seed cho reported run.
6. Không representative Vietnamese subgroup assessment; không thể infer generalization.

### Không blocking cho prototype/technical-paper hẹp, nhưng phải công bố rõ

- `make` và `pytest` không có trong environment của audit này: `make eval-smoke` và `pytest -q evaluation/tests` **chưa chạy**. Lệnh Python runner và manifest validator đã pass như nêu ở Mục 4.1.
- Các test contract hiện có là regression evidence; không thay thế final evaluation.
- DrugBank XML 2017 có license nhưng cần release mới hơn và full rerun trước vận hành/công bố tính cập nhật.

## 12. Khuyến nghị quyết định

Nếu nộp ngay, đổi framing thành **software/prototype and evaluation-protocol paper** và không dùng claim clinical performance. Nếu mục tiêu là journal clinical-AI, hãy dừng ở revision này, sửa DrugBank conformance, khóa intended use một nhóm người dùng, tạo independent benchmark/reference standard, chạy pre-registered experiments và security/clinical review trước khi nộp.
