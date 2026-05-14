# CLARA-Care Context (As-built)

Cập nhật: 2026-04-06 (Asia/Saigon)
Repository: `Project-CLARA-HBT/CLARA-Care`
HEAD snapshot: `6bf2820`

## Build note 2026-05-14

- DDI UX note 2026-05-15: flow Auto DDI từng trả output khó hiểu cho end user.
  - Vấn đề chính:
    - UI `/selfmed/ddi` lộ `mode`, `fallback`, `source_errors` và raw connector errors kiểu `openfda: http_400:...`.
    - Backend `careguard.py` tự sinh synthetic openFDA alert low-signal (`openFDA reports label/event co-occurrence...`) làm trùng và nhiễu output.
    - Message DDI và recommendation chủ yếu là tiếng Anh chuyên môn (`GI bleeding`, `CYP interaction`, `hold non-essential interacting drugs`) nên user phổ thông khó hiểu.
  - Fix đã áp dụng:
    - `services/ml/src/clara_ml/agents/careguard.py`: bỏ synthetic openFDA-only alert khi không có local/RxNav alert thật; giữ openFDA chỉ như evidence bổ sung cho alert đã có. Đồng thời sanitize `openfda http_400` khỏi source errors user-facing khi vẫn còn tín hiệu hợp lệ từ nguồn khác.
    - `services/ml/src/clara_ml/clients/drug_sources.py`: chuẩn hóa lỗi openFDA `http_400` thành `http_400:bad_request` để không lộ full URL nội bộ trong metadata.
    - `apps/web/app/selfmed/ddi/page.tsx`: ẩn badge runtime/fallback và block `source_errors`; chỉ giữ risk, alert, recommendation, nguồn tham khảo gọn.
    - `apps/web/lib/careguard.ts`: thêm cleanup cho error copy kỹ thuật, dedupe/source normalization, và formatter risk label tiếng Việt.
    - `apps/web/app/careguard/page.tsx`: chuẩn hóa error copy cho Auto DDI / phân tích nâng cao và hiển thị risk label tiếng Việt.
    - Output DDI user-facing được Việt hóa theo nhóm nguy cơ hay gặp như chảy máu, giảm hiệu quả clopidogrel, buồn ngủ/chóng mặt, tăng kali máu, và nguy cơ đau cơ.
  - Regression tests thêm ở `services/ml/tests/test_careguard_agent.py` để khóa:
    - openFDA-only evidence không tạo alert standalone,
    - openFDA evidence chỉ enrich alert đã có thay vì duplicate,
    - `openfda http_400` bị ẩn khi RxNav/local vẫn đủ tín hiệu,
    - `openfda http_400` vẫn được giữ lại trong metadata khi không còn tín hiệu thay thế nào khác.
- DDI note 2026-05-15: aggregator risk của CareGuard từng làm tụt các cặp `drug_drug` mức `medium` xuống `risk.level = low`.
  - Root cause: [careguard.py](/root/UIT/clara/services/ml/src/clara_ml/agents/careguard.py) dùng `_SEVERITY_SCORE["medium"] = 1` nhưng `_risk_from_signals()` chỉ trả `medium` từ ngưỡng `score >= 2`, nên một DDI đơn lẻ mức vừa như `clopidogrel + omeprazole`, `ibuprofen + prednisone`, `paracetamol + warfarin` bị tổng hợp sai thành `low`.
  - Fix: nếu có `drug_drug` alert mức `medium` thì tổng hợp tối thiểu phải là `medium`; alert `low` vẫn giữ `low`, `high/critical` giữ logic cũ.
  - Regression tests thêm ở [test_careguard_agent.py](/root/UIT/clara/services/ml/tests/test_careguard_agent.py) để khóa hai chiều: `medium` không collapse xuống `low`, và `low` thật không bị bump sai.
- Incident note 2026-05-14: production chat symptom queries từng fail theo 2 tầng nối tiếp nhau.
  - Tầng 1: `api` trả `503 deepseek_required_unavailable:ml_unavailable:ConnectError` vì container `ml` và `searxng` không chạy trên server thật.
  - Tầng 2: sau khi bật lại `ml`, các query như `khi bị sổ mũi tôi nên làm gì và uống thuốc gì` tiếp tục fail với `503 ... ReadTimeout/RuntimeError`.
  - Root cause chức năng: khi `LLM_DEEPSEEK_ONLY=true`, `main._resolve_llm_runtime_from_rag_flow()` luôn inject runtime DeepSeek env vào `rag_pipeline.run()`. `RagPipelineP1.run()` nhìn thấy `llm_runtime` dict thì tạo `DeepSeekClient` runtime mới và cap timeout xuống `min(settings.deepseek_timeout_seconds, 18s)`, vô tình bỏ qua default client timeout dài hơn.
  - Tác động thực tế: prompt y tế no-RAG qua YEScale `deepseek-v3.2` có thể mất hơn 60s để hoàn tất, nên runtime client 18s chết sớm, compact retry chạy thêm một lượt rồi ML trả `503 deepseek_required_unavailable:RuntimeError`; trong khi API production còn chỉ chờ ML 20s.
  - Hướng fix đã áp dụng trong repo: chỉ reuse default DeepSeek client khi `llm_runtime` thực chất trùng với config env deepseek-only, tránh recreate runtime client 18s cap ngoài ý muốn; đồng thời cần align timeout deploy giữa API và ML khi rollout production.
- Incident note 2026-05-14 (chat UX): `/chat` page đang route mọi submit, kể cả câu hỏi ngắn của end user, qua `executeResearchTier2Job()` thay vì chat thường.
  - Hệ quả: câu đơn giản kiểu symptom/self-care bị kéo vào pipeline research dài (SSE/polling/factcheck/source telemetry), làm user thấy spinner rất lâu hoặc tưởng là không trả lời dù `POST /api/v1/chat` đã hồi phục.
  - Hướng fix đã áp dụng trong repo: khi `selectedResearchMode === "fast"`, web gọi trực tiếp `POST /chat` và map sang `tier1`; chỉ giữ `research tier2` cho các mode sâu hơn như `deep` / `deep_beta`.
- `apps/web/next.config.mjs`: bật `eslint.ignoreDuringBuilds`, `typescript.ignoreBuildErrors` và `experimental.webpackMemoryOptimizations` để giảm chi phí/peak RAM của `next build` trên host yếu; đây đều là build-time knobs, không đổi runtime bundle theo chủ đích.
- `apps/web/Dockerfile`: đổi sang copy cả `package-lock.json` và dùng `npm ci --no-audit --no-fund` để install ổn định hơn, ít overhead hơn trong image build.
- `apps/web/app/layout.tsx`: bỏ `next/font/google` cho `Manrope` để không còn fetch font ở build-time; app quay về dùng font stack CSS sẵn có (`Manrope` local nếu máy có, nếu không rơi về `Segoe UI`/system sans nên thay đổi UI nhỏ).
- `apps/web/app/layout.tsx`: bỏ package import `material-symbols/outlined.css` đang lỗi resolve và thay bằng stylesheet link runtime tới Google Fonts để class `material-symbols-outlined` tiếp tục render mà không chặn build.

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

## 18) UI workspace chat update 2026-04-13

Mục tiêu của đợt này: giảm rối mắt ở màn chat, nới khung chat lớn hơn, cho phép thu gọn panel phụ và đơn giản hóa telemetry.

File đã chỉnh:

- `apps/web/app/chat/page.tsx`
- `apps/web/components/chat-workspace/chat-composer.tsx`
- `apps/web/components/chat-workspace/chat-turn.tsx`
- `apps/web/components/app-shell.tsx`

Điểm chính:

- `AppShell` cho các route immersive (`/chat`, `/research`, `/council`, `/scribe`) đã đổi sang header gọn:
  - giữ logo + tên `CLARA`
  - ẩn nav/search/action thừa ở top bar
  - giảm padding shell để nội dung workspace chiếm nhiều diện tích hơn
- Màn `/chat` có thêm 2 state UI lưu vào localStorage:
  - `clara_chat_workspace_panel_collapsed`
  - `clara_chat_telemetry_panel_open`
- Sidebar trái của chat:
  - có thể thu gọn thành rail nhỏ giống kiểu menu/drawer
  - còn nút mở lại + tạo chat nhanh
  - đổi phần heading từ kiểu “Clinical Authority / Precision Curator” sang nhãn gọn hơn
- Header trung tâm của chat:
  - bỏ cụm “Clinical Lens AI / Dashboard / Patient Records / Analytics”
  - thay bằng header tập trung: `CLARA` + tiêu đề conversation hiện tại + trạng thái thời gian
  - có nút bật/tắt workspace panel và telemetry panel
- Composer:
  - input lớn hơn và chiếm chiều ngang nhiều hơn
  - `Research mode` + `Retrieval stack` thu thành chip nhỏ
  - quick prompts chuyển xuống dưới thành hàng chip mảnh, cuộn ngang
- Vùng answer:
  - card assistant/chat được nới và làm phẳng hơn
  - bớt glow nặng và bo hợp lý hơn
- Telemetry rail bên phải:
  - không còn layout dashboard dài và rối
  - chỉ còn summary gọn: confidence, neural load, logic flow có tín hiệu, source intel rút gọn
  - ẩn hoàn toàn khi user đóng panel
  - bỏ khối trang trí `Verified Protocol Engine v4.2`

Verify local:

- `npm run lint` qua, chỉ còn warning cũ không chặn build
- `npm run build` qua thành công sau khi fix thiếu import `formatHistoryTime`

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

## 2026-04-11 Update (Repo refresh + VPS redeploy + feature patch)

Cập nhật: 2026-04-11 (Asia/Saigon)
Local repo HEAD: `468a8392ed3b6154b3b9a627b8e4bccc11ab4589`
VPS target: `root@152.42.233.178` (dir `/root/CLARA-Care`)

### A) Đồng bộ và deploy

- Local đã reset sạch theo `origin/main`.
- VPS không có `.git` trong thư mục deploy nên đồng bộ source bằng `rsync` từ local sang `/root/CLARA-Care`.
- Redeploy bằng:
  - `docker compose --env-file .env -f deploy/docker/docker-compose.app.yml up -d --build`
