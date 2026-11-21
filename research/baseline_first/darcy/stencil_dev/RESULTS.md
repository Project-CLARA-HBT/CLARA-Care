# Nội suy một phía sửa sai số biên, boosting có lỗi tổng nhỏ nhất

Trên 128 trường development đã dùng ở phép 16→32, relative L2 trung bình ở vị trí thiếu là 0,037714 với ngoại suy bậc ba, 0,026903 với stencil áp suất, 0,023647 sau thêm tương tác vật liệu và 0,022143 với histogram boosting cùng đặc trưng. Chỉ thêm tương tác ở biên còn 0,027382. Ở riêng mép ngoài, stencil vật liệu đạt 0,164531 và boosting 0,217050; ở phần trong, hai giá trị lần lượt là 0,020416 và 0,015937. Sự đảo thứ tự theo vùng giải thích vì sao chỉ báo số ở biên sẽ đánh giá quá cao phương pháp. Các điểm quan sát có cùng giá trị với dữ liệu gốc. File fields.csv giữ mọi arm kể cả bốn arm cũ.

Từ thư mục này, với các archive train được kiểm digest và giải nén dưới /tmp, chạy lệnh dưới để sinh fields.csv. Chỉ đánh giá chỉ số train 512–639 sau khi fit ở 0–511. Đây là phục hồi áp suất khi đã thấy áp suất lưới thô.

~~~bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python study.py
~~~
