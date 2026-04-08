# CLARA Research Flow Deep-Dive (2026-03-29)

## Phạm vi
- File này tập trung vào luồng `Research` và contract output.
- Chỉ dùng dẫn chiếu nội bộ theo đường dẫn file trong repo.

## (1) Canonical flow Clara Research từ Mermaid/docs

### 1.1 Canonical graph (nguồn chuẩn hiện có)
- Mermaid runtime graph: `docs/architecture/clara-diagrams.html`
- Runtime spec chi tiết: `docs/architecture/clara-runtime-and-routing.md`
- Kiến trúc platform và policy semantics: `docs/architecture/clara-platform-architecture.md`

Ghi chú: repo hiện không có thư mục `docs/mermaid`; sơ đồ Mermaid canonical đang nằm trong `docs/architecture/clara-diagrams.html`.

### 1.2 Chuỗi canonical đã chốt
Theo các tài liệu trên, chuỗi chuẩn là:
1. `Input -> Gateway Rust + Safety Ingress`
2. `Router B1 (Role) -> Router B2 (Intent)`
3. `Planner/Supervisor (LangGraph)`
4. `Retrieval Agents` (đa nguồn/đa phương thức)
5. `Synthesis Node` (draft + claim set)
6. `Verification Node (FIDES-inspired)`
7. `Policy Gate (Rust)` quyết định `allow/warn/block/escalate`
8. `Response + Citation + Audit`

---

## (2) Đối chiếu với triển khai code hiện tại (fact-check + policy gate)

### 2.1 Bảng đối chiếu theo node

| Canonical node | Triển khai hiện tại | Fact-check | Trạng thái |
|---|---|---|---|
| Gateway + ingress | API `research/tier2` nhận payload, merge uploaded docs rồi proxy ML | `services/api/src/clara_api/api/v1/endpoints/research.py`, `services/api/src/clara_api/api/v1/endpoints/ml_proxy.py` | `Partial` |
| Safety ingress (PII/PHI + consent gate) | Có module redact PII ở ML, nhưng không chạy trong `research/tier2` | `services/ml/src/clara_ml/nlp/pii_filter.py`, `services/ml/src/clara_ml/main.py`, `services/ml/src/clara_ml/agents/research_tier2.py` | `Gap` |
| Router B1/B2 cho Research | Router có tồn tại nhưng dùng ở `/v1/chat/routed`; `research/tier2` không đi qua router | `services/ml/src/clara_ml/routing.py`, `services/ml/src/clara_ml/main.py`, `services/ml/src/clara_ml/agents/research_tier2.py` | `Gap` |
| Planner/Supervisor (LangGraph) | `plan_steps` đang là static template; chưa có graph orchestration runtime | `services/ml/src/clara_ml/agents/research_tier2.py` | `Gap` |
| Retrieval agents | Có hybrid retrieval nội bộ + external scientific (PubMed/Europe PMC khi low-context) | `services/ml/src/clara_ml/rag/pipeline.py`, `services/ml/src/clara_ml/rag/retriever.py` | `Partial -> Good` |
| Synthesis node | Có synthesis qua `RagPipelineP1.run()` | `services/ml/src/clara_ml/rag/pipeline.py` | `Good` |
| Verification node | Module FIDES-lite có sẵn, nhưng luồng Research không gọi; chỉ chat gọi verifier | `services/ml/src/clara_ml/factcheck/fides_lite.py`, `services/ml/src/clara_ml/main.py`, `services/ml/src/clara_ml/agents/research_tier2.py` | `Gap` |
| Policy gate (`allow/warn/block/escalate`) | Chưa có policy gate thực thi cho Research; không trả `policy_action` | `services/ml/src/clara_ml/agents/research_tier2.py`, `services/api/src/clara_api/schemas.py`, `apps/web/lib/research.ts` | `Gap` |
| Response + citation + audit | Có `answer/citations/metadata/plan_steps`; chưa có `verification_status/policy_action`; chưa thấy audit event chuẩn policy | `services/ml/src/clara_ml/agents/research_tier2.py`, `services/api/src/clara_api/db/models.py`, `apps/web/lib/research.ts` | `Partial` |

### 2.2 Policy gate fact-check (điểm quan trọng)
- Spec yêu cầu policy gate nằm ở lớp runtime system và quyết định cuối: `docs/architecture/clara-runtime-and-routing.md`, `docs/architecture/clara-platform-architecture.md`.
- Luồng Research hiện tại (`/api/v1/research/tier2` -> `/v1/research/tier2`) chỉ trả nội dung tổng hợp + citations, chưa có policy decision object: `services/api/src/clara_api/api/v1/endpoints/research.py`, `services/ml/src/clara_ml/agents/research_tier2.py`.
- Contract frontend Research cũng chưa parse/hiển thị `verification_status` và `policy_action`: `apps/web/lib/research.ts`.

---

## (3) Danh sách gap ưu tiên P0/P1/P2

