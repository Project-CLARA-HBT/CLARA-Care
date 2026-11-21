# Sàng lọc admission trên hai trace cache sản xuất

**Loại giả thuyết dùng mức tái sử dụng của namespace để quyết định admission lần đầu.** Ở dung lượng 1.024 đối tượng, chính sách này làm tăng số miss 1,89% so với đối chứng đơn giản nhất đạt kết quả tốt nhất ở cluster 17 và 4,61% so với S3-FIFO ở cluster 52. Nó thua S3-FIFO ở cả hai điểm chính. Biên cải thiện đã đặt trước là giảm 5% trên cả hai cluster.

## Số miss trên mọi cấu hình

| Cluster | Dung lượng (đối tượng) | LRU | SIEVE | S3-FIFO | LFU | W-TinyLFU | Chỉ nhận khóa gần đây¹ | Có thêm namespace |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 256 | 63.857 | 53.534 | 53.458 | 56.151 | 53.854 | **52.548** | 53.069 |
| 17 | 1.024 | 48.665 | 41.040 | 39.593 | 42.951 | 39.818 | **39.234** | 39.974 |
| 17 | 4.096 | 31.495 | 27.659 | **26.444** | 27.659 | 27.625 | 26.569 | 27.247 |
| 52 | 256 | 56.939 | 56.043 | **55.974** | 63.005 | 58.076 | 56.154 | 56.335 |
| 52 | 1.024 | 46.913 | 47.404 | **46.232** | 56.561 | 49.957 | 48.886 | 48.365 |
| 52 | 4.096 | 37.970 | 38.216 | **37.111** | 46.854 | 41.963 | 41.812 | 40.083 |

¹ Hai cột cuối cùng dùng SIEVE để lưu đối tượng và giữ thêm lịch sử bốn lần dung lượng. Đối chứng chỉ nhận khóa đã xuất hiện trong lịch sử này. Cột cuối có thể nhận thêm khóa thuộc namespace có tỷ lệ tái sử dụng cao hơn tỷ lệ chung tính đến thời điểm ra quyết định. Cả hai đều phục vụ mọi resident hit.

Sau warmup, mẫu có 79.731 lượt đọc ở cluster 17 và 73.773 lượt ở cluster 52. Ở dung lượng 1.024, SIEVE và S3-FIFO cùng bỏ lỡ 20.916 và 16.085 lần truy cập tới khóa từng xuất hiện. Tín hiệu namespace cứu được 521 miss so với đối chứng cùng lịch sử ở cluster 52 nhưng làm tăng 740 miss ở cluster 17. Việc quan sát thấy nhiều miss lặp lại chưa chỉ ra cách định trước khóa nào đáng giữ.

## Phạm vi

Nguồn là trace Twitter tháng 3/2020 từ kho Carnegie Mellon, do tác giả nghiên cứu OSDI phát hành theo CC BY 4.0. Cluster 17 và 52 thuộc cùng một nhà vận hành. Các cửa sổ 100.000 dòng lần lượt chỉ kéo dài 138 và 6 giây. Mọi arm nhận cùng thứ tự đọc và cùng dung lượng đối tượng đơn vị. Kết quả không đo byte miss, tỷ lệ hit sản xuất, tác động invalidate/TTL, throughput hay chi phí vật lý của metadata. Ký tự phân cách namespace có thể thay đổi theo ứng dụng. Sau khi phương pháp không đạt biên, nghiên cứu kết thúc ở development. [Dữ liệu, khuyến nghị chọn cluster và giấy phép](https://github.com/twitter/cache-trace/tree/1c503676d6972d4394a360e09162149a6c00f516) · [Trace OSDI](https://www.usenix.org/conference/osdi20/presentation/yang) · [SIEVE, NSDI 2024](https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo) · [S3-FIFO, SOSP 2023](https://s3fifo.com/)

## Tái hiện

Chạy từ thư mục này với Python có libcachesim 0.3.5 và zstandard 0.25.0. Hai file đầu vào chỉ chứa 4 MiB đầu của mỗi tệp nén. Mỗi lần chạy đọc đúng 100.000 dòng nguyên vẹn sau giải nén. Mã băm hai loại dữ liệu, số thao tác đã bỏ và số miss lần đầu nằm trong results.json. Kiểm tra LRU đối chiếu từng quyết định của thư viện với OrderedDict trên toàn bộ sáu cấu hình.

```sh
mkdir -p /tmp/cache-admission
for n in 17 52; do
  curl --fail --location --range 0-4194303 --max-filesize 4194304 \
    "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/open_source/cluster${n}.sort.zst" \
    --output "/tmp/cache-admission/cluster${n}.zst"
done
python replay.py /tmp/cache-admission > /tmp/cache-replay.json && cmp results.json /tmp/cache-replay.json
python admission.py /tmp/cache-admission > /tmp/cache-probe.json && cmp admission.json /tmp/cache-probe.json
```
