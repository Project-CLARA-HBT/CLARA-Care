# 04-PLAN: GLHS SOTA UPGRADE

**Tài liệu:** Kế Hoạch Triển Khai Thực Nghiệm & Lộ Trình Nâng Cấp GLHS v2 (SOTA Edition)  
**Dự án:** CLARA-Care (Branch: `codex/commitloop-phase-a`)  
**Ngày lập:** Tháng 8/2026  

---

## 1. LỘ TRÌNH TRIỂN KHAI THEO GIAI ĐOẠN (5-PHASE EXECUTION ROADMAP)

```
                                      LỘ TRÌNH 5 GIAI ĐOẠN NÂNG CẤP GLHS
                                      
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ GIAI ĐOẠN 1: TÁI CẤU TRÚC KERNEL & PHÂN VÙNG PHIÊN BẢN ENTITY-PARTITIONED DAG                   │
  │ Mục tiêu: Triệt tiêu False-Stale Contention từ 93.75% xuống < 3.0% ở 16 writers                 │
  └────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                           │
                                           ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ GIAI ĐOẠN 2: HOÀN THIỆN THSS v2 TOPOLOGY & DUAL-LAYER RECONCILIATION                            │
  │ Mục tiêu: Xóa bỏ 530 lỗi INSUFFICIENT_EVIDENCE của Claude Sonnet, đạt trần chính xác 98-100%    │
  └────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                           │
                                           ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ GIAI ĐOẠN 3: KIỂM TOÁN ÁP LỰC ĐỒNG THỜI POSTGRESQL (16 ĐẾN 64 LUỒNG GHI)                        │
  │ Mục tiêu: Đo lường chính xác độ trễ p50/p95, thông lượng và khả năng mở rộng ACID               │
  └────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                           │
                                           ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ GIAI ĐOẠN 4: BENCHMARK ĐỐI ĐẦU 3 NHÁNH TRÊN 384 BỆNH NHÂN (HEAD-TO-HEAD EVALUATION)             │
  │ So sánh trực tiếp: Long-Context (Brute-force) vs BTSA (Prompt SOTA) vs GLHS v2 Full (Dual-Layer)│
  └────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                           │
                                           ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ GIAI ĐOẠN 5: ĐỒNG BỘ BẢN THẢO, THẨM ĐỊNH Y KHOA & XUẤT XƯỞNG BÀI BÁO                            │
  │ Mục tiêu: Phát hành trọn bộ 11 bài báo khoa học và công bố mã nguồn mở kèm bằng chứng niêm phong │
  └─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. NGUYÊN TẮC LIÊM CHÍNH KHOA HỌC BẤT BIẾN (SCIENTIFIC INTEGRITY PROTOCOLS)

Để bảo đảm tính khách quan, minh bạch và đáp ứng tiêu chuẩn khắt khe nhất của các hội nghị/tạp chí y khoa hàng đầu (IEEE, AMIA, Nature Digital Medicine):

1. **Đóng Băng & Niêm Phong Trước Thực Thi (Pre-Execution SHA-256 Freeze):**
   Mọi tập dữ liệu, mã nguồn đánh giá, prompt và nhãn gold PHẢI được tính mã băm SHA-256 và niêm phong trong tệp `seal.json` trước khi thực hiện bất kỳ lệnh gọi router/LLM nào.
2. **Nghiêm Cấm Thao Túng Benchmark Hậu Thực Nghiệm (No Post-Hoc Benchmark Tuning):**
   Tuyệt đối KHÔNG sửa đổi câu hỏi nghiên cứu, không điều chỉnh prompt hoặc sửa nhãn gold sau khi chạy nhằm mục đích ép kết quả cho thấy GLHS vượt trội.
3. **Bảo Toàn Đơn Vị Mẫu Thống Kê $N$ (Preservation of Scientific $N$):**
   Đơn vị thống kê $N$ là số lượng bệnh nhân độc lập hoặc số lượng lịch trình logic (logical schedules). Việc lặp lại thử nghiệm (repetitions/retries) để đo lường độ phân tán thời gian KHÔNG BAO GIỜ được tính là tăng kích thước mẫu $N$.
4. **Bảo Toàn Toàn Bộ Kết Quả Âm Lịch Sử (Preservation of Historical Null Results):**
   Mọi kết quả âm hoặc kết quả hòa (v5 384-subject null, GovRed final-003, GovMut W8 45-mutant) PHẢI được lưu trữ đầy đủ trong kho lưu trữ và thảo luận trung thực trong bài báo.
5. **Ghi Nhận Lỗi Fail-Closed Minh Bạch (Transparent Error Accounting):**
   Mọi lỗi định dạng từ mô hình (format error), timeout hoặc lỗi kết nối PHẢI được ghi vào sổ cái lỗi (`error_ledger.json`) và tính là lỗi của nhánh tương ứng, không được retry vô hạn để làm đẹp số liệu.

---

## 3. CHIẾN LƯỢC QUẢN LÝ RỦI RO & DỰ PHÒNG (RISK MANAGEMENT MATRIX)

| Rủi Ro Nhận Diện | Khả Năng | Tác Động | Biện Pháp Kiểm Soát & Giảm Thiểu | Kế Hoạch Dự Phòng (Rollback) |
| :--- | :---: | :---: | :--- | :--- |
| **Deadlock trong DAG Versioning** | Thấp | Cao | Sắp xếp thứ tự khóa các thực thể theo thứ tự từ điển (`alphabetical key sorting`) trước khi gọi `SELECT ... FOR UPDATE`. | Tự động timeout sau 3s và rollback giao dịch. |
| **API Provider Rate Limit (429/503)** | Trung bình | Vừa | Áp dụng Exponential Backoff với hệ số 1.5s và hàng đợi điều phối tốc độ (Token Bucket Rate Limiter). | Tạm dừng luồng và tự động khôi phục từ checkpoint `run_manifest.json`. |
| **Mất Dữ Liệu Chạy volatile** | Thấp | Cao | Ghi log từng cell thực thi theo định dạng append-only JSONL ngay khi nhận response (`flush_immediately=True`). | Khôi phục trực tiếp từ tệp JSONL mà không cần chạy lại từ đầu. |
| **Sai lệch Múi giờ Bitemporal** | Thấp | Cao | Cưỡng chế kiểm tra `assert dt.tzinfo == UTC` tại tầng Pydantic validator của API Gateway. | Chạy bộ test hồi quy `test_timezone_integrity.py`. |

---

## 4. CHIẾN LƯỢC ROLLBACK VÀ MIGRATION KHÔNG DOWNTIME (ZERO-DOWNTIME ROLLBACK)

1. **Quy trình Migration Cơ sở Dữ liệu (Alembic Upgrade/Downgrade):**
   * Migration `20260820_0001_glhs_entity_partition.py` được thiết kế theo nguyên tắc *Additive Schema*:
     * Tạo mới bảng `glhs_entity_version_partitions`.
     * Bổ sung cột nullable hoặc default an toàn trên các bảng hiện hữu.
     * Dữ liệu cũ được backfill tự động bằng script di chuyển dữ liệu.
   * Lệnh rollback luôn được kiểm thử trước: `alembic downgrade -1`.
2. **Cơ chế Triển khai Blue/Green:**
   * Container `api` và `ml` mới được khởi chạy trên cổng phụ (ví dụ: 8101, 8011) và vượt qua 100% bài kiểm tra sức khỏe (`/health`, `/health/details`) trước khi Nginx chuyển hướng lưu lượng chính thức.
