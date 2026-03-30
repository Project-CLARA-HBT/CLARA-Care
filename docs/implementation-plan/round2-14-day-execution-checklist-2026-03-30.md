# Checklist Triển Khai 14 Ngày - Vòng 2 (30/03/2026 -> 12/04/2026)

## 1) Khóa mục tiêu Vòng 2 (không đổi)
- [ ] Một câu chuyện duy nhất: Quản lý tủ thuốc + Cảnh báo DDI + Chatbot giải thích an toàn thuốc.
- [ ] Demo chạy được cả Online và Offline Fallback.
- [ ] Chatbot không vượt ranh giới pháp lý: không chẩn đoán, không kê đơn, không hướng dẫn liều dùng.

## 2) Khóa ưu tiên
- [ ] P0 bắt buộc xong trước demo.
- [ ] P1 làm khi còn thời gian.
- [ ] P2 để sau cuộc thi.

## 3) Kế hoạch thực thi theo ngày

## Ngày 1 (30/03/2026) - Chốt contract liên thông
Mục tiêu: Đóng băng contract kỹ thuật để tránh sửa dây chuyền.
- [ ] Chốt schema chung: `policy_action`, `fallback_used`, `source_errors`, `attributions`.
- [ ] Chốt schema consent: `consent_version`, `accepted_at`, `user_id`.
- [ ] Chốt cờ runtime: `external_ddi_enabled`.
- [ ] Chốt KPI Gate và tiêu chí Go/No-Go.
Tệp liên quan:
- `services/api/src/clara_api/schemas.py`
- `services/ml/src/clara_ml/main.py`
- `services/ml/src/clara_ml/agents/careguard.py`
- `services/api/src/clara_api/api/v1/endpoints/system.py`
Lệnh kiểm tra:
```bash
rg -n "policy_action|fallback_used|source_errors|attributions|consent_version|external_ddi_enabled" services/api/src services/ml/src
```
Tiêu chí hoàn thành:
- [ ] Có tài liệu contract thống nhất, không mâu thuẫn giữa API/ML/Web.

## Ngày 2 (31/03/2026) - Migration DB + Model Consent
Mục tiêu: Có lưu vết consent dạng persistent.
- [ ] Tạo migration mới: `20260330_0004_consent_audit_medication_update.py`.
- [ ] Thêm model `ConsentLog`.
- [ ] Thêm DTO consent trong schema.
Tệp liên quan:
- `services/api/alembic/versions/20260330_0004_consent_audit_medication_update.py` (new)
- `services/api/src/clara_api/db/models.py`
- `services/api/src/clara_api/schemas.py`
Lệnh kiểm tra:
```bash
cd services/api
alembic upgrade head
```
Tiêu chí hoàn thành:
- [ ] Tạo được bảng `consent_logs`.
- [ ] Import schema không lỗi.

## Ngày 3 (01/04/2026) - Disclaimer Gate + Consent API
Mục tiêu: Bắt buộc đồng ý miễn trừ trách nhiệm trước khi dùng tính năng y tế.
- [ ] Thêm `POST /auth/consent`.
- [ ] Thêm `GET /auth/consent-status`.
- [ ] Chặn endpoint nhạy cảm nếu chưa consent (HTTP 428).
Tệp liên quan:
- `services/api/src/clara_api/api/v1/endpoints/auth.py`
- `services/api/src/clara_api/api/v1/endpoints/careguard.py`
- `services/api/src/clara_api/schemas.py`
Lệnh kiểm tra:
```bash
pytest -q services/api/tests -k "consent or auth"
```
Tiêu chí hoàn thành:
- [ ] User chưa consent bị chặn đúng.
- [ ] User đã consent đi qua luồng được bình thường.