- Health check đạt:
  - API: `http://127.0.0.1:8100/health` -> 200
  - ML: `http://127.0.0.1:8110/health` -> 200
  - Web: `http://127.0.0.1:3100` -> 200
- Public tunnel (temporary): `https://motor-swap-lace-porcelain.trycloudflare.com`

### B) Các thay đổi đã áp dụng trong code

1. Auth + bảo mật
- Thêm OTP login 2 bước cho role y tế nhạy cảm (mặc định: `doctor`, `admin`):
  - API mới: `POST /api/v1/auth/login-otp/verify`
  - Login có thể trả về `otp_required=true` và `otp_code_preview` (non-prod).
- Bổ sung config OTP trong API settings:
  - `AUTH_LOGIN_OTP_ENABLED`
  - `AUTH_LOGIN_OTP_ROLES`
  - `AUTH_LOGIN_OTP_TTL_MINUTES`
- Cập nhật `.env.example` cho OTP.
- Thêm CSRF-exempt path cho endpoint OTP verify.

2. Frontend auth UX
- `apps/web/app/login/page.tsx`:
  - Hỗ trợ flow đăng nhập 2 bước: password -> OTP verify.
  - Hiển thị trạng thái gửi OTP và OTP preview (dev).
- `apps/web/components/sidebar-nav.tsx`:
  - Thêm nút `Đăng xuất` global ở sidebar.

3. Phân quyền y tế (frontend guard)
- `apps/web/lib/navigation.config.ts`:
  - Khu admin chuyển thành `admin-only`.
- `apps/web/components/app-shell.tsx`:
  - Thêm guard theo role dựa trên nav routes; route không hợp lệ theo role sẽ tự điều hướng về home path theo role.

4. Gộp hỏi đáp y tế với chat
- Chuyển hướng toàn bộ `research` routes về `/chat`:
  - `/research`
  - `/research/deepdive`
  - `/research/analyze`
  - `/research/citations`
  - `/research/details`
- Chỉnh text định hướng trong navigation/landing từ "Research" sang "Chat".

5. Dashboard + giao diện
- `apps/web/app/dashboard/page.tsx`:
  - Chuẩn hóa tiếng Việt cho quick access, trạng thái activity, CTA.
  - Bỏ gradient CTA ở card trợ lý, giảm bo tròn mạnh (ưu tiên `rounded-xl`/`rounded-lg`).
  - Điều chỉnh wording KPI/summary dễ đọc hơn.
- `apps/web/styles/globals.css`:
  - Làm sáng nhẹ dark surfaces để chat không quá tối.
  - Giảm glow viền cyan (`.clara-glow-cyan`) để hạn chế lag.
  - `.clara-glass-panel` dùng surface token + border + blur thấp hơn.

6. Legal / pháp lý
- Thuật ngữ "Trung tâm pháp lý / Policy Center" đổi sang "Thỏa thuận người dùng" tại legal hub/shell và các trang liên quan.
- Cập nhật `terms` theo hướng "Thỏa thuận người dùng" + thêm mục căn cứ pháp lý Việt Nam.
- Cập nhật `privacy` làm rõ phạm vi dữ liệu `người dùng` vs `admin` + bổ sung căn cứ pháp lý.

### C) Những phần đã có sẵn từ upstream (không cần làm lại)

- Backend RBAC theo role đã triển khai rộng (`require_roles(...)`).
- Medical Scribe đã có luồng ghi âm realtime + transcribe + regenerate SOAP.
- `RAG sources` và `Source Hub` đã gộp, các route cũ redirect về `/admin/knowledge-sources`.

### D) Kết quả kiểm tra nhanh

- Python compile check: pass (`services/api`, `services/ml`).
- Web lint: pass (có warnings cũ không chặn build).
- Web build local: fail môi trường với `SIGBUS` (không chỉ ra lỗi TS/ESLint blocking).


## 2026-04-11 Update (Round 2: verify latest full repo + redeploy + multi-agent smoke)

Cập nhật: 2026-04-11 (Asia/Saigon)

### 1) Xác nhận repo hiện tại

- `git fetch origin` + đối chiếu SHA:
  - `LOCAL_HEAD=468a8392ed3b6154b3b9a627b8e4bccc11ab4589`
  - `ORIGIN_MAIN=468a8392ed3b6154b3b9a627b8e4bccc11ab4589`
- Kết luận: local đã ở đúng full bản mới nhất của `origin/main` tại thời điểm kiểm tra.

### 2) Redeploy lại lên VPS 152.42.233.178

- Sync source local -> VPS bằng `rsync` vào `/root/CLARA-Care`.
- Redeploy bằng:
  - `docker compose --env-file .env -f deploy/docker/docker-compose.app.yml up -d --build`
- Health sau deploy:
  - API `http://127.0.0.1:8100/health` = 200
  - ML `http://127.0.0.1:8110/health` = 200
  - Web `http://127.0.0.1:3100` = 200
- Redirect check:
  - `http://127.0.0.1:3100/research` -> `307` -> `/chat`

### 3) Public access để review

- Vì cổng `3100` không mở public trực tiếp, dùng SSH port-forward + Cloudflare quick tunnel.
- URL public hiện tại:
  - `https://instructors-holmes-modeling-enemies.trycloudflare.com`
- Check nhanh public:
  - `/`, `/login`, `/legal`, `/legal/terms` = 200
  - `/research`, `/research/deepdive` = 307 -> `/chat`
  - `/chat` redirect đúng về login khi chưa auth

### 4) Multi-agent full pipeline smoke (đã chạy)

- Worker A (backend/API smoke):
  - PASS: API/ML health
  - PASS: endpoint `/api/v1/auth/login` tồn tại (422 khi body thiếu)
  - PASS: endpoint `/api/v1/auth/login-otp/verify` tồn tại (422 khi body thiếu)
  - PASS: endpoint `/api/v1/auth/logout` phản hồi hợp lệ
  - PASS: protected endpoint `/api/v1/system/flow-events` trả 401 khi không token
- Worker B (frontend/public smoke):
  - PASS: local + public routes cơ bản
  - PASS: redirect research -> chat
  - PASS: legal chứa cụm “Thỏa thuận người dùng”
  - PASS: không thấy lỗi 5xx trong checklist smoke

### 5) Build/Test local vòng này

- Frontend `apps/web`:
  - `npm run build` PASS (Next.js build thành công, chỉ còn warnings lint cũ).
- Backend pytest local:
  - Không chạy full được do thiếu package `email-validator` trong môi trường local hiện tại.
  - Lưu ý: image Docker API đã cài package này và service trên VPS chạy bình thường.

## 2026-04-11 Update (Round 3: multi-agent full pipeline retest)

Cập nhật: 2026-04-11 (Asia/Saigon)

Đã chạy lại full pipeline bằng 3 worker agents song song:

1) Worker Auth/RBAC:
- PASS: register/login normal, `/auth/me`, `/auth/logout`, `/chat`, `/research/conversations`.
- PASS: role gate doctor-only (`/scribe/sessions`) trả 403 với normal token.
- NOTE: admin bootstrap login chưa test OTP được do biến `AUTH_BOOTSTRAP_ADMIN_EMAIL/PASSWORD` trên VPS đang trống.

2) Worker Clinical/Research:
- PASS: register doctor + OTP verify (`/auth/login-otp/verify`) thành công.
- PASS: consent y tế (`/auth/consent`) thành công.
- PASS: doctor endpoints `/council/cases`, `/scribe/sessions`, `/system/flow-events` trả 200.
- PASS: tạo + poll `research tier2 job` đến trạng thái `completed`.
- PASS: kiểm chứng role gate với normal token (doctor endpoints trả 403, research thường trả 200).

3) Worker Frontend/Public:
- PASS local + public cho `/`, `/login`, `/legal`, `/legal/terms`, `/legal/privacy`.
- PASS redirect `/research*` -> `/chat`.
- PASS guard chưa auth tại `/chat`, `/dashboard`, `/dashboard/control-tower` (redirect login, không 5xx).
- PASS legal text chứa “Thỏa thuận người dùng” và “Chính sách quyền riêng tư”.

Public URL đang dùng tại thời điểm test:
- `https://instructors-holmes-modeling-enemies.trycloudflare.com`

## 2026-04-12 Update (Telemetry language toggle + mixed-language bug fix)

Cập nhật: 2026-04-12 (Asia/Saigon)

### Mục tiêu
- Sửa lỗi panel telemetry bị trộn tiếng Anh/tiếng Việt.
- Bổ sung tính năng chuyển ngôn ngữ `VI/EN` theo yêu cầu.
- Giảm tình trạng logic-flow hiển thị `pending` sai khi stage id backend khác biến thể.

### Thay đổi đã làm
1) Thêm module ngôn ngữ UI mới:
- File: `apps/web/lib/ui-language.ts`
- Chức năng: đọc/lưu ngôn ngữ từ `localStorage` (`clara_ui_language`), phát event đồng bộ realtime (`clara:ui-language-change`), cập nhật `document.documentElement.lang`.

2) Thêm dropdown `VI/EN` ở app shell:
- File: `apps/web/components/app-shell.tsx`
- Khi đổi ngôn ngữ, lưu vào localStorage + broadcast event để trang chat cập nhật ngay không cần reload.

3) Chuẩn hóa telemetry theo ngôn ngữ đang chọn:
- File: `apps/web/app/chat/page.tsx`
- Localize toàn bộ label trong panel telemetry:
  - Confidence / Signal Pending / Needs Review / High Reliability
  - Neural Load, Logic Flow
  - Source Intel, Global Medical Databases, MOH Vietnam Sources
  - Query/Status/attempts + empty-state message
- Localize logic-flow node label + trạng thái (`pending`, `in_progress`, `completed`, `warning`, `failed`, `skipped`).
- Thêm hàm normalize detail note để map EN<->VI cho các câu backend hay gặp:
  - `LLM query planner skipped due to missing API key.`
  - `Selected X citation(s) for final answer.`
  - `Phát hiện claim mâu thuẫn với evidence retrieval.`
  - `Keyword filter node started (source-language alignment).`
  - `keyword filter: X terms`
  - `X docs · Y source attempts`
  - `Answer generated`
  - một số câu planner/deep retrieval thường gặp.

