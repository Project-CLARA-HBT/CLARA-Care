# CLARA-Care Context (As-built)

Cập nhật: 2026-04-06 (Asia/Saigon)
Repository: `Project-CLARA-HBT/CLARA-Care`
HEAD snapshot: `6bf2820`

## 1) Snapshot nhanh

- Đây là monorepo đã có code triển khai thực tế (không còn ở trạng thái docs-only).
- Mục tiêu sản phẩm: trợ lý y khoa hướng safety-first, không đóng vai trò thay thế bác sĩ.
- Runtime chính:
  - Web: Next.js (`apps/web`)
  - API gateway/business: FastAPI (`services/api`)
  - ML orchestration/RAG: FastAPI (`services/ml`)
  - Mobile: Flutter starter (`apps/mobile`)
- Data plane theo compose: PostgreSQL, Redis, Milvus, Elasticsearch, Neo4j, MinIO; retrieval web qua SearXNG.
- Không tìm thấy file handoff/context tổng quan trước đó tại root (nên tạo file này).

## 2) Cấu trúc repo

```text
.
├── apps/
│   ├── web/      # Next.js frontend production app
│   └── mobile/   # Flutter starter client
├── services/
│   ├── api/      # FastAPI API layer + DB models + Alembic
│   └── ml/       # FastAPI ML layer + routing + RAG + agent modules
├── deploy/
│   ├── docker/   # compose infra/app/deploy stacks
│   └── nginx/    # reverse proxy conf
├── scripts/
│   ├── deploy/
│   ├── demo/
│   ├── docs/
│   ├── ops/
│   ├── release/
│   └── setup/
├── docs/hackathon/
└── data/docs/
```

## 3) Kiến trúc runtime tổng quát

Luồng chuẩn:

1. Web gọi API `/api/v1/*` (cookie + bearer).
2. API xử lý auth/RBAC/consent/rate-limit/DB state.
3. API gọi ML internal endpoints (kèm `X-ML-Internal-Key` nếu có cấu hình).
4. ML chạy router + guardrails + retrieval orchestration + synthesis/verification.
5. API trả payload chuẩn hóa về Web (kèm telemetry/flow events, đặc biệt ở research).

Ports phổ biến khi chạy app compose:

- Web: `127.0.0.1:3100`
- API: `127.0.0.1:8100`
- ML: `127.0.0.1:8110`
- SearXNG: `127.0.0.1:8888`

## 4) API service (`services/api`) - vai trò và luồng chính

### 4.1 Bootstrap + middleware + security

File trọng tâm: `services/api/src/clara_api/main.py`

- Middleware mặc định:
  - CORS (chặn wildcard origin ở production)
  - Auth context middleware
  - Rate limiter middleware
  - API metrics middleware
