# Dify-style Flow Visualization Deep-Dive (2026-03-29)

## 0) Phạm vi và nguồn

- Mục tiêu: chốt mẫu UI workflow visual cho Admin CLARA theo hướng Dify/Langflow, nhưng phù hợp ngữ cảnh y tế.
- Nguồn benchmark:
  - Dify If-Else: https://docs.dify.ai/en/use-dify/nodes/ifelse
  - Dify Single Node/Step Run: https://docs.dify.ai/en/use-dify/debug/step-run
  - Dify Variable Inspector: https://docs.dify.ai/en/use-dify/debug/variable-inspect
  - Dify Run History: https://docs.dify.ai/en/use-dify/debug/history-and-logs
  - Dify Monitor Logs: https://docs.dify.ai/en/use-dify/monitor/logs
  - Langflow If-Else: https://docs.langflow.org/if-else
  - Langflow Visual Editor + Playground: https://docs.langflow.org/concepts-overview
  - Langflow Traces: https://docs.langflow.org/traces
  - Langflow Logging: https://docs.langflow.org/logging
  - Langflow Monitor endpoints: https://docs.langflow.org/api-monitor
- Nguồn canonical CLARA runtime:
  - `docs/architecture/clara-runtime-and-routing.md`
  - `docs/architecture/clara-platform-architecture.md`
  - `docs/implementation-plan/workstream-clara-research.md`
  - `docs/implementation-plan/web-mobile-information-architecture-v3.md`

## 1) Benchmark pattern workflow visual Dify/Langflow

| Pattern | Dify | Langflow | Gợi ý chuẩn hóa cho CLARA Admin |
|---|---|---|---|
| Node/edge status | Run History có Tracing: node chạy theo thứ tự, thời gian, data flow; node có “Last run” với input/output/timing/error | Traces có flow-level status + span theo component (inputs/outputs/latency/errors), Flow Activity lọc theo status/time/session | Hiển thị trạng thái theo stage runtime: `idle/running/success/warn/failed/skipped`; edge tô sáng khi active và đổi màu theo risk |
| If-Else/branching | If/ELIF/ELSE, hỗ trợ điều kiện đa kiểu + AND/OR | If-Else router theo operator; có Smart Router cho phân nhánh bằng LLM | Tách rõ branch `Router B1/B2`, branch fallback, branch policy `allow/warn/block/escalate` |
| Run debug | Có single-node run, step-by-step run, variable inspector cho phép sửa biến cache để test downstream | Chạy/test qua Playground, xem input/output, tool calls, inspect output theo component | Cần “debug sandbox” theo node/stage, cho phép override biến nhưng có audit trail |
| Run history | Có application run history (Result/Detail/Tracing), node run history, monitor logs cho production | Có Flow Activity + Trace Details + export JSON + API `/monitor/traces`; logs flow/component/chat | Cần lịch sử run hợp nhất: trace graph + metadata lâm sàng + policy decision + retention theo chuẩn compliance |

Ghi chú suy luận (inference): bộ trạng thái `idle/running/success/warn/failed/skipped` là chuẩn hóa đề xuất cho CLARA, được suy ra từ cách Dify/Langflow trình bày tracing/logs, không phải danh sách literal duy nhất trong docs của họ.

## 2) Mapping sang CLARA Research canonical flow (theo docs runtime)

Chuỗi chuẩn CLARA đã chốt trong docs runtime:
`input gateway -> safety ingress -> router B1 -> router B2 -> planner/supervisor -> retrieval -> synthesis -> verification -> policy gate -> response+audit`.

Bảng map visual:

| Canonical node CLARA | Cụm UI tương ứng trong Flow Studio | Trạng thái cần hiển thị |
|---|---|---|
| Gateway + Safety ingress (Rust) | `Ingress Lane` (pre-check) | consent, PHI/PII scrub, ingress pass/fail |
| Router B1 (Role), Router B2 (Intent) | `Routing Lane` (decision nodes) | route selected, confidence, fallback trigger |
| Planner/Supervisor (LangGraph) | `Planning Lane` | plan depth (5/10/20), subtask count, budget time |
| Retrieval agents | `Evidence Lane` | source hit/miss, latency, freshness, conflict flag |
| Synthesis | `Draft Lane` | claim count, draft confidence |
| Verification (FIDES-inspired) | `Verification Lane` | verified/partial/unverified/failed |
| Policy gate (Rust) | `Safety Gate Lane` | allow/warn/block/escalate + reason codes |
| Response + Audit | `Output Lane` | final response, citations, trace_id, audit completeness |

