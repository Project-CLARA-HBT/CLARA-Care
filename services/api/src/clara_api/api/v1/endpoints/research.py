import asyncio
import hashlib
import json
import math
import os
import re
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from threading import Lock
from typing import Any
from urllib.parse import quote, urljoin, urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.attribution import (
    attach_attribution,
    build_attribution,
    normalize_source_errors,
    normalize_source_used,
)
from clara_api.core.config import get_settings
from clara_api.core.control_tower import get_control_tower_config_service
from clara_api.core.control_tower.defaults import get_default_control_tower_config
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    KnowledgeDocument,
    KnowledgeSource,
    ResearchJob,
    SessionModel,
    SystemSetting,
    User,
)
from clara_api.db.models import (
    Query as QueryModel,
)
from clara_api.db.session import SessionLocal, get_db
from clara_api.schemas import (
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpdateRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceResponse,
    KnowledgeSourceUpdateRequest,
    ResearchConversationCreateRequest,
    ResearchConversationListResponse,
    ResearchConversationMessageResponse,
    ResearchConversationMessagesResponse,
    ResearchConversationResponse,
    ResearchTier2JobCreateRequest,
    ResearchTier2JobResponse,
    SourceHubCatalogEntry,
    SourceHubRecord,
    SourceHubRecordsResponse,
    SourceHubSourceKey,
    SourceHubSyncRequest,
    SourceHubSyncResponse,
)

router = APIRouter()

_MAX_RESEARCH_UPLOADS = 200
_PREVIEW_CHAR_LIMIT = 500
_MAX_EXTRACTED_TEXT_CHARS = 20_000
_DEFAULT_SOURCE_NAME = "General Uploads"
_TEXT_FILE_EXTENSIONS = {
    ".csv",
    ".json",
    ".log",
    ".markdown",
    ".md",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
_IMAGE_FILE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
_SOURCE_HUB_SETTING_KEY = "source_hub_records_v1"
_SOURCE_HUB_MAX_RECORDS = 500
_SOURCE_HUB_TIMEOUT_SECONDS = 12.0
_TRUE_VALUES = {"1", "true", "yes", "on"}
_SOURCE_HUB_SNIPPET_CHAR_LIMIT = 300
_DEFAULT_MARKDOWN_RENDER_HINTS: dict[str, Any] = {
    "markdown": True,
    "tables": True,
    "mermaid": True,
    "chart_spec_fences": [
        "chart-spec",
        "vega-lite",
        "echarts-option",
        "json",
        "yaml",
    ],
}
_VN_HTML_SOURCE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "vn_moh": {
        "label": "Bộ Y tế Việt Nam",
        "docs_url": "https://moh.gov.vn/",
        "default_query": "huong dan chan doan dieu tri",
        "search_urls": (
            "https://moh.gov.vn/tim-kiem?q={query_q}",
            "https://moh.gov.vn/",
        ),
    },
    "vn_kcb": {
        "label": "Cục Quản lý Khám chữa bệnh",
        "docs_url": "https://kcb.vn/",
        "default_query": "huong dan kham chua benh",
        "search_urls": (
            "https://kcb.vn/?s={query_q}",
            "https://kcb.vn/",
        ),
    },
    "vn_canhgiacduoc": {
        "label": "Trung tâm Quốc gia về Thông tin thuốc và Theo dõi phản ứng có hại của thuốc",
        "docs_url": "https://canhgiacduoc.org.vn/",
        "default_query": "canh giac duoc ADR",
        "search_urls": (
            "https://canhgiacduoc.org.vn/?s={query_q}",
            "https://canhgiacduoc.org.vn/",
        ),
    },
    "vn_vbpl_byt": {
        "label": "VBPL Bộ Y tế",
        "docs_url": "https://vbpl.vn/boyte/Pages/home.aspx",
        "default_query": "thong tu bo y te",
        "search_urls": (
            "https://vbpl.vn/boyte/pages/default.aspx?keyword={query_q}",
            "https://vbpl.vn/boyte/Pages/home.aspx",
        ),
    },
    "vn_dav": {
        "label": "Cục Quản lý Dược Việt Nam",
        "docs_url": "https://dav.gov.vn/",
        "default_query": "thu hoi thuoc",
        "search_urls": (
            "https://dav.gov.vn/?s={query_q}",
            "https://dav.gov.vn/",
        ),
    },
}

_uploaded_research_files: dict[str, dict[str, Any]] = {}
_uploaded_research_lock = Lock()
_research_job_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="research-tier2")
_research_job_futures: dict[str, Future[Any]] = {}
_research_job_lock = Lock()


def _load_research_rag_runtime(db: Session) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        control_tower = get_control_tower_config_service().load(db)
        return control_tower.rag_flow.model_dump(), [
            item.model_dump() for item in control_tower.rag_sources
        ]
    except Exception:  # pragma: no cover - defensive path for runtime resilience
        fallback = get_default_control_tower_config()
        return fallback.rag_flow.model_dump(), [item.model_dump() for item in fallback.rag_sources]


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