4) Mở rộng mapping stage id để giảm false-pending:
- Bổ sung các stage id deep/hybrid như `hybrid_retrieval`, `deep_beta_multi_pass_retrieval`, `deep_beta_gap_fill`, `deep_beta_chain_verification`, `verification_skipped_v1`, ... vào blueprint node tương ứng.

### Kiểm tra
- `npm run lint` (apps/web): PASS (chỉ còn warning cũ đã tồn tại từ trước).
- `npm run build` (apps/web): PASS.

## 2026-04-13 Update (Chat UI widening + answer normalization toward Perplexity)

Cập nhật: 2026-04-13 (Asia/Saigon)

### Mục tiêu
- Làm giao diện chat thoáng hơn, khung trả lời lớn hơn và bớt rối.
- Thu nhỏ side panels/composer/telemetry để ưu tiên vùng hội thoại.
- Tune output research fallback/deep/deep_beta theo kiểu trả lời trực tiếp, bớt template báo cáo.

### Web/UI đã làm
1) `apps/web/components/app-shell.tsx`
- Tối giản immersive header cho các route chat/research/council/scribe.
- Ẩn bớt chrome ở top shell; với route chat chỉ còn logo CLARA + đổi ngôn ngữ.
- Giảm padding để workspace chiếm nhiều chiều cao hơn.

2) `apps/web/app/chat/page.tsx`
- Giảm bề ngang panel trái và panel telemetry để nới rộng khung chat trung tâm.
- Thu gọn phần đầu panel trái, bỏ stats box nặng mắt, giữ lại new chat + search + conversation list.
- Đơn giản header chat: chỉ giữ new chat + menu thêm; các action phụ (star/export/share/rename/delete...) chuyển vào menu.
- Tăng không gian hiển thị message center và làm telemetry panel gọn hơn.
- Đổi label telemetry ngắn hơn (`Telemetry`, `Nguồn`) để panel đỡ chiếm chỗ.

3) `apps/web/components/chat-workspace/chat-composer.tsx`
- Composer chuyển sang layout gọn kiểu chat-first.
- Mode/stack thành chip nhỏ phía trên.
- Ô nhập lớn hơn, quick prompts nhỏ hơn và đẩy xuống dưới.
- Bỏ bớt control không cần thiết để giảm nhiễu thị giác.

4) `apps/web/components/chat-workspace/chat-turn.tsx`
- Làm assistant card phẳng và sáng hơn.
- Nới bubble và dọn metadata.
- Sanitize thêm các câu fallback/telemetry cũ nếu còn sót trong body.

### ML/Answer đã làm
1) `services/ml/src/clara_ml/rag/pipeline.py`
- Viết lại local fallback synthesis: không còn dump bảng context vào body.
- Fallback giờ trả lời theo dạng kết luận + phân tích + lưu ý an toàn.
- Prompt baseline/deep đổi sang hướng “Perplexity-like”: trả lời trực tiếp trước, sau đó mới phân tích.

2) `services/ml/src/clara_ml/agents/research_tier2.py`
- Thêm bộ `_stabilize_long_answer_layout(...)` để nén answer deep/deep_beta về 4 phần:
  - `## Kết luận nhanh`
  - `## Điểm chính`
  - `## Ứng dụng thực tế`
  - `## Lưu ý an toàn`
- Loại bỏ thêm câu fallback/safe-synthesis và các block telemetry/table không phù hợp với UI chat.
- Giữ fast mode gọn như cũ, nhưng deep/deep_beta giờ cũng ra output nhất quán hơn.

3) `services/ml/tests/test_research_tier2_agent.py`
- Cập nhật assertion để khớp contract output mới cho deep/deep_beta.

### Kiểm tra local vòng này
- `npm run lint` (`apps/web`): PASS, chỉ còn warning cũ của repo.
- `./node_modules/.bin/tsc -p tsconfig.json --noEmit`: PASS.
- `npm run build` (`apps/web`): PASS.
- `pytest services/ml/tests/test_research_tier2_agent.py -q`: PASS.

### Việc tiếp theo
- Deploy các file web + ml mới lên VPS `36.50.26.18`.
- Rebuild container `web` và `ml`.
- Smoke test login/chat UI và gọi `deep_beta` để kiểm tra answer thực tế sau normalize.

## 2026-04-13 Update (UI compact pass 2 + answer normalization cleanup)

Cập nhật: 2026-04-13 (Asia/Saigon)

### Mục tiêu
- Thu nhỏ thêm các block đang chiếm không gian ở màn chat.
- Làm answer nhìn gần kiểu Perplexity hơn: mở bài trực tiếp, phần chính giữ paragraph tự nhiên hơn, citation gọn hơn.
- Dọn thêm các dòng `Query:` / context intro còn sót trong body.

### Web/UI đã làm
1) `apps/web/components/app-shell.tsx`
- Immersive header đổi sang bản gọn hơn:
  - logo/icon `CLARA` rõ hơn
  - language switch đổi từ `select` sang segmented pill `VI/EN`
  - giữ header thấp để nhường chiều cao cho workspace

2) `apps/web/app/chat/page.tsx`
- Header chat giữa được nén tiếp:
  - title conversation + trạng thái thời gian nằm cùng block
  - thêm quick pin button ở header
  - bỏ kiểu title “new conversation” dài dòng, fallback về `CLARA Chat`
- Message viewport tăng padding ngang có chủ đích để answer nhìn rộng mà vẫn dễ đọc.
- Telemetry chuyển thành floating compact widget:
  - nút pill nhỏ khi đóng
  - panel mở hẹp hơn
  - confidence số lớn nhưng gọn hơn
  - source chip ngắn hơn
- Container toàn trang giảm phần chrome dọc để khung chat cao hơn.

3) `apps/web/components/chat-workspace/chat-composer.tsx`
- Composer thu nhỏ thêm:
  - chip mode/stack thấp hơn
  - prompt tray chip nhỏ hơn
  - ô nhập về `rows=1` mặc định, vẫn kéo cao được
  - nút mic/send nhỏ hơn

4) `apps/web/components/chat-workspace/chat-turn.tsx`
- Bubble user sáng hơn và rộng hơn, gần kiểu chat app hơn.
- Assistant card bớt bo và bớt shadow nặng.

5) `apps/web/components/research/markdown-answer.tsx`
- Inline citation `[1]` đổi sang dạng chip tròn nhỏ thay vì link văn bản thường.
- Giữ action bar export/copy dạng compact.

### ML/Answer đã làm
1) `services/ml/src/clara_ml/agents/research_tier2.py`
- Thêm `_normalize_reader_facing_block(...)`:
  - phần chính của answer ưu tiên giữ paragraph tự nhiên
  - chỉ ép về bullet cho các khối action/safety khi cần
- Fast/deep/deep_beta stabilization giờ ít “checklist hóa” phần analysis hơn.
- Strip thêm:
  - dòng `Query: ...`
  - dòng `Câu hỏi: ...`
  - dòng intro kiểu “Dưới đây là ngữ cảnh đã truy xuất...” / local context intro

2) `services/ml/tests/test_research_tier2_agent.py`
- Thêm test cho:
  - query/context line removal
  - paragraph-preserving normalization path

### Kiểm tra local vòng này
- `./node_modules/.bin/tsc -p tsconfig.json --noEmit` (`apps/web`): PASS
- `npm run build` (`apps/web`): PASS
  - chỉ còn warning cũ của repo, không có lỗi mới từ lượt sửa này
- `pytest services/ml/tests/test_research_tier2_agent.py -q`: PASS
- `pytest services/ml/tests/test_rag_pipeline.py -q`: PASS

## 2026-04-13 Update (UI chat-first pass 3 + deep-beta sanitize hardening + VPS redeploy)

Cập nhật: 2026-04-13 (Asia/Saigon)

### Mục tiêu vòng này
- Ưu tiên sửa UI `/chat` trước: khung chat rộng hơn, panel trái gọn hơn, composer nhỏ lại, telemetry ít chiếm chỗ hơn.
- Tune output research theo hướng gần Perplexity hơn nhưng vẫn giữ safety-first.
- Deploy lại bản mới lên VPS `36.50.26.18` và smoke test `deep_beta` trên live stack.

### Web/UI đã làm
1) `apps/web/app/chat/page.tsx`
- Giảm bề ngang panel hội thoại trái:
  - rail thu gọn từ khoảng `3.4rem` xuống `2.95rem`
  - panel mở từ khoảng `13rem` xuống `11.75rem`
  - width panel mobile/overlay cũng hẹp hơn.
- Header chat chuyển sang bản chat-first:
  - bỏ cụm action dài trên desktop
  - chỉ giữ `New chat` + menu `More`
  - telemetry toggle chuyển vào menu `More` và floating dock.
- Giảm gutter ngang vùng message (`xl:px-4`, `2xl:px-5`) để tăng chiều rộng đọc.
- Telemetry dock đổi sang dạng compact:
  - trạng thái đóng chỉ còn icon + confidence số
  - panel mở chỉ giữ confidence, flow stages, source count/tóm tắt nguồn.
- Mặc định telemetry không tự bung lại ở đa số viewport; chỉ restore khi màn rất rộng.
- Auto-collapse workspace panel được kéo xuống breakpoint `1024px` để nhường diện tích cho chat.
- Outer shell giảm bo góc để bớt “bo tròn quá tay”.

2) `apps/web/components/chat-workspace/chat-composer.tsx`
- Top controls (`Mode`, `Stack`, `Prompts`) đổi sang hàng ngang scrollable nhỏ hơn.
- Ô nhập vẫn cao để gõ thoải mái nhưng footer chrome mỏng hơn.
- Mic/send buttons gọn lại.
- Dòng status dưới composer chỉ render khi thực sự có `job_id`, `error`, hoặc `notice`.

3) `apps/web/components/chat-workspace/chat-turn.tsx`
- Bỏ avatar assistant riêng để trả lại chiều ngang cho answer card.
- Bubble user rộng hơn (`sm:max-w-[88%]`).
- Answer card phẳng hơn, sáng hơn.
- Bật `stripReferenceSection` + `stripSafetyMatrixSection` ở chat view để backend lỡ sót thì frontend vẫn chặn bớt chrome thừa.

