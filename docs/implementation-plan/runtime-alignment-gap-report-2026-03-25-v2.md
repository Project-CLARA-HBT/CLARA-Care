# Runtime Alignment Gap Report v2 (2026-03-25)

## 1) Kết luận nhanh
- Trạng thái tổng thể: **đạt một phần**.
- Đã có tiến triển lớn ở `SelfMed permanent`, `OCR import`, `DDI check`, `Admin dashboard riêng`.
- Chưa đạt đầy đủ ở `2-layer intent taxonomy theo docs`, `verification/policy gate end-to-end`, `family dashboard + reminder/escalation`, `Flutter route/deep-link đầy đủ`.

## 2) Các mục đã đóng trong vòng cập nhật này
- [x] Nâng cấp DDI sang nguồn chuẩn theo mô hình hybrid:
  - RxNorm/RxNav interaction lookup.
  - openFDA label/event evidence enrichment.
  - fallback local deterministic rules.
- [x] Thêm metadata DDI runtime: `source_used`, `source_errors`, `fallback_used`.
- [x] Thêm Admin dashboard riêng biệt `/admin/*`:
  - overview, rag-sources, answer-flow, observability.
- [x] Rebuild landing + research UI theo phong cách modern/future-med, đơn giản cho người mới.
- [x] Đồng bộ OCR strategy: dùng key/provider từ `tgc-transhub`, CLARA gọi service OCR nội bộ.

## 3) Gap còn mở (ưu tiên cao)
1. Router 2 lớp B1/B2 chưa khớp hoàn toàn taxonomy trong docs runtime.
2. Verification + policy gate chưa thành chuỗi cứng `route->retrieve->synthesize->verify->policy->respond`.
3. Family dashboard/reminder/escalation flow chưa hoàn chỉnh trong web/mobile.
4. Scan job lifecycle cho SelfMed (`queued/processing/review/completed/failed`) chưa đầy đủ.
5. Flutter route map chưa đủ named routes + deep-link + guard theo tài liệu.
6. Control-plane modules chưa đủ: incidents/audit/compliance/cost/IAM tenant.
7. Config control tower chưa tác động đầy đủ tới mọi luồng runtime ML (mới tác động một phần).

## 4) Kế hoạch đóng gap theo wave
### Wave 1 (ngay sau bản này)
- Chuẩn hóa role-intent taxonomy theo docs.
- Bổ sung verification contract + policy action (`allow/warn/block/escalate`).
- Tạo scan-job lifecycle API + model + UI state.

### Wave 2
- Family dashboard + reminder scheduling + escalation engine.
- Flutter Android route map theo đúng spec (deep-link/state restore).

### Wave 3
- Mở rộng admin control-plane modules: incident center, audit explorer, compliance board, cost board.

## 5) Checklist đối chiếu yêu cầu docs
- [~] Multi AI agents: có (đang dùng), cần chuẩn hóa orchestration policy sâu hơn.
- [~] Multimodal RAG: có phần nền, cần hoàn thiện verifier/policy chain.
- [x] SelfMed là module riêng và dữ liệu permanent.
- [~] DDI chuẩn nguồn: đã có hybrid, cần tuning severity mapping clinical-grade.
- [~] Admin dashboard riêng kiểu control tower: đã có bản v1, cần thêm module governance.
- [~] Frontend hiện đại + landing ads-ready: đã rebuild v1, tiếp tục tinh chỉnh conversion copy.
