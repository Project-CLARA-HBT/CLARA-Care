# Luồng Công Việc CLARA Research

## 1. Mục tiêu nhánh

Xây dựng trợ lý nghiên cứu y khoa có khả năng:
- truy xuất đa nguồn đa phương thức,
- tổng hợp theo bằng chứng có trích dẫn,
- kiểm chứng độc lập trước khi trả kết quả,
- quan sát chất lượng theo thời gian thực qua dashboard quản trị.

## 2. Áp dụng LangChain/LangGraph (chốt triển khai)

- Dùng **LangGraph** làm runtime orchestration cho các graph workflow:
  - `research_simple_graph`
  - `research_progressive_graph` (mốc 5-10-20)
  - `doctor_council_graph` (khi cần hội chẩn)
- Dùng **LangChain** cho:
  - retriever composition,
  - tool binding,
  - prompt template quản trị theo phiên bản.
- Backend Rust đóng vai trò:
  - gateway/API,
  - auth/RBAC,
  - session/audit/policy,
  - streaming transport và observability ingest.

## 3. Phạm vi chức năng

### 3.1 Chức năng lõi
- Intent router 2 lớp cho role `Researcher`.
- Progressive workflow 5-10-20 phút.
- So sánh guideline BYT với WHO và nguồn quốc tế.
- Xuất báo cáo PDF/DOCX/Markdown có citation.

### 3.2 Chức năng mở rộng
- Multi-hop retrieval theo hypothesis.
- Phân tích bất đồng nguồn và conflict notes.
- Coding agent hỗ trợ công thức y khoa có guardrails.

## 4. Kiến trúc nhánh Research

1. Planner (LangGraph) phân rã câu hỏi thành sub-queries.
2. Retrieval agents gọi PubMed, ClinicalTrials, BYT crawler, Dược thư, web recheck.
3. Synthesis node tạo draft + claim set.
4. Verification node (FIDES-inspired) xác thực claim/citation.
5. Policy gate áp mức tin cậy và cảnh báo.

## 5. Tích hợp với nền tảng

- Rust backend cung cấp API orchestration, streaming, audit trail.
- Python ML services xử lý embedding/rerank/generation/verifier.
- Web/Flutter dùng chung contract response gồm:
  - `citations`
  - `confidence`
  - `verification_status`
  - `policy_action`

## 6. Deliverables theo phase

- P0-P1: router + retrieval + synthesis/verification nền.
- P2: progressive 5-10-20 + export + quality dashboards.
- P3: AI Council logs + governance dashboard.
- P4-P6: hardening + enterprise + ecosystem federation.

## 7. Dashboard cần có cho nhánh Research

- Query volume theo intent.
- Time-to-first-result và time-to-final-result.
- Citation coverage, verification pass rate.
- Conflict frequency giữa nguồn VN và quốc tế.
- Cost per research session theo độ sâu 5-10-20.

## 8. KPI nhánh Research

- Mốc 5 phút: tóm tắt sơ bộ + nguồn chính.
- Mốc 10 phút: bảng so sánh bằng chứng + bất đồng.
- Mốc 20 phút: báo cáo hoàn chỉnh + export.
- Citation coverage >= 95%.
- Verification pass >= 97%.

## 9. Rủi ro và kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| Nguồn mâu thuẫn | conflict resolver + note bắt buộc trong output |
| Hallucination khi tổng hợp dài | tách synthesis/verification + policy gate |
| Độ trễ tăng khi multi-hop | giới hạn budget token/time + cache thông minh |
| Trôi chất lượng theo thời gian | dashboard drift + eval jobs định kỳ |

## 10. Tiêu chí hoàn tất

1. Flow research 5-10-20 chạy ổn định trên web và mobile.
2. Export báo cáo hoạt động với đầy đủ citation.
3. Dashboard hiển thị được KPI chất lượng và cảnh báo drift cho nhánh Research.
