# Nghiên Cứu Multimodal RAG Và Data Connectors

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu

Thiết kế pipeline RAG đa phương thức phục vụ đồng thời CLARA Research và CLARA Self-Med, đảm bảo:
- truy xuất đúng nguồn,
- kiểm chứng được,
- cập nhật an toàn theo nguyên tắc `update/invalidate`.

## 2. Danh mục nguồn dữ liệu ưu tiên

## 2.1 Nguồn Việt Nam

| Nguồn | Mục đích | Độ ưu tiên | Cơ chế cập nhật |
|---|---|---|---|
| Dược thư Quốc gia | thông tin thuốc chuẩn hóa VN | P0 | batch định kỳ + diff update |
| Cổng/Bản tin BYT (monthly crawl) | hướng dẫn chuyên môn, cảnh báo mới | P0 | crawler theo tháng + kiểm duyệt |
| Hướng dẫn bệnh viện/hiệp hội chuyên khoa trong nước | điều trị theo bối cảnh VN | P1 | pull theo đối tác |

## 2.2 Nguồn quốc tế

| Nguồn | Mục đích | Độ ưu tiên | Lưu ý |
|---|---|---|---|
| PubMed | bằng chứng nghiên cứu | P0 | yêu cầu citation PMID |
| RxNorm | chuẩn hóa hoạt chất và RxCUI | P0 | lõi cho DDISafe |
| openFDA | cảnh báo an toàn, adverse events | P0 | bắt buộc recheck định kỳ |
| ClinicalTrials | thông tin thử nghiệm lâm sàng | P1 | dùng cho nhánh Research |
| WHO ICD | chuẩn hóa bệnh/chẩn đoán | P1 | map cho entity normalization |

## 2.3 Recheck web có kiểm soát

- Web chỉ là nguồn bổ trợ, không phải nguồn sự thật chính.
- Cơ chế `web-recheck` dùng để:
  - xác minh cảnh báo mới,
  - phát hiện thay đổi nhanh khi nguồn chính chưa cập nhật.
- Kết quả web-recheck luôn phải bị hạ độ tin cậy nếu chưa được nguồn chuẩn đối chiếu.

## 3. Pipeline ingest đa phương thức

## 3.1 Text ingest

1. Thu thập -> chuẩn hóa encoding -> tách đoạn.
2. Trích metadata: nguồn, ngày hiệu lực, cấp bằng chứng.
3. Embedding + index theo domain.

## 3.2 PDF scan/OCR ingest

1. OCR với quality score theo trang.
2. Chuẩn hóa cấu trúc bảng/cột.
3. Gắn cờ đoạn có OCR thấp để verifier xử lý chặt hơn.

## 3.3 Image ingest

1. Phát hiện vùng chứa text/ký tự viên thuốc.
2. Trích dấu hiệu nhận diện (màu, shape, imprint).
3. Mapping ứng viên với kho thuốc VN + RxNorm (nếu có).

## 3.4 Audio/ASR ingest

1. ASR tiếng Việt y khoa.
2. Chuẩn hóa thuật ngữ và tách câu lệnh dùng thuốc.
3. Gắn confidence theo câu, phục vụ policy gating.

## 4. Entity normalization và chuẩn mã

- Thuốc: biệt dược -> hoạt chất -> RxCUI.
- Bệnh/chẩn đoán: thuật ngữ VN -> ICD-10/ICD-11.
- Xét nghiệm/chỉ số: map chuẩn nội bộ hoặc LOINC khi khả thi.
- Dị ứng/chống chỉ định: chuẩn hóa alias để kiểm tra chéo.

## 5. Routing và retrieval theo intent + role

## 5.1 Router 2 lớp

- Lớp 1: phân loại vai trò (`normal`, `researcher`, `doctor`).
- Lớp 2: phân loại intent trong từng vai trò.

## 5.2 Quyết định nguồn truy xuất

- Kết hợp `role + intent + risk_level + freshness_requirement`.
- Ví dụ:
  - Self-Med DDI: ưu tiên RxNorm + openFDA + Dược thư.
  - Research guideline: ưu tiên BYT + PubMed + guideline quốc tế.

## 5.3 Retrieval hợp nhất

1. Dense retrieval.
2. Sparse/BM25 retrieval.
3. Cross-encoder rerank.
4. Hợp nhất theo chất lượng nguồn + độ mới + độ phù hợp.

## 6. Synthesis/verification và FIDES integration

- `Synthesis Node` tạo nháp câu trả lời + claim list.
- `Verification Node` (FIDES-inspired):
  1. claim decomposition,
  2. evidence retrieval,
  3. cross-source check,
  4. citation validity,
  5. verdict + action.

Kết quả đi qua policy engine để quyết định `allow/warn/block/escalate`.

## 7. Cache policy: update/invalidate

## 7.1 Nguyên tắc

- Không thêm “chân lý mới” chồng lên bản cũ nếu chưa kiểm chứng.
- Khi nguồn đổi trạng thái:
  - `update` record chuẩn nếu xác thực thành công,
  - `invalidate` record cũ nếu lỗi thời/mâu thuẫn.

