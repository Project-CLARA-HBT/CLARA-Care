# HỒ SƠ DỰ ÁN CLARA (PLAN V2)
## GDGoC Hackathon Vietnam 2026

Phiên bản: 2.0 (Plan-focused, aligned với execution plans)  
Ngày cập nhật: 2026-04-02  
Đội: Clararara

---

## Thông tin đội

| STT | Họ và tên | Vai trò |
|---|---|---|
| 1 |  | Product/PM |
| 2 |  | Backend/API |
| 3 |  | ML/RAG |
| 4 |  | Frontend/Mobile |

---

## 0. Executive Pitch

### 0.1 Vấn đề trọng tâm
- Gánh nặng bệnh mạn/NCD tăng cao.
- Nguy cơ tương tác thuốc (DDI), dùng thuốc sai, tự ý dùng thuốc trong cộng đồng.
- Nhóm sinh viên y/bác sĩ trẻ thiếu công cụ deep research có kiểm chứng.

### 0.2 Giải pháp CLARA
- `CLARA Research`: truy xuất bằng chứng y khoa đa nguồn, có verification và citations.
- `CLARA Self-MED`: quản lý tủ thuốc gia đình, cảnh báo DDI/allergy, hướng dẫn an toàn.
- `CLARA Council`: hội chẩn AI có safety gate và giải trình theo chuyên khoa.
- `CLARA Control Tower`: quản trị runtime, nguồn tri thức, telemetry và quality gates.

### 0.3 Điểm khác biệt cạnh tranh
- Kiến trúc `route -> retrieve -> synthesize -> verify -> policy`.
- Kết hợp Agentic RAG + safety policy + governance vận hành.
- Có roadmap kỹ thuật theo phase, KPI gate, rollback và pilot metrics rõ ràng.

### 0.4 Mapping tiêu chí hackathon

| Tiêu chí | CLARA đáp ứng |
|---|---|
| Innovation | Agentic RAG + verification matrix + policy action gate |
| Impact | Trực diện DDI risk + medication safety + research efficiency |
| Feasibility | Monorepo đang chạy + kế hoạch triển khai chi tiết theo phase |
| Scalability | Control Tower + observability + rollout/canary/rollback plan |
| Demo readiness | Demo script 5 phút cho Research + Self-MED + Council + Admin |

### 0.5 Các điểm mới kỹ thuật để định vị CLARA vượt thị trường VN
1. Policy-first Agentic RAG: pipeline cưỡng chế `route -> retrieve -> verify -> policy` thay vì chatbot trả lời trực tiếp.
2. Claim-level verification matrix: không dừng ở citations mà đánh giá từng claim `supported/contradicted/insufficient`.
3. Dual-track answer engine: tách `Clinical Safe` và `Analyst Deep` để vừa an toàn vừa đủ chiều sâu.
4. Agentic Document Extraction (ADE): trích xuất tài liệu nhiều bước `parse -> normalize -> confidence gate -> human confirm`.
5. Hybrid VN drug normalization: dictionary exact + neural candidate matching + confidence-based mapping source.
6. OCR-to-clinical safety pipeline: `OCR raw -> neural correction -> manual confirm` trước khi ghi vào cabinet.
7. Risk-aware source routing: chọn retrieval profile theo intent/domain/risk, có policy ràng buộc nguồn.
8. Active eval loop tự động: `baseline -> hard-negative mining -> rerun -> regression gate`.
9. Replayable research runbook: mỗi run có trace/replay pack phục vụ audit và phản biện.
10. Runtime Control Tower for AI Safety Ops: bật/tắt nguồn và strictness theo thời gian thực không cần redeploy.

---

## 1. Bài toán và mục tiêu

### 1.1 Bài toán
- Làm sao tự động phát hiện rủi ro DDI trong tủ thuốc gia đình nhanh, dễ dùng, có kiểm soát?
- Làm sao trả lời y khoa theo ngôn ngữ dễ hiểu nhưng giảm hallucination?
- Làm sao giữ an toàn pháp lý/đạo đức: AI hỗ trợ tham khảo, không thay thế quyết định lâm sàng?

### 1.2 Mục tiêu dự án
1. Tăng độ đúng retrieval/answer trong Research mode.
2. Giảm lỗi safety-critical (bỏ sót DDI, claim không có evidence).
3. Tối ưu user flow, giảm thao tác, tăng tỷ lệ hoàn thành phiên.
4. Thiết lập quality gates để không ship khi KPI tụt ngưỡng.

---

## 2. Kiến trúc giải pháp (Target Architecture)

### 2.1 Runtime flow
1. Input + auth + consent.
2. Router theo role/intent/risk.
3. Multi-pass retrieval (internal/scientific/web/file).
4. Synthesis draft.
5. Verification matrix (claim-level).
6. Policy decision (`allow/warn/block/escalate`).
7. Response + citations + telemetry + flow events.

