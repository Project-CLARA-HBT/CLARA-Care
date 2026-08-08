# Kế hoạch thực thi GLHS (HEAD audit, 2026-08-08)

## Mục tiêu và ranh giới

GLHS là lớp state chuẩn có kiểm soát, bổ sung vào HEAD hiện tại; không thay thế
ngay PHR, LifeMap hay Medicine bằng một JSON snapshot. Hai ranh giới bắt buộc
là `Evidence → GST → GLHS` và `GLHS → THSS → AI`. PostgreSQL là canonical;
Neo4j, Milvus, Elasticsearch, Redis, LifeMap/Today và giao diện là projection
hoặc consumer có thể dựng lại.

Không công bố readiness lâm sàng từ các kiểm thử này. Các fixture GLHS/Q3 sau
này chỉ được mô tả là synthetic hoặc semi-synthetic structural robustness.

## Bằng chứng audit hiện tại

Đã đọc `AGENTS.md`, `CLAUDE.md`, `README.md`, đặc tả LifeMap convergence và
spec GLHS do dự án cung cấp; local HEAD là nguồn quyết định khi có mâu thuẫn
với tài liệu cũ.

| Bề mặt | Canonical/đường ghi hiện tại | Đường đọc/current-state | Khoảng cách GLHS |
| --- | --- | --- | --- |
| PHR | `phr_profiles`, `phr_versions`, `phr_observations` | profile scalar/JSON + observation rows | Adapter ghi list dị ứng/bệnh nền/thuốc tự khai và observation đã có. Whole-record, onboarding, single-entry create/patch/delete và OCR-confirm đều mirror trong transaction; thuốc free text/OCR vẫn là candidate không định danh và correction/removal retire candidate cũ. Read projection và scalar/body legacy còn phải hội tụ. |
| LifeMap | `lifemap_events`, immutable `lifemap_event_revisions`, command/outbox | GLHS-limited event IDs → revision citation projection | Adapter đã đồng bộ create/confirm/dispute/invalidate/resolve/correct. Ask, visit-preparation, summaries và delegated digest compile THSS trước rồi mới truy hồi exact revision wording. Thu hồi nguồn retire assertion GLHS bằng transition append-only và invalidates projection/citation; không xóa lịch sử. |
| Thuốc | `medication_courses`, append-only `medication_course_changes` | GLHS medication THSS cho DrugBank-only DDI và CareGuard reconciliation | Adapter create/correct/end có deterministic identity boundary. CareGuard reconciliation và endpoint DrugBank-only DDI đã đọc THSS; cabinet vẫn là user-scoped input cho phép kiểm tra trực tiếp, không phải profile personalization. |
| Visits/Scribe | visit/document/note, LifeMap event adapter riêng | visit packs, grounded notes | Visit pack là user/clinician-selected projection với review/approval riêng; visit-preparation AI dùng THSS cho LifeMap. Visit document (kể cả signed Scribe note được người dùng liên kết vào visit) nay mirror thành assertion `evidence/visit_document_available` có checksum, version và GST lifecycle; transcript/SOAP tuyệt đối không auto-ingest thành health assertion. Withdraw/delete retire assertion append-only. Grounded extraction + human review riêng vẫn mới được phép đề xuất dữ kiện lâm sàng. |
| Connected Health | consent-bound `WearableObservation` + version/tombstone | device rows và rebuildable daily aggregate | Import now mirrors each exact `(data_origin, provider_record_id)` slot through source evidence and GST. Provider values are `documented`, never clinician-confirmed; update supersedes, tombstone retires, and origin is included in the selector to prevent cross-origin record-ID conflation. Full device/FHIR E2E and relevance policy remain pending. |
| Family | `FamilyAccessGrant` + profile scope | API scope theo actor/grant/purpose/data class | Scope tốt, nhưng AI snapshot chưa dùng một compiler trung tâm. |
| AI LifeMap | `lifemap/intelligence.py` truy vấn event revision trực tiếp | deterministic answer/temporal retrieval | Chưa có THSS manifest/task-purpose. |
| CareGuard/Council/Research/Chat | API/ML boundary và guard riêng | module payload riêng | CareGuard, Research personal mode và Chat đã dùng THSS bound theo task/purpose. Chat nhận `clinical_context` từ client dưới nhãn `untrusted_user_context`; personal state chỉ được thêm sau scope (owner/Family), personalization consent và THSS strict, ở cả REST/stream. Council và Scribe hiện không đọc PHR/GLHS: case payload/transcript là untrusted per-request input, không được gọi là personalized state. Bất kỳ personalization tương lai nào phải đi qua THSS riêng theo task/purpose; không được tự nối JSON profile. |

## Baseline đã đo

| Lệnh | Kết quả | Diễn giải |
| --- | --- | --- |
| `make test` trước sửa | lỗi ngay: `/bin/zsh` không tồn tại | Footgun Makefile, không phải bằng chứng test xanh. |
| `services/api/.venv/bin/python -m pytest -q` | 1300 passed, 3 failed, 1 skipped | Các failure thuộc invalid-token/route-public inventory/control tower contract cần audit riêng; không che giấu. |
| `services/ml/.venv/bin/python -m pytest -q` | 49 last-failed tests | Nhiều test cũ kỳ vọng fallback/degraded LLM trái với policy hiện hành không fallback; cần phân loại từng test, không bật fallback để làm xanh. |

## Thiết kế đã bắt đầu

Migration `20260808_0050_glhs_foundation` bổ sung ledger:

- `glhs_evidence`, `glhs_assertions`, `glhs_assertion_evidence`, `glhs_relations`;
- `glhs_state_versions`, `glhs_transitions`, `glhs_transition_items`;
- `glhs_conflicts`, `glhs_snapshot_manifests`.

`clara_api.glhs.gateway` là trusted API boundary: evidence phải thuộc profile,
assertion phải có evidence, model không thể tạo assertion/transition, transition
kiểm tra optimistic state version, assertion confirmed cần caller có review
authority tường minh, conflict được giữ lại, và THSS chỉ nhận ProfileScope đã
được authorize, data class là subset và purpose đúng tại thời điểm dùng.

Các adapter hiện chạy trong cùng transaction cho LifeMap create và truth
transition, gồm source revocation → assertion supersede; MedicationCourse create/correct/end; CareGuard OCR capture được
người dùng xác nhận; PHR observations; và PHR list dị ứng/bệnh nền/thuốc. Không backfill/auto-confirm dữ liệu lịch sử. Xác nhận
của owner trong LifeMap là `documented`, không phải `confirmed` lâm sàng. Thuốc
không có DrugBank ID được giữ `medications_unresolved`, không vào medication
THSS/DDI. PHR list vẫn là response/projection legacy trong giai đoạn hội tụ,
không được personalized Research đọc trực tiếp.

## Checkpoint kế tiếp

1. Chạy/điều chỉnh migration clean-db và thêm migration/upgrade regression.
2. Hoàn tất adapters cho PHR scalar/body projection, Visit/Scribe reviewed
   clinical extraction (không phải document evidence đã có), Connected Health relevance filtering và consent/revocation
   invalidation.
3. Thay personalized consumers theo thứ tự LifeMap Ask → Council/Chat, giữ
   feature-flag rollback ở API boundary. CareGuard reconciliation đã chuyển
   sang THSS; không có fallback về `PhrProfile.*_json` khi feature bật.
4. Viết E2E cho profile/Family/CSRF/consent/revocation/THSS; sửa test stale
   theo strict no-fallback policy mà không làm yếu safety invariants.
5. Tạo `evaluation/glhs_q3/`: generator >=300 case / >=150 subject, paired LWW
   và Naive RAG, ablation GST/THSS, analysis/figures from frozen output only.
6. Chỉ sau output measured, cập nhật manuscript/IEEE macros/tables/PDF.

## Quy tắc rollback

Migration là additive; adapter có thể được rollback bằng code commit/revert mà
không xóa health history. Không có cờ nào được phép bỏ qua consent, RBAC,
Family isolation, CSRF, emergency/legal guard, FIDES, deterministic medication
identity hay review boundary.

## Q3 structural checkpoint (2026-08-08)

`evaluation/glhs_q3/run.py` hiện là protocol `glhs-q3-structural-v3`: 300 case
developer-authored, 150 subject synthetic, seed mặc định `20260808`, 8–30
episode/subject. Artifact tái lập được tạo bằng `make eval-glhs-q3` tại
`artifacts/glhs-q3/latest/`; `evidence-manifest.json` liên kết summary SHA-256,
Git revision, source hash runner/gateway/adapter/model/migration và toàn bộ
CSV/SVG. Nó so cùng case ID trên sáu model cấu trúc: LWW, naive RAG,
temporal/provenance resolver, full GLHS reference policy, GLHS-no-THSS và
GLHS-no-GST; phủ late evidence, conflict, provenance, Family,
consent/revocation, stale state, Scribe ambiguity, rebuild và direct-write.

Run này báo raw numerator/denominator, Wilson CI, exact paired McNemar + Holm,
patient-clustered bootstrap risk difference, THSS 4 profile với authorization
fixed, lỗi/automation và pure-Python scalability 10/50/100/250; sáu figure
được dựng trực tiếp từ `summary.json`. Nó vẫn chỉ là **structural
robustness/protocol conformance** với oracle developer-authored, không phải
clinical accuracy, clinical safety, performance trên bệnh nhân, production/LLM
latency, real-world privacy hay superiority thực tế. MIMIC Demo đang `not_run`
vì không có local path hợp pháp được truyền rõ; full MIMIC credentialed tuyệt
đối không tự truy cập.

V3 không phát hành final benchmark score từ developer set, kể cả khi
`glhs_full` đạt 100%: reference-policy và oracle dùng cùng declared rules. Một
score cuối chỉ được phép khi manifest external v2 ghi một cohort riêng
(MIMIC-IV Demo, MIMIC-IV-ED Demo, MIMIC-IV on FHIR Demo hoặc Synthea FHIR R4),
`partition=sealed_holdout`, checksum perturbation/oracle/development-set,
freeze metadata, curator và independence attestation. Từng cohort phải được
báo riêng, không gộp Synthea và MIMIC thành headline metric; attestation vẫn
cần được governance review ngoài khả năng kiểm tra máy của runner.

## Migration checkpoint (2026-08-08)

`services/api/tests/test_glhs_foundation_migration.py` khởi tạo schema pre-GLHS
tối thiểu, chạy `20260808_0050_glhs_foundation.upgrade()`, kiểm tra đủ chín
bảng ledger và các index truy vấn trọng yếu, rồi chạy `downgrade()`. Test cũng
xác nhận chỉ các bảng GLHS additive bị gỡ; `users`, `phr_profiles` và
`health_source_references` giữ nguyên. Đây là schema round-trip trên SQLite,
không thay thế migration rehearsal PostgreSQL production hoặc backup/rollback
drill trên dữ liệu thật.
