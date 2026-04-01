# CLARA Scientific Eval Testkit Guide (Round 2)

## 1) Mục tiêu
Để số liệu demo và pitch có tính thuyết phục khoa học, KPI không chỉ dừng ở `pass/fail` mà phải có:
- Chỉ số phân loại chuẩn: accuracy, precision (PPV), recall/sensitivity, specificity, F1, balanced accuracy.
- Khoảng tin cậy (95% CI) cho các tỷ lệ chính.
- Slice an toàn lâm sàng: tỷ lệ phát hiện ca mức độ cao/nghiêm trọng (critical/high recall).
- Đo hiệu năng hệ thống: p50/p95 latency online/offline, fallback success rate.

## 2) Testkit uy tín nên dùng

### A. Thống kê cổ điển (bắt buộc)
- `scikit-learn`:
  - confusion matrix + precision/recall/F1/accuracy theo chuẩn ML.
  - Link: https://scikit-learn.org/stable/modules/model_evaluation.html
- `statsmodels`:
  - CI cho tỉ lệ nhị thức (Wilson/Clopper-Pearson), so sánh cặp model (McNemar).
  - Link CI: https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html
  - Link McNemar: https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html
- `scipy`:
  - bootstrap CI (BCa) khi cần đánh giá metric không có công thức CI đóng.
  - Link: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html

### B. Evals cho RAG/LLM (khuyến nghị)
- `Ragas`:
  - context precision/recall, faithfulness, answer relevancy.
  - Link: https://docs.ragas.io/en/stable/
- `TruLens`:
  - trace + eval groundedness/context relevance cho workflow agentic.
  - Link: https://www.trulens.org/
- `Promptfoo`:
  - regression test prompt/model và policy assertions trong CI.
  - Link: https://www.promptfoo.dev/docs/getting-started/

### C. Load/performance (khuyến nghị)
- `k6` cho stress/soak test endpoint API.
  - Link: https://grafana.com/docs/k6/latest/
- `Locust` cho scenario user-level (login -> consent -> careguard -> research).
  - Link: https://docs.locust.io/en/stable/

### D. Khung báo cáo nghiên cứu y sinh (nên áp dụng)
- `STARD 2015` cho báo cáo kiểu “diagnostic accuracy”.
  - Link: https://www.equator-network.org/reporting-guidelines/stard/
- `TRIPOD+AI / TRIPOD-LLM` cho minh bạch mô hình dự đoán/LLM trong y tế.
  - Link: https://www.tripod-statement.org/

## 3) Công thức chỉ số cốt lõi
Cho confusion matrix:
- TP: dự đoán có cảnh báo, gold có cảnh báo
- FP: dự đoán có cảnh báo, gold không cảnh báo
- TN: dự đoán không cảnh báo, gold không cảnh báo
- FN: dự đoán không cảnh báo, gold có cảnh báo

Các công thức:
- `accuracy = (TP + TN) / (TP + TN + FP + FN)`
- `precision = TP / (TP + FP)`
- `recall (sensitivity) = TP / (TP + FN)`
- `specificity = TN / (TN + FP)`
- `F1 = 2TP / (2TP + FP + FN)`
- `balanced_accuracy = (recall + specificity) / 2`

Khoảng tin cậy:
- Ưu tiên Wilson 95% CI cho tỷ lệ nhị thức.
- Khi metric phức tạp (vd. F1), dùng bootstrap BCa 95% CI.

## 4) Protocol chạy đánh giá chuẩn cho CLARA

### Dataset policy
- DDI goldset cần có cả positive và negative case (không chỉ positive).
- Chia rõ:
  - `critical/high` pair set (ưu tiên không bỏ sót).
  - `moderate/low` set.
  - `negative` set để đo FP/specificity.

### Runtime policy
- Chạy 2 mode:
  - Online (`external_ddi_enabled=true`)
  - Offline fallback (`external_ddi_enabled=false`)
- Ghi log đầy đủ:
  - `source_used`, `source_errors`, `fallback_used`, `latency_ms`.

### Báo cáo tối thiểu phải có
- Confusion matrix + accuracy/precision/recall/specificity/F1 + CI.
- Critical-severity recall + CI.
- p50/p95 latency online/offline.
- Fallback success rate + CI.
- Refusal compliance rate + CI.

## 5) Áp dụng ngay trong repo CLARA
- Runner KPI: `scripts/demo/run_hackathon_kpis.py`
  - Đã hỗ trợ scientific metrics + Wilson CI cho DDI.
- Artifact output:
  - `artifacts/round2/<run_id>/kpi-report/kpi-report.json`
  - `artifacts/round2/<run_id>/kpi-report/kpi-report.md`

Lệnh chạy nhanh:

```bash
python3 scripts/demo/run_hackathon_kpis.py --mode static --run-id local-science-smoke
```

Lệnh live:

```bash
python3 scripts/demo/run_hackathon_kpis.py \
  --mode live \
  --strict-live \
  --run-id round2-scientific-live \
  --api-base-url http://127.0.0.1:8000 \
  --ml-base-url http://127.0.0.1:8001 \
  --email admin@example.com \
  --password 'Clara#Admin2026!' \
  --doctor-email admin@example.com \
  --doctor-password 'Clara#Admin2026!'
```

## 6) Ngưỡng gợi ý cho vòng 2 (mang tính vận hành)
- Critical-severity recall: `>= 0.98` (ưu tiên an toàn, tránh false negative nặng).
- Precision: `>= 0.95` (giảm báo động giả).
- Fallback success rate: `= 1.00`.
- Refusal compliance: `= 1.00`.
- Latency p95:
  - online `< 3.0s`
  - offline `< 0.5s`

> Lưu ý: đây là ngưỡng vận hành cho hackathon demo, không phải tuyên bố hiệu lực lâm sàng ngoài thực địa.
