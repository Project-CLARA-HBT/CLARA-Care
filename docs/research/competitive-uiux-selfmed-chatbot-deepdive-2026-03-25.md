# Deepdive Đối Thủ UI/UX Chatbot Y Tế + Self-Med (2026-03-25)

## 1) Mục tiêu

Tài liệu này tổng hợp nhanh các sản phẩm tương tự để:

- học flow giao diện chatbot dễ dùng kiểu Perplexity/Gemini,
- học flow tủ thuốc cá nhân (permanent cabinet) + nhắc thuốc + refill,
- học cách vận hành control panel cho RAG/answer-flow kiểu Dify,
- chuyển hóa thành checklist triển khai cụ thể cho CLARA Web.

## 2) Phạm vi nghiên cứu

- Nhóm `AI chat/research UX`: Perplexity, Gemini, Buoy.
- Nhóm `Self-Med/pillbox`: MyTherapy, GoodRx Medicine Cabinet, CareClinic, Medisafe.
- Nhóm `RAG control plane`: Dify Docs.

## 3) Kết quả deepdive theo sản phẩm

### 3.1 Perplexity (chat UX theo mode, học tập theo bước)

- Learn Mode có cơ chế học theo bước, không chỉ trả đáp án trực tiếp.
- Có toggle mode ngay ở thanh nhập để đổi cách trả lời theo ngữ cảnh.
- Có logic phản hồi theo tiến trình học (guiding question, step-by-step).

Ứng dụng cho CLARA:

- Giữ `mode switch` ngay ở composer: `Nhanh` / `Chuyên sâu`.
- Kết quả phải có `phân lớp`: tóm tắt chính -> bằng chứng -> bước tiếp theo.
- Với end user, ưu tiên nhánh trả lời ngắn + CTA hành động an toàn.

### 3.2 Gemini (entrypoint đơn giản, tập trung vào 1 ô nhập)

- Giao diện mở đầu tối giản, tập trung 1 input trung tâm.
- Có nhóm gợi ý tác vụ ngay dưới ô nhập, giảm tải nhận thức cho người mới.

Ứng dụng cho CLARA:

- Trang Research mở đầu kiểu `single-focus composer`.
- Thêm suggestion chips theo role/use case (người dân, researcher, bác sĩ).

### 3.3 Dify (workflow control plane + log)

- Dify nhấn mạnh `If/Else`, branching, workflow node rõ ràng.
- Có `Run History` hiển thị output, metadata, tracing theo node.
- Mô hình điều hành: cấu hình nguồn tri thức + debug flow trong 1 panel.

Ứng dụng cho CLARA:

- Admin dashboard tách riêng, không trộn với user UI.
- Có tab bắt buộc: `RAG Sources`, `Answer Flow`, `Observability`.
- Hiển thị rõ các bật/tắt: role router, intent router, verifier, fallback.

### 3.4 MyTherapy / GoodRx / CareClinic / Medisafe (self-med)

Điểm chung mạnh:

- Tủ thuốc là thực thể lâu dài (`permanent cabinet`) theo tài khoản.
- Trọng tâm là reminder + refill + theo dõi tồn thuốc + dữ liệu theo thời gian.
- Có cơ chế thêm thuốc nhanh (search, chọn loại, match ảnh/định danh).
- Có hướng caregiver/care-team để giảm bỏ liều.

Ứng dụng cho CLARA:

- Self-Med phải là module riêng (không chỉ card trong dashboard).
- Flow chính: `Quét hóa đơn -> nhận diện thuốc -> add vào tủ -> auto DDI`.
- Ưu tiên action “đủ dùng”: thêm thuốc, chỉnh sửa, xóa, lịch nhắc, refill.

### 3.5 Buoy / K Health (triage & care routing)

- Tập trung câu hỏi dẫn dắt từng bước, sau đó điều hướng care path.
- Rõ trạng thái “đi khám ngay” vs “theo dõi tại nhà”.

Ứng dụng cho CLARA:

- Trong phản hồi DDI/cảnh báo phải có CTA triage rõ ràng.
- Mỗi kết luận cần gắn mức khẩn cấp và hành động tương ứng.

## 4) Gap chính của CLARA hiện tại (trước đợt rebuild FE này)

- Landing còn đúng thông tin nhưng chưa đủ mạnh về chuyển đổi (hero + proof + CTA funnel chưa sắc).
- Điều hướng còn nhiều nhãn kỹ thuật, chưa ưu tiên ngôn ngữ end-user.
- Chat UX còn nhiều block hiển thị kỹ thuật, thiếu nhịp “đọc nhanh -> đào sâu”.
- Self-Med đã có chức năng cốt lõi nhưng chưa “app-like” đủ rõ luồng chính cho người mới.

## 5) Quy tắc thiết kế chốt cho lần rebuild

- Tối đa 1 CTA chính trên mỗi khung hero.
- Mỗi trang chỉ có 1 mục tiêu nhận thức chính.
- Từ ngữ ưu tiên hành động thực tế, không dùng thuật ngữ ML nặng ở UI người dùng.
- Mọi cảnh báo y tế cần có `mức độ + hành động + giới hạn miễn trừ`.
- Navbar sắp theo hành trình người dùng, không sắp theo module kỹ thuật.

## 6) Danh sách nguồn tham chiếu

- Perplexity Help Center (Learn Mode): https://www.perplexity.ai/help-center/en/articles/12120542-what-is-learn-mode
- Gemini Apps Help: https://support.google.com/gemini?hl=en&p=temp_chats
- Dify If-Else Node: https://docs.dify.ai/en/guides/workflow/node/ifelse
- Dify Run History: https://docs.dify.ai/en/guides/workflow/debug-and-preview/history-and-logs
- Dify Knowledge/RAG: https://docs.dify.ai/en/learn-more/extended-reading/retrieval-augment
- GoodRx Medicine Cabinet: https://support.goodrx.com/hc/en-us/articles/17613838405019-Medicine-Cabinet
- MyTherapy app page (medication reminder + inventory/report): https://www.mytherapyapp.com/app-for-high-cholesterol-treatment
- CareClinic Treatment Tracker: https://careclinic.io/treatment-tracker/
- K Health App: https://khealth.com/app/
- Buoy Health: https://www.buoyhealth.com/
- Medisafe website (solution taxonomy / caregiver support): https://www.medisafe.com/
- Drugs.com Interaction Checker: https://www.drugs.com/drug_interactions.html

## 7) Ghi chú suy luận

- Một số đề xuất UI/flow ở trên là suy luận tổng hợp từ nhiều nguồn (không phải quote trực tiếp).
- Các quyết định về conversion/IA được tùy biến theo bối cảnh CLARA (health + RAG + self-med), không sao chép nguyên mẫu.
