FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Tesseract OCR (fallback engine for medication-label scanning when Google
# Vision is unavailable). The Vietnamese + English language packs are required
# for the `vie+eng` model used by the CareGuard/PHR scan endpoints.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-vie \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/pyproject.toml /app/pyproject.toml
COPY services/api/uv.lock /app/uv.lock
COPY services/api/README.md /app/README.md
COPY services/api/src /app/src
COPY services/api/alembic /app/alembic
COPY services/api/alembic.ini /app/alembic.ini

# Production must resolve the exact dependency graph exercised by CI.  A plain
# ``pip install .`` accepts every future version satisfying broad lower bounds;
# FastAPI 0.140, for example, changed router inclusion semantics and silently
# removed the mounted API surface.  ``uv sync --frozen`` fails the image build
# if pyproject and the committed lock diverge.
RUN python -m pip install --no-cache-dir "uv==0.8.22" \
    && uv sync --frozen --no-dev --no-editable

# The server process must not run as root. Source and the virtual environment
# are immutable at runtime; writable state belongs to explicitly mounted
# volumes owned by the deployment, not the image layer.
RUN groupadd --system --gid 10001 clara \
    && useradd --system --uid 10001 --gid clara --home-dir /app --no-create-home clara \
    && chown -R clara:clara /app
USER clara

EXPOSE 8000

CMD ["sh", "-c", "uvicorn clara_api.main:app --app-dir src --host 0.0.0.0 --port 8000 --workers ${API_UVICORN_WORKERS:-1}"]
