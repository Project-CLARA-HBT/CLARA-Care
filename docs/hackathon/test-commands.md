# Lệnh chạy KPI / Artifact cho Hackathon

## Mục tiêu
Tài liệu này chốt các lệnh ngắn gọn để team tạo bộ bằng chứng cho Vòng 2 mà không phải nhớ tay từng bước.

## Bộ dữ liệu đầu vào
- `data/demo/ddi-goldset.jsonl`
- `data/demo/refusal-scenarios.jsonl`
- `data/demo/fallback-scenarios.jsonl`
- `data/demo/latency-scenarios.jsonl`

## 0. Full scientific testset (1 lệnh)

```bash
bash scripts/demo/run_scientific_eval_full.sh \
  --run-id round2-science-full \
  --api-base-url http://127.0.0.1:8000 \
  --ml-base-url http://127.0.0.1:8001 \
  --email admin@example.com \
  --password 'Clara#Admin2026!' \
  --doctor-email admin@example.com \
  --doctor-password 'Clara#Admin2026!'
```

Output chính:
- `artifacts/round2/round2-science-full-static/*`
- `artifacts/round2/round2-science-full-live/*`
- `artifacts/round2/round2-science-full/scientific-eval-summary.md`
- `artifacts/round2/round2-science-full/scientific-eval-summary.json`
- `artifacts/round2/round2-science-full-active/*` (nếu active loop bật)

## 0. Chạy one-shot matrix (khuyến nghị cho Vòng 2)
Script này orchestration toàn bộ flow theo thứ tự:
1. Generate artifacts
2. KPI static
3. KPI live online strict-live
4. KPI live offline fallback (toggle `external_ddi_enabled` OFF rồi ON lại)
5. Tổng hợp output và fail ngay nếu bước bắt buộc lỗi

```bash
bash scripts/demo/run_round2_matrix.sh
```

Kết quả chính:
- `artifacts/round2/<run_id>/matrix-summary.md`
- `artifacts/round2/<run_id>/matrix-summary.json`
- `artifacts/round2/<run_id>-static/*`
- `artifacts/round2/<run_id>-online/*`
- `artifacts/round2/<run_id>-offline/*`

Lưu ý:
- Script sẽ cố chạy đủ các bước để thu thập evidence (kể cả khi một bước fail), sau đó mới trả exit code fail ở cuối.
- Danh sách bước fail được ghi trong `matrix-summary.md/.json` (`failed_steps`).

Biến môi trường quan trọng:
- `CLARA_MATRIX_RUN_ID`: run id gốc (mặc định tự sinh theo timestamp).
- `CLARA_API_BASE_URL`, `CLARA_ML_BASE_URL`: base URL API/ML.
- `CLARA_MATRIX_TIMEOUT_SECONDS`: timeout cho runner KPI.
- `CLARA_DEMO_EMAIL`, `CLARA_DEMO_PASSWORD`: tài khoản user cho live KPI.
- `CLARA_DOCTOR_EMAIL`, `CLARA_DOCTOR_PASSWORD`: tài khoản doctor/admin để toggle runtime offline.
- `CLARA_BEARER_TOKEN`, `CLARA_DOCTOR_BEARER_TOKEN`: dùng token thay cho password.
- `CLARA_MATRIX_REQUIRE_ONLINE`: `true|false` (mặc định `true`).
- `CLARA_MATRIX_REQUIRE_OFFLINE`: `true|false` (mặc định `true`).
- `CLARA_MATRIX_PYTHON`: binary python (mặc định `python3`).

Ví dụ chạy đầy đủ:

```bash
CLARA_MATRIX_RUN_ID=round2-final \
CLARA_API_BASE_URL=http://127.0.0.1:8000 \
CLARA_ML_BASE_URL=http://127.0.0.1:8001 \
CLARA_DEMO_EMAIL=admin@example.com \
CLARA_DEMO_PASSWORD='Clara#Admin2026!' \
CLARA_DOCTOR_EMAIL=admin@example.com \
CLARA_DOCTOR_PASSWORD='Clara#Admin2026!' \
bash scripts/demo/run_round2_matrix.sh
```

Ví dụ chỉ chạy static + generate (bỏ qua online/offline):

