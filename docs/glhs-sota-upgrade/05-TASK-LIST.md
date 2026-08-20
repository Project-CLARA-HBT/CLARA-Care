# 05-TASK-LIST: GLHS SOTA UPGRADE

**Tài liệu:** Danh Sách Nhiệm Vụ Kỹ Thuật Chi Tiết (Granular Task Breakdown & DoD)  
**Dự án:** CLARA-Care (Branch: `codex/commitloop-phase-a`)  
**Ngày lập:** Tháng 8/2026  

---

## MA TRẬN NHIỆM VỤ THEO GIAI ĐOẠN (ENGINEERING TASKS BREAKDOWN)

### GIAI ĐOẠN 1: TÁI CẤU TRÚC KERNEL & PHÂN VÙNG PHIÊN BẢN ENTITY-PARTITIONED DAG

* [ ] **TASK-1.1: Tạo Alembic Migration cho Bảng Phân Vùng Thực Thể**
  * **File:** `services/api/alembic/versions/20260820_0001_glhs_entity_partition.py`
  * **Mô tả:** Khởi tạo bảng `glhs_entity_version_partitions` với composite index `(profile_id, domain, semantic_key)` và khóa duy nhất.
  * **Tiêu chí Hoàn thành (DoD):** Chạy `alembic upgrade head` và `alembic downgrade -1` thành công không lỗi trên PostgreSQL 16.
  * **Lệnh kiểm thử:** `cd services/api && pytest tests/test_glhs_foundation_migration.py`

* [ ] **TASK-1.2: Triển khai DAG Lock Manager & Cập nhật `apply_commitment_transition`**
  * **File:** `services/api/src/clara_api/glhs/commitment_gateway.py`
  * **Mô tả:** Thay thế khóa toàn cục `PhrProfile` bằng việc khóa có thứ tự các phân vùng thực thể trong `dependencies` bằng `SELECT ... FOR UPDATE`.
  * **DoD:** Loại bỏ hoàn toàn đụng độ false-stale giữa các domain độc lập.
  * **Lệnh kiểm thử:** `pytest services/api/tests/test_commitloop_gateway.py`

* [ ] **TASK-1.3: Cưỡng chế Chuẩn Hóa UTC Toàn Diện Trên Toàn Bộ Gateway**
  * **File:** `services/api/src/clara_api/glhs/commitment_gateway.py`, `gateway.py`, `commitment_reconciliation.py`
  * **Mô tả:** Bọc toàn bộ các tham số thời gian (`known_at`, `valid_at`, `due_time`) qua hàm `_utc()`, từ chối dứt khoát naive datetime.
  * **DoD:** 100% test cases về datetime pass trên PostgreSQL 16.

* [ ] **TASK-1.4: Loại Bỏ Hoàn Toàn Constructor `base_version_only` Nội Bộ**
  * **File:** `services/api/src/clara_api/glhs/commitment_gateway.py`
  * **Mô tả:** Xóa bỏ constructor không an toàn, bắt buộc mọi hàm tạo proposal phải nhận `GlhsInferenceContextBinding`.
  * **DoD:** Không còn bất kỳ đường dẫn nào cho phép commit thiếu snapshot binding.

---

### GIAI ĐOẠN 2: HOÀN THIỆN THSS v2 TOPOLOGY & DUAL-LAYER RECONCILIATION

* [ ] **TASK-2.1: Triển khai Cấu Trúc THSS v2 Kèm Phân Định Vai Trò Thực Thể**
  * **File:** `services/api/src/clara_api/glhs/commitment_thss.py`, `evaluation/commitloop/production_context.py`
  * **Mô tả:** Bổ sung `minimal_evidence.roles` (`anchor`, `contradiction`, `target_match`, `context_prior`) và `fact_coverage`.
  * **DoD:** Cấu trúc THSS v2 tương thích hoàn toàn với Pydantic schema `glhs_v2_full_reconciled`.
  * **Lệnh kiểm thử:** `pytest evaluation/commitloop/tests/test_production_context_v7.py`

* [ ] **TASK-2.2: Thiết Lập Header Khung Thế Giới Đóng (Closed-World Framing)**
  * **File:** `evaluation/commitloop/prompts/reconciliation_system_prompt.txt`, `services/ml/src/clara_ml/agents/`
  * **Mô tả:** Bổ sung chỉ dẫn tường minh cho LLM rằng ngữ cảnh đã được tinh gọn có chủ đích bởi GST Gate, triệt tiêu phản xạ bảo thủ `INSUFFICIENT_EVIDENCE`.
  * **DoD:** Tỷ lệ dự đoán `INSUFFICIENT_EVIDENCE` trên các ca có đầy đủ anchor giảm về 0%.

* [ ] **TASK-2.3: Tối Ưu Hóa Lazy Dispatch Cho Bộ Tạo Solver Packet**
  * **File:** `evaluation/commitloop/solver_packets.py`
  * **Mô tả:** Chuyển đổi cơ chế dựng context từ eager sang lazy dispatch table theo đúng điều kiện được yêu cầu.
  * **DoD:** Giảm 85% thời gian khởi tạo packet khi chạy các nhánh baseline đơn lẻ.
  * **Lệnh kiểm thử:** `pytest evaluation/commitloop/tests/test_solver_packets.py`