### 2.2 Các nguyên tắc an toàn
1. Hard legal guard không phụ thuộc prompt.
2. Safety-critical luôn có rule override.
3. Khi low-context hoặc timeout: fallback an toàn có giải thích.
4. Human-in-the-loop cho OCR confidence thấp và ca rủi ro cao.

---

## 3. Agentic AI trong CLARA

### 3.1 Luồng tác tử chính
1. `Routing Agent`: phân loại role/intent/risk để chọn retrieval profile.
2. `Retrieval Orchestrator`: điều phối pass retrieval đa nguồn.
3. `Synthesis Agent`: tạo draft có cấu trúc.
4. `Verifier Agent`: claim-level verification + contradiction summary.
5. `Policy Gate`: ra quyết định cuối theo luật an toàn.

### 3.2 Tác tử nghiệp vụ theo module
- `CareGuard Agent`: DDI/an toàn thuốc, ưu tiên deterministic + external evidence.
- `Research Tier2 Agent`: deep research nhiều pass, citation-heavy.
- `Council Agent`: hội chẩn đa chuyên khoa, confidence/data-quality aware.
- `Scribe Agent`: chuẩn hóa SOAP từ transcript.

### 3.3 Agentic Document Extraction (ADE)
1. Mục tiêu ADE: biến dữ liệu không cấu trúc (ảnh toa, PDF, file upload, transcript) thành dữ liệu có thể suy luận an toàn.
2. Luồng ADE chuẩn:
3. Ingestion: nhận file và phân loại loại tài liệu.
4. Parse layer: OCR/ASR/PDF text extraction theo adapter phù hợp.
5. Normalization layer: chuẩn hóa tên thuốc, hoạt chất, đơn vị, alias VN/EN.
6. Confidence layer: chấm độ tin cậy extraction/mapping cho từng item.
7. Verification layer: đối chiếu dictionary/rule/external sources để giảm nhận diện sai.
8. Human-in-the-loop: confidence thấp thì bắt buộc manual confirm.
9. Output contract: `extracted_fields`, `normalized_entities`, `confidence`, `mapping_source`, `requires_manual_confirm`.
10. Lợi thế kỹ thuật: ADE tách khỏi chat flow để có thể đo kiểm, audit và rollback độc lập.

### 3.4 Neural Network Stack trong CLARA
1. Retrieval Neural Layer:
2. Neural reranker cho top-N candidates trước synthesis.
3. Biomedical scoring để ưu tiên nguồn đúng miền lâm sàng.
4. Verification Neural Layer:
5. NLI claim verifier cho từng claim với confidence và contradiction rationale.
6. Safety override cho claim loại `dosage/contraindication` khi verdict rủi ro.
7. Normalization Neural Layer:
8. Neural candidate matching cho biệt dược VN và mapping sang hoạt chất chuẩn.
9. OCR Correction Neural Layer:
10. Hậu xử lý lỗi ký tự/spacing của OCR trước bước confirm.
11. Neural Source Router Layer:
12. Dự đoán retrieval profile `internal-heavy/scientific-heavy/web-assisted/file-grounded` theo query complexity.
13. Training/Eval Loop:
14. Hard-negative mining từ production telemetry để tái huấn luyện/rerank tuning theo chu kỳ.
15. Feature flags:
16. Toàn bộ neural components đều bật/tắt qua config để fail-safe và canary rollout.

---

## 4. Kế hoạch Neural Network 3-Phase trong 28 ngày

## 4.1 Phase 1 (Day 1-10): Neural Reranker + NLI Verification
Mục tiêu:
1. Tăng độ đúng retrieval.
2. Giảm unsupported claims.
3. Chuẩn hóa verification matrix end-to-end.

Deliverables:
1. Reranker sidecar có feature flag.
2. NLI claim verifier với verdict `supported/contradicted/insufficient`.
3. Payload chuẩn: `verification_matrix`, `unsupported_claims`, `nli_summary`.
4. UI matrix + telemetry hiển thị đầy đủ.

KPI Gate:
1. `Precision@5` tăng >= 8% so baseline.
2. `Unsupported claim rate` giảm >= 30%.
3. `Refusal compliance` >= 99%.
4. `p95 latency` tăng không quá 20%.

Definition of Done:
1. Bật/tắt qua runtime config.
2. Có telemetry + dashboard đọc được.
3. CI + active-eval + smoke deploy pass.

## 4.2 Phase 2 (Day 11-18): VN Drug Neural Normalization
Mục tiêu:
1. Chuẩn hóa biệt dược Việt Nam theo pipeline hybrid.
2. Giảm miss DDI do sai mapping tên thuốc.

