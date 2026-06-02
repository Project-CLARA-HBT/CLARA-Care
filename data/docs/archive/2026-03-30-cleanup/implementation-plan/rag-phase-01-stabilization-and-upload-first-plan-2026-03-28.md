# Kế hoạch Phase 1: Ổn định RAG + Upload-First + Citation Bar (2026-03-28)

## 1) Mục tiêu phase
- Sửa lỗi timeout `15000ms exceeded` ở luồng Research.
- Tránh phản hồi thất bại kiểu: "không có thông tin từ ngữ cảnh".
- Bổ sung truy xuất khoa học từ API chuẩn (PubMed/NCBI, Europe PMC, ClinicalTrials).
- Có trang/luồng upload file để khởi tạo trước, sau đó mới phân tích chi tiết.
- Có citation bar dạng chip (giống trải nghiệm tra cứu hiện đại).
- Mở rộng Admin để cấu hình RAG có tác dụng thực tế runtime.

## 2) Vấn đề hiện tại (tóm tắt)
- Retriever hiện tại còn dạng stub/in-memory, chưa đủ cho truy vấn thực tế.
- Luồng Tier2 chưa truy xuất nguồn bên ngoài một cách ổn định.
- FE dùng timeout ngắn, dễ fail khi truy vấn chuyên sâu.
- Citation chủ yếu hiển thị ở block cuối, chưa có bar gọn theo ngữ cảnh trả lời.
- Upload file cho Research chưa là first-class flow.

## 3) Thiết kế kỹ thuật phase này

### 3.1 Hybrid Retrieval tối thiểu khả dụng
- Dense score (stub embedding hiện tại) + lexical overlap.
- Nếu low-context:
  - gọi PubMed E-utilities (ESearch + ESummary)
  - gọi Europe PMC REST search
  - hợp nhất/rerank nhẹ rồi mới fallback LLM.
- Khi external lỗi: fail-soft, không làm hỏng phản hồi.

### 3.2 Fallback an toàn
- Nếu không có RAG context đủ mạnh, dùng DeepSeek trả lời an toàn có hướng dẫn rõ.
- Nếu output LLM rơi vào mẫu "không có ngữ cảnh" thì ép sang nhánh trả lời hữu ích (guardrail hậu xử lý).

### 3.3 Upload-first UX
- Bước 1: upload file lớn để bắt đầu.
- Bước 2: chạy process + hiển thị kết quả chi tiết.
- Có thể gửi `uploaded_file_ids` vào Tier2 để tăng context.

### 3.4 Citation UX
- Citation bar ngay dưới câu trả lời (`[1] [2] ...`) + nguồn chính.
- Vẫn giữ phần chi tiết citation card (title/source/year/url/snippet).

### 3.5 Admin RAG runtime control
- Source có `enabled`, `priority`, và `weight`.
- Flow có toggles: router, verification, fallback, scientific/web/file retrieval.
- Cấu hình phải được truyền vào runtime thay vì chỉ lưu config.

## 4) Nguồn dữ liệu uy tín và trạng thái API key

### 4.1 Nguồn có thể dùng ngay (không cần key hoặc chế độ no-key)
- NCBI E-utilities / PubMed: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- Europe PMC REST: https://europepmc.org/RestfulWebService
- ClinicalTrials.gov API v2: https://clinicaltrials.gov/data-api/api
- RxNav/RxNorm APIs: https://lhncbc.nlm.nih.gov/RxNav/APIs/
- DailyMed REST: https://dailymed.nlm.nih.gov/dailymed/webservices-help/v2/spls_api.cfm
- Crossref REST API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/

### 4.2 Nguồn nên có API key để scale tốt hơn
- NCBI API key (tăng throughput E-utilities): https://www.ncbi.nlm.nih.gov/books/NBK25500/
- openFDA API key (quota cao hơn): https://open.fda.gov/apis/authentication/

### 4.3 Nguồn thương mại/đối tác (nâng cấp sau)
- DrugBank API (DDI chuyên sâu, license)
- VigiBase (pharmacovigilance, data agreement)
- FHIR đối tác bệnh viện (thỏa thuận liên thông)

## 5) Benchmark nhanh sản phẩm tương tự (để áp dụng)
- Medisafe: nhắc thuốc, theo dõi gia đình, cảnh báo tương tác, tracker chỉ số.
  - https://medisafeapp.com/features/
- Drugs.com Interaction Checker: UX nhập danh sách thuốc + mức độ tương tác rõ.
  - https://www.drugs.com/drug_interactions.html
- Dosecast: lịch linh hoạt, refill alerts, adherence history, multi-person.
  - https://dosecast.com/features/
- CareClinic: tracker tổng hợp (thuốc + triệu chứng + lối sống), báo cáo theo dõi.
  - https://careclinic.io/features/

## 6) Kiến trúc RAG tham chiếu để mở rộng P2+
- GraphRAG (graph memory): https://github.com/microsoft/graphrag
- Self-RAG (adaptive retrieve + self-reflection): https://arxiv.org/abs/2310.11511
- LangGraph workflows/agents: https://docs.langchain.com/oss/javascript/langgraph/workflows-agents
- Dify knowledge pipeline orchestration (tham khảo control plane):
  - https://docs.dify.ai/en/guides/knowledge-base/knowledge-pipeline/knowledge-pipeline-orchestration

## 7) Danh sách key cần bạn cung cấp để chạy full công suất
- `DEEPSEEK_API_KEY` (đã có)
- `NCBI_API_KEY` (khuyến nghị)
- `OPENFDA_API_KEY` (khuyến nghị)
- `TGC_OCR_API_KEY` (dùng chung từ tgc-transhub)
- (Tuỳ chọn) `SERP_API_KEY` hoặc provider web search khác nếu muốn web retrieval rộng ngoài biomedical APIs

## 8) Định nghĩa xong phase (DoD)
- Không còn timeout 15s ở luồng research chuyên sâu.
- Tier2 có thể trả lời ngay cả khi local RAG yếu, vẫn có fallback hữu ích.
- Có upload-first flow hoạt động thực tế.
- Có citation bar + citation details rõ nguồn.
- Admin chỉnh source/flow có ảnh hưởng runtime.
- Test backend/frontend trọng yếu pass.
