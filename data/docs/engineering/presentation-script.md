# CLARA-Care - Kịch bản thuyết trình 15 phút

Tài liệu này dùng để thuyết trình, không đi sâu vào code. Mục tiêu là giải thích CLARA-Care hoạt động như một hệ thống trợ lý y tế có nhiều module liên kết với nhau: Chat, RAG, kiểm tra tương tác thuốc, hồ sơ cá nhân, nguồn nghiên cứu, hội chẩn AI và thư ký y khoa.

## 1. Mở đầu - 1 phút

CLARA-Care là một nền tảng hỗ trợ chăm sóc sức khỏe bằng AI. Hệ thống không chỉ là chatbot trả lời câu hỏi, mà có nhiều chức năng phục vụ các tình huống y tế khác nhau:

- Chat y tế có truy xuất bằng chứng.
- Kiểm tra tương tác thuốc trong tủ thuốc.
- Lưu hồ sơ sức khỏe cá nhân.
- Đồng bộ nguồn nghiên cứu từ bên ngoài.
- Hội chẩn AI nhiều góc nhìn chuyên khoa.
- Thư ký y khoa: ghi âm, chuyển thành văn bản và tạo SOAP note.

Điểm chính khi thuyết trình:

> CLARA-Care không để AI trả lời tự do hoàn toàn. Hệ thống luôn cố gắng đưa câu hỏi qua các bước kiểm tra an toàn, truy xuất nguồn, cá nhân hóa theo hồ sơ và tạo minh chứng cho câu trả lời.

## 2. Kiến trúc tổng quan - 1.5 phút

CLARA-Care gồm 3 lớp chính:

1. **Frontend**: nơi người dùng thao tác trên giao diện web.
2. **API backend**: nơi kiểm tra quyền, lưu dữ liệu, gom dữ liệu và gọi ML service.
3. **ML service**: nơi xử lý AI, RAG, kiểm tra thuốc, hội chẩn, scribe và các pipeline thông minh.

Luồng đơn giản:

```text
Người dùng thao tác
-> Frontend gửi request
-> API backend kiểm tra quyền và dữ liệu
-> ML service xử lý AI/RAG
-> Backend lưu kết quả nếu cần
-> Frontend hiển thị lại cho người dùng
```

Giải thích dễ hiểu:

> Frontend giống như quầy tiếp nhận. Backend giống như bộ phận điều phối và lưu hồ sơ. ML service giống như bộ phận chuyên môn AI, nơi thực hiện phân tích và sinh kết quả.

## 3. Luồng Chat và RAG - 2 phút

Khi người dùng hỏi CLARA-Care, hệ thống không gửi câu hỏi thẳng vào AI rồi trả lời ngay. Chat đi qua nhiều bước:

1. Người dùng nhập câu hỏi.
2. API lấy cấu hình RAG hiện tại từ Control Tower.
3. API gửi câu hỏi, vai trò người dùng và cấu hình nguồn sang ML service.
4. ML service kiểm tra an toàn, ví dụ không cho kê đơn hoặc chẩn đoán chắc chắn.
5. ML service phân loại ý định câu hỏi.
6. Nếu cần bằng chứng, RAG sẽ tìm tài liệu phù hợp.
7. AI sinh câu trả lời dựa trên tài liệu đã chọn.
8. Hệ thống kiểm tra lại câu trả lời và trả về cả thông tin nguồn.

RAG có thể lấy dữ liệu từ:

- Tài liệu nền có sẵn trong hệ thống.
- Nguồn đã cấu hình trong Control Tower.
- Tài liệu upload.
- Source Hub đã đồng bộ.
- Nguồn ngoài như PubMed, Europe PMC, Semantic Scholar, openFDA, DailyMed, RxNorm nếu được bật.

Nói đơn giản:

> RAG là cơ chế giúp AI không trả lời theo trí nhớ chung chung. Trước khi trả lời, hệ thống đi tìm các mảnh thông tin liên quan, chọn mảnh đáng tin hơn, rồi mới đưa vào ngữ cảnh cho AI.

