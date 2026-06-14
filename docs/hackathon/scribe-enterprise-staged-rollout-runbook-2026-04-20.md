# Clara Scribe Enterprise — Staged Rollout & Rollback Runbook (2026-04-20)

Spec: `.kiro/specs/clara-scribe-enterprise/` (task 3.5 — wave 1; task 10.3 — wave 2).

## Mục tiêu
- Bật từng năng lực Clara Scribe enterprise **theo từng giai đoạn**, an toàn và đảo ngược tức thì.
- Mọi flag mặc định **OFF** ⇒ hành vi byte-for-byte như batch scribe hiện tại (Req 11.2).
- Thứ tự deploy mỗi giai đoạn: **ml → api → web** (web phụ thuộc contract của ml+api).
- Giám sát đĩa trước/sau mỗi giai đoạn; rollback = tắt flag + redeploy, không mất dữ liệu (Req 11.3).

## Nguyên tắc an toàn
- Flag-gated + additive: bật flag chỉ thêm hành vi, không sửa note text/transcript đã có.
- Regression gate là cổng chặn: `services/api/tests/test_scribe_regression_gate.py` +
  `services/ml/tests/test_scribe_regression_gate.py` phải xanh **trước** khi bật flag bất kỳ,
  và sau khi rollback (tất cả flag off ⇒ legacy nguyên trạng).
- Không commit `.env` hay backup `.env` vào git. Bật flag = sửa `.env` runtime, không sửa default trong code.

## Thành phần
- `scripts/deploy/scribe_staged_rollout.sh` — điều phối bật flag theo giai đoạn (dry-run mặc định),
  giám sát đĩa, redeploy theo thứ tự ml→api→web, và rollback tức thì. Tái sử dụng
  `scripts/deploy/redeploy_app_stack.sh` (health + smoke) và `scripts/ops/cleanup_disk.sh` (đĩa).
- `scripts/deploy/redeploy_app_stack.sh` — preflight env guard + `docker compose up` + health/smoke.
- `scripts/ops/cleanup_disk.sh` — kiểm tra ngưỡng đĩa, dọn dẹp an toàn (dùng `--dry-run` để chỉ kiểm tra).

## Cổng tiền điều kiện (preflight gate)
Chạy trước mọi giai đoạn:

```bash
# 1) Regression gate phải xanh (flags-off ⇒ legacy byte-for-byte)
.venv-api/bin/python -m pytest services/api/tests/test_scribe_regression_gate.py -q
.venv-ml/bin/python  -m pytest services/ml/tests/test_scribe_regression_gate.py  -q

# 2) Đủ dung lượng đĩa (chỉ kiểm tra, không xoá gì)
scripts/ops/cleanup_disk.sh --dry-run

# 3) Env hợp lệ
REQUIRE_DEEPSEEK=true scripts/ops/validate_runtime_env.sh /opt/clara-care/.env
```

## Thứ tự giai đoạn (staged flag sequence)

### Wave 1 (R1–R11) — bật theo thứ tự phụ thuộc
| Giai đoạn | Flag(s) | Ghi chú |
| --- | --- | --- |
| w1-consent     | `RAG_SCRIBE_CONSENT_REQUIRED` | Compliance trước tiên |
| w1-templates   | `RAG_SCRIBE_TEMPLATES_ENABLED` | Multi-template note |
| w1-coding      | `RAG_SCRIBE_CODING_ENABLED` | ICD + drug safety (advisory) |
| w1-sign        | `RAG_SCRIBE_SIGN_WORKFLOW_ENABLED` | review→sign→amend + audit |
| w1-export      | `RAG_SCRIBE_EXPORT_ENABLED`, `RAG_SCRIBE_FHIR_EXPORT_ENABLED` | md/docx/FHIR DocumentReference |
| w1-diarization | `RAG_SCRIBE_DIARIZATION_ENABLED` | speaker labels (additive) |
| w1-streaming   | `RAG_SCRIBE_STREAMING_ENABLED` | ambient SSE; fallback batch khi off |

### Wave 2 (R12–R20) — theo design rollout (task 10.3)
| Giai đoạn | Flag(s) |
| --- | --- |
| w2-grounding-extraction | `RAG_SCRIBE_GROUNDING_ENABLED`, `RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED` |
| w2-em-cpt               | `RAG_SCRIBE_EM_CPT_CODING_ENABLED` |
| w2-quality-wer          | `RAG_SCRIBE_QUALITY_METRICS_ENABLED`, `RAG_SCRIBE_WER_REPORTING_ENABLED` |
| w2-fhir-addendum        | `RAG_SCRIBE_FHIR_COMPOSITION_ENABLED`, `RAG_SCRIBE_ADDENDUM_ENABLED` |
| w2-specialty-templates  | `RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED` |
| w2-eval-gate            | `RAG_SCRIBE_EVAL_GATE_ENABLED` (offline/CI only) |

