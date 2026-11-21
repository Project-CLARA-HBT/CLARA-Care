# Đối chứng làm trơn hai phía trên ETTh

**Loại tuyên bố ưu thế của phương pháp chọn bộ làm trơn.** Trên 174 khoảng trống từ hai trạm, phương pháp được chọn trên validation có MAE 1,21187 và kernel chỉ dùng nhiệt độ có MAE 1,21066. Phương pháp chọn thắng 84 khoảng trống và thua 90. Mức giảm MAE tương đối đạt −0,10%, dưới ngưỡng 5% đã khóa. Khoảng bootstrap 95% cho MAE kernel trừ MAE phương pháp chọn là [−0,05162; 0,04299]. Khoảng này cho phép chênh lệch theo cả hai hướng. [Protocol](PROTOCOL.md) · [Đủ 19 phương pháp, số lần thắng thua và khoảng tin cậy](results/comparison.csv)

| Phương pháp | MAE trung bình qua trạm, độ dài và tuần |
| --- | ---: |
| Kernel chỉ dùng nhiệt độ | 1,21066 |
| Tự hồi quy Yule–Walker | 1,21187 |
| Xu hướng tuyến tính và thành phần điều hòa trong không gian trạng thái | 1,23548 |
| Chọn giữa hai bộ làm trơn bằng validation | 1,21187 |

Cả hai bộ làm trơn chỉ thấy 24 giờ nhiệt độ ở mỗi phía cùng giờ địa phương theo chỉ số của chuỗi. Mỗi trạm và mỗi độ dài có 123 cửa sổ validation theo thời gian. Tất cả 42 cấu hình mỗi ô (27 cấu hình không gian trạng thái và 15 tự hồi quy) chạy thành công. Kernel trong nghiên cứu trước dùng chín cấu hình. Validation chọn tự hồi quy ở cả sáu ô. Riêng khoảng 72 giờ của ETTh1 dùng bậc 1, năm ô còn lại dùng bậc 48. Tất cả sáu chọn hệ số regularization bằng 0. Tập chấm dùng mặt nạ đã từng được kiểm tra, gồm 29 tuần đồng bộ. Bootstrap lấy khối bốn tuần và giữ các trạm, độ dài cùng nhau trong từng lần lấy mẫu. Kết quả chỉ mô tả development trên hai trạm với khoảng mất dữ liệu được tạo bằng che nhiệt độ thực. [Tất cả lựa chọn và điểm validation](results/validation.json) · [Lỗi từng khoảng trống](results/losses.csv)

## Quan hệ với công trình trước

Rauch, Tung và Striebel đưa ra đệ quy làm trơn cho hệ tuyến tính. Harvey và Peters nghiên cứu ước lượng mô hình chuỗi thời gian cấu trúc. Gómez, Maravall và Peña so sánh hai cách xử lý quan sát thiếu trong ARIMA, bao gồm bỏ qua cập nhật khi quan sát thiếu. Vì vậy việc điều kiện hóa lên hai đầu khoảng trống và việc mô hình hóa xu hướng, mùa vụ đều có tiền lệ trực tiếp. Thử nghiệm này kiểm tra liệu các đối chứng thống kê cổ điển có giải thích được mức sai số quan sát trên hai trạm. Hòa với tự hồi quy và khoảng chênh lệch rộng so với kernel khiến hướng này thiếu cơ sở cho một bài độc lập về thuật toán mới. [Rauch và cộng sự](https://doi.org/10.2514/3.3166) · [Harvey và Peters](https://doi.org/10.1002/for.3980090203) · [Gómez và cộng sự](https://doi.org/10.1016/S0304-4076(98)00036-0)

## Tái lập

Chạy từ thư mục gốc của repo. CACHE chứa hai CSV ghim SHA-256 hoặc là thư mục rỗng đã tồn tại. Hàm nạp dữ liệu kiểm tra digest từng trạm. OUT là đường dẫn mới. Phiên WSL2 dùng CPU với Python 3.12.15, NumPy 2.5.4 và SciPy 1.18.1. Hai lượt chạy tạo CSV và JSON trùng từng byte. Bản kiểm tra độc lập dùng lan truyền trạng thái để dựng hiệp phương sai và Kalman filter/RTS để tái dựng cả khoảng trống. Sai số tuyệt đối lớn nhất giữa hai cách tính là 2,9 × 10⁻¹⁰ trên 81 cấu hình và độ dài.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m evaluation.sensor_gap.smoother.verify
python -m evaluation.sensor_gap.smoother.run "$CACHE" "$OUT"
python -m evaluation.sensor_gap.smoother.compare "$OUT" \
  evaluation/sensor_gap/{periodic,conditional,kernel}_results/losses.csv > "$OUT/comparison.csv"
node evaluation/sensor_gap/smoother/verify-reports.mjs "$OUT/losses.csv" \
  evaluation/sensor_gap/kernel_results/losses.csv "$OUT/comparison.csv"
```
