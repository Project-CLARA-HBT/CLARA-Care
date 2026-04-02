# CLARA-Care

[![Kiểm thử tích hợp](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/ci.yml/badge.svg)](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/ci.yml)
[![Phát hành](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/release.yml/badge.svg)](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/release.yml)
[![Triển khai](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/cd.yml/badge.svg)](https://github.com/Project-CLARA-HBT/CLARA-Care/actions/workflows/cd.yml)
[![Giấy phép](https://img.shields.io/github/license/Project-CLARA-HBT/CLARA-Care)](LICENSE)
[![Website](https://img.shields.io/badge/Website-clara.thiennn.icu-0A66C2?logo=google-chrome&logoColor=white)](https://clara.thiennn.icu)

Nền tảng trợ lý y khoa đa mô-đun cho mục tiêu **hỗ trợ tham khảo** (không thay thế chẩn đoán hoặc kê đơn), gồm web, dịch vụ API, dịch vụ ML, ứng dụng di động mẫu và bộ hạ tầng Docker/CI/CD.

## 1) Trạng thái hiện tại (bám codebase)

- Mã nguồn theo kiến trúc đơn kho với 4 khối chính: `apps/web`, `apps/mobile`, `services/api`, `services/ml`.
- Luồng đã chạy được trong hệ thống hiện tại:
  - Hỏi đáp y khoa (`chat` + `research tier2`).
  - Self-MED/CareGuard (quản lý tủ thuốc + phân tích tương tác thuốc).
  - Council (hội chẩn mô phỏng).
  - Scribe SOAP (mức nền).
  - Control Tower + bảng giám sát vận hành.
- Có quy trình kiểm thử tích hợp, phát hành ảnh container và triển khai qua Docker Compose.

Phạm vi trách nhiệm:
- Hệ thống là công cụ hỗ trợ tham khảo.
- Chưa phải phần mềm thiết bị y tế (SaMD), chưa có xác nhận lâm sàng đa trung tâm.

## 2) Kiến trúc tổng quan

### 2.1 Thành phần chạy thời gian thực

- **Web**: Next.js 14 (`apps/web`) cổng `3000` (compose ánh xạ `127.0.0.1:3100`).
- **API**: FastAPI (`services/api`) cổng `8000` (compose ánh xạ `127.0.0.1:8100`).
- **ML**: FastAPI (`services/ml`) cổng `8010` (compose ánh xạ `127.0.0.1:8110`).
- **Cổng tìm kiếm**: SearXNG (compose ánh xạ `127.0.0.1:8888`).
- **Giám sát**: Prometheus (`127.0.0.1:9090`) + Grafana (`127.0.0.1:3001`, qua reverse proxy `/grafana/`).
- **Hạ tầng dữ liệu cục bộ**: PostgreSQL, Redis, Milvus (+etcd+minio), Elasticsearch, Neo4j.

### 2.2 Luồng xử lý chính

1. Ứng dụng khách gọi API tại `/api/v1/*`.
2. API xử lý xác thực, phân quyền, giới hạn tần suất, đồng thuận và điều phối nghiệp vụ.
3. API chuyển tiếp các tác vụ suy luận sang ML (`chat`, `research/tier2`, `careguard`, `council`, `scribe`).
4. ML chạy định tuyến vai trò/ý định, hàng rào pháp lý, pipeline RAG, kết nối nguồn ngoài và chế độ dự phòng an toàn.

## 3) Cấu trúc thư mục

```text
.
├── apps/
│   ├── web/                 # giao diện Next.js
│   └── mobile/              # ứng dụng Flutter mẫu
├── services/
│   ├── api/                 # API FastAPI + nghiệp vụ
│   └── ml/                  # dịch vụ điều phối ML
├── deploy/
│   ├── docker/              # docker-compose cho hạ tầng/app/triển khai
│   └── nginx/               # cấu hình reverse proxy mẫu
├── scripts/
│   ├── setup/               # kiểm tra môi trường
│   ├── docs/                # kiểm tra liên kết tài liệu
│   ├── demo/                # tạo hiện vật benchmark/demo
│   ├── rag_seed/            # thu thập/seed dữ liệu RAG
│   └── release|deploy|ops   # tự động hóa phát hành/triển khai/vận hành
├── docs/hackathon/          # tài liệu dùng trực tiếp trong kiểm thử CI
└── data/docs/               # tài liệu chi tiết (kiến trúc, đề xuất, devops...)
```

## 4) Tính năng đã có trong mã nguồn

### 4.1 Xác thực, phân quyền, đồng thuận

- JWT truy cập/làm mới.
- Đăng ký, đăng nhập, làm mới phiên, đăng xuất, xác minh thư điện tử, quên/đặt lại/đổi mật khẩu.
- Vai trò hiện có: `normal`, `researcher`, `doctor`, `admin`.
- Cổng đồng thuận disclaimer y khoa cho các luồng liên quan dữ liệu nhạy cảm.

Nhóm endpoint chính:
- `/api/v1/auth/register|login|refresh|logout|me`
- `/api/v1/auth/verify-email|forgot-password|reset-password|change-password`
- `/api/v1/auth/consent-status|consent`

### 4.2 Nghiên cứu và hỏi đáp

- Hỏi đáp định tuyến: `/api/v1/chat` -> ML `/v1/chat/routed`.
- Nghiên cứu tầng 2 đồng bộ: `/api/v1/research/tier2`.
- Nghiên cứu tầng 2 theo cơ chế tác vụ:
  - `/api/v1/research/tier2/jobs`
  - `/api/v1/research/tier2/jobs/{job_id}`
  - `/api/v1/research/tier2/jobs/{job_id}/stream`
- Quản lý cuộc hội thoại và kho tri thức theo từng người dùng.
- Source Hub (danh mục/ghi nhận/đồng bộ) và tìm kiếm đa nguồn `/api/v1/search`.

### 4.3 CareGuard và Self-MED

- Quản lý tủ thuốc: `/api/v1/careguard/cabinet*`.
- Quét nội dung toa thuốc:
  - `/api/v1/careguard/cabinet/scan-text`
  - `/api/v1/careguard/cabinet/scan-file`
- Nhập kết quả nhận diện vào tủ thuốc.
- Phân tích tương tác thuốc:
  - `/api/v1/careguard/cabinet/auto-ddi-check`
  - `/api/v1/careguard/analyze`
- Cơ chế kết hợp luật cục bộ + nguồn DDI bên ngoài (bật/tắt theo cấu hình runtime).

### 4.4 Council và Scribe

- Hội chẩn:
  - `/api/v1/council/run`
  - `/api/v1/council/intake`
- Scribe SOAP mức nền:
  - `/api/v1/scribe/soap`

### 4.5 Control Tower và giám sát

- Chỉ số/tình trạng phụ thuộc/hệ sinh thái:
  - `/api/v1/system/metrics`
  - `/api/v1/system/dependencies`
  - `/api/v1/system/ecosystem`
- Quản trị cấu hình runtime:
  - `/api/v1/system/control-tower/config`
  - `/api/v1/system/careguard/runtime`
- Dòng sự kiện:
  - `/api/v1/system/flow-events`
  - `/api/v1/system/flow-events/stream`

## 5) Khởi chạy nhanh bằng Docker

### 5.1 Điều kiện

- Docker Engine + Docker Compose v2
- GNU Make

### 5.2 Chuẩn bị

```bash
cp .env.example .env
make check-env
```

### 5.3 Chạy hạ tầng cục bộ (cơ sở dữ liệu và tìm kiếm)

```bash
make docker-up
make docker-ps
```

Dừng hạ tầng:

```bash
make docker-down
```

### 5.4 Chạy bộ ứng dụng (web/api/ml/searxng)

```bash
make docker-app-up
make docker-app-ps
```

Xem nhật ký:

```bash
make docker-app-logs
```

Dừng ứng dụng:

```bash
make docker-app-down
```

### 5.5 Kiểm tra trạng thái nhanh

```bash
curl -sS http://127.0.0.1:8100/health
curl -sS http://127.0.0.1:8100/metrics | head -n 20
curl -sS http://127.0.0.1:8100/api/v1/health
curl -sS http://127.0.0.1:8110/health
curl -sS http://127.0.0.1:8110/metrics | head -n 20
curl -sS http://127.0.0.1:3100/
curl -I http://127.0.0.1:3001/grafana/
```

## 6) Chạy từng dịch vụ ở môi trường cục bộ

### 6.1 Dịch vụ API

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn clara_api.main:app --app-dir src --host 0.0.0.0 --port 8000 --reload
```

### 6.2 Dịch vụ ML

```bash
cd services/ml
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn clara_ml.main:app --app-dir src --host 0.0.0.0 --port 8010 --reload
```

### 6.3 Ứng dụng web

```bash
cd apps/web
npm ci
npm run dev
```

### 6.4 Ứng dụng di động mẫu

```bash
cd apps/mobile
flutter pub get
flutter run --dart-define=CLARA_API_BASE_URL=http://localhost:8000
```

## 7) Kiểm thử và cổng chất lượng

Chạy từ thư mục gốc:

```bash
make lint
make type-check
make test
make docs-check
```

Cài tiền kiểm tra trước khi đẩy mã:

```bash
pip install pre-commit
make precommit-install
```

Lệnh Make dùng thường xuyên:

- `make dev-api`: chạy API cục bộ (`services/api`).
- `make dev-ml`: chạy ML cục bộ (`services/ml`).
- `make dev-web`: chạy web cục bộ (`apps/web`).
- `make docker-up|docker-down|docker-ps|docker-logs`: quản lý stack hạ tầng.
- `make docker-app-up|docker-app-down|docker-app-ps|docker-app-logs`: quản lý stack ứng dụng.

## 8) Quy trình tự động CI/CD

Các workflow chính:

- `.github/workflows/ci.yml`
  - Phát hiện tệp thay đổi.
  - Kiểm tra tài liệu + ruff + mypy.
  - Kiểm thử API, kiểm thử ML.
  - Kiểm tra và dựng bản web.
  - Kiểm tra bảo mật phụ thuộc (`pip-audit`, `npm audit`).
  - Dựng thử bằng Docker Compose.
  - Quét bảo mật ảnh container bằng Trivy.
  - Cổng tổng hợp bắt buộc: `required-ci-gates`.
- `.github/workflows/release.yml`
  - Tạo thẻ phiên bản (`vX.Y.Z`), dựng/đẩy ảnh GHCR, xuất bản bản phát hành GitHub.
- `.github/workflows/cd.yml`
  - Triển khai thủ công lên môi trường thử nghiệm, kiểm tra khói, tùy chọn đẩy tiếp lên sản xuất.
- `.github/workflows/branch-protection-sync.yml`
  - Đồng bộ chính sách bảo vệ nhánh.

## 9) Biến môi trường quan trọng

Xem đầy đủ trong `.env.example`.

Nhóm biến cần quan tâm:

- Vận hành: `ENV`, `API_PORT`, `ML_SERVICE_URL`, `NEXT_PUBLIC_API_URL`.
- Xác thực: `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `AUTH_*`.
- Mô hình/LLM: `DEEPSEEK_*`, `EMBEDDING_*`.
- Kết nối ngoài: `RAG_EXTERNAL_CONNECTORS_ENABLED`, `EXTERNAL_DDI_ENABLED`, `SEARXNG_*`.
- Cầu nối OCR: `TGC_OCR_BASE_URL`, `TGC_OCR_ENDPOINTS`, `TGC_OCR_API_KEY`.

## 10) Bảo mật và vận hành

- API có lớp trung gian cho ngữ cảnh phân quyền, giới hạn tần suất, đo lường và tiêu đề bảo mật HTTP.
- Ở môi trường sản xuất có kiểm tra cấu hình bắt buộc (`JWT_SECRET_KEY`, `AUTH_COOKIE_SECURE`).
- Không lưu bí mật vào kho mã nguồn; dùng `.env` theo từng môi trường.
- Không đưa thông tin tài khoản thật vào README hoặc tài liệu công khai.

## 11) Giới hạn hiện tại (để tránh tuyên bố quá mức)

- Scribe hiện ở mức nền, chưa phải mô-đun hoàn thiện cho hồ sơ lâm sàng thực tế.
- Một phần bảng giám sát vẫn dựa trên snapshot runtime và lấy mẫu sự kiện.
- Truy xuất lõi mức sản xuất chưa chạy toàn phần trên toàn bộ stack vector/graph/search; hiện là kết hợp trong bộ nhớ + nguồn ngoài + cấu hình runtime.
- Ứng dụng di động hiện là bản mẫu (phiên lưu trong bộ nhớ, chưa tăng cứng đầy đủ cho sản xuất).
- Chưa phải SaMD, không thay thế quy trình chuyên môn lâm sàng.

## 12) Tài liệu nội bộ liên quan

- Kiến trúc runtime: `data/docs/architecture/clara-runtime-and-routing.md`
- Hồ sơ đề xuất: `data/docs/proposal/`
- Tài liệu DevOps: `data/docs/devops/`
- Hiện vật hackathon: `docs/hackathon/` và `data/docs/hackathon/`

Ghi chú:

- `make docs-check` đang quét `docs/*.md` (đặc biệt nhóm `docs/hackathon`).
- Bộ tài liệu mở rộng được lưu trong `data/docs/*`.

## 13) Giấy phép

- MIT, xem `LICENSE`.