Branch logic tối thiểu cần vẽ rõ trên canvas:

- `Router low-confidence -> ask-context/safe-mode`
- `Retrieve empty/source outage -> degrade/fallback`
- `Verification fail -> block hoặc escalate`
- `Policy action -> allow/warn/block/escalate`

## 3) Checklist implement UI Admin giống Dify nhưng phù hợp y tế

### 3.1 Canvas + trạng thái

- [ ] Canvas node-edge có lane theo runtime CLARA (Ingress/Routing/Planning/Evidence/Verification/Policy/Output).
- [ ] Node badge bắt buộc: `status`, `duration`, `owner service (Rust/ML)`, `risk level`.
- [ ] Edge hiển thị điều kiện branch (ví dụ `confidence < threshold`, `verification=failed`).
- [ ] Có mini-map + zoom + fit view cho flow dài.

### 3.2 If-Else và policy branch

- [ ] Editor hỗ trợ IF/ELIF/ELSE cho router/policy/fallback.
- [ ] Rule form có validation mạnh cho điều kiện y tế (không cho publish nếu thiếu nhánh fail-safe).
- [ ] Branch policy phải map 1-1 với `allow/warn/block/escalate` trong runtime docs.

### 3.3 Debug và test-run

- [ ] Chế độ `single node test` + `step run` với input mẫu clinical-safe.
- [ ] Inspector cho biến trung gian nhưng log đầy đủ mọi lần override.
- [ ] Trace pane hiển thị I/O, latency, token/cost, error theo node.
- [ ] Cảnh báo đỏ khi node bypass verification/policy.

### 3.4 Run history + compliance

- [ ] Bảng lịch sử run có filter theo `tenant/role/intent/policy_action/time range`.
- [ ] Chi tiết run có 3 tab tối thiểu: `Result`, `Detail`, `Tracing`.
- [ ] Lưu và hiển thị `trace_id`, `session_id`, `reason_codes`, citations.
- [ ] Retention và masking log theo chính sách dữ liệu nhạy cảm y tế.

### 3.5 Governance

- [ ] RBAC: chỉ `builder-access`/`admin-ops` được chỉnh flow hoặc xem log nhạy cảm.
- [ ] Versioning: draft -> review -> approve -> publish -> rollback.
- [ ] Mọi thay đổi flow/debug override phải có audit event bất biến.

## 4) Micro-plan 2 phase

## P1 - Visual Foundation (Flow Studio UI)

Mục tiêu: có visual graph editor giống tinh thần Dify, map đúng canonical CLARA runtime.

- Scope:
  - Canvas lane-based + node/edge status.
  - Flow editor cho branch IF/ELIF/ELSE và policy branch.
  - Flow list, version list, test-run shell UI (chưa cần trace sâu).
- Deliverables:
  - Route: `/app/dashboard/flow-config`, `/app/dashboard/flow-config/:flow-id`, `/app/dashboard/flow-config/:flow-id/version-history`.
  - State model FE chuẩn cho node/edge/policy badges.
- DoD:
  - Vẽ được full chain canonical CLARA không missing node bắt buộc.
  - Hiển thị được trạng thái run cơ bản theo từng node.
  - Pass review UX nội bộ cho readability và safety cues y tế.

## P2 - Runtime Debug & History

Mục tiêu: đạt năng lực debug/audit tương đương Dify Run History + mở rộng governance cho y tế.

- Scope:
  - Step-run + variable inspector + trace details.
  - Run History hợp nhất Result/Detail/Tracing.
  - Log filters và compliance controls (masking, retention, RBAC).
- Deliverables:
  - Route: `/app/dashboard/flow-config/:flow-id/test-run`.
  - API contract UI cho trace/log/policy outcome.
  - Incident handoff hooks từ failed/escalated runs sang Ops.
- DoD:
  - Truy vết end-to-end mỗi run từ ingress đến policy gate.
  - Có thể debug node-level và chứng minh không bypass verification/policy.
  - Audit trail đủ cho review an toàn y tế và post-incident analysis.
