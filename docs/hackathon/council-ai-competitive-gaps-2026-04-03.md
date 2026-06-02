# CLARA Council AI Competitive Research & Gap Report (2026-04-03)

## 1) Mục tiêu
- So sánh CLARA Council với các sản phẩm AI lâm sàng/hội chẩn đang triển khai thực tế.
- Chỉ ra các khoảng trống còn thiếu trong codebase hiện tại.
- Đề xuất lộ trình nâng cấp theo phase, ưu tiên mục tiêu Vòng 2 hackathon.

## 2) Snapshot thị trường (official/public)

| Product | Điểm mạnh nổi bật | Hàm ý cho CLARA |
|---|---|---|
| Infermedica | Virtual triage có symptom interview, condition list, triage recommendation, specialist recommendation. | CLARA cần triage orchestration rõ hơn theo chuyên khoa + confidence routing thay vì một luồng tổng quát. |
| Microsoft Dragon Copilot | Clinical workflow workspace theo vai trò, tự động hóa documentation + surfacing information + task automation. | CLARA cần role-specific council view sâu hơn (doctor/admin/researcher), không chỉ một màn result chung. |
| Suki | Tập trung documentation + coding + clinical reasoning trong một assistant, EHR integration sâu. | CLARA cần chuẩn hóa output council để có thể cắm vào EMR/EHR adapter sau hackathon. |
| Hippocratic AI | Nhấn mạnh safety policy và guardrails cho healthcare agents. | CLARA cần tăng hard guard + audit trail cấp run (who/when/why) cho mọi cảnh báo y khoa. |
| Isabel Healthcare | Differential diagnosis/decision support theo clinical context. | CLARA nên bổ sung differential diagnosis panel nhất quán thay vì phân tán qua raw sections. |
| Ada Health | Symptom assessment public với emphasis về advice safety. | CLARA cần scorecard “advice safety” có thể đo và theo dõi theo thời gian. |
| OpenEvidence (app listing public) | Clinical decision support + sourced/cited answers cho clinician. | CLARA cần source-attribution nhất quán cấp claim, không chỉ cấp answer. |
| Nabla / Abridge (clinical AI assistants) | Tập trung workflow bác sĩ, giảm burden hành chính bằng conversational AI. | CLARA cần conversation persistence + case follow-up loop cho từng patient/case ID. |

## 3) Đánh giá nhanh codebase CLARA Council (as-is)

## 3.1 Điểm đã tốt
- Đã có council orchestration và specialist reasoning logs.
- Đã có conflict detection + consensus + escalation logic.
- Đã có hardening ban đầu cho citation quality và reasoning timeline (backend).

## 3.2 Khoảng trống chính
1. UI chưa khai thác hết metadata mới của council (vừa bổ sung trong đợt này, cần mở rộng thêm ở các route chuyên biệt).
2. Chưa có claim-level attribution matrix hiển thị trực quan cho reviewer.
3. Chưa có persistence/audit đầy đủ cho case lifecycle (create -> run -> review -> signoff).
4. Thiếu regression benchmark dành riêng cho council quality/safety (false-negative legal, critical DDI miss theo ca).
5. Chưa có mô-đun neural network chuyên biệt để cải thiện risk scoring/reranking hội chẩn.

## 4) Lộ trình nâng cấp đề xuất (multi-phase)

## Phase A (đang thực thi)
- Đồng bộ contract backend -> frontend:
  - `council_consensus`
  - `emergency_escalation.metadata`
  - `citation_quality`
  - `reasoning_timeline`
- Nâng result page: thêm consensus quality cards + reasoning timeline.

## Phase B
- Triển khai chuyên trang council theo workspace thật (không redirect):
  - Analyze
  - Details
  - Citations
  - Research
  - Deepdive
- Mỗi trang có contract render riêng, giảm phụ thuộc raw dump.

## Phase C
- Claim-level verification matrix cho council:
  - claim
  - supporting evidence IDs
  - contradiction flag
  - severity
  - reviewer verdict

## Phase D (Neural Network track)
- Bổ sung neural scorer sidecar cho hội chẩn:
  - input: triage features (symptoms, labs, meds, risk flags, specialty votes)
  - output: calibrated risk probability + explanation-friendly feature contributions
- Chạy chế độ shadow trước, không override rule-engine trong giai đoạn đầu.

## 5) Neural Network hướng áp dụng cho CLARA

## 5.1 Use-cases phù hợp
1. **Risk calibration**: tinh chỉnh xác suất escalation từ ensemble rule + model.
2. **Specialist vote weighting**: học trọng số ngữ cảnh cho từng chuyên khoa theo loại ca.
3. **Citation relevance reranking**: ưu tiên evidence mạnh cho final recommendation.

## 5.2 Guardrail bắt buộc
- Model chỉ là **decision support**, không thay chẩn đoán/kê đơn.
- Hard policy chặn liều/kê đơn/chẩn đoán vẫn chạy trước mọi tầng model.
- Tất cả model output phải có audit metadata (`model_version`, `feature_set`, `confidence`, `fallback_reason`).

## 6) Deliverable đề xuất cho sprint tiếp theo
- [ ] Council route pack (analyze/details/citations/research/deepdive) chạy thật.
- [ ] Council safety benchmark pack (legal FN + critical miss regression).
- [ ] Neural sidecar P0: training/eval scaffold + shadow inference endpoint.
- [ ] Dashboard panel hiển thị quality metrics theo ca hội chẩn.

## 7) Nguồn tham khảo (official/public)
- Infermedica Virtual Triage: https://infermedica.com/solutions/triage
- Microsoft Dragon Copilot: https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot
- Suki AI: https://www.suki.ai/
- Hippocratic AI: https://www.hippocraticai.com/
- Isabel Healthcare: https://www.isabelhealthcare.com/
- Ada Health: https://ada.com/
- OpenEvidence (public app listing): https://apps.apple.com/es/app/openevidence/id6612007783?l=en-GB
- Nabla: https://www.nabla.com/
- Abridge: https://www.abridge.com/
