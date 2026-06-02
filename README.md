# CLARA-Care

[![Kiểm thử tích hợp](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/ci.yml/badge.svg)](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/ci.yml)
[![Phát hành](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/release.yml/badge.svg)](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/release.yml)
[![Triển khai](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/cd.yml/badge.svg)](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/cd.yml)
[![Giấy phép](https://img.shields.io/github/license/Project-CLARA-HBT/CLARA-Care)](LICENSE)
[![Website](https://img.shields.io/badge/Website-clara.thiennn.icu-0A66C2?logo=google-chrome&logoColor=white)](https://clara.thiennn.icu)

Nền tảng trợ lý y khoa đa mô-đun theo định hướng **Safety-first AI** cho bối cảnh gia đình và hội chẩn tham khảo.

CLARA không định vị là “AI bác sĩ”. Hệ thống ưu tiên:
- cảnh báo rủi ro sớm,
- trích dẫn nguồn minh bạch,
- và cơ chế fallback an toàn khi upstream lỗi.

## 1) CLARA khác gì thị trường?

Thay vì cạnh tranh bằng “trả lời nhanh nhất”, CLARA tập trung vào **độ tin cậy vận hành + biên an toàn y khoa**.

### 1.1 Legal Hard Guard ở tầng backend (không chỉ prompt)
- Chặn cưỡng chế các yêu cầu vượt ranh giới pháp lý: kê đơn, chẩn đoán, liều dùng cá nhân.
- Guard chạy ở service ML/API, không phụ thuộc duy nhất vào system prompt.
- Mục tiêu: giảm rủi ro “hallucination có hại” trong use-case y tế.

### 1.2 Hybrid Retrieval có degrade-path rõ ràng
- Kết hợp nguồn nội bộ + nguồn ngoài (scientific/web connectors) + index cục bộ.
- Khi upstream lỗi, hệ thống chuyển sang chế độ fail-soft có metadata cảnh báo rõ nguyên nhân.
- Với CareGuard/DDI: có luồng fallback luật cục bộ để tránh “tịt ngòi” khi demo hoặc mất mạng.

### 1.3 Council AI theo mô hình “human-in-the-loop ready”
- Hội chẩn đa chuyên khoa với conflict list, consensus, divergence notes.
- Timeline suy luận và citation quality để reviewer theo dõi logic từng bước.
- Neural scoring chạy **shadow mode** (decision support), chưa thay thế rule-engine.

### 1.4 Demo Resilience thiết kế từ đầu
- Có gate deploy + smoke test cho research/careguard/auth.
- Có env guard để chặn deploy với cấu hình DB/DeepSeek sai.
- Có cron cleanup/backup để vận hành bền vững trên hạ tầng hạn chế tài nguyên.

## 2) Product modules (as-built)

### 2.1 CLARA Research
- Chat routed + Research Tier2 (`fast` / `deep` / `deep_beta`).
- Flow telemetry theo stage (planner/retrieval/llm/verification).
- Citation + metadata để phục vụ review nội bộ.

### 2.2 CLARA Self-MED / CareGuard
- Quản lý tủ thuốc cá nhân (cabinet).
- Quét text/file toa thuốc và đưa vào workflow DDI.
- DDI pipeline kết hợp local rules + nguồn ngoài.

### 2.3 CLARA Council
- Intake -> hội chẩn -> workspace phân tích.
- Các màn chuyên biệt: Analyze / Details / Citations / Research / Deepdive.
- Result hiển thị consensus quality + escalation + reasoning timeline + neural shadow risk.

### 2.4 CLARA Scribe (nền)
- SOAP scribe ở mức nền để chuẩn hóa đầu ra ghi chú lâm sàng tham khảo.

## 3) Kiến trúc runtime

```text
Web (Next.js)  <->  API (FastAPI)  <->  ML (FastAPI)
                         |               |
                         |               +-- Routing / Guardrails / RAG / Council
                         |
                         +-- Auth / RBAC / Consent / Proxy / Observability

Data plane: PostgreSQL, Redis, Milvus, Elasticsearch, Neo4j
Retrieval gateway: SearXNG + scientific connectors
```

Cổng mặc định khi chạy compose app:
- Web: `127.0.0.1:3100`
- API: `127.0.0.1:8100`
- ML: `127.0.0.1:8110`
- SearXNG: `127.0.0.1:8888`

## 4) Cấu trúc repo

```text
.
├── apps/
│   ├── web/                 # Next.js frontend
│   └── mobile/              # Flutter skeleton
├── services/
│   ├── api/                 # FastAPI API layer
│   └── ml/                  # ML orchestration layer
├── deploy/
│   ├── docker/              # compose stacks
│   └── nginx/               # reverse proxy conf
├── scripts/
│   ├── deploy/              # redeploy script + smoke
│   ├── demo/                # benchmark/demo artifact scripts
│   ├── ops/                 # cleanup/cron/env guard/backup
│   ├── rag_seed/            # seed/crawl tooling
│   └── release/             # semver/image release helpers
├── docs/hackathon/          # docs cần cho vòng thi/CI docs-check
└── data/docs/               # kho tài liệu nội bộ mở rộng
```

## 5) Quick start (Docker)

### 5.1 Chuẩn bị
```bash
cp .env.example .env
make check-env
```

### 5.2 Chạy hạ tầng nền
```bash
make docker-up
make docker-ps
```

### 5.3 Chạy app stack
```bash
make docker-app-up
make docker-app-ps
```

### 5.4 Kiểm tra health
```bash
curl -sS http://127.0.0.1:8100/health
curl -sS http://127.0.0.1:8110/health
curl -sS http://127.0.0.1:8110/health/details
curl -sS http://127.0.0.1:3100/
```

## 6) Chạy local từng service

### API
```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn clara_api.main:app --app-dir src --host 0.0.0.0 --port 8000 --reload
```

### ML
```bash
cd services/ml
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn clara_ml.main:app --app-dir src --host 0.0.0.0 --port 8010 --reload
```

### Web
```bash
cd apps/web
npm ci
npm run dev
```

## 7) CI/CD và quality gates

- `ci.yml`: docs-check, lint/type-check, test API/ML, web build, security audit, docker smoke, container scan.
- `release.yml`: semver tag + release artifacts/images.
- `cd.yml`: deploy staging/prod theo workflow chuẩn.
- `required-ci-gates`: cổng bắt buộc trước merge theo policy branch protection.

## 8) DevOps vận hành mới (đã bổ sung)

### 8.1 Env Guard trước deploy
- Script: `scripts/ops/validate_runtime_env.sh`
- Tự chặn các lỗi cấu hình phổ biến:
  - `POSTGRES_HOST=localhost` trong container runtime
  - `DATABASE_URL` trỏ localhost
  - thiếu DeepSeek credentials khi bật gate strict

### 8.2 Backup `.env` định kỳ
- Script: `scripts/ops/backup_env.sh`
- Cài cron: `scripts/ops/install_env_backup_cron.sh`
- Backup có checksum và retention policy.

### 8.3 Disk cleanup định kỳ
- Script: `scripts/ops/cleanup_disk.sh`
- Cài cron: `scripts/ops/install_cleanup_cron.sh`

## 9) Biến môi trường cần chú ý

Xem đầy đủ tại `.env.example`.

Nhóm chính:
- Runtime: `API_PORT`, `ML_SERVICE_URL`, `NEXT_PUBLIC_API_URL`
- Auth/Security: `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `AUTH_*`
- LLM/Embedding: `DEEPSEEK_*`, `EMBEDDING_*`
- Retrieval: `RAG_*`, `SEARXNG_*`, `EXTERNAL_DDI_ENABLED`
- OCR bridge: `TGC_OCR_*`

## 10) Giới hạn hiện tại

- Chưa phải phần mềm thiết bị y tế (SaMD).
- Một số module vẫn ở mức tăng dần độ cứng production theo phase hackathon.
- Mobile app hiện là skeleton để nối backend flow, chưa full parity với web.

## 11) Tài liệu nội bộ quan trọng

- `docs/hackathon/deep-research-2026-benchmark-and-implementation-plan.md`
- `docs/hackathon/council-ai-competitive-gaps-2026-04-03.md`
- `docs/hackathon/council-neural-network-implementation-plan-2026-04-03.md`
- `docs/hackathon/production-env-guard-and-backup-runbook-2026-04-03.md`

## 12) License

MIT — xem `LICENSE`.
