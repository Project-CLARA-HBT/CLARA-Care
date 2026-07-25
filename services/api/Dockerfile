FROM python:3.14-slim

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

EXPOSE 8000

CMD ["sh", "-c", "uvicorn clara_api.main:app --app-dir src --host 0.0.0.0 --port 8000 --workers ${API_UVICORN_WORKERS:-1}"]
