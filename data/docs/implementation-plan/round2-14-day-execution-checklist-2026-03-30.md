# Checklist Triển Khai 14 Ngày - Vòng 2 (30/03/2026 -> 12/04/2026)

> Nguồn trạng thái chuẩn để đối chiếu nhanh: `data/docs/hackathon/hackathon-status-truth-2026-04-02.md`

## 1) Khóa mục tiêu Vòng 2 (không đổi)
- [x] Một câu chuyện duy nhất: Quản lý tủ thuốc + Cảnh báo DDI + Chatbot giải thích an toàn thuốc.
- [x] Demo chạy được cả Online và Offline Fallback.
- [x] Chatbot không vượt ranh giới pháp lý: không chẩn đoán, không kê đơn, không hướng dẫn liều dùng.

## 2) Khóa ưu tiên
- [x] P0 bắt buộc xong trước demo.
- [x] P1 làm khi còn thời gian.
- [ ] P2 để sau cuộc thi.

## Trạng thái thực tế (snapshot 31/03/2026)
- Quy ước: `[x]` = đã có bằng chứng trong codebase, `[ ]` = chưa xong hoặc chưa đủ bằng chứng.
- Một số mục có ghi chú `(partial)` để phản ánh đã có triển khai một phần nhưng chưa đạt đúng định nghĩa ban đầu.

## Cập nhật triển khai (01/04/2026)
- [x] Bổ sung Go/No-Go Gate tự động trong `scripts/demo/run_hackathon_kpis.py`.
- [x] Xuất thêm artifact `go-no-go/go-no-go.json` và `go-no-go/go-no-go.md`.
- [x] `--mode live --strict-live` sẽ fail exit code nếu gate NO-GO; mode khác có thể bật `--enforce-gate`.
- [x] Bổ sung matrix runner one-shot `scripts/demo/run_round2_matrix.sh` (generate + static + live online + live offline fallback).
- [x] Bổ sung tài liệu lệnh matrix tại `docs/hackathon/test-commands.md`.
- [x] Đã có bằng chứng benchmark live online/offline trên môi trường chạy thật (`round2-live-postdeploy-timeout06-cache`, `round2-matrix-final-20260401`).

## 3) Kế hoạch thực thi theo ngày

## Ngày 1 (30/03/2026) - Chốt contract liên thông
Mục tiêu: Đóng băng contract kỹ thuật để tránh sửa dây chuyền.
- [x] Chốt schema chung: `policy_action`, `fallback_used`, `source_errors`, `attributions`. (đã chốt `attributions` là canonical; giữ `attribution` singular ở chế độ tương thích ngược)
- [x] Chốt schema consent: `consent_version`, `accepted_at`, `user_id`. (`user_id` đã vào response contract)
- [x] Chốt cờ runtime: `external_ddi_enabled`.
- [x] Chốt KPI Gate và tiêu chí Go/No-Go.
Tệp liên quan:
- `docs/implementation-plan/day1-unified-contract-2026-03-30.md`
- `services/api/src/clara_api/schemas.py`
- `services/ml/src/clara_ml/main.py`
- `services/ml/src/clara_ml/agents/careguard.py`
- `services/api/src/clara_api/api/v1/endpoints/system.py`
Lệnh kiểm tra:
```bash
rg -n "policy_action|fallback_used|source_errors|attributions|consent_version|accepted_at|user_id|external_ddi_enabled" services/api/src services/ml/src apps/web/lib || \
grep -RIn "policy_action\|fallback_used\|source_errors\|attributions\|consent_version\|accepted_at\|user_id\|external_ddi_enabled" services/api/src services/ml/src apps/web/lib
```
Tiêu chí hoàn thành:
- [x] Có tài liệu contract thống nhất, không mâu thuẫn giữa API/ML/Web.
- [x] Có quy ước tương thích ngược (`attribution` singular -> `attributions` canonical).

Cập nhật triển khai thực tế (30/03/2026 - buổi tối):
- [x] Nâng cấp landing page theo hướng hiện đại hơn với motif y tế + kết nối dữ liệu (`clara-medical-visual`, `clara-data-orbit`), thay icon/nhấn thị giác thay cho emoji.
- [x] Sửa lỗi giao diện: tăng line-height/letter-spacing cho tiêu đề lớn, dọn duplicate CSS selector gây override khó kiểm soát, sửa tương phản vùng sáng khi dark mode.
- [x] Deploy frontend lên server `36.50.26.18` (docker compose rebuild service `web`), kiểm tra container chạy ổn và `HTTP 200` tại `http://127.0.0.1:3100/`.

