FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/api/pyproject.toml /app/pyproject.toml
COPY services/api/README.md /app/README.md
COPY services/api/src /app/src
COPY services/api/alembic /app/alembic
COPY services/api/alembic.ini /app/alembic.ini

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "clara_api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
