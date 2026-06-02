# Đề Xuất Nhánh Sản Phẩm CLARA Research

Phiên bản: 1.1  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu nhánh Research

CLARA Research là nhánh trợ lý nghiên cứu y khoa giúp:
- Rút ngắn thời gian truy xuất và tổng hợp bằng chứng.
- So sánh guideline giữa BYT và nguồn quốc tế.
- Cung cấp phản hồi có trích dẫn, có log kiểm chứng và dễ audit.

## 2. Quyết định kỹ thuật của nhánh

- Dùng **LangChain/LangGraph** cho orchestration flow nghiên cứu:
  - planner -> retrieval sub-agents -> synthesis -> verification -> policy.
- Backend runtime ưu tiên Rust để xử lý API, streaming, audit, policy và cache.
- Luồng AI Council cho doctor được kích hoạt qua graph chuyên biệt và bắt buộc lưu log.

## 3. Năng lực sản phẩm cốt lõi

### 3.1 Workflow theo mức độ truy vấn
- Mức nhanh (5 phút): trả lời câu hỏi hẹp, nguồn ưu tiên.
- Mức trung bình (10 phút): so sánh đa nguồn và phát hiện khác biệt.
- Mức sâu (20 phút): phân tích mâu thuẫn, xuất báo cáo đầy đủ.

### 3.2 Tính năng chính
- Progressive response 5-10-20.
- Citation card chuẩn hóa theo PMID/RxCUI/NCT khi có.
- So sánh guideline VN với WHO/quốc tế.
- Xuất báo cáo PDF/DOCX/Markdown.
- AI council logs cho các case cần hội chẩn.

### 3.3 Kiến trúc vận hành
- Intent router 2 lớp để định tuyến đúng role + intent.
- Multi-source retrieval + multimodal parsing.
- Synthesis node và verification node độc lập.
- FIDES-inspired fact checking trước khi publish phản hồi.

## 4. CLARA Control Tower cho nhánh Research

Dashboard phục vụ nhóm Product/Ops/Clinical/Security với các màn hình:
1. Research KPI board: time-to-first-insight, completion rate, citation quality.
2. Source quality board: freshness, coverage, conflict rate theo nguồn.
3. AI Council log explorer: tiến trình deliberation, quyết định cuối, trace id.
4. Drift & eval board: thay đổi chất lượng retrieval/verifier theo thời gian.
5. Incident board: timeout, source outage, hallucination alerts.

## 5. Giá trị kinh doanh

- Giảm giờ công tổng hợp tài liệu của đội nghiên cứu.
- Chuẩn hóa chất lượng trích dẫn và quy trình audit.
- Tăng năng lực hội chẩn đa chuyên khoa dựa trên bằng chứng.

## 6. Business model cho nhánh Research

### 6.1 Gói dịch vụ
- Research Team: theo số seat.
- Institutional: theo số khoa/phòng ban + SLA.
- API/Integration: theo số request hoặc hợp đồng năm.

### 6.2 Đơn vị trả phí chính
- Trường đại học y.
- Bệnh viện tuyến tỉnh/tuyến trung ương.
- Viện nghiên cứu và tổ chức giáo dục y khoa.

## 7. Roadmap P0 -> P6 (Research + Control Tower)

| Phase | Deliverables CLARA Research | Deliverables Control Tower |
|---|---|---|
| P0 | Router 2 lớp nền, retrieval cơ bản | KPI widget cơ bản + source health |
| P1 | Citation + verifier nền + export cơ bản | Policy gate console + feature flags |
| P2 | Progressive 5-10-20, compare guideline | Research KPI board + drift cảnh báo nền |
| P3 | AI Council + log reasoning đầy đủ | AI council log explorer + incident center |
| P4 | Hardening + enterprise analytics | Audit explorer + compliance evidence |
| P5 | Multi-tenant scale + API mở rộng | Tenant governance + cost dashboard |
| P6 | Regional/federation expansion | Dashboard liên vùng + federation controls |

## 8. KPI nhánh Research

- Time-to-first-insight theo từng tier.
- Citation coverage và citation correctness.
- Tỷ lệ phát hiện mâu thuẫn bằng chứng đa nguồn.
- Tỷ lệ phiên hoàn tất export báo cáo.
- Tỷ lệ hài lòng của researcher/bác sĩ.

## 9. Risk controls nhánh Research

- Hallucination: verification node + confidence threshold + policy gate.
- Nguồn lỗi thời: cache update/invalidate + freshness monitoring.
- Mâu thuẫn guideline: hiển thị bất đồng, không ép một kết luận.
- Latency: workflow 5-10-20 + degradation policy có kiểm soát.

## 10. Quyết định đề xuất

1. Chốt LangChain/LangGraph cho orchestration nhánh Research.
2. Chốt Research Control Tower là thành phần bắt buộc từ P0.
3. Không cho mở rộng phase nếu KPI và quality gates chưa đạt.
