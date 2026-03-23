# Đề Xuất Tổng Thể CLARA (Master Proposal)

Phiên bản: 1.1  
Ngày cập nhật: 2026-03-24

## 1. Tóm tắt điều hành

CLARA được phát triển như một nền tảng AI y tế có hai nhánh sản phẩm dùng chung hạ tầng:
- **CLARA Research**: trợ lý nghiên cứu y khoa dựa trên bằng chứng, phục vụ researcher/bác sĩ.
- **CLARA Self-Med**: ứng dụng quản lý thuốc gia đình, tập trung an toàn dùng thuốc và tuân thủ điều trị.

Quyết định kỹ thuật ở mức sản phẩm:
- **Dùng LangChain/LangGraph** để orchestration các luồng AI (planner, retrieval, synthesis, verification, council).
- **Backend ưu tiên Rust** cho các dịch vụ runtime hiệu năng cao và kiểm soát vận hành.
- **Web + Mobile Flutter** cho trải nghiệm đa nền tảng.
- Bổ sung năng lực nền tảng mới: **CLARA Control Tower** (dashboard quản trị toàn hệ thống).

## 2. Định vị 3 năng lực sản phẩm

| Năng lực | Đối tượng chính | Giá trị cốt lõi |
|---|---|---|
| CLARA Research | Researcher, bác sĩ, QA lâm sàng | Truy xuất nhanh, kiểm chứng nguồn, so sánh guideline |
| CLARA Self-Med | Người dân, người chăm sóc, gia đình bệnh mạn tính | Quản lý thuốc an toàn, DDI, nhắc lịch, escalation |
| CLARA Control Tower | Product/Ops/Clinical/Security | Quản trị hệ thống, giám sát chất lượng, vận hành an toàn |

## 3. Quyết định kỹ thuật bắt buộc

### 3.1 Orchestration AI: LangChain/LangGraph

- **LangGraph**: biểu diễn workflow theo đồ thị trạng thái cho các luồng dài và nhiều nhánh.
- **LangChain**: tool calling, retriever integration, prompt template, output parser.
- Mô hình áp dụng:
  - Planner/Supervisor điều phối sub-agents theo role và intent.
  - Retrieval agents chạy song song theo nguồn/modality.
  - Synthesis node tổng hợp phản hồi có citation map.
  - Verification node kiểm chứng độc lập (FIDES-inspired).
  - Policy gate chặn/giảm phạm vi/chuyển tuyến.

### 3.2 Rust backend-first

- Rust chịu trách nhiệm: gateway, auth, RBAC, policy gate, audit, session, cache services, realtime event bus.
- Python service dành cho ML/OCR/ASR/fine-tune khi cần thư viện chuyên dụng.
- Contract Rust <-> AI services được version hóa, có timeout/retry và trace id xuyên suốt.

### 3.3 Intent Router 2 lớp

1. **Lớp 1**: phân loại role (Normal / Researcher / Doctor).  
2. **Lớp 2**: phân loại intent theo role.  
Kết quả role+intent là đầu vào để quyết định workflow, nguồn dữ liệu và mức kiểm chứng.

## 4. CLARA Control Tower (Dashboard quản trị toàn hệ thống)

### 4.1 Persona sử dụng

- **Product**: theo dõi adoption, funnel, retention, feature flags.
- **Operations/SRE**: theo dõi uptime, latency, queue health, incidents.
- **Clinical/Safety**: theo dõi DDI safety, AI council logs, escalation queue, policy violations.
- **Security/Compliance**: audit trail, access logs, consent status, compliance evidence.

### 4.2 Các module bắt buộc

1. **IAM & Role/Tenant Admin**: quản trị user/role/tenant, phân quyền môi trường.
2. **Feature Flags & Rollout**: bật/tắt theo cohort, canary control.
3. **Policy Gates Console**: quản trị ngưỡng chặn/cảnh báo/chuyển tuyến.
4. **KPI & SLO Console**: theo role, theo workflow, theo nhánh sản phẩm.
5. **AI Council Log Explorer**: truy vết deliberation và quyết định.
6. **DDI Safety Monitor**: giám sát cảnh báo critical/major/moderate.
7. **Model/Prompt Registry**: version hóa và phê duyệt phát hành.
8. **Source Pipeline Registry**: trạng thái ingest BYT/Dược thư/PubMed/openFDA/RxNorm.
9. **Drift & Eval Center**: theo dõi drift dữ liệu/model, kết quả benchmark.
10. **Incident Center**: phân loại sự cố, RCA, hành động khắc phục.

### 4.3 Phạm vi dữ liệu dashboard

- Role-level metrics: normal/researcher/doctor.
- Safety metrics: DDI detection, allergy alerts, false positive/negative trends.
- Compliance metrics: audit completeness, consent coverage, PHI policy checks.
- Data freshness: pipeline latency, source freshness, recheck status.

## 5. Lộ trình P0 -> P6 (góc nhìn tổng thể)

| Phase | CLARA Research | CLARA Self-Med | CLARA Control Tower |
|---|---|---|---|
| P0 | Router 2 lớp nền, retrieval cơ bản | Tủ thuốc số hóa nền | Dashboard khung: IAM + KPI tối thiểu + health widgets |
| P1 | Citation + verifier nền | Nhắc lịch + DDI nền + dị ứng | Policy gate UI + feature flags + source pipeline health |
| P2 | Progressive 5-10-20, compare guideline | Family dashboard + escalation | DDI safety board + role KPI board + drift cảnh báo nền |
| P3 | AI Council + log reasoning | Bảo quản/kiểm kê/tiêu hủy + tri thức chuẩn | AI council log explorer + incident center + eval center |
| P4 | Hardening + enterprise analytics | Tích hợp bác sĩ thật | Audit explorer + compliance evidence automation |
| P5 | Multi-tenant scale + API đối tác | Partner channels | Multi-tenant control + cost governance + rollout governance |
| P6 | Regional/federation expansion | Regional expansion | Liên thông dashboard đa vùng + governance federation |

## 6. KPI điều hành cấp nền tảng

- **Thời gian phản hồi theo role**:
  - Normal users: < 2 phút.
  - Researchers: 5-10-20 phút theo độ sâu.
  - Doctors: < 10-20 phút, có log hội chẩn khi bật AI Council.
- **Chất lượng tri thức**: citation coverage, verification pass rate, conflict-resolution rate.
- **An toàn dùng thuốc**: DDI critical detection sensitivity, allergy alert precision.
- **Vận hành**: availability, MTTR, incident recurrence.

## 7. Risk controls cấp nền tảng

- Không cho synthesis tự kết luận cuối khi chưa qua verification.
- Cache y khoa chỉ `update/invalidate`, không append mù.
- Không dùng LLM cho quyết định hard-stop trong DDI critical/allergy critical.
- Mọi thay đổi model/prompt/policy phải đi qua gate và có rollback.

## 8. Quyết định đề xuất

1. Phê duyệt chiến lược 2 nhánh sản phẩm + 1 control-plane dashboard.
2. Chốt sử dụng **LangChain/LangGraph** cho orchestration AI flow.
3. Chốt **Rust backend-first** cho runtime và quản trị vận hành.
4. Triển khai roadmap P0->P6 có deliverables dashboard bắt buộc ở mọi phase.
