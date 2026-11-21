# Kết quả development VietMed

Cả hai phép đo dùng 168 đoạn, 21 người nói, 10 bản ghi và 3.730 token tham chiếu. Với timestamp, PhoWhisper-base mắc 1.169 lỗi, PhoWhisper-large mắc 577 lỗi. Bỏ dấu ở cả hai phía chỉ giảm lần lượt 47 và 23 lỗi.

Trong lần giải mã năm giả thuyết không timestamp, hạng đầu mắc 553 lỗi, medoid 550 và oracle 445. Oracle giảm 19,5% so với hạng đầu và 19,1% so với medoid. Có 78 đoạn có thể cải thiện, trải trên cả 10 bản ghi. Hạng đầu đúng nguyên đoạn 22 lần, medoid 21 và oracle 31. Oracle dùng đáp án nên mức giảm này chỉ là giới hạn trên.

Chạy `node verify.mjs base.json large.json` và `node verify_nbest.mjs nbest.json` từ thư mục này để kiểm tra số đếm. Khi chuyển trọng số sang CTranslate2 với Transformers đời cũ, dùng `torch_dtype=torch.float16` trong lời gọi `from_pretrained` của converter, rồi xuất với `--quantization float16`. Tham số `dtype` thuộc giao diện mới hơn.
