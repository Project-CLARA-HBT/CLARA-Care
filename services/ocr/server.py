"""CLARA OCR adapter — Multimodal Gemini Vision bridge.

Cầu nối OCR thông minh sử dụng multimodal LLM (Gemini 3.7 Flash Tiered / 3.6 Flash High)
qua OpenAI-compatible router gateway. CLARA gửi ảnh toa thuốc, vỏ hộp thuốc hoặc
phiếu xét nghiệm (multipart hoặc JSON base64) tới `POST /ocr`; adapter gọi Vision LLM
để nhận diện văn bản chính xác kèm danh mục thuốc có cấu trúc.

Key / router config:
    ROUTER_BASE_URL = https://router.theclaracare.com/v1
    ROUTER_API_KEY  = <read from environment>
    OCR_MODEL       = gemini-3.7-flash-tiered
    OCR_FALLBACK_MODEL = gemini-3.6-flash-high

Endpoints:
    GET  /health
    POST /ocr          — multipart file hoặc JSON base64
    POST /api/ocr      — alias tương thích TGC
    POST /api/extract  — alias tương thích TGC
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clara-ocr-vision")

DEFAULT_ROUTER_BASE_URL = "https://router.theclaracare.com/v1"
DEFAULT_API_KEY = ""
DEFAULT_PRIMARY_MODEL = "gemini-3.7-flash-tiered"
DEFAULT_FALLBACK_MODEL = "gemini-3.6-flash-high"
DEFAULT_LANG = "vi"
TIMEOUT_SECONDS = float(os.getenv("OCR_TIMEOUT_SECONDS", "45.0"))

_JSON_B64_KEYS = ("image", "image_base64", "content", "base64", "file", "data")

app = FastAPI(title="clara-ocr-multimodal-gemini", version="2.0.0")


def _get_base_url() -> str:
    url = (
        os.getenv("ROUTER_BASE_URL")
        or os.getenv("OCR_ROUTER_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL")
        or DEFAULT_ROUTER_BASE_URL
    ).strip().rstrip("/")
    return url


def _get_api_key() -> str:
    key = (
        os.getenv("ROUTER_API_KEY")
        or os.getenv("CLARA_UNOFFICIAL_GEMINI_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OCR_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or DEFAULT_API_KEY
    ).strip()
    return key


def _get_primary_model() -> str:
    return (os.getenv("OCR_MODEL") or os.getenv("LLM_MODEL") or DEFAULT_PRIMARY_MODEL).strip()


def _get_fallback_model() -> str:
    return (os.getenv("OCR_FALLBACK_MODEL") or os.getenv("LLM_FALLBACK_MODEL") or DEFAULT_FALLBACK_MODEL).strip()


def _detect_mime_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
        return "image/webp"
    return "image/jpeg"


async def _extract_image_bytes(request: Request) -> tuple[bytes, str]:
    """Lấy bytes ảnh và mime-type từ multipart hoặc JSON base64."""
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        for value in form.values():
            if hasattr(value, "read"):  # UploadFile
                raw_bytes = await value.read()
                mime = getattr(value, "content_type", "") or _detect_mime_type(raw_bytes)
                return raw_bytes, mime
        raise HTTPException(status_code=400, detail="Không tìm thấy file trong multipart form")

    # JSON base64 payload
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Body không phải multipart hay JSON hợp lệ") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body phải là object")

    mime = str(payload.get("mime_type") or payload.get("content_type") or "")

    for key in _JSON_B64_KEYS:
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            if raw.startswith("data:"):
                prefix, encoded = raw.split(",", 1)
                if not mime and ";" in prefix:
                    mime = prefix.split(";")[0].replace("data:", "").strip()
            else:
                encoded = raw
            try:
                raw_bytes = base64.b64decode(encoded)
                if not mime:
                    mime = _detect_mime_type(raw_bytes)
                return raw_bytes, mime
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=f"base64 ở key '{key}' không hợp lệ") from exc

    raise HTTPException(status_code=400, detail="Không tìm thấy ảnh base64 trong JSON")


def _call_gemini_multimodal(image_bytes: bytes, mime_type: str, lang: str = "vi") -> tuple[dict[str, Any], str]:
    base_url = _get_base_url()
    api_key = _get_api_key()
    primary_model = _get_primary_model()
    fallback_model = _get_fallback_model()

    b64_image = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64_image}"

    prompt = (
        "You are CLARA OCR - an expert clinical multimodal OCR vision system specialized in "
        "Vietnamese medical prescriptions, medicine boxes/blister packs, hospital discharge summaries, "
        "and lab results.\n\n"
        "Instructions:\n"
        "1. Extract ALL visible text verbatim from the image, preserving accurate Vietnamese diacritics and line breaks.\n"
        "2. Parse any identifiable medications into structured items (drug name, strength/dose, quantity, frequency/instructions).\n"
        "3. Output MUST be valid JSON with this exact schema:\n"
        "{\n"
        '  "full_text": "complete verbatim text with line breaks",\n'
        '  "lines": ["line 1", "line 2", ...],\n'
        '  "items": ["line 1", "line 2", ...],\n'
        '  "medications": [\n'
        '    {\n'
        '      "name": "drug name",\n'
        '      "strength": "dose / strength e.g. 500mg, 1g",\n'
        '      "quantity": "quantity e.g. 20 vien",\n'
        '      "frequency": "usage instructions / frequency",\n'
        '      "confidence": 0.95\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "Return ONLY the JSON object."
    )

    models_to_try = [primary_model]
    if fallback_model and fallback_model != primary_model:
        models_to_try.append(fallback_model)

    last_error: Exception | None = None

    for model in models_to_try:
        chat_url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }

        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                resp = client.post(chat_url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_ocr_content(content)
                return parsed, model
            else:
                logger.warning("Model %s returned HTTP %s: %s", model, resp.status_code, resp.text[:200])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Model %s call failed: %s", model, exc)
            last_error = exc

    if last_error:
        raise HTTPException(status_code=502, detail=f"Multimodal OCR failed: {last_error}")
    raise HTTPException(status_code=502, detail="Tất cả mô hình OCR router đều không phản hồi thành công")


def _parse_ocr_content(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            full_text = str(data.get("full_text") or "")
            lines = data.get("lines")
            if not isinstance(lines, list):
                lines = [line.strip() for line in full_text.splitlines() if line.strip()]
            items = data.get("items")
            if not isinstance(items, list):
                items = lines
            medications = data.get("medications") if isinstance(data.get("medications"), list) else []
            return {
                "text": full_text,
                "lines": lines,
                "items": items,
                "medications": medications,
            }
    except json.JSONDecodeError:
        pass

    # Fallback to pure text extraction
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return {
        "text": cleaned,
        "lines": lines,
        "items": lines,
        "medications": [],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "clara-ocr-multimodal-gemini",
        "primary_model": _get_primary_model(),
        "fallback_model": _get_fallback_model(),
        "router_base_url": _get_base_url(),
        "key_configured": bool(_get_api_key()),
    }


@app.post("/ocr")
@app.post("/api/ocr")
@app.post("/api/extract")
async def ocr(request: Request) -> dict[str, Any]:
    image_bytes, mime_type = await _extract_image_bytes(request)
    lang = DEFAULT_LANG
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            if isinstance(body, dict) and isinstance(body.get("lang"), str):
                lang = body["lang"]
        except Exception:  # noqa: BLE001
            pass

    parsed, model_used = _call_gemini_multimodal(image_bytes, mime_type, lang=lang)
    return {
        "text": parsed["text"],
        "lines": parsed["lines"],
        "items": parsed["items"],
        "medications": parsed.get("medications", []),
        "ocr_provider": f"clara-multimodal-{model_used}",
    }