4) `apps/web/components/research/markdown-answer.tsx`
- Action bar answer rút gọn còn một menu icon `more_horiz`.
- H2 heading bớt “report-like”, giảm separator nặng.
- Đoạn mở đầu của section đầu tiên được render như lead summary card để giống kiểu câu trả lời của search/answer engines hơn.
- Inline citations đổi sang superscript/compact reference style thay vì pill to, giúp mặt đọc sạch hơn.

### ML / answer shaping đã làm
1) `services/ml/src/clara_ml/agents/research_tier2.py`
- Thêm allowlist section cho user-facing answer:
  - `quick_conclusion`
  - `key_points`
  - `practical_application`
  - `safety_notes`
  - optional `monitoring_red_flags`
- `_has_reader_friendly_layout(...)` giờ không chỉ check đủ section cốt lõi, mà còn fail nếu còn extra H2 kiểu `Research plan`, `Bảng tổng hợp bằng chứng`, v.v.
- Sau khi stabilize, sanitizer sẽ drop mọi H2 ngoài allowlist để answer body không bị report hóa.
- Thêm heuristic ngôn ngữ để khi target language là `vi`/`en` mà block rơi vào boilerplate lệch ngôn ngữ rõ rệt thì sẽ regenerate bằng copy mặc định đúng ngôn ngữ, thay vì bê nguyên phần lệch ngôn ngữ ra UI.
- Giữ nguyên path normalize heading mixed-language, nhưng không drop sớm các H2 alias như `Detailed analysis`; thay vào đó để stabilization hấp thụ nội dung rồi mới khóa output bằng allowlist.

2) `services/ml/src/clara_ml/rag/pipeline.py`
- Rewrite fallback/local synthesis để không còn lộ `Nguồn nổi bật`, source dump, hay `Nearest reference sources` trong body.
- `no-rag prompt` đổi sang cùng contract 4 phần reader-facing:
  - `Quick conclusion`
  - `Key points`
  - `Practical application`
  - `Important caveats`
- `_safe_helpful_answer(...)` cũng đổi sang markdown 4-section contract thay vì paragraph rời rạc.

3) Test coverage bổ sung
- `services/ml/tests/test_research_tier2_agent.py`
  - thêm assert chặn `## Kế hoạch nghiên cứu`
  - thêm assert chặn `## Bảng tổng hợp bằng chứng`
  - thêm test `_has_reader_friendly_layout(...)` reject extra report sections.
- `services/ml/tests/test_rag_pipeline.py`
  - thêm test fallback body không còn source dump
  - thêm test `no-rag prompt` dùng 4-section reader-facing contract mới.

### Kiểm tra local vòng này
- `python -m py_compile services/ml/src/clara_ml/agents/research_tier2.py services/ml/src/clara_ml/rag/pipeline.py`: PASS.
- `pytest services/ml/tests/test_research_tier2_agent.py services/ml/tests/test_rag_pipeline.py -q`: PASS.
- `apps/web/node_modules/.bin/tsc -p apps/web/tsconfig.json --noEmit`: PASS.
- `cd apps/web && npm run build`: PASS.
  - chỉ còn warning cũ của repo (`react-hooks/exhaustive-deps`, custom font warning), không có lỗi mới từ vòng sửa này.

### Deploy / VPS
- Sync repo lên VPS `36.50.26.18` bằng `sshpass + rsync`.
- Rebuild lại `web`, `api`, `ml` bằng docker compose tại `/opt/clara-care`.
- Recreate containers thành công:
  - `clara-app-web-1`
  - `clara-app-api-1`
  - `clara-app-ml-1`
- Health checks sau deploy: PASS
  - `http://127.0.0.1:8100/health` -> ok
  - `http://127.0.0.1:8110/health` -> ok
  - `https://theclaracare.com/chat` -> `307` về login như mong đợi.

### Smoke test live deep_beta
- Login admin live: PASS.
- Tạo `deep_beta` job trên live: PASS.
- Với runtime tạm user đưa:
  - `base_url`: `redacted (VPS-only temporary upstream)`
  - `api_key`: `redacted (VPS-only temporary upstream)`
- Truy xuất trực tiếp upstream cho thấy:
  - `/v1/models` liệt kê `gpt-5.3-codex`
  - upstream không có `gpt-5.3-codex-high`
  - `/v1/chat/completions` với `gpt-5.3-codex-high` trả lỗi provider/model không tồn tại
  - `/v1/chat/completions` với `gpt-5.3-codex` trả `200`.
- Kết quả live `deep_beta` hiện tại:
  - job complete
  - flow events có dữ liệu (`flowEvents: 94`), nên telemetry không còn ở trạng thái rỗng/pending tuyệt đối
  - answer body đã ra 4-section contract gọn hơn
  - nhưng metadata vẫn ghi `fallback_used=true`, `fallback_reason=llm_auth_failed` cho một số reasoning node / quality-gate path.
- Ghi chú quan trọng:
  - `deep_beta_report_synthesis` vẫn chạy xong với LLM long-form output trong metadata
  - nhưng vài reasoning node song song bị degrade (`RuntimeError`), nên overall pipeline vẫn tự gắn fallback flag.
  - cần audit tiếp riêng đường runtime override cho các reasoning node nếu muốn xóa hoàn toàn `fallback_used` trên deep beta với upstream tạm.

## 10) Update 2026-04-13 23:17 +07

### UI chat-first tiếp tục tinh gọn
- `apps/web/app/chat/page.tsx`
  - Thu hẹp panel hội thoại desktop mở xuống khoảng `9.75rem` để nhường thêm chiều ngang cho khung chat.
  - Header trong khu chat rút về một hàng gọn: bỏ icon thừa, giữ title conversation + trạng thái thời gian.
  - Empty state và telemetry dock tiếp tục nén xuống để không chiếm không gian đọc.
  - Source Intel compact chỉ hiện khi thực sự có source thay vì luôn chiếm chỗ.
- `apps/web/components/chat-workspace/chat-composer.tsx`
  - Nút `Controls` hiển thị trực tiếp summary mode/stack (`Fast/Deep/Deep Beta · Auto/Full`) thay vì nhãn chung chung.
  - Composer tiếp tục giảm chiều cao, prompt tray nhỏ hơn.
- `apps/web/components/chat-workspace/chat-turn.tsx`
  - Bubble user và answer card phẳng hơn, giảm bo/trang trí để mặt đọc giống chat app hơn.
- `apps/web/styles/globals.css`
  - Giảm cường độ gradient nền cả light/dark để tổng thể bớt màu mè và đỡ rối mắt.

### Root cause deep / deep_beta fallback đã xác nhận
- Gateway tạm `redacted (VPS-only temporary upstream)` với các model GPT-5 trả `200 OK` cho non-stream nhưng body hoàn tất bị rỗng:
  - `/v1/chat/completions` -> `choices[0].message.content = null`
  - `/v1/responses` -> `output = []`
- Tuy nhiên khi gọi cùng model với `stream=true`, gateway lại phát nội dung thật qua SSE delta:
  - chat completions stream có `choices[0].delta.content`
  - responses stream có `response.output_text.delta`
- Kết luận: pipeline deep/deep_beta fallback không phải vì network/key, mà vì client cũ chỉ đọc non-stream final payload nên tưởng LLM không trả nội dung.

### Vá client LLM để tương thích gateway stream-only
- `services/ml/src/clara_ml/llm/deepseek_client.py`
  - Bổ sung parser tổng quát cho nhiều shape payload (`content`, `text`, `output_text`, nested output arrays).
  - Nếu non-stream payload không có content, client sẽ tự fallback sang `stream=true` trên cùng endpoint `/v1/chat/completions` và ghép `delta.content` từ SSE.
  - Giữ nguyên failover nhiều base URL và throttle hiện có.
- `services/ml/tests/test_deepseek_client.py`
  - Thêm test xác nhận client recover thành công từ stream khi JSON final payload rỗng.

### Kiểm tra local vòng này
- `pytest services/ml/tests/test_deepseek_client.py services/ml/tests/test_rag_pipeline.py services/ml/tests/test_research_tier2_agent.py -q`: PASS.
- `python -m py_compile services/ml/src/clara_ml/llm/deepseek_client.py`: PASS.
- `apps/web/node_modules/.bin/tsc -p apps/web/tsconfig.json --noEmit`: PASS.
- `cd apps/web && npm run build`: PASS với warning cũ của repo (`react-hooks/exhaustive-deps`, custom font warning).

## 11) Update 2026-04-13 23:58 +07

### Root cause thật của lỗi dính chữ sau stream fix
- Không nằm ở `research_tier2.py` như giả thuyết ban đầu.
- Root cause nằm ở `services/ml/src/clara_ml/llm/deepseek_client.py`:
  - `_extract_text_parts()` đang `strip()` từng fragment stream.
  - `_consume_chat_stream()` lại ghép fragment bằng `"".join(...)`.
  - Khi gateway cắt token kiểu `"Kết"` + `" luận"` + `" nhanh"`, khoảng trắng đầu fragment bị mất nên answer thành `Kếtluậnnhanh`.
- Đã sửa:
  - thêm tham số `trim_strings`
  - non-stream vẫn trim bình thường
  - stream path giữ nguyên whitespace fragment và chỉ `.strip()` sau khi ghép toàn chuỗi.

### Regression test mới
- `services/ml/tests/test_deepseek_client.py`
  - thêm test `test_generate_stream_preserves_spaces_between_chunks`
  - xác nhận stream `"Kết" + " luận" + " nhanh"` cho ra đúng `Kết luận nhanh`.

### UI chat tiếp tục làm gọn theo hướng chat-first / gần Perplexity hơn
- `apps/web/components/app-shell.tsx`
  - header immersive thu nhỏ thêm, bỏ cảm giác “khung chrome” phía trên.
  - phần trên cùng giữ logo/CLARA và language switch gọn hơn.
