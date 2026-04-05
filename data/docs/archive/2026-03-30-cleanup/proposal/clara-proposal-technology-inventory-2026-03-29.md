# Đề Xuất Công Nghệ Dự Án CLARA (Tổng Hợp Từ Codebase + Research)

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-29  
Phạm vi tổng hợp: toàn bộ `docs/`, `apps/`, `services/`, `deploy/`, `.github/workflows`, `.env.example`

## 1) TỔNG QUAN

CLARA được phát triển như một hệ sinh thái AI y tế gồm 2 nhánh nghiệp vụ chính:
- `CLARA Research`: trợ lý nghiên cứu y khoa đa nguồn, có kiểm chứng và trích dẫn.
- `CLARA Self-Med`: trợ lý an toàn dùng thuốc tại gia đình (DDI, dị ứng, nhắc liều, quản lý tủ thuốc).

Hệ thống đang được triển khai theo kiến trúc lai:
- Lớp sản phẩm: Web và Mobile.
- Lớp API/Gateway: FastAPI hiện tại, định hướng Rust control-plane trong roadmap.
- Lớp AI/ML: LangChain/LangGraph orchestration + RAG + policy gate + fact-check.
- Lớp dữ liệu: DB giao dịch + cache + vector/search/graph stores.
- Lớp quản trị vận hành: Control Tower Dashboard.

## 2) ĐẶT VẤN ĐỀ

Các bài toán trung tâm CLARA đang giải quyết:
- Sai sót dùng thuốc tại nhà (quên liều, trùng liều, tương tác thuốc, dị ứng).
- Truy xuất tri thức y khoa từ nhiều nguồn nhưng vẫn phải kiểm chứng và giải thích được.
- Đảm bảo an toàn dữ liệu cá nhân trong bối cảnh dữ liệu y tế là dữ liệu nhạy cảm.
- Duy trì khả năng vận hành ở quy mô lớn với observability, governance, audit và rollback.

## 3) MÔ TẢ SẢN PHẨM

### 3.1 CLARA Research
- Router theo role/intent.
- Hybrid retrieval (nội bộ + external scientific sources).
- Synthesis + verification (FIDES-lite hiện tại, hướng tới strict verification).
- Xuất kết quả có citation, policy action và verification status.

### 3.2 CLARA Self-Med
- Tủ thuốc số hóa, scan text/file, mapping thuốc.
- DDI check kết hợp local rules + nguồn ngoài (RxNav/openFDA).
- OCR tích hợp qua `tgc-transhub` endpoint adapter.
- Cảnh báo theo mức nguy cơ và luồng escalate an toàn.

### 3.3 CLARA Control Tower
- Quản trị nguồn RAG, cấu hình rag-flow, quan sát chất lượng và dependencies.
- Roadmap mở rộng sang governance release, incident center, compliance và cost board.

## 4) KIẾN TRÚC CÔNG NGHỆ TỔNG THỂ

1. Client layer: Next.js Web + Flutter Mobile.
2. API layer: FastAPI (`services/api`) + auth/RBAC/rate-limit + ML proxy.
3. ML layer: FastAPI (`services/ml`) + router + RAG + fact-check + domain agents.
4. Data layer: PostgreSQL, Redis, Milvus, Elasticsearch, Neo4j, MinIO.
5. External connectors: PubMed, Europe PMC, OpenAlex, Crossref, ClinicalTrials, openFDA, DailyMed, RxNav, SearXNG.
6. Ops layer: Docker Compose, CI quality gates, pre-commit, metrics middleware, dashboard APIs.

## 5) DANH MỤC CÔNG NGHỆ ĐẦY ĐỦ

## 5.1 Công nghệ đang triển khai trong code hiện tại