Deliverables:
1. Hybrid normalize: dictionary -> neural candidate -> cross-encoder chọn best.
2. Lưu metadata mapping: `mapping_source`, `confidence`, `active_ingredients`, `rxcui`.
3. Manual confirm UX cho người lớn tuổi.
4. Admin curation endpoint + audit history.

KPI Gate:
1. `Mapping accuracy` >= 90% trên testset VN nội bộ.
2. `Critical DDI miss` giảm >= 40%.
3. `Manual confirm rate` giảm dần theo thời gian curation.

Definition of Done:
1. Mapping có audit trail.
2. DDI pipeline phản ánh đúng ingredient normalized.
3. CareGuard/Self-MED đồng nhất một nguồn dữ liệu.

## 4.3 Phase 3 (Day 19-28): OCR Correction + Source Router + Active Eval Automation
Mục tiêu:
1. Tăng độ bền production.
2. Giảm source mismatch và timeout fallback.
3. Tạo vòng phản hồi chất lượng tự động.

Deliverables:
1. OCR correction module sau OCR raw.
2. Neural source router theo intent/domain/risk.
3. Metadata chuẩn: `retrieval_route`, `router_confidence`, `fallback_reason`.
4. Active eval loop tự động: baseline -> mine hard negatives -> rerun -> compare.

KPI Gate:
1. `Source mismatch rate` giảm >= 25%.
2. `Fallback due to timeout` giảm >= 30%.
3. `Regression detection lead time` < 1 ngày.
4. Không giảm metric safety-critical.

Definition of Done:
1. Deep flow ổn định tải cao.
2. Có feedback loop tự động và báo cáo regression.
3. Có canary + rollback theo ngưỡng.

---

## 5. Lịch thực thi Day-by-Day (28 ngày)

### Day 1-10 (Phase 1)
1. Day 1-2: contract + config flags + reranker skeleton.
2. Day 3-4: scoring/ranking + timeout fallback + NLI module.
3. Day 5-6: tích hợp vào research pipeline + UI matrix.
4. Day 7-8: integration/regression + latency optimization + cache.
5. Day 9-10: active eval full + gate phase 1.

### Day 11-18 (Phase 2)
1. Day 11-12: schema/migration + seed dictionary VN.
2. Day 13-14: hybrid normalize + tích hợp careguard/selfmed.
3. Day 15-16: UX confirm + admin curation + audit trail.
4. Day 17-18: testset VN + gate phase 2.

### Day 19-28 (Phase 3)
1. Day 19-20: OCR correction + integration scan flow.
2. Day 21-22: source router + policy constraints.
3. Day 23-24: metadata chuẩn + active-eval upgrade.
4. Day 25-26: workflow schedule + flow canvas update.
5. Day 27-28: full KPI run + canary + final gate.

---

## 6. Deep Research Upgrade Plan

### 6.1 Mục tiêu
1. Ít bước hơn, dễ dùng hơn.
2. Report chất lượng hơn, giải trình tốt hơn.
3. Quan sát vận hành tốt hơn.

### 6.2 Điểm nâng cấp sản phẩm
1. Plan-first research có thể chỉnh tay trước khi chạy.
2. Multi-pass retrieval theo pass budget và risk profile.
3. Contradiction-aware verification matrix.
4. Dual-track output:
   - Safe concise answer.
   - Deep evidence pack.
5. Replayable runbook để audit/review.
6. Auto-Mermaid evidence graph cho reviewer.

### 6.3 Phase execution
1. Phase 1: planner + multi-pass retrieval + stage spans.
2. Phase 2: verification matrix v2 + formatter/export.
3. Phase 3: collaboration + observability + hardening.

---

## 7. Council AI Upgrade Plan

### 7.1 Mục tiêu
1. Giảm friction, ít thao tác.
2. Tăng chất lượng hội chẩn đa chuyên khoa.
3. Tăng safety/accuracy controls.

### 7.2 UX flow đề xuất
1. 1 trang intake chính (thu thập ca bệnh).
2. Kết quả tách ra nhiều trang chuyên biệt:
   - Analyze
   - Details
   - Citations
   - Research
   - Deep Dive

### 7.3 Nâng cấp kỹ thuật
1. Negation-aware symptom handling.
2. Missing-info workflow + follow-up prompts.
3. Confidence/data-quality scoring.
4. Structured citations + compatibility field cho hệ cũ.

---

## 8. Công nghệ dự kiến sử dụng

### 8.1 AI/ML
- Agentic RAG.
- LangChain/LangGraph orchestration.
- Neural reranker + NLI verifier.
- Drug normalization hybrid (dictionary + neural).
- OCR correction + source router.

### 8.2 Backend/Frontend
- Backend: FastAPI (Python), async APIs.
- Frontend web: Next.js/React.
- Mobile: Flutter (roadmap production hardening).

