# Phase 01 Plan: Research Flow Hardening + DDI Nâng Chuẩn + Web Research Engine (No API) + KP3-like Landing

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-29  
Phạm vi: Chỉ Phase 01, triển khai tuần tự từng phase con, không chạy song song nhiều phase.

## 1) Mục tiêu Phase 01

1. Làm cứng luồng Research theo chuỗi bắt buộc: `route -> retrieve -> synthesize -> verify -> policy -> respond`.
2. Chuẩn hóa DDI lên mức clinical-grade có giải thích rõ nguồn và mức độ rủi ro.
3. Xây web research engine không phụ thuộc API ngoài (không dùng API key provider tìm kiếm).
4. Nâng chất UI/UX chat và landing theo định hướng KP3-like để tăng clarity + conversion.

## 2) Nguyên tắc triển khai "mỗi lần 1 phase"

1. Chỉ mở 1 phase con tại 1 thời điểm; phase sau chỉ bắt đầu khi phase trước `pass gate`.
2. Mỗi phase con bắt buộc đủ: code/config + test + telemetry + runbook rollback.
3. Mọi thay đổi có feature flag theo stream để rollback độc lập.
4. Không promote production nếu chưa có bằng chứng pass cho cả 4 stream trong cùng phase.

## 3) Lộ trình tuần tự theo phase (8 tuần)

| Phase | Tuần | Trọng tâm | Exit gate bắt buộc |
|---|---:|---|---|
| P01-F1 | Tuần 1 | Baseline + contract freeze | Contract và metric baseline được chốt, có trace đầu-cuối |
| P01-F2 | Tuần 2 | Core build v1 cho 4 stream | Chạy được flow kỹ thuật tối thiểu trên staging |
| P01-F3 | Tuần 3 | Quality logic v1 (verify/policy/severity/ranking/UI states) | Unit + integration pass theo ngưỡng phase |
| P01-F4 | Tuần 4 | E2E integration v1 | End-to-end luồng chính chạy ổn định, không bypass gate |
| P01-F5 | Tuần 5 | Hardening + red-team + accessibility | Regression pack pass, có risk-control rõ |
| P01-F6 | Tuần 6 | Perf + observability + funnel tracking | KPI latency/quality/funnel đạt ngưỡng staging |
| P01-F7 | Tuần 7 | Release candidate + canary | Canary pass không phát sinh sự cố Sev0/Sev1 |
| P01-F8 | Tuần 8 | Go-live + rollback drill + handover | Go-live checklist pass và rollback drill thành công |

## 4) Stream A - Flow Hardening + Factcheck/Policy

| Phase | Task nhỏ (tuần tự) | Output | Tiêu chí pass | Risk | Rollback |
|---|---|---|---|---|---|
| P01-F1 | A1.1 Chốt state-machine research flow; A1.2 Chốt schema `verification_status`, `policy_action`, `policy_reason`; A1.3 Baseline log `trace_id/session_id/stage` | Spec flow v1 + contract response v1 + dashboard baseline panel | 100% request research có đủ 6 stage trong trace mẫu; contract ký duyệt liên team | Lệch định nghĩa giữa BE/ML/FE | Giữ contract cũ sau cờ `research_flow_v2=false` |
| P01-F2 | A2.1 Cứng hóa transition rule (không cho skip `verify/policy`); A2.2 Timeout budget theo stage; A2.3 Idempotency key cho retry | Runtime guard module + timeout map + idempotency middleware | Không còn path bypass `verify/policy` trong integration test; retry không tạo response trùng | Latency tăng do thêm guard | Hạ guard về advisory mode, giữ logging |
| P01-F3 | A3.1 Claim extraction trước verify; A3.2 Factcheck verdict `pass/partial/fail`; A3.3 Confidence re-score theo verdict | Verifier v1 + claim/factcheck report + confidence policy table | Verification pass >= 97% trên bộ goldset nội bộ; claim không có chứng cứ bị đánh dấu `partial/fail` | False-negative cao làm tụt UX | Bật profile `verify_lenient_v1`, chỉ cảnh báo không block |
| P01-F4 | A4.1 Policy matrix theo role-intent; A4.2 Ánh xạ hành động `allow/warn/block/escalate`; A4.3 Audit trail quyết định policy | Policy engine v1 + policy registry + audit stream | 100% response có `policy_action`; case cấm bắt buộc `block/escalate`; audit truy vết đầy đủ | Over-block ở truy vấn biên | Rollback policy profile về phiên bản trước trong registry |
| P01-F5 | A5.1 Red-team prompt suite; A5.2 Test injection bypass verify; A5.3 Chuẩn hóa safe response template | Bộ test adversarial + safe template + report lỗ hổng | 0 case critical bypass policy; hallucination nghiêm trọng giảm theo ngưỡng phase | Pattern mới chưa bao phủ | Bật manual-review cho intent nhạy cảm |
| P01-F6 | A6.1 Tối ưu pipeline concurrency; A6.2 Circuit breaker cho verifier/tool; A6.3 Alert rule cho fail rate theo stage | Perf tuning pack + SLO alert + incident playbook v1 | p95 flow Normal <= 120s; stage fail-rate trong ngưỡng cảnh báo | Cache sai ngữ cảnh gây sai trả lời | Tắt cache layer mới, quay về cache stable profile |
| P01-F7 | A7.1 Canary 10%-30%; A7.2 So sánh quality trước/sau; A7.3 Chốt release notes policy | Canary report + go/no-go biên bản + release artifact | Không tăng Sev1; quality không giảm so với baseline | Drift theo traffic thật | Giảm canary về 0%, chuyển toàn bộ về bản stable |
| P01-F8 | A8.1 Go-live toàn lượng; A8.2 Drill rollback định kỳ; A8.3 Handover runbook cho Ops | Runbook vận hành + rollback script + tài liệu handover | Rollback drill hoàn tất < 15 phút; audit pass | Runbook thiếu bước khi sự cố thật | Kích hoạt war-room, dùng rollback profile đã kiểm chứng |