## Wave 2 — chi tiết từng giai đoạn (task 10.3)

Nguồn chân lý duy nhất cho mọi flag (mặc định OFF + chú thích) là `.env.example`.
Mỗi giai đoạn áp dụng theo thứ tự service **ml → api → web**. Sau khi bật, chạy
**verification/smoke** tương ứng; chỉ chuyển sang giai đoạn kế tiếp khi đạt
**success criteria**. **Rollback tức thì** = bật lại flag về `false` + redeploy ⇒ hành vi
byte-for-byte như trước (tận dụng regression gate flags-off của task 10.1).

### Giai đoạn 1 — grounding + structured extraction
- **Flags:** `RAG_SCRIBE_GROUNDING_ENABLED=true`, `RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED=true` (ship cùng nhau — chung span model).
- **Enable:** `APPLY=true scripts/deploy/scribe_staged_rollout.sh enable w2-grounding-extraction`
- **Verification/smoke:** tạo note qua `POST /scribe/sessions/{id}/notes`; gọi
  `GET .../notes/{ver}/grounding` và `.../notes/{ver}/extraction` (clinician RBAC) → 200 + payload có dữ liệu.
- **Success criteria:** note `sections_json` + transcript **không đổi** (P7); statement có chip grounded/unverified, không có critical-safety ungrounded được khẳng định (P8); extraction có provenance span + RxCUI, type vắng mặt ⇒ list rỗng (P9).
- **Rollback tức thì:** `APPLY=true scripts/deploy/scribe_staged_rollout.sh disable w2-grounding-extraction` ⇒ `grounding`/`extraction` endpoints trả 404, không còn `grounding_json`/`extraction_json`.

### Giai đoạn 2 — E/M + CPT coding (anti-upcoding)
- **Flags:** `RAG_SCRIBE_EM_CPT_CODING_ENABLED=true`.
- **Enable:** `APPLY=true scripts/deploy/scribe_staged_rollout.sh enable w2-em-cpt`
- **Verification/smoke:** tạo note → `coding_json` chứa gợi ý E/M + CPT, mỗi gợi ý có justifying span, `selected=false`, `status="advisory"`.
- **Success criteria:** E/M ≤ defensible level (anti-upcoding), không code nào ở trạng thái selected khi chưa clinician confirm (P10); note text không đổi (P7).
- **Rollback tức thì:** `disable w2-em-cpt` ⇒ coding trở lại R7 (ICD + drug-safety) thuần.

### Giai đoạn 3 — quality metrics + WER reporting (non-blocking)
- **Flags:** `RAG_SCRIBE_QUALITY_METRICS_ENABLED=true`, `RAG_SCRIBE_WER_REPORTING_ENABLED=true`.
- **Enable:** `APPLY=true scripts/deploy/scribe_staged_rollout.sh enable w2-quality-wer`
- **Verification/smoke:** `GET /scribe/analytics/quality` → payload metrics; kiểm tra không có PII (id bệnh nhân / transcript thô).
- **Success criteria:** metrics PII-free + omit-on-missing (P13); WER không chặn/không đổi workflow ghi chú (R16.5).
- **Rollback tức thì:** `disable w2-quality-wer` ⇒ không tính/không lộ metrics, không `quality_json`/`wer_json`.

### Giai đoạn 4 — FHIR Composition/Encounter + addendum
- **Flags:** `RAG_SCRIBE_FHIR_COMPOSITION_ENABLED=true`, `RAG_SCRIBE_ADDENDUM_ENABLED=true`.
- **Enable:** `APPLY=true scripts/deploy/scribe_staged_rollout.sh enable w2-fhir-addendum`
- **Verification/smoke:** với note đã `signed`, `GET .../export?format=fhir_composition` → `Composition`+`Encounter` (+ `DocumentReference`); `POST .../notes/{ver}/addendum` → 1 audit entry.
- **Success criteria:** Composition 1 section/template section + round-trip, chỉ cho note signed/exported (P11); addendum giữ signed version byte-for-byte, không tạo version mới, đúng 1 audit entry, demarcated trong export (P12).
- **Rollback tức thì:** `disable w2-fhir-addendum` ⇒ `fhir_composition` + addendum endpoints retracted; export quay về md/docx/fhir (DocumentReference).

