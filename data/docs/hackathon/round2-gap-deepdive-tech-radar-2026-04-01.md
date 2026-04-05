# CLARA Vòng 2: Deep-Dive Gap Audit + Tech Radar (2026-04-01)

## 1) Mục tiêu báo cáo
- Chốt các hạng mục còn thiếu để hoàn tất Day 12, Day 13-14 trong checklist hackathon.
- Xác định nguyên nhân gốc (root-cause) và rủi ro vỡ demo.
- Đề xuất công nghệ mới/hot có lợi thực tế cho CLARA (ưu tiên thứ có thể áp dụng ngay, không chỉ “trend”).
- Chuẩn hóa chiến lược keyword theo từng nguồn (VN/EN) để tăng độ chính xác crawl/retrieval.

## 2) Kết luận nhanh (Executive Summary)
- `Day 12` còn thiếu thật ở 3 điểm: legal false negative, critical DDI miss với tên thuốc có liều/dạng bào chế, và metadata `fallback/source_errors` chưa chuẩn hóa xuyên API/ML.
- `Day 13-14` thiếu bằng chứng vận hành: chưa có artifact demo Case A/B/C dạng canonical; parent run artifact chưa đồng nhất chuẩn JSON+MD.
- Bảng owner/standup hiện còn dạng placeholder, chưa ở mức SOP vận hành evidence-first.
- Đã cập nhật cơ chế keyword theo nguồn trong crawler:
  - nguồn VN ưu tiên keyword tiếng Việt,
  - nguồn quốc tế ưu tiên keyword tiếng Anh,
  - hỗ trợ cú pháp `vi:` / `en:` + auto keyword theo source.

---

## 3) Deep-dive Day 12 (3 mục pending)

### 3.1 Legal false negative (hard guard)
**Hiện trạng rủi ro**
- Hard guard có thể bị lách ở ngữ cảnh research phrasing (hỏi kiểu “guideline-based diagnosis...”, “recommended dose...” ).
- Regex hiện tại chưa phủ đủ biến thể tiếng Việt không dấu/tiếng Anh đời thường.

**Root cause chính**
- Logic guard theo `channel` còn có nhánh khiến một số intent nguy hiểm đi qua ở mode research.
- Pattern detection chưa normalize accent/biến thể từ vựng.

**Tác động**
- Có thể trả lời vượt ranh giới pháp lý (kê đơn/chẩn đoán/liều dùng) trong luồng research.

**Đề xuất chốt**
1. Bỏ hoặc siết cực chặt exemption theo `channel="research"` cho 3 nhóm intent: kê đơn/chẩn đoán/liều.
2. Thêm normalize text trước regex: lower-case, remove punctuation, hỗ trợ tiếng Việt không dấu.
3. Bổ sung regex nhóm số-liều-đơn vị (`mg`, `mcg`, `viên/ngày`, `x 2 viên`...).
4. Bổ sung regression tests bắt buộc cho các prompt bẫy VN/EN.

**File liên quan**
- `services/ml/src/clara_ml/main.py`
- `services/ml/tests/test_main_api.py`

---

### 3.2 Critical DDI miss
**Hiện trạng rủi ro**
- Một số cặp DDI nguy hiểm bị miss khi tên thuốc có kèm strength/form (ví dụ `warfarin 5mg`, `ibuprofen 400mg`).

**Root cause chính**
- Matching đang phụ thuộc nhiều vào token raw, thiếu canonicalization thuốc trước khi so cặp rule.
- Một số external query bị cắt cặp do giới hạn pair check, làm giảm recall ở polypharmacy.

**Tác động**
- False safe trong case nguy hiểm.

**Đề xuất chốt**
1. Canonical medication normalization trước khi match rule:
   - strip liều, dạng bào chế, tần suất,
   - map alias -> active ingredient,
   - chạy đối chiếu cả raw + canonical.
2. Bổ sung telemetry coverage:
   - `normalization_confidence`,
   - `unmatched_medications`,
   - `openfda_pairs_checked`.
3. Tăng test cases decorated-name trong ML tests + demo datasets.

**File liên quan**
- `services/ml/src/clara_ml/agents/careguard.py`
- `services/ml/src/clara_ml/clients/drug_sources.py`
- `services/ml/tests/test_careguard_agent.py`

---

### 3.3 Chuẩn hóa metadata fallback/source-errors
**Hiện trạng rủi ro**
- Có tình huống `source_errors` bị rơi mất qua lớp API attribution normalization.
- `fallback_used` chưa luôn đồng nhất giữa payload top-level và metadata.

