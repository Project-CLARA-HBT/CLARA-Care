# 01-AUDIT-AND-REQUIREMENTS: GLHS SOTA UPGRADE

**Tài liệu:** Báo cáo Kiểm toán Chuyên sâu & Đặc tả Yêu cầu Hệ thống GLHS v2 (SOTA Edition)  
**Dự án:** CLARA-Care (Branch: `codex/commitloop-phase-a`)  
**Ngày lập:** Tháng 8/2026  
**Tiêu chuẩn:** IEEE 830 / ISO/IEC/IEEE 29148 / ISO 25010 Software Quality Standards  

---

## 1. KHẢO SÁT CHUYÊN SÂU CÁC CÔNG TRÌNH NGHIÊN CỨU LIÊN QUAN (LITERATURE DEEP-DIVE & NOVELTY MATRIX)

### 1.1. Bối cảnh Khoa học (State-of-the-Art Landscape 2024–2026)
Hệ thống AI Y tế hoạt động trên hồ sơ sức khỏe theo chiều dọc (Longitudinal Health AI) đòi hỏi sự kết hợp chặt chẽ giữa tính toàn vẹn thời gian, quản trị quyền riêng tư và an toàn giao dịch. Các nghiên cứu gần đây đã phân chia không gian này thành các nhánh chuyên biệt:

1. **Nhóm Bộ nhớ AI Giao dịch (Transactional Agent Memory):**
   * **MemTX (VLDB 2025/2026):** Giới thiệu mô hình bộ nhớ giao dịch phân tán cho AI Agents, hỗ trợ ACID trên bộ nhớ ngắn hạn/dài hạn thông qua snapshot isolation. Tuy nhiên, MemTX không có khái niệm về *thời gian hai chiều y tế (bitemporal health time)* và *đồng thuận bệnh nhân động (dynamic consent)*.
   * **MemTxn & MemClaw (arXiv 2026):** Mở rộng các giao dịch bộ nhớ phân tán với khả năng rollback khi AI đưa ra quyết định sai. Hạn chế: xem mọi dữ liệu bộ nhớ là phi cấu trúc, thiếu cơ chế xác minh vị từ lâm sàng (clinical predicate validation).
   * **Cordon (arXiv 2026):** Thiết lập ranh giới giao dịch ngữ nghĩa (semantic transaction boundary) để phân lập các hiệu ứng không thể đảo ngược (irreversible actions). Cordon chỉ chặn ở tầng thực thi hành động, không giải quyết vấn đề trôi dạt ngữ cảnh giữa lúc đọc và ghi.
   * **TOKI (arXiv 2026):** Định nghĩa tính đúng đắn thời gian hai chiều (valid time vs knowledge time) cho bộ nhớ AI. Tuy nhiên, TOKI không gắn kết ngữ cảnh suy luận của LLM vào điều kiện ghi dữ liệu của cơ sở dữ liệu.
   * **CommitGuard (USENIX Security 2026):** Kiểm tra tính hợp lệ của bằng chứng thẩm quyền (authority witness) tại thời điểm commit. Điểm mù: chỉ kiểm tra quyền hạn (authorization), không kiểm tra xem nội dung bệnh án thực tế mà AI đã đọc có bị thay đổi hay không.
   * **Provenact (ACM CCS 2026):** Đề xuất tính khả tuần tự của trạng thái chính sách (policy-state serializability), đảm bảo chính sách bảo mật không bị thay đổi trong quá trình thực thi đa tác tử. Hạn chế: chỉ áp dụng cho chính sách bảo mật máy tính, không hỗ trợ logic y tế lâm sàng và chuỗi bằng chứng FHIR.

2. **Nhóm AI Y tế & Phân xử Hồ sơ Sức khỏe (Health-AI & Longitudinal EHR Arbitration):**
   * **BTSA (Bitemporal State Arbitration - Zhao et al., 2026):** Dùng prompt kỹ thuật để yêu cầu LLM phân xử các quan sát mâu thuẫn theo thời gian hai chiều. Nhược điểm chí mạng: dựa hoàn toàn vào khả năng suy luận của LLM (dễ bị ảo giác, tính toán thời gian không ổn định, chi phí token cực lớn khi context dài).
   * **VitalTrace (2026) & DualStream (2026):** Tái tạo dòng sự kiện y tế theo thời gian thực từ nhiều nguồn không đồng bộ. Thiếu: cơ chế khóa và kiểm tra điều kiện ghi bền vững (persistent write-admission contract).
   * **openEHR Archetypes & W3C PROV:** Cung cấp mô hình thông tin chuẩn và chuỗi dòng dõi (lineage), nhưng là các tiêu chuẩn lưu trữ thụ động, không có cơ chế chủ động kiểm soát vòng đời suy luận AI trong thời gian thực.
   * **HL7 FHIR (R4 / R5 / STU3):** Cung cấp các tài nguyên `Provenance`, `Consent`, `CarePlan`, `ServiceRequest`. FHIR định nghĩa cấu trúc dữ liệu nhưng không quy định hợp đồng giao dịch bitemporal giữa AI Gateway và LLM Reasoner.