Khi demo có thể nói:

> Ví dụ người dùng hỏi về triệu chứng hoặc thuốc. CLARA-Care sẽ route câu hỏi, kiểm tra an toàn, truy xuất tài liệu, sau đó trả lời kèm nguồn hoặc dấu vết truy xuất. Vì vậy câu trả lời có cơ sở hơn một chatbot thông thường.

## 4. Kiểm tra tương tác thuốc - CareGuard - 2 phút

CareGuard là module kiểm tra an toàn thuốc. Người dùng có thể thêm thuốc vào tủ thuốc, sau đó chạy kiểm tra tương tác.

Nguồn dữ liệu của CareGuard:

- Danh sách thuốc người dùng đã lưu trong tủ thuốc.
- Liều dùng nếu người dùng nhập.
- Dị ứng hoặc bối cảnh sức khỏe nếu có.
- Bộ luật tương tác thuốc nội bộ.
- Nguồn thuốc bên ngoài như RxNorm, openFDA.

Luồng xử lý:

1. Frontend hiển thị tủ thuốc.
2. Người dùng bấm kiểm tra tương tác.
3. Backend lấy danh sách thuốc trong tủ.
4. Backend gửi danh sách thuốc sang ML service.
5. ML service chuẩn hóa tên thuốc.
6. Hệ thống so với luật tương tác nội bộ.
7. Nếu cần, hệ thống bổ sung bằng chứng từ nguồn thuốc bên ngoài.
8. Kết quả trả về gồm mức rủi ro, cảnh báo và khuyến nghị.

Ví dụ demo:

```text
Warfarin + Ibuprofen
-> Có nguy cơ tăng chảy máu
-> Mức rủi ro cao
-> Khuyến nghị hỏi bác sĩ/dược sĩ trước khi dùng chung
```

Điểm cần nhấn mạnh:

> CareGuard không thay bác sĩ kê đơn. Nó đóng vai trò cảnh báo sớm để người dùng không bỏ qua nguy cơ tương tác thuốc.

## 5. Hồ sơ sức khỏe cá nhân - PHR - 1.5 phút

PHR là nơi lưu thông tin sức khỏe cá nhân của người dùng.

Dữ liệu có thể gồm:

- Dị ứng.
- Bệnh nền.
- Thuốc đang dùng.
- Thông tin cơ bản khác phục vụ cá nhân hóa.

PHR tác động đến hệ thống như sau:

- Khi nghiên cứu hoặc tư vấn cá nhân hóa, hệ thống có thêm bối cảnh về người dùng.
- Khi kiểm tra thuốc, dị ứng và bệnh nền có thể làm thay đổi mức cảnh báo.
- Khi chat ở chế độ cá nhân hóa, câu trả lời có thể nhắc đến yếu tố liên quan trong hồ sơ.

Ví dụ dễ hiểu:

> Nếu hai người hỏi cùng một câu về thuốc giảm đau, nhưng một người có tiền sử dị ứng hoặc đang dùng thuốc chống đông, hệ thống cần cảnh báo khác nhau. PHR giúp CLARA-Care hiểu bối cảnh đó.

Điểm cần nói rõ:

> PHR không phải để AI tự quyết định điều trị. Nó giúp hệ thống đưa cảnh báo phù hợp hơn với hoàn cảnh của người dùng.

## 6. Nguồn nghiên cứu và đồng bộ nguồn - 2 phút

Source Hub là nơi CLARA-Care đồng bộ dữ liệu từ các nguồn nghiên cứu và nguồn thuốc bên ngoài.

Các nguồn có thể gồm:

- PubMed: bài báo y sinh.
- Europe PMC: bài nghiên cứu y học.
- Semantic Scholar: bài nghiên cứu học thuật.
- ClinicalTrials: thử nghiệm lâm sàng.
- RxNorm/RxNav: chuẩn hóa tên thuốc.
- openFDA và DailyMed: nhãn thuốc và thông tin thuốc.
- Nguồn Việt Nam như Bộ Y tế, Cục Quản lý Dược, văn bản pháp luật hoặc DAVIDrug.