| Nhóm | Công nghệ | Vai trò trong CLARA | Trạng thái |
|---|---|---|---|
| Ngôn ngữ | Python 3.11 | API + ML services | Đang dùng |
| Ngôn ngữ | TypeScript | Web app | Đang dùng |
| Ngôn ngữ | Dart | Mobile app Flutter | Đang dùng |
| Web framework | Next.js 14.2.8 | Frontend web | Đang dùng |
| UI runtime | React 18.3.1 | Component rendering | Đang dùng |
| HTTP client (web) | Axios | Gọi API từ web | Đang dùng |
| CSS framework | TailwindCSS 3.4.13 | Utility-first styling | Đang dùng |
| CSS tooling | PostCSS + Autoprefixer | Build CSS | Đang dùng |
| Mobile framework | Flutter (SDK >=3.3) | Ứng dụng di động | Skeleton đang dùng |
| Mobile HTTP | package `http` | Gọi API từ app mobile | Đang dùng |
| API framework | FastAPI | REST APIs (api + ml) | Đang dùng |
| ASGI server | Uvicorn | Runtime server Python | Đang dùng |
| Validation | Pydantic v2 | Request/response schemas | Đang dùng |
| Settings | pydantic-settings | Quản lý cấu hình env | Đang dùng |
| ORM | SQLAlchemy 2.x | DB models/query | Đang dùng |
| Migration | Alembic | DB migration | Đang dùng |
| DB driver | psycopg (binary) | Kết nối PostgreSQL | Đang dùng |
| Auth token | python-jose | JWT encode/decode | Đang dùng |
| API networking | httpx | Proxy API và call external services | Đang dùng |
| Multipart | python-multipart | Upload file endpoints | Đang dùng |
| AI orchestration | LangChain | Prompt/tool abstractions | Đang dùng (P0/P1) |
| AI orchestration | LangGraph | Workflow graph orchestration | Đang dùng (PoC + runtime path) |
| Numeric lib | NumPy | ML utility dependency | Đang dùng |
| Model provider | DeepSeek API | Generation fallback/synthesis | Đang dùng |
| Embedding adapter | BGE-M3 stub | Embedding lớp P0 | Đang dùng (stub) |
| Fact-check | FIDES-lite | Kiểm chứng claim/evidence sau synthesis | Đang dùng |
| NLP safety | Regex-based PII redaction | Ẩn phone/id/email trước xử lý | Đang dùng |
| Role routing | P1 Role-Intent Router | Phân loại role + intent + emergency | Đang dùng |
| Streaming | WebSocket endpoint | Token streaming skeleton | Đang dùng |
| OCR integration | tgc-transhub endpoints (`/api/ocr,/api/extract,/ocr`) | OCR scan file cho Self-Med | Đang dùng |
| DDI engine | Local rules + external merge | Cảnh báo tương tác thuốc | Đang dùng |
| External DDI source | RxNav API | RxCUI và interaction list | Đang dùng |
| External safety source | openFDA API | Label/event evidence | Đang dùng |
| Research sources | PubMed E-utilities | Literature retrieval | Đang dùng |
| Research sources | Europe PMC REST | Literature retrieval | Đang dùng |
| Research sources | OpenAlex API | Citation metadata retrieval | Đang dùng |
| Research sources | Crossref API | DOI/metadata retrieval | Đang dùng |
| Research sources | ClinicalTrials.gov API v2 | Trial retrieval | Đang dùng |
| Drug label source | DailyMed API | Drug label retrieval | Đang dùng |
| Web retrieval | SearXNG | Self-host web search connector | Đang dùng |
| Data store | PostgreSQL 16 | DB giao dịch | Đang dùng |
| Cache store | Redis 7 | Cache và queue primitive | Đang dùng |
| Vector DB | Milvus 2.4.12 | Vector search layer | Đang dùng |
| Milvus dependency | etcd 3.5.5 | Metadata store cho Milvus | Đang dùng |
| Milvus dependency | MinIO | Object store cho Milvus | Đang dùng |
| Search engine | Elasticsearch 8.13.4 | Full-text/search analytics | Đang dùng |
| Graph DB | Neo4j 5.22 | Graph knowledge/query layer | Đang dùng |
| Containerization | Docker + Docker Compose | Local infra + app stack | Đang dùng |
| Reverse proxy | Nginx | Route web/api/ml domain deployment | Đang dùng |
| CI/CD | GitHub Actions | CI quality gate | Đang dùng |
| Quality tools | Ruff + mypy + pytest | Lint, type-check, tests | Đang dùng |
| Dev hooks | pre-commit | Chặn lỗi trước push | Đang dùng |
| Build/runtime image | `node:20-alpine`, `python:3.11-slim` | Web/API/ML container images | Đang dùng |