---

### GIAI ĐOẠN 3: KIỂM TOÁN ÁP LỰC ĐỒNG THỜI POSTGRESQL (CONCURRENCY STRESS-TESTING)

* [ ] **TASK-3.1: Xây Dựng Harness Kiểm Thử Áp Lực 16–64 Writers**
  * **File:** `evaluation/glhs_postgres_toctou/concurrency_stress_harness.py`
  * **Mô tả:** Tự động sinh tải với 16, 32, 64 luồng ghi đồng thời trên PostgreSQL 16 thật, đo lường tỷ lệ True-Stale vs False-Stale.
  * **DoD:** False-Stale rate ở 16 writers $< 3.0\%$ (so với mức cũ 93.75%).

* [ ] **TASK-3.2: Đo Lường & Niêm Phong Bảng Benchmark Hiệu Năng Dịch Vụ**
  * **File:** `research/glhs_journal/service_overhead_v2/`
  * **Mô tả:** Đo lường chính xác p50, p95, p99 và ops/sec cho 7 thao tác chính của GLHS (GST transition, state reconstruction, THSS compilation, v.v.).
  * **DoD:** Tạo tệp `metrics.json` và `checksums.sha256` được ký điện tử.

---

### GIAI ĐOẠN 4: BENCHMARK ĐỐI ĐẦU 3 NHÁNH TRÊN 384 BỆNH NHÂN (HEAD-TO-HEAD EVALUATION)

* [ ] **TASK-4.1: Đóng Băng Tập Dữ Liệu & Niêm Phong Giao Thức Mới**
  * **File:** `protocols/commitloop/v7-confirmatory-sota/`
  * **Mô tả:** Khởi tạo bộ freeze độc lập cho cohort 384 bệnh nhân, ghi nhận SHA-256 mã nguồn và nhãn gold vào `freeze_manifest.json`.
  * **DoD:** Không thay đổi bất kỳ tệp tin nào trong các thư mục freeze lịch sử (v5, v6).

* [ ] **TASK-4.2: Thực Thi Benchmark Đối Đầu Trực Tiếp 3 Nhánh**
  * **Mô tả:** Chạy song song trên router với 2 mô hình (Gemini 3.6 Flash High & Claude Sonnet 4.6):
    * Nhánh A: Long-Context Chronological (Brute-force baseline).
    * Nhánh B: BTSA (Prompt SOTA comparator).
    * Nhánh C: GLHS v2 Full (Dual-Layer Deterministic State Barrier).
  * **DoD:** 100% cell hoàn tất, ghi nhận sổ cái lỗi minh bạch, không retry lạm phát.

* [ ] **TASK-4.3: Tính Toán Phân Tích Thống Kê & Paired Exact McNemar**
  * **File:** `evaluation/commitloop/statistics.py`
  * **Mô tả:** Tính toán kiểm định dấu chính xác (Exact Sign Test), Holm adjustment, Paired Risk Difference và Bootstrap 95% CI.
  * **DoD:** Xuất tệp `statistical_results.json` có chữ ký niêm phong.

---

### GIAI ĐOẠN 5: ĐỒNG BỘ BẢN THẢO, THẨM ĐỊNH Y KHOA & XUẤT XƯỞNG BÀI BÁO

* [ ] **TASK-5.1: Đồng Bộ Số Liệu Mới Vào 11 Bản Thảo Tiếng Anh & Tiếng Việt**
  * **File:** `CLARA_R3_RepoAudit_MasterSpec_WordingFixed_2026-08-19/SOURCE_SUBMISSION/`, `SOURCE_VIETNAMESE/`
  * **Mô tả:** Cập nhật bảng kết quả, phân tích thảo luận về Dual-Layer Architecture và Entity DAG Locking.
  * **DoD:** Toàn bộ số liệu trong text khớp 100% với `statistical_results.json`.

* [ ] **TASK-5.2: Tổ Chức Hội Đồng Thẩm Định Y Khoa Cho GovRed & GovMut**
  * **Mô tả:** Thu thập biên bản thẩm định mù từ chuyên gia y khoa độc lập cho 30 ca holdout GovRed và 11 mutant W9 của GovMut.
  * **DoD:** Chuyển trạng thái các cổng kiểm soát từ `MANUAL_GATE` sang `VERIFIED`.

* [ ] **TASK-5.3: Biên Dịch Trọn Bộ 22 Bản PDF Cuối Cùng & Xác Minh SHA-256**
  * **Mô tả:** Biên dịch toàn bộ 11 PDF nộp bài và 11 PDF companion tiếng Việt, sinh tệp `SHA256SUMS.txt` niêm phong cuối cùng.
  * **DoD:** 22/22 PDF biên dịch thành công, không lỗi layout/overflow, khớp checksum 100%.
