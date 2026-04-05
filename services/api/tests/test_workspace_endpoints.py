import io
import json
import zipfile

from fastapi.testclient import TestClient

from clara_api.db.models import Query as QueryModel
from clara_api.db.models import SessionModel, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_conversation(
    email: str,
    query_text: str,
    *,
    title: str = "",
    response_text: str = "ok",
) -> int:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        session_obj = SessionModel(user_id=user.id, title=title or "Workspace conversation")
        db.add(session_obj)
        db.flush()
        db.add(
            QueryModel(
                session_id=session_obj.id,
                role="normal",
                user_input=query_text,
                response_text=response_text,
            )
        )
        db.commit()
        return int(session_obj.id)


def test_workspace_folder_and_channel_crud_basic() -> None:
    token = _login("workspace-crud@example.com")
    headers = _auth_headers(token)

    create_folder_response = client.post(
        "/api/v1/workspace/folders",
        headers=headers,
        json={
            "name": "Clinical Cases",
            "description": "Folder for case threads",
            "color": "cyan",
            "icon": "folder",
            "sort_order": 1,
        },
    )
    assert create_folder_response.status_code == 200
    folder = create_folder_response.json()
    folder_id = folder["id"]
    assert folder["name"] == "Clinical Cases"
    assert folder["slug"] == "clinical-cases"
    assert folder["conversation_count"] == 0

    folders_response = client.get("/api/v1/workspace/folders", headers=headers)
    assert folders_response.status_code == 200
    assert any(item["id"] == folder_id for item in folders_response.json())

    update_folder_response = client.patch(
        f"/api/v1/workspace/folders/{folder_id}",
        headers=headers,
        json={"name": "Archived Cases", "is_archived": True},
    )
    assert update_folder_response.status_code == 200
    updated_folder = update_folder_response.json()
    assert updated_folder["slug"] == "archived-cases"
    assert updated_folder["is_archived"] is True

    active_folders_response = client.get("/api/v1/workspace/folders", headers=headers)
    assert active_folders_response.status_code == 200
    assert all(item["id"] != folder_id for item in active_folders_response.json())

    all_folders_response = client.get(
        "/api/v1/workspace/folders?include_archived=true",
        headers=headers,
    )
    assert all_folders_response.status_code == 200
    assert any(item["id"] == folder_id for item in all_folders_response.json())

    delete_folder_response = client.delete(
        f"/api/v1/workspace/folders/{folder_id}",
        headers=headers,
    )
    assert delete_folder_response.status_code == 200
    assert delete_folder_response.json() == {"deleted": True}

    create_channel_response = client.post(
        "/api/v1/workspace/channels",
        headers=headers,
        json={
            "name": "Care Team",
            "description": "Shared updates",
            "visibility": "team",
            "color": "teal",
            "icon": "hash",
            "sort_order": 2,
        },
    )
    assert create_channel_response.status_code == 200
    channel = create_channel_response.json()
    channel_id = channel["id"]
    assert channel["name"] == "Care Team"
    assert channel["slug"] == "care-team"
    assert channel["visibility"] == "team"

    channels_response = client.get("/api/v1/workspace/channels", headers=headers)
    assert channels_response.status_code == 200
    assert any(item["id"] == channel_id for item in channels_response.json())

    update_channel_response = client.patch(
        f"/api/v1/workspace/channels/{channel_id}",
        headers=headers,
        json={"visibility": "public", "is_archived": True},
    )
    assert update_channel_response.status_code == 200
    updated_channel = update_channel_response.json()
    assert updated_channel["visibility"] == "public"
    assert updated_channel["is_archived"] is True

    active_channels_response = client.get("/api/v1/workspace/channels", headers=headers)
    assert active_channels_response.status_code == 200
    assert all(item["id"] != channel_id for item in active_channels_response.json())

    all_channels_response = client.get(
        "/api/v1/workspace/channels?include_archived=true",
        headers=headers,
    )
    assert all_channels_response.status_code == 200
    assert any(item["id"] == channel_id for item in all_channels_response.json())

    delete_channel_response = client.delete(
        f"/api/v1/workspace/channels/{channel_id}",
        headers=headers,
    )
    assert delete_channel_response.status_code == 200
    assert delete_channel_response.json() == {"deleted": True}


