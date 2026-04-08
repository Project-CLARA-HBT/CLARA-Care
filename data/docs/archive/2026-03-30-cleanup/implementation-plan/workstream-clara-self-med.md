# Luồng Công Việc CLARA Self-Med

## 1. Mục tiêu nhánh

CLARA Self-Med tập trung vào an toàn dùng thuốc tại gia đình:
- giảm sai sót dùng thuốc,
- phát hiện sớm tương tác nguy hiểm,
- tăng tuân thủ điều trị,
- giảm rủi ro thuốc hết hạn và ngộ độc ở trẻ em.

## 2. Áp dụng LangChain/LangGraph (chốt triển khai)

- Dùng LangGraph để điều phối flow Self-Med:
  - parse input đa phương thức,
  - chuẩn hóa thực thể thuốc,
  - chạy DDI/allergy checks,
  - tạo response có trích dẫn và gắn risk label.
- Dùng LangChain cho retriever/tool orchestration và prompt templates.
- Quy tắc an toàn: DDI critical và allergy hard-stop dùng rule engine + DB chuẩn, không giao quyết định cuối cho LLM.
- AI recommendations chỉ đóng vai trò diễn giải/nhắc tuân thủ/escalation, không thay thế chỉ định bác sĩ.

## 3. Phạm vi chức năng bắt buộc

### 3.1 Số hóa tủ thuốc gia đình
- Quét barcode/chụp đơn thuốc để nhận diện.
- Mapping hoạt chất và RxCUI (RxNorm).
- Đồng bộ cảnh báo openFDA và thông báo thu hồi.

### 3.2 Phân loại thông minh theo đối tượng
- Theo thành viên gia đình.
- Theo nhóm nguy cơ (cao tuổi, trẻ em, bệnh nền).
- Theo thuốc kê đơn/không kê đơn.

### 3.3 DDI và cảnh báo dị ứng
- Kiểm tra tương tác tức thời trước liều dùng.
- Cảnh báo khẩn nếu trùng tiền sử dị ứng.
- Severity: critical/major/moderate/minor.

### 3.4 Nhắc lịch và giám sát tuân thủ
- Lịch uống thuốc tự động từ đơn đã quét.
- Family dashboard theo dõi nhiều người.
- Escalation alert sau 30-40 phút nếu bỏ lỡ liều.

### 3.5 Bảo quản, kiểm kê, tiêu hủy
- Hướng dẫn nhiệt độ/ánh sáng.
- Nhắc kiểm kê định kỳ và cảnh báo hết hạn.
- Hướng dẫn tiêu hủy đúng cách.

### 3.6 Tra cứu tri thức chống tin giả
- Agentic RAG trả lời câu hỏi dùng thuốc cơ bản có trích dẫn.
- Luôn hiển thị nguồn chuẩn (BYT, Dược thư, PubMed, RxNorm, openFDA).

## 4. Luồng kỹ thuật nhánh Self-Med

### 4.1 Luồng Self-Med chuẩn (end-to-end)

1. Người dùng khai báo hồ sơ cá nhân/gia đình (bệnh nền, dị ứng, thuốc đang dùng).
2. Quản lý tủ thuốc cá nhân: thêm/sửa/xóa thuốc, hạn dùng, liều dùng, lịch dùng.
3. Scan thuốc:
   - ưu tiên barcode,
   - fallback OCR đa lượt khi barcode fail,
   - xác nhận thủ công nếu confidence thấp.
4. Entity mapping sang hoạt chất + RxCUI + hồ sơ dị ứng/bệnh nền.
5. DDI engine + allergy checker chạy deterministic và phân tầng mức nguy cơ.
6. AI recommendations có guardrails để diễn giải cảnh báo và hướng dẫn bước tiếp theo.
7. Policy gate quyết định `allow/warn/block/escalate`.
8. Ghi log tuân thủ, phát reminder và đẩy escalation realtime.

### 4.2 Guardrails cho AI recommendations

- Không cho phép khuyến nghị tự đổi thuốc/tự tăng giảm liều.
- Không cho phép ghi đè kết quả DDI critical hoặc allergy hard-stop.
- Bắt buộc kèm trích dẫn nguồn chuẩn + confidence + risk label.
- Bắt buộc xác nhận người dùng khi dữ liệu OCR/mapping không chắc chắn.

