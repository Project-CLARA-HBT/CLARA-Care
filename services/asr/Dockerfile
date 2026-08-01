FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# faster-whisper kéo theo ctranslate2 + PyAV (ffmpeg bundled trong wheel av,
# decode được webm/opus từ trình duyệt mà không cần cài ffmpeg hệ thống).
COPY services/asr/requirements.lock /app/requirements.lock
RUN python -m pip install --no-cache-dir --requirement /app/requirements.lock
COPY services/asr/server.py ./server.py
RUN groupadd --system --gid 10001 clara \
    && useradd --system --uid 10001 --gid clara --home-dir /app --no-create-home clara \
    && chown -R clara:clara /app
USER clara
EXPOSE 8090
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8090"]
