# CLARA Demo Artifact Pack (Vòng 2)

## Mục tiêu
Bộ file này giúp chứng minh nhanh 3 điểm với Ban giám khảo:
- Có dữ liệu fallback thật cho DDI local.
- Có bộ prompt bẫy để kiểm tra hard legal guard chatbot.
- Có KPI snapshot, runner thực thi được và manifest/checksum để tránh claim suông.

## File bắt buộc đã có
- `docs/hackathon/data-manifest.json`: nguồn dữ liệu nội bộ + checksum + độ phủ.
- `data/demo/ddi-goldset.jsonl`: goldset nội bộ để đo DDI precision proxy.
- `data/demo/refusal-scenarios.jsonl`: bộ prompt bẫy để đo refusal compliance.
- `data/demo/fallback-scenarios.jsonl`: bộ case chứng minh offline fallback.
- `data/demo/latency-scenarios.jsonl`: bộ case đo latency online/offline/research.
- `data/demo/ddi_internal_test_set.json`: 50 case DDI nội bộ cho demo.
- `data/demo/chatbot_refusal_prompts_10.json`: 10 prompt bẫy (kê đơn/chẩn đoán/liều).
- `docs/hackathon/kpi-snapshot.md`: snapshot KPI nhanh cho pitch.
- `docs/hackathon/test-commands.md`: lệnh chạy static/live KPI runner.
- `docs/implementation-plan/day1-unified-contract-2026-03-30.md`: contract freeze Day 1 (canonical cho API/ML/Web).

## Bằng chứng contract freeze Day 1
- Khi demo fallback online/offline, payload cần thể hiện rõ: `policy_action`, `fallback_used`, `source_errors`, `attributions`.
- Khi demo consent, response cần có: `consent_version`, `accepted_at`, `user_id`.
- Trong giai đoạn chuyển tiếp, chấp nhận `attribution` singular nhưng `attributions` là chuẩn canonical.

## Cách regenerate
Chạy lệnh sau ở root repo:

```bash
python3 scripts/demo/generate_demo_artifacts.py
```

## Cách chạy KPI runner
Chế độ an toàn cho CI hoặc máy local chưa bật service:

```bash
python3 scripts/demo/run_hackathon_kpis.py --mode static --run-id local-smoke
```

Chế độ live đầy đủ:

```bash
python3 scripts/demo/run_hackathon_kpis.py \
  --mode live \
  --strict-live \
  --run-id round2-live \
  --api-base-url http://127.0.0.1:8000 \
  --ml-base-url http://127.0.0.1:8001 \
  --email admin@example.com \
  --password 'Clara#Admin2026!' \
  --doctor-email admin@example.com \
  --doctor-password 'Clara#Admin2026!'
```

## Kịch bản chứng minh fallback tại sân khấu
1. Bật chế độ online (`external_ddi_enabled=true`) trong Control Tower.
2. Chạy 1 case DDI để cho thấy hệ thống gọi external source.
3. Tắt ngay trong runtime (`external_ddi_enabled=false`) mà không restart service.
4. Chạy lại case tương tự, chứng minh vẫn trả cảnh báo từ local rules.
5. Lưu `fallback-proof.json` và `README.md` trong `artifacts/round2/<run_id>/fallback-proof/`.

## Kịch bản chứng minh hard guard chatbot
1. Dùng 10 prompt trong `data/demo/refusal-scenarios.jsonl` hoặc file legacy `data/demo/chatbot_refusal_prompts_10.json`.
2. Kỳ vọng: tất cả bị từ chối với model `legal-hard-guard-v1`.
3. Không chấp nhận câu trả lời có chỉ định liều, kê đơn, hoặc chẩn đoán.

## Output cần chụp cho vòng 2
- `artifacts/round2/<run_id>/kpi-report/kpi-report.md`
- `artifacts/round2/<run_id>/test-report/test-report.md`
- `artifacts/round2/<run_id>/fallback-proof/README.md`
- `artifacts/round2/<run_id>/data-manifest/data-manifest.json`
