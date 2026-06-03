#!/usr/bin/env bash
# CLARA startup — chạy mỗi khi bật máy.
#
#   ./scripts/start-clara.sh          # docker stack: infra (postgres/redis) + app (web/api/ml/searxng)
#   ./scripts/start-clara.sh --dev    # thêm native dev: ollama + uvicorn api:8000 + ml:8110 + next dev:3000
#
# Docker stack dùng deploy/docker/.env (gitignored) để tránh compose env-masking —
# KHÔNG xoá file đó. Native dev đọc .env gốc trực tiếp.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="$ROOT/deploy/docker"
LOG_DIR="$ROOT/.devlogs"
DEV_MODE=false
[ "${1:-}" = "--dev" ] && DEV_MODE=true

port_busy() { ss -tln 2>/dev/null | grep -q ":$1 "; }

wait_http() { # name url max_tries
  local name="$1" url="$2" tries="${3:-30}" i
  for i in $(seq 1 "$tries"); do
    if curl -sf -m 3 -o /dev/null "$url"; then
      echo "  ✓ $name OK ($url)"
      return 0
    fi
    sleep 2
  done
  echo "  ✗ $name KHÔNG phản hồi sau $((tries * 2))s ($url)"
  return 1
}

# ---------------------------------------------------------------- 1. Docker --
echo "[1/4] Chờ Docker Desktop..."
for _ in $(seq 1 60); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done
if ! docker info >/dev/null 2>&1; then
  echo "  ✗ Docker daemon chưa chạy sau 120s."
  echo "    → Mở Docker Desktop trên Windows (bật 'Start Docker Desktop when you sign in' để tự chạy), rồi chạy lại script."
  exit 1
fi
echo "  ✓ Docker sẵn sàng"

# ----------------------------------------------------- 2. Compose stacks up --
# Idempotent: container đều restart=unless-stopped nên thường đã tự lên cùng
# Docker Desktop; up -d chỉ tạo lại cái nào thiếu/đổi config.
echo "[2/4] Khởi động docker stack..."
cd "$COMPOSE_DIR"
# Chỉ up postgres + redis — docker-compose.yml còn chứa milvus/elasticsearch/neo4j
# (nặng, app hiện chưa dùng); KHÔNG up cả file kẻo nghẹt máy 7.6GB RAM.
docker compose -f docker-compose.yml up -d postgres redis
docker compose -f docker-compose.app.yml up -d --remove-orphans
cd "$ROOT"

# ------------------------------------------------------------ 3. Health check --
echo "[3/4] Health check docker stack..."
FAIL=0
wait_http "api (docker)" "http://127.0.0.1:8100/health" || FAIL=1
wait_http "ml  (docker)" "http://127.0.0.1:8111/health" || FAIL=1
wait_http "web (docker)" "http://127.0.0.1:3100/" || FAIL=1
wait_http "ocr (docker)" "http://127.0.0.1:8080/health" || FAIL=1

# ------------------------------------------------------------- 4. Native dev --
if $DEV_MODE; then
  echo "[4/4] Native dev (--dev)..."
  mkdir -p "$LOG_DIR"

  # ollama (bge-m3 embeddings + reranker cho native ml)
  if pgrep -x ollama >/dev/null 2>&1; then
    echo "  • ollama đã chạy"
  else
    nohup ollama serve >"$LOG_DIR/ollama.log" 2>&1 &
    echo "  • ollama serve khởi động (log: .devlogs/ollama.log)"
  fi

  # api native :8000 — chạy từ repo root như thường lệ (--reload watch cả repo)
  if port_busy 8000; then
    echo "  • api:8000 đã chạy"
  else
    nohup "$ROOT/services/api/.venv/bin/uvicorn" clara_api.main:app \
      --app-dir services/api/src --host 0.0.0.0 --port 8000 --reload \
      >"$LOG_DIR/api.log" 2>&1 &
    echo "  • api:8000 khởi động (log: .devlogs/api.log)"
  fi

  # ml native :8110
  if port_busy 8110; then
    echo "  • ml:8110 đã chạy"
  else
    nohup "$ROOT/services/ml/.venv/bin/uvicorn" clara_ml.main:app \
      --app-dir services/ml/src --host 0.0.0.0 --port 8110 --reload \
      >"$LOG_DIR/ml.log" 2>&1 &
    echo "  • ml:8110 khởi động (log: .devlogs/ml.log)"
  fi

  # web dev :3000 (cần node qua nvm)
  if port_busy 3000; then
    echo "  • web:3000 đã chạy"
  else
    export NVM_DIR="$HOME/.nvm"
    # shellcheck disable=SC1091
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    (cd "$ROOT/apps/web" && nohup npm run dev >"$LOG_DIR/web.log" 2>&1 &)
    echo "  • web:3000 khởi động (log: .devlogs/web.log)"
  fi

  wait_http "api (native)" "http://127.0.0.1:8000/health" 15 || FAIL=1
  wait_http "ml  (native)" "http://127.0.0.1:8110/health" 15 || FAIL=1
  wait_http "web (native)" "http://127.0.0.1:3000/" 45 || FAIL=1
else
  echo "[4/4] Bỏ qua native dev (thêm --dev nếu cần)."
fi

echo
echo "================ CLARA ================"
echo "  Web (docker) : http://localhost:3100"
echo "  API (docker) : http://localhost:8100/health"
echo "  ML  (docker) : http://localhost:8111/health"
echo "  OCR (docker) : http://localhost:8080/health"
if $DEV_MODE; then
  echo "  Web (dev)    : http://localhost:3000"
  echo "  API (dev)    : http://localhost:8000/health"
  echo "  ML  (dev)    : http://localhost:8110/health"
fi
echo "======================================="
[ "$FAIL" -eq 0 ] && echo "Tất cả service OK ✓" || echo "CÓ SERVICE LỖI — xem log: docker compose -f deploy/docker/docker-compose.app.yml logs / .devlogs/"
exit "$FAIL"