## Ngày 2 (31/03/2026) - Migration DB + Model Consent
Mục tiêu: Có lưu vết consent dạng persistent.
- [x] Tạo migration consent (hiện tại là `20260330_0004_user_consent_logs.py`).
- [ ] Thêm model `ConsentLog`. (partial: đã có model `UserConsent` phục vụ consent audit)
- [x] Thêm DTO consent trong schema.
Tệp liên quan:
- `services/api/alembic/versions/20260330_0004_user_consent_logs.py`
- `services/api/src/clara_api/db/models.py`
- `services/api/src/clara_api/schemas.py`
Lệnh kiểm tra:
```bash
cd services/api
alembic upgrade head
```
Tiêu chí hoàn thành:
- [ ] Tạo được bảng `consent_logs`. (partial: hiện dùng bảng `user_consents`)
- [ ] Import schema không lỗi. (chưa có bằng chứng chạy lệnh trong checklist)

## Ngày 3 (01/04/2026) - Disclaimer Gate + Consent API
Mục tiêu: Bắt buộc đồng ý miễn trừ trách nhiệm trước khi dùng tính năng y tế.
- [x] Thêm `POST /auth/consent`.
- [x] Thêm `GET /auth/consent-status`.
- [x] Chặn endpoint nhạy cảm nếu chưa consent (HTTP 428).
Tệp liên quan:
- `services/api/src/clara_api/api/v1/endpoints/auth.py`
- `services/api/src/clara_api/api/v1/endpoints/careguard.py`
- `services/api/src/clara_api/schemas.py`
Lệnh kiểm tra:
```bash
pytest -q services/api/tests -k "consent or auth"
```
Tiêu chí hoàn thành:
- [x] User chưa consent bị chặn đúng (đã có `ensure_medical_disclaimer_consent` trả `HTTP_428_PRECONDITION_REQUIRED`).
- [ ] User đã consent đi qua luồng được bình thường. (chưa có bằng chứng test run trong checklist)

## Ngày 4 (02/04/2026) - Khóa pháp lý chatbot (hard guard)
Mục tiêu: Cưỡng chế backend, không dựa riêng vào prompt.
- [x] Tạo policy contract cưỡng chế `allow/warn/block/escalate` trên backend response (ML chat/research).
- [x] Áp guard vào `/v1/chat/routed`.
- [x] Áp guard vào `/v1/research/tier2` (block kê đơn/chẩn đoán/liều; escalation riêng cho emergency query).
- [x] Giữ fallback an toàn ở API chat khi ML lỗi.
Tệp liên quan:
- `services/ml/src/clara_ml/main.py`
- `services/ml/src/clara_ml/agents/careguard.py`
- `services/api/src/clara_api/api/v1/endpoints/chat.py`
- `services/ml/src/clara_ml/routing.py`
Lệnh kiểm tra:
```bash
pytest -q services/ml/tests/test_main_api.py -k "chat or emergency"
pytest -q services/api/tests/test_chat_proxy.py
```
Tiêu chí hoàn thành:
- [x] 10/10 prompt bẫy liều/chẩn đoán/kê đơn bị từ chối đúng policy (pre-check qua artifact dataset).

## Ngày 5 (03/04/2026) - Cứng hóa fallback DDI (>=50 cặp)
Mục tiêu: API ngoài lỗi vẫn cảnh báo được.
- [x] Tách local DDI rules ra file JSON versioned (`careguard_ddi_rules.v1.json`).
- [x] Mở rộng tối thiểu 50 cặp DDI phổ biến, ưu tiên mức nặng. (hiện tại 62 cặp)
- [x] Chuẩn hóa key cặp thuốc đối xứng (dùng `_pair_key` + merge theo cặp đã sort).
Tệp liên quan:
- `services/ml/src/clara_ml/agents/careguard.py`
- `services/ml/src/clara_ml/clients/drug_sources.py`
- `services/ml/src/clara_ml/nlp/seed_data/local_ddi_rules_v1.json` (new)
Lệnh kiểm tra:
```bash
pytest -q services/ml/tests/test_careguard_agent.py -k "ddi"
```
Tiêu chí hoàn thành:
- [x] Có bộ test nội bộ cho offline fallback (50 case) và runner KPI static tạo đầy đủ artifact.

