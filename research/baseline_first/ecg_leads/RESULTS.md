# Giới hạn của việc chọn bộ dự báo theo bản ghi ECG

Trên 32 người trong tập development PTB-XL, ngay cả khi biết trước lựa chọn tốt nhất cho từng chuyển đạo, số byte chỉ giảm **1,15%** so với công thức chuyển đạo chi cố định. Mức lớn nhất trên một người là 7,08%. Cả 32 đều dưới biên 10% đã khóa. Dừng cơ chế chọn giữa các predictor đã đăng ký ở mức toàn bản ghi. INCART còn giữ riêng. [Protocol](PROTOCOL.md) · [PTB-XL 1.0.3, PhysioNet](https://physionet.org/content/ptb-xl/1.0.3/)

| Cách mã hóa | Tổng byte |
|---|---:|
| FLAC, cặp kênh gốc | 1.098.551 |
| FLAC, nhóm sáu kênh gốc | 1.102.717 |
| FLAC, từng chuyển đạo gốc | 1.137.580 |
| Dự báo cố định bốn chuyển đạo chi | 870.339 |
| Thêm sai phân giữa chuyển đạo ngực kề nhau | 890.440 |
| Tối ưu riêng từng kênh và bản ghi, miễn phí truyền lựa chọn | 860.322 |

Phép đo dùng độ dài **toàn bộ buffer FLAC đã đóng**. Vị trí con trỏ sau khi thư viện ghi lại header không biểu diễn độ dài stream. Tất cả phép thử đều kiểm tra decode chính xác mẫu ADC nguyên và checksum của từng kênh trên dữ liệu nguồn. Tổng cộng 32 bản ghi × 5.000 thời điểm × 12 kênh. Hai phép chạy trên WSL và Linux cho cùng số byte ở từng phương án trên từng kênh. Dữ liệu development này không định lượng tốc độ và chưa thử predictor ở mức block ngắn hay codec ECG chuyên dụng. [Số liệu từng record](summary.json) · [Selective linear prediction, Rzepka và cộng sự](https://doi.org/10.1016/j.bspc.2019.101705)

Tái lập bằng Python 3.12, soundfile 0.13.1, libsndfile 1.2.2 và NumPy. Chạy từ thư mục này với cache cục bộ riêng. Đối chiếu các khóa baseline_bytes, free_choice_bytes và records với kết quả đã lưu. Nguồn được phát hành theo CC BY 4.0.

~~~bash
python screen.py /tmp/ptbxl-1.0.3-screen > replay.json
~~~
