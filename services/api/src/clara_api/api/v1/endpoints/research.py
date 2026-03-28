import math
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload

router = APIRouter()

_MAX_RESEARCH_UPLOADS = 200
_PREVIEW_CHAR_LIMIT = 500
_TEXT_FILE_EXTENSIONS = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
_IMAGE_FILE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}

_uploaded_research_files: dict[str, dict[str, Any]] = {}
_uploaded_research_lock = Lock()


def _guess_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return f".{filename.rsplit('.', 1)[-1].lower()}"


def _is_text_file(filename: str, content_type: str) -> bool:
    extension = _guess_extension(filename)
    if content_type.startswith("text/"):
        return True
    if extension in _TEXT_FILE_EXTENSIONS:
        return True
    return content_type in {"application/json", "application/xml"}


def _is_image_file(filename: str, content_type: str) -> bool:
    if content_type.startswith("image/"):
        return True
    return _guess_extension(filename) in _IMAGE_FILE_EXTENSIONS


def _is_pdf_file(filename: str, content_type: str) -> bool:
    return content_type == "application/pdf" or _guess_extension(filename) == ".pdf"


def _extract_basic_text(file_bytes: bytes, filename: str, content_type: str) -> tuple[str, str]:
    if _is_text_file(filename, content_type):
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("utf-8", errors="replace")
        return text, "text"

    if _is_pdf_file(filename, content_type):
        return "PDF đã được tải lên. Hệ thống chưa hỗ trợ parse sâu cho định dạng này.", "pdf"

    if _is_image_file(filename, content_type):
        return "Ảnh đã được tải lên. Hệ thống chưa hỗ trợ parse sâu cho định dạng này.", "image"

    return "File đã được tải lên. Hệ thống chưa hỗ trợ parse sâu cho định dạng này.", "other"


def _approx_token_count(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, math.ceil(len(stripped) / 4))


def _store_uploaded_file(entry: dict[str, Any]) -> None:
    with _uploaded_research_lock:
        _uploaded_research_files[entry["file_id"]] = entry
        if len(_uploaded_research_files) <= _MAX_RESEARCH_UPLOADS:
            return

        oldest_file_id = min(
            _uploaded_research_files,
            key=lambda item_file_id: str(_uploaded_research_files[item_file_id]["created_at"]),
        )
        _uploaded_research_files.pop(oldest_file_id, None)


def _build_uploaded_documents(uploaded_file_ids: Any) -> list[dict[str, Any]]:
    if not isinstance(uploaded_file_ids, list):
        return []

    documents: list[dict[str, Any]] = []
    with _uploaded_research_lock:
        for raw_file_id in uploaded_file_ids:
            if not isinstance(raw_file_id, str):
                continue
            cached = _uploaded_research_files.get(raw_file_id)
            if not cached:
                continue

            documents.append(
                {
                    "file_id": raw_file_id,
                    "filename": cached["filename"],
                    "content_type": cached["content_type"],
                    "size": cached["size"],
                    "created_at": cached["created_at"],
                    "text": cached["text"],
                    "preview": cached["preview"],
                    "token_count": cached["token_count"],
                }
            )
    return documents


def _research_tier2_fallback_payload(payload: dict[str, Any]) -> dict[str, Any]:
    fallback_answer = (
        "Hệ thống truy xuất chuyên sâu đang bận hoặc tạm thời không kết nối được nguồn RAG. "
        "Tạm thời dùng chế độ an toàn: bạn nên ưu tiên phác đồ chính thống, đối chiếu tương tác thuốc quan trọng, "
        "và trao đổi bác sĩ khi có bệnh nền hoặc dấu hiệu nặng."
    )
    return {
        "answer": fallback_answer,
        "summary": fallback_answer,
        "metadata": {},
        "citations": [],
        "fallback": True,
        "source_mode": payload.get("source_mode"),
    }


@router.post("/upload-file")
async def upload_research_file(
    file: UploadFile = File(...),
    _token: TokenPayload = Depends(require_roles("researcher", "doctor")),
) -> dict[str, Any]:
    file_name = file.filename or "uploaded-file"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File upload rỗng")

    extracted_text, file_kind = _extract_basic_text(file_bytes, file_name, content_type)
    preview = extracted_text[:_PREVIEW_CHAR_LIMIT]
    token_count = _approx_token_count(extracted_text if file_kind == "text" else "")
    created_at = datetime.now(tz=UTC).isoformat()
    file_id = str(uuid4())

    _store_uploaded_file(
        {
            "file_id": file_id,
            "filename": file_name,
            "content_type": content_type,
            "size": len(file_bytes),
            "created_at": created_at,
            "text": extracted_text if file_kind == "text" else "",
            "preview": preview,
            "token_count": token_count,
        }
    )

    return {
        "file_id": file_id,
        "preview": preview,
        "token_count": token_count,
        "metadata": {
            "filename": file_name,
            "size": len(file_bytes),
            "created_at": created_at,
        },
    }


@router.post("/tier2")
def research_tier2(
    payload: dict[str, Any],
    _token: TokenPayload = Depends(require_roles("researcher", "doctor")),
) -> dict[str, Any]:
    upstream_payload = dict(payload)
    uploaded_documents = _build_uploaded_documents(payload.get("uploaded_file_ids"))
    if uploaded_documents or payload.get("source_mode") == "uploaded_files":
        upstream_payload["uploaded_documents"] = uploaded_documents

    return proxy_ml_post(
        "/v1/research/tier2",
        upstream_payload,
        fail_soft_payload=_research_tier2_fallback_payload(payload),
    )
