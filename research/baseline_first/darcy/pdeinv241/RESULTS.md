# Hiệu ứng của hình dạng bốn đỉnh lặp lại trên archive 241

Trên 64 trường đánh giá sau khi fit lại bằng 128 trường khác của PDEInvBench train, lỗi relative L2 trung bình của phương pháp là **0,004048**. So với hồi quy chỉ đếm số đỉnh, lỗi giảm **4,06%** (bootstrap cặp theo trường 95% từ 2,88% đến 5,19%, thắng 55/64). Trên archive NeuralOperator trước đó, cùng đối chứng cho mức giảm 4,46%. Các khoảng chỉ mô tả hai cohort development. Biên thắng mạnh trước từng arm vẫn là 10%.

| Cách nội suy | Relative L2 điểm thiếu | Relative L2 phần trong | Relative L2 mép |
|---|---:|---:|---:|
| Ridge chung | 0,005383 | 0,004978 | 0,023412 |
| Số đỉnh vật liệu | 0,004219 | 0,003922 | 0,018022 |
| Hình dạng bốn đỉnh | 0,004048 | 0,003737 | 0,018145 |
| Histogram boosting | 0,004471 | 0,004289 | 0,013696 |
| CNN chỉ áp suất | 0,006828 | 0,006665 | 0,016615 |
| CNN áp suất và vật liệu | 0,006358 | 0,006220 | 0,015729 |

So với boosting cùng đầu vào, mức giảm lỗi toàn vùng là 9,47% (5,17–13,55%). Boosting có lỗi mép thấp hơn. CNN có và không có vật liệu chọn epoch 140 và 139 trên ngân sách 140, nên kết quả chưa xác lập mức tốt nhất có thể đạt bằng CNN. Cả sáu arm khôi phục chính xác các nút đã quan sát.

Tải và xác minh LFS SHA-256 của cả 192 file từ bản phát hành tác giả, hệ số thực có hai giá trị 3 và 12. Tất cả mặt nạ thô trong cohort là khác nhau; không có mặt nạ 16×16 khớp 640 trường NeuralOperator đã dùng, kể cả đảo cực. Phụ lục PDEInvBench xác nhận dữ liệu 241 được lấy mẫu xuống từ dữ liệu FNO 421. Đối chiếu của chúng tôi chưa thiết lập ID trường nào trùng giữa hai archive. [Đối chiếu nguồn gốc](../PRIOR.md) Đây là phép tái lập khi fit lại trên archive khác và chấm các trường train giữ riêng cho development. Chưa kiểm định chuyển trọng số sang nguồn độc lập. Kết luận chỉ áp dụng cho phần giữa của lưới 241 theo tọa độ đã khóa. [Nguồn PDEInvBench](https://huggingface.co/datasets/DabbyOWL/PDE_Inverse_Problem_Benchmarking/tree/98b5332fef39da6b9d110a7f62702499ff913a14/darcy-flow-241/train)

~~~bash
python prepare.py /tmp/clara-pdeinv241 /tmp /tmp/darcy-sources.csv
cmp sources.csv /tmp/darcy-sources.csv
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python score.py /tmp/clara-pdeinv241 /tmp/pdeinv-scores
diff fields.csv /tmp/pdeinv-scores/fields.csv
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ../conv_control/study.py /tmp/clara-pdeinv241 --fit-size 128 --train-size 112 --count 192 --epochs 140 --output /tmp/pdeinv-cnn
diff cnn/fields.csv /tmp/pdeinv-cnn/fields.csv
~~~
