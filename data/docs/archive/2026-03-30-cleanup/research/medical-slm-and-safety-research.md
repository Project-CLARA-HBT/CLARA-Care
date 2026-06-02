# Nghiên Cứu Medical SLM Và Kiến Trúc An Toàn

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu

Lựa chọn và phân vai mô hình ngôn ngữ nhỏ (SLM) cho hệ thống CLARA theo nguyên tắc:
- đúng tác vụ,
- dễ kiểm soát,
- an toàn y khoa,
- tối ưu chi phí vận hành.

## 2. Bộ mô hình ứng viên chính

## 2.1 Mistral (các biến thể instruction)

- Điểm mạnh: hiệu năng suy luận tốt, hệ sinh thái triển khai rộng.
- Hạn chế: cần kiểm soát hallucination chặt cho tác vụ y khoa.
- Phù hợp: synthesis có ràng buộc citation, tóm tắt evidence.

## 2.2 GPT-OSS (open-weight/open-stack định hướng)

- Điểm mạnh: linh hoạt tích hợp, dễ tùy biến pipeline.
- Hạn chế: chất lượng phụ thuộc mạnh vào fine-tuning và guardrails.
- Phù hợp: coding/tool agent, orchestration trợ giúp, utility reasoning.

## 2.3 Qwen (các biến thể nhỏ và trung)

- Điểm mạnh: đa ngôn ngữ tốt, phù hợp router/intent và tác vụ tiếng Việt.
- Hạn chế: cần benchmark riêng cho domain y khoa Việt.
- Phù hợp: router 2 lớp, intent classification, một phần verifier support.

## 3. Phân vai mô hình theo tác vụ

| Thành phần | Mục tiêu | Khuyến nghị model |
|---|---|---|
| Router L1/L2 | phân vai + phân ý định nhanh | Qwen small/medium fine-tune |
| Synthesis | tạo câu trả lời có cấu trúc | Mistral hoặc Qwen-instruct có guardrails |
| Verifier (FIDES support) | kiểm chứng claim | model chuyên entailment + rule engine |
| Coding agent | tạo công cụ tính toán y khoa an toàn | GPT-OSS/Mistral nhỏ + sandbox |
| Self-Med DDI | phân loại rủi ro tương tác | rule+knowledge first, model chỉ hỗ trợ diễn giải |

## 4. Chiến lược fine-tune theo TCVN

## 4.1 Mục tiêu chuẩn hóa

- Chuẩn hóa ngôn ngữ y khoa tiếng Việt theo thuật ngữ trong nước.
- Đồng bộ mapping thuật ngữ VN -> mã chuẩn quốc tế.
- Giảm sai lệch diễn giải ở các cụm từ đa nghĩa trong y khoa.

## 4.2 Lộ trình fine-tune

1. **Data curation**: gom dữ liệu đã cấp phép từ BYT, Dược thư, guideline.
2. **Normalization corpus**: tạo cặp thuật ngữ VN chuẩn và alias thực tế.
3. **Instruction tuning**: huấn luyện tác vụ router, explain, summarize.
4. **Safety tuning**: học hành vi từ chối/escalate khi thiếu bằng chứng.
5. **Evaluation loop**: benchmark theo role và severity.

## 5. Lỗ hổng điển hình của SLM trong y khoa

1. Hallucination dưới áp lực trả lời nhanh.
2. Prompt injection từ tài liệu đầu vào nhiễu.
3. Citation fabrication (PMID/DOI giả).
4. Overconfidence khi evidence mâu thuẫn.
5. Sai lệch khi gặp tên thuốc địa phương/biệt dược hiếm.

## 6. Kiến trúc an toàn bắt buộc

- Tách node `Synthesis` và `Verification`.
- FIDES module kiểm chứng claim theo 5 bước.
- Policy engine quyết định theo mức rủi ro.
- Reviewer-in-the-loop cho ca high-risk.
- Logging đầy đủ để audit và RCA.

## 7. Đánh giá mô hình và ngưỡng chất lượng

## 7.1 Chỉ số bắt buộc

- Router accuracy theo role/intent.
- Verification pass rate theo severity.
- Hallucination rate trên bộ ca lâm sàng chuẩn.
- Citation validity rate.
- Latency theo role (normal/researcher/doctor).

## 7.2 Gate phát hành model

- Không phát hành nếu regression safety > ngưỡng.
- Bắt buộc có shadow deployment trước full rollout.
- Rollback model profile trong thời gian ngắn.

## 8. Khuyến nghị stack thực tế

- Router: Qwen fine-tuned.
- Synthesis: Mistral hoặc Qwen instruct có guardrail mạnh.
- Tool/coding support: GPT-OSS cho luồng utility, không trực tiếp kết luận y khoa.
- Verifier: kết hợp model + rule + source constraints (FIDES-inspired).

## 9. Kết luận

SLM chỉ an toàn trong y khoa khi đóng vai trò đúng chỗ, bị ràng buộc bởi verification độc lập và policy gating. Trọng tâm của CLARA không phải “một model mạnh nhất”, mà là “kiến trúc nhiều lớp kiểm soát sai sót”.

## 10. LangChain/LangGraph suitability trong vòng đời model

### 10.1 Giá trị thực tế

- Dễ chuẩn hóa orchestration giữa router -> retriever -> synthesis -> verifier.
- Tăng tốc vòng lặp thử nghiệm prompt/tool/graph cho nhiều role.
- Hỗ trợ tốt cho luồng multi-agent phức tạp (AI Council, coding agent, HITL).

### 10.2 Hạn chế và lock-in

- Mức phụ thuộc cao vào framework nếu business logic nhúng sâu trong graph nodes.
- Khó thay thế từng phần nếu không tách rõ domain logic và orchestration logic.
- Cần governance nghiêm cho thay đổi graph để tránh regression an toàn.

### 10.3 Mô hình hybrid khuyến nghị

- Rust quản lý runtime APIs, auth, rate limit, policy gate, audit.
- LangGraph service xử lý điều phối AI và tool calling.
- Rule engine độc lập cho ràng buộc y khoa bắt buộc (DDI/liều/chống chỉ định).

## 11. Ops Dashboard & Governance cho model safety

### 11.1 Chỉ số cần theo dõi

- Router accuracy theo role/intent.
- Hallucination rate theo severity.
- Citation validity và factual consistency.
- Tỷ lệ block/escalate đúng ngữ cảnh.

### 11.2 Governance model/version

- Model registry: model_id, dataset lineage, benchmark results, approval state.
- Prompt registry: prompt version, risk notes, rollback compatibility.
- Policy registry: action thresholds, release history, owner phê duyệt.

### 11.3 Eval pipelines và HITL

- Offline benchmark theo tuần (golden set).
- Online safety sampling theo ngày cho case rủi ro cao.
- HITL queue với SLA riêng cho doctor và Self-Med critical alerts.

### 11.4 Compliance evidence

- Lưu artefact benchmark trước/sau mỗi lần đổi model.
- Lưu bằng chứng reviewer action cho case escalation.
- Lưu mapping giữa version model và phản hồi thực tế để phục vụ kiểm toán.

## 12. Checklist nghiên cứu dashboard an toàn cho clinical AI

1. Có đủ dashboard cho chất lượng model, safety, compliance.
2. Có version lineage cho model/prompt/policy.
3. Có cảnh báo drift và cảnh báo calibration lệch.
4. Có cơ chế freeze rollout khi vượt ngưỡng safety.
5. Có HITL queue và phân loại ưu tiên ca bệnh.
6. Có audit trail gắn chặt với mọi quyết định block/escalate.
