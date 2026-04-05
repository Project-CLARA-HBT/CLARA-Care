# CLARA-Care - Bản Chỉnh Theo Góc Nhìn Giám Khảo (Bám Sát Codebase)

Ngày cập nhật: **Thứ Ba, 31/03/2026**

## 1) Kết luận chấm nhanh
- Mức sẵn sàng demo hiện tại: **khá**.
- Điểm mạnh nổi bật: có sản phẩm chạy được end-to-end (`web + api + ml`), có legal guard, có consent gate, có fallback cho DDI.
- Điểm trừ chính: một số mô tả trong hồ sơ đang cao hơn trạng thái triển khai thực tế.

## 2) Điểm tốt (nên giữ và nhấn mạnh)
- Có `hard legal guard` chặn yêu cầu kê đơn/chẩn đoán/liều dùng tại backend: `services/ml/src/clara_ml/main.py:220`.
- Có `consent gate` trước tính năng y tế: `services/api/src/clara_api/core/consent.py:26`.
- CareGuard có local DDI rules + external RxNav/openFDA + fallback metadata:  
  `services/ml/src/clara_ml/agents/careguard.py:377`,  
  `services/ml/src/clara_ml/clients/drug_sources.py:44`.
- Có pipeline CI (lint/type/test/build) rõ ràng: `.github/workflows/ci.yml:1`.

## 3) Điểm chưa tốt (cần sửa trong hồ sơ)
- `Search` endpoint vẫn là placeholder: `services/api/src/clara_api/api/v1/endpoints/search.py:14`.
- Upload research chưa parse sâu PDF/ảnh (mới parse text tốt): `services/api/src/clara_api/api/v1/endpoints/research.py:89`.
- Scribe đang ở mức skeleton + fallback: `services/ml/src/clara_ml/agents/scribe_soap.py:125`.
- UI Scribe vẫn ghi rõ chức năng placeholder (copy/export): `apps/web/app/scribe/page.tsx:53`.
- RAG runtime chính đang dùng retriever in-memory, chưa thể hiện luồng sản xuất qua Milvus/Elastic/Neo4j:  
  `services/ml/src/clara_ml/rag/retrieval/in_memory.py:16`,  
  `services/ml/src/clara_ml/rag/pipeline.py:35`.
- Dữ liệu ecosystem trong system endpoint là mock/simulated: `services/api/src/clara_api/api/v1/endpoints/system.py:71`.

## 4) Các câu cần sửa trực tiếp trong thuyết minh

### 4.1 Sửa claim hạ tầng dữ liệu
**Không nên ghi:** “Đang vận hành đầy đủ Milvus/Elasticsearch/Neo4j trong pipeline lõi.”

**Nên ghi:**
> Hệ thống đã dựng sẵn hạ tầng PostgreSQL/Redis/Milvus/Elasticsearch/Neo4j ở mức infrastructure để chuẩn bị mở rộng.  
> Trong phiên bản hiện tại phục vụ demo cuộc thi, luồng truy xuất chính đang dùng retriever in-memory kết hợp external connectors (PubMed, RxNav/openFDA, ...), có fallback an toàn khi nguồn ngoài không sẵn sàng.

### 4.2 Sửa claim ingestion/chunking
**Không nên ghi:** “Đã parse sâu đa định dạng PDF/ảnh hoàn chỉnh.”

**Nên ghi:**
> Phiên bản hiện tại xử lý tốt file text và metadata hóa tài liệu tải lên.  
> Với PDF/ảnh, hệ thống đang ở mức nhận file + tạo preview + OCR theo adapter; parsing sâu và chunking chuyên biệt theo cấu trúc phác đồ là lộ trình nâng cấp tiếp theo.

### 4.3 Sửa claim Medical Scribe
**Không nên ghi:** “Medical Scribe đã hoàn thiện và sẵn sàng vận hành bệnh viện.”

**Nên ghi:**
> CLARA Medical Scribe đang ở mức baseline (SOAP skeleton) để chứng minh kiến trúc và luồng tích hợp.  
> Mục tiêu sau cuộc thi là mở rộng template chuyên khoa, chuẩn hóa coding lâm sàng và hoàn thiện export workflow.