### 1.2. Ma trận So sánh & Định vị Tính Độc đáo của GLHS (Novelty Matrix)

| Tiêu chí / Cơ chế | MemTX (2025) | CommitGuard (2026) | Provenact (2026) | BTSA (2026) | openEHR / FHIR | **GLHS (CLARA-Care)** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bitemporal Reconstruction ($t_v, t_k$)** | ❌ | ❌ | ❌ | ⚠️ (Chỉ Prompt) | ⚠️ (Metadata) | **✅ (PostgreSQL Native)** |
| **Dynamic Consent Gating** | ❌ | ⚠️ (Static RBAC) | ⚠️ (Policy Engine)| ❌ | ✅ (FHIR Consent) | **✅ (Versioned Gate)** |
| **Deterministic Clinical Predicates** | ❌ | ❌ | ❌ | ❌ (LLM Prompt) | ❌ | **✅ (Python/DB Kernel)** |
| **Co-versioned Disclosure-to-Commit** | ❌ | ❌ | ⚠️ (Policy Only) | ❌ | ❌ | **✅ (THSS $\to$ GST Binding)** |
| **Anti-Laundering Lineage Merkle Token** | ❌ | ⚠️ (Witness Hash) | ❌ | ❌ | ⚠️ (Provenance) | **✅ (Immutable ORM Binding)**|
| **TOCTOU Race Detection in DB** | ⚠️ (MVCC) | ⚠️ (Auth Check) | ✅ (Serializability)| ❌ | ❌ | **✅ (Post-Lock Re-read)** |
| **Entity-Scoped Low Contention** | ⚠️ | ❌ | ⚠️ | N/A | N/A | **✅ (DAG Key Versioning)** |

---

## 2. KẾT QUẢ KIỂM TOÁN MÃ NGUỒN HIỆN TẠI (COMPREHENSIVE CODEBASE AUDIT)

Sau khi kiểm toán chi tiết mã nguồn tại `services/api/src/clara_api/glhs/`, `evaluation/commitloop/`, và `services/ml/`:

```
                               DANH MỤC LỖI & ĐIỂM NGHẼN HỆ THỐNG
                               
  ┌─────────────────────────────────┐     ┌─────────────────────────────────┐
  │ 1. PROFILE-GLOBAL LOCKING       │     │ 2. OVER-MINIMIZATION & MISMATCH │
  │    - Khóa toàn cục PhrProfile   │     │    - Claude 4.6 đoán sai 530 ca │
  │    - False-stale 93.75% ở 16 wt │     │    - Thiếu Role Metadata & Frame│
  └─────────────────────────────────┘     └─────────────────────────────────┘
                   │                                       │
                   ▼                                       ▼
  ┌─────────────────────────────────┐     ┌─────────────────────────────────┐
  │ 3. BASE-VERSION-ONLY BYPASS     │     │ 4. TIMEZONE NORMALIZATION LEAK  │
  │    - Constructor nội bộ bỏ qua  │     │    - Naive datetime lọt vào DB  │
  │      bắt buộc Snapshot ID       │     │    - SQLite vs PostgreSQL drift │
  └─────────────────────────────────┘     └─────────────────────────────────┘
```

### 2.1. Điểm nghẽn Tranh chấp Khóa Toàn cục (Profile-Global Lock Contention)
* **Vị trí mã:** `services/api/src/clara_api/glhs/commitment_gateway.py` (`_lock_profile_state`, `apply_commitment_transition`).
* **Cơ chế:** Giao dịch khóa toàn bộ bản ghi `PhrProfile` bằng `SELECT ... FOR UPDATE` và tăng `PhrProfile.state_version` (1 counter duy nhất cho toàn bộ bệnh nhân).
* **Hậu quả:** Khi 16 luồng cùng ghi nhận các quan sát khác nhau (ví dụ: cập nhật Huyết áp, Đường huyết, Nhịp tim, Dị ứng), 15 luồng bị coi là "Stale" dù không hề có xung đột về mặt ngữ nghĩa lâm sàng. Tỷ lệ False-Stale lên tới **93.75%**.

