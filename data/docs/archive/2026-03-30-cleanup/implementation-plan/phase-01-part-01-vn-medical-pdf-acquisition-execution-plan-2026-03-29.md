# Phase-1 Part-1 Detailed Execution Plan: VN Medical PDF Acquisition

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-29  
Phạm vi: kế hoạch triển khai kỹ thuật từng phần cho catalog + ingest PDF y khoa VN

## 1) Mục tiêu triển khai

- Xây pipeline thu thập và quản trị phiên bản tài liệu PDF y khoa VN từ nguồn chính thống.
- Kết nối dữ liệu này vào luồng RAG hiện có theo cách incremental, không phá vỡ kiến trúc P0/P1.
- Đảm bảo tuân thủ pháp lý, kiểm soát freshness, dedupe, checksum, và audit trail.

## 2) Trạng thái codebase hiện tại (alignment)

### 2.1 Thành phần đã có

- API đã có mô hình upload kiến thức theo user:
  - `knowledge_sources`, `knowledge_documents` tại [services/api/src/clara_api/db/models.py](/Users/nguyennt/Documents/CLARA-Care/services/api/src/clara_api/db/models.py).
  - Endpoint CRUD/upload tại [research.py](/Users/nguyennt/Documents/CLARA-Care/services/api/src/clara_api/api/v1/endpoints/research.py).
- Control Tower đã có `rag_sources` + `rag_flow` và lưu trong `system_settings`:
  - [system.py](/Users/nguyennt/Documents/CLARA-Care/services/api/src/clara_api/api/v1/endpoints/system.py).
- ML retriever đã nhận `rag_sources` và `uploaded_documents`:
  - [retriever.py](/Users/nguyennt/Documents/CLARA-Care/services/ml/src/clara_ml/rag/retriever.py).
  - [main.py](/Users/nguyennt/Documents/CLARA-Care/services/ml/src/clara_ml/main.py).

### 2.2 Khoảng trống cần lấp

- Chưa có connector VN-first cho DAV/KCB/DI&ADR/YDCT/VNCDC/IMPE.
- Chưa có bảng metadata hệ thống cho tài liệu công khai (ngoài phạm vi user upload).
- Chưa có job freshness + checksum/versioning chuẩn.
- PDF hiện tại chưa parse sâu trong upload flow (đang placeholder text cho PDF/image trong `research.py`).

## 3) Nguyên tắc triển khai incremental

- Triển khai theo vertical slices, mỗi slice có dữ liệu thực + gate nghiệm thu.
- Ưu tiên `A1/A2 sources` trước, nguồn `B1` sau, `C1` chỉ fallback metadata.
- Không phụ thuộc thay đổi frontend trong Part-1; sử dụng API hiện có và config control tower.
- Mọi ingestion phải idempotent bằng `doc_uid + sha256`.

## 4) Thiết kế schema mục tiêu (engineering-ready)

## 4.1 Bảng/collection đề xuất

1. `source_registry` (cấu hình nguồn crawl)
- `id`, `source_key` (unique), `name`, `owner`, `category`, `trust_tier`, `enabled`
- `entry_urls` (json), `allowed_domains` (json), `schedule_cron`, `crawl_mode`, `legal_notes`
- `created_at`, `updated_at`

2. `source_documents` (thực thể tài liệu logic)
- `id`, `doc_uid` (unique), `source_key`, `title`, `publisher`
- `decision_no`, `decision_date`, `document_type`, `language`, `primary_source_url`
- `trust_tier`, `confidence`, `is_active`, `first_seen_at`, `last_seen_at`

3. `source_document_versions` (phiên bản file vật lý)
- `id`, `doc_uid` (fk), `version_no`
- `download_url`, `storage_uri`, `sha256`, `xxh3_64`, `size_bytes`, `mime_type`
- `http_etag`, `http_last_modified`, `retrieved_at`, `is_current`

4. `source_crawl_runs` (audit & vận hành)
- `id`, `source_key`, `started_at`, `finished_at`, `status`
- `fetched_count`, `new_docs_count`, `updated_docs_count`, `failed_count`
- `error_summary` (json), `duration_ms`

## 4.2 Tương thích với mô hình hiện có

- Giai đoạn đầu có thể chưa thêm migration ngay:
  - Lưu manifest JSONL ở `docs/research/data/` hoặc object storage để pilot.
  - Nạp subset vào `rag_sources` control tower để test retrieval.
- Khi ổn định connector, thêm migration DB cho `source_*` tables.

## 5) Work breakdown theo Part

## Part 1.1 (đã hoàn thành trong task này): Source research baseline

Deliverables:
- Catalog sâu: [2026-03-29-vn-medical-pdf-source-catalog-phase1-part1-deepdive.md](/Users/nguyennt/Documents/CLARA-Care/docs/research/2026-03-29-vn-medical-pdf-source-catalog-phase1-part1-deepdive.md).
- Data CSV machine-readable: [vn-medical-pdf-sources-phase1-part1-2026-03-29.csv](/Users/nguyennt/Documents/CLARA-Care/docs/research/data/vn-medical-pdf-sources-phase1-part1-2026-03-29.csv).

Acceptance criteria:
- Có URL cụ thể cho từng nguồn.
- Có trust tier + confidence + cadence + usage notes.
- Có mô tả rõ các điểm chưa chắc chắn (Dược thư portal).

## Part 1.2: Source registry + scheduler config (không đụng runtime chat)

Tasks:
1. Tạo `source_registry.v1.json` từ CSV catalog (chỉ `A1/A2` trong wave đầu).
2. Tạo job config `ingest_schedule.v1.json` theo cadence.
3. Thiết lập rule domain-rate-limit cho từng nguồn.