### 4.4 Sửa claim observability
**Không nên ghi:** “Control Tower đang hiển thị toàn bộ tín hiệu liên viện theo thời gian thực.”

**Nên ghi:**
> Control Tower đã có khung quản trị cấu hình RAG, health check và flow event runtime.  
> Một số dashboard ecosystem hiện dùng dữ liệu mô phỏng để phục vụ demo giao diện, sẽ thay bằng telemetry production trong giai đoạn pilot.

## 5) Bản mô tả kiến trúc đề xuất (đã chỉnh, dùng cho hồ sơ)

### 5.1 Kiến trúc vận hành hiện tại
- **Client layer:** Web (Next.js), Mobile (Flutter skeleton).
- **API layer:** FastAPI + JWT + RBAC + consent gate.
- **ML layer:** Role/Intent routing, RAG pipeline, legal guard, verification lite, fallback.
- **Data layer đang dùng trực tiếp:** PostgreSQL (nghiệp vụ), in-memory retrieval + external connectors.
- **Data/infra đã chuẩn bị:** Redis, Milvus, Elasticsearch, Neo4j, MinIO/etcd (phục vụ scale-out giai đoạn sau).
- **Ops:** Docker Compose, CI pipeline, test suite.

### 5.2 Luồng an toàn cốt lõi
1. User gửi truy vấn/case.
2. API kiểm tra auth + role + consent.
3. Routing xác định intent và nhánh xử lý.
4. Legal guard chặn yêu cầu vượt thẩm quyền.
5. Retrieval + synthesis + verification lite.
6. Trả kết quả kèm attribution/citation/fallback flag.

## 6) Tính mới, tính sáng tạo (bản viết lại an toàn)

### 6.1 Tính mới (đã triển khai được)
- Tích hợp trong một nền tảng thống nhất các luồng: Research, Self-Med, Scribe baseline, Control Tower.
- Có cơ chế fallback an toàn khi ML hoặc nguồn ngoài lỗi.
- Có consent gate và legal guard ngay trong backend thay vì chỉ dựa prompt.

### 6.2 Tính sáng tạo (đúng mức triển khai)
- Tạo kiến trúc “AI có kiểm soát” cho bài toán y tế học đường/cộng đồng: routing + policy + evidence + fail-soft.
- Kết hợp local safety rules với nguồn mở y khoa (RxNav/openFDA/PubMed...) để tăng khả năng giải trình.
- Thiết kế runtime toggle để trình diễn online/offline behavior mà không cần restart toàn hệ thống.

## 7) Câu chuyện demo nên chốt với giám khảo
- **Case A (Self-Med):** Scan/nhập tủ thuốc -> DDI cảnh báo -> có nguồn + mức độ rủi ro.
- **Case B (An toàn pháp lý):** Prompt bẫy kê đơn/chẩn đoán/liều dùng -> bị chặn bởi legal guard.
- **Case C (Fallback):** Tắt external DDI runtime -> hệ thống vẫn cảnh báo từ local rules.

## 8) Danh sách chỉnh sửa hồ sơ trước khi nộp
- [ ] Sửa ngày “31/03/2026” thành **Thứ Ba**.
- [ ] Hạ claim Milvus/Elastic/Neo4j từ “đang dùng lõi” thành “đã dựng sẵn, đang mở rộng”.
- [ ] Đổi phần ingestion thành “text-first + OCR adapter, parse sâu là roadmap”.
- [ ] Đổi phần Scribe thành “baseline/skeleton”.
- [ ] Đánh dấu rõ các phần dữ liệu mô phỏng trong dashboard.
- [ ] Giữ trọng tâm chấm thi vào `Self-MED + Safety + Evidence`, không dàn trải quá rộng.

## 9) Thông điệp trả lời hội đồng (ngắn gọn)
> Nhóm không tuyên bố tự huấn luyện model nền hay đã production hóa toàn bộ stack dữ liệu lớn.  
> Nhóm làm chủ phần cốt lõi đã chạy được: safety policy, legal guard, consent gate, DDI fallback, retrieval có attribution và kiến trúc runtime control.  
> Các thành phần nâng cao như parse sâu đa định dạng và vector/graph retrieval production là lộ trình mở rộng sau cuộc thi, đã có hạ tầng chuẩn bị và kế hoạch kỹ thuật cụ thể.