## Ngày 4 (02/04/2026) - Khóa pháp lý chatbot (hard guard)
Mục tiêu: Cưỡng chế backend, không dựa riêng vào prompt.
- [ ] Tạo policy engine `allow/warn/block/escalate`.
- [ ] Áp guard vào `/v1/chat/routed`.
- [ ] Áp guard vào `/v1/research/tier2`.
- [ ] Giữ fallback an toàn ở API chat khi ML lỗi.
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
- [ ] 10/10 prompt bẫy liều/chẩn đoán/kê đơn bị từ chối đúng policy.

## Ngày 5 (03/04/2026) - Cứng hóa fallback DDI (>=50 cặp)
Mục tiêu: API ngoài lỗi vẫn cảnh báo được.
- [ ] Tách local DDI rules ra file JSON versioned.
- [ ] Mở rộng tối thiểu 50 cặp DDI phổ biến, ưu tiên mức nặng.
- [ ] Chuẩn hóa key cặp thuốc đối xứng.
Tệp liên quan:
- `services/ml/src/clara_ml/agents/careguard.py`
- `services/ml/src/clara_ml/clients/drug_sources.py`
- `services/ml/src/clara_ml/nlp/seed_data/local_ddi_rules_v1.json` (new)
Lệnh kiểm tra:
```bash
pytest -q services/ml/tests/test_careguard_agent.py -k "ddi"
```
Tiêu chí hoàn thành:
- [ ] Offline vẫn trả cảnh báo đúng trên bộ test nội bộ.

## Ngày 6 (04/04/2026) - Runtime toggle không cần restart
Mục tiêu: Bật/tắt external DDI ngay tại demo.
- [ ] Thêm `external_ddi_enabled` vào control tower config.
- [ ] Wire API sang ML để đọc cờ runtime.
- [ ] Ghi log nguồn cờ: runtime hay env.
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
- [ ] Toggle có hiệu lực ngay, không restart service.

## Ngày 7 (05/04/2026) - VN Drug Dictionary (>=100 biệt dược)
Mục tiêu: Bản địa hóa mapping thuốc Việt Nam.
- [ ] Tạo `vn_drug_dictionary.json` ít nhất 100 bản ghi.
- [ ] Tích hợp mapping vào pipeline careguard.
- [ ] Confidence thấp thì bắt buộc manual confirm.
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
- [ ] Mapping đúng >90% trên bộ test nội bộ.

## Ngày 8 (06/04/2026) - Hợp nhất luồng /careguard và /selfmed
Mục tiêu: Một nguồn dữ liệu thật, tránh local workflow lệch.
- [ ] Refactor `/careguard` dùng chung backend truth với `/selfmed`.
- [ ] Bỏ localStorage làm nguồn chính.
- [ ] Chỉnh navigation nếu cần.
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
- [ ] Thêm thuốc từ selfmed, refresh careguard vẫn thấy đúng.

## Ngày 9 (07/04/2026) - Manual Confirm UX cho người lớn tuổi
Mục tiêu: Giảm lỗi OCR và tăng khả dụng.
- [ ] Bắt buộc xác nhận từng item trước khi lưu.
- [ ] Tăng cỡ chữ, tăng tương phản, nút lớn, focus rõ.
- [ ] Cảnh báo rõ cho item confidence thấp.
- [ ] Ghi chú roadmap TTS (chưa triển khai ở vòng 2).
Tệp liên quan:
- `apps/web/app/selfmed/page.tsx`
Lệnh kiểm tra:
```bash
cd apps/web
npm run dev
```
Tiêu chí hoàn thành:
- [ ] Item confidence thấp không thể auto-commit.
- [ ] Luồng dùng bàn phím chạy ổn.

## Ngày 10 (08/04/2026) - Dựng bộ Demo Artifact
Mục tiêu: Có bằng chứng cứng khi chấm.
- [ ] Tạo cây thư mục artifact theo `run_id`.
- [ ] Tạo `data-manifest.json` (source/license/checksum/date).
- [ ] Tạo khung `test-report`, `fallback-proof`, `kpi-report`.
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
- [ ] Team có đầy đủ khung để điền số liệu thật.

