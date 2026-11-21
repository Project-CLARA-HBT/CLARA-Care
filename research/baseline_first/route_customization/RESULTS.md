# Tám lần cập nhật liên tiếp của đồ thị đường ô tô Monaco

Trong tám ngày có **38 thao tác sửa, thêm hoặc xóa đối tượng OSM**, nhưng không có lần nào làm đổi một giá trị thời gian trên 2.173 cung của profile ô tô RoutingKit. Cả chín lần dựng đều có 1.270 nút và 49 cặp cung cấm rẽ. Danh sách kề, tọa độ, tập lượt rẽ cấm và trọng số có nội dung trùng từng byte. Theo quy tắc dừng đã đăng ký, workload này không có batch cần cập nhật metric. Dừng phép thử tốc độ cho nguồn development này. [Protocol](PROTOCOL.md) · [Số đếm, chuỗi replication và SHA-256](summary.json)

Các batch 4967–4974 có lần lượt 5, 11, 3, 0, 0, 3, 2 và 14 thay đổi. Lần 4969 được khôi phục bằng cách áp diff chính thức lên snapshot 4968 do lỗi tải PBF ngày 15/11. Diff 4970 rỗng và đồ thị khôi phục khớp cả bảy vector với snapshot chính thức kế tiếp. Tám snapshot còn lại là PBF có ngày phát hành. Năm snapshot cuối đã được đối chiếu MD5 do Geofabrik công bố. Dữ liệu được ghi công cho OpenStreetMap contributors, trích xuất Geofabrik, ODbL. [Nguồn Monaco](https://download.geofabrik.de/europe/monaco.html) · [Nhật ký thay đổi](https://download.geofabrik.de/europe/monaco/updates/)

Kết quả này giới hạn ở profile và tám ngày đã đo. Tắc đường, thời gian lái thực và các tuần khác chưa được đánh giá. Việc đo thời gian giữa hai cách cập nhật trên 0 thay đổi trọng số sẽ không trả lời câu hỏi đã đăng ký.

Tái lập với RoutingKit ở revision trong protocol, GNU C++17 trên Linux x86-64 và Python có osmium. Đặt RK trỏ tới checkout của thư viện. Nếu các snapshot có ngày đã hết thời gian lưu trên mirror, cần bản lưu có digest tương ứng.

~~~bash
make -C "$RK" lib/libroutingkit.a
g++ -std=c++17 -O2 -I"$RK/include" extract.cpp "$RK/lib/libroutingkit.a" -lz -fopenmp -pthread -o /tmp/monaco-extract
python screen.py /tmp/monaco-cache /tmp/monaco-extract > replay.json
~~~