## 7.2 Cấu trúc cache đề xuất

- L1 session cache: ngắn hạn theo phiên.
- L2 retrieval cache: kết quả truy xuất gần đây.
- L3 normalized entity cache: map thuật ngữ/ID chuẩn.
- L4 freshness registry: theo dõi TTL và trạng thái hiệu lực.

## 8. KPIs kỹ thuật cho multimodal RAG

- OCR CER/WER theo loại tài liệu.
- ASR WER và tỷ lệ sai thuật ngữ y khoa.
- Recall@k theo từng modality.
- Cross-modal consistency score.
- Citation validity rate.
- Tỷ lệ policy escalation đúng ngữ cảnh.

## 9. Rủi ro và kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| OCR sai làm sai DDI | quality threshold + human confirmation |
| Web recheck đưa thông tin nhiễu | hạ trust score + cần nguồn chuẩn đối chiếu |
| Entity map sai biệt dược | nhiều tầng chuẩn hóa + unit tests mapping |
| Cache stale kéo dài | freshness scheduler + invalidate bắt buộc |

## 10. Khuyến nghị triển khai

1. Ưu tiên build source registry chuẩn trước khi mở rộng model.
2. Làm chặt entity normalization cho thuốc/dị ứng trước tính năng nâng cao.
3. Bật FIDES ở mức strict cho nhánh doctor và DDI high-risk.
4. Thiết kế dashboard theo dõi chất lượng theo modality ngay từ phase đầu.

## 11. Đánh giá khả năng áp dụng LangChain/LangGraph

### 11.1 Lợi ích

- Rút ngắn thời gian dựng workflow multi-agent (planner/supervisor/sub-agents).
- Dễ tích hợp retriever, prompt template, memory, tool calling trong cùng framework.
- Thuận tiện cho luồng progressive và HITL (human-in-the-loop) ở workflow research/doctor.

### 11.2 Giới hạn và rủi ro lock-in

- Lock-in ở lớp orchestration nếu flow phụ thuộc sâu vào DSL/runtime đặc thù.
- Khi nâng tải production lớn, cần kiểm soát chặt latency và memory footprint.
- Nguy cơ khó debug nếu workflow graph quá phức tạp và thiếu chuẩn observability.

### 11.3 Độ phức tạp vận hành

- Cần phiên bản hóa graph, prompt, tool contract đồng bộ.
- Cần test harness riêng cho graph transitions và failure branches.
- Cần quy trình release riêng cho orchestration logic, tách khỏi release backend Rust.

### 11.4 Mô hình hybrid với backend Rust (khuyến nghị)

- Rust giữ vai trò control-plane/runtime APIs: gateway, auth, policy gate, cache, audit, tenant controls.
- LangGraph/LangChain vận hành trong AI orchestration service (Python) cho nhánh Research/Doctor/Self-Med reasoning.
- Contract giữa Rust và AI service dùng gRPC/HTTP + schema versioning + trace id.
- Các quyết định an toàn mức cao (DDI critical, allergy hard-stop) vẫn ưu tiên rule engine deterministic.

## 12. Ops Dashboard & Governance cho Multimodal RAG

### 12.1 Metrics và alerts

- Chất lượng ingest theo modality: OCR CER/WER, ASR WER, parser confidence.
- Retrieval quality: Recall@k, rerank gain, citation validity rate.
- Safety metrics: block/escalate ratio, critical miss rate, verification pass rate.
- Alerts: drift tăng nhanh, source freshness quá hạn, policy action bất thường.

### 12.2 Model/version governance

- Registry cho model, prompt pack, retriever config, routing thresholds.
- Bắt buộc gắn `version_id` vào mọi phản hồi để audit và rollback.
- Shadow/canary evaluation trước khi promote cấu hình mới.

### 12.3 Eval pipelines và HITL queues

- Batch eval nightly cho regression theo role và modality.
- Online eval sampling cho phiên high-risk.
- HITL queue ưu tiên ca `doctor`, `selfmed_ddi_check`, `allergy_conflict`.

### 12.4 Compliance evidence collection

- Tự động lưu bằng chứng: nguồn trích dẫn, verdict FIDES, action policy, trace timeline.
- Chuẩn hồ sơ kiểm toán cho Nghị định 13: consent, access log, retention/deletion actions.

## 13. Checklist nghiên cứu triển khai dashboard an toàn

1. Định nghĩa taxonomy alert theo severity và role.
2. Có dashboard riêng cho data quality, model quality, clinical safety, compliance.
3. Mọi KPI có threshold và owner rõ ràng.
4. Có pipeline phát hiện drift theo từng modality.
5. Có phiên bản hóa model/prompt/policy và rollback test định kỳ.
6. Có HITL queue với SLA xử lý cho ca critical.
7. Có audit explorer truy xuất theo `trace_id`, `claim_id`, `session_id`.
8. Có kịch bản DR cho mất nguồn BYT/RxNorm/openFDA/PubMed.
