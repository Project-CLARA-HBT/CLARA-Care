# GLHS R4 và token ký trên cùng 500 quyết định

**Rút tuyên bố GLHS có độ đúng cao hơn token ký trong E16. Đồng thời rút con số “khôi phục chính xác 100 so với 50” khỏi các kết quả thực nghiệm của bài.** Kiểm toán đọc lại 2.500 dòng đã niêm phong, ghép đủ năm phương pháp trên từng mã lịch, chấm theo nhãn hợp lệ của fixture và đối chiếu mã nguồn đúng revision ghi trong bundle. Tất cả mười tệp trong danh mục niêm phong khớp SHA-256. [Kết quả kiểm tra](results.json) · [Quy tắc quyết định R4, mục 6](../q4_r4/novelty_contract_r4.md)

| Nhóm lịch | Mã lịch | C3 và C4 cùng đúng | C4 có thời gian thấp hơn / bằng / cao hơn C3 |
|---|---:|---:|---:|
| Đề xuất hợp lệ | 100 | 100 | 0 / 0 / 100 |
| Phiên bản cũ | 100 | 100 | 0 / 0 / 100 |
| Thay nội dung đã cung cấp | 100 | 100 | 0 / 0 / 100 |
| Bằng chứng ngoài tập đã cung cấp | 100 | 100 | 0 / 0 / 100 |
| Chữ ký hỏng | 100 | 100 | 84 / 0 / 16 |

C3 là token ký có digest và các điều kiện về phiên bản. C4 là bộ kiểm tra GLHS đầy đủ. Trên 400 đề xuất có nhãn sai, mỗi phương pháp chấp nhận nhầm 0. Trên 100 đề xuất có nhãn đúng, mỗi phương pháp từ chối nhầm 0. Vì C3 đúng ở từng lịch, mọi cách gán trọng số không âm cho năm nhóm đều cho C3 độ đúng tối đa. Thêm lần lặp của những quyết định này không thể tạo chênh lệch dương về độ đúng. Số mã lịch là 500, nhưng chúng đến từ năm nhánh sinh fixture. C3 và C4 cùng dùng phép kiểm chữ ký C3 khi token được gắn vào fixture. [Bộ kiểm tra năm phương pháp](../../../evaluation/glhs_r4_eval/run_e16.py) · [Định nghĩa các bộ kiểm tra](../../../services/api/src/clara_api/glhs/comparator_policies.py)

**Hai điểm làm thay đổi cách đọc kết quả đã niêm phong.** Protocol yêu cầu PostgreSQL 16. Hồ sơ backend và lệnh khởi tạo trong harness đều xác định SQLite trong bộ nhớ. “Admitted” trong mỗi dòng là kết quả gọi bộ kiểm tra đầu vào. Harness không đo kết quả ghi bền bằng một giao dịch độc lập. Nhãn trường thời gian là `cpu_latency_us`, nhưng mã dùng đồng hồ wall-clock, gọi C4 một lần trước khi đo rồi chạy C0–C4 theo thứ tự cố định. Phân bố 84/416 ở bảng mô tả lần chạy đó. Một tuyên bố về chi phí PostgreSQL hoặc về CPU riêng từng phương pháp cần phép đo khác. [Backend](../q4_r4/evidence/E16_five_way_comparator/backend_attestation.json) · [Protocol E16](../q4_r4/evidence/E16_five_way_comparator/protocol.json)

Mục 3.2 của kế hoạch thống kê gán mức 75 cho trường hợp C3 xác minh digest rồi truy hồi nội dung ngoại tuyến. Hàm tính điểm được gọi chỉ với tên arm trước vòng lặp và trả hằng số 50 cho C3, 100 cho C4. Các dòng kết quả thiếu cả byte cần khôi phục lẫn câu trả lời của phép khôi phục. Các con số trên mô tả cách phân loại kiến trúc của nhóm tác giả. Chúng không nhận dạng được tỷ lệ khôi phục bit-exact, kể cả khi mọi checksum đều đúng. [Thang điểm đã khóa](../q4_r4/statistical_plan_r4.md) · [Tệp kết quả gốc](../q4_r4/evidence/E16_five_way_comparator/raw/runs.jsonl)

## Phạm vi nghiên cứu còn lại

PostgreSQL SSI xử lý tính tuần tự hóa trong cơ sở dữ liệu; việc kiểm các thuộc tính của một lần cung cấp dữ liệu ngoài giao dịch đòi hỏi ứng dụng ghi lại thuộc tính đó. Macaroons cho phép bên xác minh thực thi điều kiện gắn với capability. C3 trong kho là một hiện thực token tùy chỉnh lấy ý tưởng từ capability, còn C1 là bộ kiểm phiên bản của ứng dụng. E16 không chạy hiện thực Macaroons của tác giả hay PostgreSQL SSI. So sánh công bằng phải cho các phương pháp cùng quan sát, quyền lưu và truy vấn. [Ports và Grittner, PVLDB 2012](https://www.vldb.org/pvldb/vol5/p1850_danrkports_vldb2012.pdf) · [Birgisson và cộng sự, NDSS 2014](https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/)

Khả năng trả lời câu hỏi về nguồn gốc sau khi một số nhật ký hết hạn vẫn là một câu hỏi mở. Một đối chứng phù hợp là token ký kèm kho nội dung và nhật ký append-only, có cùng dữ liệu đầu vào và ngân sách lưu. Nếu cả hai lưu cùng byte theo cùng khóa, câu hỏi chỉ yêu cầu lấy lại byte đã lưu sẽ cho hai phương pháp cùng đáp án. Muốn đo đóng góp riêng của quản lý vòng đời, cần truy vấn quan hệ nguồn–đích có đáp án được sinh độc lập, quan sát byte truy xuất, chi phí lưu tổng và các trường hợp thiếu. Câu hỏi sau hết hạn cũng xuất hiện trong đề xuất ReceiptMin, nên portfolio chỉ được tính kết quả đó một lần. E16 chưa cung cấp lý do để tính GLHS là một bài thắng tất cả baseline. [Danh mục và phạm vi ReceiptMin](../../MANUSCRIPT_CANDIDATE_PORTFOLIO.md)

## Tái lập

Từ thư mục gốc của repo, dùng Node.js và Git. Lệnh lấy runner đúng revision bằng `git show`. Kết quả là kiểm toán hồi cứu của workload tổng hợp đã có. Toàn bộ việc kiểm dùng tệp công khai trong repo và không cần dữ liệu bệnh nhân hoặc dịch vụ đang chạy.

```sh
node --check research/glhs_journal/comparator_recheck/audit.mjs
node research/glhs_journal/comparator_recheck/audit.mjs | diff - research/glhs_journal/comparator_recheck/results.json
```
