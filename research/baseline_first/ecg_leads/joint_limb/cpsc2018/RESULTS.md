# Mã vector parity chuyển sang CPSC nhưng thua LZMA cùng thông tin

Trên 32 record training của CPSC 2018 (v1.0.3 PhysioNet Challenge 2021), joint-parity rANS dùng **883.729 byte**, giảm **3,99%** trước FLAC năm trăm Hz cùng cách đóng khung. LZMA theo parity cho tổng nhỏ nhất, 882.488 byte. rANS thắng LZMA này ở 21 record, hòa 1 và thua 10; tổng số byte của rANS lớn hơn **0,14%**. Trên PTB-XL thứ tự giữa hai codec ngược lại, với rANS nhỏ hơn 0,21%. Tần suất thắng theo record không quyết định tổng byte.

| Arm | Byte |
|---|---:|
| FLAC sau dự báo chi cố định | 920.415 |
| rANS rời | 889.197 |
| rANS rời có parity | 890.421 |
| rANS vector | 887.036 |
| rANS vector có parity | 883.729 |
| LZMA vector | 891.460 |
| LZMA vector có parity | 882.488 |

Mọi arm khôi phục 1.920.000 giá trị ADC nguyên chính xác trên 10 giây đầu mỗi record. File nguồn có từ 5.000 đến 27.390 mẫu mỗi kênh. Cả 32 record lấy theo hash trước khi đọc waveform đều đủ 5.000 mẫu. Header, checksum ADC toàn file và sample đầu đều khớp. Digest tải về và mọi số byte theo record trong results.json. Việc fit bảng đếm theo record đã nằm trong codec từ trước. Mẫu được chọn theo record; số bệnh nhân riêng biệt và kết quả trên INCART chưa được xác minh.

~~~bash
python study_cpsc.py /tmp/clara-cpsc2018 | diff - results.json
~~~

Cần NumPy, SciPy, requests, python-soundfile và constriction 0.4.2. [Bản phát hành và giấy phép](https://physionet.org/content/challenge-2021/1.0.3/)
