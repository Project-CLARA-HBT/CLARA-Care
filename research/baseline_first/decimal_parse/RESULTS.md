# Ghép hai số để chuyển sang binary64 trên dữ liệu điện UCI

**Loại cơ chế ghép cặp SIMD.** Trên 14 ngày đầu của dữ liệu điện hộ gia đình UCI, cơ chế ghép hai trường giảm trung vị 35,32% thời gian so với fast_float nhưng chậm hơn 25,26% so với đối chứng dùng cùng phép nhận dạng dạng số và chia từng trường. Đối chứng vô hướng thắng ở cả 14 ngày. Ngưỡng đã đăng ký là giảm ít nhất 20% trước từng parser. Đây là kết quả development trên một hộ gia đình. [Protocol trước phép đo](PROTOCOL.md) · [Nguồn UCI, CC BY 4.0](https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption)

| Arm | Trung vị ns/trường¹ | Tiết kiệm của ghép cặp so với arm² | Số ngày ghép cặp thắng |
|---|---:|---:|---:|
| fast_float v8.3.3 | 13,40 | 35,32% | 14/14 |
| libstdc++ from_chars | 13,89 | 35,37% | 14/14 |
| Chuyên biệt vô hướng | 7,06 | −25,26% | 0/14 |
| Chuyên biệt ghép cặp SSE2 | 8,87 | — | — |
| Chỉ quét trường và ghi độ dài | 5,10 | — | — |

¹ Trung vị mười lượt của từng ngày rồi lấy trung vị theo ngày. ² Tính tỷ số hai thời gian trung vị trong cùng ngày trước khi lấy trung vị theo ngày. Chênh lệch nhanh nhất/chậm nhất của ghép cặp so với đối chứng vô hướng là chậm hơn 1,41% và 52,69%. Hai implementation tổng quát có thể chia sẻ kỹ thuật chuyển đổi. Mốc quét chỉ đo chi phí nhận diện trường và ghi độ dài. [Toàn bộ 700 phép đo](timings.csv) · [Từng ngày](summary.json)

Có 19.116 hàng, 1.258.436 byte và 133.812 trường. Cả 133.798 trường có số đều có một đến ba chữ số trước dấu chấm và đúng ba chữ số sau dấu chấm. Có 14 giá trị thiếu. Trong 57.348 cặp có thể xử lý trong hàng, 57.342 có hai thành viên đạt điều kiện. Mức đồng nhất gần tuyệt đối này thuận lợi cho chuyên biệt hóa. Với fast path trên từng trường đã có, ghép cặp thêm công việc nhưng không rút ngắn tổng thời gian trên CPU đã đo. Chưa tách riêng tác động của kiểm tra cặp, bố trí mã sinh bởi compiler và phép chia. [Số đếm và digest theo ngày](oracle.json)

Bốn parser khớp oracle ở từng bit trên toàn bộ 133.812 trường, gồm cả sentinel cho giá trị thiếu. Oracle Node dùng số nguyên lớn, xác định số mũ từ phân số và làm tròn một lần về binary64 gần nhất, hòa về chẵn. Dữ liệu không có ký pháp mũ, mantissa âm, subnormal hoặc phân số dài để đánh giá các dạng đó. Mỗi phép chạy đọc các hàng nguyên bản trong RAM, bỏ hai cột ngày/giờ khi quét, và ghi bảy từ đầu ra đã cấp phát. Tất cả arm dùng cùng vòng tách trường. Phép đo loại chi phí I/O, khởi tạo bộ đệm và ghi file oracle. CPU WSL2 i5-12600K, ghim logical CPU 2 trên máy dùng chung. Không có suy luận GPU. Hai tuần liền nhau cho biết độ nhất quán trên workload này. Mẫu không đủ để suy luận độ biến thiên giữa các hộ hoặc các định dạng. [Oracle độc lập](verify.mjs) · [Công trình fast_float](https://arxiv.org/abs/2101.11408)

### Tái lập

Tài liệu protocol ghim SHA của đối tượng tag v8.3.3. Commit nguồn mà tag này trỏ tới là `dbeabeeb3e6791cb96994c2a7a084c36e62ccfb2`. SHA-256 ZIP UCI đã tải là `9f84b46ade8a2d8e1286ec4b2b6c2987a45a755c59f263be3b3d10dfbda3ff`. Sử dụng GNU C++ 13.3.0, build tĩnh trên Linux x86-64 và chép binary sang WSL2. Các lệnh sau cũng chạy được trên cùng một host x86-64 với CPU 2 trong cpuset. Chọn một thư mục scratch trống. [Nguồn upstream đúng commit](https://github.com/fastfloat/fast_float/tree/dbeabeeb3e6791cb96994c2a7a084c36e62ccfb2)

```bash
d=$(mktemp -d)
curl -fsSL 'https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip' -o "$d/uci.zip"
echo "9f84b46ade8a2d8e1286ec4b2b6c2987a45a755c59f263be3b3d10dfbda3ff  $d/uci.zip" | sha256sum -c -
git clone -q --depth 1 --branch v8.3.3 https://github.com/fastfloat/fast_float "$d/ff"
test "$(git -C "$d/ff" rev-parse HEAD)" = dbeabeeb3e6791cb96994c2a7a084c36e62ccfb2
g++ -std=c++20 -O3 -msse2 -static -Wall -Wextra -Werror -I"$d/ff/include" parse.cpp -o "$d/parse"
python3 prepare.py "$d/uci.zip" "$d/days"
bash benchmark.sh "$d" 2
node --check verify.mjs
node verify.mjs "$d/days" "$d/out" > "$d/oracle.json"
cmp oracle.json "$d/oracle.json"
python3 summarize.py "$d/timings.csv" > "$d/summary.json"
```

Open Food Facts vẫn dành riêng. Pilot không cung cấp lý do để mở holdout cho cơ chế ghép cặp, chạy simdjson trên JSON thực hoặc tuyên bố rằng nhận diện số thập phân ngắn là đóng góp mới.