Luồng đồng bộ:

```text
Người dùng chọn nguồn
-> Nhập từ khóa
-> Backend gọi API hoặc đọc HTML nguồn ngoài
-> Chuẩn hóa kết quả thành record
-> Lưu vào database
-> Khi RAG cần, hệ thống lọc record liên quan và đưa vào tài liệu truy xuất
```

Cách giải thích khi thuyết trình:

> Source Hub giống như thư viện kết nối. Mỗi nguồn có một cách lấy dữ liệu riêng, nhưng sau khi lấy về, CLARA-Care chuẩn hóa chúng về một dạng chung. Nhờ vậy RAG có thể dùng PubMed, openFDA hay nguồn Việt Nam theo cùng một pipeline.

Điểm kỹ thuật dễ hiểu:

- Nguồn có API thì gọi API JSON.
- Nguồn là website thì tải HTML và trích thông tin phù hợp.
- Dữ liệu sau khi lấy không đưa thẳng cho AI, mà phải qua lọc, chấm điểm và chọn nguồn liên quan.

## 7. Hội chẩn AI - Council - 1.5 phút

Council là module mô phỏng hội chẩn nhiều góc nhìn. Thay vì một câu trả lời đơn lẻ, hệ thống phân tích ca bệnh theo nhiều vai trò chuyên khoa.

Luồng xử lý:

1. Người dùng tạo ca hội chẩn.
2. Nhập thông tin ca bệnh, transcript hoặc audio.
3. Hệ thống chuẩn hóa dữ liệu đầu vào.
4. Các vai trò chuyên môn phân tích từng phần.
5. Hệ thống tổng hợp đồng thuận, điểm chưa chắc chắn và cảnh báo cần chuyển tuyến.

Ví dụ các góc nhìn:

- Nội tổng quát.
- Dược lâm sàng.
- Cấp cứu.
- Điều dưỡng/chăm sóc.
- Tổng hợp cuối cùng.

Điểm cần nhấn mạnh:

> Council không phải nhiều AI tranh luận cho vui. Mục tiêu là chia vấn đề thành nhiều góc nhìn để hạn chế bỏ sót rủi ro, đặc biệt trong ca có thuốc, triệu chứng nặng hoặc dữ liệu chưa rõ.

## 8. Thư ký y khoa - Scribe - 2 phút

Scribe giúp bác sĩ hoặc người dùng ghi lại buổi tư vấn.

Luồng chính:

1. Người dùng bấm ghi âm.
2. Trình duyệt xin quyền microphone.
3. Frontend dùng `MediaRecorder` để ghi âm thành từng đoạn ngắn.
4. Các đoạn audio được gửi lên backend.
5. Backend chuyển tiếp sang ML service.
6. ML service gọi hệ thống speech-to-text.
7. Text được ghép thành transcript.
8. Từ transcript, hệ thống tạo SOAP note.

Kỹ thuật chuyển giọng nói thành văn bản:

- Frontend dùng browser microphone API và `MediaRecorder`.
- Audio thường là `webm/opus`, chia thành chunk khoảng 2.8 giây.
- Backend nhận audio và kiểm tra định dạng/kích thước.
- ML service gọi endpoint `/v1/audio/transcriptions`.
- Trong repo có ASR adapter local dùng **Whisper qua faster-whisper**.
- Model mặc định có thể cấu hình, ví dụ `small`, chạy CPU `int8` để đủ nhẹ cho demo.

Nói dễ hiểu:

> Phần ghi âm không phải AI nghe trực tiếp trong trình duyệt. Trình duyệt chỉ thu âm. Sau đó audio được gửi đến dịch vụ nhận dạng giọng nói, dịch vụ này dùng Whisper để chuyển âm thanh thành chữ.

SOAP note là gì:

- **S - Subjective**: lời kể/chủ quan của bệnh nhân.
- **O - Objective**: thông tin khách quan, chỉ số, dấu hiệu.
- **A - Assessment**: nhận định sơ bộ.
- **P - Plan**: kế hoạch hoặc bước tiếp theo.

Điểm cần nhấn mạnh:

> Scribe giúp tiết kiệm thời gian ghi chép, nhưng kết quả vẫn cần người chuyên môn kiểm tra lại trước khi dùng chính thức.

## 9. Tác động giữa các module - 1 phút

Các module không tách rời nhau. Chúng hỗ trợ nhau:

- Chat dùng RAG để lấy bằng chứng.
- Source Hub cung cấp thêm nguồn cho RAG.
- PHR cung cấp bối cảnh cá nhân.
- CareGuard dùng danh sách thuốc và có thể liên quan đến PHR.
- Council dùng transcript/audio hoặc thông tin ca bệnh để phân tích đa góc nhìn.
- Scribe tạo transcript và SOAP, có thể dùng làm đầu vào cho hội chẩn hoặc hồ sơ.

Luồng tổng hợp:

```text
PHR + Tủ thuốc + Source Hub + Transcript
-> RAG / CareGuard / Council / Scribe
-> Kết quả có cảnh báo, khuyến nghị và bằng chứng
```

Một câu dễ nói:

> CLARA-Care giống một hệ sinh thái nhỏ. Mỗi module giải quyết một việc riêng, nhưng dữ liệu có thể hỗ trợ qua lại để tạo ra câu trả lời và cảnh báo có ngữ cảnh hơn.

## 10. Kịch bản demo nhanh - 1 phút

Nếu chỉ có 1 phút demo, nên đi theo thứ tự:

1. Mở Chat, hỏi một câu y tế có cần bằng chứng.
2. Chỉ ra hệ thống có RAG/source/debug hoặc nguồn tham khảo.
3. Mở tủ thuốc, chạy kiểm tra tương tác thuốc.
4. Mở Source Hub, nói hệ thống có thể đồng bộ PubMed/openFDA/RxNorm.
5. Mở Scribe, nói ghi âm được chuyển thành transcript và SOAP.

Câu dẫn:

> Tôi sẽ demo nhanh 3 năng lực chính: trả lời có bằng chứng, kiểm tra an toàn thuốc và biến ghi âm thành ghi chú y khoa.

## 11. Phân bổ thời gian thuyết trình 15 phút

| Phần | Thời lượng |
|---|---:|
| Mở đầu và mục tiêu hệ thống | 1 phút |
| Kiến trúc tổng quan | 1.5 phút |
| Chat và RAG | 2 phút |
| CareGuard tương tác thuốc | 2 phút |
| PHR hồ sơ cá nhân | 1.5 phút |
| Source Hub và đồng bộ nguồn | 2 phút |
| Council hội chẩn AI | 1.5 phút |
| Scribe ghi âm, transcript, SOAP | 2 phút |
| Tổng kết liên kết module | 1 phút |
| Dự phòng hỏi đáp/demo lỗi | 0.5 phút |

## 12. Kết luận - 30 giây

CLARA-Care hướng tới một hệ thống hỗ trợ y tế an toàn hơn chatbot thông thường. Hệ thống có guard an toàn, có truy xuất bằng chứng, có cá nhân hóa theo hồ sơ, có kiểm tra tương tác thuốc, có đồng bộ nguồn nghiên cứu, có hội chẩn AI và có thư ký y khoa.

Thông điệp kết:

> Điểm mạnh của CLARA-Care là không đặt toàn bộ niềm tin vào một câu trả lời AI duy nhất. Hệ thống chia bài toán thành nhiều pipeline: kiểm tra an toàn, lấy bằng chứng, cá nhân hóa, phân tích thuốc, hội chẩn và ghi chép. Nhờ vậy kết quả dễ kiểm soát hơn, dễ giải thích hơn và phù hợp hơn cho bối cảnh chăm sóc sức khỏe.

