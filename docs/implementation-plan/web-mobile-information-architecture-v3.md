# Web + Mobile Information Architecture V3 (CLARA)

Phiên bản: 3.0  
Ngày cập nhật: 2026-03-25  
Phạm vi: Web app + Flutter Android app

## 1. Mục tiêu IA

- Chuẩn hóa cấu trúc thông tin và điều hướng cho CLARA trên web và mobile.
- Giữ naming route đồng nhất `kebab-case` cho tất cả path segment và param.
- Bao phủ đầy đủ các nhóm trang bắt buộc:
  - landing page,
  - onboarding,
  - auth full flow,
  - chat kiểu Perplexity/Gemini,
  - module Self-Med tách riêng với `cabinet` luôn hiện diện,
  - OCR upload,
  - DDI,
  - dashboard kiểu Dify (RAG source + flow config),
  - admin operations.

## 2. Quy ước route chuẩn

- Dùng chữ thường + `kebab-case`: ví dụ `rag-sources`, `flow-config`.
- Param path dùng `:kebab-case-id`: ví dụ `:thread-id`, `:scan-job-id`, `:ddi-check-id`.
- Prefix theo miền chức năng:
  - web authenticated: `/app/...`
  - web admin ops: `/ops/...`
  - flutter mobile: `/m/...`
- Không trộn camelCase/snake_case trong route.

## 3. IA tổng thể theo domain

1. Public Marketing + Entry
2. Onboarding
3. Authentication + Session Security
4. Core App Shell
5. Chat AI Workspace (Perplexity/Gemini style)
6. Self-Med Workspace (cabinet permanent)
7. Dashboard & Builder (Dify-like RAG + Flow)
8. Admin Operations

## 4. Web IA và route map

### 4.1 Public + Landing

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/` | Landing | Giới thiệu giá trị CLARA, CTA bắt đầu | public |
| `/features` | Tính năng | So sánh module chat/self-med/dashboard | public |
| `/pricing` | Gói dịch vụ | Minh bạch plan cho user/team | public |
| `/help-center` | Trung tâm trợ giúp | FAQ + hướng dẫn | public |
| `/contact` | Liên hệ | Sales/support entry | public |

### 4.2 Onboarding

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/onboarding/welcome` | Chào mừng | Chọn mục tiêu sử dụng | public/logged-out |
| `/onboarding/use-case` | Use case | Chọn nhánh: cá nhân, gia đình, nghiên cứu, phòng khám | public/logged-out |
| `/onboarding/profile-setup` | Khởi tạo hồ sơ | Thiết lập hồ sơ cơ bản | public/logged-out |
| `/onboarding/permissions` | Quyền truy cập | Camera/file/notification consent | public/logged-out |
| `/onboarding/preview` | Xem trước trải nghiệm | Demo nhanh trước khi đăng ký | public/logged-out |

### 4.3 Auth full flow

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/auth/login` | Đăng nhập | Email/phone + password/passkey | public |
| `/auth/register` | Đăng ký | Tạo tài khoản mới | public |
| `/auth/verify-otp` | Xác thực OTP | Verify phone/email | public |
| `/auth/forgot-password` | Quên mật khẩu | Yêu cầu reset | public |
| `/auth/reset-password` | Đặt lại mật khẩu | Đổi mật khẩu qua token | public |
| `/auth/two-factor` | 2FA challenge | OTP/TOTP khi risk cao | semi-auth |
| `/auth/consent-medical-data` | Đồng ý dữ liệu y tế | Consent bắt buộc trước dùng tính năng y tế | logged-in |
| `/auth/role-select` | Chọn vai trò | `normal`, `researcher`, `doctor`, `admin-ops` | logged-in |
| `/auth/session-expired` | Phiên hết hạn | Re-auth với context giữ nguyên | public |

### 4.4 Core app shell

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/app` | App root | Redirect theo role + trạng thái onboarding | logged-in |
| `/app/home` | Home | Snapshot hoạt động và shortcut | logged-in |
| `/app/alerts` | Alerts center | Task an toàn thuốc và nhắc xử lý | logged-in |
| `/app/profile` | Hồ sơ | Hồ sơ cá nhân, bảo mật, thiết bị | logged-in |
| `/app/settings` | Cài đặt | Notification, language, data export | logged-in |

