# Đề Xuất Nhánh Sản Phẩm CLARA Self-Med

Phiên bản: 1.1  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu nhánh Self-Med

CLARA Self-Med là nhánh app/web quản lý thuốc cá nhân cho gia đình, tập trung vào:
- An toàn dùng thuốc (đúng thuốc, đúng liều, đúng thời điểm).
- Giảm rủi ro tương tác thuốc, dị ứng, quá liều.
- Nâng cao tuân thủ điều trị và giảm gánh nặng người chăm sóc.

## 2. Tính cấp thiết

### 2.1 Rủi ro tương tác và sai sót dùng thuốc
- Tỷ lệ tương tác thuốc có ý nghĩa lâm sàng cao ở nhóm nguy cơ.
- Hậu quả có thể gồm ADR nghiêm trọng, độc tính, giảm hiệu quả điều trị.
- Cần mô-đun DDI check và cảnh báo trước liều dùng.

### 2.2 Tự điều trị và lạm dụng thuốc
- Tỷ lệ tự dùng thuốc cao, nhiều trường hợp thiếu nhãn/thông tin chuẩn.
- Lạm dụng kháng sinh/kháng viêm làm tăng rủi ro kháng thuốc và tổn thương cơ quan.
- Cần kênh thông tin chuẩn hóa chống tin giả.

### 2.3 Gánh nặng người chăm sóc
- Người chăm sóc thường lo lắng không biết bệnh nhân đã uống thuốc đúng chưa.
- Không tuân thủ điều trị làm tăng tái nhập viện và chi phí.
- Cần family dashboard và escalation alerts theo thời gian thực.

### 2.4 Thuốc hết hạn và ngộ độc trẻ em
- Nhiều hộ gia đình giữ thuốc quá hạn hoặc không nhãn mác.
- Trẻ em có nguy cơ uống nhầm thuốc/hóa chất tại nhà.
- Cần hướng dẫn bảo quản, kiểm kê định kỳ và tiêu hủy an toàn.

## 3. Tính năng trọng tâm

### 3.1 Số hóa tủ thuốc
- Quét mã vạch hoặc chụp đơn thuốc để nhận diện thuốc/hoạt chất.
- Chuẩn hóa định danh bằng RxCUI, kết nối cảnh báo openFDA khi phù hợp.
- Phân loại theo thành viên gia đình và mức rủi ro.

### 3.2 DDI Safe và cảnh báo dị ứng
- Kiểm tra tương tác trước mỗi liều dùng.
- Cảnh báo tức thì khi thuốc trùng với tiền sử dị ứng.
- Phân tầng cảnh báo: critical/major/moderate/minor.

### 3.3 Nhắc lịch và theo dõi tuân thủ
- Tạo lịch uống thuốc tự động từ đơn đã quét.
- Family dashboard để người nhà cùng theo dõi.
- Escalation alert nếu trễ liều (ví dụ 30-40 phút).

### 3.4 Bảo quản, kiểm kê và tiêu hủy
- Nhắc kiểm kê định kỳ và phát hiện thuốc hết hạn.
- Hướng dẫn bảo quản theo nhiệt độ/ánh sáng.
- Hướng dẫn tiêu hủy thuốc an toàn, giảm tác động môi trường.

### 3.5 Tra cứu tri thức chống tin giả
- Hỏi đáp bằng chứng hóa qua agentic RAG.
- Trả lời có trích dẫn chuẩn hóa, giải thích đơn giản cho người dân.
- Nêu rõ giới hạn hệ thống và khi nào cần liên hệ bác sĩ.

## 4. Quyết định kỹ thuật cho Self-Med

- Dùng **LangChain/LangGraph** để điều phối luồng AI cho:
  - DDI explanation flow
  - allergy risk explanation flow
  - storage/disposal guidance flow
- Backend API: ưu tiên Rust cho hiệu năng và độ ổn định.
- Node tổng hợp và node kiểm chứng tách riêng, policy gate bắt buộc.
- Với các quyết định hard-stop (DDI critical/allergy critical), dùng rule engine + DB chuẩn, không phụ thuộc LLM thuần.

## 5. CLARA Control Tower cho Self-Med

Dashboard phục vụ Product/Ops/Clinical/Security với các bảng điều khiển:
1. **Medication Safety Board**: DDI alerts, allergy alerts, false alert trends.
2. **Adherence Board**: nhắc lịch đúng giờ, trễ liều, escalation xử lý thành công.
3. **Family Care Board**: phân bổ người chăm sóc, mức tải cảnh báo theo hộ gia đình.
4. **Source Freshness Board**: trạng thái pipeline BYT/Dược thư/openFDA/RxNorm.
5. **Incident Board**: lỗi OCR, mapping sai thuốc, lỗi cảnh báo critical.

## 6. Business model cho Self-Med

### 6.1 Mô hình doanh thu
- Freemium cho người dùng cá nhân.
- Gói Family Plus: nhiều thành viên, escalation nâng cao, báo cáo định kỳ.
- Gói Partner: tích hợp nhà thuốc/đơn vị chăm sóc.

### 6.2 Đòn bẩy tăng trưởng
- Hợp tác nhà thuốc và phòng khám gia đình.
- Chương trình giáo dục cộng đồng về dùng thuốc an toàn.
- Referral từ nhóm người chăm sóc bệnh mạn tính.

## 7. Roadmap P0 -> P6 (Self-Med + Control Tower)

| Phase | Deliverables Self-Med | Deliverables Control Tower |
|---|---|---|
| P0 | Quét thuốc cơ bản + hồ sơ thuốc nền | Safety widget nền + source health |
| P1 | Nhắc lịch + DDI + dị ứng cơ bản | Policy gate cho DDI + role/tenant controls |
| P2 | Family dashboard + escalation alerts | Adherence board + DDI board + drift cảnh báo |
| P3 | Bảo quản/kiểm kê/tiêu hủy + tri thức chuẩn | Incident center + clinical escalation queue |
| P4 | Tích hợp bác sĩ thật + tư vấn mở rộng | Audit/compliance explorer cho Self-Med |
| P5 | Partner APIs (nhà thuốc/chăm sóc) | Multi-tenant governance + cost board |
| P6 | Regional rollout + localization | Liên thông dashboard đa vùng |

## 8. KPI nhánh Self-Med

- Tỷ lệ tuân thủ uống thuốc theo tuần/tháng.
- Tỷ lệ phát hiện tương tác nghiêm trọng trước khi dùng.
- Tỷ lệ trễ liều được can thiệp thành công qua escalation.
- Tỷ lệ thuốc hết hạn được xử lý đúng quy trình.
- Tỷ lệ câu trả lời có citation và mức hài lòng người dùng.

## 9. Risk controls nhánh Self-Med

- Cảnh báo sai: verification + threshold + human escalation.
- Lạm dụng app thay bác sĩ: disclaimer và trigger chuyển tuyến.
- Rủi ro dữ liệu cá nhân: mã hóa, phân quyền, lưu tối thiểu.
- Rủi ro thuốc không nhãn: bắt buộc xác nhận lại và gắn confidence level.

## 10. Quyết định đề xuất

1. Chốt Self-Med sử dụng LangChain/LangGraph cho orchestration AI flow.
2. Chốt Self-Med Control Tower là năng lực bắt buộc để vận hành an toàn ở quy mô lớn.
3. Không mở rộng phase nếu KPI safety chưa đạt gate.