```bash
CLARA_MATRIX_REQUIRE_ONLINE=false \
CLARA_MATRIX_REQUIRE_OFFLINE=false \
bash scripts/demo/run_round2_matrix.sh
```

## 0.1. Preflight local giống CI (khuyến nghị trước khi push)

Chạy nhanh 2 check blocking mới trong CI:

```bash
# 1) syntax check scripts shell
find scripts -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n

# 2) artifact + KPI static smoke
RUN_ID=local-ci-smoke-$(date +%Y%m%d-%H%M%S)
python3 scripts/demo/generate_demo_artifacts.py --run-id "$RUN_ID"
python3 scripts/demo/run_hackathon_kpis.py --mode static --run-id "$RUN_ID"
```

Expected output:
- `artifacts/round2/<RUN_ID>/kpi-report/kpi-report.json`
- `artifacts/round2/<RUN_ID>/test-report/test-report.json`
- `artifacts/round2/<RUN_ID>/fallback-proof/fallback-proof.json`

## 1. Regenerate artifact tĩnh từ source repo
Lệnh này không cần service đang chạy.

```bash
python3 scripts/demo/generate_demo_artifacts.py --run-id local-smoke
```

Kết quả chính:
- `docs/hackathon/data-manifest.json`
- `docs/hackathon/kpi-snapshot.md`
- `data/demo/ddi_internal_test_set.json`
- `data/demo/chatbot_refusal_prompts_10.json`
- `artifacts/round2/local-smoke/*`

## 2. Chạy runner KPI ở chế độ static
Phù hợp CI hoặc máy chưa bật API/ML.

```bash
python3 scripts/demo/run_hackathon_kpis.py --mode static --run-id local-smoke
```

Kết quả:
- `artifacts/round2/local-smoke/kpi-report/kpi-report.json`
- `artifacts/round2/local-smoke/kpi-report/kpi-report.md`
- `artifacts/round2/local-smoke/test-report/test-report.json`
- `artifacts/round2/local-smoke/fallback-proof/fallback-proof.json`

## 3. Chạy runner KPI ở chế độ auto
Runner sẽ thử live trước, nếu không reach được service hoặc thiếu auth thì tự hạ xuống static.

```bash
python3 scripts/demo/run_hackathon_kpis.py \
  --mode auto \
  --run-id round2-auto \
  --api-base-url http://127.0.0.1:8000 \
  --ml-base-url http://127.0.0.1:8001 \
  --email admin@example.com \
  --password 'Clara#Admin2026!' \
  --doctor-email admin@example.com \
  --doctor-password 'Clara#Admin2026!'
```

## 4. Chạy runner KPI ở chế độ live nghiêm ngặt
Chế độ này fail ngay nếu không reach được service hoặc không login được.

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

## 5. Dùng bearer token thay vì password

```bash
python3 scripts/demo/run_hackathon_kpis.py \
  --mode live \
  --run-id round2-token \
  --api-base-url http://127.0.0.1:8000 \
  --ml-base-url http://127.0.0.1:8001 \
  --bearer-token "$CLARA_BEARER_TOKEN" \
  --doctor-bearer-token "$CLARA_DOCTOR_BEARER_TOKEN"
```

## Ý nghĩa các report
- `kpi-report`: tổng hợp metric chính cho pitch.
- `test-report`: log trạng thái từng case.
- `fallback-proof`: bằng chứng bật/tắt external DDI và kết quả local fallback.

## Bổ sung scientific metrics
- Từ phiên bản hiện tại, `kpi-report` có thêm:
  - confusion matrix (TP/FP/TN/FN)
  - accuracy, precision, recall/sensitivity, specificity, F1, balanced accuracy
  - 95% CI (Wilson) cho các tỷ lệ chính
  - critical-severity recall (slice ca high/critical)
- Tài liệu phương pháp + testkit khuyến nghị:
  - `docs/hackathon/scientific-eval-testkit-guide-2026-04-01.md`

## Lưu ý vận hành
- Live fallback proof cần quyền `doctor` hoặc `admin` để gọi `/api/v1/system/careguard/runtime`.
- Nếu chỉ có user token thường, runner vẫn đo được `DDI` và `refusal`, nhưng phần fallback sẽ bị đánh dấu `blocked`.
- `DDI precision` trong report chỉ là proxy theo goldset nội bộ, không phải chỉ số kiểm định lâm sàng.