### 2.2. Xung đột Giả định Thế giới Đóng & Cắt tỉa Quá mức (Over-Minimization Bias)
* **Vị trí mã:** `evaluation/commitloop/production_context.py` (`_compact_solver_context`).
* **Hiện tượng:** Claude Sonnet 4.6 chỉ đạt 45.36% trên `glhs_hybrid_thss_strict` do đưa ra 530 lần dự đoán `INSUFFICIENT_EVIDENCE`.
* **Nguyên nhân:** Bản tin THSS cắt bỏ toàn bộ các quan sát lâm sàng nền, chỉ để lại duy nhất dòng `ServiceRequest`. Mô hình lý luận cao cấp suy diễn rằng "dữ liệu bị mất mát trong đường truyền" và chọn giải pháp an toàn là từ chối kết luận. Bản tin không có cờ xác nhận *Closed-World Sufficiency Frame* và không có nhãn vai trò `role: anchor` / `role: contradiction`.

### 2.3. Lỗ hổng Hạ cấp Dòng dõi Nội bộ (Base-Version-Only Bypass Vector)
* **Vị trí mã:** `services/api/src/clara_api/glhs/commitment_gateway.py` (`propose_commitment_transition`).
* **Nguy cơ:** Mặc dù endpoint API công khai đã bắt buộc `snapshot_id`, trong nội bộ service vẫn tồn tại overload cho phép tạo proposal chỉ với `base_state_version`. Nếu một module nội bộ (như Background Batch Job hoặc Council Agent) gọi nhầm hàm này, giao dịch sẽ được commit mà không có bằng chứng snapshot ràng buộc.

### 2.4. Rò rỉ Chuẩn hóa Múi giờ (Timezone Normalization Drift)
* **Vị trí mã:** `services/api/src/clara_api/glhs/commitment_gateway.py` và `gateway.py`.
* **Hiện tượng:** Một số hàm chấp nhận đối tượng `datetime` dạng naive (không có `tzinfo=UTC`). Trong SQLite in-memory, chuỗi ISO string được so sánh tự do, nhưng khi chạy trên PostgreSQL (`TIMESTAMPTZ`), các so sánh thời gian gây ra ngoại lệ hoặc lọc nhầm bản ghi lịch sử trong `reconstruct_commitments`.

---

## 3. ĐẶC TẢ YÊU CẦU HỆ THỐNG GLHS v2 (SYSTEM REQUIREMENTS SPECIFICATION)

### 3.1. Yêu cầu Chức năng (Functional Requirements - FR)

* **FR-01: Tái tạo Lịch sử Thời gian Hai chiều (Bitemporal Reconstruction):**
  Hệ thống PHẢI có khả năng tái tạo trạng thái hồ sơ bệnh nhân tại bất kỳ cặp mốc thời gian nào: Thời gian hiệu lực y tế ($t_v \le \text{valid\_cutoff}$) và Thời gian hệ thống ghi nhận ($t_k \le \text{known\_cutoff}$). Mọi dữ liệu đến muộn có $t_k > \text{known\_cutoff}$ tuyệt đối KHÔNG được xuất hiện trong snapshot.

* **FR-02: Đóng gói Snapshot THSS Có Cấu trúc & Vai trò (Role-Annotated THSS Compilation):**
  Snapshot THSS PHẢI chứa:
  1. `snapshot_id` (UUIDv4) và `manifest_digest` (SHA-256 theo chuẩn `clara.canonical-json.v1`).
  2. Bảng phân định vai trò tường minh (`minimal_evidence.roles`): `anchor`, `contradiction`, `target_match`, `context_prior`.
  3. Cờ xác thực khung thế giới đóng: `closed_world_frame: true`.
  4. Mốc thời gian hiệu lực thực tế (`state_effective_at`) và đồng hồ độ tươi (`freshness_clock`).

* **FR-03: Ràng buộc Dòng dõi Bất biến (Immutable Inference Context Binding):**
  Mọi đề xuất can thiệp y tế ($P$) do mô hình hoặc chuyên gia tạo ra PHẢI được liên kết vĩnh viễn với bản ghi `GlhsInferenceContextBinding`. Bản ghi này lưu trữ băm Merkle của: `[snapshot_id, manifest_digest, evidence_ids_hash, policy_version, consent_version, actor_role, purpose, task]`.

* **FR-04: Cổng Xác thực Trạng thái Quản trị (Governed State Transition - GST Gate):**
  Tại thời điểm Commit, GST PHẢI thực hiện kiểm tra đồng thời 4 điều kiện:
  $$\operatorname{Commit}(P) \Leftrightarrow \operatorname{Bound}(P, H) \land \operatorname{StateCurrent}(P) \land \operatorname{GovernanceCurrent}(P) \land \operatorname{SnapshotValid}(P)$$
  Nếu bất kỳ điều kiện nào thất bại, giao dịch PHẢI bị hủy bỏ (Rollback) và ghi log lỗi có cấu trúc.