## Ngày 6 (04/04/2026) - Runtime toggle không cần restart
Mục tiêu: Bật/tắt external DDI ngay tại demo.
- [x] Thêm `external_ddi_enabled` vào control tower config.
- [x] Wire API sang ML để đọc cờ runtime.
- [x] Ghi log nguồn cờ: runtime hay env (`external_ddi_flag_source`).
Tệp liên quan:
- `services/api/src/clara_api/api/v1/endpoints/system.py`
- `services/api/src/clara_api/core/control_tower/defaults.py`
- `services/api/src/clara_api/schemas.py`
- `services/ml/src/clara_ml/config.py`
- `services/ml/src/clara_ml/main.py`
Lệnh kiểm tra:
```bash
pytest -q services/api/tests/test_system_control_tower_config.py
pytest -q services/ml/tests -k "toggle or careguard"
```
Tiêu chí hoàn thành:
- [x] Toggle có hiệu lực runtime qua payload/config path (đã có test config + metadata source).

## Ngày 7 (05/04/2026) - VN Drug Dictionary (>=100 biệt dược)
Mục tiêu: Bản địa hóa mapping thuốc Việt Nam.
- [x] Tạo `vn_drug_dictionary.json` ít nhất 100 bản ghi (hiện tại 217 record alias).
- [x] Tích hợp mapping vào pipeline careguard (ML normalize + active ingredients expansion).
- [x] Confidence thấp thì bắt buộc manual confirm (API scan/import guard + UI confirm step).
Tệp liên quan:
- `services/ml/src/clara_ml/nlp/seed_data/vn_drug_dictionary.json` (new)
- `services/api/src/clara_api/api/v1/endpoints/careguard.py`
- `services/ml/src/clara_ml/agents/careguard.py`
Lệnh kiểm tra:
```bash
pytest -q services/ml/tests -k "dictionary or mapping"
pytest -q services/api/tests -k "careguard"
```
Tiêu chí hoàn thành:
- [ ] Mapping đúng >90% trên bộ test nội bộ (cần chạy benchmark live để chốt tỷ lệ).

## Ngày 8 (06/04/2026) - Hợp nhất luồng /careguard và /selfmed
Mục tiêu: Một nguồn dữ liệu thật, tránh local workflow lệch.
- [x] Refactor `/careguard` dùng chung backend truth với `/selfmed`.
- [x] Bỏ localStorage làm nguồn chính cho luồng thuốc.
- [x] Chỉnh copy/navigation để tránh hiểu nhầm nguồn dữ liệu.
Tệp liên quan:
- `apps/web/app/careguard/page.tsx`
- `apps/web/app/selfmed/page.tsx`
- `apps/web/lib/selfmed.ts`
- `apps/web/lib/careguard.ts`
- `apps/web/lib/navigation.config.ts`
Lệnh kiểm tra:
```bash
cd apps/web
npm run dev
```
Tiêu chí hoàn thành:
- [x] Thêm thuốc từ selfmed, refresh careguard vẫn thấy đúng (đọc chung API `/careguard/cabinet`).

## Ngày 9 (07/04/2026) - Manual Confirm UX cho người lớn tuổi
Mục tiêu: Giảm lỗi OCR và tăng khả dụng.
- [x] Bắt buộc xác nhận từng item trước khi lưu.
- [x] Tăng cỡ chữ, tăng tương phản, nút lớn, focus rõ.
- [x] Cảnh báo rõ cho item confidence thấp.
- [x] Ghi chú roadmap TTS (chưa triển khai ở vòng 2).
Tệp liên quan:
- `apps/web/app/selfmed/page.tsx`
Lệnh kiểm tra:
```bash
cd apps/web
npm run dev
```
Tiêu chí hoàn thành:
- [x] Item confidence thấp không thể auto-commit.
- [x] Luồng dùng bàn phím chạy ổn.

## Ngày 10 (08/04/2026) - Dựng bộ Demo Artifact
Mục tiêu: Có bằng chứng cứng khi chấm.
- [x] Tạo cây thư mục artifact theo `run_id`.
- [x] Tạo `data-manifest.json` (source/license/checksum/date).
- [x] Tạo khung `test-report`, `fallback-proof`, `kpi-report`.
Tệp mới:
- `artifacts/round2/<run_id>/data-manifest/data-manifest.json`
- `artifacts/round2/<run_id>/test-report/test-report.md`
- `artifacts/round2/<run_id>/fallback-proof/README.md`
- `artifacts/round2/<run_id>/kpi-report/kpi-report.md`
Lệnh kiểm tra:
```bash
find artifacts/round2 -maxdepth 4 -type f | sort
```
Tiêu chí hoàn thành:
- [x] Team có đầy đủ khung để điền số liệu thật.

