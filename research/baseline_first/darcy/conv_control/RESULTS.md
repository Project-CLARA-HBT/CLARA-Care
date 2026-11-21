# Đối chứng tích chập cho nội suy Darcy 16→32

Trên 128 trường development đã dùng ở các thí nghiệm trước, thêm kênh vật liệu giảm 9,41% sai số trung bình ở điểm thiếu. Cải thiện nằm ở phần trong lưới. Lỗi ở hàng cuối hoặc cột cuối tăng nhẹ. Stencil chọn theo mẫu bốn bit ở nghiên cứu trước đạt 0,017217 trên cùng trường, thấp hơn 9,29% so với mạng tích chập có vật liệu.

| Đầu vào | Epoch chọn | Relative L2 điểm thiếu | Phần trong | Hàng hoặc cột cuối |
|---|---:|---:|---:|---:|
| Áp suất | 35 | 0,020952 | 0,020202 | 0,074304 |
| Áp suất và vật liệu | 32 | 0,018981 | 0,018136 | 0,074424 |

Mỗi mạng dùng ba lớp tích chập 3×3 rộng 32 kênh, zero padding, GELU và đầu ra 1×1 với ba kênh phần dư, mỗi kênh ứng với một parity thiếu. Mạng cộng phần dư vào áp suất nút quan sát gần đó rồi xen kẽ theo parity. Cả hai khôi phục chính xác toàn bộ 32.768 nút quan sát trên development. Relative L2 được tính riêng từng trường và từng vùng trước khi lấy trung bình.

Dùng trường 0–447 để fit và 448–511 để chọn epoch có relative L2 trung bình thấp nhất trong 35 epoch. Ở epoch đầu, tốt nhất và cuối, lỗi validation lần lượt là 0,074422 / 0,020969 / 0,020969 với áp suất và 0,077597 / 0,018767 / 0,019320 khi thêm vật liệu. Mạng chỉ dùng áp suất đạt cực tiểu ở giới hạn ngân sách, nên chưa xác định được lỗi sau khi huấn luyện lâu hơn. Khởi tạo lại với seed 412, fit đủ 512 trường theo số epoch đã chọn rồi chấm trường 512–639. Một seed và một ngân sách huấn luyện giới hạn phạm vi kết luận.

Chạy trong thư mục này với Python 3.12, PyTorch 2.7.1, CPU hai luồng và hai file train 16/32 có SHA-256 trong [kiểm tra archive](../restriction/AUDIT.md). File convergence.csv ghi từng epoch, fields.csv ghi từng trường.

```bash
python study.py /tmp
node --check summarize.mjs
node summarize.mjs
```
