# Kế Hoạch Tính Năng Và Lộ Trình Triển Khai (Research + Self-Med + Control Tower)

Phiên bản: 1.1  
Ngày cập nhật: 2026-03-24

## 1. Nguyên tắc roadmap

- Một kiến trúc lõi, hai nhánh sản phẩm và một lớp điều hành hệ thống.
- Ưu tiên tính năng giảm rủi ro y khoa trước tính năng tăng trưởng.
- Mọi feature mới phải có KPI, quality gate và tiêu chí rollback.
- Dùng LangChain/LangGraph cho orchestration AI flows; backend Rust ưu tiên cho runtime/control-plane.

## 2. Trụ cột sản phẩm

- **CLARA Research**: workflow bằng chứng 5-10-20.
- **CLARA Self-Med**: quản lý thuốc gia đình, DDI, nhắc lịch, cảnh báo.
- **CLARA Control Tower**: dashboard quản trị toàn bộ hệ thống.

## 3. Roadmap phase P0 -> P6 (tổng hợp)

| Phase | CLARA Research | CLARA Self-Med | CLARA Control Tower | Hạ tầng chung |
|---|---|---|---|---|
| P0 | Router 2 lớp nền, retrieval cơ bản | Số hóa tủ thuốc nền | Dashboard khung: IAM + KPI nền + health check | Rust API skeleton, auth, observability |
| P1 | Citation + verifier nền + export cơ bản | Nhắc lịch + DDI + dị ứng cơ bản | Policy gates + feature flags + source pipeline health | Cache update/invalidate, policy gate |
| P2 | Progressive 5-10-20, guideline compare | Family dashboard + escalation alerts | DDI safety board + role KPI board + drift alerts | Multimodal ingestion OCR/PDF/audio |
| P3 | AI council + reasoning logs | Bảo quản/kiểm kê/tiêu hủy + tri thức chuẩn | AI council log explorer + incident center + eval center | FIDES nâng cao, risk controls |
| P4 | Hardening + enterprise analytics | Tích hợp tư vấn bác sĩ thật | Audit explorer + compliance evidence automation | SLO hardening, cost optimization |
| P5 | Multi-tenant scale + API mở rộng | Partner channels (nhà thuốc/chăm sóc) | Tenant governance + rollout governance + cost board | DevOps + compliance automation |
| P6 | Regional expansion + federation | Regional expansion + localization | Multi-region control tower + governance federation | Ecosystem integration |

## 4. Backlog ưu tiên theo mức độ (P0/P1/P2)

### 4.1 P0 (phải có)
- Router 2 lớp role -> intent.
- Synthesis và verification node tách riêng.
- DDI check, nhắc lịch, cảnh báo dị ứng cơ bản (Self-Med).
- Citation có nguồn cho phản hồi y khoa (Research).
- Control Tower nền: IAM + health + KPI cơ bản + audit log tối thiểu.

### 4.2 P1 (nên có)
- Progressive workflow 5-10-20.
- Family dashboard + escalation alerts.
- OCR/PDF parsing nâng cao.
- Policy gate console, feature flag console, source registry board.

### 4.3 P2 (mở rộng)
- AI council đa chuyên khoa với log chi tiết.
- Tích hợp bác sĩ thật và đối tác hệ sinh thái.
- Eval center, drift center, incident center nâng cao.

## 5. KPI theo phase

| Nhóm KPI | Mô tả | Mục tiêu hướng tới |
|---|---|---|
| Thời gian phản hồi | Normal <2m, Research 5-10-20, Doctor <10-20m | Đạt theo gate từng phase |
| Chất lượng tri thức | Citation coverage, verification pass rate | Tăng dần qua phase |
| An toàn dùng thuốc | Tỷ lệ phát hiện DDI/dị ứng, giảm sai sót | Cải thiện liên tục |
| Tuân thủ điều trị | Adherence rate, escalations handled | Cải thiện theo cohort |
| Vận hành hệ thống | Availability, MTTR, error budget | Đạt chuẩn production |
| Quản trị dashboard | Policy gate action latency, incident response SLA | Đáp ứng chuẩn vận hành |

## 6. Quản trị rủi ro roadmap

- Không mở rộng phase nếu chưa đạt gate phase trước.
- Mọi feature liên quan quyết định y khoa phải qua verifier + policy gate.
- Mọi thay đổi model/prompt/policy phải có phê duyệt và rollback plan.
- Dashboard không chỉ hiển thị, mà phải điều khiển được rollback/feature flags theo quyền.

## 7. Mốc quyết định chính

1. Cuối P1: quyết định mở rộng pilot Self-Med dựa trên DDI/adherence KPIs.
2. Cuối P3: quyết định bật AI Council diện rộng dựa trên quality + safety logs.
3. Cuối P4: quyết định enterprise onboarding sau audit/compliance pass.
4. Cuối P5: quyết định regional scale khi control tower đa tenant ổn định.
