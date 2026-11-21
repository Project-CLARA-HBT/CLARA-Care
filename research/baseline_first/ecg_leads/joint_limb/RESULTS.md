# Mã hóa chung bốn phần dư chuyển đạo chi giảm kích thước trên PTB-XL

Trên 32 người, joint-parity rANS dùng **826.597 byte**, giảm **5,20%** trước FLAC cùng đóng gói (871.907) và 5,03% trước FLAC chi cố định cũ (870.339). Cả bảy decoder đọc lại mỗi record từ byte và tái tạo đúng 1.920.000 giá trị ADC.

| Codec phần dư | Tổng byte | Số record candidate thắng / 32 |
|---|---:|---:|
| Bốn FLAC riêng | 871.907 | 32 |
| Bốn rANS riêng | 833.408 | 32 |
| Bốn rANS có parity | 834.088 | 32 |
| Một rANS chung | 830.959 | 32 |
| Một rANS chung có parity | 826.597 | — |
| Một LZMA chung | 832.621 | 31 |
| Một LZMA chung có parity | 828.361 | 25 |

Riêng việc cấp hai bit parity cho rANS chung chỉ tiết kiệm 0,52%; trước LZMA cùng thông tin, lợi ích còn 0,21% và thua 7/32 record. Đây là mức giảm nhỏ dù so với FLAC nhìn thấy lợi ích lớn hơn. Chi phí tính toán và baseline codec ECG chuyên dụng còn chưa đánh giá. Biên 10% chưa đạt.

~~~bash
uv pip install constriction==0.4.2 numpy soundfile
python study.py /tmp/clara-ecg-leads-pr1/cache | diff - results.json
~~~
