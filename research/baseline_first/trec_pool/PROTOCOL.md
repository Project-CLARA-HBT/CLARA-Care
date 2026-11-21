# Độ ổn định khi NIST bổ sung nhãn vào vòng 1

Đây là kiểm tra development. Đơn vị so sánh là cùng một run gửi cho cùng các topic và corpus ở vòng 1. Đã đọc hai báo cáo năm 2020 của Voorhees, trang lưu trữ và mẫu định dạng đầu tệp trước khi chốt phân tích. Dùng toàn bộ danh sách submission file trên trang archive vòng 1. Tải duy nhất topic, danh sách docid, qrels ban đầu và qrels chronological **cho corpus vòng 1**. Các nhãn đến muộn trong tệp chronological thuộc phép đo development này.

1. Kiểm từng cặp topic–docid thuộc frame. Báo tổng, mới, mất, sửa điểm, phân bố điểm 0/1/2 và số topic.
2. Gọi trec_eval v9.0.8 trên mỗi run cố định với cả hai qrels, kể cả các run ít hiệu quả và run trùng kết quả. Dùng mean NDCG@10 tính trên toàn bộ topic (`-c`). Kiểm thêm P@5. Giữ cả hai điểm trên từng run. Đếm mọi cặp đảo thứ tự, cặp hòa ở mỗi đầu và so Kendall tau-b trên điểm xuất ra bốn chữ số thập phân. Các run cùng nhóm có thể phụ thuộc nhau.
3. Nếu bằng chứng chỉ là thay đổi thứ hạng khi pool sâu hơn thì rút đề tài vì ban tổ chức đã công bố chính thiết kế này. Mốc nhãn muộn hơn có thể bổ sung một quan sát định lượng. Muốn mở claim khác cần một quyết định có ý nghĩa, baseline dùng cùng thông tin và nguồn kiểm định mới.
