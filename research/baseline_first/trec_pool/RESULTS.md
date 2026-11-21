# Chấm lại 143 run TREC-COVID khi bổ sung nhãn cho corpus vòng 1

**Rút đề xuất bài về độ ổn định thứ hạng khi pool được mở rộng.** Có đủ dữ liệu ngoài để kiểm tra câu hỏi. NIST đã công bố cùng thiết kế trên các run này với hai lần bổ sung phán xét. Lần chấm dưới đây theo dõi tới đợt nhãn cuối cùng của corpus vòng 1. Hệ đứng đầu vẫn giữ vị trí theo cả hai chỉ số. Chưa có phương pháp mới thể hiện ưu thế, hoặc tập kiểm định độc lập cho phương pháp đó. [Báo cáo của Voorhees ngày 25/5](https://ir.nist.gov/trec-covid/papers/halfround.pdf) · [Báo cáo ngày 25/6](https://ir.nist.gov/trec-covid/papers/rnd1runs_j0.5-2.0.pdf)

Kho NIST cho phép tải đủ **143 submission file**. Các hệ tìm trên cùng danh sách **51.070 docid** và **30 topic** của tháng 4/2020. Mỗi tệp run được chấm nguyên vẹn hai lần bằng trec_eval 9.0.8. Hai bộ nhãn lần lượt là cumulative vòng 1 và chronological dành cho chính corpus vòng 1. Trường thời gian trong qrels ghi đợt đánh giá. Corpus, tập topic và quy tắc gửi run thực sự thay đổi *giữa* các vòng thi, nên điểm trong bảng chỉ so sánh cùng những submission vòng 1. [Danh sách submission](https://ir.nist.gov/trec-covid/archive/archive-round1.html) · [NIST giải thích các bộ qrels](https://ir.nist.gov/trec-covid/data.html) · [Protocol](PROTOCOL.md)

**Trong 8.691 nhãn ban đầu, có hai cặp mang điểm 0 với docid nằm ngoài danh sách hợp lệ.** Cả hai biến mất khỏi bộ chronological. 8.689 cặp chung giữ nguyên điểm. Có 12.856 cặp mới, gồm 10.285 điểm 0, 1.567 điểm 1 và 1.004 điểm 2. Bộ sau có 21.545 cặp. Chúng tôi giữ nguyên tệp NIST khi tính điểm. Các cặp chưa được chấm ở cả hai thời điểm vẫn thiếu nhãn. [Số đếm và SHA-256](summary.json)

| Chỉ số | Giữ thứ tự | Đảo thứ tự | Chỉ hòa ban đầu | Chỉ hòa về sau | Hòa cả hai | Kendall τ-b |
|---|---:|---:|---:|---:|---:|---:|
| Mean nDCG@10 | 9.903 | 242 | 1 | 1 | 6 | 0,9522 |
| P@5 | 9.669 | 305 | 85 | 63 | 31 | 0,9319 |

Mẫu số ở mỗi dòng là 10.153 cặp trong 143 run. Thứ tự dùng điểm tổng hợp với bốn chữ số thập phân do trec_eval xuất. Các cặp phụ thuộc nhau vì có chung run, nhóm tác giả và topic. Run đứng đầu nDCG@10 là `run1` ở cả hai lần (0,6844 → 0,6921). Với P@5, `xj4wang_run1` đứng đầu ở cả hai (0,8333). Việc đảo một số cặp cũng đã được NIST mô tả ở các đợt trước; chấm muộn hơn kéo dài phép tái lập. Với BBGhelani1, điểm nDCG@10 ban đầu 0,6689 và P@5 ban đầu 0,8200 khớp báo cáo tác giả. [Đủ điểm của mọi run](runs.csv) · [Phiếu điểm chính thức BBGhelani1](https://ir.nist.gov/trec-covid/archive/round1/BBGhelani1.pdf)

## Tái lập

Từ thư mục này, chọn thư mục scratch cho dữ liệu tải về, cài Python với `requests`, `beautifulsoup4`, cùng make, trình biên dịch C và Node.js. Chỉ số dẫn xuất và digest được lưu trong repo. Bản đánh giá thứ hai dùng nhãn do NIST đưa về cùng frame vòng 1. Cả hai lần đều là development.

```bash
CACHE="$(mktemp -d)"
curl -fsSL https://codeload.github.com/usnistgov/trec_eval/tar.gz/refs/tags/v9.0.8 -o "$CACHE/tool.tar.gz"
echo "c3994a73103ec842e12df693749584a45814c35c36dcc15f38984bd463566ba1  $CACHE/tool.tar.gz" | sha256sum -c -
tar xzf "$CACHE/tool.tar.gz" -C "$CACHE"
make -s -C "$CACHE/trec_eval-9.0.8"
python replay.py "$CACHE/raw" "$CACHE/trec_eval-9.0.8/trec_eval" "$CACHE/out"
cmp "$CACHE/out/runs.csv" runs.csv
cmp "$CACHE/out/summary.json" summary.json
node --check verify.mjs
node verify.mjs "$CACHE/raw" "$CACHE/out"
```
