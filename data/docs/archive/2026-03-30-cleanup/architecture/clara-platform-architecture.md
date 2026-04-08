# Kiến Trúc Nền Tảng CLARA (Research + Self-Med)

Phiên bản: 2.1  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu kiến trúc

CLARA là nền tảng AI y tế gồm 2 nhánh sản phẩm dùng chung kiến trúc:
- **CLARA Research**: hỗ trợ truy xuất, tổng hợp và kiểm chứng bằng chứng y khoa.
- **CLARA Self-Med**: quản lý thuốc cá nhân/gia đình, giảm sai sót dùng thuốc tại nhà.

Mục tiêu kiến trúc:
- bảo đảm an toàn y khoa theo cơ chế kiểm chứng nhiều lớp,
- tối ưu thời gian phản hồi theo từng role,
- hỗ trợ web + app Flutter,
- vận hành trên backend Rust với lớp orchestration AI chuyên biệt.

## 2. Kênh sản phẩm và nền tảng công nghệ

- Web: cổng người dùng + cổng quản trị hệ thống.
- Mobile: Flutter (Android/iOS) cho Self-Med và trải nghiệm người dùng cuối.
- Backend runtime: **ưu tiên Rust** cho gateway/auth/rbac/policy/audit/cache.
- AI orchestration: **LangGraph/LangChain** trong dịch vụ AI (Python) để điều phối tác tử.
- Dịch vụ ML chuyên sâu: OCR/ASR/inference trong Python, tích hợp với Rust qua gRPC/HTTP.

## 3. Role input và Intent Router 2 lớp

### 3.1 Role input

Mọi truy vấn đều đi qua role input (khai báo hoặc suy luận):
- `normal_user`
- `researcher`
- `doctor`

### 3.2 Router 2 lớp bắt buộc

1. **B1 - Role Classification**: phân loại role + confidence.
2. **B2 - Intent Classification theo role**: phân loại ý định chuyên biệt cho role vừa chọn.

Fallback an toàn:
- B1 thấp: hạ về `normal_user` + hỏi lại ngữ cảnh.
- B2 thấp: route qua luồng rủi ro thấp và giới hạn phạm vi trả lời.

## 4. Kiến trúc multi-agent

Tầng tác tử vận hành:
- `planner/supervisor` (LangGraph): lập đồ thị thực thi và điều phối nhánh.
- `retrieval agents`: truy xuất theo nguồn và phương thức (text/PDF-OCR/image/audio).
- `domain specialist agents`: dược lý, guideline, nghiên cứu, lâm sàng.
- `coding agent`: tạo/chạy tool tính toán y khoa có kiểm soát.
- `synthesis node`: tổng hợp phản hồi + claim set + citation map.
- `verification node` (FIDES-inspired): kiểm chứng độc lập claim/citation.
- `policy/safety agent`: quyết định `allow/warn/block/escalate`.
- `reviewer-in-the-loop`: xử lý ca nguy cơ cao hoặc AI Council bất đồng.

### 4.1 Coding agent là gì?

`coding agent` là tác tử tạo và thực thi công cụ tính toán y khoa có kiểm soát (BMI, CKD-EPI, Cockcroft-Gault, liều theo chức năng thận), chỉ được phép chạy khi:
- intent yêu cầu tính toán rõ ràng,
- dữ liệu đầu vào đã chuẩn hóa đơn vị,
- policy cho phép.

Guardrails:
- chỉ dùng tool trong registry đã duyệt,
- kết quả bắt buộc qua verification + policy,
- lưu log đầy đủ công thức, input, output, version tool.

## 5. LangChain/LangGraph application (chốt sử dụng)

### 5.1 Vai trò của LangGraph trong orchestration

- Dùng **LangGraph** làm state machine cho planner/supervisor/sub-agents.
- Mỗi workflow là một graph có node rõ ràng: route -> retrieve -> synthesize -> verify -> policy -> respond.
- Hỗ trợ nhánh song song (AI Council) và hợp nhất kết quả có kiểm soát.
- Hỗ trợ checkpoint state cho truy vấn dài (research 5-10-20).

### 5.2 Vai trò của LangChain

- Dùng **LangChain** cho:
  - retriever abstraction,
  - tool binding,
  - prompt templates versioned,
  - callback/tracing hooks cho pipeline AI.
- Prompt templates tách theo role + intent + risk level.

### 5.3 Phân tách với backend Rust

- Rust giữ toàn bộ control mặt nghiệp vụ hệ thống:
  - gateway, auth, RBAC, tenant, rate limit,
  - policy enforcement ở lớp hệ thống,
  - audit/event bus,
  - cache và adapter dữ liệu.
