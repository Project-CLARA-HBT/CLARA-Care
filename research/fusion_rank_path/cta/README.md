# Đối chứng LP-CTA hai chiều trên lưới trọng số nguyên

Đối chứng dựng chỉ mục cho mỗi cặp vector điểm của một truy vấn. Mỗi tài liệu có nhãn dương lần lượt làm bản ghi trọng tâm. Hàm trả về trọng số đầu tiên và hạng đã cắt của từng đoạn hạng không đổi, theo thứ tự tài liệu dương được truyền vào. Bài toán gốc của Tang, Mouratidis và Yiu trả các miền mà bản ghi trọng tâm thuộc top k. Bản chuyển ở đây giữ cả những lần đổi hạng bên trong miền đó. [SIGMOD 2017, phần 4–6 và phụ lục E](https://web.comp.polyu.edu.hk/csmlyiu/conf/SIGMOD17_kspr.pdf)

## Đối chiếu với thuật toán công bố

- **CTA, thuật toán 1.** Mỗi đối thủ tạo tối đa một điểm cắt với tài liệu trọng tâm. Vì chỉ có một trọng số độc lập, ta biểu diễn lá của CellTree bằng khoảng số nguyên đóng. Mỗi lô chia các khoảng còn lại tại các giao điểm thuộc lô đó. Các tài liệu cùng giao điểm chỉ tạo một đường biên.
- **P-CTA, thuật toán 2.** Duyệt theo skyline. Tài liệu xếp sau bản ghi trọng tâm trên mọi ô còn mở vẫn là pivot và tiếp tục che các tài liệu mà nó trội hơn. Bỏ khỏi skyline những tài liệu xếp trước bản ghi trọng tâm ở ít nhất một ô còn mở, rồi tìm skyline mới. Quan hệ trội dùng thứ tự từ điển (điểm, ưu tiên ID) tại từng đầu mút. Dãy đã sắp theo tọa độ đầu cho phép tính lại skyline bằng một lượt quét. Tác giả dùng BBS gia tăng và đồ thị trội để tránh duyệt lại. Các tối ưu đó chưa được tái hiện.
- **LP-CTA, thuật toán 3.** Mỗi nút của chỉ mục hình chữ nhật lưu góc dưới, góc trên và số hàng. Ở mỗi ô, phép so điểm của góc với bản ghi trọng tâm tại hai đầu mút chứng nhận được nhóm luôn đứng trước hoặc sau. Khi chưa đủ thông tin, đi xuống các con và cuối cùng đếm riêng từng hàng. Dừng khi cận dưới của hạng vượt k. Đây là phiên bản hai chiều sử dụng tính tuyến tính của *hiệu điểm* và cây xếp khối 16 phần tử. Tác giả dùng một chuỗi cận điểm nhanh, cận nhóm và cận từng hàng trong không gian biến đổi. Cận ghép trực tiếp tại cùng trọng số cho phép bỏ các bước giải LP riêng lẻ.
- Thuật toán gốc có thể trả cả ô ngay khi hạng tối đa không quá k. Đầu ra chi tiết của phép đo này yêu cầu tiếp tục chia cho đến khi cận dưới và cận trên bằng nhau, hoặc mọi hạng trong ô bị cắt thành k+1. Khi cận dưới đã vượt k, việc dừng đếm không ảnh hưởng kết quả. Hai đầu mút của lưới và các hòa điểm đều có hạng xác định.

Đây là bản chuyển theo công trình công bố. So sánh thời gian với bản này không tái lập số đo, tổ chức bộ nhớ hoặc BBS gia tăng của tác giả.

## Giao diện và kiểm tra

`rank_path_cta::evaluate(rows, positives)` trong `lp_cta.hpp` nhận các hàng có trường nguyên `a` và `b` trong [0, 65535], theo thứ tự ID cố định. `positives` chứa chỉ số hàng hoặc bản ghi có trường `id` bằng chỉ số hàng. Hàm trả đúng kiểu vector của `path.cpp`. Gọi một lần cho mỗi truy vấn bên trong phần đo để tính đủ chi phí xây chỉ mục và trích kết quả. Hai tham số tùy chọn là k và trọng số cuối, mặc định 10 và 65535.

Ví dụ nhà hàng tại hình 1 của tác giả cho hạng Kyma bằng 3, 4, 3 và 2 khi trọng số dành cho dịch vụ tăng dần. Với quy tắc hòa theo thứ tự bảng và k bằng 3, các đoạn bắt đầu ở 0, 26214, 39322 và 52429. Kiểm tra độc lập sắp xếp toàn bộ hàng tại từng trọng số. Trên 68 truy vấn nhỏ, 711 đường hạng và 590.280 hạng số nguyên khớp, bao gồm các đường đồng nhất, giao đồng thời và hai đầu mút. Đã đối chiếu thêm toàn bộ 417 đường hạng trên 150 truy vấn NanoBEIR development với kết quả lưu của thí nghiệm chính. Các phép kiểm này chỉ xét độ đúng.

```sh
g++ -std=c++17 -Wall -Wextra -Werror -O3 research/fusion_rank_path/cta/driver.cpp -o /tmp/clara-cta-driver
node --check research/fusion_rank_path/cta/verify.mjs
node research/fusion_rank_path/cta/verify.mjs /tmp/clara-cta-driver
```
