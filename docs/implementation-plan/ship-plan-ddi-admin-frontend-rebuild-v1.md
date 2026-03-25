# Ship Plan v1: DDI chuẩn hóa + Admin Dashboard + Frontend Rebuild

## 1. Scope giao bản ship hiện tại
- Nâng cấp `DDI engine` từ local-rule sang `hybrid source` (RxNorm/openFDA + fallback deterministic).
- Tạo `Admin Dashboard` riêng biệt để quản trị RAG sources, answer flow, quan sát hệ thống.
- Rebuild hoàn toàn frontend web theo phong cách `modern, future-med, simple`, bao gồm landing chuẩn chạy ads.
- Rà soát docs-vs-implementation và đóng gap mức P0/P1 trước.

## 2. Deliverables kỹ thuật
### 2.1 Backend DDI
- Chuẩn hóa input thuốc -> canonical name / RxCUI candidates.
- Query tương tác từ nguồn chuẩn (ưu tiên RxNorm interaction APIs).
- Bổ sung evidence từ openFDA label/event để enrich cảnh báo.
- Merge + dedupe + severity mapping:
  - `critical/high/medium/low`
- Fallback policy:
  - nếu nguồn ngoài lỗi -> dùng local rules để không rỗng kết quả.
- Metadata bắt buộc:
  - `sources_used`, `source_errors`, `fallback_used`, `latency_ms`.

### 2.2 Admin Dashboard (Control Tower)
- Namespace route riêng: `/admin/*`.
- Pages:
  - `/admin/overview`
  - `/admin/rag-sources`
  - `/admin/answer-flow`
  - `/admin/observability`
- Chức năng:
  - Bật/tắt nguồn RAG, chỉnh priority/category.
  - Điều chỉnh answer flow flags (role router, intent router, verifier, fallback).
  - Xem trạng thái nguồn + error snapshot + health cards.

### 2.3 Frontend Rebuild
- Landing page đầy đủ funnel:
  - Hero + USP
  - Feature sections
  - Social proof placeholders
  - CTA blocks
  - FAQ cơ bản
  - Footer legal/contact
- Chat UI theo pattern Perplexity/Gemini:
  - input trung tâm
  - suggestion chips
  - answer area sạch + source cards
- SelfMed module rõ ràng:
  - tủ thuốc permanent
  - scan OCR hoá đơn/toa thuốc
  - auto DDI check + hành động khuyến nghị

## 3. QA/Validation gates
- `npm run build` pass cho web.
- API compile/test smoke pass.
- Smoke flow end-to-end:
  - đăng nhập -> thêm thuốc -> scan OCR -> auto DDI -> xem admin flags.

## 4. Docs alignment checklist (bắt buộc)
- [ ] Intent router 2 lớp được thể hiện đúng trong runtime flow.
- [ ] SelfMed là module riêng, dữ liệu permanent ngoài session.
- [ ] Fallback khi thiếu RAG không trả lời rỗng.
- [ ] Admin dashboard có chỉnh RAG source + answer flow.
- [ ] Plan có route Flutter Android rõ ràng.

## 5. Rollout
1. Merge backend DDI + tests.
2. Merge admin dashboard pages.
3. Merge frontend rebuild pages.
4. Chạy QA checklist.
5. Deploy.
