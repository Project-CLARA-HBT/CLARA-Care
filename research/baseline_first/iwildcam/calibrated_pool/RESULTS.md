# Hiệu chỉnh dự báo theo độ hiếm trên ảnh iWildCam

Trên 104 ảnh của 11 camera giữ lại, trung bình log xác suất đạt accuracy 51,92% và macro-F1 5,236%. Quy tắc ưu tiên ảnh có bằng chứng mạnh nhất cho lớp hiếm đạt 48,08% và 5,132%, thấp hơn cả hai kiểu lấy trung bình. Chưa có cơ sở chọn quy tắc mới.

| Quy tắc | τ chọn trên 94 ảnh của 11 camera khác | Macro-F1 giữ lại (%) | Accuracy giữ lại (%) |
|---|---:|---:|---:|
| Từng ảnh | 0 | 4,661 | 48,08 |
| Trung bình xác suất | 0 | 5,204 | 50,00 |
| Trung bình log xác suất | 0 | 5,236 | 51,92 |
| Trộn trung bình và cực đại theo độ hiếm | 0 | 5,132 | 48,08 |

Cả bốn lần chỉnh prior đều chọn τ=0. Với quy tắc độ hiếm, macro-F1 giữ lại dao động từ 4,104% đến 5,146% trên lưới đã đăng ký. Với trung bình log, τ=0,75 đạt 5,514% khi xem lại nhóm giữ lại. Dùng giá trị này để chọn phương pháp sẽ làm mất tính độc lập của phép đánh giá.

Mỗi điểm macro-F1 lấy trung bình trên đúng 182 đầu ra với F1 bằng 0 cho lớp không có nhãn thật hoặc dự báo nào. Mẫu nhỏ, camera có số ảnh khác nhau, và các ảnh cùng chuỗi phụ thuộc nhau. Giá trị tuyệt đối không so trực tiếp với kết quả cũ dùng tập lớp thay đổi theo phương pháp. Prior dùng 129.809 ảnh train trong metadata. Nguồn checkpoint, cách lấy phần đầu archive và hạn chế về lịch sử huấn luyện được ghi ở [thí nghiệm ảnh ban đầu](../image_dev/RESULTS.md).

[Tất cả điểm chỉnh và giữ lại theo τ, số ảnh và điểm theo camera](summary.json) · [Quy tắc đăng ký trước](PROTOCOL.md)

Chạy từ thư mục này với môi trường Python của thí nghiệm ảnh ban đầu.

~~~bash
python study.py /tmp/clara-iwpixels /tmp/clara-iwmodel.pt /tmp/clara-iwildcam-wilds-metadata.csv > summary.json
~~~
