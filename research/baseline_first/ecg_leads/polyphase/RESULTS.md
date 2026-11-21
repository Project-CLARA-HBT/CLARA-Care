# Tách pha không bù đủ phí hai luồng FLAC

Trên cùng 32 người, phiên bản có hệ số fit dùng 871.468 byte. Phiên bản luôn có thể quay về FLAC gốc, trả một byte chọn mode và bốn byte chiều dài mỗi kênh. Ba dự báo cố định đều dùng 872.259 byte sau chọn mode. Bộ fit thắng cả 32 record trước ba đối chứng cùng đóng gói nhưng tổng phần giảm chỉ 791 byte (0,09%). FLAC chi cố định ở cách đóng gói ban đầu dùng 870.339 byte. Biên phát triển đã khóa là 10%.

| Dự báo | Byte khi bắt buộc tách | Byte khi được quay về FLAC |
|---|---:|---:|
| Trung bình hai láng giềng | 1.000.984 | 872.259 |
| Bộ lọc bốn điểm cố định | 995.807 | 872.259 |
| Lagrange trên bốn tọa độ thực | 979.422 | 872.259 |
| Hệ số fit và truyền 8 byte | 969.981 | 871.468 |

Trong 384 luồng kênh của bộ fit, 352 dùng nguyên luồng FLAC, 32 chọn pha 0. Mỗi bản ghi có 60.000 mẫu nguyên và tất cả được khôi phục đúng từ byte đã đóng gói, kể cả khi ép tách pha. Kết quả cho thấy chi phí của phép tách này lớn hơn lợi ích dự báo trên phần lớn kênh. Mức vượt Sprintz ở cùng tập không đủ để tiếp tục nhánh này. Dữ liệu INCART còn giữ riêng.

~~~bash
OPENBLAS_NUM_THREADS=1 python bench.py /tmp/clara-ecg-leads-pr1/cache | diff - results.json
~~~
