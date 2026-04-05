# ruff: noqa: B008

import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.markdown_docx import build_docx_bytes_from_markdown as render_docx_bytes
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import Query as QueryModel
from clara_api.db.models import (
    SessionModel,
    User,
    WorkspaceChannel,
    WorkspaceConversationMeta,
    WorkspaceConversationShare,
    WorkspaceFolder,
    WorkspaceNote,
)
from clara_api.db.session import get_db
from clara_api.schemas import (
    WorkspaceBulkConversationMetaUpdateRequest,
    WorkspaceBulkConversationMetaUpdateResponse,
    WorkspaceChannelCreateRequest,
    WorkspaceChannelResponse,
    WorkspaceChannelUpdateRequest,
    WorkspaceConversationListItem,
    WorkspaceConversationListResponse,
    WorkspaceConversationMetaResponse,
    WorkspaceConversationMetaUpdateRequest,
    WorkspaceConversationShareCreateRequest,
    WorkspaceConversationShareListItem,
    WorkspaceConversationShareResponse,
    WorkspaceConversationUpdateRequest,
    WorkspaceFolderCreateRequest,
    WorkspaceFolderResponse,
    WorkspaceFolderUpdateRequest,
    WorkspaceNoteCreateRequest,
    WorkspaceNoteResponse,
    WorkspaceNoteUpdateRequest,
    WorkspacePublicConversationMessageResponse,
    WorkspacePublicConversationResponse,
    WorkspaceSearchResponse,
    WorkspaceSuggestionResponse,
    WorkspaceSuggestionsResponse,
    WorkspaceSummaryResponse,
)

router = APIRouter()

USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))

_DEFAULT_SUGGESTIONS: tuple[str, ...] = (
    "Tương tác warfarin với NSAID",
    "So sánh DASH và Địa Trung Hải",
    "Checklist an toàn đa trị liệu",
    "Cảnh báo chống chỉ định trên bệnh thận",
    "Tóm tắt ADR nghiêm trọng cần đi viện",
)
settings = get_settings()


class WorkspaceDocxFromMarkdownRequest(BaseModel):
    markdown: str = Field(min_length=1, max_length=1_500_000)
    title: str | None = Field(default=None, max_length=200)


def _get_user_by_token(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại",
        )
    return user


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    base = base.strip("-")
    return base or "item"


def _ensure_unique_folder_slug(
    db: Session,
    *,
    user_id: int,
    slug: str,
    exclude_id: int | None,
) -> str:
    candidate = slug
    counter = 1
    while True:
        stmt = select(WorkspaceFolder).where(
            WorkspaceFolder.user_id == user_id,
            WorkspaceFolder.slug == candidate,
        )
        if exclude_id is not None:
            stmt = stmt.where(WorkspaceFolder.id != exclude_id)
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is None:
            return candidate
        counter += 1
        candidate = f"{slug}-{counter}"


def _ensure_unique_channel_slug(
    db: Session,
    *,
    user_id: int,
    slug: str,
    exclude_id: int | None,
) -> str:
    candidate = slug
    counter = 1
    while True:
        stmt = select(WorkspaceChannel).where(
            WorkspaceChannel.user_id == user_id,
            WorkspaceChannel.slug == candidate,
        )
        if exclude_id is not None:
            stmt = stmt.where(WorkspaceChannel.id != exclude_id)
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is None:
            return candidate
        counter += 1
        candidate = f"{slug}-{counter}"


def _folder_counts(db: Session, *, user_id: int) -> dict[int, int]:
    rows = db.execute(
        select(WorkspaceConversationMeta.folder_id, func.count(WorkspaceConversationMeta.id))
        .where(WorkspaceConversationMeta.user_id == user_id)
        .group_by(WorkspaceConversationMeta.folder_id)
    ).all()
    return {int(folder_id): int(total) for folder_id, total in rows if folder_id is not None}


def _channel_counts(db: Session, *, user_id: int) -> dict[int, int]:
    rows = db.execute(
        select(WorkspaceConversationMeta.channel_id, func.count(WorkspaceConversationMeta.id))
        .where(WorkspaceConversationMeta.user_id == user_id)
        .group_by(WorkspaceConversationMeta.channel_id)
    ).all()
    return {int(channel_id): int(total) for channel_id, total in rows if channel_id is not None}


