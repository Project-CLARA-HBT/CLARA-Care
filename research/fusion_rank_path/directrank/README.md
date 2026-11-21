# Đối chứng quét top-k của DirectRank

Bản chuyển dùng thuật toán 2 của Tan, Xia, Guo và Wang để tìm điểm đổi thứ tự trong danh sách top-k chung cho cả truy vấn. Mỗi bước xét giao điểm kề nhau trong top-k và giao điểm của từng tài liệu bên ngoài với tài liệu đứng thứ k. Nhờ đó nhiều tài liệu có nhãn dương dùng chung một lần duyệt. Đầu ra giữ từng lần đổi thứ hạng, kể cả khi hai tài liệu đổi chỗ có cùng nhãn liên quan. Phạm vi là thủ tục tìm điểm đổi thứ tự trong mục 2.2. Phần học tọa độ, mô hình xác suất và cây hồi quy của bài báo nằm ngoài phép so sánh đã đăng ký. [Tan et al., KDD 2013, thuật toán 2 và bảng 1–2](https://chbrown.github.io/kdd-2013-usb/kdd/p856.pdf)

Thuật toán gốc bắt đầu ở âm vô cực. Bản này khởi đầu bằng top-k chính xác ở trọng số 0 và xét đến 65.535. Khi một cặp đổi thứ tự, phép chia số nguyên 64 bit trả về trọng số biểu diễn được đầu tiên mà tài liệu thách thức vượt tài liệu hiện tại, dùng vị trí theo ID để phân xử hòa. Một tài liệu có thể nhảy nhiều hạng tại một bước nguyên. Khi chỉ một tài liệu bên ngoài vượt ranh giới và thứ tự nội bộ vẫn giữ nguyên, chèn tài liệu đó vào đúng vị trí. Khi nhiều lần vượt ranh giới xảy ra cùng bước, chọn lại top-k ở bước đó. Thao tác chọn lại cũng cần khi một thay đổi nội bộ làm giảm điểm của tài liệu cuối top-k và để một tài liệu khác lọt vào. Đường của tài liệu chưa vào top-k luôn bắt đầu với hạng k+1.

Hàm C++17 trong `path.hpp` nhận hai cột điểm unsigned 16-bit theo thứ tự tăng của ID, chỉ số tài liệu dương và k. Trọng số và hạng trả về đều là số nguyên. Overload nhận accessor đọc trực tiếp các trường của từng hàng để phép đo bao gồm xây dựng và cập nhật danh sách, đồng thời tránh sao chép đầu vào. Tất cả biến trạng thái được tạo mới cho mỗi truy vấn.

```cpp
auto curves = directrank::rank_paths(int(q.rows.size()),
    [&](int i) { return q.rows[i].a; }, [&](int i) { return q.rows[i].b; },
    int(q.positives.size()), [&](int i) { return q.positives[i].id; }, 10);
```

## Kiểm tra độ đúng

Bảng 1 và 2 của tác giả cho thứ tự top 3 của hai truy vấn qua lần lượt sáu và tám khoảng. Bài báo minh họa các đường điểm bằng hình và không liệt kê hệ số. Hai bộ hệ số nguyên trong `verify.mjs` được dựng để tái hiện đúng hai chuỗi thứ tự công bố. Vị trí trọng số cụ thể chỉ thuộc các bộ hệ số được dựng. Trình kiểm tra so toàn bộ đường hạng của mỗi tài liệu với sắp xếp độc lập tại từng trọng số trên hai ví dụ, các ca hòa/giao đồng thời và 20 fixture sinh với seed cố định. Bộ chạy chấp nhận cùng định dạng dữ liệu đã ghim như thí nghiệm chính.

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic research/fusion_rank_path/directrank/replay.cpp -o /tmp/directrank-replay
node --check research/fusion_rank_path/directrank/verify.mjs
node research/fusion_rank_path/directrank/verify.mjs /tmp/directrank-replay
/tmp/directrank-replay < data.txt | cmp - research/fusion_rank_path/results/changes.tsv
```