## Ngày 11 (09/04/2026) - Chạy KPI lần 1 (Online + Offline)
Mục tiêu: Có baseline đo được thật.
- [x] Chuẩn bị `ddi-goldset.jsonl`.
- [x] Chuẩn bị `refusal-scenarios.jsonl`.
- [x] Chuẩn bị `fallback-scenarios.jsonl`.
- [x] Chuẩn bị `latency-scenarios.jsonl`.
- [x] Chạy benchmark online. (evidence: `artifacts/round2/round2-live-20260401b/*`)
- [x] Chạy benchmark offline fault injection. (qua runtime toggle trong cùng run)
Lệnh kiểm tra:
```bash
bash scripts/setup/check-env.sh
make docker-app-up
make docker-app-ps
make test
pytest -q services/api/tests/test_chat_proxy.py services/api/tests/test_p2_proxy_endpoints.py -k fallback
pytest -q services/ml/tests/test_careguard_agent.py services/ml/tests/test_main_api.py -k "careguard or emergency or metrics"
docker compose --env-file .env -f deploy/docker/docker-compose.app.yml stop ml
docker compose --env-file .env -f deploy/docker/docker-compose.app.yml start ml
```
Tiêu chí hoàn thành:
- [x] Có báo cáo KPI lần 1 cho 4 chỉ số chính (live mode).  
  Kết quả snapshot run `round2-live-postdeploy-20260401`:  
  - DDI precision: `100% (50/50)`  
  - Fallback success: `100% (4/4)`  
  - Refusal compliance: `100% (10/10)`  
  - Latency online p95: `3.670s` (chưa đạt ngưỡng `< 3.0s`)  
  - Latency offline p95: `0.121s` (đạt ngưỡng `< 0.5s`)

## Ngày 12 (10/04/2026) - Ngày vá gap KPI
Mục tiêu: Sửa toàn bộ khoảng cách dưới ngưỡng.
- [x] Sửa false negative ở legal guard. (evidence: `services/ml/src/clara_ml/main.py`, `services/ml/tests/test_main_api.py`)
- [x] Sửa critical miss ở DDI fallback. (evidence: `services/ml/src/clara_ml/agents/careguard.py`, `services/ml/tests/test_careguard_agent.py`)
- [x] Giảm latency ở endpoint nóng. (evidence: `round2-live-postdeploy-timeout06-cache` đạt gate)
- [x] Chuẩn hóa metadata fallback/source errors. (evidence: `services/api/src/clara_api/core/attribution.py`, `services/api/src/clara_api/api/v1/endpoints/chat.py`, `services/api/src/clara_api/api/v1/endpoints/research.py`, `services/api/tests/test_attribution_utils.py`)
Tệp liên quan:
- `services/ml/src/clara_ml/main.py`
- `services/ml/src/clara_ml/agents/careguard.py`
- `services/ml/src/clara_ml/clients/drug_sources.py`
- `services/api/src/clara_api/api/v1/endpoints/chat.py`
- `services/api/src/clara_api/api/v1/endpoints/system.py`
Lệnh kiểm tra:
```bash
make test
```
Tiêu chí hoàn thành:
- [x] KPI đạt ngưỡng nội bộ. (evidence: `round2-live-postdeploy-timeout06-cache`)

## Ngày 13 (11/04/2026) - Freeze + UAT + Demo Drill
Mục tiêu: Chốt release candidate.
- [x] Có script full matrix (`scripts/demo/run_round2_matrix.sh`) để chạy 1 lệnh.
- [x] Chạy full matrix lần 2. (evidence: `round2-matrix-final-20260401`)
- [x] Điền artifact pack đầy đủ. (evidence: `artifacts/round2/round2-final-canonical-20260402-110603/{data-manifest,test-report,fallback-proof,kpi-report,go-no-go}/*`)
- [x] Chạy demo script Case A/B/C. (evidence: `scripts/demo/run_round2_demo_cases.sh`, run `artifacts/round2/round2-final-canonical-20260402-110603/demo-cases/*`)
- [x] Chốt `go-no-go.md`. (evidence: `artifacts/round2/round2-final-canonical-20260402-110603/go-no-go/go-no-go.md`)
Lệnh kiểm tra:
```bash
make test
cd apps/web && npm run dev
```
Tiêu chí hoàn thành:
- [x] Có bằng chứng fallback thật. (evidence: `round2-matrix-final-20260401-offline/fallback-proof/*`)
- [x] Có test report và KPI report final. (evidence: `round2-matrix-final-20260401-{online,offline}/`)

