# Hackathon Status Truth (Vòng 2) - 2026-04-02

## 1) Mục tiêu tài liệu
- Làm **single source of truth** cho trạng thái thực thi vòng 2.
- Tránh lệch giữa các file checklist/plan rải rác trong `docs/` và `data/docs/`.
- Chỉ ghi trạng thái có bằng chứng trong code/artifact.

## 2) Snapshot tổng quan
- Nguồn checklist chính: `data/docs/implementation-plan/round2-14-day-execution-checklist-2026-03-30.md`
- Tổng checkboxes hiện tại:
  - Done: **92**
  - Chưa done: **24**
- Trạng thái chung:
  - P0: phần lớn đã có implementation + artifact.
  - P1: đã có implementation chính.
  - P2: chưa làm (đúng phạm vi “sau cuộc thi”).

## 3) Trạng thái theo hạng mục ưu tiên

### 3.1 P0 (bắt buộc trước demo)
1. Khóa pháp lý chatbot (hard guard): **Done**
   - Bằng chứng:
     - `services/ml/src/clara_ml/main.py`
     - `services/api/src/clara_api/api/v1/endpoints/chat.py`
2. Disclaimer gate + consent log: **Done (functional), Partial (naming theo checklist)**
   - Bằng chứng:
     - `services/api/src/clara_api/api/v1/endpoints/auth.py`
     - `services/api/src/clara_api/core/consent.py`
     - `services/api/src/clara_api/db/models.py` (`user_consents`)
     - `apps/web/app/careguard/page.tsx`
     - `apps/web/components/selfmed/selfmed-consent-gate.tsx`
   - Ghi chú:
     - Checklist có kỳ vọng `consent_logs`; code thực tế dùng `user_consents`.
3. Fallback DDI cứng hóa: **Done**
   - Bằng chứng:
     - `services/ml/src/clara_ml/nlp/seed_data/careguard_ddi_rules.v1.json` (62 rules)
     - `services/ml/src/clara_ml/agents/careguard.py`
4. Runtime toggle external DDI không restart: **Done**
   - Bằng chứng:
     - `services/api/src/clara_api/api/v1/endpoints/system.py` (`/careguard/runtime`)
     - `services/api/src/clara_api/core/control_tower/defaults.py`
     - `services/ml/src/clara_ml/agents/careguard.py`
5. VN Drug Dictionary: **Done (data), Partial (benchmark mapping >90% chưa chốt canonical)**
   - Bằng chứng:
     - `services/ml/src/clara_ml/nlp/seed_data/vn_drug_dictionary.json` (`record_count: 217`)
6. Hợp nhất /careguard và /selfmed backend truth: **Done**
   - Bằng chứng:
     - `apps/web/lib/selfmed.ts`
     - `apps/web/app/careguard/page.tsx` (khẳng định không dùng localStorage làm source chính)
7. Manual Confirm UX người lớn tuổi: **Done**
   - Bằng chứng:
     - `apps/web/app/careguard/page.tsx`
     - `apps/web/app/selfmed/page.tsx`
8. Demo artifact pack: **Done (canonical run đã khóa)**
   - Bằng chứng:
     - `artifacts/round2/round2-final-canonical-20260402-110603/{data-manifest,test-report,fallback-proof,kpi-report,go-no-go}/*`
     - `artifacts/round2/round2-final-canonical-20260402-110603/demo-cases/*`
     - `artifacts/round2/round2-final-canonical-20260402-110603/legal-attribution-review/*`
9. KPI đo được thật: **Done**
   - Bằng chứng:
     - `scripts/demo/run_hackathon_kpis.py`
     - `artifacts/round2/round2-final-canonical-20260402-110603/go-no-go/go-no-go.json`

### 3.2 P1 (nên làm)
1. Update medication endpoint: **Done**
   - Bằng chứng:
     - `services/api/src/clara_api/api/v1/endpoints/careguard.py` (`PATCH/PUT /cabinet/items/{item_id}`)
     - `services/api/tests/test_careguard_cabinet_endpoints.py`
2. Tăng test coverage flow mới: **Done (mức chức năng chính), Partial (chưa có coverage gate cứng theo % cho module research mới)**
   - Bằng chứng:
     - `services/api/tests/*`
     - `services/ml/tests/*`
3. Source-attribution payload thống nhất: **Done**
   - Bằng chứng:
     - `services/api/src/clara_api/core/attribution.py`
     - `services/api/src/clara_api/api/v1/endpoints/chat.py`
     - `services/api/src/clara_api/api/v1/endpoints/research.py`

### 3.3 P2 (sau cuộc thi)
1. Mobile native hoàn chỉnh: **Chưa done (starter/skeleton)**
   - Bằng chứng:
     - `apps/mobile/README.md` (starter, in-memory session)
2. Smart reminder scheduler: **Chưa done**
3. Caregiver dashboard: **Chưa done**
4. Encryption-at-rest/column-level encryption sâu: **Chưa done**

## 4) Trạng thái theo ngày (Day 13-14 là gap chính)
- Day 1-12: đa số hạng mục đã done.
- Day 13:
  - Done: có matrix script, có go/no-go, có artifact online/offline, có script demo Case A/B/C và đã khóa run canonical `round2-final-canonical-20260402-110603`.
- Day 14:
  - Done: rà legal text + attribution UI final (có artifact review).
  - Done: readiness kỹ thuật online/offline PASS (`readiness/readiness.json`).
  - Chưa done:
    - Rehearsal pitch 3 lần.

## 5) Phần còn skeleton/flow cơ bản cần nêu rõ
1. Mobile app
- Hiện là starter, chưa production-grade.
- Session store đang in-memory.

2. Một số nhánh ML/RAG vẫn dùng stub/fallback-oriented adapter
- `services/ml/src/clara_ml/rag/embedder.py`
- `services/ml/src/clara_ml/nlp/bge_adapter.py`
- `services/ml/src/clara_ml/agents/langgraph_workflow.py`

3. Deep Research plan 2026
- File plan benchmark có nhiều checklist chưa triển khai hết (0/30 checkbox trong chính tài liệu).
- Dùng làm roadmap nâng cấp, chưa thể coi là “đã ship toàn phần”.

## 6) Chênh lệch docs cần dọn ngay
- Hiện đang có split giữa:
  - `docs/hackathon/*`
  - `data/docs/hackathon/*`
- Trạng thái git đang có nhiều file `docs/*` bị delete + `data/docs/*` untracked.
- Rủi ro:
  - Team đọc nhầm nguồn.
  - Báo cáo tiến độ lệch.

## 7) Danh sách việc cần chốt để “xong vòng 2”
1. [x] Chốt **1 run canonical** cho artifact pack (run_id duy nhất).
2. [x] Viết script demo canonical Case A/B/C + lưu artifact kết quả.
3. [x] Chốt legal text + attribution UI vòng cuối (checklist + artifact report).
4. [x] Freeze một file KPI final + go/no-go final để mang đi chấm.
5. [ ] Dọn docs để chỉ còn 1 nhánh tài liệu active.

## 8) Quy ước cập nhật sau tài liệu này
- Mọi thay đổi trạng thái phải kèm:
  - file path đã sửa
  - lệnh test chạy
  - artifact path (nếu có)
- Không đánh dấu Done nếu chưa có bằng chứng.
