# Round2 Closeout Plan - 2026-04-02

## Mục tiêu
Đóng toàn bộ gap còn lại trong Day 13-14 để đạt trạng thái demo-ready thực sự.

## Nguồn đối chiếu
- Checklist gốc: `data/docs/implementation-plan/round2-14-day-execution-checklist-2026-03-30.md`
- Status truth: `data/docs/hackathon/hackathon-status-truth-2026-04-02.md`

## Task 1 - Chốt run canonical cho artifact pack
- Owner: `GOV-KPI`
- SLA: 0.5 ngày
- Việc làm:
  1. Chọn duy nhất 1 `run_id` để đi thi.
  2. Đảm bảo đủ 5 thư mục:
     - `data-manifest`
     - `test-report`
     - `fallback-proof`
     - `kpi-report`
     - `go-no-go`
  3. Khóa checksum + không ghi đè.
- Lệnh mẫu:
```bash
RUN_ID=round2-final-canonical-$(date +%Y%m%d-%H%M%S)
python3 scripts/demo/generate_demo_artifacts.py --run-id "$RUN_ID"
python3 scripts/demo/run_hackathon_kpis.py --mode live --strict-live --run-id "$RUN_ID"
```
- DoD:
  - Có 1 run canonical duy nhất, không còn tranh chấp nhiều run.

## Task 2 - Script demo Case A/B/C canonical
- Owner: `GOV-OPS` + `GOV-CAREGUARD`
- SLA: 0.5 ngày
- Việc làm:
  1. Tạo script `scripts/demo/run_round2_demo_cases.sh`.
  2. Case A: online normal path.
  3. Case B: runtime toggle offline fallback.
  4. Case C: legal trap refusal.
  5. Xuất `artifacts/round2/<run_id>/demo-cases/*.json|*.md`.
- DoD:
  - Chạy 1 lệnh là ra đủ chứng cứ A/B/C.

## Task 3 - Legal text + attribution UI final review
- Owner: `GOV-SAFE` + `GOV-WEB`
- SLA: 0.5 ngày
- Việc làm:
  1. Rà wording disclaimer ở `/careguard` và `/selfmed`.
  2. Rà consistency field `attributions`/`source_errors`/`fallback_used` trên UI chat/research/careguard.
  3. Chụp screenshot evidence.
- DoD:
  - Checklist legal UI pass, không còn text mâu thuẫn policy.

## Task 4 - Rehearsal 3 lần + log lỗi
- Owner: Team lead
- SLA: 0.5 ngày
- Việc làm:
  1. Rehearsal 3 vòng (10 phút/vòng).
  2. Ghi log lỗi từng vòng.
  3. Sửa lỗi blocker ngay trong ngày.
- DoD:
  - 3/3 rehearsal không vỡ flow.

## Task 5 - Freeze docs và đặt 1 nhánh tài liệu active
- Owner: `GOV-OPS`
- SLA: 0.5 ngày
- Việc làm:
  1. Chốt `data/docs/` là nhánh active.
  2. Chuyển/cắm link từ `docs/` sang `data/docs/`.
  3. Ngăn cập nhật song song 2 nơi.
- DoD:
  - Không còn trạng thái “một nội dung, hai nơi”.

## Gate chốt trước khi đi thi
- [ ] Canonical run có `go-no-go = GO`.
- [ ] Demo Case A/B/C chạy xong và lưu artifact.
- [ ] Legal text + attribution UI được rà vòng cuối.
- [ ] 3 rehearsal pass.
- [ ] Tài liệu trạng thái cập nhật vào status truth.
