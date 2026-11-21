# Dự báo sai phân theo biên độ làm tăng kích thước

Trên 32 người PTB-XL, kích thước lần lượt là 871.875 byte với FLAC sau biến đổi chi, 872.129 với sai phân ngực, 901.435 với hệ số tuyến tính và 901.767 với hệ số chia theo biên độ. Cả bốn decoder tái tạo chính xác 1.920.000 giá trị ADC. Việc ước lượng hệ số chỉ từ block trước cho phép bỏ toàn bộ chi phí truyền hệ số. Lợi ích đó vẫn chưa đủ trên phép thử đã khóa.

So với FLAC đã đóng khung, phương pháp chia biên độ thắng 3 người, thua 29; so với hồi quy một hệ số, thắng 13, hòa 2, thua 17. Phương pháp dùng ít byte hơn Sprintz có biến đổi chi (1.020.652), nhưng dùng nhiều hơn FLAC có biến đổi chi trong cách đóng gói cũ (870.339). Dừng biến thể này trước INCART. Không có claim về thời gian giải mã.

Tái lập trong thư mục này bằng lệnh dưới với cache PTB-XL của nghiên cứu trước. Xem digest đầu vào trong ../summary.json, tiêu chí ở PROTOCOL.md và số byte từng record trong results.json.

~~~bash
python measure.py /tmp/clara-ecg-leads-pr1/cache | diff - results.json
~~~