## 13. Kịch bản thuyết trình demo trực tiếp

Phần này dùng khi vừa thuyết trình vừa thao tác trên hệ thống. Nên chuẩn bị sẵn dữ liệu trước khi demo: đăng nhập tài khoản, có vài thuốc trong tủ thuốc, có một hồ sơ PHR mẫu, Source Hub đã có vài record sync sẵn, và có transcript mẫu cho Scribe/Council nếu microphone hoặc mạng không ổn.

### 13.1. Mở demo - 30 giây

Câu nói:

> Sau phần giới thiệu kiến trúc, em sẽ demo nhanh CLARA-Care theo một tình huống thực tế: người dùng có câu hỏi y tế, có danh sách thuốc đang dùng, cần kiểm tra tương tác, cần tham khảo nguồn nghiên cứu, và cuối cùng bác sĩ có thể dùng Scribe để tạo ghi chú SOAP.

Mục tiêu demo:

- Cho thấy hệ thống không chỉ chat.
- Có nguồn tham khảo/RAG.
- Có kiểm tra tương tác thuốc.
- Có hồ sơ cá nhân.
- Có hội chẩn và thư ký y khoa.

### 13.2. Demo 1 - Chat có RAG - 2 phút

Thao tác:

1. Mở trang Chat.
2. Nhập câu hỏi mẫu:

```text
Tôi đang dùng warfarin, nếu đau đầu thì có nên dùng ibuprofen không?
```

3. Chờ hệ thống trả lời.
4. Chỉ vào phần câu trả lời, nguồn tham khảo hoặc debug/context nếu UI có hiển thị.

Câu nói:

> Ở đây người dùng hỏi một câu có yếu tố thuốc và rủi ro. CLARA-Care không trả lời theo kiểu khẳng định ngay. Câu hỏi được gửi qua backend, sau đó ML service kiểm tra an toàn, nhận diện đây là câu hỏi liên quan đến thuốc, rồi RAG ưu tiên tìm các nguồn liên quan đến tương tác thuốc.

Điểm cần nhấn:

> Kết quả nên cảnh báo người dùng không tự phối hợp thuốc nếu chưa hỏi bác sĩ hoặc dược sĩ, vì warfarin và ibuprofen có thể làm tăng nguy cơ chảy máu.

Nếu hệ thống trả lời chậm:

> Vì phần này có truy xuất nguồn và kiểm tra an toàn, thời gian phản hồi có thể lâu hơn chatbot thường. Nếu demo offline, ta có thể dùng câu trả lời đã lưu để minh họa flow.

### 13.3. Demo 2 - CareGuard kiểm tra tương tác thuốc - 2 phút

Thao tác:

1. Mở trang tủ thuốc hoặc CareGuard.
2. Đảm bảo có sẵn các thuốc:

```text
Warfarin
Ibuprofen
Omeprazole
Clopidogrel
Paracetamol
```

3. Bấm kiểm tra tương tác.
4. Chỉ vào mức rủi ro, cảnh báo và khuyến nghị.

Câu nói:

> Đây là module CareGuard. Thay vì người dùng phải nhớ từng tương tác thuốc, hệ thống lấy danh sách thuốc trong tủ và gửi sang pipeline kiểm tra tương tác. Pipeline này chuẩn hóa tên thuốc, so với luật tương tác nội bộ, sau đó có thể bổ sung bằng chứng từ nguồn thuốc như RxNorm hoặc openFDA.

Điểm cần nhấn:

> Kết quả không thay thế bác sĩ, nhưng giúp phát hiện sớm các phối hợp có nguy cơ. Ví dụ warfarin với ibuprofen có thể tăng nguy cơ chảy máu, nên hệ thống đánh mức rủi ro cao và khuyến nghị hỏi chuyên môn.

Nếu nút kiểm tra bị disabled:

