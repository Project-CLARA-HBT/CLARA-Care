# Khi nào lưới trọng số bỏ sót tín hiệu truy hồi?

Phân tích mô tả development dùng lại các đường hạng đã kiểm định. Các kết quả trước về tốc độ và lưới 11 điểm của nghiên cứu truy hồi đã được biết. Khóa các phép tổng hợp dưới đây trước khi đọc các đường hạng để tính ảnh hưởng. Sử dụng mọi nhãn dương, mọi truy vấn và cả ba nguồn. Giữ riêng kết quả từng nguồn.

1. So toàn bộ 65.536 trọng số với ba lưới đều có cả hai đầu mút. Dùng 11 điểm như protocol truy hồi trước, 21 và 101 điểm là hai lần kiểm tra độ nhạy dày hơn. Ánh xạ i/m vào số nguyên gần nhất của 65.535 i/m, hòa chọn số chẵn. Ba lưới lồng nhau. Đếm các cặp truy vấn–tài liệu có nhãn từng lọt top 10 và những cặp hoàn toàn vắng ở lưới thưa.
2. Một khoảng là một dải liên tục cực đại nằm trong top 10, gộp cả các lần đổi hạng nội bộ. Liệt kê mọi khoảng mà lưới bỏ qua, kể cả tài liệu xuất hiện trong một khoảng khác. Báo số khoảng, số truy vấn liên quan và độ rộng tính bằng số trọng số nguyên (hai biên đều đóng).
3. Tính nDCG@10 nhị phân với mẫu số lý tưởng từ toàn bộ nhãn dương của mỗi truy vấn. So giá trị tốt nhất trong lưới với giá trị tốt nhất toàn miền ở hai mức. Ở mức truy vấn, chọn lại trọng số cho mỗi truy vấn bằng nhãn của chính nó, báo chênh lệch trung bình, lớn nhất và số truy vấn bị giảm. Ở mức nguồn, chọn một trọng số chung tối đa hóa trung bình trên 50 truy vấn, báo giá trị, chênh lệch và trọng số. Khi nhiều trọng số đạt tối đa trong sai số tuyệt đối 1e-12, báo trọng số nhỏ nhất. Các tối ưu này đo sai số khi khảo sát hồi cứu; việc chọn trọng số trên truy vấn tương lai cần thí nghiệm khác.
4. Kiểm tra bằng hai cách tính độc lập từ cùng đường hạng, một cách khai triển mọi trọng số, một cách đánh giá tại các mốc thay đổi. So cả mẫu số nhãn, số khoảng và các chênh lệch. Lưu kết quả từng truy vấn và từng khoảng bị bỏ sót. Không suy diễn ra ngoài ba corpus NanoBEIR hoặc lưới 16 bit.

[Thiết kế đường hạng](../PROTOCOL.md) · [Protocol lưới 11 điểm](../../retrieval_disagreement/PROTOCOL.md)
