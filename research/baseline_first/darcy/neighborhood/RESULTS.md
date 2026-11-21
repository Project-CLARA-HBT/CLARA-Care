# Mở rộng lân cận lên chín bit chưa vượt stencil bốn đỉnh

Trên NeuralOperator 16→32, chia sẻ trọng số hồi quy giữa các mẫu 3×3 theo khoảng cách Hamming đạt lỗi relative L2 trung bình 0,017821. Trên PDEInvBench 241, lỗi là 0,004792. Hồi quy riêng theo bốn bit ở nghiên cứu trước đạt 0,017217 và 0,004048 tương ứng. Cả hai tập đã được dùng để phát triển.

| Khoảng cách để chọn mẫu fit | NeuralOperator | PDEInvBench 241 |
|---|---:|---:|
| Hamming chín bit | 0,017821 | 0,004792 |
| Chỉ đếm số bit bật trong chín ô | 0,020721 | 0,004632 |
| Chỉ chấp nhận khớp đúng chín bit | 0,020081 | 0,006294 |
| Hamming bốn bit | 0,018362 | 0,004144 |

Chia sẻ mềm có lợi so với yêu cầu khớp tuyệt đối trên cả hai tập. Lợi ích không nhất quán trước cách chỉ đếm số đỉnh; ngay cả bốn bit với Hamming cũng tốt hơn chín bit ở archive 241. Kết quả giữ các nút đo đúng nguyên giá trị và công bố mọi trường, arm, vùng, so sánh và CI trong fields.csv, summary.json. Dừng họ chín bit đã khóa. [Nguồn gốc chung FNO của hai archive](../PRIOR.md)

~~~bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python study.py /tmp /tmp/clara-pdeinv241 /tmp/darcy-neighbors-replay
diff fields.csv /tmp/darcy-neighbors-replay/fields.csv
~~~
