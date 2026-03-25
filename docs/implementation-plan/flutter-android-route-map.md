# Route Map Flutter Android-First (CLARA)

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-24

## 1. Audit hiện trạng tài liệu

### 1.1 File đã có

- `frontend-web-mobile-flutter-plan.md`: có phạm vi màn hình và roadmap, chưa có route map chi tiết theo màn hình Flutter.
- `web-sitemap-v2.md`: có route web mức tổng quát, chưa tách route tree cho Android app shell.
- `workstream-clara-research.md` và `workstream-clara-self-med.md`: có flow nghiệp vụ/kỹ thuật, chưa map thành route điều hướng cụ thể.

### 1.2 Kết luận audit

Hiện tại **chưa có** tài liệu route map Flutter Android-first đầy đủ cho:
- app shell,
- Clara Research,
- Clara Self-Med,
- dashboard người dùng và dashboard vận hành.

Tài liệu này là bản route chuẩn để triển khai Flutter Android trước.

## 2. Nguyên tắc route Android-first

- Đặt route theo domain nghiệp vụ, không đặt theo widget kỹ thuật.
- Dùng route name ngắn, path rõ nghĩa, deep link được.
- App shell thống nhất cho mọi role; quyền quyết định bằng guard.
- Flow có rủi ro thuốc phải có trạng thái trung gian rõ: `processing`, `review`, `confirm`, `blocked/escalate`.
- Route Self-Med bắt buộc log được trace theo `scan_job_id` và `ddi_check_id`.

## 3. Route map tổng thể

### 3.1 Public + Auth

| Route | Mục đích | Guard |
|---|---|---|
| `/splash` | kiểm tra app state, token, config | public |
| `/intro` | onboarding ngắn | public |
| `/auth/login` | đăng nhập | public |
| `/auth/otp` | xác thực OTP | public |
| `/auth/role-select` | chọn role chính | logged-in |
| `/auth/consent` | đồng ý điều khoản dữ liệu y tế | logged-in |

### 3.2 App shell (Flutter)

| Route | Mục đích | Guard |
|---|---|---|
| `/app` | shell root + bottom nav | logged-in |
| `/app/home` | trang tổng quan nhanh theo role | logged-in |
| `/app/research` | entry Clara Research | `role in [normal,researcher,doctor]` |
| `/app/self-med` | entry Clara Self-Med | `role in [normal,doctor]` |
| `/app/dashboard` | dashboard cá nhân/gia đình | logged-in |
| `/app/alerts` | cảnh báo và escalation | logged-in |
| `/app/profile` | hồ sơ và cài đặt | logged-in |

### 3.3 Clara Research routes

| Route | Mục đích | Guard |
|---|---|---|
| `/app/research/query` | nhập câu hỏi nghiên cứu | `research_access` |
| `/app/research/session/:sessionId` | xem kết quả streaming 5-10-20 | `research_access` |
| `/app/research/citations/:sessionId` | explorer nguồn trích dẫn | `research_access` |
| `/app/research/verify/:sessionId` | trạng thái verify/policy action | `research_access` |
| `/app/research/export/:sessionId` | xuất PDF/DOCX/MD | `research_access` |
| `/app/research/history` | lịch sử phiên nghiên cứu | `research_access` |

### 3.4 Clara Self-Med routes

| Route | Mục đích | Guard |
|---|---|---|
| `/app/self-med/cabinet` | tủ thuốc gia đình | `self_med_access` |
| `/app/self-med/scan-invoice` | chụp/chọn hóa đơn, đơn thuốc | `self_med_access` |
| `/app/self-med/scan-processing/:scanJobId` | tiến trình OCR/ADE | `self_med_access` |
| `/app/self-med/scan-review/:scanJobId` | người dùng xác nhận khi confidence thấp | `self_med_access` |
| `/app/self-med/drug-recognition/:scanJobId` | map tên thuốc -> hoạt chất/RxCUI | `self_med_access` |
| `/app/self-med/cabinet/auto-add/:scanJobId` | tự động thêm vào tủ thuốc | `self_med_access` |
| `/app/self-med/ddi/auto-check/:ddiCheckId` | chạy DDI/allergy tự động sau auto-add | `self_med_access` |
| `/app/self-med/ddi/result/:ddiCheckId` | kết quả DDI + hành động | `self_med_access` |
| `/app/self-med/reminder/:memberId` | lịch nhắc thuốc | `self_med_access` |
| `/app/self-med/family` | quản lý thành viên và risk profile | `self_med_access` |
| `/app/self-med/expiry-center` | cảnh báo hết hạn/kiểm kê | `self_med_access` |
| `/app/self-med/escalation/:alertId` | escalation/handoff bác sĩ | `self_med_access` |