- Security headers middleware: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control`, HSTS khi HTTPS.
- CSRF middleware:
  - Chỉ áp cho request mutating khi thực sự dùng cookie-auth.
  - Bỏ qua nếu request dùng Bearer token.
  - Exempt một số auth path (login/register/refresh/forgot/reset/verify/resend).
- Production guard tại startup:
  - Chặn JWT secret mặc định.
  - Bắt buộc `AUTH_COOKIE_SECURE=true` nếu production.
  - Bắt buộc `ML_INTERNAL_API_KEY`.
  - Cấm auto-provision user trong production.
  - Chặn password admin bootstrap yếu.
  - Yêu cầu `REDIS_URL` nếu bật distributed limiters.

### 4.2 API Router map

File: `services/api/src/clara_api/api/router.py`

Prefix chung: `/api/v1`

Nhóm endpoint chính:

- `auth`: register, verify-email, login, refresh, forgot/reset password, me, consent status/accept.
- `chat`: chat routed proxy.
- `research`:
  - Conversation CRUD
  - Knowledge sources + documents
  - Tier2 synchronous (`/tier2`) và async job (`/tier2/jobs`, poll + SSE stream)
  - Source hub catalog/records/sync
- `careguard`:
  - Medicine cabinet CRUD + scan text/file + import detections
  - Auto DDI check
  - VN drug dictionary CRUD + audit + resolve
  - `/analyze` proxy ML
- `council`: run/consult/intake.
- `scribe`: SOAP.
- `system`: metrics, dependencies/ecosystem, sources, control-tower config, runtime config careguard, flow events + SSE.
- `workspace`:
  - folders/channels/conversations metadata
  - share links
  - export markdown/docx
  - notes/suggestions/search
- `mobile`: summary endpoint.

### 4.3 Research Tier2 API orchestration (điểm quan trọng)

File lớn: `services/api/src/clara_api/api/v1/endpoints/research.py`

- Chuẩn hóa contract request để tránh drift giữa web/api/ml.
- Hỗ trợ upload tài liệu (text/pdf/image), OCR qua bridge `TGC_OCR_*`.
- Knowledge source theo user:
  - `knowledge_sources`
  - `knowledge_documents`
- Async job engine trong API:
  - Lưu `research_jobs` vào DB.
  - Background worker pool (`RESEARCH_JOB_MAX_WORKERS`) gọi ML.
  - Theo dõi progress/event, merge flow events với progress cục bộ.
  - Expose polling + SSE stream cho UI realtime.
- Chuẩn hóa response telemetry:
  - trace/planner metadata
  - stage status
  - verification matrix
  - stack mode requested/effective

### 4.4 Workspace module

File: `services/api/src/clara_api/api/v1/endpoints/workspace.py`

- Object chính: folder, channel, conversation meta, share token, notes.
- Có luồng export:
  - conversation -> markdown
  - markdown -> DOCX bytes
- Có search + suggestions + share public conversation.

## 5) Database model và migrations

### 5.1 SQLAlchemy models (`services/api/src/clara_api/db/models.py`)

Nhóm model chính:

- Identity/session:
  - `User`, `SessionModel`, `Query`
  - `AuthToken`, `UserConsent`
- Research jobs:
  - `ResearchJob` (status/progress/result/error)
- CareGuard:
  - `MedicineCabinet`, `MedicineItem`
  - `VnDrugMapping`, `VnDrugMappingAlias`, `VnDrugMappingAudit`
- System/runtime settings:
  - `SystemSetting`
- Knowledge source/file RAG:
  - `KnowledgeSource`, `KnowledgeDocument`
- Workspace:
  - `WorkspaceFolder`, `WorkspaceChannel`
  - `WorkspaceConversationMeta`, `WorkspaceConversationShare`
  - `WorkspaceNote`

### 5.2 Alembic versions

`services/api/alembic/versions/`:

- `20260324_0001_init_users_sessions_queries.py`
- `20260325_0002_auth_cabinet_control.py`
- `20260329_0003_knowledge_sources.py`
- `20260330_0004_user_consent_logs.py`
- `20260402_0005_vn_drug_dictionary.py`

## 6) ML service (`services/ml`) - as-built behavior

### 6.1 Endpoint surface

File: `services/ml/src/clara_ml/main.py`

- Health/metrics:
  - `GET /health`, `GET /health/details`
  - `GET /metrics`, `GET /metrics/json`
- Core infer:
  - `POST /v1/chat/routed`
  - `POST /v1/research/tier2`
  - `POST /v1/rag/poc`
- Domain agents:
  - `POST /v1/careguard/analyze`
  - `POST /v1/scribe/soap`
  - `POST /v1/council/run`
  - `POST /v1/council/consult`
  - `POST /v1/council/intake` (form/audio)
- Prompt/debug:
  - `GET /v1/prompts/{role}/{intent}`
- Streaming:
  - `WS /ws/stream`

### 6.2 Internal security + policy guard

- Protected prefixes (`/v1/*`, `/metrics`, `/health/details`) có kiểm tra `X-ML-Internal-Key` khi key được cấu hình.
- Nếu production mà thiếu key thì trả 503 cho protected paths.
- Legal hard guard (regex, vi/en) block các intent:
  - kê đơn
  - chẩn đoán
  - liều dùng cá nhân
- Emergency fastpath:
  - phát hiện symptom cấp cứu -> trả escalation ngay.

### 6.3 Router + flow chat

File: `services/ml/src/clara_ml/routing.py`

- Router phân role (`normal/researcher/doctor`) + intent theo keyword heuristic + confidence.
- Có emergency keyword set tách riêng.

Trong `chat/routed`:

- Nhận `rag_flow` flags từ caller.
- Có profile retrieval tối ưu theo intent/query length (smalltalk/lifestyle/standard).
- Có degrade-path khi upstream lỗi:
  - fallback retrieval an toàn
  - policy_action mặc định chuyển `warn` khi fallback/high-risk factcheck.
- Verification:
  - run FIDES-lite (rule/NLI theo cờ)
  - đính flow events + flow_applied đầy đủ.

### 6.4 RAG pipeline

File: `services/ml/src/clara_ml/rag/pipeline.py`

- Lõi pipeline: retrieve -> synthesize (LLM) -> deterministic local fallback.
- Support retrieval stack:
  - mode `auto` / `full`
  - reason codes cho decision stack mode
- Support:
  - planner hints
  - hybrid internal + external retrieval
  - reranker (optional)
  - GraphRAG sidecar (optional)
  - trace/telemetry chi tiết
- Fallback local luôn có safety wording + refs tối thiểu để không fail hard.

### 6.5 Research Tier2 fast/deep/deep_beta

File: `services/ml/src/clara_ml/agents/research_tier2.py`

- Chuẩn hóa `research_mode`:
  - `fast`
  - `deep`
  - `deep_beta`
- Có planner tạo query plan/source queries/decomposition.
- Deep/Deep Beta có multi-pass retrieval, pass summaries, verification matrix.
- Deep Beta mở rộng thêm:
  - reasoning nodes song song
  - evidence verification node
  - quality gate
  - long-form report synthesis
  - chain status và stage timeline chi tiết
- Trả metadata/telemetry giàu thông tin cho UI và active-eval scripts.

### 6.6 CareGuard + Council + Scribe agents

- CareGuard (`agents/careguard.py`):
  - local DDI rules cache + external source merge
  - VN drug dictionary normalization + active ingredient expansion
  - severity ranking, critical symptom escalation signal
- Council (`agents/council.py`):
  - multi-specialist assessment (cardiology/neurology/nephrology/pharmacology/endocrinology)
  - conflict + consensus + divergence notes
  - citation quality + reasoning timeline
  - neural shadow scoring qua `council_neural`
- Scribe (`agents/scribe_soap.py`): chuẩn hóa SOAP output.

## 7) Web app (`apps/web`) - hành vi chính

### 7.1 Auth/session model

Files trọng tâm:

- `apps/web/middleware.ts`
- `apps/web/lib/http-client.ts`
- `apps/web/lib/auth-store.ts`

Luồng:

- Middleware kiểm tra session cookie/token, redirect login nếu route private.
- HTTP client axios:
  - withCredentials
  - đính bearer token nếu có
  - đính CSRF header cho mutating requests
  - auto refresh token (single-flight) khi 401
  - fallback redirect `/login?next=...` nếu refresh fail
- Token state lưu memory + session/localStorage (để recover trong webview/cross-origin quirks).

### 7.2 Navigation và module theo role

File: `apps/web/lib/navigation.config.ts`

- Role: `normal`, `researcher`, `doctor`, `admin`
- Route chính:
  - `/chat`, `/research`, `/dashboard`
  - `/selfmed`, `/careguard`
  - `/council`, `/scribe` (doctor/admin)
  - admin control tower pages (`/admin/*`)
- Default post-login: `/research`.

### 7.3 Các khu vực màn hình quan trọng

- Research UI có realtime flow timeline/telemetry, mode fast/deep/deep_beta, knowledge sources.
- Chat UI route tới ML routed chat và hiển thị flow/policy context.
- CareGuard UI quản lý tủ thuốc + DDI checks + dictionary admin.
- Council UI gồm intake/consult/result view và các panel phân tích/citation.
- Workspace UI kết nối folder/channel/share/export/notes/suggestions/search.

## 8) Mobile app (`apps/mobile`) - trạng thái hiện tại

- Là Flutter starter, chưa parity đầy đủ với web.
- Màn hình cơ bản:
  - login
  - dashboard
  - research
  - careguard
  - council
- API wiring cơ bản có sẵn.
- Session hiện in-memory (restart app sẽ mất).

## 9) Deploy, CI/CD, Ops, Demo scripts

### 9.1 Compose stacks

- `deploy/docker/docker-compose.yml`: infra local (postgres/redis/milvus/elasticsearch/neo4j/minio/etcd).
- `deploy/docker/docker-compose.app.yml`: api/ml/web/searxng.
- `deploy/docker/docker-compose.deploy.yml`: stack triển khai server.

### 9.2 CI/CD workflows

`.github/workflows/`:

- `ci.yml`: quality/test/build/security checks + smoke tầng scripts/docs.
- `cd.yml`: preflight -> deploy staging -> promote production.
- `release.yml`: semver tag, build/push images, publish release.
- `active-eval.yml`: chạy active eval định kỳ/thủ công.
- `branch-protection-sync.yml`: đồng bộ branch protection policy.

### 9.3 Scripts vận hành nổi bật

- Deploy:
  - `scripts/deploy/redeploy_app_stack.sh`
    - env guard trước deploy
    - rebuild/restart stack
    - smoke API/ML/research deep+deep_beta/careguard
- Ops:
  - `scripts/ops/validate_runtime_env.sh`
  - `scripts/ops/cleanup_disk.sh`
  - `scripts/ops/backup_env.sh`
  - cron installers cho cleanup/backup/source-hub crawl
  - `scripts/ops/source_hub_auto_crawl.sh` cho crawl/sync source hub tự động
- Release:
  - `scripts/release/compute_next_semver.sh`
  - `scripts/release/build_and_push_images.sh`
- Demo/eval:
  - `scripts/demo/run_active_eval_loop.sh`
  - `scripts/demo/run_round2_matrix.sh`
  - `scripts/demo/run_round2_demo_cases.sh`

## 10) Config/env đáng chú ý

File: `.env.example`

- Auth/security:
  - JWT/cookie/csrf/distributed limiter
  - bootstrap admin toggles
- ML/RAG:
  - DeepSeek/Primary LLM runtime
  - external connectors, reranker, NLI, GraphRAG
  - deep_beta knobs (reasoning nodes/rounds/quality gate/report)
- OCR bridge:
  - `TGC_OCR_*`
- Ports cho app/infra compose.

## 11) Tài liệu và mức độ đồng bộ

- README phản ánh khá sát runtime as-built hiện tại.
- `CLAUDE.md` đang lỗi thời nghiêm trọng: vẫn mô tả repo "documentation-only".
- `data/docs/index.md` tham chiếu nhiều path trong `docs/...` theo cấu trúc cũ; không phản ánh đầy đủ split hiện tại giữa `docs/` và `data/docs/` cũng như code đã có thật.

## 12) Ghi chú rủi ro/kỹ thuật cần theo dõi

- Drift tài liệu:
  - `CLAUDE.md` mâu thuẫn với codebase hiện tại.
  - `data/docs/index.md` có tham chiếu path/docs lifecycle không còn đồng bộ hoàn toàn.
- Drift cấu hình:
  - `.env.example` có key `DEEP_BETA_REPORT_MIN_WORDS` lặp lại nhiều lần; giá trị cuối sẽ override, dễ gây hiểu nhầm khi vận hành.
- Security vận hành:
  - Production an toàn phụ thuộc việc set đúng `ML_INTERNAL_API_KEY`, `JWT_SECRET_KEY`, `AUTH_COOKIE_SECURE`, và tắt bootstrap yếu.

## 13) Bản đồ đọc nhanh cho dev mới

Nếu onboard nhanh theo thứ tự:

1. `README.md`
2. API bootstrap + router:
   - `services/api/src/clara_api/main.py`
   - `services/api/src/clara_api/api/router.py`
3. ML bootstrap + routed chat + tier2:
   - `services/ml/src/clara_ml/main.py`
   - `services/ml/src/clara_ml/rag/pipeline.py`
   - `services/ml/src/clara_ml/agents/research_tier2.py`
4. Web auth/research integration:
   - `apps/web/lib/http-client.ts`
   - `apps/web/lib/research.ts`
   - `apps/web/app/research/page.tsx`
5. DB schema + migrations:
   - `services/api/src/clara_api/db/models.py`
   - `services/api/alembic/versions/*`
6. Deploy/Ops:
   - `.github/workflows/*`
   - `deploy/docker/*`
   - `scripts/deploy/redeploy_app_stack.sh`
   - `scripts/ops/validate_runtime_env.sh`

## 14) Kết luận ngắn

CLARA-Care đang ở trạng thái monorepo production-oriented với pipeline research/careguard/council tương đối đầy đủ, có guardrails và degrade-path rõ ràng. Điểm cần ưu tiên tiếp theo là giảm drift tài liệu và chuẩn hóa config/env để vận hành ổn định giữa môi trường local-staging-production.