## Ngày 14 (12/04/2026) - Buffer + Rehearsal
Mục tiêu: Không thêm tính năng mới, chỉ hardening.
- [ ] Sửa blocker cuối.
- [x] Rà lại legal text và disclaimer trên UI. (evidence: `artifacts/round2/round2-final-canonical-20260402-110603/legal-attribution-review/legal-attribution-review.md`)
- [x] Rà source attribution trên cảnh báo/chat. (evidence: `artifacts/round2/round2-final-canonical-20260402-110603/legal-attribution-review/legal-attribution-review.json`)
- [ ] Rehearsal pitch 3 lần đúng kịch bản.
Lệnh kiểm tra:
```bash
make test
```
Tiêu chí hoàn thành:
- [x] Sẵn sàng demo Online/Offline không vỡ luồng. (evidence: `artifacts/round2/round2-final-canonical-20260402-110603/readiness/readiness.json`)

## 4) KPI Gate bắt buộc trước demo
- [x] Gate evaluator tự động đã được triển khai trong `run_hackathon_kpis.py`.
- [x] DDI precision (proxy, internal) >= 0.95. (`round2-live-postdeploy-timeout06-cache`: 1.00)
- [x] Fallback success rate >= 1.00. (`round2-live-postdeploy-timeout06-cache`: 1.00)
- [x] Refusal compliance rate >= 1.00. (`round2-live-postdeploy-timeout06-cache`: 1.00)
- [x] p95 Online (latency KPI runner) < 3.0s. (`round2-live-postdeploy-timeout06-cache`: 0.185s)
- [x] p95 Offline fallback (latency KPI runner) < 0.5s. (`round2-live-postdeploy-20260401`: 0.121s)

## 5) Kịch bản demo cơ khí (10 phút)
- [x] Case A Online: Panadol Extra + Warfarin -> map hoạt chất -> cảnh báo đỏ -> chatbot giải thích + hiển thị nguồn. (evidence: `artifacts/round2/round2-final-canonical-20260402-110603/demo-cases/case-a-online.json`)
- [x] Case B Offline: tắt external DDI bằng runtime toggle -> fallback local rules -> vẫn cảnh báo đỏ. (evidence: `artifacts/round2/round2-final-canonical-20260402-110603/demo-cases/case-b-offline-fallback.json`)
- [x] Case C Legal trap: hỏi liều/chẩn đoán/kê đơn -> chatbot từ chối đúng policy. (evidence: `artifacts/round2/round2-final-canonical-20260402-110603/demo-cases/case-c-legal-trap.json`)

## 6) Bảng phân công (điền tên)
- [x] `GOV-SAFE` Owner Safety/Legal Guard (ML hard guard + policy contract)
- [x] `GOV-API` Owner API/DB Consent (auth/consent/system config)
- [x] `GOV-CAREGUARD` Owner DDI Fallback + VN Dictionary
- [x] `GOV-WEB` Owner Web Unify + UX Manual Confirm
- [x] `GOV-KPI` Owner Test/KPI/Artifacts
- [x] `GOV-OPS` Owner Deploy/Runtime + Demo Script support

## 7) Mẫu standup hằng ngày (15 phút)
- [x] Hôm qua đã xong gì? (bắt buộc kèm bằng chứng: file + command + artifact path)
- [x] Hôm nay chốt gì? (nêu rõ file/endpoint + ETA)
- [x] Blocker nào cần mở ngay? (đính kèm owner + SLA xử lý)
- [x] Rủi ro nào có thể làm vỡ demo? (gắn mức độ + phương án giảm thiểu)

## 8) Kỷ luật triển khai trong 14 ngày
- [ ] Không mở rộng scope ngoài Round 2.
- [ ] Mỗi PR phải có test hoặc giải trình rõ lý do chưa test.
- [ ] Mỗi thay đổi legal/policy phải cập nhật artifact report.
- [ ] Nếu KPI dưới ngưỡng, ưu tiên sửa backend/safety trước UI polish.

## 9) P1 nếu còn thời gian
- [x] Thêm Update Medication endpoint (`PATCH /careguard/cabinet/items/{id}`).
- [x] Tăng coverage test cho flow mới.
- [x] Gắn source attribution rõ ràng vào payload chatbot/careguard.

## 10) P2 sau cuộc thi
- [ ] Mobile native hoàn chỉnh.
- [ ] Smart reminder scheduler.
- [ ] Caregiver dashboard.
- [ ] Encryption-at-rest và column-level encryption sâu hơn.