### 3.5 Dashboard routes

#### A. Dashboard trong Flutter app (end-user)

| Route | Mục đích | Guard |
|---|---|---|
| `/app/dashboard/overview` | adherence, cảnh báo gần đây, task hôm nay | logged-in |
| `/app/dashboard/family/:memberId` | dashboard theo thành viên | `self_med_access` |
| `/app/dashboard/ddi-trend` | xu hướng DDI cá nhân/gia đình | `self_med_access` |
| `/app/dashboard/research-activity` | phiên research và chất lượng citation | `research_access` |

#### B. Control Tower dashboard (web admin shell)

| Route | Mục đích | Guard |
|---|---|---|
| `/ops` | shell quản trị | `admin_or_ops` |
| `/ops/health` | uptime, queue, connector heartbeat | `admin_or_ops` |
| `/ops/routing` | router confidence + latency | `admin_or_ops` |
| `/ops/self-med-safety` | DDI trend, alert funnel, escalation SLA | `admin_or_ops` |
| `/ops/ocr-ade-quality` | confidence bands, manual review rate | `admin_or_ops` |
| `/ops/policy-release` | policy/model/prompt registry | `admin_or_ops` |
| `/ops/incidents` | sự cố, runbook, audit | `admin_or_ops` |

## 4. Flow bắt buộc Self-Med: scan hóa đơn -> OCR/ADE -> nhận diện thuốc -> auto thêm tủ thuốc -> auto DDI check

### 4.1 Happy path (F-SM-01)

1. User vào `/app/self-med/scan-invoice`, chụp hóa đơn/đơn thuốc.
2. App tạo `scanJobId`, điều hướng `/app/self-med/scan-processing/:scanJobId`.
3. Backend chạy OCR/ADE và trả candidate theo từng thuốc.
4. Nếu confidence đạt ngưỡng auto-accept: điều hướng `/app/self-med/drug-recognition/:scanJobId`.
5. Mapping hoạt chất/RxCUI thành công: gọi auto-add và vào `/app/self-med/cabinet/auto-add/:scanJobId`.
6. Sau khi auto-add thành công, backend tự tạo `ddiCheckId` và điều hướng `/app/self-med/ddi/auto-check/:ddiCheckId`.
7. Trả kết quả tại `/app/self-med/ddi/result/:ddiCheckId` với policy action: `allow`, `warn`, `block`, `escalate`.
8. Nếu `warn/block/escalate`, tạo task tại `/app/alerts` và link ngược `scanJobId` để audit.

### 4.2 Fallback path (F-SM-02)

- Barcode fail -> chuyển OCR/ADE tự động trong cùng `scanJobId`.
- OCR/ADE confidence thấp -> bắt buộc vào `/app/self-med/scan-review/:scanJobId` để xác nhận thủ công.
- Mapping thuốc mơ hồ nhiều khả năng -> giữ trạng thái `pending_confirm`, chưa auto-add.
- DDI engine timeout -> trả `retryable`, giữ thuốc ở trạng thái `added_pending_ddi` và tự retry nền.

### 4.3 Dữ liệu tối thiểu cần trace

- `scan_job_id`, `source_type` (invoice/prescription), `ocr_variant_selected`.
- `ocr_text_score`, `ocr_bbox_score`, `decision_reason`.
- `drug_match_confidence`, `rxcui`, `ingredient_ids`.
- `cabinet_item_id`, `ddi_check_id`, `ddi_severity_max`, `policy_action`.