## 5) Stream B - DDI Nâng Chuẩn

| Phase | Task nhỏ (tuần tự) | Output | Tiêu chí pass | Risk | Rollback |
|---|---|---|---|---|---|
| P01-F1 | B1.1 Audit nguồn DDI hiện có (RxNorm/openFDA/local rules); B1.2 Chốt schema DDI unified; B1.3 Chốt severity dictionary clinical | DDI contract v2 + mapping dictionary + baseline quality report | Data dictionary được clinical review; schema dùng thống nhất BE/FE | Nguồn dữ liệu lệch format | Giữ parser cũ và khóa ingest nguồn lỗi |
| P01-F2 | B2.1 Chuẩn hóa entity thuốc về canonical + RxCUI; B2.2 Dedupe interaction pair; B2.3 Ghi metadata `source_used/source_errors/fallback_used` | Resolver v2 + dedupe engine + metadata pipeline | Tỉ lệ resolve canonical đạt ngưỡng nội bộ; metadata hiện đầy đủ ở response | Resolve sai tên hoạt chất | Fallback về local deterministic resolver |
| P01-F3 | B3.1 Tuning severity `critical/high/medium/low`; B3.2 Rule allergy hard-stop; B3.3 Rule contraindication theo nhóm nguy cơ | Severity mapping clinical-grade + hard-stop ruleset + test suite | DDI critical sensitivity >= 98%; hard-stop không bị ghi đè bởi LLM | False-positive tăng gây mệt mỏi cảnh báo | Hạ ngưỡng non-critical, giữ nguyên hard-stop critical |
| P01-F4 | B4.1 Tạo explainability card cho từng cảnh báo; B4.2 Gắn evidence link + rationale; B4.3 Chuẩn hóa policy handoff `warn/block/escalate` | DDI explanation payload + UI contract + handoff policy | 100% alert critical/high có rationale + evidence; handoff chạy đúng action | Evidence thiếu hoặc trùng lặp | Ẩn evidence lỗi, giữ cảnh báo với nhãn fallback |
| P01-F5 | B5.1 Regression corpus mở rộng; B5.2 Test timeout/retry queue; B5.3 Calibrate ngưỡng alert fatigue | Regression report + retry policy + calibration log | Regression pass >= 95%; timeout path không mất job | Queue backlog giờ cao điểm | Chuyển chế độ degraded: batch + retry chậm |
| P01-F6 | B6.1 Idempotency cho auto-DDI; B6.2 Monitor trend false/missed alert; B6.3 SLA dashboard cho scan-to-DDI | Idempotent workflow + DDI ops dashboard + SLA alert | Không phát sinh duplicate `ddi_check_id`; SLA scan-to-DDI trong ngưỡng | Mất đồng bộ giữa scan và DDI | Reconcile job định kỳ và retry từ checkpoint |
| P01-F7 | B7.1 Canary theo cohort nhỏ; B7.2 Clinical spot-check; B7.3 Chốt rule freeze release | Canary clinical report + rule freeze v1 | Không tụt sensitivity critical; escalation path ổn định | Khác biệt cohort thật vs test set | Tắt cohort canary, quay về rule profile stable |
| P01-F8 | B8.1 Rollout toàn hệ; B8.2 Drill sự cố DDI queue; B8.3 Handover vận hành safety | DDI production runbook + incident drill report | Drill khôi phục queue đạt SLA; clinical sign-off hoàn tất | Sự cố nguồn ngoài kéo dài | Chuyển fallback local-only tạm thời theo playbook |

