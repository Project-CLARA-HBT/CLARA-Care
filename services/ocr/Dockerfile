FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir fastapi uvicorn httpx python-multipart
COPY services/ocr/server.py ./server.py
RUN groupadd --system --gid 10001 clara \
    && useradd --system --uid 10001 --gid clara --home-dir /app --no-create-home clara \
    && chown -R clara:clara /app
USER clara
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
