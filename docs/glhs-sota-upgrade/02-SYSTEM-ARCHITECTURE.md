# 02-SYSTEM-ARCHITECTURE: GLHS SOTA UPGRADE

**Tài liệu:** Thiết Kế Kiến Trúc Hệ Thống Toàn Diện GLHS v2 (SOTA Edition)  
**Dự án:** CLARA-Care (Branch: `codex/commitloop-phase-a`)  
**Ngày lập:** Tháng 8/2026  

---

## 1. TỔNG QUAN KIẾN TRÚC PHÂN TÁN (END-TO-END SYSTEM TOPOLOGY)

Kiến trúc tổng thể của CLARA-Care được tổ chức theo mô hình phân tầng chặt chẽ với ranh giới an toàn y tế bất biến:

```
                                      CLARA-CARE DISTRIBUTED TOPOLOGY
                                      
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ 1. PRESENTATION TIER                                                                            │
  │    Next.js 15 Web App (SSR/React 18)   │   Flutter Mobile Client (Dart)   │   Clinical Admin Portal │
  └────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                           │ HTTPS (Strict Transport Security / CSRF Double-Submit)
                                           ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ 2. API GATEWAY & GOVERNANCE CORE (services/api - FastAPI / Python 3.11+)                        │
  │    ├── Auth & Session Management (JWT / Session Cookies / RBAC Engine)                         │
  │    ├── Dynamic Medical Consent Enforcement & Audit Sink                                         │
  │    ├── Task-Bounded Snapshot (THSS) Compiler & Merkle Digest Generator                          │
  │    ├── Entity-Partitioned Version Coordinator (DAG Lock Manager)                                │
  │    └── Governed State Transition (GST) Kernel & DB Persistence Gate                            │
  └────────────────────────────┬───────────────────────────────────────┬────────────────────────────┘
                               │ PostgreSQL Wire Protocol              │ X-ML-Internal-Key (gRPC/HTTP)
                               ▼                                       ▼
  ┌─────────────────────────────────────────────────┐ ┌─────────────────────────────────────────────┐
  │ 3. PERSISTENCE & AUDIT TIER (PostgreSQL 16)     │ │ 4. REASONING & SIDECAR TIER (services/ml)   │
  │    ├── Bitemporal Health Ledger (t_v, t_k)      │ │    ├── CareGuard & FIDES Safety Guardrails  │
  │    ├── Entity Partition Versions (DAG Nodes)    │ │    ├── Council Multi-Agent System           │
  │    ├── Immutable Lineage Bindings (Merkle Roots)│ │    ├── Scribe Audio ASR Transcription Sidecar│
  │    └── Write-Ahead Log (WAL / Synchronous Commit│ │    └── LLM Runtime (Gemini 3.6 / Claude 4.6)│
  └─────────────────────────────────────────────────┘ └─────────────────────────────────────────────┘
```

---

## 2. KIẾN TRÚC RÀO CẢN TRẠNG THÁI HAI TẦNG (DUAL-LAYER STATE BARRIER)

Để khắc phục nhược điểm của các hệ thống dựa hoàn toàn vào Prompt Engineering (như BTSA) hoặc chỉ dựa vào Auth Check (như CommitGuard), GLHS v2 thiết lập cơ chế phân tách ranh giới hai tầng rõ rệt:

```
                              DUAL-LAYER STATE BARRIER ARCHITECTURE
                              
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ TẦNG 1: ĐỘNG CƠ XÁC MINH TẤT ĐỊNH (DETERMINISTIC RECONCILIATION KERNEL)                         │
  │ (Thực thi bằng Python & PostgreSQL trong API Gateway - Không phụ thuộc LLM)                     │
  │                                                                                                 │
  │ 1. So khớp mã thực thể y tế (LOINC / SNOMED / RxNorm)                                          │
  │ 2. Lọc thời gian hai chiều: valid_at <= valid_cutoff VÀ known_at <= known_cutoff               │
  │ 3. Tính toán cửa sổ hoàn thành: due_time + grace_period                                         │
  │ 4. Nhận diện mâu thuẫn nguồn (Contradiction Detection) -> Gán cờ CONFLICTED / ESCALATE          │
  │ 5. Đóng gói Role-Annotated Context & Gắn nhãn Closed-World Frame                                │
  └────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                           │ Snapshot THSS v2 có cấu trúc + Gợi ý tất định (Hints)
                                           ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ TẦNG 2: MÔ HÌNH LÝ LUẬN NGỮ NGHĨA LÂM SÀNG (EPISTEMIC CLINICAL ARBITER - LLM)                   │
  │ (Thực thi tại services/ml qua Router)                                                           │
  │                                                                                                 │
  │ 1. Đọc hiểu diễn giải lâm sàng từ các triệu chứng bệnh nhân tự báo cáo                           │
  │ 2. Phân tích ngữ cảnh điều trị đa bệnh lý phức tạp (Comorbidity Nuances)                        │
  │ 3. Đề xuất kế hoạch chăm sóc cá nhân hóa (Proposal Delta: \Delta)                               │
  │ 4. Tuyệt đối KHÔNG tự tính toán phép toán thời gian (đã được Tầng 1 bảo đảm)                    │
  └────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                           │ Đề xuất có chữ ký dòng dõi: P = <u, a, r, phi, tau, Delta, BindingToken>
                                           ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ CỔNG GIAO DỊCH GST (GOVERNED STATE TRANSITION GATE)                                             │
  │ Re-check toàn bộ Tầng 1 và Tầng 2 trước khi ghi xuống cơ sở dữ liệu PostgreSQL                 │
  └─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. PHÂN VÙNG PHIÊN BẢN THEO ĐỒ THỊ THỰC THỂ (ENTITY-PARTITIONED VERSIONING DAG)

### 3.1. Mô hình Toán học (Mathematical Formulation)
Thay vì sử dụng một counter đơn điệu toàn cục `PhrProfile.state_version` (gây ra tỷ lệ False-Stale 93.75%), GLHS v2 mô hình hóa trạng thái hồ sơ của bệnh nhân $u$ dưới dạng một **Đồ thị có hướng không chu trình (DAG)** của các phân vùng thực thể:

$$S_u = \{ e_1, e_2, \dots, e_n \}$$

Mỗi thực thể $e_i$ được định danh duy nhất bởi bộ ba:
$$\text{Key}(e_i) = \langle \text{profile\_id}, \text{domain}, \text{semantic\_key} \rangle$$
với một vector phiên bản cục bộ:
$$V(e_i) = \langle v_{\text{state}}, v_{\text{policy}}, v_{\text{consent}} \rangle$$

Một giao dịch đề xuất $T_k$ khai báo tập phụ thuộc ngữ nghĩa:
$$\text{Deps}(T_k) = \{ \text{target\_key} \} \cup \{ \text{dependency\_keys} \}$$

### 3.2. Thuật toán Khóa & Kiểm tra Tuần tự (Serializability Proof)
1. **Khóa Hàng Phân Vùng:** Tại thời điểm GST commit, hệ thống chỉ chiếm khóa `SELECT ... FOR UPDATE` trên các hàng tương ứng với $\text{Deps}(T_k)$ trong bảng `glhs_entity_version_partitions`:
   $$\forall k \in \text{Deps}(T_k): \quad \text{AcquireLock}(u, k)$$
2. **Kiểm tra Điều kiện Phiên bản (Version Predicate):**
   $$\forall k \in \text{Deps}(T_k): \quad V_{\text{current}}(u, k) == V_{\text{expected\_in\_proposal}}(u, k)$$
3. **Tiến hóa Trạng thái Cục bộ:**
   Chỉ các phân vùng trong $\text{Deps}(T_k)$ được tăng counter phiên bản $v_{\text{state}} \leftarrow v_{\text{state}} + 1$. Các phân vùng độc lập khác (ví dụ: quan sát nhịp tim không phụ thuộc đơn thuốc hạ huyết áp) giữ nguyên phiên bản.

**Kết quả lý thuyết:** Giảm xác suất đụng độ khóa (Contention Probability) từ $\mathcal{O}(W^2)$ trên toàn bộ hồ sơ xuống $\mathcal{O}\left(\frac{W^2}{M}\right)$ với $M$ là số lượng phân vùng thực thể độc lập. Ở $M \ge 10$, tỷ lệ False-Stale ở 16 writers giảm từ **93.75% xuống < 2.5%**.

---

## 4. CHUỖI DÒNG DÕI MẬT MÃ ĐẦU-CUỐI (CRYPTOGRAPHIC MERKLE LINEAGE PIPELINE)

```
                            CẤU TRÚC MERKLE TREE CỦA INFERENCE BINDING
                            
                                  [Root Merkle Digest (SHA-256)]
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
           [Snapshot & Evidence Hash]                             [Governance & Task Hash]
                     │                                                     │
          ┌──────────┴──────────┐                               ┌──────────┴──────────┐
          ▼                     ▼                               ▼                     ▼
    [THSS Snapshot]      [Evidence Merkle]              [Policy & Consent]       [Model & Scope]
    - snapshot_id        - evidence_ids                 - policy_version         - model_manifest_id
    - manifest_digest    - evidence_hashes              - consent_version        - actor_role / task