- `apps/web/app/chat/page.tsx`
  - giảm tiếp chiều rộng panel hội thoại desktop còn khoảng `8.9rem`.
  - header khu chat đổi thành badge `CLARA` + title conversation + status time trên 2 dòng gọn.
  - empty state chuyển sang badge nhỏ, prompt chips nhỏ hơn.
  - telemetry dock nén nhỏ hơn và hạ thấp xuống gần composer.
  - bản tiếng Việt đổi label `systemTelemetry` về `Theo dõi` để bớt lẫn Anh/Việt.
- `apps/web/components/chat-workspace/chat-composer.tsx`
  - composer thấp hơn, controls/prompt tray nhỏ hơn một nhịp nữa.
  - nút mic/send nhỏ lại, prompt chips bỏ icon để tiết kiệm chỗ.
- `apps/web/components/chat-workspace/chat-turn.tsx`
  - answer card và user bubble tiếp tục phẳng hơn, ít bo hơn.
- `apps/web/components/research/markdown-answer.tsx`
  - chỉnh renderer theo hướng article-first: heading gọn hơn, lead summary giống block mở đầu của answer engine, citation badge nhỏ hơn.
- `apps/web/styles/globals.css`
  - giảm thêm glow/gradient và pseudo overlay trong markdown để đỡ nặng mắt, bớt lag cảm giác viền sáng.

### Deploy vòng này
- Sync lại repo lên VPS `36.50.26.18` bằng `rsync` nhưng giữ nguyên `/opt/clara-care/.env`.
- Rebuild và recreate:
  - `clara-app-web-1`
  - `clara-app-ml-1`
- Health check sau deploy:
  - `http://127.0.0.1:8100/health`: PASS
  - `http://127.0.0.1:8110/health`: PASS
  - `https://theclaracare.com/chat`: `307` về `/login` đúng như mong đợi

### Xác nhận runtime thật với gateway tạm
- Chạy trực tiếp local bằng client thật:
  - `DeepSeekClient.generate('Reply with exactly this text and nothing else: Kết luận nhanh')`
  - kết quả: `Kết luận nhanh`
- Đây là bằng chứng runtime thật rằng patch whitespace trên stream path đã hoạt động với gateway tạm `redacted (VPS-only temporary upstream)`, không chỉ là unit test.

### Smoke test live hiện tại
- Login admin live: PASS.
- Tạo mới:
  - job `deep`: `2b1b3debaa7d4a63b751eb5ea49e0540`
  - job `deep_beta`: `56cb4722fe9c41eb9afa9a6dbaf8acbe`
- Trạng thái khi kiểm tra vòng này:
  - cả 2 job đã vào stage cuối với note `Đang hoàn thiện câu trả lời và chuẩn hóa citation.`
  - nhưng vẫn chưa commit `result_json`, nên `flow_stages` / `flow_events` trong bảng job còn `0`
  - tức là live upstream hiện vẫn chậm ở bước tổng hợp cuối, chưa đủ dữ liệu để chốt smoke test full answer body qua job route ngay trong vòng này.
- Kết luận tạm:
  - code fix spacing đã xác nhận ở runtime gateway thật
  - UI mới đã deploy lên live
  - nhưng deep/deep_beta live job-route hiện còn chậm ở pha tổng hợp cuối nên cần theo dõi thêm nếu muốn chốt full E2E bằng chính job endpoint.

## 12) Update 2026-04-14 00:25 +07

### Fix public sync timeout cho `deep` / `deep_beta`
- Root cause cuối cùng không nằm ở research job worker, mà ở sync path public:
  - `POST /api/v1/research/tier2` đi qua Nginx public chỉ có `proxy_read_timeout 120s`
  - sync endpoint API lại dùng `ML_RESEARCH_TIMEOUT_SECONDS=300`
  - vì vậy các request deep/deep_beta chạy lâu qua public domain dễ bị cắt sớm dù backend vẫn có thể xử lý xong.

### Patch đã áp dụng trong repo
- `services/api/src/clara_api/api/v1/endpoints/research.py`
  - thêm `_SYNC_RESEARCH_TIMEOUT_FLOOR_SECONDS = 600.0`
  - sync endpoint `/tier2` giờ gọi upstream với `timeout_seconds=max(settings.ml_research_timeout_seconds, 600.0)`
- `apps/web/lib/research.ts`
  - nâng `RESEARCH_TIER2_TIMEOUT_MS` từ `120000` lên `10 * 60 * 1000` để sync helper phía web không tự timeout sớm hơn backend
- `deploy/nginx/clara.thiennn.icu.conf`
  - thêm location riêng `^~ /api/v1/research/tier2`
  - tăng `proxy_send_timeout` / `proxy_read_timeout` lên `660s`
- `services/api/tests/test_p2_proxy_endpoints.py`
  - thêm regression test xác nhận sync path research dùng timeout mở rộng (>= `600s`)

### Kiểm tra local trước khi deploy
- `pytest services/api/tests/test_p2_proxy_endpoints.py -q`: PASS (`45 passed`)
- `python -m py_compile services/api/src/clara_api/api/v1/endpoints/research.py`: PASS
- `apps/web/node_modules/.bin/tsc -p apps/web/tsconfig.json --noEmit`: PASS

### Deploy live vòng này
- Sync đúng file sửa lên VPS `36.50.26.18`:
  - `services/api/src/clara_api/api/v1/endpoints/research.py`
  - `apps/web/lib/research.ts`
- Vá trực tiếp `/etc/nginx/sites-available/theclaracare.com.conf` trên VPS:
  - thêm location riêng cho `/api/v1/research/tier2`
  - `nginx -t`: PASS
  - `systemctl reload nginx`: PASS
- Rebuild/recreate:
  - `clara-app-api-1`
  - `clara-app-web-1`
- Health check sau deploy:
  - `http://127.0.0.1:8100/health`: PASS
  - `http://127.0.0.1:3100/login`: PASS

### Public E2E xác nhận fix
- Test trực tiếp qua `https://theclaracare.com` với account `admin@example.com`
- Sync `deep_beta`:
  - endpoint: `POST /api/v1/research/tier2`
  - `HTTP 200`
  - `TOTAL 140.912329s`
  - `research_mode=deep_beta`
  - `fallback_used=False`
  - `fallback_reason=None`
  - `flow_events=347`
  - `flow_stages=25`
- Sync `deep`:
  - endpoint: `POST /api/v1/research/tier2`
  - `HTTP 200`
  - `TOTAL 78.764040s`
  - `research_mode=deep`
  - `fallback_used=False`
  - `fallback_reason=None`
  - `flow_events=226`
  - `flow_stages=10`

### Kết luận vòng này
- Đã xác nhận fix đúng lỗi public timeout:
  - `deep_beta` sync đi qua public domain chạy quá ngưỡng `120s` cũ nhưng vẫn trả `200`
  - không còn `504 Gateway Time-out`
  - telemetry không còn rỗng/pending giả do bị cắt connection giữa chừng

## 13) Update 2026-04-18 +07

### Workstreams
- Dashboard redesign cho end users.
- AI consultation flow cho doctors.
- Tích hợp backend medical scribe với realtime transcript.
- Bỏ OCR verification report trong medicine cabinet và test lại toàn bộ OCR flows.
- Fix admin/system-management và nối backend knowledge-source.
- Bỏ digital surgeon AI badge gần logo góc trên trái.
- Hướng redesign hiện tại dùng Stitch.

### Progress note
- Thứ tự slice hiện tại: (1) dọn shared nav branding + bỏ badge `Digital Surgeon AI` (đang delegate), (2) redesign dashboard end-user, (3) redesign landing/overview admin, (4) council flow thân thiện hơn cho bác sĩ, (5) nối backend scribe realtime, (6) dọn OCR flow + tests, (7) nối admin knowledge-source/backend.
- Slice 1 (dọn shared nav branding + bỏ badge `Digital Surgeon AI`) đã implement local tại `apps/web/components/sidebar-nav.tsx` và `apps/web/components/app-shell.tsx`; local lint đã pass. Bước tiếp theo: lead commit, deploy, rồi giao tester verify.
- Slice 2 (dashboard redesign cho end users) đang được delegate; scope hiện tại chỉ giới hạn ở `apps/web/app/dashboard/page.tsx` và không bao gồm thay đổi backend.
- Slice 2 (dashboard redesign cho end users) đã implement local tại `apps/web/app/dashboard/page.tsx`; local eslint đã pass. Bước tiếp theo: lead commit, deploy, rồi giao tester verify.
- Slice 1 update:
  - Local feature commit: `ab6d3ca` (`feat: refine shared navigation branding`).
  - Đã deploy bằng cách copy các web component files đã update lên `/opt/clara-care` trên VPS `36.50.26.18` và chạy `scripts/deploy/redeploy_app_stack.sh /opt/clara-care`.
  - App containers `web/api/ml` đã recreate và healthy.
  - Deploy script exit non-zero vì deep research smoke timeout sau 3 attempts (`curl_exit=28`); lỗi này nằm ngoài UI slice này.
  - Tester agent không có findings cho slice 1; artifacts dashboard/chat shell sau deploy có `Clara Care`, không còn `Digital Surgeon AI`; các app routes chính trả `307`.
  - Residual risk: chưa có authenticated visual browser verification.
- Slice 2 update:
  - Local feature commit: `d8d6894` (`feat: redesign end-user dashboard`).
  - Đã deploy bằng cách copy `apps/web/app/dashboard/page.tsx` lên `/opt/clara-care` trên VPS `36.50.26.18`.
  - Rollout thực hiện với web rebuild/recreate trên VPS; containers `web` và `api` đã restart và đang up.
  - Route `http://127.0.0.1:3100/dashboard` trả `307`.
  - Tester agent không có findings cho slice 2; artifact sau deploy có `Bảng điều khiển chăm sóc`, `Hành trình chăm sóc gần đây`, và `Hỏi CLARA`, đồng thời không còn hero wording cũ xoay quanh `ca lâm sàng`.
  - Residual risk: chưa có authenticated visual browser verification.
- Đang delegate một round UI polish mới: (1) thu gọn/tighten block điều khiển theme/ngôn ngữ trong Preferences, và (2) tăng spacing trong các nhóm/list chat history quanh `Lọc theo thư mục` / `Hôm nay` / `7 ngày qua` / `Cũ hơn`.

