# Kết quả development VietMed

Cả hai phép đo dùng 168 đoạn, 21 người nói, 10 bản ghi và 3.730 token tham chiếu. Với timestamp, PhoWhisper-base mắc 1.169 lỗi, PhoWhisper-large mắc 577 lỗi. Bỏ dấu ở cả hai phía chỉ giảm lần lượt 47 và 23 lỗi.

Trong lần giải mã năm giả thuyết không timestamp, hạng đầu mắc 553 lỗi, medoid 550 và oracle 445. Oracle giảm 19,5% so với hạng đầu và 19,1% so với medoid. Có 78 đoạn có thể cải thiện, trải trên cả 10 bản ghi. Hạng đầu đúng nguyên đoạn 22 lần, medoid 21 và oracle 31. Oracle dùng đáp án nên mức giảm này chỉ là giới hạn trên.

Chạy `node verify.mjs base.json large.json` và `node verify_nbest.mjs nbest.json` từ thư mục này để kiểm tra số đếm. Khi chuyển trọng số sang CTranslate2 với Transformers đời cũ, dùng `torch_dtype=torch.float16` trong lời gọi `from_pretrained` của converter, rồi xuất với `--quantization float16`. Tham số `dtype` thuộc giao diện mới hơn.

## Chấm lại trên development

Từ thư mục đo trên WSL, chạy `python feature_cache.py` bằng môi trường CUDA của lần giải mã gốc. Cache chứa điểm decoder và log xác suất bigram trung bình của từng giả thuyết. Bigram đếm trên transcript train, thêm 0,1 vào mỗi số đếm và tính cả ký hiệu kết câu. Chạy `python rerank.py features.json nbest.json` để đối chiếu toàn bộ số đếm từng đoạn rồi đánh giá.

Mỗi lượt giữ riêng một bản ghi và kiểm tra người nói không xuất hiện ở cả hai phía. Chín bản ghi còn lại dùng để chọn trọng số LM giảm số lỗi nhiều nhất hoặc khớp hồi quy ridge dự đoán chênh lệch số lỗi giữa các giả thuyết trong cùng đoạn. Đối chứng LM và hồi quy dùng cùng hai đặc trưng. Một biến thể hồi quy bổ sung tổng khoảng cách edit đến năm giả thuyết. Hòa điểm chọn hạng xuất hiện trước.

Trên 10 lượt giữ riêng bản ghi, LM đã tune mắc 541 lỗi (14,50% trên 3.730 token), hồi quy cùng đặc trưng 548 lỗi và hồi quy thêm khoảng cách đồng thuận 549 lỗi. LM giảm 12/553 lỗi (2,17%) so với hạng đầu. Cả hai hồi quy đều thua LM. Không bộ chọn nào đạt mức giảm 15%. Tệp `rerank_results.json` giữ số lỗi ở từng bản ghi, kể cả các lượt kết quả kém hơn. Đây là kết quả development trên mẫu đã chọn.