**Root cause chính**
- Ưu tiên đọc metadata chưa thống nhất giữa chat/research.
- `source_used` khi là string chưa normalize tách token đầy đủ.

**Đề xuất chốt**
1. Chuẩn 1 contract duy nhất (canonical):
   - `policy_action`, `fallback_used`, `source_errors`, `attributions`.
2. Bắt buộc merge từ nested trace trước khi fallback default.
3. Normalize `source_used` cho cả list/string (split `,;\n`).
4. Dùng chung helper normalize ở chat/careguard/research.

**File liên quan**
- `services/api/src/clara_api/core/attribution.py`
- `services/api/src/clara_api/api/v1/endpoints/chat.py`
- `services/api/src/clara_api/api/v1/endpoints/research.py`

---

## 4) Deep-dive Day 13-14 (vận hành/demo)

### 4.1 Artifact pack “đủ chuẩn chấm”
**Gap**
- Chưa đồng đều giữa parent run và suffixed run.
- Một số run thiếu đủ bộ JSON bằng chứng theo chuẩn.

**Đề xuất chốt**
- Chọn **1 run canonical duy nhất** để chấm (`round2-matrix-ready-<timestamp>`).
- Chỉ dùng artifact từ run canonical + 3 case demo tách riêng:
  - `demo-cases/case-a-online.json`
  - `demo-cases/case-b-offline.json`
  - `demo-cases/case-c-legal-guard.json`

### 4.2 Script demo Case A/B/C
**Gap**
- Chưa có script explicit cho A/B/C (mới có matrix runner tổng quát).

**Đề xuất chốt**
- Thêm script `scripts/demo/run_round2_cases.sh` để chạy deterministic 3 case.
- Kết quả đổ ra `artifacts/round2/<run_id>/demo-cases/`.

### 4.3 Rà legal text + attribution UI
**Gap**
- Careguard/Selfmed đã có disclaimer tốt.
- Research/Council chưa đồng đều legal banner/gating.

**Đề xuất chốt**
- Chốt một legal microcopy chuẩn dùng lại cho toàn bộ route y tế.
- Đảm bảo luôn hiển thị attribution + source error state ở mọi answer panel.

### 4.4 Rehearsal pitch 3 lần
**Gap**
- Chưa có evidence runbook rehearsal 3 vòng.

**Đề xuất chốt**
- Mỗi rehearsal lưu 1 biên bản ngắn: thời gian, fail-point, fix action, verdict.
- Lưu tại: `artifacts/round2/<run_id>/rehearsal/rehearsal-01.md` ... `03.md`.

---

## 5) Owner model + Standup discipline (đề xuất áp dụng ngay)

### 5.1 Owner theo role (không phụ thuộc tên người)
- `GOV-SAFE`: legal guard + policy contract
- `GOV-API`: auth/consent/db/system config
- `GOV-CAREGUARD`: DDI engine + VN dictionary
- `GOV-RAG`: research pipeline + retrieval/source hub
- `GOV-WEB`: web flow + UX + attribution UI
- `GOV-KPI`: artifact/go-no-go/matrix
- `GOV-OPS`: deploy/runtime/CI-CD

### 5.2 Standup SOP (15 phút, evidence-first)
- Mỗi owner bắt buộc báo cáo: file đã chạm + lệnh đã chạy + artifact path.
- `GOV-KPI` công bố `GO/NO-GO` đầu phiên.
- Sev-1 không để qua ngày.

---

## 6) Cập nhật keyword strategy theo nguồn (đã triển khai)

### 6.1 Đã cập nhật
Trong `scripts/ops/source_hub_auto_crawl.sh`:
- Thêm `SOURCE_HUB_AUTO_KEYWORDS=true` (default).
- Hỗ trợ topic theo ngôn ngữ:
  - `vi: ...`
  - `en: ...`
- Tự gợi ý keyword theo source:
  - `vn_*`, `davidrug` -> keyword tiếng Việt,
  - `pubmed`, `europepmc`, `clinicaltrials`, `rxnorm`, `openfda`, `dailymed`, `semantic_scholar` -> keyword tiếng Anh.

### 6.2 Cú pháp đề xuất dùng trong production
```bash
SOURCE_HUB_TOPICS="en: warfarin nsaid bleeding risk;vi: tương tác warfarin thuốc giảm đau;davidrug=paracetamol"
SOURCE_HUB_AUTO_KEYWORDS=true
```

---

## 7) Tech Radar 2026 (ưu tiên thứ hữu ích thực chiến cho CLARA)

