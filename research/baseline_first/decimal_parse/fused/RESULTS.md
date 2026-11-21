# Gộp tách trường và chuyển số trên dữ liệu điện UCI

Trên 14 ngày development, đường xử lý đọc số ngay khi tìm dấu phân cách **giảm 54,33% thời gian so với bản scalar chuyên biệt trước**, thắng 14/14 ngày. Việc dùng độ rộng của cột ở hàng trước chỉ giảm thêm **0,36%** so với bản gộp không dùng lịch sử. Loại đóng góp dự báo độ rộng theo biên 20%. [Protocol](PROTOCOL.md) · [840 phép đo](timings.csv)

| Đối chứng | Mức giảm thời gian của bản gộp không dùng lịch sử |
|---|---:|
| fast_float v8.3.3, tách trường riêng | 73,08% |
| libstdc++ from_chars, tách trường riêng | 74,57% |
| Scalar chuyên biệt, tách trường riêng | 54,33% |
| Ghép cặp SSE2, tách trường riêng | 53,95% |

Đại lượng là trung vị theo ngày của tỷ số giữa median thời gian mỗi arm, 10 lượt/ngày trên một luồng WSL. Quy tắc gộp dùng dấu chấm, chiều dài, mọi chữ số và dấu kết thúc để nhận diện dạng số, sau đó chia mantissa nguyên cho 1.000. Nó bỏ lần duyệt độc lập dùng để xây bảy string_view. Kết quả xác lập lợi ích của cả thay đổi implementation này trên một nguồn. Để quy tác động riêng cho fusion, còn cần đối chứng dùng cùng kernel độ rộng cố định nhưng nhận token đã tách sẵn; hai scalar cũ/mới cũng khác cách chuyên biệt hóa vòng lặp. Dạng phổ biến chiếm 133.798/133.812 trường. Giữ Open Food Facts cho một thiết kế có prior và comparator đầy đủ hơn. [Phân bố dữ liệu và oracle](../RESULTS.md)

Hai arm mới trùng từng byte với fast_float mới và kết quả fast_float đã đối chiếu oracle hữu tỉ trước đó cho cả 14 ngày. Thêm 21 trường kiểm tra nhánh dự phòng gồm missing, giá trị âm, số mũ, chuỗi lỗi, số quá rộng và dấu zero âm. Các ca bổ sung dùng fast_float làm chuẩn tương thích. Các phép đo không bao gồm file I/O. Nhánh gộp chỉ nhận nhanh miền được mô tả trong protocol.

Tái lập trên x86-64 với cùng fast_float, dữ liệu và toolchain như study gốc. Lệnh đầu lấy nguyên bốn parser đối chứng từ mã nguồn gốc. Đặt DATA trỏ tới scratch mới có thư mục days/ do prepare.py tạo và FF trỏ tới checkout fast_float.

~~~bash
sed '/^int main(/,$d' ../parse.cpp > "$DATA/reference.hpp"
g++ -std=c++20 -O3 -msse2 -static -I"$DATA" -I"$FF/include" bench.cpp -o "$DATA/parse"
bash ../benchmark.sh "$DATA" 2
~~~