### 8.3 Dữ liệu và hạ tầng
- PostgreSQL cho dữ liệu giao dịch.
- Caching/queue và retrieval stack mở rộng theo roadmap.
- Docker Compose cho môi trường triển khai.
- CI/CD qua GitHub Actions, có smoke gates.

---

## 9. KPI Framework và Go/No-Go Gate

### 9.1 KPI nhóm chất lượng
1. Retrieval quality: Precision@K, Recall@K, NDCG@K.
2. Verification quality: unsupported claim rate, contradiction handling.
3. Safety quality: refusal compliance, critical DDI miss rate.
4. Runtime quality: p50/p95 latency, fallback success rate, source timeout rate.

### 9.2 Gate nguyên tắc
1. Không đạt safety KPI -> NO-GO.
2. Regression chất lượng > ngưỡng -> NO-GO.
3. Gate pass mới được promote staging/production.

---

## 10. Kế hoạch Pilot 90 ngày sau hackathon

### 10.1 Mục tiêu
1. Xác thực tác động thực tế trên cohort pilot.
2. Đo được cải thiện rõ so baseline nội bộ.

### 10.2 KPI pilot đề xuất
1. Citation coverage >= 90% (Research mode).
2. Verification pass rate >= 95%.
3. Alerts acknowledged >= 85%.
4. Availability >= 99% trong pilot window.

### 10.3 Milestone 30-60-90
1. 30 ngày: ổn định core quality gates.
2. 60 ngày: mở rộng cohort pilot + dashboard governance.
3. 90 ngày: báo cáo tác động + quyết định mở rộng.

---

## 11. Mô hình kinh doanh

### 11.1 B2C
1. Trial onboarding:
   - 7 ngày premium đầu tiên.
   - Trial theo hành vi (vượt giới hạn scan/query).
2. Credit model cho AI usage.
3. Gói quyền:
   - Basic.
   - Family/High.
   - Full safety.

### 11.2 B2B
1. Nhà thuốc:
   - Referral/order integration.
2. Doanh nghiệp:
   - MedAI benefit cho nhân viên.
3. Đơn vị đào tạo y:
   - Research workflow package + governance dashboard.

---

## 12. Phân công thực thi theo workstream

1. Product/Clinical: scope, safety policy, acceptance criteria.
2. ML: reranker/NLI/router/normalization/active-eval.
3. Backend: API contracts, auth/rbac, control tower, telemetry.
4. Frontend: research/council/selfmed UX + admin panels.
5. Mobile: flow parity theo roadmap.
6. DevOps/SRE: CI/CD, canary, rollback, observability.
7. Security/Compliance: consent/audit/data governance.
8. QA: unit/integration/e2e/safety regression.

---

## 13. Risk Register và phương án giảm thiểu

| Risk | Tác động | Mitigation |
|---|---|---|
| Latency tăng do NN | UX giảm, timeout tăng | Timeout cứng, cache, pass budget, degrade mode |
| False confidence | Khuyến nghị sai | Confidence gate + safety override + manual confirm |
| Source drift/mismatch | Sai evidence | Trusted source policy + source router constraints |
| OCR noise | Mapping sai -> DDI sai | OCR correction + threshold + manual confirm |
| External API outage | Gián đoạn retrieval | Retry, circuit-breaker, fallback an toàn |
| Telemetry thiếu | Khó audit/debug | Trace completeness gate + replay runbook |

---

## 14. Kế hoạch demo 5 phút

1. `Research`: chạy query deep, hiển thị citations + verification matrix.
2. `Self-MED`: scan/nhập thuốc, phát hiện DDI + khuyến nghị an toàn.
3. `Council`: intake ca bệnh, xem Analyze/Details/Citations.
4. `Control Tower`: bật/tắt source/runtime, xem flow events/telemetry.
5. Chốt bằng KPI gate và roadmap 28 ngày + pilot 90 ngày.

---

## 15. Tuyên bố phạm vi và đạo đức

1. CLARA là hệ thống hỗ trợ tham khảo, không thay thế bác sĩ/dược sĩ.
2. Không tự động kê đơn/chẩn đoán/chỉ định liều.
3. Tình huống cấp cứu phải escalation tới cơ sở y tế.
4. Quyết định chuyên môn cuối cùng thuộc nhân sự y tế có thẩm quyền.

---

## 16. Tài liệu nguồn nội bộ dùng để align bản kế hoạch này

1. `docs/hackathon/neural-network-3phase-28day-execution-plan.md`
2. `docs/hackathon/deep-research-2026-benchmark-and-implementation-plan.md`
3. `docs/hackathon/council-ai-upgrade-2026-04-02.md`
4. `data/docs/proposal/clara-full-proposal-2026-03-29.md`
5. `data/docs/implementation-plan/round2-14-day-execution-checklist-2026-03-30.md`
6. `data/docs/hackathon/hackathon-status-truth-2026-04-02.md`
