# Khôi phục byte từ snapshot GLHS và biên nhận kèm kho nội dung

**GLHS hòa đối chứng ở cả 3.699 lượt đọc.** Mỗi phương pháp trả đúng 836.429 byte qua 2.057 lượt được giữ nội dung và để trống đúng cả 1.642 lượt sau xóa. Mọi kết quả được chấm bằng cách so byte thực sự trả về với một bản dựng độc lập từ nguồn. Rút tuyên bố GLHS khôi phục byte chính xác hơn biên nhận ký khi hai bên có cùng quyền lưu nội dung. Điểm 100 và 50 của E16 trước đó được gán theo tên phương pháp và không đo endpoint này. [Kiểm toán E16](../comparator_recheck/RESULTS.md) · [Protocol development](PROTOCOL.md)

| Giai đoạn | Số lượt đọc mỗi phương pháp | Trả đúng byte | Để trống đúng | Byte trả về |
|---|---:|---:|---:|---:|
| Còn toàn bộ nội dung | 1.233 | 1.233 | 0 | 501.721 |
| Sau xóa 43/128 hội thoại | 1.233 | 824 | 409 | 334.708 |
| Sau xóa hết nội dung | 1.233 | 0 | 1.233 | 0 |

Tất cả 1.233 lượt USER trong 128 hội thoại thuộc một shard huấn luyện của Schema-Guided Dialogue đều được xét ở cả ba giai đoạn. Mỗi snapshot là chuỗi UTF-8 JSON chính tắc của trường frames đã đóng gói, không phải byte thụt lề của tệp nguồn. Hai lần đọc cùng một snapshot là phép đo lặp. Lịch xóa do nghiên cứu đặt ra, không phải nhãn thu hồi quyền của bộ dữ liệu. Nguồn và quyền sử dụng do Abhinav Rastogi, Xiaoxue Zang, Srinivas Sunkara, Raghav Gupta và Pranav Khaitan công bố theo CC BY-SA 4.0. Bảng dẫn xuất phát hành cùng giấy phép. [Nguồn ghim revision](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue/blob/e852981ae34990f4358979625854259302feaa78/train/dialogues_001.json) · [Giấy phép](https://creativecommons.org/licenses/by-sa/4.0/)

Phép đo gọi trực tiếp hàm `reconstruct_snapshot_artifact` với đối tượng `GlhsSnapshotManifest` của repo, dùng schema v3, xác minh cả digest payload và digest manifest. Mã thí nghiệm dựng manifest và thay lớp lưu trữ bằng các tệp riêng. Vì thế số byte đo ở đây chỉ xét bước đọc snapshot GLHS; việc chọn nội dung, khôi phục quyết định từ nhiều bảng, thu hồi đồng thời, giao dịch PostgreSQL và kiểm soát truy cập khi triển khai nằm ngoài phép đo. Mỗi biên nhận đối chứng ràng buộc khóa tra cứu, hội thoại và SHA-256 bằng Ed25519. Đối chứng xác minh chữ ký, khóa tra cứu và hash nội dung trước khi trả về. Cả hai được giữ đủ snapshot và metadata. Thư mục nội dung từng hội thoại bị xóa vật lý ở lịch tương ứng. [Mã đọc gốc](../../../services/api/src/clara_api/glhs/gateway.py) · [Bộ chạy](run.py)

Lúc đầy đủ, metadata GLHS dùng 1.010.143 byte, metadata đối chứng dùng 311.512 byte (gồm 32 byte khóa công khai). Nội dung chiếm lần lượt 501.721 và 499.828 byte vì kho đối chứng gộp các payload trùng trong một hội thoại. Đây là độ dài tệp logic của hai định dạng trong thí nghiệm. Số byte metadata lưu trữ, chi phí thiết lập hệ tệp, xác minh chữ ký và phối hợp vòng đời là những đại lượng khác nhau. Kết quả hòa về đọc byte không tạo thêm một bài ReceiptMin. [Kích thước từng giai đoạn](results/sizes.json) · [Mọi kết quả ghép cặp](results/queries.csv) · [Kiểm tra độc lập](results/verified.json)

## Tái lập

Chạy từ gốc repo với Python 3.12, các dependency khóa trong services/api/uv.lock và Node.js 20.20.2. Cây Git services/api/src có object ID `e9de01f14ba2c96dbb602c371c65be73bd4bb8fd`. Protocol SHA-256 trước lần đo đầu là `6de7c9cf77cbd5b1d322d45f61eb47f90516daa43c0335ade3baddc3fe62611c`. Hai lượt WSL2 chạy CPU từ hai kho mới với hai cặp khóa ký độc lập cho các luồng kết quả và ba tệp báo cáo trùng từng byte. Bước ghi và bước đọc chạy trong hai tiến trình riêng. Tệp nguồn chỉ được cấp qua đối số của bước ghi và bước chấm độc lập.

```bash
study=research/glhs_journal/byte_reconstruction
work=$(mktemp -d)
curl -fsSL https://raw.githubusercontent.com/google-research-datasets/dstc8-schema-guided-dialogue/e852981ae34990f4358979625854259302feaa78/train/dialogues_001.json -o "$work/source.json"
(cd services/api && uv sync --frozen --no-dev --no-install-project)
export PYTHONPATH=services/api/src
services/api/.venv/bin/python "$study/run.py" write "$work/source.json" "$work/archive"
services/api/.venv/bin/python "$study/run.py" read "$work/archive" "$work/frames"
mkdir "$work/evidence"
node --check "$study/verify.mjs"
node "$study/verify.mjs" "$work/source.json" "$work/frames" "$work/evidence"
cp "$work/frames/sizes.json" "$work/evidence/"
diff -rq "$study/results" "$work/evidence"
```
