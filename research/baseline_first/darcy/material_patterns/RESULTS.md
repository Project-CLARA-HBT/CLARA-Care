# Bốn bit ở mặt phân cách mang thông tin ngoài số lượng vật liệu

Trên 128 trường development 16→32, chọn stencil theo mẫu có hướng đạt relative L2 trung bình **0,017217** ở các điểm thiếu. Mô hình chỉ đếm số đỉnh vật liệu đạt 0,018021 và boosting cùng đầu vào đạt 0,018195. Lỗi giảm **4,46%** và **5,37%** tương ứng. Cả ba dùng cùng 512 trường fit. Các điểm áp suất đã quan sát được tái tạo đúng. Đây là bước tiến trên development, còn dưới biên 10% trước từng đối chứng đã khóa.

| Đối chứng | Mức giảm lỗi của candidate | Khoảng bootstrap 95% | Số trường thắng / 128 |
|---|---:|---:|---:|
| Ridge chung | 18,72% | 17,58–19,84% | 128 |
| Ridge chia theo số đỉnh | 4,46% | 3,91–5,02% | 120 |
| Boosting cùng đầu vào và mã pattern | 5,37% | 3,14–7,55% | 90 |
| Boosting từ thử nghiệm stencil trước | 22,25% | 18,76–25,55% | 117 |

Đơn vị bootstrap là một trường áp suất. Khoảng theo từng so sánh chỉ mô tả độ biến thiên trong các trường đã dùng để phát triển phương pháp. Chúng chưa hiệu chỉnh cho việc thử nhiều ý tưởng hay thay đổi phân phối giữa các nguồn. Xem toàn bộ 12 so sánh với đối chứng và phép tự đối chiếu trong comparisons.json; các chỉ số toàn lưới, phần trong và biên của bốn arm mới ở fields.csv. Cả 32 và 16 phải lấy từ cùng cặp archive train đã kiểm digest ở ../restriction/AUDIT.md. Chỉ số được phép dùng là 0–639.

~~~bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python study.py /tmp /tmp/darcy-pattern-replay
diff fields.csv /tmp/darcy-pattern-replay/fields.csv
diff comparisons.json /tmp/darcy-pattern-replay/comparisons.json
~~~
