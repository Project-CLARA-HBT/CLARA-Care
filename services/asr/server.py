"""CLARA ASR adapter — local Whisper (faster-whisper) bridge.

Cung cấp endpoint OpenAI-compatible `POST /v1/audio/transcriptions` để ML
service trỏ `DEEPSEEK_AUDIO_BASE_URL` vào đây thay vì yescale (key yescale
nhóm `deepseek` KHÔNG có model audio). Nhận multipart `file` (webm/opus từ
trình duyệt, wav, mp3...) → faster-whisper decode qua PyAV → trả `{"text"}`.

Chạy CPU int8 mặc định — model `small` đủ realtime cho chunk 2.8s của trang
/scribe. Đổi model/thiết bị qua env:
    WHISPER_MODEL=small|medium|large-v3   (default: small)
    WHISPER_DEVICE=cpu|cuda|auto           (default: cpu)
    WHISPER_COMPUTE=int8|float16|int8_float16  (default: int8)

Endpoints:
    GET  /health
    POST /v1/audio/transcriptions — multipart: file, model?, language?, prompt?
"""
from __future__ import annotations

import io
import os
import time
from threading import Lock

from fastapi import FastAPI, Form, HTTPException, UploadFile

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")
DEFAULT_LANGUAGE = os.getenv("WHISPER_LANGUAGE_DEFAULT", "vi")

app = FastAPI(title="clara-asr-whisper")

_model = None
_model_lock = Lock()


def _get_model():
    """Load model lười + một lần (download lần đầu được cache qua volume)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from faster_whisper import WhisperModel

                _model = WhisperModel(
                    WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE
                )
    return _model


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "clara-asr-whisper",
        "model": WHISPER_MODEL,
        "device": WHISPER_DEVICE,
        "loaded": _model is not None,
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile,
    model: str = Form(default=""),  # nhận để tương thích OpenAI, bỏ qua
    language: str = Form(default=""),
    prompt: str = Form(default=""),
    response_format: str = Form(default="json"),
) -> dict:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio payload is empty")

    lang = (language or DEFAULT_LANGUAGE).strip() or None
    started = time.perf_counter()
    try:
        segments, info = _get_model().transcribe(
            io.BytesIO(audio_bytes),
            language=lang,
            initial_prompt=prompt or None,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as exc:  # noqa: BLE001 — trả lỗi rõ thay vì 500 câm
        raise HTTPException(status_code=422, detail=f"Whisper decode failed: {exc}") from exc

    return {
        "text": text,
        "language": getattr(info, "language", lang),
        "duration": round(getattr(info, "duration", 0.0), 2),
        "processing_ms": int((time.perf_counter() - started) * 1000),
        "model": WHISPER_MODEL,
    }