### P0 (an toàn + contract bắt buộc)
1. Thiếu `verification_status` trong output Research dù có verifier module.
- Ảnh hưởng: không có bằng chứng pass/warn/fail độc lập trước khi trả lời.
- Dẫn chiếu: `services/ml/src/clara_ml/factcheck/fides_lite.py`, `services/ml/src/clara_ml/agents/research_tier2.py`, `docs/implementation-plan/workstream-clara-research.md`.

2. Thiếu `policy_action` chuẩn `allow/warn/block/escalate` ở Research flow.
- Ảnh hưởng: không có gate quyết định cuối theo risk.
- Dẫn chiếu: `docs/architecture/clara-runtime-and-routing.md`, `docs/implementation-plan/workstream-clara-research.md`, `services/ml/src/clara_ml/agents/research_tier2.py`.

3. Chuỗi cứng `route -> retrieve -> synthesize -> verify -> policy -> respond` chưa được enforce cho Research.
- Ảnh hưởng: có thể trả lời dù verify/policy chưa chạy.
- Dẫn chiếu: `docs/implementation-plan/runtime-alignment-gap-report-2026-03-25-v2.md`, `services/ml/src/clara_ml/agents/research_tier2.py`.

### P1 (độ tin cậy vận hành + governance)
1. Research flow chưa có B1/B2 router runtime riêng theo taxonomy docs.
- Dẫn chiếu: `docs/architecture/clara-runtime-and-routing.md`, `services/ml/src/clara_ml/routing.py`, `services/ml/src/clara_ml/agents/research_tier2.py`.

2. Thiếu audit event chuẩn cho policy/verification outcome trong data model API.
- Dẫn chiếu: `services/api/src/clara_api/db/models.py`, `docs/architecture/clara-runtime-and-routing.md`.

3. `plan_steps` hiện là static, chưa phải progressive orchestration 5-10-20 thật.
- Dẫn chiếu: `services/ml/src/clara_ml/agents/research_tier2.py`, `docs/implementation-plan/workstream-clara-research.md`.

### P2 (chuẩn hóa tài liệu + UX contract)
1. Vị trí canonical Mermaid chưa tách thành `docs/mermaid/*`, gây lệch tham chiếu tài liệu.
- Dẫn chiếu: `docs/architecture/clara-diagrams.html`.

2. Citation schema còn mềm (parse nhiều biến thể), chưa có strict contract version cho client.
- Dẫn chiếu: `apps/web/lib/research.ts`, `services/ml/src/clara_ml/agents/research_tier2.py`.

---

## (4) Đề xuất contract output chuẩn (`verification_status` / `policy_action` / `citations`)

### 4.1 Contract đề xuất (v1)

```json
{
  "answer": "string",
  "confidence": 0.0,
  "verification_status": {
    "state": "verified|partial|unverified|failed",
    "verifier_stage": "fides-lite-v1",
    "supported_claims": 0,
    "total_claims": 0,
    "unsupported_claims": ["string"],
    "evidence_count": 0,
    "confidence": 0.0,
    "note": "string"
  },
  "policy_action": {
    "action": "allow|warn|block|escalate",
    "risk_level": "low|medium|high|critical",
    "reason_codes": ["NO_EVIDENCE", "LOW_SUPPORT_RATIO", "SOURCE_CONFLICT", "HIGH_RISK_CLAIM"],
    "human_review_required": false
  },
  "citations": [
    {
      "id": "string",
      "title": "string",
      "source": "pubmed|europepmc|uploaded|byt|who|other",
      "url": "string",
      "snippet": "string",
      "year": "string",
      "supports_claim_ids": ["claim-1"]
    }
  ],
  "metadata": {
    "contract_version": "research-response-v1",
    "pipeline": "string",
    "fallback_used": false
  }
}
```

### 4.2 Quy tắc ra quyết định tối thiểu
1. `allow`
- Điều kiện: `verification_status.state=verified`, `evidence_count>0`, có citations hợp lệ.

2. `warn`
- Điều kiện: `partial` hoặc support ratio trung bình; vẫn trả lời nhưng bắt buộc cảnh báo.

3. `block`
- Điều kiện: `failed/unverified` + claim rủi ro cao hoặc không có evidence cho kết luận trọng yếu.

4. `escalate`
- Điều kiện: tín hiệu nguy cơ lâm sàng cao hoặc conflict lớn cần clinician review.

### 4.3 Mapping nhanh từ triển khai hiện tại -> contract v1
- `answer` dùng trực tiếp từ `services/ml/src/clara_ml/agents/research_tier2.py`.
- `citations` dùng danh sách hiện có nhưng chuẩn hóa key (`id/source/supports_claim_ids`).
- `verification_status` sinh từ `run_fides_lite(...)` (đang có module, cần gắn vào flow Research).
- `policy_action` tính từ `verification_status + risk rule` trước khi trả về API.

### 4.4 Điều chỉnh tối thiểu ở lớp client
- `apps/web/lib/research.ts` cần parse thêm `verification_status`, `policy_action` và hiển thị badge/risk state.
- `services/api/src/clara_api/schemas.py` cần model hóa response contract để chặn payload lệch schema.