### Giai đoạn 5 — specialty / macro templates
- **Flags:** `RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED=true`.
- **Enable:** `APPLY=true scripts/deploy/scribe_staged_rollout.sh enable w2-specialty-templates`
- **Verification/smoke:** chọn specialty template → note có đúng section keys của template; template/macro mới không đổi output template hiện hữu.
- **Success criteria:** template-completeness (P1 tái dùng) + isolation khi thêm template/macro (P14).
- **Rollback tức thì:** `disable w2-specialty-templates` ⇒ chỉ còn template set của R6.

### Giai đoạn 6 — note-generation eval gate (offline/CI)
- **Flags:** `RAG_SCRIBE_EVAL_GATE_ENABLED=true` (chỉ chạy offline/CI, không nằm trên đường runtime của clinician).
- **Enable:** `APPLY=true scripts/deploy/scribe_staged_rollout.sh enable w2-eval-gate`
- **Verification/smoke:** chạy `scribe_eval` golden-set harness trong CI → pass iff mọi metric đạt threshold; nêu tên metric vi phạm.
- **Success criteria:** threshold enforcement (P15); golden data + report PII-free (P13); không thay đổi hành vi runtime (R20.1/20.6).
- **Rollback tức thì:** `disable w2-eval-gate` ⇒ gate không chạy, không ảnh hưởng runtime.

## Cách dùng

Dry-run mặc định — chỉ in kế hoạch + kiểm tra đĩa, **không** sửa `.env`, **không** redeploy:

```bash
# Xem toàn bộ kế hoạch giai đoạn
scripts/deploy/scribe_staged_rollout.sh plan

# Mô phỏng bật một giai đoạn (không thay đổi gì)
scripts/deploy/scribe_staged_rollout.sh enable w1-consent
```

Thực thi thật (có guard) — backup `.env`, bật flag, redeploy ml→api→web, health/smoke:

```bash
APPLY=true ROOT_DIR=/opt/clara-care scripts/deploy/scribe_staged_rollout.sh enable w1-consent
```

Rollback tức thì — tắt một giai đoạn, hoặc tắt TẤT CẢ flag về legacy:

```bash
# Tắt một giai đoạn
APPLY=true scripts/deploy/scribe_staged_rollout.sh disable w1-streaming

# Rollback toàn bộ về legacy (mọi flag OFF) + redeploy
APPLY=true scripts/deploy/scribe_staged_rollout.sh rollback-all
```

## Quy trình mỗi giai đoạn (script tự thực hiện khi APPLY=true)
1. **Preflight đĩa**: `cleanup_disk.sh --dry-run`; nếu vượt ngưỡng → dừng (chạy cleanup thủ công trước).
2. **Backup `.env`**: `scripts/ops/backup_env.sh` (timestamp + sha256) để rollback nhanh.
3. **Bật flag**: set `RAG_SCRIBE_*=true` trong `.env` (idempotent — thêm hoặc cập nhật dòng).
4. **Redeploy ml → api → web**: `redeploy_app_stack.sh` chạy env guard + health + smoke (`/health`, `/health/details`, smoke ml/auth).
5. **Hậu kiểm đĩa**: in `df` used%/free GB sau khi build image.
6. Nếu bất kỳ bước nào fail → **tự rollback** giai đoạn vừa bật và thoát non-zero.

## Checklist vận hành
- [ ] Regression gate (api + ml) xanh trước khi bật flag.
- [ ] `.env` đã backup (có file `.sha256` mới) trước mỗi lần APPLY.
- [ ] Đĩa dưới ngưỡng (`cleanup_disk.sh --dry-run` không cảnh báo) trước build.
- [ ] Health `/health` (api 8100, ml 8110) trả `"status":"ok"` sau redeploy.
- [ ] Smoke ml + auth pass (do `redeploy_app_stack.sh` chạy).
- [ ] Sau rollback-all: regression gate vẫn xanh ⇒ legacy byte-for-byte.

## Ghi chú
- Script **mặc định dry-run**: không có `APPLY=true` thì không sửa `.env` và không redeploy — an toàn để chạy ở mọi môi trường.
- Bật flag chỉ thay đổi `.env` runtime; default trong `services/*/config.py` luôn OFF (Req 11.1).
- Rollback không mất dữ liệu: session/note/audit hiện hữu vẫn đọc được khi flag tắt (Req 11.3).