Output artifacts (đề xuất):
- `docs/research/data/source-registry.v1.json`
- `docs/research/data/ingest-schedule.v1.json`

Acceptance criteria:
- Mỗi source có `source_key`, `entry_urls`, `allowed_domains`, `crawl_mode`, `schedule`.
- Có thể chạy dry-run validator để báo thiếu trường bắt buộc = 0.

## Part 1.3: Connector MVP (DAV + DI&ADR + KCB)

Tasks:
1. Viết connector parser HTML list + attachment link cho DAV.
2. Viết connector issue+download cho DI&ADR magazine.
3. Viết connector guideline page + file-list cho KCB.
4. Chuẩn hóa output về `document_manifest`.

Test strategy:
- Unit test parser HTML (fixture tĩnh).
- Integration smoke test 1 nguồn/1 URL thật mỗi domain.

Acceptance criteria:
- Mỗi connector ingest >= 20 tài liệu lịch sử (nếu nguồn cho phép).
- Tỷ lệ thành công fetch >= 95% trên sample run.
- Không duplicate `doc_uid` trong cùng run.

## Part 1.4: Versioning, checksum, dedupe pipeline

Tasks:
1. Implement canonical URL normalize + metadata-key generation.
2. Implement hash pipeline (`sha256`, `xxh3_64`) và policy version bump.
3. Implement near-duplicate detector (simhash text) ở mức cảnh báo.
4. Lưu run manifest và failure log.

Acceptance criteria:
- Duplicate hard (cùng hash) bị gộp 100%.
- Cập nhật nội dung (hash đổi) tạo `version_no + 1` chính xác.
- Có báo cáo run gồm `new/updated/unchanged/failed`.

## Part 1.5: Freshness monitoring + alerting

Tasks:
1. Tạo freshness job theo schedule (daily/weekly/monthly).
2. Tính `staleness_hours` theo source.
3. Xuất report và cảnh báo nguồn stale vượt SLA.

Tích hợp bước đầu:
- Dùng endpoint hệ thống sẵn có để hiển thị số liệu trong panel admin sau này (`/api/v1/system/*`).

Acceptance criteria:
- Safety-critical sources (DAV/DIADR) cảnh báo khi stale > 24h.
- Guideline sources cảnh báo khi stale > 72h.
- Có snapshot report tái tạo được cho 7 ngày gần nhất.

## Part 1.6: Bridge vào RAG hiện tại

Tasks:
1. Chuyển đổi top-N tài liệu mới thành `rag_sources` payload hoặc `uploaded_documents` format đang dùng.
2. Cập nhật mapping source-id VN trong control tower config (`davidrug`, `di_adr_vn`, `kcb_vn`, `ydct_vn`, ...).
3. Định nghĩa source weighting theo trust tier (`A1 > A2 > B1 > C1`).

Code touchpoints tương thích:
- [chat.py](/Users/nguyennt/Documents/CLARA-Care/services/api/src/clara_api/api/v1/endpoints/chat.py) (payload sang ML).
- [system.py](/Users/nguyennt/Documents/CLARA-Care/services/api/src/clara_api/api/v1/endpoints/system.py) (control tower config).
- [retriever.py](/Users/nguyennt/Documents/CLARA-Care/services/ml/src/clara_ml/rag/retriever.py) (source policies).

Acceptance criteria:
- Bật/tắt nguồn VN trong control tower có tác động thật đến `retrieved_ids`.
- Truy vấn thử về thuốc giả/guideline VN trả citation từ nguồn VN hợp lệ.

## Part 1.7: Compliance + runbook

Tasks:
1. Tạo checklist legal crawl theo domain.
2. Định nghĩa cơ chế stoplist khi site báo chặn hoặc đổi chính sách.
3. Tạo runbook incident cho crawl failure hàng loạt.

Acceptance criteria:
- Có policy văn bản cho: robots, auth boundary, PII boundary, attribution.
- Có thủ tục rollback khi ingest lỗi metadata hàng loạt.

## 6) Ước lượng triển khai và thứ tự ưu tiên

Wave 1 (nhanh nhất, giá trị cao):
1. DAV
2. DI&ADR
3. KCB

Wave 2:
1. YDCT
2. MCH
3. VNCDC
4. IMPE-QN

Wave 3:
1. JPRDI
2. Journal 108
3. Tạp chí Y học Việt Nam
4. HMU DSpace metadata

## 7) KPI/gates cho Phase-1 Part-1 -> Part-2

Gate G1 (sau Part 1.3):
- 3 connector MVP chạy ổn định 7 ngày.
- Không vi phạm rate-limit/policy crawl.

Gate G2 (sau Part 1.5):
- Freshness alerts hoạt động đúng cho ít nhất 5 nguồn A1/A2.

Gate G3 (sau Part 1.6):
- Truy vấn smoke test có citation VN trên ít nhất 2 nhóm nghiệp vụ:
  - cảnh báo thuốc giả/thu hồi,
  - guideline chẩn đoán/điều trị.

## 8) Rủi ro chính và giảm thiểu

- Dược thư portal gián đoạn (`duocquocgia.com.vn`):
  - Giảm thiểu: health-check định kỳ + placeholder source state `temporarily_unreachable`.
- HTML site thay đổi cấu trúc:
  - Giảm thiểu: parser theo selector dự phòng + regression fixtures.
- Giới hạn pháp lý/bản quyền (đặc biệt kho đại học restricted):
  - Giảm thiểu: chỉ ingest metadata khi chưa có quyền fulltext.

## 9) Definition of Done cho toàn Part-1

- Có catalog nguồn VN y khoa đủ sâu, có thể machine-read.
- Có execution plan chi tiết theo part với schema + acceptance criteria.
- Có lộ trình incremental khớp với kiến trúc API/ML hiện tại, không yêu cầu big-bang rewrite.

