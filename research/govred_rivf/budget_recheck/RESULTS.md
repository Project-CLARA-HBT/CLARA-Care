# GovMut hòa một lịch chạy đối chứng ở ngân sách 233 giây

Trên 45 mutant W8, bộ kiểm thử kết hợp M3 và lịch chạy lần lượt các bộ kiểm thử thành phần phát hiện **cùng 20 mutant** ở mức trần 233 giây cho mỗi mutant. Tổng thời gian pytest tính vào ngân sách là 5.023,96 giây cho M3 và 2.564,52 giây cho đối chứng. Đối chứng dùng ít hơn 48,95% thời gian, nhanh hơn ở 44/45 mutant. Các con số được tái dựng từ nhật ký thực thi đã niêm phong. **Loại tuyên bố M3 vượt mọi đối chứng ở cùng ngân sách trên W8.** [Thiết kế phân tích](PROTOCOL.md) · [Thời gian, số lần gọi hoàn tất và trạng thái từng ca](results/mutants.csv)

| Ngân sách cho mỗi ca (s) | M0 hồi quy | M1 thuộc tính | M2 máy trạng thái | M3 kết hợp | Đối chứng chạy lần lượt | Chỉ M3 / chỉ đối chứng |
|---|---:|---:|---:|---:|---:|---:|
| 29,125 | 15 | 4 | 2 | 9 | 16 | 0 / 7 |
| 58,25 | 16 | 4 | 2 | 17 | 18 | 0 / 1 |
| 116,5 | 16 | 4 | 5 | 18 | 19 | 0 / 1 |
| 233 | 16 | 4 | 6 | 20 | 20 | 0 / 0 |

Tại 233 giây, cả bốn mutant M3 phát hiện thêm so với M0 đều được lịch chạy lần lượt phát hiện. Lịch này chạy M0 một lần, sau đó xen kẽ M1 và M2 theo từng seed đã chốt. M3 chạy lại bộ kết hợp cho mỗi seed cho đến khi phát hiện lỗi hoặc hết ngân sách. Phân tích tính cả thời gian tiêu vào lần gọi cuối nếu chạm trần, và tính kết quả bắt lỗi khi tiến trình pytest hoàn tất. M3 chạm trần ở ba ca, đối chứng ở 0 ca. W8 chưa đo trực tiếp lịch chạy xen kẽ như một chiến dịch riêng. Việc tái dựng dựa trên giả định thời gian và kết quả của từng tiến trình đã ghi vẫn áp dụng khi đổi thứ tự chạy. [Mọi phép so sánh từng cặp](results/summary.csv)

**Giới hạn của đồng hồ.** Trong runner W8, thời điểm bắt đầu tính nằm sau bước dựng thư mục tạm, áp dụng thay đổi và kiểm tra import. Có thời lượng từng tiến trình pytest, còn thời gian chuẩn bị, dọn thư mục và thời điểm từng assertion bên trong tiến trình chưa được ghi. Nếu cho phép chi phí ngoài pytest không âm, tùy ý và khác nhau giữa lần gọi, hiệu số số ca phát hiện M3 trừ đối chứng dưới trần đầu-cuối 233 giây nằm trong khoảng **[−20, +20]**. Hai đầu mút đạt được trong mô hình này khi chi phí chuẩn bị của riêng một chiến lược vượt trần ở tất cả các ca nó có thể bắt, còn chiến lược kia có chi phí bằng 0. Đây là giới hạn nhận diện cho hai lịch chạy trên W8. Nó không ước lượng chi phí thật hoặc hiệu quả ở W9. [Vị trí bắt đầu tính thời gian](../../../evaluation/property_assurance/mutation_runner.py)

**Kiểm tra nguồn.** Đối chiếu 720 lần gọi với bản niêm phong, hash của mã mutant trước/sau, danh sách và hash các tệp test của từng phương pháp, kết quả tiến trình và hash hai luồng đầu ra. Các lần gọi ghi nhận 12 revision Git, gồm 59/720 lần ở revision trong manifest. Các tệp test mục tiêu đều khớp, song revision của toàn bộ checkout thay đổi trong quá trình chạy. Mẫu gồm 45 mutant chọn có chủ đích, từ một hệ thống. Ngân sách 233 giây lấy từ hiệu chuẩn W9 riêng biệt và được áp hồi cứu ở đây. Chưa có phép đo end-to-end ghép cặp trên tập ngoài độc lập. [Phân bố revision](results/revision_counts.json) · [Hiệu chuẩn gốc](../../assurance_soict/budget_fair_design.md)

## Tái lập

Chạy từ thư mục gốc repo với Python 3.11+ và Node. Thư mục đầu ra phải mới. Lượt tái lập trên CPU WSL2 khớp từng byte với cả ba tệp kết quả. Trình kiểm tra JavaScript tính riêng tổng tích lũy theo seed, nhận diện lần gọi có mã thoát 1 và đối chiếu đủ 900 kết quả và 20 hàng tổng hợp.

```sh
study=research/govred_rivf/budget_recheck
src=research/assurance_soict
python "$study/replay.py" "$src" "$OUT"
node --check "$study/verify.mjs"
node "$study/verify.mjs" "$src/seal/govmut-soict-2026-final_run-v2" "$OUT"
diff -r "$study/results" "$OUT"
```
