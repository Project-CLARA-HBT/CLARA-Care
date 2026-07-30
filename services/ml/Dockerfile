FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY services/ml/pyproject.toml /app/pyproject.toml
COPY services/ml/uv.lock /app/uv.lock
COPY services/ml/README.md /app/README.md
COPY services/ml/config /app/config
COPY services/ml/src /app/src

# Use the exact graph exercised by tests. Resolving broad lower bounds during
# a production build can silently introduce incompatible FastAPI/LangChain
# releases even when application source has not changed.
RUN python -m pip install --no-cache-dir "uv==0.8.22" \
    && uv sync --frozen --no-dev --no-editable

EXPOSE 8010

CMD ["sh", "-c", "uvicorn clara_ml.main:app --app-dir src --host 0.0.0.0 --port 8010 --workers ${ML_UVICORN_WORKERS:-1}"]
