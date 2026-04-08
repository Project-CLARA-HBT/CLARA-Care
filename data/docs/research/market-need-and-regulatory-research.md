# Nghiên Cứu Nhu Cầu Thị Trường Và Khung Pháp Lý: CLARA Research + CLARA Self-Med

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu tài liệu

Tài liệu này trả lời 3 câu hỏi cốt lõi:
1. Vì sao CLARA Self-Med cần triển khai ngay trong bối cảnh Việt Nam?
2. Rủi ro trách nhiệm (liability) lớn nhất nằm ở đâu khi tư vấn dùng thuốc tại nhà?
3. Khung pháp lý và mô hình thị trường nào khả thi cho 2 nhánh CLARA Research và CLARA Self-Med?

## 2. Bối cảnh cấp thiết của Self-Med

## 2.1 Gánh nặng tương tác thuốc và sai sót dùng thuốc

- Tương tác thuốc có ý nghĩa lâm sàng được ghi nhận rất cao ở các nhóm nguy cơ: người cao tuổi nội trú có thể tới **47,9%**, bệnh nhân đột quỵ có thể tới **72,2%**.
- Hậu quả thường gặp: ADR, độc tính do cộng hưởng, giảm hiệu quả điều trị, tăng tái nhập viện và tử vong phòng ngừa được.
- Điều này tạo ra nhu cầu bắt buộc cho mô-đun `DDISafe` trong Self-Med.

## 2.2 Tự điều trị và sử dụng thuốc không kiểm soát

- Tự điều trị thuốc tân dược ở cộng đồng ở mức cao (ước lượng ghi nhận trong các note dự án: **65,8%**).
- Tình trạng thuốc thiếu nhãn/không có thông tin đi kèm rất phổ biến (note dự án nêu tới **90%** trong nhóm tự điều trị).
- Tự mua kháng sinh/kháng viêm làm tăng nguy cơ kháng kháng sinh và tổn thương gan-thận.

## 2.3 Gánh nặng cho người chăm sóc và hộ gia đình

- Người chăm sóc thường chịu áp lực theo dõi liều dùng, dễ bỏ sót hoặc dùng trùng liều.
- Không tuân thủ điều trị ở bệnh mạn thường cao, kéo theo chi phí y tế tăng.
- Self-Med cần có `Family Dashboard`, nhắc liều, cảnh báo leo thang và nhật ký tuân thủ.

## 2.4 Rủi ro thuốc hết hạn và ngộ độc trẻ em

- Thuốc hết hạn vẫn bị giữ lại do thói quen tiết kiệm/chủ quan.
- Trẻ nhỏ dễ ngộ độc do uống nhầm thuốc hoặc hóa chất, trong khi sơ cứu tại nhà thường sai.
- Self-Med phải có module giáo dục an toàn bảo quản/tiêu hủy.

## 3. Cấu trúc sản phẩm và phân vai thị trường

## 3.1 Hai nhánh sản phẩm

- **CLARA Research**: phục vụ truy xuất bằng chứng y khoa, tổng hợp guideline, hỗ trợ nghiên cứu và lâm sàng có kiểm chứng.
- **CLARA Self-Med**: phục vụ người dùng cá nhân/gia đình quản lý thuốc, an toàn dùng thuốc và tư vấn tri thức chuẩn hóa.

## 3.2 Định vị khách hàng mục tiêu

| Nhánh | Khách hàng chính | Giá trị cốt lõi | KPI giá trị |
|---|---|---|---|
| CLARA Research | bác sĩ, researcher, bệnh viện, trường y | truy xuất bằng chứng nhanh + có kiểm chứng | thời gian tìm bằng chứng, tỷ lệ trích dẫn hợp lệ |
| CLARA Self-Med | hộ gia đình, người cao tuổi, người chăm sóc | giảm sai sót dùng thuốc và tăng tuân thủ | tỷ lệ bỏ liều, tỷ lệ cảnh báo đúng, tỷ lệ xử lý thuốc hết hạn |

## 3.3 Tại sao triển khai song song

- Research cung cấp tri thức và pipeline kiểm chứng cho Self-Med.
- Self-Med cung cấp dữ liệu hành vi thực tế để tinh chỉnh cảnh báo và ưu tiên nghiên cứu.
- Mô hình song trục giúp cân bằng tác động xã hội và mô hình doanh thu.

## 4. Liability map (bản đồ trách nhiệm)

## 4.1 Vùng trách nhiệm cao

1. Cảnh báo DDI sai hoặc bỏ sót tương tác nghiêm trọng.
2. Gợi ý liều không phù hợp lứa tuổi/chức năng gan-thận.
3. Nhầm nhận diện thuốc từ ảnh/OCR.
4. Diễn giải sai thông tin từ mạng xã hội hoặc nguồn không chuẩn.

## 4.2 Cơ chế giảm trách nhiệm

- Mọi claim rủi ro cao phải qua `FIDES Verification Module`.
- Tách rõ 2 node: `Synthesis` và `Verification`.
- Chính sách `allow / warn / block / escalate` theo mức nguy cơ.
- Gắn disclaimer theo ngữ cảnh và bắt buộc chuyển tuyến khi nghi ngờ nguy cấp.

## 5. Khung pháp lý và tuân thủ

## 5.1 Việt Nam

- Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân: yêu cầu thu thập tối thiểu, mục đích rõ, quản trị truy cập và lưu vết.
- Dữ liệu sức khỏe là dữ liệu nhạy cảm: cần cơ chế đồng ý rõ ràng, quyền rút lại đồng ý, và nhật ký truy cập.
- Với tính năng tư vấn thuốc, cần kiểm soát ngôn ngữ để không vượt quá phạm vi “hỗ trợ thông tin” khi chưa có hành lang thiết bị y tế đầy đủ.

## 5.2 Quốc tế (tham chiếu)

- HIPAA/GDPR là baseline tham chiếu cho thiết kế privacy-by-design.
- Cơ chế giải trình AI cần chuẩn bị cho yêu cầu minh bạch mô hình trong tương lai.

## 6. Mô hình triển khai thị trường đề xuất

## 6.1 Giai đoạn 1 (0-6 tháng)

- Pilot kín tại một số cơ sở y tế/đơn vị đào tạo và hộ gia đình tự nguyện.
- Tập trung DDISafe, nhắc liều, OCR đơn thuốc, cảnh báo dị ứng.

## 6.2 Giai đoạn 2 (6-12 tháng)

- Mở rộng Family Dashboard, workflow escalation cho người chăm sóc.
- Bổ sung xử lý thuốc hết hạn, kháng sinh thừa, hướng dẫn tiêu hủy.

## 6.3 Giai đoạn 3 (12+ tháng)

- Tích hợp marketplace bác sĩ (tele-consult/recommendation có kiểm soát).
- Chuẩn hóa hợp đồng API với hệ thống bệnh viện/đối tác.

## 7. KPIs thị trường và tác động

- Giảm tỷ lệ bỏ liều ở nhóm dùng thuốc mạn tính.
- Tăng tỷ lệ phát hiện sớm DDI có ý nghĩa lâm sàng.
- Giảm tỷ lệ dùng thuốc hết hạn/không nhãn trong mẫu người dùng hoạt động.
- Tăng tỷ lệ người chăm sóc báo cáo giảm căng thẳng theo khảo sát định kỳ.

## 8. Giả định, giới hạn và bước nghiên cứu tiếp

- Số liệu dịch tễ và hành vi dùng thuốc có khác biệt theo vùng, cần khảo sát pilot địa phương.
- Cần thiết kế nghiên cứu hậu triển khai (post-market surveillance) cho chất lượng cảnh báo.
- Cần mở rộng đối tác dữ liệu trong nước để tăng độ phủ tên biệt dược.

## 9. Nghiên cứu Ops Dashboard & Governance trong bối cảnh y tế

### 9.1 Vì sao dashboard là năng lực bắt buộc

- Khi triển khai song song Research + Self-Med, rủi ro vận hành tăng theo số role, số nguồn và số modality.
- Dashboard quản trị là điểm hợp nhất để theo dõi chất lượng, an toàn, tuân thủ, và hiệu quả vận hành theo thời gian thực.

### 9.2 Nhóm chỉ số ưu tiên cho dashboard

- Clinical safety: DDI critical miss rate, allergy alert precision, escalation SLA.
- Research quality: citation validity, conflict disclosure rate, progressive latency 5-10-20.
- Vận hành: uptime, queue depth, incident MTTR, source freshness status.
- Tuân thủ: consent status, access logs, data retention/deletion actions.

### 9.3 Governance bắt buộc

- Quản trị version model/prompt/policy theo cơ chế approve-promote-rollback.
- Quản trị nguồn dữ liệu theo trust tier (BYT/Dược thư/PubMed/RxNorm/openFDA/web recheck).
- Quản trị HITL queue cho các trường hợp high-risk.

## 10. LangChain/LangGraph suitability nhìn từ góc pháp lý-vận hành

### 10.1 Điểm mạnh

- Đẩy nhanh việc xây workflow kiểm chứng đa bước.
- Dễ thêm hàng đợi HITL, retries, và policy transitions.

### 10.2 Rủi ro

- Lock-in nếu quy trình nghiệp vụ bị “trói” vào graph runtime đặc thù.
- Tăng độ phức tạp release nếu không tách control-plane (Rust) và AI orchestration-plane.

### 10.3 Mô hình hybrid được đề xuất

- Rust giữ vai trò nền tảng kiểm soát và audit.
- LangGraph/LangChain xử lý luồng AI đa tác tử.
- Rule engine deterministic xử lý các quyết định chặn nguy cơ y khoa cao.

## 11. Checklist nghiên cứu triển khai dashboard an toàn clinical AI

1. Xác định rõ owner cho từng nhóm KPI (clinical/product/ops/compliance).
2. Thiết lập ngưỡng cảnh báo và playbook ứng phó theo severity.
3. Bắt buộc traceability từ phản hồi -> nguồn chứng cứ -> phiên bản model.
4. Bắt buộc lưu bằng chứng tuân thủ cho Nghị định 13.
5. Đảm bảo kiểm toán được mọi hành động `block/escalate`.
6. Tổ chức drill định kỳ cho tình huống mất nguồn dữ liệu chính.

## 12. Kết luận

Self-Med có nhu cầu thực và mức ưu tiên cao vì giải quyết đồng thời 4 vấn đề: DDI, tuân thủ điều trị, an toàn thuốc tại nhà và chống tin giả y tế. Triển khai song song với CLARA Research là hướng khả thi nhất để vừa đảm bảo chất lượng tri thức, vừa tạo tác động xã hội đo được; trong đó dashboard governance là điều kiện bắt buộc để mở rộng an toàn.