### 4.5 Chat workspace (Perplexity/Gemini style)

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/app/chat` | Chat home | Danh sách thread + đề xuất prompt | `chat-access` |
| `/app/chat/new` | New thread | Khởi tạo câu hỏi mới | `chat-access` |
| `/app/chat/thread/:thread-id` | Thread streaming | Trả lời streaming + follow-up inline | `chat-access` |
| `/app/chat/thread/:thread-id/citations` | Citation panel | Nguồn tham chiếu + độ tin cậy | `chat-access` |
| `/app/chat/thread/:thread-id/sources` | Source focus | Lọc kết quả theo nguồn/tài liệu | `chat-access` |
| `/app/chat/thread/:thread-id/artifacts` | Artifacts | Bảng/tóm tắt/câu trả lời đã ghim | `chat-access` |
| `/app/chat/thread/:thread-id/export` | Export | Xuất PDF/Markdown/JSON | `chat-access` |
| `/app/chat/history` | Lịch sử chat | Tìm kiếm và pin thread | `chat-access` |
| `/app/chat/templates` | Prompt templates | Mẫu hỏi theo use case | `chat-access` |

### 4.6 Self-Med module (cabinet permanent)

Ghi chú IA: trong toàn bộ nhánh `/app/self-med/*`, thanh điều hướng trái hoặc tab đầu tiên luôn giữ `cabinet` là mục mặc định/persistent.

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/app/self-med` | Self-Med root | Redirect cố định về cabinet | `self-med-access` |
| `/app/self-med/cabinet` | Cabinet list | Danh sách thuốc hiện có theo thành viên | `self-med-access` |
| `/app/self-med/cabinet/item/:cabinet-item-id` | Cabinet item detail | Liều dùng, hạn dùng, lịch sử | `self-med-access` |
| `/app/self-med/cabinet/add-manual` | Add manual | Thêm thuốc thủ công | `self-med-access` |
| `/app/self-med/cabinet/import-from-ocr/:scan-job-id` | Import từ OCR | Xác nhận thêm thuốc từ OCR | `self-med-access` |
| `/app/self-med/intake-schedule` | Lịch dùng thuốc | Lịch uống theo ngày/tuần | `self-med-access` |
| `/app/self-med/refill-center` | Refill center | Theo dõi sắp hết thuốc | `self-med-access` |
| `/app/self-med/expiry-center` | Expiry center | Thuốc sắp hết hạn/hết hạn | `self-med-access` |
| `/app/self-med/family-profiles` | Family profiles | Hồ sơ dị ứng/bệnh nền theo thành viên | `self-med-access` |

### 4.7 OCR upload pages

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/app/self-med/ocr-upload` | Upload entry | Chọn camera/file upload | `self-med-access` |
| `/app/self-med/ocr-upload/camera` | Camera capture | Chụp đơn thuốc/hóa đơn | `self-med-access` |
| `/app/self-med/ocr-upload/file` | File picker | Upload PDF/ảnh | `self-med-access` |
| `/app/self-med/ocr-upload/processing/:scan-job-id` | Processing | Tiến trình OCR/ADE | `self-med-access` |
| `/app/self-med/ocr-upload/review/:scan-job-id` | Review low confidence | Người dùng xác nhận thực thể nhận diện | `self-med-access` |
| `/app/self-med/ocr-upload/recognition/:scan-job-id` | Drug recognition | Map tên thuốc -> hoạt chất/RxCUI | `self-med-access` |
| `/app/self-med/ocr-upload/finalize/:scan-job-id` | Finalize import | Chốt danh sách thêm vào cabinet | `self-med-access` |
| `/app/self-med/ocr-upload/error/:scan-job-id` | Error + retry | Xử lý lỗi OCR/ADE | `self-med-access` |

### 4.8 DDI pages

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/app/self-med/ddi/check` | DDI check entry | Chạy kiểm tra tương tác thủ công | `self-med-access` |
| `/app/self-med/ddi/result/:ddi-check-id` | DDI result | Kết quả `allow/warn/block/escalate` | `self-med-access` |
| `/app/self-med/ddi/history` | DDI history | Lịch sử lần kiểm tra | `self-med-access` |
| `/app/self-med/ddi/rule-detail/:rule-id` | Rule detail | Giải thích guideline/rule áp dụng | `self-med-access` |
| `/app/self-med/ddi/escalation/:alert-id` | Escalation | Chuyển tuyến bác sĩ/chuyên gia | `self-med-access` |

### 4.9 Dashboard & Builder (Dify-like RAG source + flow config)

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/app/dashboard` | Dashboard root | Redirect về overview theo role | logged-in |
| `/app/dashboard/overview` | Overview | KPI sử dụng, cảnh báo, SLA cá nhân/team | logged-in |
| `/app/dashboard/rag-sources` | RAG source list | Danh sách nguồn dữ liệu tri thức | `builder-access` |
| `/app/dashboard/rag-sources/new` | Add source | Kết nối file, URL, cloud storage | `builder-access` |
| `/app/dashboard/rag-sources/:source-id` | Source detail | Trạng thái indexing/chunking/sync | `builder-access` |
| `/app/dashboard/rag-sources/:source-id/sync-history` | Sync history | Lịch sử đồng bộ và lỗi ingest | `builder-access` |
| `/app/dashboard/knowledge-chunks` | Chunk explorer | Kiểm tra chunk + metadata + embeddings health | `builder-access` |
| `/app/dashboard/flow-config` | Flow list | Danh sách workflow hỏi đáp | `builder-access` |
| `/app/dashboard/flow-config/new` | New flow | Tạo flow mới | `builder-access` |
| `/app/dashboard/flow-config/:flow-id` | Flow editor | Cấu hình node, router, guardrail | `builder-access` |
| `/app/dashboard/flow-config/:flow-id/test-run` | Test run | Chạy thử với trace/debug | `builder-access` |
| `/app/dashboard/flow-config/:flow-id/version-history` | Version history | So sánh version và rollback | `builder-access` |
| `/app/dashboard/evaluations` | Eval center | Bộ test, accuracy, hallucination checks | `builder-access` |
| `/app/dashboard/cost-latency` | Cost & latency | Theo dõi token cost, p95 latency | `builder-access` |

### 4.10 Admin ops pages

| Route | Trang | Mục tiêu | Guard |
|---|---|---|---|
| `/ops` | Ops home | Điều hướng nhanh tới vận hành trọng yếu | `admin-ops` |
| `/ops/health` | System health | Uptime, service heartbeat | `admin-ops` |
| `/ops/queues` | Queue monitor | OCR, DDI, ingest queue depth | `admin-ops` |
| `/ops/model-routing` | Model routing | Theo dõi route Perplexity/Gemini/LLM adapter | `admin-ops` |
| `/ops/ocr-quality` | OCR quality | Confidence bands, manual review rate | `admin-ops` |
| `/ops/ddi-safety` | DDI safety | Critical alert trend, sensitivity | `admin-ops` |
| `/ops/policy-registry` | Policy registry | Rule/prompt/model policy release | `admin-ops` |
| `/ops/audit-logs` | Audit logs | Truy vết hành động và quyết định tự động | `admin-ops` |
| `/ops/incidents` | Incident center | Triage, timeline, postmortem | `admin-ops` |
| `/ops/user-access` | Access control | RBAC/ABAC và review quyền | `admin-ops` |
| `/ops/feature-flags` | Feature flags | Bật/tắt tính năng theo cohort | `admin-ops` |
| `/ops/runbooks` | Runbooks | SOP sự cố và playbook | `admin-ops` |

## 5. Flutter Android IA và route map

Ghi chú: dùng prefix `/m` cho deep link mobile; mọi route giữ chuẩn `kebab-case`.

### 5.1 Public + onboarding + auth

| Flutter route | Màn hình | Guard |
|---|---|---|
| `/m/splash` | Splash + bootstrap config | public |
| `/m/landing` | Landing mobile | public |
| `/m/onboarding/welcome` | Onboarding bước 1 | public |
| `/m/onboarding/use-case` | Onboarding bước 2 | public |
| `/m/onboarding/profile-setup` | Onboarding bước 3 | public |
| `/m/onboarding/permissions` | Onboarding bước 4 | public |
| `/m/auth/login` | Login | public |
| `/m/auth/register` | Register | public |
| `/m/auth/verify-otp` | OTP verify | public |
| `/m/auth/forgot-password` | Forgot password | public |
| `/m/auth/reset-password` | Reset password | public |
| `/m/auth/two-factor` | 2FA challenge | semi-auth |
| `/m/auth/consent-medical-data` | Consent dữ liệu | logged-in |
| `/m/auth/role-select` | Role select | logged-in |

### 5.2 Mobile app shell

| Flutter route | Màn hình | Guard |
|---|---|---|
| `/m/app` | Shell root | logged-in |
| `/m/app/home` | Home tab | logged-in |
| `/m/app/chat` | Chat tab | `chat-access` |
| `/m/app/self-med/cabinet` | Self-Med tab mặc định | `self-med-access` |
| `/m/app/dashboard/overview` | Dashboard tab | logged-in |
| `/m/app/profile` | Profile tab | logged-in |
| `/m/app/alerts` | Alerts center | logged-in |

### 5.3 Mobile chat routes

| Flutter route | Màn hình | Guard |
|---|---|---|
| `/m/app/chat/new` | New prompt | `chat-access` |
| `/m/app/chat/thread/:thread-id` | Thread streaming | `chat-access` |
| `/m/app/chat/thread/:thread-id/citations` | Citation bottom sheet/full page | `chat-access` |
| `/m/app/chat/thread/:thread-id/sources` | Nguồn dữ liệu | `chat-access` |
| `/m/app/chat/history` | Lịch sử chat | `chat-access` |
| `/m/app/chat/templates` | Prompt templates | `chat-access` |

### 5.4 Mobile self-med + OCR + DDI

| Flutter route | Màn hình | Guard |
|---|---|---|
| `/m/app/self-med/cabinet` | Cabinet list | `self-med-access` |
| `/m/app/self-med/cabinet/item/:cabinet-item-id` | Cabinet item detail | `self-med-access` |
| `/m/app/self-med/cabinet/add-manual` | Add manual | `self-med-access` |
| `/m/app/self-med/ocr-upload` | Upload entry | `self-med-access` |
| `/m/app/self-med/ocr-upload/camera` | Camera scan | `self-med-access` |
| `/m/app/self-med/ocr-upload/file` | File upload | `self-med-access` |
| `/m/app/self-med/ocr-upload/processing/:scan-job-id` | OCR processing | `self-med-access` |
| `/m/app/self-med/ocr-upload/review/:scan-job-id` | Review | `self-med-access` |
| `/m/app/self-med/ocr-upload/recognition/:scan-job-id` | Drug recognition | `self-med-access` |
| `/m/app/self-med/ocr-upload/finalize/:scan-job-id` | Finalize import | `self-med-access` |
| `/m/app/self-med/ddi/check` | DDI check | `self-med-access` |
| `/m/app/self-med/ddi/result/:ddi-check-id` | DDI result | `self-med-access` |
| `/m/app/self-med/ddi/history` | DDI history | `self-med-access` |
| `/m/app/self-med/ddi/escalation/:alert-id` | Escalation | `self-med-access` |

### 5.5 Mobile dashboard builder-lite + admin-lite

| Flutter route | Màn hình | Guard |
|---|---|---|
| `/m/app/dashboard/overview` | KPI tổng quan | logged-in |
| `/m/app/dashboard/rag-sources` | Danh sách source (lite) | `builder-access` |
| `/m/app/dashboard/rag-sources/:source-id` | Source detail (lite) | `builder-access` |
| `/m/app/dashboard/flow-config` | Danh sách flow (lite) | `builder-access` |
| `/m/app/dashboard/flow-config/:flow-id` | Flow detail (lite) | `builder-access` |
| `/m/app/dashboard/evaluations` | Eval snapshot | `builder-access` |
| `/m/ops/health` | Ops health (lite) | `admin-ops` |
| `/m/ops/incidents` | Incident list (lite) | `admin-ops` |
| `/m/ops/audit-logs` | Audit log (lite) | `admin-ops` |

## 6. Key state transition flows

### 6.1 Funnel A: Landing -> onboarding -> auth -> first value

| State hiện tại | Sự kiện | State kế tiếp | Route đích |
|---|---|---|---|
| `landing-view` | click `bat-dau` | `onboarding-welcome` | `/onboarding/welcome` |
| `onboarding-welcome` | submit use-case | `onboarding-use-case` | `/onboarding/use-case` |
| `onboarding-use-case` | continue | `onboarding-profile-setup` | `/onboarding/profile-setup` |
| `onboarding-profile-setup` | continue | `onboarding-permissions` | `/onboarding/permissions` |
| `onboarding-permissions` | complete | `auth-register-or-login` | `/auth/register` hoặc `/auth/login` |
| `auth-register-or-login` | auth success | `consent-pending` | `/auth/consent-medical-data` |
| `consent-pending` | consent accepted | `role-select` | `/auth/role-select` |
| `role-select` | role confirmed | `first-value-ready` | `/app/chat/new` hoặc `/app/self-med/cabinet` |

### 6.2 Funnel B: Auth full flow + session recovery

| State hiện tại | Sự kiện | State kế tiếp | Route đích |
|---|---|---|---|
| `login-form` | submit valid creds | `two-factor-check` | `/auth/two-factor` (nếu yêu cầu) |
| `login-form` | click forgot-password | `forgot-password` | `/auth/forgot-password` |
| `forgot-password` | reset link valid | `reset-password` | `/auth/reset-password` |
| `reset-password` | reset success | `login-form` | `/auth/login` |
| `two-factor-check` | otp pass | `auth-complete` | `/auth/consent-medical-data` hoặc `/app/home` |
| `session-active` | token expired | `session-expired` | `/auth/session-expired` |
| `session-expired` | re-auth success | `resume-context` | route trước đó được restore |

### 6.3 Funnel C: Chat thread kiểu Perplexity/Gemini

| State hiện tại | Sự kiện | State kế tiếp | Route đích |
|---|---|---|---|
| `chat-home` | click new-thread | `prompt-compose` | `/app/chat/new` |
| `prompt-compose` | submit prompt | `thread-streaming` | `/app/chat/thread/:thread-id` |
| `thread-streaming` | open citations | `citation-inspect` | `/app/chat/thread/:thread-id/citations` |
| `thread-streaming` | open sources | `source-inspect` | `/app/chat/thread/:thread-id/sources` |
| `thread-streaming` | follow-up question | `thread-streaming` | `/app/chat/thread/:thread-id` |
| `thread-streaming` | export | `thread-export` | `/app/chat/thread/:thread-id/export` |

### 6.4 Funnel D: OCR upload -> cabinet -> DDI auto-check

| State hiện tại | Sự kiện | State kế tiếp | Route đích |
|---|---|---|---|
| `cabinet-view` | click scan/upload | `ocr-upload-entry` | `/app/self-med/ocr-upload` |
| `ocr-upload-entry` | submit image/file | `ocr-processing` | `/app/self-med/ocr-upload/processing/:scan-job-id` |
| `ocr-processing` | confidence high | `recognition-auto` | `/app/self-med/ocr-upload/recognition/:scan-job-id` |
| `ocr-processing` | confidence low | `recognition-review` | `/app/self-med/ocr-upload/review/:scan-job-id` |
| `recognition-auto` | finalize import | `cabinet-imported` | `/app/self-med/cabinet/import-from-ocr/:scan-job-id` |
| `recognition-review` | user confirm | `cabinet-imported` | `/app/self-med/cabinet/import-from-ocr/:scan-job-id` |
| `cabinet-imported` | auto ddi start | `ddi-processing` | `/app/self-med/ddi/check` |
| `ddi-processing` | result ready | `ddi-result` | `/app/self-med/ddi/result/:ddi-check-id` |
| `ddi-result` | severity warn/block/escalate | `alert-created` | `/app/self-med/ddi/escalation/:alert-id` |
| `ddi-result` | severity allow | `cabinet-stable` | `/app/self-med/cabinet` |

### 6.5 Funnel E: RAG source ingest + flow config publish

| State hiện tại | Sự kiện | State kế tiếp | Route đích |
|---|---|---|---|
| `dashboard-overview` | open rag sources | `rag-source-list` | `/app/dashboard/rag-sources` |
| `rag-source-list` | click add source | `rag-source-create` | `/app/dashboard/rag-sources/new` |
| `rag-source-create` | create success | `rag-source-detail` | `/app/dashboard/rag-sources/:source-id` |
| `rag-source-detail` | indexing complete | `rag-source-ready` | `/app/dashboard/rag-sources/:source-id` |
| `rag-source-ready` | open flow config | `flow-list` | `/app/dashboard/flow-config` |
| `flow-list` | create new flow | `flow-editing` | `/app/dashboard/flow-config/new` |
| `flow-editing` | save version | `flow-versioned` | `/app/dashboard/flow-config/:flow-id/version-history` |
| `flow-versioned` | run test | `flow-test-run` | `/app/dashboard/flow-config/:flow-id/test-run` |
| `flow-test-run` | test pass + publish | `flow-live` | `/app/dashboard/flow-config/:flow-id` |

### 6.6 Funnel F: Admin ops incident triage

| State hiện tại | Sự kiện | State kế tiếp | Route đích |
|---|---|---|---|
| `ops-home` | alert critical | `incident-open` | `/ops/incidents` |
| `incident-open` | assign owner | `incident-investigating` | `/ops/incidents` |
| `incident-investigating` | need evidence | `audit-inspect` | `/ops/audit-logs` |
| `incident-investigating` | need system check | `health-inspect` | `/ops/health` |
| `incident-investigating` | mitigation ready | `incident-mitigated` | `/ops/feature-flags` hoặc `/ops/policy-registry` |
| `incident-mitigated` | postmortem complete | `incident-closed` | `/ops/runbooks` |

## 7. Điều hướng chính đề xuất

- Web global nav (logged-in): `home`, `chat`, `self-med`, `dashboard`, `alerts`.
- Self-Med local nav cố định: `cabinet`, `ocr-upload`, `ddi`, `intake-schedule`, `expiry-center`, `family-profiles`.
- Flutter bottom nav: `home`, `chat`, `self-med`, `dashboard`, `profile`.
- Admin nav: `health`, `queues`, `model-routing`, `ocr-quality`, `ddi-safety`, `incidents`, `audit-logs`.

## 8. Checkpoint triển khai

- Route map web và flutter đã tách riêng, đồng nhất `kebab-case`.
- Bao phủ đầy đủ nhóm trang bắt buộc theo yêu cầu micro-task.
- Có state transition rõ cho các funnel trọng yếu từ entry đến hành động cuối.