## 7.1 Áp dụng ngay (Now)
1. **OpenAI Responses API + tool calling chuẩn hóa**
- Lợi ích: hợp nhất orchestration tool/web/file vào 1 contract responses.
- Giá trị với CLARA: giảm phân mảnh khi phối nhiều provider/retriever.
- Tham chiếu: https://developers.openai.com/api/docs/guides/tools-web-search

2. **MCP (Model Context Protocol) cho tool/data connectors**
- Lợi ích: chuẩn mở để tích hợp nguồn ngoài và internal tools nhất quán.
- Giá trị với CLARA: thống nhất lớp kết nối nguồn y tế + ops tools.
- Tham chiếu:
  - https://modelcontextprotocol.io/docs/getting-started/intro
  - https://www.anthropic.com/news/model-context-protocol

3. **Deep Research style multi-pass retrieval + verification rubric**
- Lợi ích: nâng chất lượng câu trả lời dài và có kiểm chứng.
- Giá trị với CLARA: chuẩn hóa scoring accuracy/completeness/citation.
- Tham chiếu (benchmark mới): https://r2cdn.perplexity.ai/pplx-draco.pdf

4. **Source-aware retrieval policy (domain/language aware)**
- Lợi ích: giảm nhiễu retrieval, tăng precision theo nguồn.
- Giá trị với CLARA: đúng yêu cầu VN/EN keyword theo nguồn (đã bắt đầu triển khai).

## 7.2 Áp dụng giai đoạn kế tiếp (Next)
1. **GraphRAG (knowledge graph + retrieval)**
- Lợi ích: xử lý multi-hop tốt hơn cho câu hỏi guideline phức tạp.
- Giá trị với CLARA: truy vết claim-level tốt hơn trong research y khoa.
- Tham chiếu: https://github.com/microsoft/graphrag

2. **RAG evaluation stack chuyên dụng (rubric + automated judge + golden set)**
- Lợi ích: đo chất lượng có hệ thống, chống regressions khi đổi model/nguồn.
- Giá trị với CLARA: biến KPI thành gating thực tế, không dựa cảm giác.

3. **Clinical source prioritization by trust tiers**
- Lợi ích: luôn ưu tiên nguồn chuẩn y tế, giảm hallucination/rác web.
- Giá trị với CLARA: tăng an toàn pháp lý và độ tin cậy hội đồng chấm.

## 7.3 Để sau hackathon (Later)
1. **FHIR-aligned interoperability layer**
- Lợi ích: sẵn đường kết nối hệ thống y tế chuẩn.
- Giá trị với CLARA: chuẩn bị cho tích hợp bệnh án/clinical workflow thật.
- Tham chiếu: https://www.hl7.org/fhir/

2. **Advanced policy engine (runtime policy versioning + audit trails)**
- Lợi ích: rollback nhanh khi policy lỗi.
- Giá trị với CLARA: hardening production/legal compliance.

---

## 8) Plan chốt vòng 2 trong 72 giờ (thực dụng)

## T+0 đến T+24h
- Vá Day 12 (3 mục pending) + test hồi quy.
- Chạy matrix canonical run mới.

## T+24 đến T+48h
- Tạo script demo Case A/B/C + đẩy artifact demo-cases.
- Rà legal text + attribution UI trên `careguard/selfmed/research/council`.

## T+48 đến T+72h
- Rehearsal pitch 3 lần + lưu biên bản.
- Tick checklist Day13-14 + freeze.

---

## 9) File/chỗ cần cập nhật tiếp theo
- Checklist chính:
  - `docs/implementation-plan/round2-14-day-execution-checklist-2026-03-30.md`
- Ops crawl docs:
  - `docs/ops/source-hub-crawl.md`
  - `docs/ops/README.md`
- Script crawl:
  - `scripts/ops/source_hub_auto_crawl.sh`

---

## 10) Nguồn tham khảo chính (đã đối chiếu)
1. OpenAI Tools / Web Search guide: https://developers.openai.com/api/docs/guides/tools-web-search
2. OpenAI Deep Research announcement: https://openai.com/index/introducing-deep-research/
3. MCP intro: https://modelcontextprotocol.io/docs/getting-started/intro
4. Anthropic MCP announcement: https://www.anthropic.com/news/model-context-protocol
5. DRACO benchmark (Perplexity, 2026): https://r2cdn.perplexity.ai/pplx-draco.pdf
6. GraphRAG (Microsoft): https://github.com/microsoft/graphrag
7. HL7 FHIR: https://www.hl7.org/fhir/
8. openFDA query syntax: https://open.fda.gov/apis/query-syntax/
