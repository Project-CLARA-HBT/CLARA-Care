# Stencil bốn đỉnh thua boosting trên PDEBench beta=1

Trên cùng 64 trường PDEBench training giữ riêng để chấm development sau khi fit lại bằng 128 trường đầu, histogram boosting đạt lỗi **0,008298**, thấp hơn stencil theo mẫu bốn đỉnh ở **0,008988**. Lỗi của stencil cao hơn 8,32% (bootstrap 95% theo trường từ 0,18% đến 17,35%, 29 thắng và 35 thua). So với đối chứng chỉ đếm số đỉnh, stencil giảm lỗi 2,13% (1,41–2,88%, 49 thắng, 1 hòa và 14 thua).

| Arm | Relative L2 vùng thiếu | Phần trong | Mép |
|---|---:|---:|---:|
| Ridge chung | 0,011108 | 0,008098 | 0,081529 |
| Đếm số đỉnh | 0,009184 | 0,006541 | 0,067527 |
| Mẫu bốn đỉnh | 0,008988 | 0,006336 | 0,066690 |
| Boosting cùng đặc trưng | 0,008298 | 0,007258 | 0,039530 |
| CNN áp suất | 0,013058 | 0,010722 | 0,068310 |
| CNN áp suất và vật liệu | 0,012116 | 0,010469 | 0,059220 |

File 2D_DarcyFlow_beta1.0_Train.hdf5 có 10.000 trường. Đã đối chiếu MD5 của toàn file với bản phát hành. Có hai giá trị vật liệu là 0,1 và 1,0; trong 192 trường đầu, một trường đồng nhất. Quy tắc đã sửa trước khi fit để giữ trường đó, sau lần dừng kiểm tra schema ban đầu. Cả 192 mảng áp suất và 192 mặt nạ vật liệu ở kích thước 32×32 đều khác nhau trong từng loại; không có áp suất toàn 0. Mỗi arm giữ đúng các nút đã quan sát. CNN áp suất và CNN thêm vật liệu chọn epoch 124 và 137 bằng 16 trường validation nội bộ. Mỗi mô hình chỉ dùng một seed. Các kết quả chỉ nói về phục hồi nút thiếu từ áp suất và hệ số thô của file phát hành, chưa đo trường vật lý khi không quan sát áp suất thô. [Bộ PDEBench](https://doi.org/10.18419/DARUS-2986)

~~~bash
mkdir -p /tmp/clara-pdebench133219
curl -fL --retry 3 https://darus.uni-stuttgart.de/api/access/datafile/133219 -o /tmp/clara-pdebench133219/data.h5
python screen.py /tmp/clara-pdebench133219/data.h5 .
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ../pdeinv241/score.py /tmp/clara-pdebench133219 /tmp/pdebench-scores
diff fields.csv /tmp/pdebench-scores/fields.csv
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ../conv_control/study.py /tmp/clara-pdebench133219 --fit-size 128 --train-size 112 --count 192 --epochs 140 --output /tmp/pdebench-cnn
diff cnn/fields.csv /tmp/pdebench-cnn/fields.csv
~~~