## 6) Stream C - Web Research Engine Không API

| Phase | Task nhỏ (tuần tự) | Output | Tiêu chí pass | Risk | Rollback |
|---|---|---|---|---|---|
| P01-F1 | C1.1 Chốt whitelist domain + robots policy; C1.2 Chốt chuẩn crawl cadence; C1.3 Chốt schema tài liệu ingest | Crawl governance v1 + domain whitelist + ingest schema | 100% domain có policy rõ (allow/deny/rate-limit); có log legal/compliance | Vi phạm robots/TOS | Disable domain ngay bằng config, purge dữ liệu vừa crawl |
| P01-F2 | C2.1 Xây crawler HTML/RSS/Sitemap không dùng API key; C2.2 Rate limiter per-domain; C2.3 Retry/backoff tiêu chuẩn | Crawler v1 + scheduler + retry policy | Crawl được seed set, không vượt limit đã đặt; không dùng API ngoài | Block IP do crawl quá nhanh | Giảm crawl rate + tăng interval + cache |
| P01-F3 | C3.1 Parser làm sạch HTML; C3.2 Extract title/date/source/snippet; C3.3 Deduplicate theo URL/hash | Parser v1 + metadata extractor + dedupe index | Tài liệu parse thành công đạt ngưỡng phase; duplicate giảm theo mục tiêu | Parse lỗi layout động | Fallback parser đơn giản + đưa vào queue manual review |
| P01-F4 | C4.1 Lexical retrieval + BM25; C4.2 Rerank heuristic theo source/freshness; C4.3 Citation builder | Search index v1 + rerank module + citation payload | Top-k trả về citation có nguồn rõ; không có kết quả rỗng ở case chuẩn | Ranking lệch nguồn uy tín | Khóa weight về profile conservative |
| P01-F5 | C5.1 Claim-grounding với nguồn crawl; C5.2 Freshness score + stale warning; C5.3 Conflict note giữa nguồn | Grounding module + freshness board + conflict note formatter | Response có cảnh báo stale khi cần; conflict note hiển thị đúng | Nguồn cũ gây trả lời lỗi thời | Tăng trọng số freshness, hạ nguồn stale xuống cuối |
| P01-F6 | C6.1 Tối ưu index cập nhật tăng dần; C6.2 Quan sát crawl health/failure; C6.3 Fail-soft khi crawl outage | Incremental indexing + crawl observability + fail-soft path | Khi crawl lỗi vẫn trả lời từ corpus cũ có nhãn cảnh báo; không crash flow | Storage phình nhanh | Bật retention/TTL và nén index |
| P01-F7 | C7.1 Canary retrieval engine mới; C7.2 Đo precision nội bộ; C7.3 Chốt runbook vận hành crawl | Canary search report + precision dashboard + crawl runbook | Precision không giảm so baseline; crawl lỗi được auto-recover | Drift chất lượng do thay đổi website | Khôi phục snapshot index gần nhất |
| P01-F8 | C8.1 Rollout đầy đủ engine no-API; C8.2 Drill mất nguồn diện rộng; C8.3 Handover vận hành | Production config + DR drill report + on-call guide | DR drill thành công; thời gian phục hồi trong SLA nội bộ | Outage diện rộng kéo dài | Chuyển sang chế độ knowledge-cache-only tạm thời |

## 7) Stream D - UI/UX Polish Chat + Landing KP3-like