## 5. Kiến trúc tích hợp OCR/ADE cho CLARA (tham chiếu từ tgc-transhub)

### 5.1 Nguyên tắc áp dụng

- Reuse kiến trúc đã chứng minh hiệu quả, không copy nguyên khối code từ `tgc-transhub`.
- Giữ biên giới rõ giữa Flutter app, Rust gateway, OCR/ADE adapter, DDI engine.
- Mọi quyết định tự động phải có quality gate và fallback an toàn.

### 5.2 Mô hình tích hợp đề xuất

1. Flutter chỉ gửi file scan + metadata, không xử lý OCR trên client.
2. Rust gateway tạo `scanJobId`, đẩy job sang OCR/ADE adapter service.
3. OCR/ADE adapter chạy multi-pass preprocess (ví dụ: `raw`, `gray_contrast`, `upscale`, `binarize`, `median_otsu_layout`) và scoring chọn candidate tốt nhất.
4. Áp ngưỡng quyết định theo `OCR_GCP_MIN_TEXT_SCORE`, `OCR_GCP_MIN_BBOX_SCORE`, `OCR_GCP_EARLY_STOP`.
5. Chuẩn hóa layout: lọc confidence thấp, dedupe overlap, merge line boxes, sort reading order.
6. Trả về contract chuẩn cho CLARA Self-Med: candidate thuốc + confidence + decision reason.
7. Drug resolver map sang hoạt chất/RxCUI -> medication service auto-add -> DDI service auto-check.
8. Dashboard ingest telemetry OCR/ADE và safety events để theo dõi drift/regression.

### 5.3 Contract tích hợp mức hệ thống

- `POST /self-med/scan-jobs`: tạo job scan.
- `GET /self-med/scan-jobs/:scanJobId`: trạng thái `queued|processing|needs_review|recognized|completed|failed`.
- `POST /self-med/scan-jobs/:scanJobId/confirm`: xác nhận thủ công candidate.
- `POST /self-med/cabinet/auto-add`: thêm thuốc tự động từ job đã nhận diện.
- `POST /self-med/ddi/auto-check`: chạy DDI ngay sau auto-add.

### 5.4 Metrics vận hành bắt buộc

- OCR/ADE: confidence distribution, low-confidence rate, manual review rate.
- Recognition: drug match success rate, ambiguous match rate.
- Safety: DDI critical detection sensitivity, alert-to-action latency.
- Stability: retry rate, fallback rate, end-to-end scan-to-ddi duration.

### 5.5 Nguồn tham chiếu kiến trúc từ tgc-transhub

- Nguồn ngoài (repo `tgc-transhub`, không nằm trong repo CLARA): `/Users/nguyennt/Documents/tgc-transhub/...`
- `/Users/nguyennt/Documents/tgc-transhub/docs/technical/ocr-integration.md`: chuẩn hóa OCR output và layout cleanup.
- `/Users/nguyennt/Documents/tgc-transhub/docs/technical/agentic-document-extraction.md`: pipeline ADE theo stage + telemetry.
- `/Users/nguyennt/Documents/tgc-transhub/docs/technical/ade-refactor-plan.md`: tách module preprocess/scoring và early-stop gate.
- `/Users/nguyennt/Documents/tgc-transhub/docs/technical/ocr-layout-tuning.md`: bộ metrics layout và ngưỡng vận hành.
- `/Users/nguyennt/Documents/tgc-transhub/services/api/src/ade/types.rs`, `/Users/nguyennt/Documents/tgc-transhub/services/api/src/ade/preprocess.rs`, `/Users/nguyennt/Documents/tgc-transhub/services/api/src/ade/scoring.rs`: cấu hình `GcpAdeConfig`, multi-pass variants, scoring logic.

## 6. Checklist triển khai route (Android-first)

- Đủ deep link cho tất cả route Self-Med critical.
- Có guard role cho từng route, không lộ màn hình ngoài quyền.
- State restore khi app bị kill ở `scan-processing`.
- Retry UI rõ ràng cho `processing timeout` và `retryable DDI`.
- Event analytics thống nhất key theo mục 4.3.
