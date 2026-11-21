# Có thể đọc được mục đích khai báo của bao nhiêu sự kiện?

Trong 13 ví dụ AuditEvent chính thức của HL7 FHIR R5, **ba sự kiện có mã PurposeOfUse ở cấp sự kiện**. Một ví dụ khác chỉ ghi mục đích cho tác nhân. Chín ví dụ còn lại thiếu khai báo ở cả hai cấp. Bản chiếu giữ mã theo phạm vi và truy vấn SQL đọc trực tiếp tài liệu đầy đủ trả về cùng kết quả trên cả 13 ví dụ, kể cả khi thiếu mã. Vì vậy loại tuyên bố bản chiếu tăng độ đúng cho tác vụ đọc mã trên bộ này. [Danh mục ví dụ HL7](https://hl7.org/fhir/R5/auditevent-examples.html) · [13 kết quả và digest của từng câu trả lời](results.json)

| Ví dụ có khai báo | Mã sự kiện | Mã tác nhân |
|---|---|---|
| Advanced create | TREAT | Vắng |
| Breakglass start | ETREAT | Vắng |
| Consent authorization | Vắng | TREAT |
| Disclosure | HMARKT | HMARKT |

Cả năm Coding quan sát được đều là thành viên PurposeOfUse trong phiên bản thuật ngữ đã ghim. Định nghĩa của FHIR cho phép ghi authorization rộng hơn và gắn bộ mã ở mức *example*. Chương trình giữ nguyên thứ tự của từng CodeableConcept, từng Coding, mã hệ thống, phiên bản, giá trị và vị trí tác nhân. Mã chỉ xuất hiện ở tác nhân vẫn thuộc tác nhân đó. [Định nghĩa AuditEvent](https://hl7.org/fhir/R5/auditevent-definitions.html) · [Bộ mã HL7 PurposeOfUse](https://terminology.hl7.org/5.1.0/ValueSet-v3-PurposeOfUse.html)

FQ-AUTH-02 hỏi mục đích nào *đã biện minh cho hành động được commit*. Ba giá trị cấp sự kiện cung cấp nhãn cho **mục đích ghi trong bản khai**. Những ví dụ minh họa này thiếu phép quan sát độc lập về giao dịch commit, hiệu lực consent và việc hệ thống thực sự dùng mục đích đó khi quyết định. Kết quả 13/13 đo khả năng đọc đúng cả giá trị lẫn dấu hiệu thiếu. Dùng bộ này làm ground truth cho toàn bộ câu hỏi FQ-AUTH-02 sẽ vượt phạm vi chứng cứ. Phép thử không vận hành toàn bộ cơ chế ReceiptMin hoặc đo đánh đổi quyền riêng tư sau thời hạn lưu trữ. [Câu hỏi đã đóng băng](../../../../evaluation/venue2027/pst/forensic_queries.py) · [Kế hoạch development](PROTOCOL.md)

## Tái lập

Từ thư mục này, chạy với Python 3 có SQLite JSON1 và Node.js. Bên đọc SQL truy vấn trực tiếp cấu trúc nguyên bản. Bên chiếu Python chỉ lưu cây mã. Chương trình JavaScript kiểm độc lập từng cây mã và duyệt hệ thống phân cấp thuật ngữ theo chiều ngược lại. Quy trình chạy trên CPU WSL2. Lượt chạy lại tái tạo cùng kết quả. Kho lưu chỉ chứa mã nguồn, bản đếm, digest và URL của tài liệu HL7. [17 nguồn và checksum](sources.json)

```bash
python3 fetch.py scratch > replay-sources.json
cmp replay-sources.json sources.json
python3 measure.py scratch > replay.json
cmp results.json replay.json
node --check verify.mjs
node verify.mjs scratch sources.json replay.json
```
