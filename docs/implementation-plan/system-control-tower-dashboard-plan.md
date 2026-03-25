# Kế Hoạch System Control Tower Dashboard

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-25

## 1. Mục tiêu dashboard quản trị toàn hệ thống CLARA

- Thiết lập một control-plane thống nhất cho Product/Ops/Clinical/Security để theo dõi và điều hành hệ thống CLARA theo thời gian thực.
- Giảm thời gian phát hiện và xử lý sự cố (MTTD/MTTR), có cơ chế cảnh báo theo ngưỡng và runbook rõ ràng.
- Quản trị vòng đời model/prompt/policy có kiểm soát, có bằng chứng phê duyệt và khả năng rollback.
- Đảm bảo tuân thủ vận hành AI y tế: audit trail đầy đủ, truy vết hành động, xuất báo cáo compliance.
- Minh bạch chi phí theo role/workflow/tenant để tối ưu hiệu năng - chất lượng - chi phí.

## 2. Các module bắt buộc

| Module | Câu hỏi vận hành chính | Thành phần UI bắt buộc |
|---|---|---|
| Health | Hệ thống có đang ổn định không? dịch vụ nào suy giảm? | Uptime board, error-rate panel, queue-depth panel, connector heartbeat |
| Source Freshness | Nguồn dữ liệu nào đã cũ/stale và ảnh hưởng nhánh nào? | Freshness heatmap theo source, stale alert feed, SLA compliance table |
| Routing Quality | Router có phân luồng đúng role/intent và đạt chất lượng không? | Role/intent traffic split, confidence distribution, verification/citation board |
| Policy Release | Release model/prompt/policy có qua gate và rollback an toàn không? | Release pipeline board, gate result panel, approval trail, rollback actions |
| Incidents | Sự cố đang ở mức nào, ai chịu trách nhiệm, SLA còn bao lâu? | Incident center (Sev0-Sev3), timeline, owner board, runbook linkage |
| Audit/Compliance | Có đủ bằng chứng tuân thủ và truy vết hành động không? | Audit explorer, access review table, compliance evidence/report generator |
| Cost | Chi phí có vượt ngân sách theo role/workflow/tenant không? | Cost overview, cost per session/workflow, tenant cost board, budget variance panel |

## 3. KPI vận hành và cảnh báo ngưỡng

### 3.1 KPI nền của Control Tower

- Dashboard availability >= 99.9%.
- Alert delivery latency (P95) <= 5 giây.
- Incident detection-to-ack <= 3 phút.
- Audit query response (P95) <= 2 giây.
- Release approval lead time <= 30 phút (release standard).
- Drift detection lag <= 15 phút từ khi vượt ngưỡng.

### 3.2 Ngưỡng cảnh báo theo module

| Module | KPI | Warning | Critical | Hành động tự động/đề xuất |
|---|---|---|---|---|
| Health | Availability (rolling 24h) | < 99.9% | < 99.5% | Tạo incident Sev2/Sev1, mở runbook service owner |
| Health | Error rate 5xx (5 phút) | > 1% | > 2% | Bật degrade mode, cảnh báo on-call |
| Source Freshness | Freshness compliance | < 98% nguồn đạt SLA | < 95% | Khoanh vùng connector lỗi, ưu tiên retry/backfill |
| Source Freshness | Nguồn critical bị stale | > 30 phút | > 120 phút | Nâng mức cảnh báo, gắn cờ output có rủi ro dữ liệu cũ |
| Routing Quality | Misroute rate | > 2% | > 4% | Chuyển safe-route + mở điều tra router drift |
| Routing Quality | Verification pass rate | < 97% | < 95% | Chặn release mới, tăng sampling review |
| Policy Release | Change failure rate | > 5% | > 10% | Dừng rollout, kích hoạt rollback profile |
| Policy Release | Approval lead time | > 30 phút | > 60 phút | Escalate approver, mở SLA breach ticket |
| Incidents | Sev0/Sev1 quá SLA | Có case quá SLA | Nhiều case quá SLA đồng thời | Mở war-room, khóa rollout không khẩn cấp |
| Audit/Compliance | Audit completeness (risk cao) | < 99% | < 98% | Chặn go-live gate, yêu cầu bù log bắt buộc |
| Audit/Compliance | Truy cập trái quyền | >= 1 sự kiện xác thực | Lặp lại/đa tenant | Khóa session, yêu cầu incident security |
| Cost | Cost variance tuần/tuần | > +15% | > +25% | Áp throttle policy, tối ưu model tier |
| Cost | Cost per session theo role vượt ngân sách | > 10% budget | > 20% budget | Giảm mức model mặc định + review policy |

