# GLHS/CommitLoop contract baseline audit và kế hoạch hardening

Trạng thái: **baseline đã xác minh một phần; chưa đạt confirmatory readiness**.
Ngày chốt baseline: 2026-08-11 (Asia/Ho_Chi_Minh). Tài liệu này chỉ mô tả
bằng chứng kỹ thuật trên dữ liệu tổng hợp; không phải bằng chứng lâm sàng và
không phải tuyên bố chất lượng xuất bản.

## 1. Baseline có thể tái kiểm chứng

| Hạng mục | Bằng chứng hiện tại |
| --- | --- |
| Branch | `codex/commitloop-phase-a`, khớp `origin/codex/commitloop-phase-a` |
| Commit | `6d71c8bcb7207237563d409bb816947c994761d1` |
| Tracked worktree | Sạch; 24 đường dẫn untracked thuộc người dùng, không được sửa/stage |
| Host | Fedora 44, Linux 6.19.10 x86_64 |
| Runtime test | API/ML venv Python 3.11.15; host Python 3.14.3; Node 24.13.1; npm 11.8.0 |
| Runtime image | `services/api/Dockerfile` dùng `python:3.14-slim`; Docker không có trên host audit |
| Package runner | `uv` không có trên PATH; venv cục bộ có pytest 9.1.1, Ruff 0.16.0, mypy 2.3.0 |
| Lock hashes | API `1928a06c...cf1f9c`; ML `020e6163...ee705`; web `5b26ccba...3f6` |
| Focused tests | 49 passed, 3 framework deprecation warnings |
| Focused lint/type | Ruff pass; mypy pass trên 11 file GLHS/CommitLoop liên quan |
| Historical full suites | API 1,357 passed/1 skipped; ML 1,500 passed/2 skipped tại freeze cũ; cần chạy lại cho HEAD mới trước seal |
| Repository-wide quality | Audit cũ ghi 635 Ruff findings và 332 mypy errors; chưa được chứng minh đã giải quyết |

Lệnh baseline trọng tâm:

```bash
cd services/api
.venv/bin/python -m pytest -q \
  tests/test_glhs_gateway.py tests/test_glhs_connected_adapter.py \
  tests/test_glhs_visit_document_adapter.py tests/test_glhs_foundation_migration.py \
  tests/test_chat_thss_context.py tests/test_commitloop_gateway.py \
  tests/test_commitloop_predicate_dsl.py tests/test_commitloop_reconciliation.py \
  tests/test_commitment_endpoint_contract.py \
  tests/test_commitment_endpoints_integration.py tests/test_commitment_policies.py
```

## 2. Lifecycle và mapping claim → implementation

| Lifecycle/claim | Implementation | Test/artifact | Kết luận |
| --- | --- | --- | --- |
| Evidence ingestion | `glhs/adapters.py`, `record_evidence()` | adapter/gateway tests | Có provenance pointer và fingerprint; chưa có DB immutability |
| Governed state | `GlhsStateVersion`, assertion/evidence/transition ledger, `apply_transition()` | `test_glhs_gateway.py` | Có optimistic version check; race chưa được chứng minh trên PostgreSQL |
| Bitemporal replay | `reconstruct_state()` và `reconstruct_commitments()` | gateway/reconciliation tests | Có valid/known cutoffs; replay dài và ledger-tamper recovery còn thiếu |
| THSS disclosure | `compile_thss()` và `compile_commitment_thss()` | THSS/chat/commitment tests | Có scope, purpose, expiry, payload digest; thứ tự pipeline chưa được biểu diễn/kiểm tra như invariant |
| Model proposal | generic assertion chặn `process_kind=model`; commitment proposal nhận `model_manifest_ref` | commitment gateway tests | Chưa có production path model→proposal đầy đủ; ref là chuỗi rời, không bind manifest ID/hash |
| GST validation | `apply_transition()` và `apply_commitment_transition()` | stale/provenance/API tests | Có stale version, evidence subset và human-review gates; chưa bắt buộc snapshot cho mọi AI proposal |
| Persistence | SQLAlchemy models + Alembic 0050–0054 + outbox | migration round trip | “Append-only” chủ yếu theo convention/service API; UPDATE/DELETE trực tiếp vẫn khả thi |
| Derivative stores | state ledger không phụ thuộc vector/cache/model output | architecture + focused tests | Thiết kế đúng hướng; chưa có invariant test quét các write path phụ |
| Benchmark evidence | evaluator, sealed v4/v5 artifacts | artifact validator/checksums | v4 chỉ exploratory; v5 cũ có 64 subjects và power non-tie không đạt, không được tái dùng |

## 3. Gap register ưu tiên

### P0 — chặn confirmatory freeze

1. Ledger chưa chống UPDATE/DELETE ở ORM/DB; canonical projection còn mutate
   `GlhsAssertion.lifecycle_status` và `GlhsConflict.status`.
2. Snapshot manifest thiếu assertion hashes có kiểu rõ ràng; actor ID không nằm
   trong payload hash; “consent basis” mới chỉ là version string.
