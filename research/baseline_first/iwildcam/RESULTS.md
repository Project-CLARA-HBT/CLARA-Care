# Nhãn loài trong cùng một chuỗi ảnh iWildCam-WILDS

Trên 32 camera validation ngoài miền, **162 trong 2.533 chuỗi** có từ hai nhãn khác nhau. 647 ảnh nằm trong các chuỗi đó. Bắt buộc dự báo cùng một lớp cho mọi ảnh trong chuỗi cho độ chính xác tối đa **98,53%**, ngay cả khi biết toàn bộ nhãn. Với ảnh trong chuỗi nhiều ảnh, lấy nhãn thật phổ biến nhất của các ảnh *còn lại* đạt 97,76% accuracy và 83,37% macro-F1. Cả hai phép tính dùng nhãn thật để mô tả dữ liệu. Chưa có số đo cho classifier dùng ảnh khi triển khai. [Số liệu đầy đủ](summary.json) · [Protocol](PROTOCOL.md)

| Split | Camera | Ảnh | Chuỗi nhiều ảnh / tổng chuỗi | Chuỗi có nhiều nhãn | Macro-F1 của quy tắc mode biết nhãn |
|---|---:|---:|---:|---:|---:|
| Train | 243 | 129.809 | 23.490 / 24.109 | 1.513 | 88,02% |
| Validation ngoài miền | 32 | 14.961 | 2.484 / 2.533 | 162 | 88,62% |

Hai split không có camera chung. Mode trong chuỗi tối ưu accuracy. Macro-F1 trên bảng là giá trị đạt bởi lựa chọn đó. Tập mẫu của phép đo chỉ dùng ảnh còn lại loại chuỗi đơn ảnh; ở validation còn 14.912 ảnh và 74 lớp. Việc gộp dự báo theo chuỗi đã có trong hệ iWildCam công bố trước đây. Kết quả cho thấy cần giữ tín hiệu từng ảnh ở chuỗi có đối tượng thay đổi. Muốn kết luận phương pháp tốt hơn cần đo trên cùng logits và cùng các frame nhìn thấy. [Hệ đã kết hợp dự báo theo chuỗi](https://github.com/alcunha/iwildcam2021ufam)

Nguồn là metadata.csv của iWildCam-WILDS 2.0 tại revision 78b5e7d858adb01cb5661c7b5f8666a4e91be2cb. Phép tải từng phần khôi phục thành viên TAR dài 34.546.159 byte; đã kiểm tra checksum header và giải nén hai lần từ cùng byte range với hai từ điển khởi đầu khác nhau. Hai bản metadata trùng toàn bộ byte; SHA-256 là 1886a57eddee108aeaabc9d4b79562374baee1b79d37dd782aa1a26a6d4706b6. Chưa xác nhận digest toàn bộ archive 11,96 GB. Để tái lập bằng công cụ chuẩn, giải nén thành viên bằng tar và chạy các lệnh sau. Script chỉ tổng hợp nhãn ở train và val. [Mirror của bản phát hành](https://huggingface.co/datasets/pangwei/wilds-iwildcam/tree/78b5e7d858adb01cb5661c7b5f8666a4e91be2cb) · [Định nghĩa split và license](https://github.com/p-lambda/wilds/blob/472677590de351857197a9bf24958838c39c272b/wilds/datasets/iwildcam_dataset.py)

~~~bash
tar -xOzf iwildcam_v2.0.tar.gz ./metadata.csv > /tmp/iwildcam-metadata.csv
sha256sum /tmp/iwildcam-metadata.csv
python bursts.py /tmp/iwildcam-metadata.csv > replay.json
cmp replay.json summary.json
~~~

## Lịch sử kiểm tra nguồn trước khi tìm được metadata

The official WILDS iWildCam v2 loader reads `sequence_remapped`, `location_remapped`, `datetime`, `y`, and `split` from `metadata.csv`. It exposes sequence and timestamp fields to models, and defines distinct `train`, `val`, `test`, `id_val`, and `id_test` splits. This establishes the schema, not that individual sequences contain multiple frames or that labels are consistent within them. Source: [official loader](https://github.com/p-lambda/wilds/blob/main/wilds/datasets/iwildcam_dataset.py).

No metadata rows or images were opened in this preliminary investigation. Consequently there are no development counts, credible macro-F1 headroom estimates, baseline comparisons, or grounds to advance or reject the opportunity. In particular, a sequence-label oracle would be an upper bound using ground truth, not a model result. Test data must remain unopened. The published WILDS archive is approximately 12 GB compressed, and the loader alone does not provide the requested development screen. Resume by obtaining train/validation-only metadata from a public source, recording its provenance and checksums, and predeclaring the development slice before inspecting predictions.

## Follow-up: source access and competing work (2026-11-21)

The [competition maintainers' 2020 README](https://github.com/visipedia/iwildcam_comp/blob/master/2020/readme.md) and [2021 README](https://github.com/visipedia/iwildcam_comp/blob/master/2021/readme.md) say the original competition files are no longer accessible. HEAD requests to their original `metadata.zip` links returned HTTP 403 for both years; the Kaggle competition data-list endpoint checked returned 404. The official archive checksums published in those READMEs are respectively `3050b2a641ebef259ee73e1476e5e6ae` and `e67aa5c935636360b017dfbf4c8e716f`. A [third-party 2020 training JSON](https://huggingface.co/datasets/anngrosha/iWildCam2020/tree/main) exists, but has not been established as an official Kaggle mirror and was not used. WSL was reachable; no iWildCam file was found under `/root/clara-studies`.

The [2021 winning solution](https://github.com/alcunha/iwildcam2021ufam) already averages nonempty frame predictions across a sequence and combines full-image and detector-crop classifiers. It reports a maximum-box count heuristic and that its DeepSORT experiment performed worse for counting. [Yousif et al.](https://github.com/HayderYousif/iwildcam-2019-fgvc6) also investigated sequence-level species classification. These are direct prior work, not evidence of a new improvement here. Counting and per-image macro-F1 are different tasks and cannot be compared directly.