| Phase | Task nhỏ (tuần tự) | Output | Tiêu chí pass | Risk | Rollback |
|---|---|---|---|---|---|
| P01-F1 | D1.1 Audit UX hiện trạng chat + landing; D1.2 Chốt KPI funnel; D1.3 Chốt design tokens và content tone tiếng Việt | UX audit + KPI baseline + token set v1 | Có baseline onboarding funnel; token dùng thống nhất | KPI đo thiếu sự kiện | Bổ sung tracking tối thiểu trước khi redesign |
| P01-F2 | D2.1 Refactor chat layout `question-first`; D2.2 Composer + state loading/error rõ; D2.3 Chuẩn hóa response card khung | Chat shell v2 + composer state map + response card spec | Người dùng gửi câu hỏi và đọc kết quả không bị rối; không crash state | UI thay đổi mạnh gây nhiễu user cũ | Feature flag `chat_v2` để quay về UI cũ |
| P01-F3 | D3.1 Evidence panel + citation chip; D3.2 Badge `verification/policy/confidence`; D3.3 Tối ưu mobile chat | Evidence panel v1 + trust badges + mobile layout v1 | Hiển thị đầy đủ citation/verification/policy; mobile không vỡ layout | Quá tải thông tin trong 1 màn | Mặc định collapsed panel, chỉ mở khi user yêu cầu |
| P01-F4 | D4.1 Thiết kế landing KP3-like cấu trúc funnel; D4.2 Hero + problem/solution + trust bar; D4.3 CTA flow `landing -> huong-dan -> login -> first query` | Landing IA v2 + wireframe + content outline | Funnel thông suốt không dead-end; CTA chính luôn rõ | Copy không đúng insight người dùng | Rollback copy về bản baseline đã có conversion ổn định |
| P01-F5 | D5.1 Hoàn thiện UI landing desktop/mobile; D5.2 A11y (contrast/focus/keyboard); D5.3 Tối ưu tốc độ tải trang đầu | Landing implementation v2 + a11y checklist + perf report | Lighthouse/a11y nội bộ đạt ngưỡng phase; CLS/UX trong mức chấp nhận | Hiệu ứng nhiều gây chậm | Tắt animation nặng, quay về static section |
| P01-F6 | D6.1 Gắn funnel analytics chi tiết; D6.2 A/B test headline + CTA; D6.3 Tối ưu microcopy chat | Event taxonomy + A/B dashboard + copy pack v2 | Có dữ liệu đủ để quyết định biến thể thắng; giảm drop-off onboarding | Dữ liệu A/B nhiễu do traffic thấp | Kéo dài thời gian test, giữ bản control |
| P01-F7 | D7.1 Usability test nhanh theo role; D7.2 Sửa các friction chính; D7.3 Freeze UI cho RC | Usability findings + fix batch + UI freeze note | Task success rate theo kịch bản đạt ngưỡng phase | Scope creep từ feedback nhiều | Chỉ nhận fix mức blocker trước RC |
| P01-F8 | D8.1 Rollout giao diện chính thức; D8.2 Theo dõi conversion sau go-live; D8.3 Handover guideline vận hành nội dung | Go-live UX report + conversion dashboard + content playbook | Onboarding completion tăng so baseline; không phát sinh regression lớn | Conversion giảm sau rollout | Chuyển traffic về biến thể control trong feature flag |

## 8) Gate bắt buộc trước khi chuyển phase

| Gate | Điều kiện pass tối thiểu |
|---|---|
| Gate-F1 -> F2 | Contract freeze 4 stream, có baseline metric và trace |
| Gate-F2 -> F3 | Flow kỹ thuật cơ bản chạy staging, không lỗi chặn |
| Gate-F3 -> F4 | Unit/integration pass; logic verify/policy/DDI/ranking/UI state ổn |
| Gate-F4 -> F5 | E2E pass cho luồng chính của 4 stream |
| Gate-F5 -> F6 | Regression + red-team + a11y pass |
| Gate-F6 -> F7 | KPI staging đạt ngưỡng latency/quality/funnel |
| Gate-F7 -> F8 | Canary an toàn, không tăng sự cố nghiêm trọng |
| Gate-F8 (đóng phase) | Go-live ổn định + rollback drill pass + handover hoàn tất |

## 9) Checklist nghiệm thu cuối Phase 01

1. Stream A: Chuỗi `route->retrieve->synthesize->verify->policy->respond` là hard gate, không bypass.
2. Stream B: DDI đạt ngưỡng sensitivity critical, có explainability và fallback an toàn.
3. Stream C: Web research engine chạy không API key ngoài, có compliance crawl và fail-soft.
4. Stream D: Chat + landing đạt chuẩn UX mới, funnel đo được và có phương án rollback bằng feature flag.
5. Mọi stream có runbook vận hành + rollback đã drill thành công.
