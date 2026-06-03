"""CLARA OCR adapter — Google Cloud Vision bridge.

Cầu nối mỏng giữa CLARA careguard bridge (`_scan_with_tgc_ocr`) và Google
Cloud Vision API. CLARA gửi ảnh toa thuốc (multipart hoặc JSON base64) tới
`POST /ocr`; adapter gọi Vision `DOCUMENT_TEXT_DETECTION` rồi trả về JSON
shape mà bridge đọc được: `{"text", "lines", "items"}`.

OCR chạy trên cloud của Google nên adapter này cực nhẹ — không model, không
GPU. Chỉ cần `GCP_VISION_API_KEY` (key restrict cho Cloud Vision API).

Chạy:
    GCP_VISION_API_KEY=... uvicorn server:app --app-dir services/ocr --port 8080

Endpoints:
    GET  /health
    POST /ocr   — multipart file (field: file/image/document/upload_file)
                  HOẶC JSON {"image"|"image_base64"|"content"|"base64"|"file": "<b64>", "lang": "vi"}
"""
from __future__ import annotations

import base64
import os

import httpx
from fastapi import FastAPI, HTTPException, Request

VISION_ENDPOINT = os.getenv(
    "GCP_VISION_ENDPOINT", "https://vision.googleapis.com/v1/images:annotate"
)
DEFAULT_LANG = os.getenv("OCR_LANG_DEFAULT", "vi")
TIMEOUT_SECONDS = float(os.getenv("GCP_VISION_TIMEOUT_SECONDS", "30"))
# Đọc key động (không cache lúc import) để đổi key không cần sửa code.
_JSON_B64_KEYS = ("image", "image_base64", "content", "base64", "file", "data")

app = FastAPI(title="clara-ocr-vision")


def _api_key() -> str:
    key = (os.getenv("GCP_VISION_API_KEY") or "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GCP_VISION_API_KEY")
    return key


async def _extract_image_bytes(request: Request) -> bytes:
    """Lấy bytes ảnh từ multipart (bất kỳ field nào) hoặc JSON base64."""
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        for value in form.values():
            if hasattr(value, "read"):  # UploadFile
                return await value.read()
        raise HTTPException(status_code=400, detail="Không tìm thấy file trong multipart")

    # JSON base64 — thử các key mà CLARA bridge dùng.
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Body không phải multipart hay JSON hợp lệ") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body phải là object")
    for key in _JSON_B64_KEYS:
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            encoded = raw.split(",", 1)[1] if raw.startswith("data:") else raw
            try:
                return base64.b64decode(encoded)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=f"base64 ở key '{key}' không hợp lệ") from exc
    raise HTTPException(status_code=400, detail="Không tìm thấy ảnh base64 trong JSON")


def _call_vision(image_bytes: bytes, lang: str) -> dict:
    body = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                "imageContext": {"languageHints": [lang or DEFAULT_LANG]},
            }
        ]
    }
    url = f"{VISION_ENDPOINT}?key={_api_key()}"
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        resp = client.post(url, json=body)
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Vision HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    result = (data.get("responses") or [{}])[0]
    if "error" in result:
        raise HTTPException(status_code=502, detail=f"Vision error: {result['error'].get('message', '?')}")
    return result


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "clara-ocr-vision", "key_configured": bool(os.getenv("GCP_VISION_API_KEY"))}


@app.post("/ocr")
async def ocr(request: Request) -> dict:
    image_bytes = await _extract_image_bytes(request)
    lang = DEFAULT_LANG
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            if isinstance(body, dict) and isinstance(body.get("lang"), str):
                lang = body["lang"]
        except Exception:  # noqa: BLE001
            pass

    result = _call_vision(image_bytes, lang)
    full_text = result.get("fullTextAnnotation", {}).get("text", "") or ""
    lines = [ln for ln in full_text.splitlines() if ln.strip()]
    return {"text": full_text, "lines": lines, "items": lines, "ocr_provider": "gcp-vision"}
