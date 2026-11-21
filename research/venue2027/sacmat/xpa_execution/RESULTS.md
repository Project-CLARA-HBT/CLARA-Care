# Chạy bộ sinh MC/DC của XPA trên ví dụ hội nghị

Bộ sinh Java của nhóm tác giả tạo **25 yêu cầu** trên policy `conference3`. Cả 25 quyết định do Balana trả về khớp phép tính độc lập từ các điều kiện của luật. Có 14 Permit, 10 Deny và một Indeterminate{DP}. Chạy lại **27 yêu cầu tác giả lưu sẵn** bằng cùng Balana cho đúng toàn bộ nhãn công bố. Bộ sinh đã gọi đúng entry point mà GUI dùng khi chọn MC/DC có cả lỗi. [Mã tác giả](https://github.com/dianxiangxu/XPA/blob/89c000495d81a1a82ca8de2ab0fc73fecfc4e440/src/main/java/org/seal/xacml/gui/TestPanel.java#L250-L260) · [Bộ mẫu có nhãn](https://github.com/dianxiangxu/XPA/tree/89c000495d81a1a82ca8de2ab0fc73fecfc4e440/src/test/resources/org/seal/policies/conference3)

Trên mỗi lượt chạy, 25 yêu cầu khác nhau cả theo byte XML và theo tập thuộc tính đã chuẩn hóa. Sau khi tính khả năng đi tới từng luật, bộ mới thỏa 28/28 nghĩa vụ ảnh hưởng độc lập của từng điều kiện và 14/14 nghĩa vụ lỗi trong 14 target. Một yêu cầu lỗi làm chứng cho cả 14 target. Bộ đóng gói 27 yêu cầu đạt cùng mức bao phủ với hai yêu cầu lỗi. Hai bộ có cùng phạm vi MC/DC đo được trên ví dụ này; sự trùng khớp không thiết lập độ tương đương với mọi policy. Bài báo công bố tháng 6/2018, commit XPA là tháng 10/2018. [Định nghĩa 3 trong bài SACMAT 2018](https://par.nsf.gov/servlets/purl/10376453) · [Đối chiếu bộ đã công bố](../coverage_fidelity/RESULTS.md)

| Đơn vị quan sát trong mỗi lượt có gắn bộ đếm | Số lần |
|---|---:|
| Kiểm chuẩn trên yêu cầu đã công bố, nguyên policy | 27 |
| Solver Z3 khởi chạy khi sinh yêu cầu | 25 |
| Gọi TargetEvaluate để đánh giá target của luật trong khi sinh | 217 |
| Gọi ConditionEvaluate hoặc PolicyRunner.evaluate trong khi sinh | 0 |
| Đánh giá nguyên policy sau sinh | 25 |

Ba lượt có bộ đếm chạy trong ba JVM riêng và cho các số đếm như nhau. Lượt đầu không gắn bộ đếm cho cùng kết quả tổng hợp. Một số bảng chân trị theo từng yêu cầu thay đổi giữa các lượt do bộ sinh tạo giá trị và tên phụ trợ. Số 217 là số lần vào phương thức đánh giá target. Số 25 dưới cùng là chi phí chấm quyết định tất cả yêu cầu mới bằng Balana. Muốn so ngân sách với PolicyTrace, cần cấp cùng quyền truy cập các target và kê cả chi phí phản hồi trong lúc sinh, ngoài chi phí chấm quyết định đầu ra. Cả bốn lượt đều dùng một policy tĩnh, do đó chỉ có một đơn vị ngoại sinh. Phép so khả năng phát hiện lỗi xuyên lịch sử của PolicyTrace còn mở. [Bảng chân trị và nhãn lượt đầu](results/run1.json) · [Lượt có đếm 1](results/tallied1.json) · [Lượt 2](results/tallied2.json) · [Lượt 3](results/tallied3.json)

## Môi trường và tái lập

Máy WSL2 chạy CPU với OpenJDK 8u514, Maven 3.9.9 và Z3 4.8.7. XPA ghi gitlink Z3 `cfdde2f4d1d1286d2bfcaad7bf5c7be202b024ad`. Thí nghiệm dùng binary phát hành 4.8.7 có hỗ trợ `smt.string_solver=z3str3`, nên kết quả mô tả môi trường này. Build toàn dự án từ commit ghim thất bại vì giao diện bảng tính tham chiếu lớp Experiment mà tác giả đã xóa. Script cung cấp một khai báo trường chỉ cho compiler rồi loại lớp đó khỏi classpath chạy. Java biên dịch nguyên nguồn MC/DC và Balana trong repo. Không nạp giao diện hay AspectJ tracer. Agent đếm các lần vào ba phương thức đã nêu qua bytecode instrumentation. [Z3](https://github.com/Z3Prover/z3/releases/tag/z3-4.8.7) · [Bản sửa của tác giả đã bỏ Experiment](https://github.com/dianxiangxu/XPA/commit/b01c3429658797dd3be1b3754e15e76c7f3fe966)

Trong checkout tác giả, có giấy phép riêng dưới Z3-str và các header trong mã Balana. Không thấy tệp giấy phép cấp gốc cho toàn bộ XPA. Repo nghiên cứu này lưu wrapper và kết quả dẫn xuất. Mã Java, JAR MC/DC và XML nguồn được lấy trực tiếp từ repo tác giả theo revision.

| Archive đầu vào | SHA-256 |
|---|---|
| zulu8.98.0.201-ca-jdk8.0.514-linux_x64.tar.gz | 16a4c55c3061ee41e94edb109f5aea1c55a2952d37e25e215d478b8347350860 |
| apache-maven-3.9.9-bin.tar.gz | 7a9cdf674fc1703d6382f5f330b3d110ea1b512b51f1652846d9e4e8a588d766 |
| z3-4.8.7-x64-ubuntu-16.04.zip | fcde3273ba88e291fe93db4b9d39957274700caeebba8aefbae28796da0dc0b7 |

Gán XPA cho checkout sạch ở commit `89c000495d81a1a82ca8de2ab0fc73fecfc4e440`; đặt JAVA_HOME, MVN và Z3 thành đường dẫn tuyệt đối. Từ thư mục này, chạy trong thư mục trống mới. Dùng TALLY=0 để bỏ bộ đếm trong giai đoạn tạo và đánh giá yêu cầu. Lượt này vẫn đếm số tiến trình solver qua wrapper.

```bash
study="$PWD"
scratch=$(mktemp -d)
(cd "$scratch" && bash "$study/run.sh")
python3 evidence.py "$XPA" "$scratch" > "$scratch/report.json"
node --check verify.mjs
node verify.mjs results
```
