# Kế Hoạch Dịch Vụ Nền Rust

## 1. Mục tiêu

- Dùng Rust làm nền tảng backend ưu tiên cho hiệu năng, ổn định và an toàn bộ nhớ.
- Tích hợp LangChain/LangGraph ngay từ đầu qua kiến trúc hybrid Rust + Python.
- Cung cấp control-plane API cho `System Control Tower Dashboard`.

## 2. Phân ranh Rust vs Python

### 2.1 Rust (bắt buộc ưu tiên)
- API Gateway, Auth, RBAC, tenant isolation.
- Session, audit, policy engine, feature flags.
- Orchestration runtime API (điều phối request vào LangGraph services).
- Connector control APIs (health/freshness/retry/circuit-breaker).
- Dashboard APIs (IAM, registry, incidents, billing/cost, audit explorer).

### 2.2 Python (dịch vụ ML)
- LangGraph workflow services.
- OCR/ASR/embedding/rerank/generation/verifier.
- Eval jobs và benchmark pipelines.

## 3. Áp dụng LangChain/LangGraph trong backend

- Rust không thay thế LangGraph orchestration; Rust đóng vai trò control-plane + serving-plane ổn định.
- Luồng chuẩn:
  1. Rust Gateway nhận request.
  2. Rust Router runtime xác định role/intent và policy context.
  3. Rust gọi LangGraph workflow API phù hợp.
  4. Rust thu response + verification status + policy action.
  5. Rust ghi audit + stream kết quả cho web/Flutter.

## 4. Hợp đồng dịch vụ chính

- `POST /api/v1/runtime/query`
- `POST /api/v1/runtime/query/stream`
- `POST /api/v1/runtime/council`
- `GET /api/v1/control/health`
- `GET /api/v1/control/metrics`
- `GET /api/v1/control/incidents`
- `POST /api/v1/control/release/model`
- `POST /api/v1/control/release/prompt`
- `POST /api/v1/control/release/policy`

## 5. Lộ trình triển khai Rust theo P0-P6

### P0
- Workspace Rust + framework API (Axum/Actix) + auth + metrics baseline.

### P1
- Runtime query APIs + role/intent routing + cache update/invalidate.

### P2
- Self-Med APIs (DDI/reminder/escalation) + research progressive streaming APIs.

### P3
- AI Council realtime logs + governance release APIs.

### P4
- Incident center APIs + DR automation hooks.

### P5
- Multi-tenant enterprise APIs + compliance reports + billing/cost endpoints.

### P6
- Ecosystem federation APIs + partner governance endpoints.

## 6. Chuẩn chất lượng backend

- CI bắt buộc: `cargo fmt`, `cargo clippy`, `cargo test`.
- Contract tests Rust <-> LangGraph services.
- Load test theo role/workflow trước mỗi release major.
- Security scan + dependency audit định kỳ.

## 7. KPI backend

- p95 latency theo role đạt mục tiêu phase.
- Error rate trong error budget.
- MTTR giảm theo target.
- Contract success rate Rust <-> Python >= 99%.

## 8. Rủi ro và kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| Lỗi contract Rust/Python | schema versioning + contract tests bắt buộc |
| Độ trễ tăng do chain gọi chéo | timeout budget + queue isolation + circuit breaker |
| Khó vận hành release model/prompt/policy | release APIs + dashboard governance + rollback profile |
| Chi phí tăng do workload AI | cost board + throttle policy + autoscaling profile |

## 9. Tiêu chí hoàn tất

1. API runtime cốt lõi chạy trên Rust, ổn định production.
2. LangGraph workflows tích hợp chuẩn qua contract có kiểm thử.
3. Dashboard control-plane dùng được đầy đủ API quản trị.
