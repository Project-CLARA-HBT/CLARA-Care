# Deep-Dive Rủi Ro Và Chiến Lược Giảm Thiểu

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu

Thiết lập ma trận rủi ro vận hành cho CLARA Research và CLARA Self-Med, ưu tiên an toàn y khoa, trách nhiệm pháp lý và độ tin cậy hệ thống.

## 2. Ma trận rủi ro ưu tiên cao

| Mã | Rủi ro | Mức độ | Xác suất | Nhánh ảnh hưởng |
|---|---|---|---|---|
| R1 | Bỏ sót DDI nghiêm trọng | Critical | Medium | Self-Med |
| R2 | OCR/ASR sai gây quyết định sai | High | High | Self-Med/Research |
| R3 | Hallucination không bị chặn | Critical | Medium | cả hai |
| R4 | Lộ dữ liệu nhạy cảm | Critical | Medium | cả hai |
| R5 | Drift router làm misroute workflow | High | Medium | cả hai |
| R6 | Citation giả hoặc sai nguồn | High | Medium | Research |
| R7 | Cache stale gây tư vấn lỗi thời | High | Medium | cả hai |
| R8 | Quá tải gây trễ vượt KPI role | Medium | High | cả hai |

## 3. FIDES module trong chiến lược kiểm soát

## 3.1 Vai trò FIDES

- Là tầng kiểm chứng độc lập sau synthesis.
- Không dùng chung prompt/logic với synthesis để giảm thiên lệch tự xác nhận.

## 3.2 Quy trình FIDES khuyến nghị

1. Claim decomposition.
2. Evidence retrieval per claim.
3. Cross-source consistency check.
4. Citation validity check.
5. Verdict + action mapping.

## 3.3 Action mapping

- `PASS`: cho phép trả lời.
- `PASS_WITH_WARN`: trả lời kèm cảnh báo giới hạn.
- `BLOCK`: chặn trả lời trực tiếp, yêu cầu chuyển tuyến.
- `ESCALATE`: chuyển reviewer/doctor workflow.

## 4. Rủi ro theo từng vai trò người dùng

## 4.1 Normal users

- Rủi ro chính: hiểu sai khuyến cáo, tự ý dùng thuốc.
- Giảm thiểu: câu trả lời ngắn, rõ, có cảnh báo và khuyến nghị đi khám khi cần.
- KPI: thời gian < 2 phút, ưu tiên an toàn hơn độ đầy đủ.

## 4.2 Researchers

- Rủi ro chính: tổng hợp sai do nguồn mâu thuẫn.
- Giảm thiểu: progressive output 5-10-20 phút, hiển thị conflict notes.
- KPI: minh bạch nguồn và độ tin cậy theo từng claim.

## 4.3 Doctors

- Rủi ro chính: gợi ý sai trong ca phức tạp.
- Giảm thiểu: AI Council + log suy luận + strict verification + escalation.
- KPI: <10-20 phút và bắt buộc có log hội chẩn khi kích hoạt council.

## 5. Kiểm soát kỹ thuật bắt buộc

1. Router 2 lớp với confidence threshold.
2. Nguồn dữ liệu có source registry + freshness policy.
3. Cache `update/invalidate` thay vì add mù.
4. Policy engine tập trung cho block/escalate.
5. Observability theo claim-level và modality-level.

## 6. Kiểm soát vận hành và pháp lý

- Cơ chế đồng ý dữ liệu rõ ràng theo loại dữ liệu nhạy cảm.
- Nhật ký truy cập và quyết định bắt buộc cho mọi phiên high-risk.
- Quy trình RCA sự cố P0/P1 trong vòng thời gian cam kết.
- Đào tạo đội ngũ vận hành về incident playbook y tế.

## 7. Chỉ số theo dõi rủi ro

- Critical miss rate cho DDI/allergy alerts.
- Tỷ lệ escalation theo severity.
- Drift của router accuracy theo tuần.
- Citation validity theo nguồn.
- Tỷ lệ lỗi cache stale bị phát hiện muộn.

## 8. Gating theo phase

- **Gate G0-G1**: baseline safety + privacy.
- **Gate G1-G2**: DDI/allergy detection đạt ngưỡng.
- **Gate G2-G3**: FIDES strict mode cho luồng doctor.
- **Gate G3-G4**: stress/load + DR drill đạt yêu cầu.
- **Gate G4+**: governance tự động và audit readiness.

## 9. Kịch bản dự phòng

- Mất nguồn dữ liệu chính: degrade mode + cảnh báo trust score.
- OCR service lỗi: fallback text entry + xác nhận người dùng.
- Verifier quá tải: ưu tiên case high-risk, queue phần còn lại.
- Nghi ngờ vi phạm dữ liệu: cô lập dịch vụ + incident response ngay.

## 10. Kết luận

Chiến lược rủi ro của CLARA phải đặt verification và policy ở trung tâm. Thành công không đo bằng số câu trả lời, mà đo bằng khả năng chặn sai sót nguy hiểm trước khi đến tay người dùng.

## 11. LangChain/LangGraph suitability dưới góc rủi ro vận hành

### 11.1 Lợi ích

- Mô hình hóa workflow phức tạp rõ ràng bằng graph transitions.
- Dễ chèn guardrails, retries, fallback nodes, HITL transitions.
- Phù hợp với bài toán multi-agent và progressive execution.

### 11.2 Rủi ro lock-in và phức tạp

- Lock-in nếu policy/business rules gắn cứng vào graph node implementation.
- Khó quan sát nguyên nhân lỗi nếu thiếu trace chuẩn ở từng bước graph.
- Rủi ro “silent regression” khi chỉnh prompt/edge mà không có test graph-level.

### 11.3 Mô hình hybrid giảm rủi ro

- Đặt Rust làm lớp kiểm soát hệ thống (control plane) và boundary bảo mật.
- Đặt LangGraph/LangChain ở lớp điều phối AI (orchestration plane).
- Đặt rule engine deterministic cho logic safety-critical để giảm rủi ro LLM.

## 12. Checklist triển khai dashboard an toàn cho clinical AI

1. Dashboard phải có 4 lớp: `quality`, `safety`, `operations`, `compliance`.
2. Bắt buộc có alert cho: drift router, giảm verification pass, tăng block/escalate bất thường.
3. Bắt buộc có model/prompt/policy version governance và rollback one-click.
4. Bắt buộc có HITL queue và SLA xử lý ca critical.
5. Bắt buộc có incident center với RCA template chuẩn.
6. Bắt buộc có audit explorer theo `trace_id/claim_id/session_id`.
7. Bắt buộc có compliance evidence export cho kiểm toán y tế.
8. Bắt buộc diễn tập DR cho mất nguồn dữ liệu và verifier degradation.
