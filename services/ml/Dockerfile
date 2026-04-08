FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/ml/pyproject.toml /app/pyproject.toml
COPY services/ml/README.md /app/README.md
COPY services/ml/src /app/src

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8010

CMD ["sh", "-c", "uvicorn clara_ml.main:app --app-dir src --host 0.0.0.0 --port 8010 --workers ${ML_UVICORN_WORKERS:-8}"]