3. `GlhsClinicalCommitmentProposal.model_manifest_ref` không phải FK và không
   lưu snapshot ID + snapshot hash riêng; GST không tái xác minh expiry, digest,
   policy, consent và disclosed-evidence tại thời điểm commit.
4. CommitLoop THSS không công khai pipeline có thứ tự
   Authorization → Temporal/Lifecycle → Conflict → Relevance/Freshness →
   Minimization, nên khó chứng minh không đảo bước.
5. `current_state_version()` rồi insert `base + 1` không khóa profile/state row;
   SQLite tests chưa chứng minh an toàn trước race PostgreSQL.
6. Protocol tracked vẫn ghi solver v4 và năm primary comparators, trái với runtime
   solver v5 và yêu cầu một primary contrast.

### P1 — reproducibility/security

1. CI API/ML dùng `pip install -e .[dev]`, không `uv sync --frozen`; lock hiện chỉ
   được dùng làm cache key.
2. CI/local test Python 3.11 nhưng image API là Python 3.14; chưa có matrix hoặc
   bằng chứng cùng lock chạy sạch ở cả hai runtime.
3. Chưa có một lệnh network-disabled tái tạo toàn bộ bảng/CI/p-value từ sealed
   outputs; `reanalyze.py` mới tạo một correction artifact riêng.
4. Chưa có fault injection cho commit giữa version/transition/outbox, crash
   recovery, DB trigger tamper, concurrent writers và replay corruption.
5. Chưa đo storage growth, context bytes/tokens, governance overhead và
   throughput theo cùng một harness versioned.

### P2 — evidence scope

1. BTSA chỉ là mechanism mapping, không phải faithful published implementation;
   không dùng làm primary superiority comparator.
2. Real EHR, clinician adjudication, deployed-boundary và PostgreSQL adversarial
   execution đều `NOT_RUN`.
3. Phase B v4 giữ nguyên nhãn exploratory. Cohort v5 64-subject cũ giữ nguyên
   bằng chứng prospective nhưng underpowered theo target non-tie; tuyệt đối
   không tune/recycle.

## 4. Benchmark design ba tầng

1. **Structural/conformance:** deterministic replay, bitemporal boundaries,
   provenance completeness, THSS stage trace, manifest/hash binding, direct and
   stale-write rejection, reconstruction equality.
2. **Adversarial/security/fault:** malformed/tampered/expired/replayed manifests,
   undisclosed evidence, policy/consent drift, cross-profile access, concurrent
   writers, transaction crash/retry, storage corruption and recovery.
3. **Independent model-mediated confirmation:** cohort mới, held-out template
   families, subject-level analysis, frozen model mapping/prompts/schema, invalid
   output = incorrect, không tune sau unblinding.

Primary draft là strict THSS so với authorization-only full history trên
`all_axes_exact_match`, với Claude Sonnet 4.6 là model primary. Đây là comparator
mạnh và trực tiếp kiểm tra giá trị của THSS; Naive RAG, LWW, bitemporal resolver,
GST/THSS ablations và model thứ hai là secondary/exploratory. Primary này chưa
được freeze và có thể được phê duyệt cùng cost gate.

## 5. Power assumptions sơ bộ

Run 64-subject trước có 14/64 non-ties cho Claude strict THSS so với full history.
Không dùng effect quan sát làm kỳ vọng confirmatory. Kế hoạch bảo thủ dùng:

- exact two-sided paired sign test, alpha 0.05;
- xác suất non-tie `q = 0.15` (thấp hơn 14/64);
- xác suất strict thắng khi non-tie `p = 0.70`;
- `N = 384` subjects độc lập, 48 subjects cho mỗi tám held-out strata;
- unconditional exact power `0.8445713131`; sensitivity: `0.65435` tại
  `q=0.10,p=0.70`, `0.58430` tại `q=0.15,p=0.65`, và `0.93431` tại
  `q=0.20,p=0.70`.

Vì power phụ thuộc mạnh vào ties, 384 là sample tối thiểu draft, không phải lời
hứa kết quả. Mọi subject và output lỗi vẫn nằm trong denominator. Benchmark defect
ảnh hưởng kết quả làm run vô hiệu và buộc freeze/cohort mới.

## 6. Implementation plan và file dự kiến thay đổi

1. Integrity schema/immutability: `db/models.py`, migration mới sau 0054,
   `glhs/gateway.py`, `glhs/commitment_gateway.py`.
2. THSS/proposal binding: `glhs/commitment_thss.py`, commitment endpoints và
   schema response/request liên quan.
3. Tests: GLHS gateway, commitment gateway/endpoints/migration, thêm race/fault/
   tamper/replay/performance tests tách biệt SQLite và PostgreSQL.
4. Benchmark: `evaluation/commitloop/{statistics,validate,freeze,run_benchmark}.py`,
   harness conformance/adversarial/performance mới và test tương ứng.
5. Protocol: thư mục `protocols/commitloop/v5-confirmatory/`.
6. Reproducibility: Make target zero-call, workflow CI clean/frozen, environment
   manifest, checksum/tamper verifier.

Không sửa paper. Không gọi provider cho tới khi implementation, cohort và mọi
freeze hash hoàn tất, sau đó dừng để xin phê duyệt chi phí.
