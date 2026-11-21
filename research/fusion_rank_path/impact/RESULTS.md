# Lưới trọng số bỏ sót hai tài liệu liên quan trên NanoSCIDOCS

Trong 417 cặp truy vấn–tài liệu có nhãn dương, 245 cặp lọt vào top 10 ở ít nhất một trọng số. Lưới 11 điểm cách đều tìm thấy 243 cặp. Cả hai cặp bị bỏ sót thuộc NanoSCIDOCS, xuất hiện trong hai truy vấn khác nhau. Các khoảng tương ứng chứa 2.166 và 3.094 trọng số, chiếm 3,31% và 4,72% miền. Lưới 21 và 101 điểm tìm thấy đủ 245 cặp và chạm đủ cả 249 khoảng liên tục có tài liệu trong top 10. [Hai khoảng bị bỏ qua và hai đầu mút](results/missed_intervals.csv)

**Thấy đủ tài liệu vẫn có thể bỏ qua thứ hạng tốt nhất.** Khi chọn trọng số riêng cho từng truy vấn bằng nhãn của chính nó, lưới 11 điểm cho giá trị nDCG@10 tối đa thấp hơn ở 12/150 truy vấn. Mức giảm lớn nhất là 0,11285 trên NanoSCIDOCS. Lưới 21 điểm còn 8/150 truy vấn bị giảm. Lưới 101 điểm còn 1/150, giảm 0,00776. Khi chọn một trọng số chung trên 50 truy vấn của mỗi nguồn, mức giảm lớn nhất giữa ba nguồn lần lượt là 0,00907, 0,00891 và 0,00196. Các giá trị này đo sai số xấp xỉ của phép khảo sát hồi cứu sử dụng nhãn. Đánh giá khả năng học trọng số để triển khai cần truy vấn hoặc nguồn giữ riêng. [Đủ 450 hàng truy vấn–lưới](results/queries.csv)

| Nguồn | Điểm lưới | Truy vấn giảm khi chọn riêng / 50 | Giảm trung bình khi chọn riêng | nDCG tốt nhất với một trọng số chung, lưới | nDCG tốt nhất với một trọng số chung, toàn miền | Chênh lệch |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NanoArguAna | 11 | 2 | 0,00175 | 0,64438 | 0,65345 | 0,00907 |
| NanoArguAna | 21 | 1 | 0,00088 | 0,64454 | 0,65345 | 0,00891 |
| NanoArguAna | 101 | 0 | 0 | 0,65345 | 0,65345 | 0 |
| NanoFiQA2018 | 11 | 6 | 0,00280 | 0,51191 | 0,51681 | 0,00490 |
| NanoFiQA2018 | 21 | 3 | 0,00088 | 0,51219 | 0,51681 | 0,00461 |
| NanoFiQA2018 | 101 | 0 | 0 | 0,51635 | 0,51681 | 0,00045 |
| NanoSCIDOCS | 11 | 4 | 0,00272 | 0,43435 | 0,44229 | 0,00795 |
| NanoSCIDOCS | 21 | 4 | 0,00272 | 0,43777 | 0,44229 | 0,00453 |
| NanoSCIDOCS | 101 | 1 | 0,00016 | 0,44033 | 0,44229 | 0,00196 |

Trên NanoFiQA2018, lưới 101 điểm đạt cực đại riêng của từng truy vấn. Mỗi truy vấn có thể đạt cực đại ở một vị trí khác. Điều đó giải thích vì sao bài toán chọn một trọng số chung vẫn có chênh lệch. Việc quét chính xác phát hiện được một số trường hợp riêng mà lưới thưa bỏ qua, trong khi lưới 101 điểm đã gần giá trị trung bình tốt nhất trên cả ba nguồn. Kết quả hiện tại chưa xác lập ưu thế truy hồi hay độ mới của thuật toán. [Tổng hợp, trọng số tối ưu và số khoảng từng nguồn](results/summary.csv)

## Tái lập và phạm vi

Từ thư mục này, chạy các lệnh sau với NumPy và Node.js 20+. Python khai triển đường hạng trên cả miền và lưu kết quả vào thư mục mới. Chương trình JavaScript tính lại trực tiếp ở các điểm đổi hạng và từng trọng số lưới bằng một cách làm tròn số nguyên độc lập. Đã kiểm tra cả 450 hàng, hai khoảng bị bỏ sót và chín hàng tổng hợp. WSL2 chạy phần khai triển trên CPU. Hai phép tổng hợp này cùng dùng một đầu vào đã được kiểm tra độc lập trước đó trên 27.328.512 hạng. [Kiểm tra đầu vào](../results/verification.json) · [Phép đo đã khóa](PROTOCOL.md)

```sh
python measure.py ../results/changes.tsv replay
node --check verify.mjs
node verify.mjs ../results/changes.tsv replay
diff -r results replay
```

Các truy vấn và nhãn trong NanoArguAna, NanoFiQA2018 và NanoSCIDOCS do Zeta Alpha công bố theo CC BY 4.0. Phân tích chuyển chúng thành đường hạng cho BM25 và MiniLM trên ba tập con, dùng miền điểm 16 bit và quy tắc hòa của nghiên cứu. Chỉ các tài liệu có nhãn dương được tính vào tử số. Độ bao phủ nhãn giới hạn suy luận về mức liên quan thực của các tài liệu khác. Tất cả số liệu là development trên ba nguồn đã khảo sát. [Nguồn ghim và checksum](../../retrieval_disagreement/sources.json) · [Ghi công và biến đổi tập dữ liệu](../../retrieval_disagreement/RESULTS.md) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