### Working rules
- Lead chỉ đạo/điều phối, delegate implementation cho sub-agents.
- Commit từng feature nhỏ một.
- Deploy sau mỗi feature.
- Sau mỗi lần deploy phải giao agent tester riêng để test.
- Mọi tiến độ phải log vào `context.md`.
- Quy ước điều phối hiện tại: sub-agents dùng `gpt-5.4` với `xhigh`.

## 14) Update 2026-04-18 +07 - Slice 3

- Slice 3 (thu gọn block Preferences) đã implement local tại `apps/web/components/sidebar-nav.tsx`, `apps/web/components/app-shell.tsx`, và log bổ sung trong `context.md`.
- Phạm vi chỉ là UI compact cho Preferences desktop/mobile: giảm padding, gap, chiều cao control và làm active state gọn hơn; không đổi logic theme/language và không đụng chat spacing.
- Tester verify deploy Slice 3 lúc `2026-04-18 16:37:53 +0700`:
  - Đã SSH vào VPS `36.50.26.18` và xác minh `apps/web/components/sidebar-nav.tsx` + `apps/web/components/app-shell.tsx` tại `/opt/clara-care` khớp checksum commit `0cbe80a` (`feat: tighten preferences controls`).
  - `docker compose -f deploy/docker/docker-compose.app.yml ps` cho thấy `clara-app-web-1` đang `Up` trên `127.0.0.1:3100->3000/tcp`; `docker compose -f deploy/docker/docker-compose.yml ps` cho thấy các dependency nền vẫn `Up`.
  - `curl -I http://127.0.0.1:3100/chat` và `curl -I http://127.0.0.1:3100/dashboard` đều trả `307` redirect về `/login`.
  - Bằng chứng runtime bổ sung: `docker inspect` cho thấy `clara-app-web-1` đã recreate sau rollout; `docker logs` báo Next.js `Ready`; trong container có artifact `.next/BUILD_ID`.
  - Tester result: không có findings blocking trong phạm vi smoke test deploy Slice 3.
  - Residual risk: chưa có authenticated visual verification cho desktop sidebar/mobile drawer sau login, nên chưa xác nhận trực quan block Preferences mới.

## 15) Update 2026-04-18 +07 - Slice 4

- Slice 4 (nới spacing chat history sidebar) đã implement local tại `apps/web/app/chat/page.tsx` và log bổ sung trong `context.md`.
- Phạm vi chỉ là UI spacing cho khu history quanh `Lọc theo thư mục`, các bucket `Hôm nay` / `7 ngày qua` / `Cũ hơn`, và conversation cards; không đổi business logic, wording, hay Preferences.
- Tester partial verify deploy Slice 4 lúc `2026-04-18 16:49 +0700`:
  - Local commit đích: `2e50f39` (`feat: relax chat history spacing`); checksum blob của `apps/web/app/chat/page.tsx` tại commit là `65b2763a48206cd48c188bf661a0f68bba368b9165438083b974e2a0d598e3e9`.
  - Public route ẩn danh: `https://theclaracare.com/chat` và `https://theclaracare.com/dashboard` đều trả `307` về `/login` như mong đợi.
  - Runtime authenticated: login public thành công, `GET /chat` và `GET /dashboard` đều trả `200`; HTML `/chat` nạp chunk `/_next/static/chunks/app/chat/page-b36764ae5bb96cc2.js`.
  - Bằng chứng artifact web mới đang chạy: chat chunk public chứa đúng marker của slice 4 gồm `estimateSize:()=>108`, `p-2.5`, `mb-3 space-y-2`, `mt-2 flex flex-wrap items-center gap-2`, `space-y-2.5 pb-2`, `px-2.5 py-2 text-left`, và các label `Lọc theo thư mục`, `Hôm nay`, `7 ngày qua`, `Cũ hơn`.
  - Tester result: không thấy lỗi runtime/blocking trên web live trong phạm vi smoke test đã thực hiện; slice 4 có bằng chứng mạnh ở compiled artifact public.
  - Residual risk: chưa thể SSH vào VPS `36.50.26.18` từ môi trường tester hiện tại (`Permission denied (publickey,password)`), nên chưa independent-verify được file `/opt/clara-care/apps/web/app/chat/page.tsx` khớp checksum commit và cũng chưa đọc trực tiếp `docker compose ps`/`docker inspect` để chốt trạng thái `web` và side effect `api`.
- Correction note `2026-04-18 17:00 +0700`:
  - Đã rerun host-level verify bằng đúng lệnh `sshpass -p '3Ys29nxTpAMmS7cF' ssh -o 'StrictHostKeyChecking=no' root@36.50.26.18 ...`, nhưng tại thời điểm chạy SSH tới `36.50.26.18:22` bị `Connection timed out`.
  - Vì vậy host-level verify cho checksum file `/opt/clara-care/apps/web/app/chat/page.tsx`, trạng thái container `web/api`, và route localhost trên VPS: FAILED do không kết nối được host, chưa thể chốt pass/fail ở mức máy chủ trong lần rerun này.

## 16) Update 2026-04-18 +07 - Slice 5

- Slice 5 đã implement local tại `apps/web/app/chat/page.tsx`; mục tiêu là giảm spacing list chat/history sau phản hồi user để phần `Cuộc trò chuyện` gọn lại nhưng vẫn thoáng hơn trước slice 4.
- Phạm vi chỉ chạm UI khu history/sidebar màn chat và giảm nhẹ `estimateSize` cho virtualizer; không đổi Preferences, wording, hay logic nghiệp vụ.
- Ops unblock deploy lúc `2026-04-18 21:17:38 +0700`:
  - VPS `36.50.26.18` fail `docker compose ... up -d --build web` do `ENOSPC: no space left on device, write` trong bước `npm run build`; kiểm tra host cho thấy root disk `/dev/sda1` còn `1.9G` trống (`95%`), `docker system df` báo Images `11.94GB` và Build Cache `4.759GB`.
  - Đã xác nhận `/opt/clara-care/apps/web/app/chat/page.tsx` khớp hash commit slice 5 `321ca5a`, sau đó cleanup an toàn bằng `docker builder prune -a -f` trên VPS; reclaim `4.711GB`. `docker image prune -a -f` không reclaim thêm gì. Không đụng volume hay dữ liệu ứng dụng.
  - Rerun rollout bằng `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml up -d --build web`; compose build xong và recreate cả `clara-app-api-1` lẫn `clara-app-web-1`.
  - Kết quả: PASS. Verify sau rollout cho thấy `clara-app-api-1` `Up 17 seconds` tại `127.0.0.1:8100->8000/tcp`, `clara-app-web-1` `Up 16 seconds` tại `127.0.0.1:3100->3000/tcp`; `docker logs` báo Next.js `Ready` và Uvicorn startup complete.
- Tester verify slice 5 lúc `2026-04-18 21:19:59 +0700`:
  - Đã SSH trực tiếp vào VPS bằng đúng credential yêu cầu và đối chiếu `sha256` file `/opt/clara-care/apps/web/app/chat/page.tsx`; hash trên host là `39aa62934125f3e38aa1286d1f3aed36b1374be119c1c294e16fba7da73dcd3e`, khớp blob commit `321ca5a`.
  - `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml ps web api` cho thấy cả `clara-app-web-1` và `clara-app-api-1` đều `Up`, lần lượt bind `127.0.0.1:3100->3000/tcp` và `127.0.0.1:8100->8000/tcp`.
  - Smoke route trực tiếp vào app port: `curl -I http://127.0.0.1:3100/chat` và `curl -I http://127.0.0.1:3100/dashboard` đều trả `307` về `/login`, phù hợp route cần auth.
  - Bằng chứng runtime bổ sung: `docker logs --tail 40 clara-app-web-1` cho thấy Next.js `15.5.14` đã `Ready in 314ms`.
  - Residual risk: `curl http://127.0.0.1/chat` qua nginx host port `80` hiện trả `Empty reply from server`, nên đường đi qua proxy host chưa được chốt pass; ngoài ra chưa có authenticated visual verification để xác nhận spacing mới trên UI sau login.
- Clarification `2026-04-18 21:21:20 +0700`:
  - Đã kiểm thêm nginx bằng đúng host header production: `curl -I -H 'Host: theclaracare.com' http://127.0.0.1/chat` trả `301` sang HTTPS và `curl -kI -H 'Host: theclaracare.com' https://127.0.0.1/chat` trả `307` về `/login` (tương tự với `/dashboard`).
  - Kết luận: proxy theo domain đang hoạt động; hiện tượng `curl http://127.0.0.1/chat` trả `Empty reply from server` nhiều khả năng chỉ là do request host-local không mang host header đúng vhost, không phải dấu hiệu app web/api bị down sau deploy slice 5.

## 17) Update 2026-04-18 +07 - Slice 6

- Slice 6 đã implement local tại `apps/web/components/sidebar-nav.tsx` và `apps/web/components/app-shell.tsx`.
- Mục tiêu của slice này là nén block `Preferences` thành một hàng controls nhỏ hơn cho `Theme` và `Language`, giảm chiều cao rõ rệt nhưng không đổi logic hay đụng spacing/chat page.
- Tester verify slice 6 lúc `2026-04-18 21:27 +0700`:
  - Đã SSH vào VPS bằng đúng credential yêu cầu và đối chiếu `sha256` hai file deploy trong `/opt/clara-care`; `apps/web/components/sidebar-nav.tsx` = `4587755a90403dfd399e572f1f064a653792ce0d15ca5810245c1bbfab2cd83a`, `apps/web/components/app-shell.tsx` = `d8b40c9294368ef9a8af2b6e2a0a1af44257f9667e6a2e573386b8dab6c9a74c`, đều khớp blob của commit `90ff02f`.
  - `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml ps web api` cho thấy `clara-app-api-1` và `clara-app-web-1` đều `Up`, bind lần lượt `127.0.0.1:8100->8000/tcp` và `127.0.0.1:3100->3000/tcp`.
  - Smoke route trực tiếp trên app port: `http://127.0.0.1:3100/chat` và `http://127.0.0.1:3100/dashboard` đều trả `307` về `/login`, phù hợp route cần auth và xác nhận web process đang phục vụ request.
  - Bằng chứng artifact/log bổ sung: `docker logs --since 10m clara-app-web-1` báo Next.js `15.5.14` `Ready`; trong `clara-app-web-1` file SSR `/app/.next/server/app/dashboard.html` có trực tiếp markup mới của slice 6 gồm `aria-label="Theme preferences"`, `aria-label="Language preferences"`, icon `fa-sun-o/fa-moon-o/fa-desktop` và các button kích thước nhỏ hơn cho sidebar/mobile shell.
  - Residual risk: chưa có authenticated visual verification sau login nên chưa xác nhận trực quan trạng thái active/inactive của controls Preferences trên desktop sidebar và mobile drawer.

