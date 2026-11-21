# Đăng ký phép thử trên camera validation

Chỉ dùng các chuỗi có ≥2 ảnh từ manifest val đã công bố ở image_dev. Sắp camera đủ điều kiện theo ID số, xen kẽ vào nhóm chỉnh tham số (vị trí 0,2,…) và nhóm đánh giá (1,3,…). Các kết quả gộp cũ đã công khai nên đây là phân tích phát triển, không phải xác nhận độc lập.

Tính prior π bằng tần suất ảnh train với cộng một cho từng lớp. Chấm macro-F1 trên toàn bộ K đầu ra checkpoint cho mọi nhóm và mọi phương pháp, lớp có mẫu số bằng 0 nhận F1=0. Với mỗi phương pháp, chọn τ trong {0, 0.25, 0.5, 0.75, 1} tối đa hóa macro-F1 gộp trên camera chỉnh tham số, hòa chọn τ nhỏ nhất. Báo cáo từng ảnh, trung bình xác suất, trung bình log xác suất, và cả ba sau hiệu chỉnh bằng cách trừ τ log π từ điểm log. Quy tắc mới dùng bằng chứng mạnh nhất trong chuỗi cho lớp hiếm: trộn trung bình và cực đại xác suất theo trọng số r_c=log(π_max/π_c)/log(π_max/π_min), rồi hiệu chỉnh log như trên. Báo cáo cả trường hợp τ=0. Đối chiếu kết quả theo từng camera và độ nhạy theo τ. Không thay đổi lưới sau khi chấm.

Hiệu chỉnh prior tham khảo Menon và cộng sự, ICLR 2021. [Long-tail learning via logit adjustment](https://arxiv.org/abs/2007.07314)
