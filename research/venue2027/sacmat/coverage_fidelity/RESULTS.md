# Đối chiếu MC/DC của Xu và cộng sự trên bộ mẫu hội nghị

**Đã tìm thấy mã tác giả và hai bộ yêu cầu MC/DC có nhãn.** XPA ở commit `89c000495d81a1a82ca8de2ab0fc73fecfc4e440` có lớp sinh MC/DC, bộ `conference3` với 27 yêu cầu và bộ `itrust3` với 197 yêu cầu. Vì vậy cần sửa nhận định cũ trong danh mục rằng chưa có mã hoặc vector công khai. Bài gốc phân biệt bốn tiêu chí bao phủ, trong đó MC/DC và bao phủ cặp luật là hai tiêu chí riêng. [Bài SACMAT 2018, §3.1–3.4 và §4](https://par.nsf.gov/servlets/purl/10376453) · [Lớp MC/DC trong XPA](https://github.com/dianxiangxu/XPA/blob/89c000495d81a1a82ca8de2ab0fc73fecfc4e440/src/main/java/org/seal/xacml/coverage/MCDC.java) · [Hai bộ mẫu của tác giả](https://github.com/dianxiangxu/XPA/tree/89c000495d81a1a82ca8de2ab0fc73fecfc4e440/src/test/resources/org/seal/policies)

Trên CPU của WSL2, phép tái lập độc lập cho đúng **27/27 quyết định đã công bố** trong bộ hội nghị, gồm 14 Permit, 11 Deny và 2 IDP. Mỗi một trong 14 điều kiện áp dụng luật là phép hội của hai phép so sánh chuỗi. Theo định nghĩa 3, chúng tôi chỉ ghi nhận ca kiểm thử khi lượt xử lý thực sự tới luật đó. Khi một luật trước trả Permit, quá trình dừng. Với mỗi phép hội, bộ mẫu có đủ ba hàng chân trị cần cho cả hai điều kiện nguyên tử, cùng một lượt tới luật có kết quả lỗi do thiếu thuộc tính bắt buộc. Tổng cộng có **28/28 nghĩa vụ ảnh hưởng độc lập và 14/14 nghĩa vụ lỗi**. Hai yêu cầu có kết quả IDP cung cấp toàn bộ 14 chứng cứ lỗi. Các nghĩa vụ dùng chung yêu cầu nên không thể xem là 42 quan sát độc lập. [Luật và yêu cầu gốc](https://github.com/dianxiangxu/XPA/tree/89c000495d81a1a82ca8de2ab0fc73fecfc4e440/src/test/resources/org/seal/policies/conference3) · [Bảng chân trị và chứng cứ từng luật](result.json)

Phạm vi xác minh là các điều kiện áp dụng luật trong một policy tĩnh. Policy có target rỗng, các luật không có phần Condition riêng, luật cuối từ chối mặc định. Mã tái lập xử lý đúng cấu trúc của fixture đã ghim. Điểm số phát hiện lỗi của PolicyTrace ở cùng ngân sách oracle vẫn chưa được đo. Trước khi dùng XPA làm đối chứng thực nghiệm, cần chạy trực tiếp bộ sinh với bộ giải tương thích, kiểm tra ngân sách cả các yêu cầu trùng và chi phí xử lý lịch sử, rồi đối chiếu thêm các cấu trúc khác nếu chúng nằm trong phạm vi tuyên bố. Khảo sát mã ở commit tháng 10/2018 không xác lập phiên bản nhị phân chính xác đã dùng cho các bảng trong bài tháng 6/2018.

## Tái lập

Dùng bản checkout sạch của XPA tại commit trên. Dữ liệu nguồn và mã Java được lấy trực tiếp từ repository tác giả. Thư mục này chỉ chứa mã đo, mã xác minh và các quyết định cùng bảng chân trị suy ra. Chạy trong thư mục này với Python 3 và Node.js.

```bash
git clone https://github.com/dianxiangxu/XPA "$XPA"
git -C "$XPA" checkout --detach 89c000495d81a1a82ca8de2ab0fc73fecfc4e440
python3 replay.py "$XPA" > reproduced.json
cmp result.json reproduced.json
node --check verify.mjs
node verify.mjs reproduced.json
```
