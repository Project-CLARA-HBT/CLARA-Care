# Đổi bản tzdb có làm thay đổi từng cuộc hẹn đã lưu?

**Loại đề xuất này khỏi danh mục bài.** IANA cung cấp bằng chứng độc lập về việc quy tắc của Beirut thay đổi. Trong các nguồn lịch lặp đã kiểm, không có cặp nhãn về thời điểm của cùng một cuộc hẹn ở Beirut dưới cả hai bản 2023b và 2023c. Vì vậy chưa thể đánh giá độ đúng của phương pháp chọn cuộc hẹn bị ảnh hưởng trên workload bên ngoài. [Protocol](PROTOCOL.md) · [Nguồn, SHA-256 và kết quả](results.json)

Trên WSL2, biên dịch riêng tệp `asia` của từng bản rồi đối chiếu mọi giờ UTC trong năm 2023 cho thấy đúng một khoảng có offset khác nhau. Từ 22:00 UTC ngày 25/3 đến trước 22:00 UTC ngày 20/4, offset của Beirut là UTC+2 với 2023b và UTC+3 với 2023c. Khoảng này chứa 624 giờ. Hai đầu mút khớp ngày chuyển đổi ghi trong NEWS. Chẳng hạn một cuộc hẹn *giả định* ở Beirut lúc 09:00 ngày 1/4 sẽ lệch một giờ UTC. 624 giờ đo mức độ thay đổi của quy tắc, không phải 624 cuộc hẹn đã quan sát. [IANA 2023b](https://data.iana.org/time-zones/releases/tzdata2023b.tar.gz) · [IANA 2023c](https://data.iana.org/time-zones/releases/tzdata2023c.tar.gz)

| Nguồn độc lập | Nhãn thực sự có | Phần thiếu cho việc đánh giá nâng cấp |
|---|---|---|
| libical, `icalrecur_test.txt` | 157 khối có RRULE và trường kết quả INSTANCES. Không có TZID trong tệp. | Không nhận diện được lịch Beirut ở hai bản. [Tệp vàng](https://github.com/libical/libical/blob/bb88226d94ab6d173c5e06fd1e548ad38e8414a6/src/test/icalrecur_test.txt) |
| libical, `recur.txt` | 58 VEVENT có nhãn số lần xuất hiện. TZID tường minh duy nhất là America/Los_Angeles. | Số lần xuất hiện có thể giữ nguyên khi thời điểm UTC thay đổi. [Tệp VEVENT](https://github.com/libical/libical/blob/bb88226d94ab6d173c5e06fd1e548ad38e8414a6/test-data/recur.txt) |
| ical4j, `RecurDstOverlapSpec` | Kiểm tra offset được chọn khi giờ địa phương lặp lại tại Los Angeles. | Kiểm tra một quy tắc giải nhập nhằng, không có cặp nhãn nâng cấp ở Beirut. [Ca hồi quy của tác giả](https://github.com/ical4j/ical4j/blob/4dac4d913706b41fa633449e8a95f7d3a0b410a2/src/test/groovy/net/fortuna/ical4j/model/RecurDstOverlapSpec.groovy) |
| IETF, RFC 5545 §3.8.5.3 | Các ví dụ RRULE chứa đáp án của tác giả. TZID tường minh là America/New_York. | Không có lịch Beirut gắn với hai bản 2023. [Đặc tả và ví dụ](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.8.5.3) |

**Khoảng trống về thuật toán cũng hẹp.** RFC 7808 đã định nghĩa cách client lấy danh sách múi giờ thay đổi bằng token đồng bộ, kiểm tra ETag và cập nhật cache. Jon Skeet đã mô tả việc giữ giờ địa phương, ID múi giờ và bản quy tắc để tính lại UTC khi có nâng cấp. Một đối chứng đủ thông tin có thể chọn vùng thay đổi, gộp thứ tự các mốc chuyển tiếp ở hai bản rồi tra khoảng trên cùng chỉ mục lịch. Cần xử lý riêng giờ bị bỏ qua, giờ bị lặp, recurrence exception và lịch tự mang VTIMEZONE trước khi tuyên bố liệt kê chính xác các lần hẹn. Đây là yêu cầu so sánh đề xuất; chưa có phép đo tốc độ giữa hai cách trên các ca thực sự có nhãn. [RFC 7808 §4.1.4](https://www.rfc-editor.org/rfc/rfc7808.html#section-4.1.4) · [Skeet, ví dụ nâng cấp dữ liệu múi giờ](https://codeblog.jonskeet.uk/2019/03/27/storing-utc-is-not-a-silver-bullet/) · [RFC 5545 §3.6.5](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.6.5)

## Tái lập

Chạy từ thư mục này với Python 3.11+, zic và Node.js. Trình kiểm tra Node đối chiếu cả sáu digest, tính hai đầu mút theo ngày IANA công bố và đếm lại các khối dữ liệu libical. Hai lần chạy ở Linux và WSL2 tạo JSON trùng từng byte. Kiểm toán chỉ bao phủ các tệp, release và múi giờ đã nêu.

```bash
python audit.py "$CACHE" > replay.json
cmp replay.json results.json
node --check verify.mjs
node verify.mjs replay.json "$CACHE"
```