## Ngày 11 (09/04/2026) - Chạy KPI lần 1 (Online + Offline)
Mục tiêu: Có baseline đo được thật.
- [ ] Chuẩn bị `ddi-goldset.jsonl`.
- [ ] Chuẩn bị `refusal-scenarios.jsonl`.
- [ ] Chuẩn bị `fallback-scenarios.jsonl`.
- [ ] Chuẩn bị `latency-scenarios.jsonl`.
- [ ] Chạy benchmark online.
- [ ] Chạy benchmark offline fault injection.
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
- [ ] Có báo cáo KPI lần 1 cho 4 chỉ số chính.

## Ngày 12 (10/04/2026) - Ngày vá gap KPI
Mục tiêu: Sửa toàn bộ khoảng cách dưới ngưỡng.
- [ ] Sửa false negative ở legal guard.
- [ ] Sửa critical miss ở DDI fallback.
- [ ] Giảm latency ở endpoint nóng.
- [ ] Chuẩn hóa metadata fallback/source errors.
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
- [ ] KPI đạt ngưỡng nội bộ.

## Ngày 13 (11/04/2026) - Freeze + UAT + Demo Drill
Mục tiêu: Chốt release candidate.
- [ ] Chạy full matrix lần 2.
- [ ] Điền artifact pack đầy đủ.
- [ ] Chạy demo script Case A/B/C.
- [ ] Chốt `go-no-go.md`.
Lệnh kiểm tra:
```bash
make test
cd apps/web && npm run dev
```
Tiêu chí hoàn thành:
- [ ] Có bằng chứng fallback thật.
- [ ] Có test report và KPI report final.

## Ngày 14 (12/04/2026) - Buffer + Rehearsal
Mục tiêu: Không thêm tính năng mới, chỉ hardening.
- [ ] Sửa blocker cuối.
- [ ] Rà lại legal text và disclaimer trên UI.
- [ ] Rà source attribution trên cảnh báo/chat.
- [ ] Rehearsal pitch 3 lần đúng kịch bản.
Lệnh kiểm tra:
```bash
make test
```
Tiêu chí hoàn thành:
- [ ] Sẵn sàng demo Online/Offline không vỡ luồng.

## 4) KPI Gate bắt buộc trước demo
- [ ] DDI Precision tổng >= 0.92.
- [ ] DDI Precision nhóm High/Critical >= 0.95.
- [ ] Critical miss = 0.
- [ ] Fallback Success Rate >= 0.98.
- [ ] Refusal Compliance (unsafe) >= 0.98.
- [ ] Refusal Compliance nhóm critical unsafe = 1.00.
- [ ] p95 Online: chat <= 4s, careguard <= 3s, research <= 8s.
- [ ] p95 Offline fallback: chat/research <= 2s.

## 5) Kịch bản demo cơ khí (10 phút)
- [ ] Case A Online: Panadol Extra + Warfarin -> map hoạt chất -> cảnh báo đỏ -> chatbot giải thích + hiển thị nguồn.
- [ ] Case B Offline: tắt external DDI bằng runtime toggle -> fallback local rules -> vẫn cảnh báo đỏ.
- [ ] Case C Legal trap: hỏi liều/chẩn đoán/kê đơn -> chatbot từ chối đúng policy.

## 6) Bảng phân công (điền tên)
- [ ] Owner Safety/Legal Guard: __________
- [ ] Owner API/DB Consent: __________
- [ ] Owner DDI Fallback + VN Dictionary: __________
- [ ] Owner Web Unify + UX Manual Confirm: __________
- [ ] Owner Test/KPI/Artifacts: __________
- [ ] Owner Demo Script + Pitch: __________

## 7) Mẫu standup hằng ngày (15 phút)
- [ ] Hôm qua đã xong gì? (kèm bằng chứng)
- [ ] Hôm nay chốt gì? (nêu rõ file/endpoint)
- [ ] Blocker nào cần mở ngay?
- [ ] Rủi ro nào có thể làm vỡ demo?

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
