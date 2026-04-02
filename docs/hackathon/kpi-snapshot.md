# CLARA Hackathon KPI Snapshot

Generated at (UTC): 2026-04-02T15:51:43.072685+00:00
Round2 run_id: `phase1-day10-live-20260402-225142`

## Core Metrics (Demo-Ready)
- Local DDI rules count: **62** pairs
- Internal DDI test set size: **50** cases
- VN Drug Dictionary alias coverage: **217** entries
- Refusal compliance pre-check: **10/10 (100.0%)** for prescription/diagnosis/dosage trap prompts
- Executable KPI datasets: **4 JSONL files** (DDI / refusal / fallback / latency)

## Consistency Hints
- Snapshot này là static generation theo source code và dataset hiện tại, không phải benchmark runtime end-to-end.
- Refusal compliance ở đây là pre-check theo bộ scenario; cần xác nhận lại bằng runner KPI live trên API+ML đang chạy.
- Số liệu online/offline fallback và latency phải lấy từ `scripts/demo/run_hackathon_kpis.py` với run_id tương ứng trong `artifacts/round2/`.

## Validation Notes
- DDI test set legacy được sinh từ JSONL goldset để giữ traceability với runner KPI mới.
- Prompt set tập trung vào 3 nhóm bị cấm: kê đơn, chẩn đoán, chỉ định liều.
- Runtime online/offline fallback vẫn phải benchmark bằng môi trường chạy thật (API + ML up).
