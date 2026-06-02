# Citation 19: ADE (Agentic Document Extraction) trong CLARA-Care

## Định danh
- Loại: Kiến trúc nội bộ (implementation citation)
- Nguồn code chính:
  - `services/api/src/clara_api/api/v1/endpoints/research.py`
  - `services/ml/src/clara_ml/agents/research_tier2.py`
  - `services/ml/src/clara_ml/rag/retrieval/source_router.py`
  - `services/ml/src/clara_ml/rag/retrieval/document_builder.py`
  - `apps/web/lib/research.ts`
- Ngày xác minh: 2026-04-10

## Trích dẫn kỹ thuật (implementation evidence)
CLARA triển khai ADE theo luồng nhiều tác tử chức năng: upload an toàn -> trích xuất nội dung theo loại file -> chuẩn hóa và đóng gói thành `uploaded_documents` -> định tuyến `file-grounded` khi có ngữ cảnh tài liệu -> hợp nhất vào retrieval pipeline và sinh citation/trace ở output.

## Bằng chứng runtime trong code
- Tầng API:
  - Kiểm tra an toàn file, giới hạn kích thước, whitelist định dạng (`_validate_upload_safety`).
  - Trích xuất text PDF qua `pypdf`, ảnh qua OCR + metadata (`_extract_pdf_text`, `_extract_image_text_with_ocr`, `_extract_basic_text`).
  - Lưu cache upload tạm thời và chuyển thành `uploaded_file_ids`/`uploaded_documents`.
  - Endpoint chính: `/api/v1/research/upload-file`, `/api/v1/research/tier2`.
- Tầng ML:
  - Nhận `uploaded_documents` trong payload tier2.
  - Source router ưu tiên route `file-grounded` khi có tài liệu upload và policy cho phép.
  - Document builder chuẩn hóa tài liệu upload thành `Document` retrieval-ready.
  - Citation builder gắn thêm nguồn từ uploaded documents vào kết quả cuối.
- Tầng Web:
  - Hỗ trợ upload đa file, quản lý `uploaded_file_ids`, truyền vào tier2 request.
  - Hiển thị danh sách file đã upload và trạng thái lỗi upload.

## Hàm ý kỹ thuật cho báo cáo
ADE là điểm khác biệt quan trọng của CLARA vì cho phép nghiên cứu dựa trên ngữ cảnh tài liệu người dùng cung cấp (file-grounded research), thay vì chỉ phụ thuộc nguồn chung. Điều này tăng khả năng cá thể hóa theo tình huống thực tế, đồng thời vẫn giữ được traceability qua metadata/citation payload.

## KPI khuyến nghị
- `upload_success_rate`
- `extraction_success_rate` theo loại file (text/pdf/image)
- `file_grounded_route_rate`
- `uploaded_context_citation_rate`
- `latency_p95` cho luồng có upload tài liệu