- LangGraph service chỉ đảm nhiệm orchestration AI.
- Rust gọi AI service qua contract versioned, không để AI service truy cập trực tiếp mọi dữ liệu nhạy cảm.

### 5.4 Khi nào KHÔNG dùng LLM

Không dùng LLM để ra quyết định cuối cho các tác vụ deterministic/rủi ro cao:
- DDI critical,
- cảnh báo dị ứng hard-stop,
- dose contra-indication hard rules,
- policy block theo compliance.

Các tác vụ này dùng rule engine + cơ sở dữ liệu chuẩn hóa; LLM chỉ hỗ trợ diễn giải ngôn ngữ.

## 6. Chiến lược nguồn dữ liệu và định tuyến nguồn

### 6.1 Nguồn Việt Nam (ưu tiên)

- Dược thư Quốc gia Việt Nam.
- Crawler BYT monthly (thông tư/cảnh báo/hướng dẫn).
- Nguồn chuyên khoa được thẩm định.

### 6.2 Nguồn quốc tế

- PubMed, ClinicalTrials, WHO ICD-11.
- RxNorm (RxCUI), openFDA.

### 6.3 Web recheck

Nguồn web chỉ dùng đối chiếu nhanh; không phải nguồn sự thật chính nếu chưa được xác thực chéo.

### 6.4 Quyết định nguồn dựa trên role + intent

- Self-Med DDI/dị ứng: RxNorm + openFDA + Dược thư VN.
- Research guideline compare: BYT + PubMed + guideline quốc tế.
- Doctor council: guideline chuyên khoa + hồ sơ ca bệnh (có quyền truy cập).

## 7. Multimodal RAG processing

1. Ingestion đa phương thức: text, PDF scan/OCR, ảnh, audio/ASR.
2. Chuẩn hóa thực thể: biệt dược -> hoạt chất -> RxCUI; thuật ngữ VN -> ICD.
3. Retrieval hybrid: dense + sparse + rerank.
4. Cross-modal fusion theo `claim_id`.
5. Synthesis tạo draft có citation.
6. Verification (FIDES) kiểm chứng độc lập claim/citation.
7. Policy gate quyết định phản hồi cuối.

### 7.1 Luồng Self-Med end-to-end (bắt buộc)

1. Khởi tạo hồ sơ người dùng/hộ gia đình: tuổi, bệnh nền, dị ứng, thuốc đang dùng.
2. Quản lý tủ thuốc cá nhân: thêm/sửa/xóa thuốc, batch, hạn dùng, đơn vị liều, lịch dùng.
3. Scan thuốc:
   - ưu tiên barcode để nhận dạng nhanh sản phẩm,
   - fallback OCR khi barcode thiếu/không đọc được,
   - bắt buộc bước xác nhận người dùng trước khi lưu vào tủ thuốc.
4. Chuẩn hóa thực thể thuốc: biệt dược -> hoạt chất -> RxCUI, nối với cảnh báo openFDA và tri thức Dược thư VN.
5. DDI/allergy check theo thời điểm dùng liều: rule engine chạy deterministic với phân tầng `critical/major/moderate/minor`.
6. AI recommendations có guardrails: chỉ diễn giải, nhắc tuân thủ, gợi ý hỏi bác sĩ, không thay thế quyết định lâm sàng.
7. Policy gate quyết định `allow/warn/block/escalate` và ghi audit log đầy đủ.

### 7.2 Guardrails cho AI recommendations trong Self-Med

- Không cho phép LLM ghi đè kết quả DDI critical, allergy hard-stop, chống chỉ định liều.
- Bắt buộc gắn `risk_label`, `confidence`, `citation map` cho mọi khuyến nghị từ mức rủi ro trung bình trở lên.
- Bắt buộc "xác nhận lại dữ liệu đầu vào" khi OCR confidence thấp, mapping hoạt chất mơ hồ, hoặc thiếu hồ sơ dị ứng.
- Chỉ cho phép nhóm khuyến nghị an toàn:
  - nhắc lịch dùng thuốc/kiểm kê/hết hạn,
  - giải thích tương tác và hành động an toàn tiếp theo,
  - đề xuất escalate tới bác sĩ/cơ sở y tế khi có dấu hiệu nguy cơ cao.
- Chặn hoàn toàn khuyến nghị kiểu "tự đổi thuốc/tự tăng giảm liều" nếu không có xác thực bác sĩ.

### 7.3 Tái sử dụng OCR + ADE từ tgc-transhub