> Nút chỉ bật khi người dùng đã đồng ý điều khoản an toàn và có đủ thuốc trong tủ. Đây là một lớp kiểm soát để tránh người dùng hiểu nhầm đây là chỉ định điều trị.

### 13.4. Demo 3 - PHR cá nhân hóa theo hồ sơ - 1.5 phút

Thao tác:

1. Mở trang PHR/hồ sơ sức khỏe.
2. Cho xem các trường như dị ứng, bệnh nền, thuốc đang dùng.
3. Lưu hoặc chỉ vào hồ sơ mẫu.

Ví dụ dữ liệu mẫu:

```text
Dị ứng: NSAID
Bệnh nền: tăng huyết áp
Thuốc đang dùng: warfarin
```

Câu nói:

> PHR là hồ sơ sức khỏe cá nhân. Dữ liệu này giúp hệ thống hiểu bối cảnh người dùng. Cùng một câu hỏi về thuốc giảm đau, người không có bệnh nền và người đang dùng warfarin hoặc dị ứng NSAID cần nhận cảnh báo khác nhau.

Điểm cần nhấn:

> PHR không phải để AI tự điều trị cho người dùng. Nó giúp hệ thống đưa cảnh báo có ngữ cảnh hơn và tránh trả lời chung chung.

### 13.5. Demo 4 - Source Hub đồng bộ nguồn - 2 phút

Thao tác:

1. Mở Source Hub.
2. Chọn nguồn, ví dụ PubMed hoặc RxNorm.
3. Nhập query mẫu:

```text
warfarin ibuprofen interaction bleeding
```

4. Bấm đồng bộ nguồn.
5. Chỉ vào danh sách record: tiêu đề, nguồn, URL, ngày sync.

Câu nói:

> Source Hub là nơi CLARA-Care lấy thêm dữ liệu từ các nguồn bên ngoài. Với PubMed, hệ thống gọi API bài báo y sinh. Với RxNorm, hệ thống lấy dữ liệu chuẩn hóa thuốc. Với openFDA hoặc DailyMed, hệ thống lấy thông tin nhãn thuốc. Một số nguồn Việt Nam có thể được lấy qua HTML nếu không có API chuẩn.

Điểm cần nhấn:

> Sau khi lấy về, dữ liệu không được đưa thẳng cho AI. Hệ thống chuẩn hóa thành record, lưu lại, sau đó khi RAG chạy thì lọc theo query, chấm điểm và chọn phần liên quan nhất.

Nếu mạng chậm hoặc nguồn lỗi:

> Vì đây là nguồn ngoài, có thể phụ thuộc mạng hoặc giới hạn API. Hệ thống có cơ chế trả cảnh báo hoặc timeout thay vì treo toàn bộ ứng dụng.

### 13.6. Demo 5 - Council hội chẩn AI - 1.5 phút

Thao tác:

1. Mở trang Council.
2. Tạo hoặc mở ca mẫu.
3. Nhập tình huống ngắn:

```text
Bệnh nhân nam 62 tuổi, đang dùng warfarin, đau đầu và muốn dùng ibuprofen. Có tiền sử tăng huyết áp.
```

4. Chạy hội chẩn.
5. Chỉ vào các phần: nhận định, cảnh báo, đồng thuận hoặc khuyến nghị.

Câu nói:

> Council mô phỏng cách một ca được nhìn từ nhiều góc độ. Thay vì chỉ có một câu trả lời, hệ thống chia vấn đề thành các vai trò như nội tổng quát, dược lâm sàng, cấp cứu và tổng hợp. Nhờ vậy các rủi ro như tương tác thuốc hoặc dấu hiệu cần chuyển tuyến ít bị bỏ sót hơn.

Điểm cần nhấn:

> Council phù hợp với các ca phức tạp hơn chat thông thường, khi cần nhìn vấn đề theo nhiều hướng.

### 13.7. Demo 6 - Scribe ghi âm, chuyển text và SOAP - 2 phút

Thao tác:

1. Mở Scribe.
2. Nếu microphone ổn, bấm ghi âm và đọc câu mẫu:

```text
Bệnh nhân nam 62 tuổi, đau đầu hai ngày, đang dùng warfarin, lo lắng về việc dùng thuốc giảm đau.
```

3. Dừng ghi âm và chờ transcript.
4. Bấm tạo hoặc cập nhật SOAP note.
5. Chỉ vào các phần S, O, A, P.

Câu nói:

> Scribe dùng microphone của trình duyệt để ghi âm. Frontend chia audio thành các đoạn ngắn rồi gửi lên backend. Backend chuyển tiếp sang ML service. Phần speech-to-text trong repo có adapter local dùng Whisper qua faster-whisper để biến âm thanh thành văn bản. Sau đó transcript được xử lý thành SOAP note.

Giải thích SOAP:

- S là lời kể của bệnh nhân.
- O là dữ liệu khách quan.
- A là nhận định.
- P là kế hoạch tiếp theo.

Điểm cần nhấn:

> Scribe không thay bác sĩ ghi bệnh án hoàn toàn. Nó giúp tạo bản nháp có cấu trúc để người chuyên môn kiểm tra và chỉnh lại nhanh hơn.

Nếu microphone không chạy:

> Trong demo thực tế, microphone có thể bị chặn quyền trên trình duyệt. Khi đó mình dùng transcript mẫu đã chuẩn bị sẵn để vẫn demo được phần tạo SOAP.

### 13.8. Kết nối các phần vừa demo - 1 phút

Câu nói:

> Qua 6 phần demo, có thể thấy CLARA-Care là một hệ thống nhiều pipeline. Chat dùng RAG để trả lời có bằng chứng. CareGuard tập trung vào an toàn thuốc. PHR tạo bối cảnh cá nhân. Source Hub bổ sung nguồn nghiên cứu. Council hỗ trợ phân tích đa góc nhìn. Scribe biến ghi âm thành ghi chú có cấu trúc.

Sơ đồ nói nhanh:

```text
Hồ sơ + thuốc + câu hỏi + nguồn nghiên cứu + transcript
-> các pipeline AI chuyên biệt
-> câu trả lời, cảnh báo, hội chẩn, SOAP note
```

Kết luận demo:

> Điểm quan trọng là hệ thống không gom mọi thứ vào một chatbot duy nhất. Mỗi chức năng có pipeline riêng, có kiểm soát an toàn và có dữ liệu đầu vào rõ ràng.

### 13.9. Câu hỏi thường gặp khi demo

**Câu hỏi: AI này có thay bác sĩ không?**

Trả lời:

> Không. CLARA-Care là hệ thống hỗ trợ. Các cảnh báo và ghi chú giúp người dùng hoặc nhân viên y tế tham khảo, nhưng quyết định điều trị vẫn cần chuyên môn y tế.

**Câu hỏi: Nguồn dữ liệu lấy từ đâu?**

Trả lời:

> Hệ thống có tài liệu nội bộ, Source Hub và connector tới nguồn ngoài như PubMed, Europe PMC, RxNorm, openFDA, DailyMed, ClinicalTrials và một số nguồn Việt Nam.

**Câu hỏi: Ghi âm thành text dùng công nghệ gì?**

Trả lời:

> Frontend dùng MediaRecorder để thu âm. Backend gửi audio sang ML service. Trong repo có service ASR local dùng Whisper qua faster-whisper để chuyển giọng nói thành văn bản.

**Câu hỏi: Nếu nguồn ngoài lỗi thì sao?**

Trả lời:

> Hệ thống có timeout và cảnh báo lỗi nguồn. RAG vẫn có thể dùng nguồn nội bộ hoặc dữ liệu đã sync trước đó nếu có.

**Câu hỏi: Vì sao cần PHR?**

Trả lời:

> Vì cùng một câu hỏi y tế nhưng mỗi người có bối cảnh khác nhau. Dị ứng, bệnh nền và thuốc đang dùng có thể làm thay đổi mức cảnh báo.

