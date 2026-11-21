# So sánh dự báo theo chuỗi trên ảnh validation iWildCam

Trên 198 ảnh của 93 chuỗi tại 22 camera validation ngoài miền, lấy trung bình xác suất trong chuỗi đạt macro-F1 cao nhất. Quy tắc co dự báo theo độ tin cậy và mức bất đồng kém phép lấy trung bình 3,40 điểm phần trăm macro-F1.

| Quy tắc | Đúng / 198 | Accuracy | Macro-F1 |
|---|---:|---:|---:|
| Từng ảnh | 95 | 47,98% | 27,88% |
| Trung bình chuỗi | 98 | 49,49% | 33,02% |
| Co về trung bình các ảnh còn lại | 95 | 47,98% | 29,62% |

Lấy 512 MiB đầu archive theo thứ tự lưu trữ, kiểm tra SHA-256 metadata theo [kết quả trước](../RESULTS.md), rồi chỉ giải mã JPEG thuộc split `val`. Trong 684 ảnh validation giải mã đầy đủ, 486 ảnh không có ảnh đồng chuỗi trong phần dữ liệu tải về. Phép so sánh dùng cả 81 nhóm hai ảnh và 12 nhóm ba ảnh còn lại. Các nhóm có thể thiếu ảnh của chuỗi gốc. Mẫu phụ thuộc thứ tự archive và chỉ bao phủ 22 trong 32 camera validation. Chênh lệch quan sát được chưa đủ để kết luận cho toàn bộ validation.

Dùng ResNet-50 ABSGD seed 0 đóng băng, ảnh RGB resize vuông 224 px, chuẩn hóa ImageNet và softmax đầu ra. Trọng số được công bố cho iWildCam, lịch sử huấn luyện và chọn checkpoint của bên cung cấp chưa được kiểm chứng độc lập. [Checkpoint đã ghim](https://huggingface.co/emmilly/absgd-iwildcam-resnet50-absgd-lam1.1-s0/tree/efca3acf59ce6e3bc2ee024e103595f7279c38ec) · [Archive WILDS đã ghim](https://huggingface.co/datasets/pangwei/wilds-iwildcam/tree/78b5e7d858adb01cb5661c7b5f8666a4e91be2cb)

Với xác suất từng ảnh p và trung bình các ảnh còn lại q, hệ số co bằng (1 − max p) × (1 − ‖p − q‖₁/2). Dự báo là lớp có giá trị lớn nhất sau khi trộn p và q theo hệ số này. Cả ba quy tắc sử dụng cùng tập ảnh và cùng checkpoint. Nhãn thật chỉ tham gia tính điểm. Macro-F1 tính trên hợp của lớp thật và lớp dự báo của từng phương pháp. [Dự báo và SHA-256 từng ảnh chấm điểm](receipt.json)

Chạy lại từ thư mục này với Python 3.12, requests, Pillow, torch 2.7.1 và torchvision 0.22.1. File metadata lấy theo hướng dẫn ở thư mục cha.

~~~bash
python acquire.py /tmp/clara-iwildcam-wilds-metadata.csv /tmp/clara-iwpixels
curl --fail --location https://huggingface.co/emmilly/absgd-iwildcam-resnet50-absgd-lam1.1-s0/resolve/efca3acf59ce6e3bc2ee024e103595f7279c38ec/model.pt -o /tmp/clara-iwmodel.pt
python score.py /tmp/clara-iwpixels /tmp/clara-iwmodel.pt > /tmp/iwild-replay.json
cmp /tmp/iwild-replay.json receipt.json
~~~