## 4. Lộ trình P1 -> P6 cho dashboard

Ghi chú: P0 đã có dashboard v0 (health/logs cơ bản). Lộ trình dưới đây tập trung các pha P1-P6 theo master plan.

| Phase | Mục tiêu dashboard | Deliverables bắt buộc |
|---|---|---|
| P1 | Quan sát routing + quality theo thời gian thực | Dashboard v1: router confidence panel, latency panel, citation coverage panel, policy action distribution |
| P2 | Bổ sung vận hành nghiệp vụ Research/Self-Med + freshness | Dashboard v2: adherence analytics, DDI trend, source freshness board, OCR/ADE quality panel |
| P3 | Vận hành governance release model/prompt/policy | Governance v3: model/prompt/policy registry, approve/reject flow, AI Council logs explorer |
| P4 | Điều hành sự cố production tập trung | Incident center: Sev0-Sev3 board, MTTR board, timeline + runbook linkage, error budget panel |
| P5 | Mở rộng enterprise với compliance và cost governance | Tenant governance console, compliance report generator, billing/cost observability theo tenant/role/workflow |
| P6 | Quản trị hệ sinh thái và liên thông đối tác | Ecosystem center: partner health board, data trust score, federation alert center |

## 5. API/contracts cần hiển thị ở frontend admin

### 5.1 API control-plane bắt buộc

- `GET /api/v1/control/health`
- `GET /api/v1/control/metrics`
- `GET /api/v1/control/incidents`
- `POST /api/v1/control/release/model`
- `POST /api/v1/control/release/prompt`
- `POST /api/v1/control/release/policy`
- `GET /api/v1/control/connectors`
- `GET /api/v1/control/routing/quality`
- `GET /api/v1/control/audit/events`
- `GET /api/v1/control/compliance/reports`
- `GET /api/v1/control/cost/summary`
- `GET /api/v1/control/cost/breakdown`
- `GET /api/v1/control/alerts/stream` (SSE/WebSocket cho cảnh báo realtime)

### 5.2 Contract hiển thị tối thiểu theo module

| Module | Endpoint chính | Trường dữ liệu tối thiểu cần render ở UI |
|---|---|---|
| Health | `GET /api/v1/control/health` | `service`, `status`, `uptime_pct_24h`, `error_rate_5m`, `latency_p95_ms`, `queue_depth`, `updated_at` |
| Source Freshness | `GET /api/v1/control/connectors` | `source_id`, `source_name`, `last_success_at`, `max_allowed_age_min`, `freshness_state`, `sla_compliance`, `owner` |
| Routing Quality | `GET /api/v1/control/routing/quality` | `role`, `intent`, `traffic_count`, `route_confidence_p50`, `misroute_rate`, `verification_pass_rate`, `citation_coverage`, `window` |
| Policy Release | `POST /api/v1/control/release/{model|prompt|policy}` + `GET /api/v1/control/releases` | `release_id`, `artifact_type`, `version`, `gate_result`, `approved_by`, `approved_at`, `rollback_ready`, `status`, `trace_id` |
| Incidents | `GET /api/v1/control/incidents` | `incident_id`, `severity`, `status`, `title`, `owner`, `detected_at`, `ack_at`, `sla_due_at`, `mttr_min`, `runbook_url` |
| Audit/Compliance | `GET /api/v1/control/audit/events`, `GET /api/v1/control/compliance/reports` | `event_id`, `trace_id`, `actor`, `action`, `resource`, `policy_action`, `result`, `risk_level`, `timestamp`, `evidence_uri` |
| Cost | `GET /api/v1/control/cost/summary`, `GET /api/v1/control/cost/breakdown` | `period`, `cost_total`, `cost_per_session`, `cost_per_role`, `cost_per_workflow`, `cost_per_tenant`, `variance_pct`, `budget_status` |

### 5.3 Contract cảnh báo realtime cho mọi widget

```json
{
  "alert_id": "alt_123",
  "module": "routing_quality",
  "severity": "sev2",
  "metric": "misroute_rate",
  "current_value": 0.043,
  "threshold": 0.04,
  "started_at": "2026-03-25T09:15:00Z",
  "trace_id": "trc_abc",
  "recommended_action": "switch_to_safe_route"
}
```

## 6. Tiêu chí hoàn tất tài liệu

1. Bao phủ đủ 7 module bắt buộc: health, source freshness, routing quality, policy release, incidents, audit/compliance, cost.
2. Có KPI và ngưỡng cảnh báo để vận hành theo mô hình go/no-go.
3. Có roadmap P1-P6 rõ deliverables dashboard theo từng phase.
4. Frontend admin có danh mục API/contracts rõ ràng để triển khai.