* **FR-05: Động cơ Đối soát Vị từ Tất định (Deterministic Predicate Reconciliation Engine):**
  Tất cả các phép kiểm tra logic lâm sàng (so sánh mã LOINC/SNOMED, kiểm tra khoảng giá trị xét nghiệm, tính toán hạn hoàn thành $due\_time + grace\_period$) PHẢI được thực thi 100% bằng mã Python/PostgreSQL tất định (`commitment_reconciliation.py`). LLM KHÔNG ĐƯỢC PHÉP tự tính toán số học thời gian.

* **FR-06: Phân vùng Khóa Thực thể (Entity-Partitioned Versioning):**
  Hệ thống PHẢI hỗ trợ kiểm tra phiên bản ở cấp độ `(profile_id, domain, semantic_key)`. Giao dịch ghi chỉ khóa và tăng phiên bản của các thực thể liên quan, không làm ảnh hưởng đến các thực thể độc lập khác của cùng một bệnh nhân.

* **FR-07: Cơ chế Chống Rửa Nguồn (Lineage Anti-Laundering):**
  Khi một proposal chuyển qua nhiều bước duyệt hoặc ủy quyền, hệ thống PHẢI truy vết ngược về root proposal ban đầu. Không một bước trung gian nào được phép gỡ bỏ `inference_context_binding_id`.

* **FR-08: Rút Consent Tức thời (Instant Consent Revocation Fast-Path):**
  Khi bệnh nhân rút consent cho một mục đích ($\phi$) hoặc đối tượng ($a$), mọi snapshot THSS chưa commit thuộc consent đó PHẢI bị vô hiệu hóa ngay lập tức tại cổng GST.

### 3.2. Yêu cầu Phi chức năng & Hiệu năng (Non-Functional Requirements - NFR)

* **NFR-01 (Độ trễ - Latency):** Thời gian thực thi cổng GST (bao gồm khóa hàng, re-read DB và ghi transition) PHẢI đạt $\text{p50} < 15\,\text{ms}$ và $\text{p95} < 35\,\text{ms}$ trên PostgreSQL 16 ở độ sâu lịch sử 100 sự kiện.
* **NFR-02 (Khả năng Mở rộng Đồng thời - Concurrency Scalability):** Tỷ lệ từ chối nhầm do tranh chấp khóa (False-Stale Rate) PHẢI đạt $< 3.0\%$ khi có 16 luồng ghi đồng thời trên các thực thể khác nhau của cùng một hồ sơ.
* **NFR-03 (Tính Toàn vẹn Dữ liệu - Strict UTC Enforcement):** 100% các trường thời gian trong toàn bộ hệ thống PHẢI được chuẩn hóa về UTC (`timezone.utc`). Nghiêm cấm lưu trữ hoặc so sánh naive datetime.
* **NFR-04 (Bộ nhớ & Tài nguyên - Resource Footprint):** Bộ nhớ RAM tiêu thụ của quá trình biên dịch THSS và đối soát không được vượt quá 150 MiB RSS cho mỗi worker process.
* **NFR-05 (Tính Tái lập Khoa học - Byte-Deterministic Reproducibility):** Cùng một tập dữ liệu đầu vào và cùng một seed PHẢI sinh ra các bản tin THSS và `algorithm_digest` giống nhau 100% về mặt byte mã hóa (SHA-256 match).

### 3.3. Bất biến An toàn Y tế & Bảo mật (Safety Invariants - SEC)

* **SEC-01 (Fail-Closed Invariant):** Mọi lỗi hệ thống, lỗi mạng, mismatch metadata hoặc timeout PHẢI dẫn đến trạng thái từ chối an toàn (Fail-Closed), tuyệt đối không tự động commit.
* **SEC-02 (No-PII Leakage Invariant):** Snapshot THSS và log giám sát tuyệt đối không chứa PII/PHI dạng rõ ngoài phạm vi scope được ủy quyền (`ProfileScope`).
* **SEC-03 (No-Downgrade Invariant):** Nghiêm cấm hoàn toàn mọi đường dẫn cho phép AI Proposal commit dưới dạng `base_version_only`.
* **SEC-04 (FHIR Conformance Invariant):** Mọi tài nguyên xuất bản hoặc tiếp nhận PHẢI vượt qua kiểm định của HL7 Java Validator 6.9.12 trên cả tầng cấu trúc (Schema) và tầng ngữ nghĩa ứng dụng (Application Semantics).
