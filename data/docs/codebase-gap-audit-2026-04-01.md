# CLARA Codebase Gap Audit (2026-04-01)

## Phạm vi rà soát
- API (`services/api`)
- ML (`services/ml`)
- Web/Mobile (`apps/web`, `apps/mobile`)

## Các điểm chưa chỉn chu đã hoàn thiện trong đợt này
1. Research upload còn placeholder parse file
- Trước: PDF/image trả text placeholder kiểu "chưa hỗ trợ parse sâu".
- Sau: parse text thực cho text/json/markdown; PDF parse basic qua `pypdf` (fail-safe); image có metadata parse và OCR nội bộ (bật bằng `RESEARCH_UPLOAD_IMAGE_OCR`).
- File: `services/api/src/clara_api/api/v1/endpoints/research.py`

2. Rate limiting thiếu production hardening
- Trước: in-memory limiter tối giản, chưa proxy-aware, không cleanup bucket cũ.
- Sau: thêm lock thread-safe, hỗ trợ `X-Forwarded-For`/`Forwarded` có trust policy, cleanup bucket stale, trả `Retry-After`.
- File: `services/api/src/clara_api/core/rate_limit.py`

3. DB session có nguy cơ fallback SQLite âm thầm
- Trước: primary DB lỗi thì fallback SQLite mặc định.
- Sau: production không cho fallback âm thầm; chỉ fallback khi bật explicit gate (`DATABASE_FALLBACK_ENABLED=true`), có kiểm tra fallback URL/health.
- File: `services/api/src/clara_api/db/session.py`

4. Test coverage cho các nhánh mới còn thiếu
- Đã bổ sung test cho upload JSON/PDF/image OCR và fallback DB/rate-limit policy.
- Files:
  - `services/api/tests/test_p2_proxy_endpoints.py`
  - `services/api/tests/test_system_endpoints.py`

5. Wording/mô tả còn “skeleton” sai hiện trạng
- Đã dọn wording ở API/ML/Web/Mobile docs và metadata cảnh báo tiếng Việt.
- Files:
  - `services/api/README.md`, `services/api/pyproject.toml`
  - `services/ml/README.md`, `services/ml/pyproject.toml`
  - `apps/web/README.md`, `apps/mobile/README.md`, `apps/mobile/pubspec.yaml`
  - `services/ml/src/clara_ml/main.py`
  - `services/ml/src/clara_ml/agents/scribe_soap.py`
  - `services/ml/src/clara_ml/agents/langgraph_workflow.py`

6. Component web rời rạc không dùng
- Đã xoá `apps/web/components/page-skeleton.tsx` (không còn import).

## Các điểm chưa đầy đủ còn lại (backlog ưu tiên)
1. Retrieval embedding vẫn có lớp `BgeM3EmbedderStub`
- File: `services/ml/src/clara_ml/rag/embedder.py`
- Tác động: khi upstream embedding lỗi, quality retrieval giảm.

2. LangGraph workflow vẫn là stub node (`_retrieve_stub`, `_generate_stub`)
- File: `services/ml/src/clara_ml/agents/langgraph_workflow.py`
- Tác động: pipeline graph fallback chưa phản ánh đầy đủ Agentic RAG chain production.

3. WebSocket streaming mô tả/luồng còn mức cơ bản
- File: `services/ml/src/clara_ml/streaming/ws.py`
- Tác động: chưa có backpressure/ack cơ chế nâng cao.

4. Bộ lint toàn cục hiện vẫn nhiều lỗi lịch sử (B008/I001/E501) ngoài phạm vi đợt fix
- Tác động: CI lint toàn phần vẫn khó bật strict blocking ngay.
- Đề xuất: áp dụng incremental lint policy theo changed-files.

## Kết quả xác minh nhanh
- API targeted tests: pass
  - `services/api/tests/test_p2_proxy_endpoints.py`
  - `services/api/tests/test_system_endpoints.py` (nhóm test rate-limit + db-fallback)
- ML targeted tests: pass
  - `services/ml/tests/test_main_api.py`
  - `services/ml/tests/test_rag_pipeline.py`
- Web lint + build: pass
  - `apps/web` (`npm run lint`, `npm run build`)