## 5.2 Công nghệ dữ liệu và chuẩn y khoa trong hệ thống

| Nhóm | Công nghệ/Chuẩn | Vai trò |
|---|---|---|
| Drug normalization | RxNorm / RxCUI | Chuẩn hóa thuốc và mapping hoạt chất |
| Drug interaction evidence | RxNav interaction + openFDA + DailyMed | Bằng chứng cảnh báo tương tác/chống chỉ định |
| Literature evidence | PubMed, Europe PMC, OpenAlex, Crossref | Bằng chứng nghiên cứu và citation |
| Trial evidence | ClinicalTrials.gov | Nguồn thử nghiệm lâm sàng |
| VN source integration (config/docs) | DAV, MOH, DI&ADR | Nguồn nội địa cho guideline/pharmacovigilance |
| Web recheck | SearXNG | Đối chiếu nhanh nguồn web có kiểm soát |

## 5.3 Công nghệ bảo mật, an toàn và governance đã có

| Nhóm | Thành phần | Trạng thái |
|---|---|---|
| Authentication | JWT access/refresh | Đang dùng |
| Authorization | RBAC theo role `normal/researcher/doctor/admin` | Đang dùng |
| Rate limiting | In-memory rate limiter middleware | Đang dùng |
| PII/PHI ingress protection | Regex redaction (phone/id/email) | Đang dùng |
| Verification | FIDES-lite verdict (`pass/warn`) | Đang dùng |
| Fallback policy | Fail-soft payload cho ML proxy | Đang dùng |
| Auditability nền | System settings + metrics + traceable response fields | Đang dùng |

## 5.4 Công nghệ frontend/mobile đang có

| Bề mặt | Công nghệ | Ghi chú |
|---|---|---|
| Web app | Next.js + React + TypeScript + Tailwind | Có role-based dashboard và admin surfaces |
| Mobile app | Flutter + Dart + http | Skeleton gồm login/dashboard/research/careguard/council |
| UI integration | Shared API endpoints (`/api/v1/*`) | Web và mobile dùng chung hợp đồng API |

## 6) CÔNG NGHỆ ĐÃ NGHIÊN CỨU TRONG DOCS (ROADMAP/PLANNED)

Các công nghệ dưới đây xuất hiện nhất quán trong research/implementation plans nhưng chưa triển khai đầy đủ end-to-end ở code hiện tại:

| Nhóm | Công nghệ | Vai trò dự kiến | Trạng thái |
|---|---|---|---|
| Backend runtime | Rust (Axum/Actix), control-plane APIs | Gateway, policy, audit, governance, tenant | Roadmap P0-P6 |
| Cross-service contract | gRPC/HTTP versioned contracts | Rust <-> Python orchestration boundary | Roadmap |
| Advanced RAG | GraphRAG | Multi-hop/knowledge graph reasoning | Research |
| Advanced RAG | Self-RAG | Retrieval self-reflection | Research |
| Advanced RAG | CRAG | Corrective retrieval cho query rủi ro cao | Research |
| Advanced RAG | Adaptive-RAG | Route chiến lược retrieval theo độ phức tạp | Research |
| Advanced RAG | RAPTOR | Hierarchical summarization cho tài liệu dài | Research |
| OCR provider | Google Cloud Vision | OCR production-grade candidate | Research/plan |
| OCR provider | AWS Textract | OCR provider candidate | Research/plan |
| OCR provider | Azure Document Intelligence | OCR provider candidate | Research/plan |
| Trial source | WHO ICTRP | Mở rộng registry trial toàn cầu | Research/plan |
| Terminology source | WHO ICD API | Chuẩn hóa ICD-11/10 | Research/plan |
| Premium drug intelligence | DrugBank API | DDI enrichment và management nâng cao | Research/plan |
| Pharmacovigilance | UMC VigiBase / EMA EudraVigilance | ADR signal mở rộng toàn cầu | Research/plan |
| Guideline integration | NICE Syndication API | Nguồn guideline có license | Research/plan |
| Dashboard evolution | Dify-style workflow studio | Visual flow editor + debug + run history | Research/plan |
| Governance | Model/Prompt/Policy Registry, release gates | Vòng đời release và rollback có kiểm soát | Roadmap |
| Incident platform | Incident center + on-call playbook | Vận hành production | Roadmap |
| Enterprise | Multi-tenant governance + cost board | Scale B2B/B2G | Roadmap |