def test_workspace_conversation_meta_update_and_ownership_guard() -> None:
    owner_email = "workspace-owner@example.com"
    other_email = "workspace-outsider@example.com"

    owner_headers = _auth_headers(_login(owner_email))
    other_headers = _auth_headers(_login(other_email))

    folder_response = client.post(
        "/api/v1/workspace/folders",
        headers=owner_headers,
        json={
            "name": "Owner Folder",
            "description": "",
            "color": "blue",
            "icon": "folder",
            "sort_order": 0,
        },
    )
    assert folder_response.status_code == 200
    owner_folder_id = folder_response.json()["id"]

    channel_response = client.post(
        "/api/v1/workspace/channels",
        headers=owner_headers,
        json={
            "name": "Owner Channel",
            "description": "",
            "visibility": "private",
            "color": "indigo",
            "icon": "hash",
            "sort_order": 0,
        },
    )
    assert channel_response.status_code == 200
    owner_channel_id = channel_response.json()["id"]

    owner_conversation_id = _create_conversation(
        owner_email,
        "Warfarin NSAID risk management checklist",
    )
    update_meta_response = client.patch(
        f"/api/v1/workspace/conversations/{owner_conversation_id}/meta",
        headers=owner_headers,
        json={
            "folder_id": owner_folder_id,
            "channel_id": owner_channel_id,
            "is_favorite": True,
            "touched": True,
        },
    )
    assert update_meta_response.status_code == 200
    meta_payload = update_meta_response.json()
    assert meta_payload["conversation_id"] == owner_conversation_id
    assert meta_payload["folder_id"] == owner_folder_id
    assert meta_payload["channel_id"] == owner_channel_id
    assert meta_payload["is_favorite"] is True
    assert meta_payload["last_opened_at"] is not None

    owner_favorites_response = client.get(
        "/api/v1/workspace/conversations?favorites_only=true",
        headers=owner_headers,
    )
    assert owner_favorites_response.status_code == 200
    favorites = owner_favorites_response.json()["items"]
    assert len(favorites) == 1
    assert favorites[0]["conversation_id"] == owner_conversation_id
    assert favorites[0]["folder_id"] == owner_folder_id
    assert favorites[0]["channel_id"] == owner_channel_id
    assert favorites[0]["is_favorite"] is True

    patch_other_conversation = client.patch(
        f"/api/v1/workspace/conversations/{owner_conversation_id}/meta",
        headers=other_headers,
        json={"is_favorite": True},
    )
    assert patch_other_conversation.status_code == 404

    other_conversation_id = _create_conversation(other_email, "General outpatient follow-up")
    use_foreign_folder_or_channel = client.patch(
        f"/api/v1/workspace/conversations/{other_conversation_id}/meta",
        headers=other_headers,
        json={
            "folder_id": owner_folder_id,
            "channel_id": owner_channel_id,
            "is_favorite": True,
        },
    )
    assert use_foreign_folder_or_channel.status_code == 404


def test_workspace_notes_crud_with_conversation_binding() -> None:
    email = "workspace-notes@example.com"
    headers = _auth_headers(_login(email))
    conversation_id = _create_conversation(email, "Conversation A for note binding")
    target_conversation_id = _create_conversation(email, "Conversation B for note binding")

    create_note_response = client.post(
        "/api/v1/workspace/notes",
        headers=headers,
        json={
            "title": "Warfarin follow-up",
            "content_markdown": "Track INR weekly and monitor bleeding signs.",
            "tags": ["warfarin", "inr"],
            "is_pinned": True,
            "conversation_id": conversation_id,
        },
    )
    assert create_note_response.status_code == 200
    note_payload = create_note_response.json()
    note_id = note_payload["id"]
    assert note_payload["conversation_id"] == conversation_id
    assert note_payload["is_pinned"] is True
    assert note_payload["tags"] == ["warfarin", "inr"]
    assert "Track INR weekly" in note_payload["summary"]

    list_notes_response = client.get(
        f"/api/v1/workspace/notes?conversation_id={conversation_id}",
        headers=headers,
    )
    assert list_notes_response.status_code == 200
    notes_for_conversation = list_notes_response.json()
    assert len(notes_for_conversation) == 1
    assert notes_for_conversation[0]["id"] == note_id

    update_note_response = client.patch(
        f"/api/v1/workspace/notes/{note_id}",
        headers=headers,
        json={
            "title": "Warfarin follow-up updated",
            "content_markdown": "Updated: monitor INR every 3-7 days after dose change.",
            "tags": ["updated"],
            "is_pinned": False,
            "conversation_id": target_conversation_id,
        },
    )
    assert update_note_response.status_code == 200
    updated_note = update_note_response.json()
    assert updated_note["title"] == "Warfarin follow-up updated"
    assert updated_note["conversation_id"] == target_conversation_id
    assert updated_note["is_pinned"] is False
    assert updated_note["tags"] == ["updated"]
    assert "Updated: monitor INR" in updated_note["summary"]

    delete_note_response = client.delete(f"/api/v1/workspace/notes/{note_id}", headers=headers)
    assert delete_note_response.status_code == 200
    assert delete_note_response.json() == {"deleted": True}

    list_after_delete_response = client.get(
        f"/api/v1/workspace/notes?conversation_id={target_conversation_id}",
        headers=headers,
    )
    assert list_after_delete_response.status_code == 200
    assert all(item["id"] != note_id for item in list_after_delete_response.json())


