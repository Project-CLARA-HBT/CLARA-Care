# Dự báo doanh số thưa trên Monash Car Parts

Dừng cơ chế co phân phối doanh số theo tuổi kể từ lần bán gần nhất. Trên tám tháng development, tổng sai số tuyệt đối bằng **704**, hòa đối chứng phân nhóm tuổi không co và cao hơn **4,76%** so với cả dự báo 0 và boosting tối ưu cho cùng hàm loss. Ngưỡng đăng ký là giảm 10% trước từng đối chứng. UCI Online Retail vẫn giữ riêng. [Protocol](PROTOCOL.md)

Trong 2.048 cặp SKU–tháng, 1.880 có nhãn của 235 SKU, 168 thiếu nhãn, và 1.503 nhãn quan sát bằng 0. Số tháng chung hạn chế suy luận về thời gian. Hai arm có và không co đạt cùng tổng sai số trong từng tháng và từng nhóm tuổi. So với dự báo 0, phần tăng tập trung ở các nhóm có bán trên một nửa số tháng quan sát. Các phương pháp cổ điển như TSB dự báo trung bình, trong khi loss tuyệt đối ưu tiên trung vị. [Tám mốc và phiên bản thư viện](summary.json) · [Tổng theo từng nhóm](strata.json) · [Dữ liệu Monash Car Parts, CC BY 4.0](https://zenodo.org/records/4656022)

| Arm | Tổng sai số tuyệt đối |
|---|---:|
| Dự báo 0 / boosting | 672 / 672 |
| Phân nhóm theo tần suất | 674 |
| Phân nhóm tuổi không co / có co | 704 / 704 |
| Trung vị lịch sử | 785 |
| TSB / IMAPA / ADIDA / Croston-SBA | 968,12 / 981,76 / 990,75 / 1.192,46 |

Để tái lập trên CPU, dùng Python 3.12, các phiên bản trong summary.json, tệp ZIP có MD5 ghi trong đó và một luồng tính. Trình kiểm tra tính lại mọi tổng từ từng dự báo và xác minh cấu hình đã chọn trên tám tháng tuning. Bảng lỗi theo SKU được tạo trong scratch khi chạy lại. [Mã StatsForecast](https://github.com/Nixtla/statsforecast)

~~~bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python screen.py data.zip /tmp/car-parts-replay
python verify.py /tmp/car-parts-replay > /tmp/car-parts-strata.json
cmp /tmp/car-parts-strata.json strata.json
~~~