Thành phần tái sử dụng vào CLARA Self-Med:
- GCP Vision OCR multi-pass với preprocess variants: `raw`, `gray_contrast`, `upscale`, `binarize`, `median_otsu` (ưu tiên intent bbox).
- ADE preprocess/scoring:
  - sinh nhiều candidate OCR theo trang,
  - chấm điểm candidate theo text + layout quality,
  - early-stop/fallback theo ngưỡng cấu hình (`OCR_GCP_MIN_TEXT_SCORE`, `OCR_GCP_MIN_BBOX_SCORE`, `OCR_GCP_EARLY_STOP`).
- Chuẩn hóa layout:
  - lọc confidence thấp,
  - dedupe overlap,
  - merge line boxes adaptive,
  - reading-order sorting ổn định cho downstream DDI parser.
- Layout telemetry và quality gate:
  - thu chỉ số `avg_layout_smoothness_score`, `avg_overlap_duplicate_rate`, `avg_reading_disorder_rate`,
  - dùng script đánh giá regression (`eval_ocr_layout.py`) trước khi rollout production.

Nguyên tắc tích hợp:
- Rust gateway vẫn là điểm kiểm soát nghiệp vụ; OCR/ADE service chỉ xử lý nhận dạng/chấm điểm.
- Contract OCR/ADE versioned, có trường confidence + decision reason để policy quyết định auto-accept hay yêu cầu xác nhận thủ công.
- Kế hoạch migration chi tiết P0-P2 nằm trong master plan/workstream Self-Med, không đưa thẳng vào production một bước.

## 8. Tách rõ Synthesis và Verification

- Synthesis không được tự xác nhận kết luận.
- Verification độc lập model/prompt/pipeline.
- Nếu conflict nghiêm trọng: `block` hoặc `escalate`.

## 9. Cache policy: update/invalidate, không add mù

- Cache chỉ lưu thông tin liên quan và đã xác thực.
- Khi nguồn đổi trạng thái:
  - `update` record hiện có,
  - `invalidate` record lỗi thời/mâu thuẫn.
- Không append "sự thật mới" nếu chưa kiểm chứng.

## 10. Workflow theo role và KPI thời gian

- **Normal users**: simple workflow, < 2 phút.
- **Researchers**: progressive workflow 5-10-20 phút theo độ sâu.
- **Doctors**: specialized/AI Council < 10-20 phút, bắt buộc log hội chẩn.

## 11. AI Council cho bác sĩ

- Specialist agents chạy song song theo chuyên khoa.
- Kết quả phải có: đồng thuận, bất đồng, rủi ro chưa giải quyết, log hội chẩn đầy đủ.

## 12. System Management Dashboard (Control Tower)

Dashboard quản trị toàn hệ thống được thiết kế như control-plane tách biệt data-plane.

### 12.1 Module quản trị bắt buộc

- User/Role/Tenant Management.
- Model/Prompt/Policy Version Registry.
- Quality Gates + Eval Jobs + Drift Monitoring.
- Data Source Registry + Connector Health + Freshness.
- Incident Center + Alert Console.
- Audit Explorer + Compliance Reports.
- Feature Flags + Rollout Manager.

### 12.2 Vai trò sử dụng dashboard

- Product/Ops: KPI, release gates, incident handling.
- Clinical/Safety: policy outcomes, cảnh báo high-risk, AI Council logs.
- Security/Compliance: audit trail, evidence packages, access review.
- ML/Platform: model drift, eval regression, connector SLA.

## 13. Blockchain: có dùng hay không?

- Phase 00-03: dùng append-only audit log (PostgreSQL/object storage) để giảm độ phức tạp.
- Phase 04+: đánh giá blockchain cho non-repudiation/liên tổ chức nếu có yêu cầu pháp lý thực sự.

## 14. SLM stack đề xuất (Mistral / GPT-OSS / Qwen)

| Tác vụ | Ưu tiên 1 | Ưu tiên 2 | Ghi chú |
|---|---|---|---|
| Role/Intent routing | Qwen nhỏ | GPT-OSS nhỏ | ưu tiên latency |
| Synthesis | Qwen cỡ trung | Mistral cỡ trung | theo quality/cost |
| Verification/FIDES | Mistral instruction | GPT-OSS instruction | ưu tiên consistency |
| Tool reasoning/coding agent | GPT-OSS | Qwen | guardrails chặt |

## 15. Bảo mật và compliance

- Tuân thủ Nghị định 13/2023/NĐ-CP.
- Mã hóa at-rest/in-transit.
- RBAC + tenant isolation.
- PII/PHI redaction trước khi vào tác tử.
- Audit trace bắt buộc cho mọi phản hồi y khoa risk trung bình trở lên.