## 5. Tái sử dụng OCR + ADE từ tgc-transhub

### 5.1 Thành phần tái sử dụng

- OCR multi-pass GCP Vision cho scan thuốc: `raw`, `gray_contrast`, `upscale`, `binarize`, `median_otsu`.
- ADE preprocess/scoring:
  - sinh candidate OCR theo trang,
  - chấm điểm text/layout,
  - early-stop và fallback theo ngưỡng (`OCR_GCP_MIN_TEXT_SCORE`, `OCR_GCP_MIN_BBOX_SCORE`, `OCR_GCP_EARLY_STOP`).
- Chuẩn hóa layout phục vụ parser thuốc:
  - lọc confidence thấp, dedupe overlap, merge line boxes, sắp xếp reading order.
- Layout telemetry:
  - `avg_layout_smoothness_score`,
  - `avg_overlap_duplicate_rate`,
  - `avg_reading_disorder_rate`,
  - manual review rate theo confidence band.

### 5.2 Nguyên tắc migration vào Self-Med

- Không copy nguyên khối pipeline `tgc-transhub`; chỉ tái sử dụng thành phần đã kiểm chứng.
- Đóng gói qua contract OCR/ADE v1 để Rust backend kiểm soát policy.
- Bắt buộc có benchmark trước/sau migration trên bộ scan thuốc chuẩn của CLARA.
- Duy trì fallback an toàn: barcode -> OCR -> xác nhận thủ công -> escalate.

## 6. Deliverables theo phase

| Phase | Deliverables chính |
|---|---|
| P0 | Chốt blueprint migration OCR/ADE; contract OCR/ADE v1; bộ benchmark scan thuốc + baseline metrics; mapping module reuse từ `tgc-transhub`. |
| P1 | Hoàn tất tích hợp staging cho OCR multi-pass + ADE scoring; bật telemetry layout; thiết lập quality gates và A/B report baseline cũ vs pipeline reuse. |
| P2 | Đưa migration vào Self-Med MVP end-to-end; policy routing theo confidence (auto-accept/manual confirm); dashboard theo dõi OCR/ADE quality + manual review queue. |
| P3 | Tích hợp doctor handoff + scribe input cho ca cảnh báo cao cần hội chẩn. |
| P4-P6 | Hardening, tối ưu vận hành, mở rộng cohort và tích hợp đối tác. |

## 7. Dashboard cần có cho nhánh Self-Med

- Medication adherence rate theo bệnh nhân/hộ gia đình.
- Alert funnel: generated -> acknowledged -> acted -> escalated.
- DDI critical trend theo nhóm nguy cơ.
- Expiry risk board (thuốc sắp hết hạn/chưa kiểm kê).
- False alert rate và missed alert rate.
- OCR/ADE quality panel: confidence distribution, low-confidence rate, manual review rate.

## 8. KPI nhánh Self-Med

- Reminder delivery SLA >= 99%.
- DDI critical sensitivity >= 98%.
- Escalation success within SLA >= 95%.
- Cảnh báo nguy cơ cao phản hồi < 5 giây.
- `avg_layout_smoothness_score >= 85` cho bộ scan thuốc chuẩn.
- `avg_overlap_duplicate_rate <= 0.03` ở pipeline OCR/ADE đã reuse.

## 9. Rủi ro và kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| OCR sai tên thuốc | quality threshold + xác nhận lại bởi người dùng |
| Dữ liệu dị ứng thiếu | bắt buộc onboarding hồ sơ trước DDI nâng cao |
| Alert fatigue | phân tầng cảnh báo theo severity + ngữ cảnh |
| Lệch guideline | verification node + source priority policy |
| Migration OCR/ADE gây regression | chạy regression gate theo benchmark trước khi rollout |

## 10. Tiêu chí hoàn tất

1. Self-Med chạy ổn định trên web và Flutter app.
2. DDI + allergy + escalation có log kiểm chứng đầy đủ.
3. Dashboard theo dõi được chất lượng vận hành và tuân thủ điều trị.
4. Migration OCR/ADE P0-P2 hoàn thành với chất lượng không thấp hơn baseline cũ.