## 7) LỘ TRÌNH ỨNG DỤNG CÔNG NGHỆ (TÓM TẮT)

1. P0-P1: hoàn thiện nền FastAPI + LangChain/LangGraph + connectors cốt lõi + OCR adapter + quality gates.
2. P2: đẩy mạnh Self-Med MVP, research progressive flow, dashboard nghiệp vụ và nguồn chuẩn hóa thuốc.
3. P3: AI council, governance release, kiểm soát an toàn ở mức doctor workflows.
4. P4: hardening production, incident center, DR và performance optimization.
5. P5-P6: enterprise multi-tenant, cost/compliance governance, mở rộng đối tác và liên thông hệ sinh thái.

## 8) TÍNH KHẢ THI

### 8.1 Điểm mạnh hiện tại
- Đã có stack chạy thực tế cho Web/API/ML + infra containerized.
- Đã có connectors y khoa quan trọng (PubMed, ClinicalTrials, RxNav/openFDA, DailyMed).
- Đã có safety foundation (PII redaction, fact-check lite, role/intent routing, fail-soft).
- Đã có tài liệu roadmap chi tiết P0-P6 cho cả product và governance.

### 8.2 Khoảng trống cần đóng
- Chưa hoàn tất migration control-plane Rust.
- Nhiều thành phần advanced RAG đang ở mức nghiên cứu, chưa productionized.
- OCR currently qua adapter; cần benchmark chính thức theo provider strategy.
- Compliance evidence automation và audit explorer vẫn ở mức roadmap.

## 9) ĐỀ XUẤT STACK CHỐT ĐỂ ĐƯA VÀO PROPOSAL NỘP HỘI ĐỒNG

Để cân bằng tính thực tế và tầm nhìn, nên trình bày theo 2 tầng:

1. Tầng `Đang triển khai` (đảm bảo khả thi ngay):
- Next.js + React + Tailwind (Web), Flutter (Mobile).
- FastAPI + SQLAlchemy + PostgreSQL + Redis.
- LangChain/LangGraph + DeepSeek + RAG connectors.
- Docker Compose + CI (Ruff/mypy/pytest) + pre-commit.

2. Tầng `Mở rộng theo lộ trình` (thể hiện năng lực scale):
- Rust control-plane + governance APIs.
- CRAG/Adaptive-RAG/GraphRAG cho quality nâng cao.
- OCR production strategy (GCP/AWS/Azure), premium drug intelligence (DrugBank).
- Control Tower đầy đủ: release governance, incident, compliance, cost, multi-tenant.

## 10) NGUỒN NỘI BỘ ĐÃ TỔNG HỢP

Các nhóm tài liệu/code chính đã được dùng để biên soạn:
- `docs/architecture/*`
- `docs/research/*` (bao gồm các deepdive ngày 2026-03-29)
- `docs/implementation-plan/*`
- `docs/proposal/*`
- `apps/web/*`, `apps/mobile/*`
- `services/api/*`, `services/ml/*`
- `deploy/docker/*`, `deploy/nginx/*`
- `.github/workflows/ci.yml`, `Makefile`, `.env.example`

