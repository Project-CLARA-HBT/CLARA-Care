# ĐẶC TẢ KỸ THUẬT VÀ KẾ HOẠCH NÂNG CẤP TOÀN DIỆN CHUẨN A* (MASTER A* SPECIFICATION & AUDIT IMPLEMENTATION)

**Dựa trên tài liệu phản biện chuyên gia:** `GLHS5.txt`  
**Mục tiêu:** Nâng cấp toàn diện hệ thống CLARA-Care và bộ 22 bản thảo (11 EN + 11 VI) để vượt qua ngưỡng Borderline Reject $\to$ **Strong Accept tại Hội nghị A* / Tạp chí Q1 (ACM SOSP / USENIX OSDI / ACM SIGMOD / IEEE JBHI)**.

---

## 1. PHÂN TÍCH YÊU CẦU & ĐỊNH HƯỚNG TÁI CẤU TRÚC (DEEP-DIVE ANALYSIS)

### 1.1. Triệt Tiêu Các Tuyên Bố Ngụy Biện Về Thuật Toán Đồng Thời (De-escalate & Reframe Concurrency)
- **Vấn đề chỉ ra trong review:** Việc tự đặt tên "Định tuyến Phiên bản DAG Phân vùng Thực thể" (Entity-Partitioned DAG Versioning) như một phát minh thuật toán mới trong năm 2026 làm suy giảm uy tín học thuật.
- **Giải pháp chuẩn A*:**
  - Định vị lại: Hệ thống ứng dụng **Kiểm soát Đồng thời Lạc quan (Kung-Robinson OCC, 1981)** cấp độ hàng theo trật tự từ điển nghiêm ngặt ($\prec_{\text{lex}}$) kết hợp **Giao thức Wound-Wait (Rosenkrantz et al., 1978)** để ngăn chặn hiện tượng nghẽn khóa và suy thoái hiệu năng (**Thrashing - Thomasian, 1998**) vốn là nhược điểm chí mạng của hệ thống khóa nguyên khối (Monolithic Locking).
  - Tích hợp đại số thời gian kép của **Snodgrass (1995)**.

### 1.2. Thiết Lập Đường Cơ Sở Đối Sánh Chuẩn Mực (Symmetrical SOTA Baselines)
- **Vấn đề:** Bỏ các baseline không có cam kết ACID (Vanilla RAG, MemGPT không có rào chắn).
- **Giải pháp:**
  - So sánh đối đầu trực diện với:
    1. **FHIR REST Conditional Update (ETag / If-Match)** theo chuẩn HL7 quốc tế.
    2. **MemTX / MemTxn (Li et al. / Cui et al., 2026):** Transactional belief commit & snapshot isolation.
    3. **CommitGuard (Santos-Grueiro, 2026):** Commit-time authorization boundaries.
    4. **Provenact (Peng & Wu, 2026):** Stateful governance in multi-agent environments.
    5. **GLHS v2 (Công trình này):** Dual-Layer State Barrier + Merkle-bound cryptographic leases.

### 1.3. Tái Cấu Trúc Chứng Minh Toán Học (Replace Tautological Theorem 3 with Formal Cryptographic Non-Forgeability)
- **Vấn đề:** Định lý 3 cũ (tính đúng đắn của code Python/PostgreSQL tất định) là hằng đúng (tautology).
- **Giải pháp:**
  - Thay thế hoàn toàn bằng **Định lý 3 Mới: Tính Kháng Giả Mạo và Ràng Buộc Trạng Thái Mật Mã (Cryptographic Non-Forgeability & Bounded-Commit Security Theorem)**:
    - Định nghĩa mô hình an toàn mật mã IND-CCA / EUF-CMA cho bản chụp Merkle THSS.
    - Chứng minh toán học rằng một kẻ tấn công đối kháng hoặc một mô hình LLM trôi dạt ngữ nghĩa không thể sinh ra một đề xuất GST $P$ hợp lệ cho thời điểm $t_2$ bằng cách tái sử dụng bản chụp $id_H$ được cấp tại $t_1$ nếu phân vùng thực thể cơ sở hoặc chính sách đồng thuận đã bị thay đổi:
      $$\Pr\left[\operatorname{GST\_Commit}(P, t_2) = \text{True} \;\middle|\; V(e_k)_{t_2} > v_s(e_k) \lor \Sigma_{t_2} \neq \Sigma_{t_1}\right] \le \operatorname{negl}(\lambda)$$

### 1.4. Mở Rộng Bối Cảnh Tổng Quan Tài Liệu (4-Boundary Agent Transaction Mapping)
- **Ánh xạ 4 Ranh giới Ủy quyền tại Thời điểm Ghi (Santos-Grueiro, 2026):**
  1. *Ranh giới Độ mới (Freshness Boundary):* Kiểm tra tính hợp lệ thời gian hiệu lực và thời gian giao dịch ($\tau_{\text{valid}} \cap \tau_{\text{txn}}$).
  2. *Ranh giới Ưu tiên Nhân quả (Causal Precedence Boundary):* Kiểm tra phiên bản phụ thuộc cơ sở ($V(e_k) == v_s(e_k)$).
  3. *Ranh giới Ràng buộc Hiệu ứng (Effect Scoping Boundary):* Khóa phân vùng thực thể Entity DAG leases.
  4. *Ranh giới Đủ điều kiện Ghi (Admissibility Boundary):* Rào chắn Tầng 1 (Tương tác thuốc DDI, đồng thuận và chính sách).

### 1.5. Đánh Giá Trên Dữ Liệu Bệnh Án Thế Giới Thực (Real-World EHR MIMIC-IV Notes)
- Bổ sung pipeline đánh giá trên **MIMIC-IV Discharge Summaries & Progress Notes** để chứng minh khả năng hạn chế ảo giác và phân xử mâu thuẫn thời gian trên dữ liệu lâm sàng lộn xộn, thực tế.

---

## 2. KẾ HOẠCH TRIỂN KHAI THEO TỪNG PHASE VỚI 10-20 SUBAGENTS

### Phase 1: Tạo Đặc Tả & Khởi Tạo Môi Trường Đồng Thời (Current)
### Phase 2: Triển Khai Mã Nguồn, Thuật Toán & Kiểm Thử Benchmark (Batch 1: 10 Subagents)
### Phase 3: Nâng Cấp Toàn Diện 22 Bài Báo LaTeX (Batch 2: 10 Subagents)
### Phase 4: Biên Dịch VPS, Niêm Phong Checksum & Triển Khai Production (Batch 3)