def test_workspace_suggestions_and_search_return_valid_structure() -> None:
    email = "workspace-search@example.com"
    headers = _auth_headers(_login(email))

    folder_response = client.post(
        "/api/v1/workspace/folders",
        headers=headers,
        json={
            "name": "Warfarin Cases",
            "description": "",
            "color": "cyan",
            "icon": "folder",
            "sort_order": 0,
        },
    )
    assert folder_response.status_code == 200
    folder_id = folder_response.json()["id"]

    channel_response = client.post(
        "/api/v1/workspace/channels",
        headers=headers,
        json={
            "name": "warfarin-team",
            "description": "",
            "visibility": "private",
            "color": "violet",
            "icon": "hash",
            "sort_order": 0,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["id"]

    conversation_id = _create_conversation(
        email,
        "Warfarin and ibuprofen interaction alert in CKD patients",
        title="Warfarin interaction review",
    )
    meta_response = client.patch(
        f"/api/v1/workspace/conversations/{conversation_id}/meta",
        headers=headers,
        json={
            "folder_id": folder_id,
            "channel_id": channel_id,
            "is_favorite": True,
            "touched": True,
        },
    )
    assert meta_response.status_code == 200

    note_response = client.post(
        "/api/v1/workspace/notes",
        headers=headers,
        json={
            "title": "Warfarin note",
            "content_markdown": "Quick note on warfarin dose adjustment.",
            "tags": ["warfarin"],
            "is_pinned": False,
            "conversation_id": conversation_id,
        },
    )
    assert note_response.status_code == 200
    note_id = note_response.json()["id"]

    suggestions_response = client.get("/api/v1/workspace/suggestions?limit=5", headers=headers)
    assert suggestions_response.status_code == 200
    suggestions_payload = suggestions_response.json()
    assert isinstance(suggestions_payload["items"], list)
    assert 1 <= len(suggestions_payload["items"]) <= 5
    for item in suggestions_payload["items"]:
        assert {"id", "text", "category", "score"}.issubset(item.keys())
        assert isinstance(item["id"], str)
        assert isinstance(item["text"], str)
        assert isinstance(item["category"], str)
        assert isinstance(item["score"], (int, float))

    search_response = client.get("/api/v1/workspace/search?q=warfarin&limit=10", headers=headers)
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert search_payload["query"] == "warfarin"
    for key in ("conversations", "notes", "folders", "channels", "suggestions"):
        assert isinstance(search_payload[key], list)

    assert any(
        item["conversation_id"] == conversation_id
        for item in search_payload["conversations"]
    )
    assert any(item["id"] == note_id for item in search_payload["notes"])
    assert any(item["id"] == folder_id for item in search_payload["folders"])
    assert any(item["id"] == channel_id for item in search_payload["channels"])
    assert all("warfarin" in item["text"].lower() for item in search_payload["suggestions"])


def test_workspace_summary_counts_are_non_negative() -> None:
    email = "workspace-summary@example.com"
    headers = _auth_headers(_login(email))
    conversation_id = _create_conversation(email, "Summary baseline conversation")

    create_folder_response = client.post(
        "/api/v1/workspace/folders",
        headers=headers,
        json={
            "name": "Summary Folder",
            "description": "",
            "color": "cyan",
            "icon": "folder",
            "sort_order": 0,
        },
    )
    assert create_folder_response.status_code == 200
    folder_id = create_folder_response.json()["id"]

    create_channel_response = client.post(
        "/api/v1/workspace/channels",
        headers=headers,
        json={
            "name": "Summary Channel",
            "description": "",
            "visibility": "private",
            "color": "violet",
            "icon": "hash",
            "sort_order": 0,
        },
    )
    assert create_channel_response.status_code == 200
    channel_id = create_channel_response.json()["id"]

    set_meta_response = client.patch(
        f"/api/v1/workspace/conversations/{conversation_id}/meta",
        headers=headers,
        json={
            "folder_id": folder_id,
            "channel_id": channel_id,
            "is_favorite": True,
            "touched": True,
        },
    )
    assert set_meta_response.status_code == 200

    create_note_response = client.post(
        "/api/v1/workspace/notes",
        headers=headers,
        json={
            "title": "Summary Note",
            "content_markdown": "Pinned note for summary count",
            "tags": ["summary"],
            "is_pinned": True,
            "conversation_id": conversation_id,
        },
    )
    assert create_note_response.status_code == 200

    summary_response = client.get("/api/v1/workspace/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()

    for key in ("conversations", "messages", "folders", "channels", "notes", "pinned_notes"):
        assert isinstance(summary[key], int)
        assert summary[key] >= 0

    assert summary["conversations"] >= 1
    assert summary["messages"] >= 1
    assert summary["folders"] >= 1
    assert summary["channels"] >= 1
    assert summary["notes"] >= 1
    assert summary["pinned_notes"] >= 0


def test_workspace_conversation_share_public_access_and_revoke() -> None:
    email = "workspace-share-owner@example.com"
    owner_headers = _auth_headers(_login(email))
    conversation_id = _create_conversation(
        email,
        "Warfarin with ibuprofen increases bleeding risk",
        title="Warfarin safety review",
    )

    create_share_response = client.post(
        f"/api/v1/workspace/conversations/{conversation_id}/share",
        headers=owner_headers,
        json={"expires_in_hours": 24},
    )
    assert create_share_response.status_code == 200
    share_payload = create_share_response.json()
    share_token = share_payload["share_token"]
    assert share_payload["conversation_id"] == conversation_id
    assert share_payload["is_active"] is True
    assert "/share/" in share_payload["public_url"]
    assert share_payload["expires_at"] is not None

    get_share_response = client.get(
        f"/api/v1/workspace/conversations/{conversation_id}/share",
        headers=owner_headers,
    )
    assert get_share_response.status_code == 200
    assert get_share_response.json()["share_token"] == share_token

    public_response = client.get(f"/api/v1/workspace/public/conversations/{share_token}")
    assert public_response.status_code == 200
    public_payload = public_response.json()
    assert public_payload["conversation_id"] == conversation_id
    assert isinstance(public_payload["messages"], list)
    assert len(public_payload["messages"]) >= 1
    assert "owner_label" in public_payload

    revoke_response = client.delete(
        f"/api/v1/workspace/conversations/{conversation_id}/share",
        headers=owner_headers,
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json() == {"revoked": True}

    public_after_revoke_response = client.get(
        f"/api/v1/workspace/public/conversations/{share_token}"
    )
    assert public_after_revoke_response.status_code == 404


def test_workspace_conversation_share_requires_owner() -> None:
    owner_email = "workspace-share-owner2@example.com"
    outsider_email = "workspace-share-outsider2@example.com"
    owner_headers = _auth_headers(_login(owner_email))
    outsider_headers = _auth_headers(_login(outsider_email))

    conversation_id = _create_conversation(
        owner_email,
        "Shared conversation ownership guard",
        title="Owner only share",
    )

    outsider_create_response = client.post(
        f"/api/v1/workspace/conversations/{conversation_id}/share",
        headers=outsider_headers,
        json={"expires_in_hours": 24},
    )
    assert outsider_create_response.status_code == 404

    owner_create_response = client.post(
        f"/api/v1/workspace/conversations/{conversation_id}/share",
        headers=owner_headers,
        json={"expires_in_hours": 24},
    )
    assert owner_create_response.status_code == 200

    outsider_revoke_response = client.delete(
        f"/api/v1/workspace/conversations/{conversation_id}/share",
        headers=outsider_headers,
    )
    assert outsider_revoke_response.status_code == 404


def test_workspace_conversation_update_and_delete() -> None:
    email = "workspace-conv-edit@example.com"
    headers = _auth_headers(_login(email))
    conversation_id = _create_conversation(
        email,
        "Theo dõi tương tác thuốc ở bệnh nhân đa bệnh lý",
        title="Tiêu đề ban đầu",
    )

    update_response = client.patch(
        f"/api/v1/workspace/conversations/{conversation_id}",
        headers=headers,
        json={"title": "Tiêu đề đã đổi"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["conversation_id"] == conversation_id
    assert updated["title"] == "Tiêu đề đã đổi"

    list_response = client.get("/api/v1/workspace/conversations", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert any(item["conversation_id"] == conversation_id for item in items)

    delete_response = client.delete(
        f"/api/v1/workspace/conversations/{conversation_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    missing_response = client.patch(
        f"/api/v1/workspace/conversations/{conversation_id}",
        headers=headers,
        json={"title": "Không còn"},
    )
    assert missing_response.status_code == 404


def test_workspace_bulk_meta_update_and_share_listing() -> None:
    email = "workspace-bulk-meta@example.com"
    headers = _auth_headers(_login(email))

    folder_response = client.post(
        "/api/v1/workspace/folders",
        headers=headers,
        json={"name": "Bulk Folder"},
    )
    assert folder_response.status_code == 200
    folder_id = folder_response.json()["id"]

    channel_response = client.post(
        "/api/v1/workspace/channels",
        headers=headers,
        json={"name": "Bulk Channel", "visibility": "private"},
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["id"]

    conversation_ids = [
        _create_conversation(email, "bulk meta conversation 1"),
        _create_conversation(email, "bulk meta conversation 2"),
    ]

    bulk_response = client.patch(
        "/api/v1/workspace/conversations/meta/bulk",
        headers=headers,
        json={
            "conversation_ids": conversation_ids,
            "folder_id": folder_id,
            "channel_id": channel_id,
            "is_favorite": True,
            "touched": False,
        },
    )
    assert bulk_response.status_code == 200
    bulk_payload = bulk_response.json()
    assert bulk_payload["updated_count"] == 2
    assert sorted(bulk_payload["updated_ids"]) == sorted(conversation_ids)

    conversations_response = client.get("/api/v1/workspace/conversations", headers=headers)
    assert conversations_response.status_code == 200
    items = conversations_response.json()["items"]
    by_id = {item["conversation_id"]: item for item in items}
    for conversation_id in conversation_ids:
        assert by_id[conversation_id]["folder_id"] == folder_id
        assert by_id[conversation_id]["channel_id"] == channel_id
        assert by_id[conversation_id]["is_favorite"] is True

    create_share_response = client.post(
        f"/api/v1/workspace/conversations/{conversation_ids[0]}/share",
        headers=headers,
        json={"expires_in_hours": 24},
    )
    assert create_share_response.status_code == 200

    list_shares_response = client.get("/api/v1/workspace/shares", headers=headers)
    assert list_shares_response.status_code == 200
    shares = list_shares_response.json()
    assert any(item["conversation_id"] == conversation_ids[0] for item in shares)


def test_workspace_export_markdown_and_docx() -> None:
    email = "workspace-export@example.com"
    headers = _auth_headers(_login(email))
    conversation_id = _create_conversation(
        email,
        "Warfarin và ibuprofen có nguy cơ xuất huyết.",
        title="Export Thread",
    )

    markdown_response = client.get(
        f"/api/v1/workspace/conversations/{conversation_id}/export?format=markdown",
        headers=headers,
    )
    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-type"].startswith("text/markdown")
    assert "# Export Thread" in markdown_response.text
    assert "Warfarin và ibuprofen" in markdown_response.text

    docx_response = client.get(
        f"/api/v1/workspace/conversations/{conversation_id}/export?format=docx",
        headers=headers,
    )
    assert docx_response.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        in docx_response.headers["content-type"]
    )
    assert len(docx_response.content) > 200

    with zipfile.ZipFile(io.BytesIO(docx_response.content), mode="r") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Export Thread" in document_xml


def test_workspace_export_docx_preserves_markdown_styles_and_mermaid_block() -> None:
    email = "workspace-export-rich@example.com"
    headers = _auth_headers(_login(email))
    markdown_answer = (
        "## Kết luận nhanh\n\n"
        "**Nguy cơ cao** khi phối hợp warfarin và NSAID.\n\n"
        "| Thuốc | Mức độ |\n"
        "|---|---|\n"
        "| Warfarin + Ibuprofen | High |\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        "A[Warfarin] --> B[Nguy cơ xuất huyết]\n"
        "```"
    )
    response_text = json.dumps({"result": {"answer_markdown": markdown_answer}}, ensure_ascii=False)
    conversation_id = _create_conversation(
        email,
        "Hãy đánh giá tương tác warfarin với thuốc giảm đau.",
        title="Rich Export Thread",
        response_text=response_text,
    )

    docx_response = client.get(
        f"/api/v1/workspace/conversations/{conversation_id}/export?format=docx",
        headers=headers,
    )
    assert docx_response.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        in docx_response.headers["content-type"]
    )

    with zipfile.ZipFile(io.BytesIO(docx_response.content), mode="r") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Rich Export Thread" in document_xml
    assert "w:b" in document_xml
    assert "w:tbl" in document_xml
    assert "Mermaid Diagram" in document_xml


def test_workspace_export_docx_normalizes_unfenced_mermaid_chart_and_unicode_bullets() -> None:
    email = "workspace-export-normalize@example.com"
    headers = _auth_headers(_login(email))
    markdown_answer = (
        "## Decision Flow (Deep Beta)\n\n"
        "flowchart TD\n"
        "A[Scope] --> B[Retrieve]\n"
        "B --> C[Synthesize]\n\n"
        "### Chart Spec (Deep Beta Signals)\n"
        "type: bar\n"
        "title: Deep Beta Evidence Signals\n"
        "x: [supported_claims, contradicted_claims]\n"
        "y:\n"
        "  - 4\n"
        "  - 1\n\n"
        "• Kiểm tra mâu thuẫn claim-evidence.\n"
        "• Gắn attribution theo từng claim.\n"
    )
    response_text = json.dumps({"result": {"answer_markdown": markdown_answer}}, ensure_ascii=False)
    conversation_id = _create_conversation(
        email,
        "Kiểm tra chuẩn hóa export docx.",
        title="Normalize Export Thread",
        response_text=response_text,
    )

    docx_response = client.get(
        f"/api/v1/workspace/conversations/{conversation_id}/export?format=docx",
        headers=headers,
    )
    assert docx_response.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        in docx_response.headers["content-type"]
    )

    with zipfile.ZipFile(io.BytesIO(docx_response.content), mode="r") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    assert "Normalize Export Thread" in document_xml
    assert "Mermaid Diagram" in document_xml
    assert "Deep Beta Evidence Signals" in document_xml
    assert "supported_claims" in document_xml
    assert "ListBullet" in document_xml


def test_workspace_export_docx_from_markdown_endpoint() -> None:
    email = "workspace-export-direct@example.com"
    headers = _auth_headers(_login(email))
    markdown = (
        "## Decision Flow (Deep Beta)\n\n"
        "flowchart TD\n"
        "A[Scope] --> B[Retrieve]\n"
        "B --> C[Synthesize]\n\n"
        "### Chart Spec (Deep Beta Signals)\n"
        "type: bar\n"
        "title: Deep Beta Evidence Signals\n"
        "x: [supported_claims, contradicted_claims]\n"
        "y:\n"
        "  - 4\n"
        "  - 1\n\n"
        "• claim-level verification\n"
    )

    response = client.post(
        "/api/v1/workspace/export/docx",
        headers=headers,
        json={"markdown": markdown, "title": "direct-export"},
    )
    assert response.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        in response.headers["content-type"]
    )
    assert len(response.content) > 300

    with zipfile.ZipFile(io.BytesIO(response.content), mode="r") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    assert "Mermaid Diagram" in document_xml
    assert "Deep Beta Evidence Signals" in document_xml
    assert "supported_claims" in document_xml
    assert "ListBullet" in document_xml