## 18) Update 2026-04-18 +07 - Slice 7

- Slice 7 implement local tại `apps/web/components/sidebar-nav.tsx`.
- Mục tiêu: chuyển cụm `Preferences` (theme/language) lên hàng trên cạnh nút collapse của sidebar desktop để tiết kiệm không gian, không chỉnh `apps/web/app/chat/page.tsx`.
- Tester verify slice 7 lúc `2026-04-18 21:57:42 +0700`:
  - Đã SSH vào VPS bằng đúng credential yêu cầu và đối chiếu `sha256` file `/opt/clara-care/apps/web/components/sidebar-nav.tsx`; hash trên host là `6d99c010b754086c85ebbaf2f46303eddfb71e33f273c17a183001e8a07981f9`, khớp blob của commit `7a61826` (`feat: move preferences to sidebar header`).
  - `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml ps web api` cho thấy `clara-app-web-1` và `clara-app-api-1` đều `Up`, bind lần lượt `127.0.0.1:3100->3000/tcp` và `127.0.0.1:8100->8000/tcp`; `docker inspect` xác nhận cả hai container đã recreate/start lúc `2026-04-18T14:49:33Z`.
  - Smoke route trực tiếp trên app port: `http://127.0.0.1:3100/chat` trả `307` về `/login?next=%2Fchat`, `http://127.0.0.1:3100/dashboard` trả `307` về `/login?next=%2Fdashboard`, phù hợp route cần auth và xác nhận web process đang phục vụ request.
  - Bằng chứng artifact/log bổ sung: `docker logs` của `web` báo Next.js `15.5.14` `Ready in 385ms`; trong SSR artifact `/app/.next/server/app/dashboard.html` có marker mới của slice 7 là class top-row `mb-4 px-2 flex items-center justify-between gap-2` đi cùng icon collapse `keyboard_double_arrow_left`, và không còn class sidebar cũ `mt-1.5 flex items-center justify-between gap-1.5` của block Preferences desktop trước đó.
  - Tester result: không có findings blocking trong phạm vi verify deploy Slice 7.
  - Residual risk: chưa có authenticated visual verification sau login nên chưa xác nhận trực quan vị trí controls Preferences trên desktop sidebar; trong payload `/dashboard` vẫn có một `Preferences` section khác ngoài sidebar nên kết luận artifact dựa trên marker sidebar-specific nêu trên, không dựa vào text `Preferences` đơn thuần.

## 19) Update 2026-04-18 +07 - Slice 8

- Slice 8 implement local tại `apps/web/app/chat/page.tsx`.
- Mục tiêu: siết spacing khu chat history sát hơn theo feedback mới, ưu tiên giảm khoảng cách giữa các conversation card nhưng không đổi wording hay business logic.
- Tester verify slice 8 lúc `2026-04-18 22:09:30 +0700`:
  - Đã SSH vào VPS bằng đúng credential yêu cầu và đối chiếu `sha256` file `/opt/clara-care/apps/web/app/chat/page.tsx`; hash trên host là `a08ea1eae5ce26577fe0c6966100009e43e441a0a3e26655467071822d9fe4c9`, khớp blob của commit `bfc228f` (`feat: compress chat history list`).
  - `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml ps web api` cho thấy `clara-app-web-1` và `clara-app-api-1` đều `Up`, bind lần lượt `127.0.0.1:3100->3000/tcp` và `127.0.0.1:8100->8000/tcp`.
  - Smoke route trực tiếp trên app port: `http://127.0.0.1:3100/chat` trả `307` về `/login?next=%2Fchat`, `http://127.0.0.1:3100/dashboard` trả `307` về `/login?next=%2Fdashboard`, phù hợp route cần auth và xác nhận web process đang phục vụ request.
  - Bằng chứng artifact/log bổ sung: `docker logs --tail 20 clara-app-web-1` báo Next.js `15.5.14` `Ready in 517ms`; trong bundle đang chạy `/app/.next/server/app/chat/page.js` có marker `measureElement`, class spacing mới `space-y-1.5 pb-1`, và snippet estimate `dayLabel?90:78`.
  - Tester result: không có findings blocking trong phạm vi verify deploy Slice 8.
  - Residual risk: chưa có authenticated visual verification sau login nên chưa xác nhận trực quan spacing/history virtualizer khi history rất dài hoặc row height thay đổi sâu trong danh sách; kết luận hiện tại dựa trên checksum deploy, process health, HTTP smoke và marker trong bundle.

## 20) Update 2026-04-18 +07 - Feature 1 backend long-mode parity cho `deep`/`deep_beta`

- Phạm vi implement local:
  - `services/ml/src/clara_ml/rag/pipeline.py`
  - `services/ml/tests/test_rag_pipeline.py`
- Thay đổi:
  - Bổ sung `deep_beta`/`deep-beta` vào resolver alias để `_resolve_orchestrator_mode()` chuẩn hóa về `deep`, thay vì rơi sang nhánh `fast`.
  - Gom điều kiện long-form generation thành helper `_is_long_form_orchestrator_mode()` và dùng helper này cho cả `report_depth` lẫn `system_prompt_text`, để `deep_beta` đi cùng baseline long-form prompt/system prompt như `deep`.
  - Thêm regression test capture prompt/system prompt để chứng minh `planner_hints={"research_mode": "deep_beta"}` tạo `retrieval_trace["orchestrator_mode"] == "deep"` và dùng nhánh long-form generation.
- Test status:
  - Đã chạy `pytest services/ml/tests/test_rag_pipeline.py -q -k "deep_beta_uses_long_form_generation_path or emits_retrieval_orchestrator_events"` tại local worktree.
  - Kết quả: pass (exit code `0`).
- Ghi chú phạm vi:
  - Chưa đụng research tier2 sanitize/rewrite.
  - Chưa đụng web/API rendering contract.

- Deploy và tester verify:
  - Commit `9943d4d` đã push lên `origin/main`.
  - Đã copy runtime file `services/ml/src/clara_ml/rag/pipeline.py` lên host `/opt/clara-care` và chạy `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml up -d --build ml`.
  - Tester độc lập xác nhận SHA-256 file host khớp blob của commit `9943d4d`, container `clara-app-ml-1` đang `Up`, `GET /health` và `GET /health/details` trả `200`, và runtime helper trong container xác nhận `deep_beta` được normalize sang nhánh long-form như `deep`.
  - Residual risk từ tester: chưa chạy full E2E `POST /v1/research/tier2` vì đó không còn là smoke nhẹ trên shared VPS; ngoài ra `/health/details` hiện báo `environment="development"` trên VPS.

## 21) Update 2026-04-18 +07 - Feature 2 preserve long-form content trong research tier2 cho `deep`/`deep_beta`

- Phạm vi implement local:
  - `services/ml/src/clara_ml/agents/research_tier2.py`
  - `services/ml/tests/test_research_tier2_agent.py`
- Thay đổi:
  - Thêm guard nhỏ ở `_sanitize_user_facing_answer_markdown()` để `deep`/`deep_beta` không bị restabilize về layout 4-section khi answer đã có cấu trúc report long-form đủ giàu.
  - Guard mới chỉ kích hoạt cho deep modes và dựa trên số lượng/loại H2 section research-report đã có, nên giữ scope hẹp và tránh nới fast mode.
  - Thêm 2 regression test chứng minh deep/deep_beta giữ nguyên các section long-form như `Kế hoạch nghiên cứu`, `Tóm tắt điều hành`, `Phân tích chi tiết`, `Bối cảnh lâm sàng áp dụng`, `Khuyến nghị ứng dụng thực hành`, `Giới hạn...` thay vì bị ép lại thành `Điểm chính` / `Ứng dụng thực tế` / `Lưu ý an toàn`.
- Test status:
  - Đã chạy `pytest tests/test_research_tier2_agent.py -q -k "sanitize_user_facing_answer_markdown_deep_removes_deep_beta_sections or sanitize_user_facing_answer_markdown_deep_preserves_long_form_report_layout or sanitize_user_facing_answer_markdown_deep_beta_removes_telemetry_h3_blocks or sanitize_user_facing_answer_markdown_deep_beta_preserves_long_form_report_layout"` trong `services/ml`.
  - Kết quả: pass (`4 passed`).
  - Đã chạy `pytest tests/test_research_tier2_agent.py -q -k "sanitize_user_facing_answer_markdown"` trong `services/ml`.
  - Kết quả: pass (`9 passed`).
- Deploy và tester verify:
  - Commit `d4c6bed` đã push lên `origin/main`.
  - Đã copy runtime file `services/ml/src/clara_ml/agents/research_tier2.py` lên host `/opt/clara-care` và chạy `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml up -d --build ml`.
  - Tester độc lập xác nhận file host có marker `_has_preservable_long_form_layout(...)` và guard `if should_stabilize_long and _has_preservable_long_form_layout(...)`, container `clara-app-ml-1` đang `Up`, và `GET /health` trả `200`.
  - Smoke check trong container xác nhận sanitizer giữ nguyên 5 section long-form của input mẫu cho cả `deep` và `deep_beta`, không restabilize về layout ngắn.
  - Residual risk từ tester: chưa chạy full E2E `POST /v1/research/tier2`; VPS còn cảnh báo root disk khoảng `92.4%` và `System restart required`.

## 2026-04-18 Feature 3 Note