def _serialize_folder(
    folder: WorkspaceFolder,
    *,
    conversation_count: int = 0,
) -> WorkspaceFolderResponse:
    return WorkspaceFolderResponse(
        id=folder.id,
        name=folder.name,
        slug=folder.slug,
        description=folder.description,
        color=folder.color,
        icon=folder.icon,
        sort_order=folder.sort_order,
        is_archived=folder.is_archived,
        conversation_count=conversation_count,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def _serialize_channel(
    channel: WorkspaceChannel,
    *,
    conversation_count: int = 0,
) -> WorkspaceChannelResponse:
    visibility = channel.visibility
    if visibility not in {"private", "team", "public"}:
        visibility = "private"
    return WorkspaceChannelResponse(
        id=channel.id,
        name=channel.name,
        slug=channel.slug,
        description=channel.description,
        visibility=visibility,  # type: ignore[arg-type]
        color=channel.color,
        icon=channel.icon,
        sort_order=channel.sort_order,
        is_archived=channel.is_archived,
        conversation_count=conversation_count,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


def _normalize_tags(raw_tags: Any) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    cleaned: list[str] = []
    for item in raw_tags:
        text = str(item).strip()
        if not text:
            continue
        cleaned.append(text[:64])
        if len(cleaned) >= 20:
            break
    return cleaned


def _note_summary(content_markdown: str) -> str:
    return re.sub(r"\s+", " ", (content_markdown or "").strip())[:180]


def _serialize_note(note: WorkspaceNote) -> WorkspaceNoteResponse:
    return WorkspaceNoteResponse(
        id=note.id,
        title=note.title,
        content_markdown=note.content_markdown,
        summary=note.summary,
        tags=_normalize_tags(note.tags_json),
        is_pinned=note.is_pinned,
        conversation_id=note.conversation_id,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _get_owned_folder(db: Session, *, user_id: int, folder_id: int) -> WorkspaceFolder:
    folder = db.execute(
        select(WorkspaceFolder).where(
            WorkspaceFolder.id == folder_id,
            WorkspaceFolder.user_id == user_id,
        )
    ).scalar_one_or_none()
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder không tồn tại")
    return folder


def _get_owned_channel(db: Session, *, user_id: int, channel_id: int) -> WorkspaceChannel:
    channel = db.execute(
        select(WorkspaceChannel).where(
            WorkspaceChannel.id == channel_id,
            WorkspaceChannel.user_id == user_id,
        )
    ).scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel không tồn tại")
    return channel


def _get_owned_conversation(db: Session, *, user_id: int, conversation_id: int) -> SessionModel:
    session_obj = db.execute(
        select(SessionModel).where(
            SessionModel.id == conversation_id,
            SessionModel.user_id == user_id,
        )
    ).scalar_one_or_none()
    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation không tồn tại",
        )
    return session_obj


def _get_owned_note(db: Session, *, user_id: int, note_id: int) -> WorkspaceNote:
    note = db.execute(
        select(WorkspaceNote).where(
            WorkspaceNote.id == note_id,
            WorkspaceNote.user_id == user_id,
        )
    ).scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note không tồn tại")
    return note


def _public_share_url(share_token: str) -> str:
    base = settings.auth_public_web_base_url.rstrip("/")
    return f"{base}/share/{share_token}"


def _generate_share_token(db: Session) -> str:
    for _ in range(8):
        candidate = secrets.token_urlsafe(24)
        exists = db.execute(
            select(WorkspaceConversationShare.id).where(
                WorkspaceConversationShare.share_token == candidate
            )
        ).scalar_one_or_none()
        if exists is None:
            return candidate
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Không thể tạo share token.",
    )


def _serialize_share(
    share: WorkspaceConversationShare,
    *,
    conversation_id: int,
) -> WorkspaceConversationShareResponse:
    return WorkspaceConversationShareResponse(
        conversation_id=conversation_id,
        share_token=share.share_token,
        public_url=_public_share_url(share.share_token),
        is_active=bool(share.is_active),
        expires_at=share.expires_at,
        created_at=share.created_at,
        updated_at=share.updated_at,
    )


def _mask_owner_label(email: str) -> str:
    raw = email.strip()
    if "@" not in raw:
        return "anonymous"
    name, domain = raw.split("@", 1)
    safe_name = name[:3] if len(name) >= 3 else name
    return f"{safe_name}***@{domain}"


def _extract_answer_text(raw_text: str) -> str:
    stripped = (raw_text or "").strip()
    if not stripped:
        return ""
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if not isinstance(parsed, dict):
        return stripped
    payload = parsed.get("result")
    data = payload if isinstance(payload, dict) else parsed
    for key in ("answer_markdown", "answer_md", "answer", "message", "summary"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return stripped


def _slug_file_name(value: str) -> str:
    slug = _slugify(value)
    return slug[:80] or "conversation"


def _build_conversation_export_markdown(
    *,
    conversation_id: int,
    title: str,
    rows: list[QueryModel],
) -> str:
    now_text = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# {title}",
        "",
        f"- Conversation ID: `{conversation_id}`",
        f"- Exported at: `{now_text}`",
        f"- Messages: `{len(rows)}`",
        "",
    ]
    for index, row in enumerate(rows, start=1):
        created = _as_utc_aware(row.created_at) or datetime.now(tz=UTC)
        lines.append(f"## Turn {index}")
        lines.append("")
        lines.append(f"**Time:** `{created.isoformat()}`")
        lines.append("")
        lines.append("### User")
        lines.append("")
        lines.append((row.user_input or "").strip() or "(empty)")
        lines.append("")
        lines.append("### Assistant")
        lines.append("")
        lines.append(_extract_answer_text(row.response_text))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _render_docx_document_xml(markdown_text: str) -> str:
    # Backward-compatible shim for test utilities that may still import this helper.
    return markdown_text


def _build_docx_bytes_from_markdown(markdown_text: str) -> bytes:
    return render_docx_bytes(markdown_text)


def _as_utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _build_workspace_conversation_items(
    db: Session,
    *,
    user_id: int,
    limit: int,
    query_text: str | None,
    folder_id: int | None,
    channel_id: int | None,
    favorites_only: bool,
) -> list[WorkspaceConversationListItem]:
    safe_limit = max(1, min(200, int(limit)))
    sessions = (
        db.execute(
            select(SessionModel)
            .where(SessionModel.user_id == user_id)
            .order_by(SessionModel.created_at.desc(), SessionModel.id.desc())
            .limit(max(safe_limit * 6, safe_limit))
        )
        .scalars()
        .all()
    )
    if not sessions:
        return []

    session_ids = [session_obj.id for session_obj in sessions]
    metas = (
        db.execute(
            select(WorkspaceConversationMeta).where(
                WorkspaceConversationMeta.user_id == user_id,
                WorkspaceConversationMeta.session_id.in_(session_ids),
            )
        )
        .scalars()
        .all()
    )
    meta_by_session = {meta.session_id: meta for meta in metas}

    query_rows = (
        db.execute(
            select(QueryModel)
            .where(QueryModel.session_id.in_(session_ids))
            .order_by(QueryModel.created_at.desc(), QueryModel.id.desc())
        )
        .scalars()
        .all()
    )
    latest_query_by_session: dict[int, QueryModel] = {}
    message_count_by_session: dict[int, int] = {}
    for row in query_rows:
        current_count = message_count_by_session.get(row.session_id, 0)
        message_count_by_session[row.session_id] = current_count + 1
        if row.session_id not in latest_query_by_session:
            latest_query_by_session[row.session_id] = row

    normalized_query = (query_text or "").strip().lower()
    items: list[WorkspaceConversationListItem] = []
    for session_obj in sessions:
        latest_query = latest_query_by_session.get(session_obj.id)
        if latest_query is None:
            continue

        meta = meta_by_session.get(session_obj.id)
        if folder_id is not None and (meta is None or meta.folder_id != folder_id):
            continue
        if channel_id is not None and (meta is None or meta.channel_id != channel_id):
            continue
        if favorites_only and not (meta and meta.is_favorite):
            continue

        title = (session_obj.title or latest_query.user_input or "").strip()[:255]
        preview = (latest_query.user_input or "").strip()
        if normalized_query:
            haystack = f"{title} {preview}".lower()
            if normalized_query not in haystack:
                continue

        created_at = session_obj.created_at or latest_query.created_at or datetime.now(tz=UTC)
        items.append(
            WorkspaceConversationListItem(
                conversation_id=session_obj.id,
                title=title or "Untitled conversation",
                preview=preview[:260],
                query_id=latest_query.id,
                message_count=message_count_by_session.get(session_obj.id, 0),
                created_at=created_at,
                last_message_at=latest_query.created_at,
                folder_id=meta.folder_id if meta else None,
                channel_id=meta.channel_id if meta else None,
                is_favorite=bool(meta.is_favorite) if meta else False,
            )
        )
        if len(items) >= safe_limit:
            break
    return items


def _build_workspace_conversation_item(
    db: Session,
    *,
    user_id: int,
    session_obj: SessionModel,
) -> WorkspaceConversationListItem | None:
    latest_query = db.execute(
        select(QueryModel)
        .where(QueryModel.session_id == session_obj.id)
        .order_by(QueryModel.created_at.desc(), QueryModel.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_query is None:
        return None

    message_count = int(
        db.execute(
            select(func.count(QueryModel.id)).where(QueryModel.session_id == session_obj.id)
        ).scalar()
        or 0
    )
    meta = db.execute(
        select(WorkspaceConversationMeta).where(
            WorkspaceConversationMeta.user_id == user_id,
            WorkspaceConversationMeta.session_id == session_obj.id,
        )
    ).scalar_one_or_none()

    title = (session_obj.title or latest_query.user_input or "").strip()[:255]
    preview = (latest_query.user_input or "").strip()[:260]
    created_at = session_obj.created_at or latest_query.created_at or datetime.now(tz=UTC)
    return WorkspaceConversationListItem(
        conversation_id=session_obj.id,
        title=title or "Untitled conversation",
        preview=preview,
        query_id=latest_query.id,
        message_count=message_count,
        created_at=created_at,
        last_message_at=latest_query.created_at,
        folder_id=meta.folder_id if meta else None,
        channel_id=meta.channel_id if meta else None,
        is_favorite=bool(meta.is_favorite) if meta else False,
    )


@router.get("/summary", response_model=WorkspaceSummaryResponse)
def get_workspace_summary(
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceSummaryResponse:
    user = _get_user_by_token(db, token)
    conversation_count = int(
        db.execute(
            select(func.count(SessionModel.id)).where(SessionModel.user_id == user.id)
        ).scalar()
        or 0
    )
    message_count = int(
        db.execute(
            select(func.count(QueryModel.id))
            .join(SessionModel, QueryModel.session_id == SessionModel.id)
            .where(SessionModel.user_id == user.id)
        ).scalar()
        or 0
    )
    note_count = int(
        db.execute(
            select(func.count(WorkspaceNote.id)).where(WorkspaceNote.user_id == user.id)
        ).scalar()
        or 0
    )
    pinned_note_count = int(
        db.execute(
            select(func.count(WorkspaceNote.id)).where(
                WorkspaceNote.user_id == user.id,
                WorkspaceNote.is_pinned.is_(True),
            )
        ).scalar()
        or 0
    )
    folder_count = int(
        db.execute(
            select(func.count(WorkspaceFolder.id)).where(WorkspaceFolder.user_id == user.id)
        ).scalar()
        or 0
    )
    channel_count = int(
        db.execute(
            select(func.count(WorkspaceChannel.id)).where(WorkspaceChannel.user_id == user.id)
        ).scalar()
        or 0
    )
    return WorkspaceSummaryResponse(
        conversations=conversation_count,
        messages=message_count,
        folders=folder_count,
        channels=channel_count,
        notes=note_count,
        pinned_notes=pinned_note_count,
    )


@router.get("/folders", response_model=list[WorkspaceFolderResponse])
def list_workspace_folders(
    include_archived: bool = False,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> list[WorkspaceFolderResponse]:
    user = _get_user_by_token(db, token)
    stmt = (
        select(WorkspaceFolder)
        .where(WorkspaceFolder.user_id == user.id)
        .order_by(
            WorkspaceFolder.sort_order.asc(),
            WorkspaceFolder.updated_at.desc(),
            WorkspaceFolder.id.desc(),
        )
    )
    if not include_archived:
        stmt = stmt.where(WorkspaceFolder.is_archived.is_(False))
    folders = db.execute(stmt).scalars().all()
    counts = _folder_counts(db, user_id=user.id)
    return [
        _serialize_folder(folder, conversation_count=counts.get(folder.id, 0))
        for folder in folders
    ]


@router.post("/folders", response_model=WorkspaceFolderResponse)
def create_workspace_folder(
    payload: WorkspaceFolderCreateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceFolderResponse:
    user = _get_user_by_token(db, token)
    slug = _ensure_unique_folder_slug(
        db,
        user_id=user.id,
        slug=_slugify(payload.name),
        exclude_id=None,
    )
    folder = WorkspaceFolder(
        user_id=user.id,
        name=payload.name.strip(),
        slug=slug,
        description=(payload.description or "").strip(),
        color=(payload.color or "cyan").strip()[:32],
        icon=(payload.icon or "folder").strip()[:64],
        sort_order=int(payload.sort_order),
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return _serialize_folder(folder, conversation_count=0)


@router.patch("/folders/{folder_id}", response_model=WorkspaceFolderResponse)
def update_workspace_folder(
    folder_id: int,
    payload: WorkspaceFolderUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceFolderResponse:
    user = _get_user_by_token(db, token)
    folder = _get_owned_folder(db, user_id=user.id, folder_id=folder_id)
    if payload.name is not None:
        folder.name = payload.name.strip()
        folder.slug = _ensure_unique_folder_slug(
            db,
            user_id=user.id,
            slug=_slugify(folder.name),
            exclude_id=folder.id,
        )
    if payload.description is not None:
        folder.description = payload.description.strip()
    if payload.color is not None:
        folder.color = payload.color.strip()[:32]
    if payload.icon is not None:
        folder.icon = payload.icon.strip()[:64]
    if payload.sort_order is not None:
        folder.sort_order = int(payload.sort_order)
    if payload.is_archived is not None:
        folder.is_archived = bool(payload.is_archived)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    counts = _folder_counts(db, user_id=user.id)
    return _serialize_folder(folder, conversation_count=counts.get(folder.id, 0))


@router.delete("/folders/{folder_id}")
def delete_workspace_folder(
    folder_id: int,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _get_user_by_token(db, token)
    folder = _get_owned_folder(db, user_id=user.id, folder_id=folder_id)
    db.execute(
        update(WorkspaceConversationMeta)
        .where(
            WorkspaceConversationMeta.user_id == user.id,
            WorkspaceConversationMeta.folder_id == folder.id,
        )
        .values(folder_id=None)
    )
    db.delete(folder)
    db.commit()
    return {"deleted": True}


@router.get("/channels", response_model=list[WorkspaceChannelResponse])
def list_workspace_channels(
    include_archived: bool = False,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> list[WorkspaceChannelResponse]:
    user = _get_user_by_token(db, token)
    stmt = (
        select(WorkspaceChannel)
        .where(WorkspaceChannel.user_id == user.id)
        .order_by(
            WorkspaceChannel.sort_order.asc(),
            WorkspaceChannel.updated_at.desc(),
            WorkspaceChannel.id.desc(),
        )
    )
    if not include_archived:
        stmt = stmt.where(WorkspaceChannel.is_archived.is_(False))
    channels = db.execute(stmt).scalars().all()
    counts = _channel_counts(db, user_id=user.id)
    return [
        _serialize_channel(channel, conversation_count=counts.get(channel.id, 0))
        for channel in channels
    ]


@router.post("/channels", response_model=WorkspaceChannelResponse)
def create_workspace_channel(
    payload: WorkspaceChannelCreateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceChannelResponse:
    user = _get_user_by_token(db, token)
    slug = _ensure_unique_channel_slug(
        db,
        user_id=user.id,
        slug=_slugify(payload.name),
        exclude_id=None,
    )
    channel = WorkspaceChannel(
        user_id=user.id,
        name=payload.name.strip(),
        slug=slug,
        description=(payload.description or "").strip(),
        visibility=payload.visibility,
        color=(payload.color or "violet").strip()[:32],
        icon=(payload.icon or "hash").strip()[:64],
        sort_order=int(payload.sort_order),
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return _serialize_channel(channel, conversation_count=0)


@router.patch("/channels/{channel_id}", response_model=WorkspaceChannelResponse)
def update_workspace_channel(
    channel_id: int,
    payload: WorkspaceChannelUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceChannelResponse:
    user = _get_user_by_token(db, token)
    channel = _get_owned_channel(db, user_id=user.id, channel_id=channel_id)
    if payload.name is not None:
        channel.name = payload.name.strip()
        channel.slug = _ensure_unique_channel_slug(
            db,
            user_id=user.id,
            slug=_slugify(channel.name),
            exclude_id=channel.id,
        )
    if payload.description is not None:
        channel.description = payload.description.strip()
    if payload.visibility is not None:
        channel.visibility = payload.visibility
    if payload.color is not None:
        channel.color = payload.color.strip()[:32]
    if payload.icon is not None:
        channel.icon = payload.icon.strip()[:64]
    if payload.sort_order is not None:
        channel.sort_order = int(payload.sort_order)
    if payload.is_archived is not None:
        channel.is_archived = bool(payload.is_archived)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    counts = _channel_counts(db, user_id=user.id)
    return _serialize_channel(channel, conversation_count=counts.get(channel.id, 0))


@router.delete("/channels/{channel_id}")
def delete_workspace_channel(
    channel_id: int,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _get_user_by_token(db, token)
    channel = _get_owned_channel(db, user_id=user.id, channel_id=channel_id)
    db.execute(
        update(WorkspaceConversationMeta)
        .where(
            WorkspaceConversationMeta.user_id == user.id,
            WorkspaceConversationMeta.channel_id == channel.id,
        )
        .values(channel_id=None)
    )
    db.delete(channel)
    db.commit()
    return {"deleted": True}


@router.get("/conversations", response_model=WorkspaceConversationListResponse)
def list_workspace_conversations(
    limit: int = 60,
    query: str | None = Query(default=None, min_length=1, max_length=512),
    folder_id: int | None = None,
    channel_id: int | None = None,
    favorites_only: bool = False,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceConversationListResponse:
    user = _get_user_by_token(db, token)
    items = _build_workspace_conversation_items(
        db,
        user_id=user.id,
        limit=limit,
        query_text=query,
        folder_id=folder_id,
        channel_id=channel_id,
        favorites_only=favorites_only,
    )
    return WorkspaceConversationListResponse(items=items)


@router.patch(
    "/conversations/{conversation_id}/meta",
    response_model=WorkspaceConversationMetaResponse,
)
def update_workspace_conversation_meta(
    conversation_id: int,
    payload: WorkspaceConversationMetaUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceConversationMetaResponse:
    user = _get_user_by_token(db, token)
    _get_owned_conversation(db, user_id=user.id, conversation_id=conversation_id)
    fields_set = payload.model_fields_set
    folder_id = payload.folder_id if "folder_id" in fields_set else None
    channel_id = payload.channel_id if "channel_id" in fields_set else None
    if "folder_id" in fields_set and folder_id is not None:
        _get_owned_folder(db, user_id=user.id, folder_id=folder_id)
    if "channel_id" in fields_set and channel_id is not None:
        _get_owned_channel(db, user_id=user.id, channel_id=channel_id)

    meta = db.execute(
        select(WorkspaceConversationMeta).where(
            WorkspaceConversationMeta.user_id == user.id,
            WorkspaceConversationMeta.session_id == conversation_id,
        )
    ).scalar_one_or_none()
    if meta is None:
        meta = WorkspaceConversationMeta(user_id=user.id, session_id=conversation_id)
        db.add(meta)
        db.flush()

    if "folder_id" in fields_set:
        meta.folder_id = folder_id
    if "channel_id" in fields_set:
        meta.channel_id = channel_id
    if payload.is_favorite is not None:
        meta.is_favorite = bool(payload.is_favorite)
    if payload.touched:
        meta.last_opened_at = datetime.now(tz=UTC)

    db.add(meta)
    db.commit()
    db.refresh(meta)
    return WorkspaceConversationMetaResponse(
        conversation_id=conversation_id,
        folder_id=meta.folder_id,
        channel_id=meta.channel_id,
        is_favorite=bool(meta.is_favorite),
        last_opened_at=meta.last_opened_at,
        updated_at=meta.updated_at,
    )


@router.patch(
    "/conversations/meta/bulk",
    response_model=WorkspaceBulkConversationMetaUpdateResponse,
)
def bulk_update_workspace_conversation_meta(
    payload: WorkspaceBulkConversationMetaUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceBulkConversationMetaUpdateResponse:
    user = _get_user_by_token(db, token)
    fields_set = payload.model_fields_set

    target_ids = sorted(
        {int(value) for value in payload.conversation_ids if isinstance(value, int) and value > 0}
    )[:200]
    if not target_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Danh sách conversation_ids không hợp lệ.",
        )

    if "folder_id" in fields_set and payload.folder_id is not None:
        _get_owned_folder(db, user_id=user.id, folder_id=payload.folder_id)
    if "channel_id" in fields_set and payload.channel_id is not None:
        _get_owned_channel(db, user_id=user.id, channel_id=payload.channel_id)

    owned_ids = db.execute(
        select(SessionModel.id).where(
            SessionModel.user_id == user.id,
            SessionModel.id.in_(target_ids),
        )
    ).scalars().all()
    owned_set = {int(value) for value in owned_ids}
    if not owned_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy conversation hợp lệ.",
        )

    metas = (
        db.execute(
            select(WorkspaceConversationMeta).where(
                WorkspaceConversationMeta.user_id == user.id,
                WorkspaceConversationMeta.session_id.in_(owned_set),
            )
        )
        .scalars()
        .all()
    )
    meta_by_session = {meta.session_id: meta for meta in metas}
    updated_ids: list[int] = []
    touched_at = datetime.now(tz=UTC)
    for conversation_id in sorted(owned_set):
        meta = meta_by_session.get(conversation_id)
        if meta is None:
            meta = WorkspaceConversationMeta(user_id=user.id, session_id=conversation_id)
            db.add(meta)
            db.flush()
        if "folder_id" in fields_set:
            meta.folder_id = payload.folder_id
        if "channel_id" in fields_set:
            meta.channel_id = payload.channel_id
        if payload.is_favorite is not None:
            meta.is_favorite = bool(payload.is_favorite)
        if payload.touched:
            meta.last_opened_at = touched_at
        db.add(meta)
        updated_ids.append(conversation_id)

    db.commit()
    return WorkspaceBulkConversationMetaUpdateResponse(
        updated_count=len(updated_ids),
        updated_ids=updated_ids,
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=WorkspaceConversationListItem,
)
def update_workspace_conversation(
    conversation_id: int,
    payload: WorkspaceConversationUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceConversationListItem:
    user = _get_user_by_token(db, token)
    session_obj = _get_owned_conversation(db, user_id=user.id, conversation_id=conversation_id)
    session_obj.title = payload.title.strip()[:255]
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    item = _build_workspace_conversation_item(db, user_id=user.id, session_obj=session_obj)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation không còn dữ liệu tin nhắn.",
        )
    return item


@router.delete("/conversations/{conversation_id}")
def delete_workspace_conversation(
    conversation_id: int,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _get_user_by_token(db, token)
    session_obj = _get_owned_conversation(db, user_id=user.id, conversation_id=conversation_id)

    db.execute(
        update(WorkspaceNote)
        .where(
            WorkspaceNote.user_id == user.id,
            WorkspaceNote.conversation_id == conversation_id,
        )
        .values(conversation_id=None)
    )
    db.execute(
        update(WorkspaceConversationShare)
        .where(
            WorkspaceConversationShare.user_id == user.id,
            WorkspaceConversationShare.session_id == conversation_id,
        )
        .values(is_active=False)
    )
    db.delete(session_obj)
    db.commit()
    return {"deleted": True}


@router.post(
    "/conversations/{conversation_id}/share",
    response_model=WorkspaceConversationShareResponse,
)
def create_or_rotate_conversation_share(
    conversation_id: int,
    payload: WorkspaceConversationShareCreateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceConversationShareResponse:
    user = _get_user_by_token(db, token)
    _get_owned_conversation(db, user_id=user.id, conversation_id=conversation_id)

    share = db.execute(
        select(WorkspaceConversationShare).where(
            WorkspaceConversationShare.user_id == user.id,
            WorkspaceConversationShare.session_id == conversation_id,
        )
    ).scalar_one_or_none()

    should_rotate = bool(payload.rotate) or share is None
    if share is None:
        share = WorkspaceConversationShare(
            user_id=user.id,
            session_id=conversation_id,
            share_token=_generate_share_token(db),
            is_active=True,
        )
    else:
        share.is_active = True
        if should_rotate:
            share.share_token = _generate_share_token(db)

    if payload.expires_in_hours is not None:
        share.expires_at = datetime.now(tz=UTC) + timedelta(hours=int(payload.expires_in_hours))

    db.add(share)
    db.commit()
    db.refresh(share)
    return _serialize_share(share, conversation_id=conversation_id)


@router.get(
    "/conversations/{conversation_id}/share",
    response_model=WorkspaceConversationShareResponse,
)
def get_conversation_share(
    conversation_id: int,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceConversationShareResponse:
    user = _get_user_by_token(db, token)
    _get_owned_conversation(db, user_id=user.id, conversation_id=conversation_id)

    share = db.execute(
        select(WorkspaceConversationShare).where(
            WorkspaceConversationShare.user_id == user.id,
            WorkspaceConversationShare.session_id == conversation_id,
        )
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation chưa được chia sẻ.",
        )
    return _serialize_share(share, conversation_id=conversation_id)


@router.delete("/conversations/{conversation_id}/share")
def revoke_conversation_share(
    conversation_id: int,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _get_user_by_token(db, token)
    _get_owned_conversation(db, user_id=user.id, conversation_id=conversation_id)

    share = db.execute(
        select(WorkspaceConversationShare).where(
            WorkspaceConversationShare.user_id == user.id,
            WorkspaceConversationShare.session_id == conversation_id,
        )
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation chưa được chia sẻ.",
        )

    share.is_active = False
    db.add(share)
    db.commit()
    return {"revoked": True}


@router.get("/shares", response_model=list[WorkspaceConversationShareListItem])
def list_workspace_shares(
    limit: int = 60,
    active_only: bool = True,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> list[WorkspaceConversationShareListItem]:
    user = _get_user_by_token(db, token)
    safe_limit = max(1, min(200, int(limit)))
    stmt = (
        select(WorkspaceConversationShare)
        .where(WorkspaceConversationShare.user_id == user.id)
        .order_by(
            WorkspaceConversationShare.updated_at.desc(),
            WorkspaceConversationShare.id.desc(),
        )
        .limit(safe_limit)
    )
    if active_only:
        stmt = stmt.where(WorkspaceConversationShare.is_active.is_(True))
    shares = db.execute(stmt).scalars().all()
    if not shares:
        return []

    session_ids = [share.session_id for share in shares]
    sessions = (
        db.execute(
            select(SessionModel).where(
                SessionModel.user_id == user.id,
                SessionModel.id.in_(session_ids),
            )
        )
        .scalars()
        .all()
    )
    session_by_id = {session_obj.id: session_obj for session_obj in sessions}
    message_counts = dict(
        db.execute(
            select(QueryModel.session_id, func.count(QueryModel.id))
            .where(QueryModel.session_id.in_(session_ids))
            .group_by(QueryModel.session_id)
        ).all()
    )
    last_message_map = dict(
        db.execute(
            select(QueryModel.session_id, func.max(QueryModel.created_at))
            .where(QueryModel.session_id.in_(session_ids))
            .group_by(QueryModel.session_id)
        ).all()
    )

    payload: list[WorkspaceConversationShareListItem] = []
    for share in shares:
        session_obj = session_by_id.get(share.session_id)
        if session_obj is None:
            continue
        title = (session_obj.title or "").strip() or f"Conversation #{session_obj.id}"
        payload.append(
            WorkspaceConversationShareListItem(
                conversation_id=session_obj.id,
                conversation_title=title,
                message_count=int(message_counts.get(session_obj.id, 0) or 0),
                last_message_at=last_message_map.get(session_obj.id),
                share_token=share.share_token,
                public_url=_public_share_url(share.share_token),
                is_active=bool(share.is_active),
                expires_at=share.expires_at,
                created_at=share.created_at,
                updated_at=share.updated_at,
            )
        )
    return payload


@router.get(
    "/conversations/{conversation_id}/export",
    responses={
        200: {
            "content": {
                "text/markdown": {},
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {},
            }
        }
    },
)
def export_workspace_conversation(
    conversation_id: int,
    format: str = Query(default="markdown", pattern="^(markdown|docx)$"),
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> Response:
    user = _get_user_by_token(db, token)
    session_obj = _get_owned_conversation(db, user_id=user.id, conversation_id=conversation_id)
    rows = (
        db.execute(
            select(QueryModel)
            .where(QueryModel.session_id == conversation_id)
            .order_by(QueryModel.created_at.asc(), QueryModel.id.asc())
        )
        .scalars()
        .all()
    )
    title = (session_obj.title or "").strip() or f"Conversation {conversation_id}"
    markdown_text = _build_conversation_export_markdown(
        conversation_id=conversation_id,
        title=title,
        rows=rows,
    )
    safe_name = _slug_file_name(title)
    selected_format = format.strip().lower()

    if selected_format == "docx":
        payload = _build_docx_bytes_from_markdown(markdown_text)
        filename = f"{safe_name}.docx"
        return Response(
            content=payload,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    filename = f"{safe_name}.md"
    return Response(
        content=markdown_text.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/export/docx",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {},
            }
        }
    },
)
def export_docx_from_markdown(
    payload: WorkspaceDocxFromMarkdownRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> Response:
    _get_user_by_token(db, token)
    markdown_text = (payload.markdown or "").strip()
    if not markdown_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Markdown rỗng, không thể xuất DOCX.",
        )

    title = (payload.title or "").strip() or "research-export"
    safe_name = _slug_file_name(title)
    docx_bytes = _build_docx_bytes_from_markdown(markdown_text)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.docx"},
    )


@router.get(
    "/public/conversations/{share_token}",
    response_model=WorkspacePublicConversationResponse,
)
def get_public_conversation_by_share_token(
    share_token: str,
    db: Session = Depends(get_db),
) -> WorkspacePublicConversationResponse:
    share = db.execute(
        select(WorkspaceConversationShare).where(
            WorkspaceConversationShare.share_token == share_token,
            WorkspaceConversationShare.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Liên kết chia sẻ không tồn tại.",
        )

    now = datetime.now(tz=UTC)
    expires_at = _as_utc_aware(share.expires_at)
    if expires_at is not None and expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Liên kết chia sẻ đã hết hạn.",
        )

    session_obj = db.execute(
        select(SessionModel).where(
            SessionModel.id == share.session_id,
            SessionModel.user_id == share.user_id,
        )
    ).scalar_one_or_none()
    owner = db.execute(select(User).where(User.id == share.user_id)).scalar_one_or_none()
    if session_obj is None or owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation không tồn tại.",
        )

    rows = (
        db.execute(
            select(QueryModel)
            .where(QueryModel.session_id == session_obj.id)
            .order_by(QueryModel.created_at.asc(), QueryModel.id.asc())
        )
        .scalars()
        .all()
    )

    messages = [
        WorkspacePublicConversationMessageResponse(
            query_id=row.id,
            role=row.role,
            query=row.user_input,
            answer=_extract_answer_text(row.response_text),
            created_at=row.created_at or now,
        )
        for row in rows
    ]
    return WorkspacePublicConversationResponse(
        conversation_id=session_obj.id,
        title=(session_obj.title or "").strip() or f"Conversation #{session_obj.id}",
        owner_label=_mask_owner_label(owner.email),
        expires_at=expires_at,
        messages=messages,
    )


@router.get("/notes", response_model=list[WorkspaceNoteResponse])
def list_workspace_notes(
    limit: int = 80,
    query: str | None = Query(default=None, min_length=1, max_length=512),
    conversation_id: int | None = None,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> list[WorkspaceNoteResponse]:
    user = _get_user_by_token(db, token)
    stmt = (
        select(WorkspaceNote)
        .where(WorkspaceNote.user_id == user.id)
        .order_by(
            WorkspaceNote.is_pinned.desc(),
            WorkspaceNote.updated_at.desc(),
            WorkspaceNote.id.desc(),
        )
        .limit(max(1, min(200, int(limit))))
    )
    if conversation_id is not None:
        stmt = stmt.where(WorkspaceNote.conversation_id == conversation_id)
    if query:
        like_pattern = f"%{query.strip()}%"
        stmt = stmt.where(
            WorkspaceNote.title.ilike(like_pattern)
            | WorkspaceNote.content_markdown.ilike(like_pattern)
        )
    notes = db.execute(stmt).scalars().all()
    return [_serialize_note(note) for note in notes]


@router.post("/notes", response_model=WorkspaceNoteResponse)
def create_workspace_note(
    payload: WorkspaceNoteCreateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceNoteResponse:
    user = _get_user_by_token(db, token)
    if payload.conversation_id is not None:
        _get_owned_conversation(db, user_id=user.id, conversation_id=payload.conversation_id)

    content_markdown = payload.content_markdown or ""
    note = WorkspaceNote(
        user_id=user.id,
        title=payload.title.strip(),
        content_markdown=content_markdown,
        summary=_note_summary(content_markdown),
        tags_json=_normalize_tags(payload.tags),
        is_pinned=bool(payload.is_pinned),
        conversation_id=payload.conversation_id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _serialize_note(note)


@router.patch("/notes/{note_id}", response_model=WorkspaceNoteResponse)
def update_workspace_note(
    note_id: int,
    payload: WorkspaceNoteUpdateRequest,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceNoteResponse:
    user = _get_user_by_token(db, token)
    note = _get_owned_note(db, user_id=user.id, note_id=note_id)

    if payload.conversation_id is not None:
        _get_owned_conversation(db, user_id=user.id, conversation_id=payload.conversation_id)
        note.conversation_id = payload.conversation_id
    if payload.title is not None:
        note.title = payload.title.strip()
    if payload.content_markdown is not None:
        note.content_markdown = payload.content_markdown
        note.summary = _note_summary(payload.content_markdown)
    if payload.tags is not None:
        note.tags_json = _normalize_tags(payload.tags)
    if payload.is_pinned is not None:
        note.is_pinned = bool(payload.is_pinned)

    db.add(note)
    db.commit()
    db.refresh(note)
    return _serialize_note(note)


@router.delete("/notes/{note_id}")
def delete_workspace_note(
    note_id: int,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _get_user_by_token(db, token)
    note = _get_owned_note(db, user_id=user.id, note_id=note_id)
    db.delete(note)
    db.commit()
    return {"deleted": True}


@router.get("/suggestions", response_model=WorkspaceSuggestionsResponse)
def list_workspace_suggestions(
    limit: int = 10,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceSuggestionsResponse:
    user = _get_user_by_token(db, token)
    safe_limit = max(1, min(20, int(limit)))
    items: list[WorkspaceSuggestionResponse] = []

    rows = db.execute(
        select(QueryModel.user_input, func.count(QueryModel.id).label("freq"))
        .join(SessionModel, QueryModel.session_id == SessionModel.id)
        .where(SessionModel.user_id == user.id)
        .group_by(QueryModel.user_input)
        .order_by(func.count(QueryModel.id).desc(), func.max(QueryModel.created_at).desc())
        .limit(safe_limit * 2)
    ).all()

    seen: set[str] = set()
    for index, row in enumerate(rows):
        text = str(row[0] or "").strip()
        if len(text) < 8:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        score = float(row[1] or 1)
        items.append(
            WorkspaceSuggestionResponse(
                id=f"history-{index}",
                text=text[:180],
                category="history",
                score=min(1.0, 0.3 + score / 10.0),
            )
        )
        if len(items) >= safe_limit:
            return WorkspaceSuggestionsResponse(items=items)

    for index, text in enumerate(_DEFAULT_SUGGESTIONS):
        lowered = text.lower()
        if lowered in seen:
            continue
        items.append(
            WorkspaceSuggestionResponse(
                id=f"default-{index}",
                text=text,
                category="starter",
                score=0.45,
            )
        )
        if len(items) >= safe_limit:
            break

    return WorkspaceSuggestionsResponse(items=items)


@router.get("/search", response_model=WorkspaceSearchResponse)
def search_workspace(
    q: str = Query(min_length=1, max_length=512),
    limit: int = 12,
    token: TokenPayload = USER_ROLE_DEP,
    db: Session = Depends(get_db),
) -> WorkspaceSearchResponse:
    user = _get_user_by_token(db, token)
    safe_limit = max(1, min(50, int(limit)))
    query_text = q.strip()

    conversations = _build_workspace_conversation_items(
        db,
        user_id=user.id,
        limit=safe_limit,
        query_text=query_text,
        folder_id=None,
        channel_id=None,
        favorites_only=False,
    )

    notes = db.execute(
        select(WorkspaceNote)
        .where(
            WorkspaceNote.user_id == user.id,
            WorkspaceNote.title.ilike(f"%{query_text}%")
            | WorkspaceNote.content_markdown.ilike(f"%{query_text}%"),
        )
        .order_by(
            WorkspaceNote.is_pinned.desc(),
            WorkspaceNote.updated_at.desc(),
            WorkspaceNote.id.desc(),
        )
        .limit(safe_limit)
    ).scalars().all()

    folder_counts = _folder_counts(db, user_id=user.id)
    folders = db.execute(
        select(WorkspaceFolder)
        .where(
            WorkspaceFolder.user_id == user.id,
            WorkspaceFolder.name.ilike(f"%{query_text}%"),
        )
        .order_by(WorkspaceFolder.updated_at.desc(), WorkspaceFolder.id.desc())
        .limit(safe_limit)
    ).scalars().all()

    channel_counts = _channel_counts(db, user_id=user.id)
    channels = db.execute(
        select(WorkspaceChannel)
        .where(
            WorkspaceChannel.user_id == user.id,
            WorkspaceChannel.name.ilike(f"%{query_text}%"),
        )
        .order_by(WorkspaceChannel.updated_at.desc(), WorkspaceChannel.id.desc())
        .limit(safe_limit)
    ).scalars().all()

    suggestions = list_workspace_suggestions(limit=min(8, safe_limit), token=token, db=db).items
    filtered_suggestions = [item for item in suggestions if query_text.lower() in item.text.lower()]
    filtered_suggestions = filtered_suggestions[: min(8, safe_limit)]

    return WorkspaceSearchResponse(
        query=query_text,
        conversations=conversations,
        notes=[_serialize_note(note) for note in notes],
        folders=[
            _serialize_folder(folder, conversation_count=folder_counts.get(folder.id, 0))
            for folder in folders
        ],
        channels=[
            _serialize_channel(channel, conversation_count=channel_counts.get(channel.id, 0))
            for channel in channels
        ],
        suggestions=filtered_suggestions,
    )
