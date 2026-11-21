# Định tuyến stencil theo vật liệu và gradient áp suất

Trên các nút thiếu, mã vật liệu bốn bit giảm relative L2 trung bình so với mã gradient áp suất 13,73% trên NeuralOperator (CI bootstrap ghép cặp 95% 12,68–14,77%, thắng 126/128 trường) và 17,83% trên PDEInvBench 241 (15,67–19,97%, thắng 62/64). Cả hai cận dưới vượt ngưỡng 10% đã đăng ký. Riêng hàng/cột cuối, hai cận dưới chỉ đạt 4,63% và 7,00%. Hai cohort đã được dùng trong phát triển, có thể có chung nguồn gốc trường. Kiểm chứng trên bộ sinh độc lập còn mở. [Giao thức đăng ký](PROTOCOL.md) · [Truy nguyên](../PRIOR.md)

| Cohort | Ridge chung | Băm áp suất | Bốn bit vật liệu | Giảm lỗi tại ô giao diện (CI 95%) |
|---|---:|---:|---:|---:|
| NeuralOperator | 0,021182 | 0,019958 | 0,017217 | 12,40% (11,22–13,56%) |
| PDEInvBench 241 | 0,005383 | 0,004926 | 0,004048 | 18,31% (15,61–21,00%) |

Ba cột ridge/băm/bốn bit là trung bình relative L2 từng trường trên toàn bộ nút thiếu. Hai nhánh phân nhóm đều nhận áp suất và hệ số thấm trong đặc trưng hồi quy. Chỉ tín hiệu chọn bộ lọc thay đổi. Mã băm do nhóm viết dựa trên tensor cấu trúc và nguyên lý chọn bộ lọc của Romano, Isidoro và Milanfar. Các kết quả ở đây đo bản thích nghi Darcy dùng stencil và ridge của nghiên cứu này. [Bài RAISR gốc](https://arxiv.org/abs/1606.01299)

Chạy lại bằng `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python study.py NEURALOPERATOR_DIR PDEINV241_DIR`. Script xác minh SHA-256 của bốn tensor và 192 file HDF5 nguồn, đối chiếu từng trường 241 với tensor đã lấy mẫu. Hai arm ridge và pattern tái lập mọi lỗi toàn trường, nội vùng và ngoại biên đã lưu với dung sai tương đối 1e−11. [Lỗi từng trường](fields.csv) · [Số nút theo bucket, dùng chung cho ba pha](buckets.csv) · [Ngưỡng và thống kê từng vùng](summary.json)
