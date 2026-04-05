# Chỉ Số, Cổng Chất Lượng Và Mô Hình Vận Hành

## 1. KPI runtime theo role (bắt buộc)

- **Normal users**: < 2 phút.
- **Researchers**: 5-10-20 phút theo độ sâu.
- **Doctors**: 10-20 phút với AI Council logs bắt buộc.

## 2. KPI chất lượng AI

- Citation coverage.
- Verification pass rate.
- Hallucination rate.
- DDI critical detection sensitivity.
- Allergy alert precision/recall.
- Conflict resolution accuracy (nguồn VN vs quốc tế).

## 3. KPI Dashboard Control Tower

- Dashboard availability >= 99.9%.
- Alert delivery latency (P95) <= 5 giây.
- Incident detection-to-ack <= 3 phút.
- Audit query response (P95) <= 2 giây.
- Release approval lead time <= 30 phút với release standard.
- Drift detection lag <= 15 phút từ khi vượt ngưỡng.

## 4. KPI vận hành hệ thống

- Availability, latency p95/p99, error rate.
- MTTR theo severity.
- Cache hit ratio và invalidation accuracy.
- Connector freshness compliance.
- Cost per session theo role/workflow.

## 5. Cổng chất lượng theo giai đoạn

### Gate G0 -> G1
- Router 2 lớp hoạt động ổn định.
- Dashboard v0 health + logs online.

### Gate G1 -> G2
- KPI normal users đạt mục tiêu.
- Dashboard v1 quality/routing board hoạt động.

### Gate G2 -> G3
- Research 5-10-20 ổn định.
- Self-Med DDI/reminder/escalation đạt ngưỡng.
- Dashboard v2 nghiệp vụ (adherence/DDI/freshness) online.

### Gate G3 -> G4
- Doctor workflow + AI Council logs đạt chuẩn.
- Dashboard governance (model/prompt/policy release) online.

### Gate G4 -> G5
- Production hardening pass load test + DR drills.
- Dashboard incident center và on-call workflow hoạt động.

### Gate G5 -> G6
- Multi-tenant governance và compliance pass audit.
- Dashboard billing/cost + tenant controls ổn định.

## 6. Mô hình vận hành

- **Daily**: theo dõi dashboard realtime, xử lý cảnh báo.
- **Weekly**: review KPI + drift + backlog rủi ro.
- **Sprint**: planning/review/retro + gate readiness.
- **Phase review**: hội đồng go/no-go gồm Product, Tech, Clinical, Security.

## 7. Cơ chế escalation

- Sev0: war-room ngay lập tức.
- Sev1: xử lý trong 4 giờ.
- Sev2: xử lý trong 24 giờ.
- Sev3: đưa vào sprint backlog.

## 8. Báo cáo bắt buộc

- Báo cáo tuần: KPI chính + sự cố + hành động khắc phục.
- Báo cáo sprint: status deliverables + gate readiness.
- Báo cáo phase: quyết định go/no-go + điều kiện còn thiếu.

## 9. Tiêu chí vận hành ổn định

1. KPI runtime theo role đạt liên tục qua 2 sprint.
2. Không còn Sev0/Sev1 quá SLA.
3. Dashboard bao phủ đầy đủ: runtime, quality, incidents, compliance, cost.
4. Mọi release model/prompt/policy có audit trail và rollback profile.