```

### 4.1. Quy trình Đóng dấu & Xác thực
1. **Giai đoạn Đọc (Read Path):**
   Khi người dùng hoặc hệ thống kích hoạt suy luận, API Gateway tạo `GlhsSnapshotManifest`, tính toán cây Merkle và lưu vào bảng `glhs_inference_context_bindings` với trạng thái `ACTIVE`. Mã `binding_id` được nhúng vào metadata trả về cho LLM/UI.
2. **Giai đoạn Đề xuất (Proposal Path):**
   Khi mô hình hoặc bác sĩ gửi đề xuất can thiệp, payload bắt buộc phải mang `binding_id`. Hệ thống kiểm tra sự tồn tại và tính hợp lệ của binding token trước khi tạo `GlhsClinicalCommitmentProposal`.
3. **Giai đoạn Ghi (Write Path):**
   Tại cổng GST, sau khi khóa hàng phân vùng, hệ thống re-read trực tiếp `GlhsInferenceContextBinding` từ DB:
   * Đối chiếu `root_proposal_id` để ngăn chặn việc rửa nguồn qua các bước trung gian.
   * Xác nhận thời hạn hợp lệ `expires_at > datetime.now(UTC)`.
   * So sánh hash của consent hiện tại với `consent_version` trong binding.

---

## 5. VÒNG ĐỜI GIAO DỊCH VÀ MÁY TRẠNG THÁI (TRANSACTION LIFECYCLE & STATE MACHINE)

```
                                  VÒNG ĐỜI GIAO DỊCH TOÀN VẸN CỦA GLHS
                                  
   (Client Request)
          │
          ▼
   [1. THSS Compilation] ──(Biên dịch Snapshot + Gắn nhãn vai trò Role Annotation)
          │
          ▼
   [2. Binding Creation] ──(Lưu Merkle Binding vào DB + Cấp Binding Token)
          │
          ▼
   [3. Model Inference]  ──(LLM phân tích ngữ nghĩa lâm sàng)
          │
          ▼
   [4. Proposal Created] ──(Tạo đề xuất mang Binding Token)
          │
          ▼
   [5. Human / AI Review]──(Duyệt đề xuất - Bảo toàn Root Lineage)
          │
          ▼
   [6. GST Commit Gate]  ──(Khóa phân vùng DAG + Re-read DB + Kiểm tra 4 điều kiện)
          │
     ┌────┴───────────────────────────┐
     ▼                                ▼
 (Thành Công)                     (Thất Bại: Stale / Revoked / Tampered)
     │                                │
     ▼                                ▼
[7. State Advanced & Committed]   [8. Atomic Rollback & Error Logged]
```

### Bảng Trạng thái Chuyển tiếp (State Transition Table)

| Trạng thái Hiện tại | Sự kiện / Hành động | Điều kiện Tiên quyết | Trạng thái Tiếp theo | Hành động Kèm theo |
| :--- | :--- | :--- | :--- | :--- |
| **NONE** | Khởi tạo Snapshot | Scope hợp lệ, Consent còn hiệu lực | **DISCLOSED** | Ghi Snapshot Manifest & Binding |
| **DISCLOSED** | Gửi Đề xuất ($P$) | Mang đúng `binding_id` còn hạn | **PROPOSED** | Tạo Proposal liên kết Binding |
| **PROPOSED** | Thẩm định (Review) | Người duyệt có quyền, không đổi gốc | **REVIEWED** | Cập nhật review state, giữ Binding |
| **REVIEWED** | GST Commit | Khớp phiên bản DAG, Consent & Policy hợp lệ | **COMMITTED** | Ghi Transition, tăng DAG version |
| **BẤT KỲ** | Vi phạm bất biến | Phát hiện stale, mismatch, expired, revoked | **ABORTED** | Rollback tức thì, ghi Audit Log |