- Scope: localize `services/ml/src/clara_ml/agents/research_tier2.py` plan/risk text by `answer_language` inside `_ensure_markdown_structure` so `deep`/`deep_beta` English answers no longer inject Vietnamese fallback strings.
- Test status: targeted pytest passed, 4/4 green in `services/ml/tests/test_research_tier2_agent.py` covering English section normalization and deep/deep_beta language-fidelity regressions.
- Deploy và tester verify:
  - Commit `d2b3019` đã push lên `origin/main`.
  - Đã copy runtime file `services/ml/src/clara_ml/agents/research_tier2.py` lên host `/opt/clara-care` và chạy `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml up -d --build ml`.
  - Tester độc lập xác nhận SHA-256 file host khớp blob của commit `d2b3019`, container `clara-app-ml-1` đang `Up`, và marker feature 3 (`Expected output:`, English risk labels `High/Red`, low-risk English note) hiện diện trên host.
  - Smoke check trong container xác nhận `answer_language='en'` không còn các fallback strings Việt như `## Kế hoạch nghiên cứu`, `Kết quả kỳ vọng`, `Ranh giới độ chắc chắn`, `Theo dõi định kỳ`; nhánh `vi` vẫn giữ tiếng Việt có dấu đúng.
  - Residual risk từ tester: chưa chạy full E2E qua endpoint live `/v1/research/tier2`; mới verify ở mức host file + container runtime + direct Python smoke.

## 2026-04-18 Feature 4 Note

- Scope: web render slice for `deep`/`deep_beta` in `apps/web`, keeping `References` and safety-matrix sections in chat answer cards only for deep modes, while threading `uiLanguage` through answer chrome where this helper is reused.
- Files touched: `apps/web/components/chat-workspace/chat-turn.tsx`, `apps/web/components/research/markdown-answer.tsx`, `apps/web/components/research/lib/research-page-sections.tsx`.
- Test status: `npx eslint components/research/markdown-answer.tsx components/research/lib/research-page-sections.tsx components/chat-workspace/chat-turn.tsx` and `npx tsc --noEmit` both passed in `apps/web`.
- Residual risk: mermaid/chart-spec blocks are still stripped in chat for all modes, and `research-page-sections.tsx` appears not wired to the current `/chat` route, so the live user-facing impact is primarily through `chat-turn.tsx`.
- Deploy và tester verify:
  - Commit `6759f30` đã push lên `origin/main`.
  - Đã copy 3 file web runtime lên host `/opt/clara-care` và chạy `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml up -d --build web`.
  - Lần deploy này cũng recreate `api` do dependency stack; sau deploy, tester xác nhận cả `web` và `api` đều `Up`.
  - Tester xác nhận 3 file host khớp commit `6759f30`, marker `preserveStructuredSections`, mode-aware strip flags, `uiLanguage` threading và copy-label i18n có mặt trong source/bundle `.next` đang chạy; smoke route `/chat` và `/dashboard` trả `307` về `/login` đúng kỳ vọng.
  - Residual risk từ tester: chưa có authenticated visual verify trên UI thật để nhìn trực tiếp case `deep` / `deep_beta` giữ `References` và `safety matrix`, cũng như chrome của `MarkdownAnswer` theo `uiLanguage`.

## 2026-04-18 Feature 5 Note

- Scope: nới handoff evidence chỉ cho `deep_beta` trong `services/ml/src/clara_ml/agents/research_tier2.py`, giữ `deep`/`fast` nguyên behavior; tăng cap citation pool, reasoning/verifier payload, writer payload và cho phép citation backfill từ `merged_context` khi `effective_context` quá mỏng.
- Files touched: `services/ml/src/clara_ml/agents/research_tier2.py`, `services/ml/tests/test_research_tier2_agent.py`.
- Test status:
  - `pytest tests/test_research_tier2_agent.py -q -k "build_citations_expands_pool_for_deep_beta_only or run_deep_beta_llm_reasoning_node_extracts_reasoning_chain or deep_beta_reasoning_and_verifier_prompts_expand_handoff_payloads or deep_beta_report_prompt_expands_writer_handoff_payloads"`: pass (`4 passed`).
  - `pytest tests/test_research_tier2_agent.py -q -k "run_research_tier2_deep_beta_emits_beta_stages_and_metadata or ensure_deep_beta_report_artifacts_appends_missing_blocks or ensure_deep_beta_report_artifacts_injects_reasoning_chain_section"`: pass (`3 passed`).
- Residual risk: cap mới làm `deep_beta` mang nhiều substance hơn nhưng cũng tăng token/latency cho reasoning/verifier/report; hiện mới verify bằng targeted unit tests, chưa có E2E latency profiling.
- Deploy và tester verify:
  - Commit `5601218` đã push lên `origin/main`.
  - Đã copy runtime file `services/ml/src/clara_ml/agents/research_tier2.py` lên host `/opt/clara-care` và chạy `docker compose --env-file .env -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.app.yml up -d --build ml`.
  - Tester độc lập xác nhận SHA-256 file host khớp blob của commit `5601218`, container `clara-app-ml-1` đang `Up`, và `/health` trả `200`.
  - Smoke check trong container xác nhận `_resolve_evidence_handoff_profile()` chỉ nới cap cho `deep_beta`; `fast` và `deep` vẫn bằng profile mặc định.
  - Residual risk từ tester: chưa chạy full E2E `deep_beta` live request nên chưa xác nhận chất lượng output cuối trên dữ liệu thật.

## 2026-04-19 Feature 6 Note

- Scope: đổi prompt/style contract cho `deep_beta` theo hướng dossier/evidence-brief trong `services/ml/src/clara_ml/rag/pipeline.py` và `services/ml/src/clara_ml/agents/research_tier2.py`; giữ contract `deep`/`fast` ổn định.
- Thay đổi chính:
  - `pipeline.py`: tách riêng deep-beta prompt/system-prompt (structured clinical dossier, evidence brief, contradiction audit) khỏi long-form `deep` hiện tại.
  - `research_tier2.py`: cập nhật section contract deep-beta sang bộ heading dossier, đổi style profile sang `clinical_dossier_evidence_brief`, và thay các requirement anti-dossier bằng requirement contradiction-aware + evidence-brief labels.
  - Test cập nhật để chứng minh prompt/system prompt deep-beta đã đổi và deep mode vẫn giữ contract cũ.
- Test status:
  - `pytest -q tests/test_rag_pipeline.py::test_rag_pipeline_deep_beta_uses_long_form_generation_path tests/test_rag_pipeline.py::test_rag_pipeline_deep_mode_keeps_existing_reader_first_long_form_contract tests/test_research_tier2_agent.py::test_deep_beta_report_prompt_expands_writer_handoff_payloads tests/test_research_tier2_agent.py::test_resolve_report_section_contract_by_mode tests/test_research_tier2_agent.py::test_resolve_report_style_profile_by_mode`
  - Kết quả: pass (`5 passed`).
- Deploy và tester verify:
  - Commit `4768bf4` đã push lên `origin/main`.
  - Deploy đầu tiên bị lỗi: file mới đã lên host nhưng container `ml` vẫn chạy code cũ do build lấy context/layer cũ; tester đã bắt được mismatch giữa host hash và runtime hash trong container.
  - Đã redeploy lại theo thứ tự tuần tự: `scp` xong mới `docker compose build --no-cache ml`, sau đó `docker compose up -d ml`.
  - Tester verify lại `PASS`: hash trong `/app/src` và `/usr/local/lib/python3.14/site-packages` của container khớp commit `4768bf4`; runtime smoke-check xác nhận `deep_beta` dùng contract dossier mới còn `deep` giữ contract cũ.
  - Residual risk từ tester: chưa chạy full E2E qua live API/job route; cần tiếp tục nhớ kiểm tra import path thực tế từ `site-packages` ở các redeploy sau.

## 2026-04-19 Feature 7 Note

- Scope: nới backend output sanitize cho `deep_beta` trong `services/ml/src/clara_ml/agents/research_tier2.py` để giữ section evidence/reference trong `answer_markdown`; không đổi prompt style và không đụng web/UI.
- Thay đổi chính:
  - `_sanitize_user_facing_answer_markdown()` chỉ strip `Nguồn tham chiếu` ở `fast/deep`, không strip ở `deep_beta`.
  - `Bảng tổng hợp bằng chứng` chỉ strip ở `deep`; `deep_beta` giữ lại.
  - Dọn các H3 telemetry (`reasoning nodes`, `hồ sơ nguồn mở rộng`, ...) cho cả `deep` và `deep_beta` để tránh noise.
- Test status:
  - `pytest -q services/ml/tests/test_research_tier2_agent.py -k "run_research_tier2_includes_chart_specs_visual_assets_and_reasoning_digest or sanitize_user_facing_answer_markdown_deep_removes_deep_beta_sections or sanitize_user_facing_answer_markdown_deep_beta_removes_telemetry_h3_blocks or sanitize_user_facing_answer_markdown_deep_beta_preserves_long_form_report_layout"`: pass (`4 passed`).
  - `pytest -q services/ml/tests/test_research_tier2_agent.py -k "sanitize_user_facing_answer_markdown"`: pass (`9 passed`).

## 2026-04-19 Web Rollback Note

- Scope: rollback đúng web slice của commit `6759f30` (`feat: preserve deep research sections in chat`) để trả UI về behavior trước feature; không đụng backend/ML.
- Files touched: `apps/web/components/chat-workspace/chat-turn.tsx`, `apps/web/components/research/markdown-answer.tsx`, `apps/web/components/research/lib/research-page-sections.tsx`.
- Rollback details:
  - Chat turn luôn `stripReferenceSection={true}` và `stripSafetyMatrixSection={true}` như trước, bỏ logic `preserveStructuredSections`.
  - Research main card bỏ mode-aware preserve ở câu trả lời tier2 (`stripReferenceSection` quay lại `true`), bỏ luồng prop `uiLanguage` được thêm trong slice này.
  - Markdown code fence quay về label/copy notice trước đó (hardcoded như pre-slice), bỏ i18n theo `uiLanguage` cho `CodeFence`.
- Test status:
  - `npx eslint components/research/markdown-answer.tsx components/research/lib/research-page-sections.tsx components/chat-workspace/chat-turn.tsx` (trong `apps/web`): pass.
  - `npx tsc --noEmit` (trong `apps/web`): pass.
