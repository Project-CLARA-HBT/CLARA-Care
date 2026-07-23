FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
# faster-whisper kéo theo ctranslate2 + PyAV (ffmpeg bundled trong wheel av,
# decode được webm/opus từ trình duyệt mà không cần cài ffmpeg hệ thống).
RUN pip install --no-cache-dir \
    fastapi==0.139.2 \
    uvicorn==0.51.0 \
    python-multipart==0.0.32 \
    faster-whisper==1.2.1
COPY services/asr/server.py ./server.py
EXPOSE 8090
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8090"]
