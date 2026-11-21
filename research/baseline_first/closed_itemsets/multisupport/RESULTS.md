# Truy vấn ba ngưỡng trên MovieLens 25M

Sau một lần đọc giao dịch chung, khai thác ở ngưỡng 500 rồi lọc cho ngưỡng 1.000 và 1.500 cho thời gian trung vị 0,961 s. Khai thác lại ba lần đạt 1,003 s. Biến thể mã hóa từng itemset một lần rồi phân phối vào các buffer mất 1,015 s. Biến thể thua cách lọc ở cả sáu block, chậm từ 3,79% tới 9,37%. Tổng thời gian tính từ khi mở archive tới khi tạo đủ ba chuỗi byte. Thời gian materialize trung vị lần lượt là 0,034 s, 0,034 s và 0,083 s.

Mọi đầu ra ở 18 lượt khớp cả ba digest của phép thuật toán gốc. Chọn ngưỡng cao hơn giữ nguyên điều kiện đóng vì một superset có cùng support cũng vượt bất kỳ ngưỡng nào mà itemset đó vượt. Kết quả kiểm định trên 5.000 người dùng đầu và 50 phim, cùng cohort như lần trước. Biên giảm thời gian 20% chưa đạt. Các block đo lặp trên một máy cho biết độ dao động khi chạy.

~~~bash
python study.py /path/to/ml-25m.zip > replay.jsonl
~~~

Cần pyfim 6.28. Archive gốc, ba giá trị support, mục rỗng, tiêu chí chọn phim và digest đầu ra kế thừa nghiên cứu cha. [Phép thử trước](../RESULTS.md) · [GroupLens](https://grouplens.org/datasets/movielens/25m/)