def _decode_text_payload(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("utf-8", errors="replace")


def _normalize_extracted_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()[:_MAX_EXTRACTED_TEXT_CHARS]


def _extract_text_like_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    decoded = _decode_text_payload(file_bytes)
    extension = _guess_extension(filename)
    if content_type == "application/json" or extension == ".json":
        try:
            parsed = json.loads(decoded)
        except json.JSONDecodeError:
            return decoded
        try:
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return _normalize_extracted_text(decoded)
    return _normalize_extracted_text(decoded)


def _extract_pdf_text(file_bytes: bytes) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except Exception:
        return "", "PDF đã tải lên nhưng chưa thể trích xuất text vì thiếu parser `pypdf`."

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception as exc:
        return "", f"PDF đã được tải lên nhưng không đọc được nội dung ({exc.__class__.__name__})."

    pages_text: list[str] = []
    for page in reader.pages[:20]:
        try:
            extracted = page.extract_text() or ""
        except Exception:
            extracted = ""
        normalized = _normalize_extracted_text(extracted)
        if normalized:
            pages_text.append(normalized)

    if not pages_text:
        return "", "PDF đã tải lên nhưng không trích xuất được text hữu ích."
    return _normalize_extracted_text("\n\n".join(pages_text)), ""


def _extract_image_metadata_text(file_bytes: bytes, filename: str) -> tuple[str, str]:
    try:
        from PIL import Image, UnidentifiedImageError
    except Exception:
        return "", "Ảnh đã tải lên nhưng môi trường chưa có parser metadata."

    try:
        with Image.open(BytesIO(file_bytes)) as image_obj:
            width, height = image_obj.size
            image_format = (image_obj.format or _guess_extension(filename).lstrip(".")).upper()
            mode = image_obj.mode or "unknown"
            frame_count = int(getattr(image_obj, "n_frames", 1) or 1)
            parts = [
                f"image_format={image_format or 'UNKNOWN'}",
                f"size={width}x{height}",
                f"mode={mode}",
            ]
            if frame_count > 1:
                parts.append(f"frames={frame_count}")
            return _normalize_extracted_text("Image metadata: " + ", ".join(parts)), ""
    except (UnidentifiedImageError, OSError):
        return "", "Ảnh đã tải lên nhưng không đọc được metadata."
    except Exception as exc:
        return "", f"Ảnh đã tải lên nhưng parse metadata thất bại ({exc.__class__.__name__})."


def _is_truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _extract_image_text_with_ocr(
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> tuple[str, str]:
    if not _is_truthy_env("RESEARCH_UPLOAD_IMAGE_OCR", default=True):
        return "", ""

    try:
        from clara_api.api.v1.endpoints.careguard import _scan_with_tgc_ocr
    except Exception:
        return "", ""

    try:
        extracted_text, _used_endpoint, _provider = _scan_with_tgc_ocr(
            file_bytes=file_bytes,
            file_name=filename,
            content_type=content_type,
        )
    except HTTPException as exc:
        detail = str(exc.detail).strip() if isinstance(exc.detail, str) else ""
        if detail:
            return "", f"Ảnh đã tải lên nhưng OCR không khả dụng: {detail}"
        return "", "Ảnh đã tải lên nhưng OCR không khả dụng."
    except Exception:
        return "", "Ảnh đã tải lên nhưng OCR không khả dụng."

    normalized = _normalize_extracted_text(extracted_text)
    if not normalized:
        return "", "Ảnh đã tải lên nhưng OCR không trích xuất được text hữu ích."
    return normalized, ""


def _extract_basic_text(file_bytes: bytes, filename: str, content_type: str) -> tuple[str, str]:
    if _is_text_file(filename, content_type):
        text = _extract_text_like_file(file_bytes, filename, content_type)
        return text, "text"

    if _is_pdf_file(filename, content_type):
        extracted_pdf_text, pdf_message = _extract_pdf_text(file_bytes)
        if extracted_pdf_text:
            return extracted_pdf_text, "text"
        return pdf_message, "pdf"

    if _is_image_file(filename, content_type):
        metadata_text, metadata_message = _extract_image_metadata_text(file_bytes, filename)
        extracted_image_text, image_message = _extract_image_text_with_ocr(
            file_bytes,
            filename,
            content_type,
        )
        if extracted_image_text and metadata_text:
            merged = _normalize_extracted_text(
                f"{metadata_text}\n\nOCR text:\n{extracted_image_text}"
            )
            return merged, "text"
        if extracted_image_text:
            return extracted_image_text, "text"
        if image_message:
            return image_message, "image"
        if metadata_text:
            return metadata_text, "text"
        return metadata_message, "image"

    return "File đã tải lên. Định dạng này chưa hỗ trợ trích xuất text tự động.", "other"


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


def _serialize_knowledge_document(document: KnowledgeDocument) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(
        id=document.id,
        source_id=document.source_id,
        filename=document.filename,
        content_type=document.content_type,
        size=document.size,
        preview=document.preview,
        token_count=document.token_count,
        is_active=document.is_active,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _serialize_knowledge_source(
    source: KnowledgeSource,
    *,
    documents_count: int,
) -> KnowledgeSourceResponse:
    return KnowledgeSourceResponse(
        id=source.id,
        name=source.name,
        description=source.description,
        is_active=source.is_active,
        created_at=source.created_at,
        updated_at=source.updated_at,
        documents_count=documents_count,
    )


def _get_user_by_token(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Người dùng không tồn tại"
        )
    return user


def _coerce_stored_result(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    if not stripped:
        return {"tier": "tier1", "answer": ""}

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return {"tier": "tier1", "answer": stripped}

    if not isinstance(parsed, dict):
        return {"tier": "tier1", "answer": stripped}

    payload = parsed.get("result")
    result = payload if isinstance(payload, dict) else parsed
    if "tier" not in result:
        if any(
            key in result
            for key in (
                "citations",
                "flowEvents",
                "flow_events",
                "telemetry",
                "source_attempts",
                "source_errors",
                "fallback_reason",
                "query_plan",
            )
        ):
            result = {"tier": "tier2", **result}
        else:
            result = {"tier": "tier1", **result}
    return result


def _serialize_research_conversation(
    *,
    session_obj: SessionModel,
    query_obj: QueryModel,
) -> ResearchConversationResponse:
    result_payload = _coerce_stored_result(query_obj.response_text)
    tier = str(result_payload.get("tier") or "tier1").strip().lower()
    if tier not in {"tier1", "tier2"}:
        tier = "tier1"
        result_payload["tier"] = tier

    created_at = query_obj.created_at or session_obj.created_at
    if created_at is None:
        created_at = datetime.now(tz=UTC)

    return ResearchConversationResponse(
        id=session_obj.id,
        query_id=query_obj.id,
        query=query_obj.user_input,
        result=result_payload,
        tier=tier,
        created_at=created_at,
    )


def _serialize_research_message(query_obj: QueryModel) -> ResearchConversationMessageResponse:
    result_payload = _coerce_stored_result(query_obj.response_text)
    tier = str(result_payload.get("tier") or "tier1").strip().lower()
    if tier not in {"tier1", "tier2"}:
        tier = "tier1"
        result_payload["tier"] = tier

    created_at = query_obj.created_at or datetime.now(tz=UTC)
    return ResearchConversationMessageResponse(
        query_id=query_obj.id,
        query=query_obj.user_input,
        tier=tier,  # type: ignore[arg-type]
        result=result_payload,
        created_at=created_at,
    )


def _validate_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(result)
    tier = str(payload.get("tier") or "").strip().lower()
    if tier not in {"tier1", "tier2"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="result.tier phải là 'tier1' hoặc 'tier2'.",
        )
    payload["tier"] = tier
    return payload


def _get_owned_source(db: Session, *, source_id: int, owner_user_id: int) -> KnowledgeSource:
    source = db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.owner_user_id == owner_user_id,
        )
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source không tồn tại"
        )
    return source


def _get_owned_document(db: Session, *, document_id: int, owner_user_id: int) -> KnowledgeDocument:
    document = db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.owner_user_id == owner_user_id,
        )
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document không tồn tại")
    return document


def _get_or_create_default_source(db: Session, owner_user_id: int) -> KnowledgeSource:
    source = db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.owner_user_id == owner_user_id,
            KnowledgeSource.name == _DEFAULT_SOURCE_NAME,
        )
    ).scalar_one_or_none()
    if source:
        return source

    source = KnowledgeSource(
        owner_user_id=owner_user_id,
        name=_DEFAULT_SOURCE_NAME,
        description="Nguồn mặc định cho upload nhanh từ màn hình chat/research",
        is_active=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _build_source_documents(
    db: Session,
    *,
    owner_user_id: int,
    source_ids: list[int],
) -> list[dict[str, Any]]:
    if not source_ids:
        return []

    source_ids_set = sorted(set(source_ids))
    source_rows = (
        db.execute(
            select(KnowledgeSource.id).where(
                KnowledgeSource.owner_user_id == owner_user_id,
                KnowledgeSource.id.in_(source_ids_set),
                KnowledgeSource.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    valid_source_ids = set(source_rows)
    if not valid_source_ids:
        return []

    documents = (
        db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.owner_user_id == owner_user_id,
                KnowledgeDocument.source_id.in_(sorted(valid_source_ids)),
                KnowledgeDocument.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )

    return [
        {
            "file_id": f"knowledge-doc-{document.id}",
            "filename": document.filename,
            "content_type": document.content_type,
            "size": document.size,
            "created_at": document.created_at.isoformat(),
            "text": document.extracted_text,
            "preview": document.preview,
            "token_count": document.token_count,
            "source": f"knowledge-source-{document.source_id}",
        }
        for document in documents
    ]


def _extract_source_hub_sources(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("source_hub_sources")
    values: list[str] = []
    if isinstance(raw, list):
        values = [str(item).strip().lower() for item in raw if str(item).strip()]
    elif isinstance(raw, str) and raw.strip():
        values = [raw.strip().lower()]
    allowed = {
        "pubmed",
        "europepmc",
        "semantic_scholar",
        "clinicaltrials",
        "rxnorm",
        "openfda",
        "dailymed",
        "vn_moh",
        "vn_kcb",
        "vn_canhgiacduoc",
        "vn_vbpl_byt",
        "vn_dav",
        "davidrug",
    }
    return {item for item in values if item in allowed}


def _build_source_hub_documents(
    db: Session,
    *,
    owner_user_id: int,
    query: str,
    source_filters: set[str],
    limit: int = 40,
) -> list[dict[str, Any]]:
    records = _load_source_hub_records(db, owner_user_id)
    query_terms = {term.strip().lower() for term in query.split() if len(term.strip()) >= 3}

    matched: list[SourceHubRecord] = []
    for record in records:
        if source_filters and record.source not in source_filters:
            continue
        haystack = " ".join(
            part for part in [record.title or "", record.snippet or "", record.query or ""] if part
        ).lower()
        if query_terms and not any(term in haystack for term in query_terms):
            continue
        matched.append(record)
        if len(matched) >= max(1, int(limit)):
            break

    docs: list[dict[str, Any]] = []
    for index, record in enumerate(matched, start=1):
        text_parts = [record.title]
        if record.snippet:
            text_parts.append(record.snippet)
        if record.metadata:
            compact_meta = ", ".join(
                f"{key}={value}"
                for key, value in list(record.metadata.items())[:4]
                if value not in (None, "", [])
            )
            if compact_meta:
                text_parts.append(compact_meta)
        docs.append(
            {
                "file_id": f"source-hub-{record.id}",
                "filename": f"{record.source}-{index}",
                "content_type": "text/plain",
                "size": 0,
                "created_at": record.synced_at or datetime.now(tz=UTC).isoformat(),
                "text": " | ".join(part for part in text_parts if part),
                "preview": (record.snippet or record.title or "")[:_PREVIEW_CHAR_LIMIT],
                "token_count": _approx_token_count(" ".join(text_parts)),
                "source": f"source_hub_{record.source}",
                "url": record.url,
            }
        )
    return docs


def _extract_source_ids(payload: dict[str, Any]) -> list[int]:
    raw_sources: list[Any] = []
    for key in ("source_ids", "knowledge_source_ids"):
        value = payload.get(key)
        if isinstance(value, list):
            raw_sources.extend(value)

    parsed: list[int] = []
    for item in raw_sources:
        if isinstance(item, int):
            parsed.append(item)
            continue
        if isinstance(item, str) and item.strip().isdigit():
            parsed.append(int(item.strip()))
    return parsed


def _coerce_research_mode(payload: dict[str, Any]) -> str:
    raw_mode = str(payload.get("research_mode") or payload.get("mode") or "fast").strip().lower()
    if raw_mode in {"deep", "deep_research", "long"}:
        return "deep"
    return "fast"


def _research_tier2_fallback_payload(payload: dict[str, Any]) -> dict[str, Any]:
    research_mode = _coerce_research_mode(payload)
    fallback_answer_text = (
        "Hệ thống truy xuất chuyên sâu đang bận hoặc tạm thời không kết nối được nguồn RAG. "
        "Tạm thời dùng chế độ an toàn: bạn nên ưu tiên phác đồ chính thống, "
        "đối chiếu tương tác thuốc quan trọng, "
        "và trao đổi bác sĩ khi có bệnh nền hoặc dấu hiệu nặng."
    )
    fallback_answer_markdown = (
        "## Kết luận nhanh\n"
        f"{fallback_answer_text}\n\n"
        "## Phân tích chi tiết\n"
        "- Luồng nghiên cứu chuyên sâu tạm thời không khả dụng, "
        "nên câu trả lời này dùng chế độ an toàn.\n"
        "- Ưu tiên xác minh lại thông tin với nguồn chuyên môn hoặc bác sĩ điều trị.\n\n"
        "## Khuyến nghị an toàn\n"
        "- Không tự ý kê đơn hoặc điều chỉnh liều khi chưa có tư vấn chuyên môn.\n"
        "- Nếu có bệnh nền hoặc đa thuốc, cần tham khảo bác sĩ/dược sĩ trước khi áp dụng.\n\n"
        "## Nguồn tham chiếu\n"
        "- [1] Hệ thống không truy xuất được nguồn RAG trong phiên hiện tại."
    )
    return {
        "answer": fallback_answer_markdown,
        "answer_markdown": fallback_answer_markdown,
        "summary": fallback_answer_text,
        "answer_format": "markdown",
        "render_hints": dict(_DEFAULT_MARKDOWN_RENDER_HINTS),
        "metadata": {
            "research_mode": research_mode,
            "deep_pass_count": 0,
            "answer_format": "markdown",
            "render_hints": dict(_DEFAULT_MARKDOWN_RENDER_HINTS),
        },
        "context_debug": {},
        "flow_events": [],
        "citations": [],
        "fallback": True,
        "source_mode": payload.get("source_mode"),
        "research_mode": research_mode,
        "deep_pass_count": 0,
    }


def _first_dict(*values: Any) -> dict[str, Any] | None:
    for value in values:
        if isinstance(value, dict):
            return value
    return None


def _first_value(
    sources: list[dict[str, Any] | None],
    *,
    keys: tuple[str, ...],
) -> Any:
    for source in sources:
        if source is None:
            continue
        for key in keys:
            if key in source and source[key] is not None:
                return source[key]
    return None


_VERIFICATION_MATRIX_KEYS: tuple[str, ...] = (
    "verification_matrix",
    "claim_verification_matrix",
    "claim_matrix",
    "claims_matrix",
)
_CONTRADICTION_SUMMARY_KEYS: tuple[str, ...] = (
    "contradiction_summary",
    "contradictions_summary",
    "contradiction_report",
    "contradiction_overview",
)
_TRACE_CONTAINER_KEYS: tuple[str, ...] = (
    "trace_metadata",
    "trace_context",
    "otel_trace_metadata",
    "otel_trace_context",
    "otel_trace",
    "trace",
    "otel",
)
_TRACE_SCALAR_KEYS: tuple[str, ...] = (
    "trace_id",
    "span_id",
    "parent_span_id",
    "trace_flags",
    "trace_state",
    "tracestate",
    "traceparent",
    "sampled",
    "service_name",
    "service",
    "component",
)
_TRACE_HINT_KEYS: set[str] = {key.lower() for key in (*_TRACE_CONTAINER_KEYS, *_TRACE_SCALAR_KEYS)}


def _is_trace_key(key: str) -> bool:
    normalized = key.strip().lower()
    if not normalized:
        return False
    return (
        normalized in _TRACE_HINT_KEYS
        or normalized.startswith("trace")
        or normalized.startswith("otel")
    )


def _normalize_trace_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        compact = [item for item in value if isinstance(item, (str, int, float, bool))]
        return compact[:20] if compact else None
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for raw_key, nested_value in value.items():
            normalized_nested = _normalize_trace_value(nested_value)
            if normalized_nested is None:
                continue
            compact[str(raw_key)] = normalized_nested
        return compact or None
    return None


def _extract_trace_metadata(
    sources: list[dict[str, Any] | None],
) -> dict[str, Any] | None:
    trace_metadata: dict[str, Any] = {}

    for source in sources:
        if source is None:
            continue

        for container_key in _TRACE_CONTAINER_KEYS:
            candidate = source.get(container_key)
            if not isinstance(candidate, dict):
                continue
            for raw_key, raw_value in candidate.items():
                key_text = str(raw_key)
                if not _is_trace_key(key_text):
                    continue
                normalized_value = _normalize_trace_value(raw_value)
                if normalized_value is None:
                    continue
                trace_metadata.setdefault(key_text, normalized_value)

        for scalar_key in _TRACE_SCALAR_KEYS:
            raw_value = source.get(scalar_key)
            normalized_value = _normalize_trace_value(raw_value)
            if normalized_value is None:
                continue
            trace_metadata.setdefault(scalar_key, normalized_value)

    return trace_metadata or None


def _build_tier2_telemetry(
    *,
    normalized: dict[str, Any],
    metadata_obj: dict[str, Any] | None,
    context_debug_obj: dict[str, Any] | None,
) -> dict[str, Any] | None:
    telemetry_root = _first_dict(
        normalized.get("telemetry"),
        metadata_obj.get("telemetry") if metadata_obj else None,
        normalized.get("debug_telemetry"),
        metadata_obj.get("debug_telemetry") if metadata_obj else None,
        context_debug_obj.get("telemetry") if context_debug_obj else None,
    )
    telemetry = dict(telemetry_root) if telemetry_root else {}
    retrieval_trace = (
        context_debug_obj.get("retrieval_trace")
        if context_debug_obj and isinstance(context_debug_obj.get("retrieval_trace"), dict)
        else {}
    )
    retriever_debug = (
        retrieval_trace.get("retriever_debug")
        if isinstance(retrieval_trace.get("retriever_debug"), dict)
        else {}
    )

    debug_obj = _first_dict(
        normalized.get("debug"),
        metadata_obj.get("debug") if metadata_obj else None,
    )
    trace_metadata = _extract_trace_metadata(
        [
            telemetry,
            normalized,
            metadata_obj,
            context_debug_obj,
            retrieval_trace if isinstance(retrieval_trace, dict) else None,
            debug_obj,
        ]
    )
    sources: list[dict[str, Any] | None] = [
        telemetry,
        normalized,
        metadata_obj,
        context_debug_obj,
        debug_obj,
    ]

    if "keywords" not in telemetry:
        keywords = _first_value(
            sources,
            keys=(
                "keywords",
                "query_keywords",
                "keyword_list",
                "matched_keywords",
                "intent_keywords",
            ),
        )
        if keywords is not None:
            telemetry["keywords"] = keywords

    if "search_plan" not in telemetry:
        search_plan = _first_value(
            sources,
            keys=("search_plan", "search_trace", "query_plan"),
        )
        if search_plan is None and isinstance(retrieval_trace, dict):
            search_plan = retrieval_trace.get("search_plan")
        if search_plan is not None:
            telemetry["search_plan"] = search_plan

    if "query_plan" not in telemetry:
        query_plan = _first_value(
            sources,
            keys=("query_plan", "search_plan", "search_trace"),
        )
        if query_plan is None and isinstance(retrieval_trace, dict):
            query_plan = retrieval_trace.get("query_plan")
            if query_plan is None:
                query_plan = retrieval_trace.get("search_plan")
        if query_plan is not None:
            telemetry["query_plan"] = query_plan

    if "query_plan" not in telemetry and "search_plan" in telemetry:
        telemetry["query_plan"] = telemetry.get("search_plan")
    if "search_plan" not in telemetry and "query_plan" in telemetry:
        telemetry["search_plan"] = telemetry.get("query_plan")

    if "source_attempts" not in telemetry:
        source_attempts = _first_value(
            sources,
            keys=(
                "source_attempts",
                "connector_attempts",
                "provider_events",
                "retrieval_attempts",
            ),
        )
        if source_attempts is None and isinstance(retriever_debug, dict):
            source_attempts = retriever_debug.get("source_attempts")
            if source_attempts is None:
                source_attempts = retriever_debug.get("provider_events")
        if source_attempts is not None:
            telemetry["source_attempts"] = source_attempts

    if "index_summary" not in telemetry:
        index_summary = _first_value(
            sources,
            keys=("index_summary", "rerank_summary", "ranking_summary"),
        )
        if index_summary is None and isinstance(retrieval_trace, dict):
            index_summary = retrieval_trace.get("index_summary")
        if index_summary is None and isinstance(retriever_debug, dict):
            index_summary = retriever_debug.get("index_summary")
        if index_summary is not None:
            telemetry["index_summary"] = index_summary

    if "crawl_summary" not in telemetry:
        crawl_summary = _first_value(
            sources,
            keys=("crawl_summary", "web_crawl_summary", "crawl_trace"),
        )
        if crawl_summary is None and isinstance(retrieval_trace, dict):
            crawl_summary = retrieval_trace.get("crawl_summary")
        if crawl_summary is None and isinstance(retriever_debug, dict):
            crawl_summary = retriever_debug.get("crawl_summary")
        if crawl_summary is not None:
            telemetry["crawl_summary"] = crawl_summary

    if "docs" not in telemetry:
        docs = _first_value(
            sources,
            keys=(
                "docs",
                "documents",
                "retrieved_docs",
                "retrieved_context",
                "context_docs",
                "context_documents",
                "evidence_docs",
                "top_docs",
                "candidates",
            ),
        )
        if docs is None:
            docs = _first_value(
                [retriever_debug],
                keys=("top_documents", "documents", "context_docs"),
            )
        if docs is not None:
            telemetry["docs"] = docs

    if "scores" not in telemetry:
        scores = _first_value(
            sources,
            keys=(
                "scores",
                "score_breakdown",
                "score_map",
                "metrics",
                "context_scores",
                "ranking_scores",
                "source_scores",
            ),
        )
        if scores is not None:
            telemetry["scores"] = scores
        else:
            score_map: dict[str, Any] = {}
            relevance = _first_value(
                sources,
                keys=("relevance", "context_relevance", "retrieval_score"),
            )
            threshold = _first_value(sources, keys=("low_context_threshold", "threshold"))
            if relevance is not None:
                score_map["relevance"] = relevance
            if threshold is not None:
                score_map["low_context_threshold"] = threshold
            if score_map:
                telemetry["scores"] = score_map

    if "source_reasoning" not in telemetry:
        source_reasoning = _first_value(
            sources,
            keys=(
                "source_reasoning",
                "source_reasonings",
                "reasoning_by_source",
                "per_source_reasoning",
                "source_notes",
            ),
        )
        if source_reasoning is None:
            source_reasoning = _first_value(
                [retriever_debug],
                keys=("score_trace", "final_score_trace"),
            )
        if source_reasoning is not None:
            telemetry["source_reasoning"] = source_reasoning

    if "errors" not in telemetry:
        errors = _first_value(
            sources,
            keys=(
                "errors",
                "error",
                "error_list",
                "source_errors",
                "retrieval_errors",
                "failed_sources",
            ),
        )
        if errors is None:
            errors = _first_value([retriever_debug], keys=("source_errors",))
        if errors is not None:
            telemetry["errors"] = errors
        elif isinstance(normalized.get("fallback_reason"), str):
            telemetry["errors"] = [normalized["fallback_reason"]]

    if "verification_matrix" not in telemetry:
        verification_matrix = _first_value(
            sources,
            keys=_VERIFICATION_MATRIX_KEYS,
        )
        if verification_matrix is not None:
            telemetry["verification_matrix"] = verification_matrix

    if "contradiction_summary" not in telemetry:
        contradiction_summary = _first_value(
            sources,
            keys=_CONTRADICTION_SUMMARY_KEYS,
        )
        if contradiction_summary is not None:
            telemetry["contradiction_summary"] = contradiction_summary

    if "trace_metadata" not in telemetry and trace_metadata is not None:
        telemetry["trace_metadata"] = trace_metadata

    return telemetry or None


def _normalize_tier2_response(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    metadata = normalized.get("metadata")
    metadata_obj = metadata if isinstance(metadata, dict) else None
    if metadata is not None and metadata_obj is None:
        normalized["metadata"] = {}

    if "context_debug" not in normalized and metadata_obj is not None:
        nested_context_debug = metadata_obj.get("context_debug")
        if isinstance(nested_context_debug, dict):
            normalized["context_debug"] = nested_context_debug

    context_debug_obj = normalized.get("context_debug")
    if not isinstance(context_debug_obj, dict):
        context_debug_obj = None

    if "flow_events" not in normalized and metadata_obj is not None:
        nested_flow_events = metadata_obj.get("flow_events")
        if isinstance(nested_flow_events, list):
            normalized["flow_events"] = nested_flow_events

    metadata_telemetry_obj = (
        metadata_obj.get("telemetry")
        if metadata_obj is not None and isinstance(metadata_obj.get("telemetry"), dict)
        else None
    )
    retrieval_trace_obj = (
        context_debug_obj.get("retrieval_trace")
        if context_debug_obj is not None
        and isinstance(context_debug_obj.get("retrieval_trace"), dict)
        else None
    )

    if "source_attempts" not in normalized:
        source_attempts = _first_value(
            [metadata_obj, metadata_telemetry_obj, context_debug_obj, retrieval_trace_obj],
            keys=(
                "source_attempts",
                "connector_attempts",
                "provider_events",
                "retrieval_attempts",
            ),
        )
        if source_attempts is not None:
            normalized["source_attempts"] = source_attempts

    if "source_errors" not in normalized:
        source_errors = _first_value(
            [metadata_obj, metadata_telemetry_obj, context_debug_obj, retrieval_trace_obj],
            keys=("source_errors", "retrieval_errors"),
        )
        if source_errors is not None:
            normalized["source_errors"] = source_errors

    if "fallback_reason" not in normalized:
        fallback_reason = _first_value(
            [metadata_obj, metadata_telemetry_obj, context_debug_obj, retrieval_trace_obj],
            keys=("fallback_reason",),
        )
        if isinstance(fallback_reason, str):
            stripped_reason = fallback_reason.strip()
            if stripped_reason:
                normalized["fallback_reason"] = stripped_reason

    if "verification_matrix" not in normalized:
        verification_matrix = _first_value(
            [metadata_obj, metadata_telemetry_obj, context_debug_obj, retrieval_trace_obj],
            keys=_VERIFICATION_MATRIX_KEYS,
        )
        if verification_matrix is not None:
            normalized["verification_matrix"] = verification_matrix

    if "contradiction_summary" not in normalized:
        contradiction_summary = _first_value(
            [metadata_obj, metadata_telemetry_obj, context_debug_obj, retrieval_trace_obj],
            keys=_CONTRADICTION_SUMMARY_KEYS,
        )
        if contradiction_summary is not None:
            normalized["contradiction_summary"] = contradiction_summary

    if "trace_metadata" not in normalized:
        trace_metadata = _extract_trace_metadata(
            [
                normalized,
                metadata_obj,
                metadata_telemetry_obj,
                context_debug_obj,
                retrieval_trace_obj,
            ]
        )
        if trace_metadata is not None:
            normalized["trace_metadata"] = trace_metadata

    if "query_plan" not in normalized:
        query_plan = _first_value(
            [metadata_obj, metadata_telemetry_obj, context_debug_obj, retrieval_trace_obj],
            keys=("query_plan", "search_plan", "search_trace"),
        )
        if query_plan is not None:
            normalized["query_plan"] = query_plan

    if "query_plan" not in normalized and normalized.get("search_plan") is not None:
        normalized["query_plan"] = normalized.get("search_plan")
    if "search_plan" not in normalized and normalized.get("query_plan") is not None:
        normalized["search_plan"] = normalized.get("query_plan")

    telemetry = _build_tier2_telemetry(
        normalized=normalized,
        metadata_obj=metadata_obj,
        context_debug_obj=context_debug_obj,
    )
    if telemetry is not None:
        normalized["telemetry"] = telemetry
        if "source_attempts" not in normalized and telemetry.get("source_attempts") is not None:
            normalized["source_attempts"] = telemetry.get("source_attempts")
        if "query_plan" not in normalized and telemetry.get("query_plan") is not None:
            normalized["query_plan"] = telemetry.get("query_plan")
        if "search_plan" not in normalized and telemetry.get("search_plan") is not None:
            normalized["search_plan"] = telemetry.get("search_plan")
        if "verification_matrix" not in normalized and telemetry.get("verification_matrix") is not None:
            normalized["verification_matrix"] = telemetry.get("verification_matrix")
        if (
            "contradiction_summary" not in normalized
            and telemetry.get("contradiction_summary") is not None
        ):
            normalized["contradiction_summary"] = telemetry.get("contradiction_summary")
        if "trace_metadata" not in normalized:
            telemetry_trace_metadata = _extract_trace_metadata([telemetry])
            if telemetry_trace_metadata is not None:
                normalized["trace_metadata"] = telemetry_trace_metadata
        if "source_errors" not in normalized:
            telemetry_source_errors = telemetry.get("source_errors")
            if telemetry_source_errors is None and isinstance(telemetry.get("errors"), dict):
                telemetry_source_errors = telemetry.get("errors")
            if telemetry_source_errors is not None:
                normalized["source_errors"] = telemetry_source_errors

    if "source_errors" in normalized:
        normalized["source_errors"] = normalize_source_errors(normalized.get("source_errors"))

    answer_markdown = normalized.get("answer_markdown")
    if not isinstance(answer_markdown, str) or not answer_markdown.strip():
        for key in ("answer", "summary", "message"):
            candidate = normalized.get(key)
            if isinstance(candidate, str) and candidate.strip():
                normalized["answer_markdown"] = candidate
                break

    if not isinstance(normalized.get("answer_format"), str):
        normalized["answer_format"] = "markdown"
    if not isinstance(normalized.get("render_hints"), dict):
        normalized["render_hints"] = dict(_DEFAULT_MARKDOWN_RENDER_HINTS)

    return normalized


def _extract_research_source_used(normalized: dict[str, Any]) -> list[str]:
    metadata_obj = (
        normalized.get("metadata")
        if isinstance(normalized.get("metadata"), dict)
        else {}
    )
    telemetry_obj = (
        normalized.get("telemetry")
        if isinstance(normalized.get("telemetry"), dict)
        else {}
    )

    source_used = normalize_source_used(
        normalized.get("source_used") or metadata_obj.get("source_used") or []
    )
    source_attempts = normalized.get("source_attempts")
    if not isinstance(source_attempts, list):
        source_attempts = telemetry_obj.get("source_attempts")
    if not isinstance(source_attempts, list):
        source_attempts = metadata_obj.get("source_attempts")
    if isinstance(source_attempts, list):
        for attempt in source_attempts:
            if not isinstance(attempt, dict):
                continue
            for key in ("source", "provider", "connector", "name"):
                raw_value = attempt.get(key)
                if raw_value is None:
                    continue
                normalized_value = str(raw_value).strip().lower()
                if normalized_value and normalized_value not in source_used:
                    source_used.append(normalized_value)
                break

    citations = normalized.get("citations")
    if isinstance(citations, list):
        for citation in citations:
            if isinstance(citation, str):
                normalized_value = citation.strip().lower()
            elif isinstance(citation, dict):
                normalized_value = str(
                    citation.get("source") or citation.get("id") or citation.get("title") or ""
                ).strip().lower()
            else:
                normalized_value = ""
            if normalized_value and normalized_value not in source_used:
                source_used.append(normalized_value)

    return source_used


def _attach_research_attribution(normalized: dict[str, Any]) -> dict[str, Any]:
    metadata_obj = (
        normalized.get("metadata")
        if isinstance(normalized.get("metadata"), dict)
        else {}
    )
    telemetry_obj = (
        normalized.get("telemetry")
        if isinstance(normalized.get("telemetry"), dict)
        else {}
    )
    source_used = _extract_research_source_used(normalized)
    source_errors = normalize_source_errors(
        normalized.get("source_errors")
        or metadata_obj.get("source_errors")
        or telemetry_obj.get("source_errors")
        or (
            telemetry_obj.get("errors")
            if isinstance(telemetry_obj.get("errors"), dict)
            else {}
        )
        or {}
    )
    if "source_errors" not in normalized and source_errors:
        normalized["source_errors"] = source_errors
    mode = str(
        normalized.get("research_mode")
        or metadata_obj.get("research_mode")
        or "fast"
    ).strip().lower()
    if mode not in {"fast", "deep"}:
        mode = "fast"

    sources = [
        {
            "id": source_id,
            "name": source_id.replace("_", " ").title(),
            "type": "retrieval",
            "category": "research",
        }
        for source_id in source_used
    ]
    fallback_reason = normalized.get("fallback_reason")
    if not isinstance(fallback_reason, str) or not fallback_reason.strip():
        metadata_fallback_reason = metadata_obj.get("fallback_reason")
        if isinstance(metadata_fallback_reason, str) and metadata_fallback_reason.strip():
            fallback_reason = metadata_fallback_reason.strip()
            normalized["fallback_reason"] = fallback_reason
        else:
            fallback_reason = ""
    fallback_used = bool(
        normalized.get("fallback_used")
        or metadata_obj.get("fallback_used")
        or normalized.get("fallback")
        or fallback_reason
    )
    if fallback_used:
        normalized["fallback"] = True

    attribution = build_attribution(
        channel="research",
        mode=mode,
        sources=sources,
        citations_payload=normalized.get("citations"),
        source_used=source_used,
        source_errors=source_errors,
        fallback_used=fallback_used,
    )
    return attach_attribution(normalized, attribution=attribution)


def _build_tier2_upstream_payload(
    payload: dict[str, Any],
    *,
    db: Session,
    user: User,
    token: TokenPayload,
) -> dict[str, Any]:
    settings = get_settings()
    upstream_payload = dict(payload)
    upstream_payload["answer_format"] = str(upstream_payload.get("answer_format") or "markdown")
    upstream_payload["response_format"] = str(upstream_payload.get("response_format") or "markdown")
    incoming_render_hints = upstream_payload.get("render_hints")
    if isinstance(incoming_render_hints, dict):
        merged_render_hints = {
            **_DEFAULT_MARKDOWN_RENDER_HINTS,
            **incoming_render_hints,
        }
    else:
        merged_render_hints = dict(_DEFAULT_MARKDOWN_RENDER_HINTS)
    upstream_payload["render_hints"] = merged_render_hints
    transient_documents = _build_uploaded_documents(payload.get("uploaded_file_ids"))
    source_ids = _extract_source_ids(payload)
    source_documents = _build_source_documents(db, owner_user_id=user.id, source_ids=source_ids)
    source_hub_filters = _extract_source_hub_sources(payload)
    source_hub_documents = _build_source_hub_documents(
        db,
        owner_user_id=user.id,
        query=str(payload.get("query") or payload.get("message") or ""),
        source_filters=source_hub_filters,
    )
    uploaded_documents = [*transient_documents, *source_documents, *source_hub_documents]

    if uploaded_documents or payload.get("source_mode") in {"uploaded_files", "knowledge_sources"}:
        upstream_payload["uploaded_documents"] = uploaded_documents
    upstream_payload["role"] = token.role
    upstream_payload["strict_deepseek_required"] = bool(settings.deepseek_strict_mode)
    runtime_rag_flow, runtime_rag_sources = _load_research_rag_runtime(db)

    incoming_rag_flow = upstream_payload.get("rag_flow")
    if isinstance(incoming_rag_flow, dict):
        upstream_payload["rag_flow"] = {**runtime_rag_flow, **incoming_rag_flow}
    else:
        upstream_payload["rag_flow"] = runtime_rag_flow

    incoming_rag_sources = upstream_payload.get("rag_sources")
    if not isinstance(incoming_rag_sources, list):
        upstream_payload["rag_sources"] = runtime_rag_sources

    return upstream_payload


def _empty_job_progress() -> dict[str, Any]:
    return {
        "flow_events": [],
        "flow_stages": [],
        "active_stage": "",
        "status_note": "",
        "reasoning_steps": [],
    }


def _stage_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stage_map: dict[str, dict[str, Any]] = {}
    for event in events:
        stage = str(event.get("stage") or "").strip()
        if not stage:
            continue
        item = stage_map.get(stage) or {
            "id": stage,
            "label": stage.replace("_", " ").title(),
            "status": "pending",
            "detail": "",
            "source": "flow_events",
        }
        event_status = str(event.get("status") or "").strip().lower() or "pending"
        item["status"] = event_status
        if isinstance(event.get("note"), str) and event.get("note"):
            item["detail"] = event["note"]
        stage_map[stage] = item
    return list(stage_map.values())


def _append_job_event(
    db: Session,
    *,
    job: ResearchJob,
    stage: str,
    status_text: str,
    note: str,
    payload: dict[str, Any] | None = None,
) -> None:
    if isinstance(job.progress_json, dict):
        progress = dict(job.progress_json)
    else:
        progress = _empty_job_progress()
    events = progress.get("flow_events")
    if not isinstance(events, list):
        events = []
    else:
        events = [item for item in events if isinstance(item, dict)]
    event_item: dict[str, Any] = {
        "id": str(uuid4()),
        "stage": stage,
        "status": status_text,
        "note": note,
        "component": "research_job",
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }
    if payload:
        event_item["payload"] = payload
    events.append(event_item)
    progress["flow_events"] = list(events[-80:])
    progress["flow_stages"] = _stage_from_events(progress["flow_events"])
    progress["active_stage"] = stage
    progress["status_note"] = note
    reasoning_steps = progress.get("reasoning_steps")
    if not isinstance(reasoning_steps, list):
        reasoning_steps = []
    else:
        reasoning_steps = [item for item in reasoning_steps if isinstance(item, dict)]
    reasoning_steps.append(
        {
            "stage": stage,
            "status": status_text,
            "note": note,
            "timestamp": event_item["timestamp"],
        }
    )
    progress["reasoning_steps"] = list(reasoning_steps[-40:])
    job.progress_json = json.loads(json.dumps(progress, ensure_ascii=False))
    job.updated_at = datetime.now(tz=UTC)
    db.add(job)
    db.commit()


def _serialize_research_job(job: ResearchJob) -> ResearchTier2JobResponse:
    progress = job.progress_json if isinstance(job.progress_json, dict) else _empty_job_progress()
    result = job.result_json if isinstance(job.result_json, dict) else None
    return ResearchTier2JobResponse(
        job_id=job.job_id,
        status=str(job.status or "queued"),  # type: ignore[arg-type]
        query=job.query_text,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        progress=progress,
        result=result,
        error=job.error_text or None,
    )


def _build_fail_soft_response_local(
    fail_soft_payload: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    response = dict(fail_soft_payload)
    response.setdefault("metadata", {})
    response.setdefault("citations", [])
    response.setdefault("fallback", True)
    response.setdefault("fallback_reason", reason)
    return response


def _estimate_reasoning_phase(elapsed_seconds: float) -> tuple[str, str, int]:
    if elapsed_seconds < 15:
        return ("scope_question", "Đang phân tích câu hỏi và xác định phạm vi.", 15)
    if elapsed_seconds < 35:
        return ("collect_evidence", "Đang truy xuất evidence từ nguồn nội bộ và nguồn live.", 40)
    if elapsed_seconds < 60:
        return ("synthesize_findings", "Đang tổng hợp điểm đồng thuận và phát hiện mâu thuẫn.", 70)
    if elapsed_seconds < 90:
        return ("verification", "Đang kiểm chứng claim theo bằng chứng truy xuất.", 88)
    return ("final_response", "Đang hoàn thiện câu trả lời và chuẩn hóa citation.", 95)


def _invoke_ml_tier2_with_progress(
    *,
    ml_payload: dict[str, Any],
    fail_soft_payload: dict[str, Any] | None,
    heartbeat: Callable[[float], None],
) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/v1/research/tier2"
    timeout_seconds = max(settings.ml_service_timeout_seconds * 3.0, 480.0)
    started = datetime.now(tz=UTC)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="research-ml-call") as executor:
        future = executor.submit(httpx.post, url, json=ml_payload, timeout=timeout_seconds)
        while True:
            try:
                response = future.result(timeout=2.0)
                break
            except FutureTimeoutError:
                elapsed = (datetime.now(tz=UTC) - started).total_seconds()
                heartbeat(elapsed)
                continue
    if response.status_code >= 500:
        if fail_soft_payload is not None:
            return _build_fail_soft_response_local(
                fail_soft_payload, f"status_{response.status_code}"
            )
        raise RuntimeError(f"ml_upstream_status_{response.status_code}")
    if response.status_code >= 400:
        if fail_soft_payload is not None:
            return _build_fail_soft_response_local(
                fail_soft_payload, f"status_{response.status_code}"
            )
        raise RuntimeError(f"ml_rejected_status_{response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        if fail_soft_payload is not None:
            return _build_fail_soft_response_local(fail_soft_payload, "InvalidJSON")
        raise RuntimeError("ml_invalid_json") from exc

    if not isinstance(data, dict):
        if fail_soft_payload is not None:
            return _build_fail_soft_response_local(
                fail_soft_payload, "UnexpectedPayloadFormat"
            )
        raise RuntimeError("ml_unexpected_payload_format")
    return data


def _run_research_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        settings = get_settings()
        job = db.execute(
            select(ResearchJob).where(ResearchJob.job_id == job_id)
        ).scalar_one_or_none()
        if job is None:
            return
        job.status = "running"
        job.started_at = datetime.now(tz=UTC)
        db.add(job)
        db.commit()
        _append_job_event(
            db,
            job=job,
            stage="dispatch_ml",
            status_text="in_progress",
            note="Đã gửi yêu cầu lên ML service, đang chạy reasoning nhiều bước.",
        )
        request_payload = job.request_payload if isinstance(job.request_payload, dict) else {}
        last_heartbeat_bucket = -1

        def _heartbeat(elapsed_seconds: float) -> None:
            nonlocal last_heartbeat_bucket
            # Emit heartbeat every ~10s and avoid duplicate messages in same 10s bucket.
            bucket = int(elapsed_seconds // 10)
            if bucket <= 0 or bucket == last_heartbeat_bucket:
                return
            last_heartbeat_bucket = bucket
            phase, note, progress_percent = _estimate_reasoning_phase(elapsed_seconds)
            _append_job_event(
                db,
                job=job,
                stage="reasoning",
                status_text="in_progress",
                note=note,
                payload={
                    "elapsed_seconds": round(elapsed_seconds, 1),
                    "heartbeat_seq": bucket,
                    "phase": phase,
                    "progress_percent": progress_percent,
                    "research_mode": str(request_payload.get("research_mode") or "deep"),
                    "source_mode": str(request_payload.get("source_mode") or "hybrid"),
                },
            )

        ml_response = _invoke_ml_tier2_with_progress(
            ml_payload=request_payload,
            fail_soft_payload=(
                None
                if settings.deepseek_strict_mode
                else _research_tier2_fallback_payload(request_payload)
            ),
            heartbeat=_heartbeat,
        )
        normalized = _normalize_tier2_response(ml_response)
        enriched = _attach_research_attribution(normalized)
        job.result_json = enriched
        job.status = "completed"
        job.completed_at = datetime.now(tz=UTC)
        db.add(job)
        db.commit()
        _append_job_event(
            db,
            job=job,
            stage="final_response",
            status_text="completed",
            note="Đã hoàn tất trả lời, có thể render Markdown đầy đủ.",
            payload={
                "fallback_used": bool(
                    enriched.get("fallback") or enriched.get("fallback_reason")
                ),
                "source_count": len(enriched.get("sources", []))
                if isinstance(enriched.get("sources"), list)
                else 0,
            },
        )
        flow_events = enriched.get("flow_events")
        if isinstance(flow_events, list) and flow_events:
            if isinstance(job.progress_json, dict):
                progress = dict(job.progress_json)
            else:
                progress = _empty_job_progress()
            history_events = progress.get("flow_events")
            if not isinstance(history_events, list):
                history_events = []
            merged = [*history_events, *[item for item in flow_events if isinstance(item, dict)]]
            progress["flow_events"] = merged[-120:]
            progress["flow_stages"] = _stage_from_events(progress["flow_events"])
            progress["active_stage"] = "final_response"
            progress["status_note"] = "Đã nhận flow events đầy đủ từ ML."
            job.progress_json = json.loads(json.dumps(progress, ensure_ascii=False))
            db.add(job)
            db.commit()
    except Exception as exc:  # pragma: no cover - defensive runtime protection
        try:
            job = db.execute(
                select(ResearchJob).where(ResearchJob.job_id == job_id)
            ).scalar_one_or_none()
            if job is not None:
                job.status = "failed"
                job.error_text = str(exc)
                job.completed_at = datetime.now(tz=UTC)
                db.add(job)
                db.commit()
                _append_job_event(
                    db,
                    job=job,
                    stage="final_response",
                    status_text="failed",
                    note=f"Lỗi khi chạy research job: {exc}",
                )
        except Exception:
            pass
    finally:
        db.close()
        with _research_job_lock:
            _research_job_futures.pop(job_id, None)


def _queue_research_job(job_id: str) -> None:
    with _research_job_lock:
        future = _research_job_executor.submit(_run_research_job, job_id)
        _research_job_futures[job_id] = future


_SOURCE_HUB_CATALOG: tuple[SourceHubCatalogEntry, ...] = (
    SourceHubCatalogEntry(
        key="pubmed",
        label="PubMed",
        description="NCBI PubMed biomedical literature via E-utilities",
        docs_url="https://www.ncbi.nlm.nih.gov/books/NBK25501/",
        default_query="diabetes type 2 guideline",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="rxnorm",
        label="RxNorm",
        description="NLM RxNorm normalized clinical drug names via RxNav",
        docs_url="https://lhncbc.nlm.nih.gov/RxNav/APIs/index.html",
        default_query="metformin",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="openfda",
        label="openFDA",
        description="US FDA drug label and safety data",
        docs_url="https://open.fda.gov/apis/",
        default_query="statin",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="dailymed",
        label="DailyMed",
        description="NLM/FDA SPL drug label feed",
        docs_url="https://dailymed.nlm.nih.gov/dailymed/webservices-help.cfm",
        default_query="warfarin",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="europepmc",
        label="Europe PMC",
        description="Biomedical literature and abstracts",
        docs_url="https://europepmc.org/RestfulWebService",
        default_query="warfarin ibuprofen interaction",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="semantic_scholar",
        label="Semantic Scholar",
        description="Academic graph search for biomedical papers",
        docs_url="https://api.semanticscholar.org/api-docs/graph",
        default_query="warfarin nsaid bleeding risk",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="clinicaltrials",
        label="ClinicalTrials.gov",
        description="Clinical study registry and metadata",
        docs_url="https://clinicaltrials.gov/data-api/about-api",
        default_query="warfarin interaction",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="vn_moh",
        label="Bộ Y tế Việt Nam",
        description="Tin tức và văn bản điều hành chính thức từ Cổng thông tin Bộ Y tế",
        docs_url="https://moh.gov.vn/",
        default_query="huong dan chan doan dieu tri",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="vn_kcb",
        label="Cục Quản lý Khám chữa bệnh",
        description="Thông báo, công văn và hướng dẫn khám chữa bệnh từ kcb.vn",
        docs_url="https://kcb.vn/",
        default_query="huong dan kham chua benh",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="vn_canhgiacduoc",
        label="Cảnh giác Dược Quốc gia",
        description="Bản tin cảnh giác dược và theo dõi phản ứng có hại của thuốc",
        docs_url="https://canhgiacduoc.org.vn/",
        default_query="canh giac duoc ADR",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="vn_vbpl_byt",
        label="VBPL Bộ Y tế",
        description="Văn bản pháp quy lĩnh vực y tế trên hệ thống VBPL",
        docs_url="https://vbpl.vn/boyte/Pages/home.aspx",
        default_query="thong tu bo y te",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="vn_dav",
        label="Cục Quản lý Dược Việt Nam",
        description="Thông tin quản lý dược, công bố và thông báo chuyên ngành từ dav.gov.vn",
        docs_url="https://dav.gov.vn/",
        default_query="thu hoi thuoc",
        supports_live_sync=True,
    ),
    SourceHubCatalogEntry(
        key="davidrug",
        label="DAVIDrug",
        description="Cục Quản lý Dược Việt Nam (public web data fallback)",
        docs_url="https://dichvucong.dav.gov.vn/congbothuoc/index",
        default_query="paracetamol",
        supports_live_sync=True,
    ),
)


def _source_hub_setting_key(owner_user_id: int) -> str:
    return f"{_SOURCE_HUB_SETTING_KEY}:{owner_user_id}"


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    return ""


def _normalize_source_hub_record(record: dict[str, Any]) -> SourceHubRecord | None:
    source = _to_text(record.get("source")).lower()
    if source not in {
        "pubmed",
        "rxnorm",
        "openfda",
        "dailymed",
        "europepmc",
        "semantic_scholar",
        "clinicaltrials",
        "vn_moh",
        "vn_kcb",
        "vn_canhgiacduoc",
        "vn_vbpl_byt",
        "vn_dav",
        "davidrug",
    }:
        return None
    title = _to_text(record.get("title"))
    if not title:
        return None

    record_id = _to_text(record.get("id")) or str(uuid4())
    metadata_raw = record.get("metadata")
    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}

    return SourceHubRecord(
        id=record_id,
        source=source,  # type: ignore[arg-type]
        title=title,
        url=_to_text(record.get("url")) or None,
        snippet=_to_text(record.get("snippet")) or None,
        external_id=_to_text(record.get("external_id")) or None,
        query=_to_text(record.get("query")) or None,
        published_at=_to_text(record.get("published_at")) or None,
        synced_at=_to_text(record.get("synced_at")) or None,
        metadata=metadata,
    )


def _load_source_hub_records(db: Session, owner_user_id: int) -> list[SourceHubRecord]:
    setting = db.execute(
        select(SystemSetting).where(SystemSetting.key == _source_hub_setting_key(owner_user_id))
    ).scalar_one_or_none()
    if not setting or not isinstance(setting.value_json, dict):
        return []

    raw_records = setting.value_json.get("records")
    if not isinstance(raw_records, list):
        return []

    parsed: list[SourceHubRecord] = []
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_source_hub_record(item)
        if normalized is not None:
            parsed.append(normalized)
    return parsed


def _save_source_hub_records(
    db: Session, owner_user_id: int, records: list[SourceHubRecord]
) -> None:
    key = _source_hub_setting_key(owner_user_id)
    setting = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    payload = {
        "records": [record.model_dump() for record in records[:_SOURCE_HUB_MAX_RECORDS]],
        "updated_at": datetime.now(tz=UTC).isoformat(),
    }
    if setting is None:
        setting = SystemSetting(key=key, value_json=payload, value_text="")
    else:
        setting.value_json = payload
    db.add(setting)
    db.commit()


def _merge_source_hub_records(
    existing: list[SourceHubRecord], incoming: list[SourceHubRecord]
) -> list[SourceHubRecord]:
    dedup: dict[str, SourceHubRecord] = {}
    for item in [*incoming, *existing]:
        dedup[item.id] = item

    merged = sorted(
        dedup.values(),
        key=lambda record: record.synced_at or "",
        reverse=True,
    )
    return merged[:_SOURCE_HUB_MAX_RECORDS]


def _http_get_json(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    with httpx.Client(timeout=_SOURCE_HUB_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _http_get_text(url: str, *, params: dict[str, Any] | None = None) -> str:
    with httpx.Client(timeout=_SOURCE_HUB_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
    response.raise_for_status()
    return response.text


def _http_post_json(url: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=_SOURCE_HUB_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=payload)
    response.raise_for_status()
    body = response.json()
    return body if isinstance(body, dict) else {}


class _LightAnchorExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self._skip_depth = 0
        self._in_anchor = False
        self._anchor_href = ""
        self._anchor_title = ""
        self._anchor_text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if normalized_tag != "a":
            return
        attributes = {str(key).lower(): _to_text(value) for key, value in attrs if key}
        self._in_anchor = True
        self._anchor_href = _to_text(attributes.get("href"))
        self._anchor_title = _to_text(attributes.get("title")) or _to_text(
            attributes.get("aria-label")
        )
        self._anchor_text_chunks = []

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style", "noscript"}:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth > 0:
            return
        if normalized_tag != "a" or not self._in_anchor:
            return

        text = _normalize_html_text(" ".join(self._anchor_text_chunks))
        title = _normalize_html_text(self._anchor_title) or text
        if self._anchor_href and title:
            self.items.append(
                {
                    "href": self._anchor_href,
                    "title": title,
                    "snippet": text[:_SOURCE_HUB_SNIPPET_CHAR_LIMIT],
                }
            )

        self._in_anchor = False
        self._anchor_href = ""
        self._anchor_title = ""
        self._anchor_text_chunks = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0 or not self._in_anchor:
            return
        text = _normalize_html_text(data)
        if text:
            self._anchor_text_chunks.append(text)


def _normalize_html_text(value: str) -> str:
    cleaned = unescape(value or "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _build_query_terms(query: str) -> list[str]:
    terms = [part for part in re.split(r"[^\w]+", query.lower()) if len(part.strip()) >= 2]
    if not terms and query.strip():
        return [query.strip().lower()]
    return list(dict.fromkeys(terms))


def _resolve_source_hub_url(page_url: str, href: str) -> str:
    raw_href = href.strip()
    if not raw_href or raw_href.startswith("#"):
        return ""
    if raw_href.lower().startswith(("javascript:", "mailto:", "tel:")):
        return ""
    resolved = urljoin(page_url, raw_href)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return resolved


def _extract_anchor_candidates(html_text: str, page_url: str) -> list[dict[str, str]]:
    parser = _LightAnchorExtractor()
    parser.feed(html_text)
    parser.close()

    candidates: list[dict[str, str]] = []
    for item in parser.items:
        title = _to_text(item.get("title"))
        href = _to_text(item.get("href"))
        if not title or not href:
            continue
        resolved_url = _resolve_source_hub_url(page_url, href)
        if not resolved_url:
            continue
        snippet = _to_text(item.get("snippet"))
        if snippet == title:
            snippet = ""
        candidates.append(
            {
                "title": title,
                "url": resolved_url,
                "snippet": snippet[:_SOURCE_HUB_SNIPPET_CHAR_LIMIT],
            }
        )
    return candidates


def _extract_published_date(value: str) -> str | None:
    for pattern, year_idx, month_idx, day_idx in (
        (r"(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)", 1, 2, 3),
        (r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})(?!\d)", 3, 2, 1),
    ):
        matched = re.search(pattern, value)
        if not matched:
            continue
        try:
            year = int(matched.group(year_idx))
            month = int(matched.group(month_idx))
            day = int(matched.group(day_idx))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            continue
    return None


def _external_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    path_value = f"{parsed.netloc}{parsed.path}?{parsed.query}".strip("?").lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", path_value).strip("-")
    if normalized:
        return normalized[:120]
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:32]


def _build_vn_source_urls(source: str, query: str) -> list[str]:
    source_def = _VN_HTML_SOURCE_DEFINITIONS.get(source)
    if not isinstance(source_def, dict):
        return []
    search_urls = source_def.get("search_urls")
    if not isinstance(search_urls, (list, tuple)):
        return []

    query_text = query.strip()
    query_q = quote(query_text)
    urls: list[str] = []
    for template in search_urls:
        if not isinstance(template, str):
            continue
        text = template.strip()
        if not text:
            continue
        try:
            candidate = text.format(query=query_text, query_q=query_q)
        except Exception:
            candidate = text
        urls.append(candidate)
    return list(dict.fromkeys(urls))


def _fetch_vn_html_source_records(
    source: SourceHubSourceKey,
    query: str,
    limit: int,
    synced_at: str,
) -> tuple[list[SourceHubRecord], list[str]]:
    source_def = _VN_HTML_SOURCE_DEFINITIONS.get(source)
    if not isinstance(source_def, dict):
        return [], [f"Nguồn không được hỗ trợ: {source}"]

    source_label = _to_text(source_def.get("label")) or source
    safe_limit = max(1, min(500, int(limit)))
    query_terms = _build_query_terms(query)
    page_urls = _build_vn_source_urls(source, query)

    records: list[SourceHubRecord] = []
    warnings: list[str] = []
    seen_urls: set[str] = set()
    seen_ids: set[str] = set()
    crawl_errors = 0

    for page_url in page_urls:
        try:
            html = _http_get_text(page_url)
        except Exception:
            crawl_errors += 1
            continue

        for item in _extract_anchor_candidates(html, page_url):
            title = _to_text(item.get("title"))
            record_url = _to_text(item.get("url"))
            snippet = _to_text(item.get("snippet"))
            if not title or not record_url:
                continue
            if record_url in seen_urls:
                continue

            haystack = f"{title} {snippet} {record_url}".lower()
            if query_terms and not any(term in haystack for term in query_terms):
                continue

            external_id = _external_id_from_url(record_url)
            record_id = f"{source}:{external_id}"
            if record_id in seen_ids:
                continue

            seen_ids.add(record_id)
            seen_urls.add(record_url)
            records.append(
                SourceHubRecord(
                    id=record_id,
                    source=source,
                    title=title,
                    url=record_url,
                    snippet=snippet[:_SOURCE_HUB_SNIPPET_CHAR_LIMIT] or None,
                    external_id=external_id,
                    query=query,
                    published_at=_extract_published_date(f"{title} {snippet} {record_url}"),
                    synced_at=synced_at,
                    metadata={
                        "crawl_url": page_url,
                        "source_label": source_label,
                        "query_terms": query_terms[:8],
                    },
                )
            )
            if len(records) >= safe_limit:
                break
        if len(records) >= safe_limit:
            break

    if not records:
        if crawl_errors >= len(page_urls) and page_urls:
            warnings.append(f"{source_label} hiện không truy cập được để crawl HTML.")
        else:
            warnings.append(f"{source_label} không có kết quả phù hợp cho query này.")
    elif crawl_errors:
        warnings.append(
            f"{source_label} có một số URL crawl lỗi ({crawl_errors}/{len(page_urls)})."
        )

    return records[:safe_limit], warnings


def _fetch_pubmed_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    warnings: list[str] = []
    search = _http_get_json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"},
    )
    search_result = search.get("esearchresult")
    if not isinstance(search_result, dict):
        return [], ["PubMed trả dữ liệu không đúng định dạng esearchresult."]

    id_list_raw = search_result.get("idlist")
    id_list = (
        [str(item).strip() for item in id_list_raw if str(item).strip()]
        if isinstance(id_list_raw, list)
        else []
    )
    if not id_list:
        return [], ["PubMed không có kết quả phù hợp cho query hiện tại."]

    summary = _http_get_json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(id_list[:limit]), "retmode": "json"},
    )
    result = summary.get("result")
    if not isinstance(result, dict):
        return [], ["PubMed không trả được summary chi tiết."]

    uids_raw = result.get("uids")
    uids = (
        [str(item).strip() for item in uids_raw if str(item).strip()]
        if isinstance(uids_raw, list)
        else []
    )

    records: list[SourceHubRecord] = []
    for uid in uids[:limit]:
        item = result.get(uid)
        if not isinstance(item, dict):
            continue
        title = _to_text(item.get("title"))
        if not title:
            continue
        journal = _to_text(item.get("fulljournalname")) or _to_text(item.get("source"))
        pubdate = _to_text(item.get("pubdate"))
        snippet = " | ".join(part for part in [journal, pubdate] if part).strip()
        records.append(
            SourceHubRecord(
                id=f"pubmed:{uid}",
                source="pubmed",
                title=title,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                snippet=snippet or None,
                external_id=uid,
                query=query,
                published_at=pubdate or None,
                synced_at=synced_at,
                metadata={
                    "authors": item.get("authors"),
                    "pubtype": item.get("pubtype"),
                    "doi": item.get("elocationid"),
                },
            )
        )

    if not records:
        warnings.append("PubMed trả về bản ghi rỗng sau bước summary.")
    return records, warnings


def _fetch_rxnorm_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    warnings: list[str] = []
    payload = _http_get_json(
        "https://rxnav.nlm.nih.gov/REST/approximateTerm.json",
        params={"term": query, "maxEntries": limit},
    )
    group = payload.get("approximateGroup")
    if not isinstance(group, dict):
        return [], ["RxNorm không trả về approximateGroup."]
    candidates = group.get("candidate")
    if not isinstance(candidates, list) or not candidates:
        return [], ["RxNorm không có candidate cho query này."]

    records: list[SourceHubRecord] = []
    for index, item in enumerate(candidates[:limit]):
        if not isinstance(item, dict):
            continue
        rxcui = _to_text(item.get("rxcui"))
        rank = _to_text(item.get("rank"))
        score = _to_text(item.get("score"))
        name = _to_text(item.get("name")) or f"RxNorm candidate {index + 1}"
        records.append(
            SourceHubRecord(
                id=f"rxnorm:{rxcui or index}",
                source="rxnorm",
                title=name,
                url=f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}"
                if rxcui
                else None,
                snippet=f"rxcui={rxcui or '-'} | score={score or '-'} | rank={rank or '-'}",
                external_id=rxcui or None,
                query=query,
                published_at=None,
                synced_at=synced_at,
                metadata=item,
            )
        )

    return records, warnings


def _fetch_openfda_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    warnings: list[str] = []
    escaped = query.replace('"', '\\"')
    payload = _http_get_json(
        "https://api.fda.gov/drug/label.json",
        params={"search": f'openfda.brand_name:"{escaped}"', "limit": limit},
    )
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return [], ["openFDA không có kết quả cho query này."]

    records: list[SourceHubRecord] = []
    for index, item in enumerate(results[:limit]):
        if not isinstance(item, dict):
            continue
        openfda = item.get("openfda")
        openfda_obj = openfda if isinstance(openfda, dict) else {}
        brand_names = openfda_obj.get("brand_name")
        title = (
            _to_text(brand_names[0]) if isinstance(brand_names, list) and brand_names else ""
        ) or f"openFDA label {index + 1}"
        set_id_list = openfda_obj.get("set_id")
        set_id = _to_text(set_id_list[0]) if isinstance(set_id_list, list) and set_id_list else ""
        purpose = item.get("purpose")
        warning_text = item.get("warnings")
        snippet = _to_text(purpose[0]) if isinstance(purpose, list) and purpose else ""
        if not snippet:
            snippet = (
                _to_text(warning_text[0]) if isinstance(warning_text, list) and warning_text else ""
            )
        records.append(
            SourceHubRecord(
                id=f"openfda:{set_id or index}",
                source="openfda",
                title=title,
                url=None,
                snippet=snippet[:280] or None,
                external_id=set_id or None,
                query=query,
                published_at=None,
                synced_at=synced_at,
                metadata={"openfda": openfda_obj},
            )
        )
    return records, warnings


def _fetch_dailymed_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    warnings: list[str] = []
    escaped_query = quote(query.strip())
    payload = _http_get_json(
        f"https://dailymed.nlm.nih.gov/dailymed/services/v1/drugname/{escaped_query}/spls.json"
    )
    rows = payload.get("data")
    if not isinstance(rows, list) or not rows:
        return [], ["DailyMed không có kết quả cho query này."]

    records: list[SourceHubRecord] = []
    for index, item in enumerate(rows[:limit]):
        if not isinstance(item, list):
            continue
        set_id = _to_text(item[0] if len(item) > 0 else "")
        title = _to_text(item[1] if len(item) > 1 else "") or f"DailyMed label {index + 1}"
        version = _to_text(item[2] if len(item) > 2 else "")
        published = _to_text(item[3] if len(item) > 3 else "")
        records.append(
            SourceHubRecord(
                id=f"dailymed:{set_id or index}",
                source="dailymed",
                title=title,
                url=(
                    f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"
                    if set_id
                    else "https://dailymed.nlm.nih.gov/"
                ),
                snippet=" | ".join(part for part in [version, published] if part) or None,
                external_id=set_id or None,
                query=query,
                published_at=published or None,
                synced_at=synced_at,
                metadata={},
            )
        )

    if not records:
        warnings.append("DailyMed trả dữ liệu không hợp lệ sau khi parse.")
    return records, warnings


def _fetch_europepmc_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    warnings: list[str] = []
    payload = _http_get_json(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": max(1, min(50, int(limit))),
        },
    )
    result_list = payload.get("resultList")
    results = result_list.get("result") if isinstance(result_list, dict) else []
    if not isinstance(results, list) or not results:
        return [], ["Europe PMC không có kết quả cho query này."]

    records: list[SourceHubRecord] = []
    for index, item in enumerate(results[:limit]):
        if not isinstance(item, dict):
            continue
        source = _to_text(item.get("source")).lower() or "europepmc"
        source_id = _to_text(item.get("id"))
        title = _to_text(item.get("title")) or f"Europe PMC record {index + 1}"
        journal = _to_text(item.get("journalTitle"))
        pub_year = _to_text(item.get("pubYear"))
        if source == "med" and source_id:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{source_id}/"
        elif source_id:
            url = f"https://europepmc.org/article/{source.upper()}/{source_id}"
        else:
            url = "https://europepmc.org/"
        records.append(
            SourceHubRecord(
                id=f"europepmc:{source}:{source_id or index}",
                source="europepmc",
                title=title,
                url=url,
                snippet=" | ".join(part for part in [journal, pub_year] if part) or None,
                external_id=source_id or None,
                query=query,
                published_at=pub_year or None,
                synced_at=synced_at,
                metadata={"source_provider": source},
            )
        )

    if not records:
        warnings.append("Europe PMC trả dữ liệu không hợp lệ sau khi parse.")
    return records, warnings


def _fetch_semantic_scholar_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    warnings: list[str] = []
    payload = _http_get_json(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={
            "query": query,
            "limit": max(1, min(50, int(limit))),
            "fields": "paperId,title,year,url,venue,journal",
        },
    )
    rows = payload.get("data")
    if not isinstance(rows, list) or not rows:
        return [], ["Semantic Scholar không có kết quả cho query này."]

    records: list[SourceHubRecord] = []
    for index, item in enumerate(rows[:limit]):
        if not isinstance(item, dict):
            continue
        paper_id = _to_text(item.get("paperId"))
        title = _to_text(item.get("title")) or f"Semantic Scholar record {index + 1}"
        year = _to_text(item.get("year"))
        url = _to_text(item.get("url"))
        venue = _to_text(item.get("venue"))
        journal_obj = item.get("journal")
        journal = _to_text(journal_obj.get("name")) if isinstance(journal_obj, dict) else ""
        records.append(
            SourceHubRecord(
                id=f"semantic_scholar:{paper_id or index}",
                source="semantic_scholar",
                title=title,
                url=(
                    url
                    or (
                        f"https://www.semanticscholar.org/paper/{paper_id}"
                        if paper_id
                        else None
                    )
                ),
                snippet=" | ".join(part for part in [venue, journal, year] if part) or None,
                external_id=paper_id or None,
                query=query,
                published_at=year or None,
                synced_at=synced_at,
                metadata={},
            )
        )

    if not records:
        warnings.append("Semantic Scholar trả dữ liệu không hợp lệ sau khi parse.")
    return records, warnings


def _fetch_clinicaltrials_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    warnings: list[str] = []
    payload = _http_get_json(
        "https://clinicaltrials.gov/api/v2/studies",
        params={
            "query.term": query,
            "pageSize": max(1, min(50, int(limit))),
            "format": "json",
        },
    )
    studies = payload.get("studies")
    if not isinstance(studies, list) or not studies:
        return [], ["ClinicalTrials.gov không có kết quả cho query này."]

    records: list[SourceHubRecord] = []
    for index, item in enumerate(studies[:limit]):
        if not isinstance(item, dict):
            continue
        protocol = item.get("protocolSection")
        if not isinstance(protocol, dict):
            continue
        identification = protocol.get("identificationModule")
        status_module = protocol.get("statusModule")
        identification = identification if isinstance(identification, dict) else {}
        status_module = status_module if isinstance(status_module, dict) else {}

        nct_id = _to_text(identification.get("nctId"))
        title = _to_text(identification.get("briefTitle")) or f"Clinical trial {index + 1}"
        overall_status = _to_text(status_module.get("overallStatus"))
        start_date_obj = status_module.get("startDateStruct")
        start_date = (
            _to_text(start_date_obj.get("date"))
            if isinstance(start_date_obj, dict)
            else ""
        )

        records.append(
            SourceHubRecord(
                id=f"clinicaltrials:{nct_id or index}",
                source="clinicaltrials",
                title=title,
                url=(f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None),
                snippet=" | ".join(part for part in [overall_status, start_date] if part) or None,
                external_id=nct_id or None,
                query=query,
                published_at=start_date or None,
                synced_at=synced_at,
                metadata={},
            )
        )

    if not records:
        warnings.append("ClinicalTrials.gov trả dữ liệu không hợp lệ sau khi parse.")
    return records, warnings


def _fetch_davidrug_records(
    query: str, limit: int, synced_at: str
) -> tuple[list[SourceHubRecord], list[str]]:
    warnings: list[str] = []
    payload = _http_post_json(
        "https://dichvucong.dav.gov.vn/api/services/app/soDangKy/GetAllPublicServerPaging",
        payload={
            "filterText": query,
            "SoDangKyThuoc": {},
            "KichHoat": True,
            "skipCount": 0,
            "maxResultCount": max(1, min(100, int(limit))),
            "sorting": None,
        },
    )
    result_obj = payload.get("result")
    result = result_obj if isinstance(result_obj, dict) else {}
    rows_obj = result.get("items")
    rows = rows_obj if isinstance(rows_obj, list) else []
    if not rows:
        warnings.append("DAVIDrug không có kết quả phù hợp cho query này.")
        return [], warnings

    records: list[SourceHubRecord] = []
    for index, item in enumerate(rows[:limit]):
        if not isinstance(item, dict):
            continue
        external_id = _to_text(item.get("id")) or _to_text(item.get("soDangKy"))
        title = _to_text(item.get("tenThuoc")) or f"DAVIDrug record {index + 1}"
        so_dang_ky = _to_text(item.get("soDangKy"))

        company_obj = item.get("congTyDangKy")
        company = company_obj if isinstance(company_obj, dict) else {}
        registrant = _to_text(company.get("tenCongTyDangKy"))

        info_obj = item.get("thongTinThuocCoBan")
        info = info_obj if isinstance(info_obj, dict) else {}
        active_ingredient = _to_text(info.get("hoatChatChinh"))

        snippet_parts = [
            part
            for part in (
                f"SĐK: {so_dang_ky}" if so_dang_ky else "",
                f"Hoạt chất: {active_ingredient}" if active_ingredient else "",
                f"Đơn vị đăng ký: {registrant}" if registrant else "",
            )
            if part
        ]
        snippet = " | ".join(snippet_parts)[:300] or None

        register_obj = item.get("thongTinDangKyThuoc")
        register = register_obj if isinstance(register_obj, dict) else {}
        published_at = _to_text(register.get("ngayCapSoDangKy")) or None

        record_id = f"davidrug:{external_id or index}"
        records.append(
            SourceHubRecord(
                id=record_id,
                source="davidrug",
                title=title,
                url="https://dichvucong.dav.gov.vn/congbothuoc/index",
                snippet=snippet,
                external_id=external_id or None,
                query=query,
                published_at=published_at,
                synced_at=synced_at,
                metadata={
                    "so_dang_ky": so_dang_ky,
                    "dang_bao_che": _to_text(info.get("dangBaoChe")) or None,
                    "ham_luong": _to_text(info.get("hamLuong")) or None,
                    "active_ingredient": active_ingredient or None,
                    "registrant": registrant or None,
                },
            )
        )

    if not records:
        warnings.append("DAVIDrug trả dữ liệu không hợp lệ sau khi parse.")
    return records, warnings


def _fetch_source_hub_records(
    source: SourceHubSourceKey, query: str, limit: int
) -> tuple[list[SourceHubRecord], list[str]]:
    synced_at = datetime.now(tz=UTC).isoformat()
    if source == "pubmed":
        return _fetch_pubmed_records(query, limit, synced_at)
    if source == "rxnorm":
        return _fetch_rxnorm_records(query, limit, synced_at)
    if source == "openfda":
        return _fetch_openfda_records(query, limit, synced_at)
    if source == "dailymed":
        return _fetch_dailymed_records(query, limit, synced_at)
    if source == "europepmc":
        return _fetch_europepmc_records(query, limit, synced_at)
    if source == "semantic_scholar":
        return _fetch_semantic_scholar_records(query, limit, synced_at)
    if source == "clinicaltrials":
        return _fetch_clinicaltrials_records(query, limit, synced_at)
    if source in {
        "vn_moh",
        "vn_kcb",
        "vn_canhgiacduoc",
        "vn_vbpl_byt",
        "vn_dav",
    }:
        return _fetch_vn_html_source_records(source, query, limit, synced_at)
    if source == "davidrug":
        return _fetch_davidrug_records(query, limit, synced_at)
    return [], [f"Nguồn không được hỗ trợ: {source}"]


@router.get("/conversations")
def list_research_conversations(
    limit: int = 50,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> ResearchConversationListResponse:
    user = _get_user_by_token(db, token)
    safe_limit = max(1, min(200, int(limit)))

    sessions = (
        db.execute(
            select(SessionModel)
            .where(SessionModel.user_id == user.id)
            .order_by(SessionModel.created_at.desc(), SessionModel.id.desc())
            .limit(max(safe_limit * 3, safe_limit))
        )
        .scalars()
        .all()
    )

    items: list[ResearchConversationResponse] = []
    for session_obj in sessions:
        query_obj = db.execute(
            select(QueryModel)
            .where(QueryModel.session_id == session_obj.id)
            .order_by(QueryModel.created_at.desc(), QueryModel.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if query_obj is None:
            continue
        items.append(_serialize_research_conversation(session_obj=session_obj, query_obj=query_obj))
        if len(items) >= safe_limit:
            break

    return ResearchConversationListResponse(items=items)


@router.post("/conversations")
def create_research_conversation(
    payload: ResearchConversationCreateRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> ResearchConversationResponse:
    user = _get_user_by_token(db, token)
    query_text = payload.query.strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query không được rỗng.",
        )

    result_payload = _validate_result_payload(payload.result)
    try:
        stored_result = json.dumps({"result": result_payload}, ensure_ascii=False)
    except TypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"result chứa dữ liệu không thể lưu JSON: {exc}",
        ) from exc

    session_obj = SessionModel(
        user_id=user.id,
        title=query_text[:255],
    )
    db.add(session_obj)
    db.flush()

    query_obj = QueryModel(
        session_id=session_obj.id,
        role=token.role,
        user_input=query_text,
        response_text=stored_result,
    )
    db.add(query_obj)
    db.commit()
    db.refresh(session_obj)
    db.refresh(query_obj)

    return _serialize_research_conversation(session_obj=session_obj, query_obj=query_obj)


@router.get("/conversations/{conversation_id}/messages")
def list_research_conversation_messages(
    conversation_id: int,
    limit: int = 100,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> ResearchConversationMessagesResponse:
    user = _get_user_by_token(db, token)
    session_obj = db.execute(
        select(SessionModel).where(
            SessionModel.id == conversation_id,
            SessionModel.user_id == user.id,
        )
    ).scalar_one_or_none()
    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation không tồn tại.",
        )

    safe_limit = max(1, min(500, int(limit)))
    rows = (
        db.execute(
            select(QueryModel)
            .where(QueryModel.session_id == session_obj.id)
            .order_by(QueryModel.created_at.asc(), QueryModel.id.asc())
            .limit(safe_limit)
        )
        .scalars()
        .all()
    )
    return ResearchConversationMessagesResponse(
        conversation_id=session_obj.id,
        items=[_serialize_research_message(row) for row in rows],
    )


@router.post("/conversations/{conversation_id}/messages")
def append_research_conversation_message(
    conversation_id: int,
    payload: ResearchConversationCreateRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> ResearchConversationResponse:
    user = _get_user_by_token(db, token)
    session_obj = db.execute(
        select(SessionModel).where(
            SessionModel.id == conversation_id,
            SessionModel.user_id == user.id,
        )
    ).scalar_one_or_none()
    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation không tồn tại.",
        )

    query_text = payload.query.strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query không được rỗng.",
        )
    result_payload = _validate_result_payload(payload.result)
    try:
        stored_result = json.dumps({"result": result_payload}, ensure_ascii=False)
    except TypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"result chứa dữ liệu không thể lưu JSON: {exc}",
        ) from exc

    query_obj = QueryModel(
        session_id=session_obj.id,
        role=token.role,
        user_input=query_text,
        response_text=stored_result,
    )
    db.add(query_obj)
    session_obj.title = query_text[:255]
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    db.refresh(query_obj)
    return _serialize_research_conversation(session_obj=session_obj, query_obj=query_obj)


@router.delete("/conversations/{conversation_id}")
def delete_research_conversation(
    conversation_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _get_user_by_token(db, token)
    session_obj = db.execute(
        select(SessionModel).where(
            SessionModel.id == conversation_id,
            SessionModel.user_id == user.id,
        )
    ).scalar_one_or_none()
    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation không tồn tại.",
        )

    db.delete(session_obj)
    db.commit()
    return {"deleted": True}


@router.get("/knowledge-sources")
def list_knowledge_sources(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, list[KnowledgeSourceResponse]]:
    user = _get_user_by_token(db, token)
    sources = (
        db.execute(
            select(KnowledgeSource)
            .where(KnowledgeSource.owner_user_id == user.id)
            .order_by(KnowledgeSource.updated_at.desc())
        )
        .scalars()
        .all()
    )

    counts_rows = db.execute(
        select(KnowledgeDocument.source_id, func.count(KnowledgeDocument.id))
        .where(KnowledgeDocument.owner_user_id == user.id)
        .group_by(KnowledgeDocument.source_id)
    ).all()
    count_by_source = {int(source_id): int(total) for source_id, total in counts_rows}

    return {
        "items": [
            _serialize_knowledge_source(
                source,
                documents_count=count_by_source.get(source.id, 0),
            )
            for source in sources
        ]
    }


@router.post("/knowledge-sources")
def create_knowledge_source(
    payload: KnowledgeSourceCreateRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> KnowledgeSourceResponse:
    user = _get_user_by_token(db, token)
    source = KnowledgeSource(
        owner_user_id=user.id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        is_active=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _serialize_knowledge_source(source, documents_count=0)


@router.patch("/knowledge-sources/{source_id}")
def update_knowledge_source(
    source_id: int,
    payload: KnowledgeSourceUpdateRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> KnowledgeSourceResponse:
    user = _get_user_by_token(db, token)
    source = _get_owned_source(db, source_id=source_id, owner_user_id=user.id)

    if payload.name is not None:
        source.name = payload.name.strip()
    if payload.description is not None:
        source.description = payload.description.strip()
    if payload.is_active is not None:
        source.is_active = payload.is_active

    db.add(source)
    db.commit()
    db.refresh(source)

    documents_count = db.execute(
        select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.source_id == source.id,
            KnowledgeDocument.owner_user_id == user.id,
        )
    ).scalar_one()

    return _serialize_knowledge_source(source, documents_count=int(documents_count or 0))


@router.delete("/knowledge-sources/{source_id}")
def delete_knowledge_source(
    source_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _get_user_by_token(db, token)
    source = _get_owned_source(db, source_id=source_id, owner_user_id=user.id)
    db.delete(source)
    db.commit()
    return {"deleted": True}


@router.get("/knowledge-sources/{source_id}/documents")
def list_knowledge_documents(
    source_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, list[KnowledgeDocumentResponse]]:
    user = _get_user_by_token(db, token)
    _get_owned_source(db, source_id=source_id, owner_user_id=user.id)
    documents = (
        db.execute(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.source_id == source_id,
                KnowledgeDocument.owner_user_id == user.id,
            )
            .order_by(KnowledgeDocument.created_at.desc())
        )
        .scalars()
        .all()
    )

    return {"items": [_serialize_knowledge_document(item) for item in documents]}


@router.post("/knowledge-sources/{source_id}/upload-file")
async def upload_file_to_knowledge_source(
    source_id: int,
    file: UploadFile = File(...),
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _get_user_by_token(db, token)
    source = _get_owned_source(db, source_id=source_id, owner_user_id=user.id)

    file_name = file.filename or "uploaded-file"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File upload rỗng")

    extracted_text, file_kind = _extract_basic_text(file_bytes, file_name, content_type)
    preview = extracted_text[:_PREVIEW_CHAR_LIMIT]
    token_count = _approx_token_count(extracted_text if file_kind == "text" else "")

    document = KnowledgeDocument(
        source_id=source.id,
        owner_user_id=user.id,
        filename=file_name,
        content_type=content_type,
        size=len(file_bytes),
        extracted_text=extracted_text if file_kind == "text" else "",
        preview=preview,
        token_count=token_count,
        is_active=True,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return {
        "document": _serialize_knowledge_document(document),
        "source_id": source.id,
    }


@router.patch("/documents/{document_id}")
def update_knowledge_document(
    document_id: int,
    payload: KnowledgeDocumentUpdateRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> KnowledgeDocumentResponse:
    user = _get_user_by_token(db, token)
    document = _get_owned_document(db, document_id=document_id, owner_user_id=user.id)
    document.is_active = payload.is_active
    db.add(document)
    db.commit()
    db.refresh(document)
    return _serialize_knowledge_document(document)


@router.post("/upload-file")
async def upload_research_file(
    file: UploadFile = File(...),
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _get_user_by_token(db, token)

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

    default_source = _get_or_create_default_source(db, user.id)
    document = KnowledgeDocument(
        source_id=default_source.id,
        owner_user_id=user.id,
        filename=file_name,
        content_type=content_type,
        size=len(file_bytes),
        extracted_text=extracted_text if file_kind == "text" else "",
        preview=preview,
        token_count=token_count,
        is_active=True,
    )
    db.add(document)
    db.commit()

    return {
        "file_id": file_id,
        "preview": preview,
        "token_count": token_count,
        "metadata": {
            "filename": file_name,
            "size": len(file_bytes),
            "created_at": created_at,
            "knowledge_source_id": default_source.id,
        },
    }


@router.post("/tier2")
def research_tier2(
    payload: dict[str, Any],
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    settings = get_settings()
    user = _get_user_by_token(db, token)
    upstream_payload = _build_tier2_upstream_payload(payload, db=db, user=user, token=token)

    response = proxy_ml_post(
        "/v1/research/tier2",
        upstream_payload,
        fail_soft_payload=(
            None if settings.deepseek_strict_mode else _research_tier2_fallback_payload(payload)
        ),
    )
    normalized = _normalize_tier2_response(response)
    return _attach_research_attribution(normalized)


@router.post("/tier2/jobs")
def create_research_tier2_job(
    payload: ResearchTier2JobCreateRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> ResearchTier2JobResponse:
    user = _get_user_by_token(db, token)
    query_text = str(payload.query or payload.message or "").strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query không được rỗng.",
        )

    input_payload = payload.model_dump()
    input_payload["query"] = query_text
    input_payload["message"] = query_text
    upstream_payload = _build_tier2_upstream_payload(input_payload, db=db, user=user, token=token)

    now = datetime.now(tz=UTC)
    job_id = uuid4().hex
    job = ResearchJob(
        job_id=job_id,
        user_id=user.id,
        role=token.role,
        status="queued",
        query_text=query_text,
        request_payload=upstream_payload,
        progress_json=_empty_job_progress(),
        result_json=None,
        error_text="",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _append_job_event(
        db,
        job=job,
        stage="queue",
        status_text="completed",
        note="Đã tạo research job. Chuẩn bị chạy truy xuất chuyên sâu.",
    )
    _queue_research_job(job_id)
    db.refresh(job)
    return _serialize_research_job(job)


@router.get("/tier2/jobs/{job_id}")
def get_research_tier2_job(
    job_id: str,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> ResearchTier2JobResponse:
    user = _get_user_by_token(db, token)
    job = db.execute(
        select(ResearchJob).where(
            ResearchJob.job_id == job_id,
            ResearchJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research job không tồn tại.",
        )
    return _serialize_research_job(job)


def _build_research_job_stream_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def _sse_event(event_name: str, payload: dict[str, Any], event_id: str | None = None) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    lines: list[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    lines.append(f"data: {data}")
    return "\n".join(lines) + "\n\n"


@router.get("/tier2/jobs/{job_id}/stream")
async def stream_research_tier2_job(
    request: Request,
    job_id: str,
    heartbeat_seconds: int = 10,
    poll_interval_seconds: float = 0.8,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
):
    user = _get_user_by_token(db, token)
    user_id = int(user.id)
    existing = db.execute(
        select(ResearchJob).where(
            ResearchJob.job_id == job_id,
            ResearchJob.user_id == user_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research job không tồn tại.",
        )

    safe_poll_interval = min(max(float(poll_interval_seconds), 0.25), 5.0)
    safe_heartbeat = 5 if heartbeat_seconds < 5 else heartbeat_seconds

    def _load_job_snapshot() -> dict[str, Any] | None:
        # Use a fresh session for each read to avoid stale identity-map cache
        # during long-lived SSE connections.
        with SessionLocal() as fresh_db:
            current = fresh_db.execute(
                select(ResearchJob).where(
                    ResearchJob.job_id == job_id,
                    ResearchJob.user_id == user_id,
                )
            ).scalar_one_or_none()
            if current is None:
                return None
            return _serialize_research_job(current).model_dump(mode="json")

    async def event_stream():
        last_heartbeat_at = time.monotonic()
        last_signature = ""
        sequence = 0
        yield ": connected\n\n"

        while True:
            if await request.is_disconnected():
                break

            snapshot = _load_job_snapshot()
            if snapshot is None:
                sequence += 1
                yield _sse_event(
                    "error",
                    {"message": "Research job không còn khả dụng."},
                    event_id=str(sequence),
                )
                break

            signature = json.dumps(
                {
                    "status": snapshot.get("status"),
                    "updated_at": snapshot.get("updated_at"),
                    "completed_at": snapshot.get("completed_at"),
                    "error": snapshot.get("error"),
                    "progress": snapshot.get("progress"),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )

            if signature != last_signature:
                last_signature = signature
                sequence += 1
                yield _sse_event("progress", snapshot, event_id=str(sequence))
                last_heartbeat_at = time.monotonic()

            status_text = str(snapshot.get("status") or "").lower()
            if status_text in {"completed", "failed"}:
                sequence += 1
                yield _sse_event("done", snapshot, event_id=str(sequence))
                break

            if time.monotonic() - last_heartbeat_at >= safe_heartbeat:
                yield ": keepalive\n\n"
                last_heartbeat_at = time.monotonic()

            await asyncio.sleep(safe_poll_interval)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_build_research_job_stream_headers(),
    )


@router.get("/source-hub/catalog")
def source_hub_catalog(
    token: TokenPayload = Depends(require_roles("researcher", "doctor", "admin")),
) -> dict[str, list[SourceHubCatalogEntry]]:
    _ = token
    return {"sources": list(_SOURCE_HUB_CATALOG)}


@router.get("/source-hub/records")
def source_hub_records(
    source: str = "all",
    query: str = "",
    limit: int = 80,
    token: TokenPayload = Depends(require_roles("researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> SourceHubRecordsResponse:
    user = _get_user_by_token(db, token)
    items = _load_source_hub_records(db, user.id)

    normalized_source = source.strip().lower()
    if normalized_source and normalized_source != "all":
        items = [item for item in items if item.source == normalized_source]

    normalized_query = query.strip().lower()
    if normalized_query:
        items = [
            item
            for item in items
            if normalized_query in (item.title or "").lower()
            or normalized_query in (item.snippet or "").lower()
            or normalized_query in (item.query or "").lower()
        ]

    safe_limit = max(1, min(500, limit))
    return SourceHubRecordsResponse(records=items[:safe_limit])


@router.post("/source-hub/sync")
def source_hub_sync(
    payload: SourceHubSyncRequest,
    token: TokenPayload = Depends(require_roles("researcher", "doctor", "admin")),
    db: Session = Depends(get_db),
) -> SourceHubSyncResponse:
    user = _get_user_by_token(db, token)
    query = payload.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Query không được rỗng."
        )

    safe_limit = max(3, min(500, int(payload.limit)))
    try:
        records, warnings = _fetch_source_hub_records(payload.source, query, safe_limit)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout khi đồng bộ dữ liệu từ nguồn ngoài.",
        ) from None
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Lỗi nguồn ngoài ({exc.response.status_code}) khi sync {payload.source}.",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Không thể sync nguồn {payload.source}: {exc}",
        ) from exc

    # Ensure query/sync metadata always present even if source omitted them.
    synced_at = datetime.now(tz=UTC).isoformat()
    normalized_records = [
        SourceHubRecord(
            **{
                **record.model_dump(),
                "query": record.query or query,
                "synced_at": record.synced_at or synced_at,
            }
        )
        for record in records
    ]

    existing = _load_source_hub_records(db, user.id)
    merged = _merge_source_hub_records(existing, normalized_records)
    _save_source_hub_records(db, user.id, merged)

    return SourceHubSyncResponse(
        source=payload.source,
        query=query,
        fetched=len(normalized_records),
        stored=len(merged),
        records=normalized_records,
        warnings=warnings,
    )
