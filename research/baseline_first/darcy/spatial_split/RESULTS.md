# Ranh giới quan sát giải thích một phần khác biệt giữa hai bộ nội suy

Dùng stencil vật liệu ở phần trong và boosting trên hàng/cột cuối đạt kết quả sau. Các sai số là relative L2 trung bình trên mọi nút thiếu. Cả hai mô hình đều được fit trên cùng trường. Các quyết định gán vùng được đưa ra sau khi đã xem lỗi theo vùng ở bốn cohort. Đây là một quy tắc có thể triển khai với kết quả development hậu nghiệm.

| Cohort | Stencil | Boosting | Ghép theo vùng | Mức giảm lỗi so với thành phần đơn tốt hơn |
|---|---:|---:|---:|---:|
| NeuralOperator, 128 trường | 0,017217 | 0,018195 | 0,017218 | −0,01% |
| PDEInvBench 241, 64 trường | 0,004048 | 0,004471 | 0,003945 | 2,56% |
| PDEBench beta=1, 64 trường | 0,008988 | 0,008298 | 0,007512 | 9,48% |
| PhysicsNeMo, 128 trường mới từ bộ sinh | 0,015074 | 0,016392 | 0,014461 | 4,07% |

Ở PDEBench, lỗi tăng ban đầu của stencil có thể đảo chiều khi dùng boosting ở vùng phải ngoại suy. Trên NeuralOperator, phép ghép thua sát stencil đơn. Không cohort nào vượt 10% trước cả hai thành phần. Phép ghép ngược cho kết quả kém hơn phép ghép đã chọn ở cả bốn cohort. Bốn cohort gồm hai archive thuộc dòng dữ liệu FNO. Cách ghép có hai mô hình nên chi phí huấn luyện và triển khai cần đo riêng.

~~~bash
python study.py /tmp /tmp/clara-pdeinv241 /tmp/clara-pdebench133219 /tmp/darcy-region-replay
diff fields.csv /tmp/darcy-region-replay/fields.csv
~~~
