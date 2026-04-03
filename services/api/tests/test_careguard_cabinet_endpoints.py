from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.core.security import create_access_token
from clara_api.main import app

client = TestClient(app)


def _login_without_consent(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    status_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    required_version = status_response.json()["required_version"]
    accept_response = client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": required_version, "accepted": True},
    )
    assert accept_response.status_code == 200
    return token


def _login_doctor() -> str:
    return _login("doctor-mapping@doctor.clara")


def _login_admin() -> str:
    settings = get_settings()
    token = create_access_token(subject=settings.auth_bootstrap_admin_email, role="admin")
    status_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    required_version = status_response.json()["required_version"]
    accept_response = client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": required_version, "accepted": True},
    )
    assert accept_response.status_code == 200
    return token


def test_cabinet_requires_consent_gate() -> None:
    token = _login_without_consent("consent-required@example.com")
    response = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 428
    assert "miễn trừ trách nhiệm y tế" in response.json()["detail"]


def test_cabinet_lifecycle() -> None:
    token = _login("cabinet-user@example.com")

    get_response = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    assert "items" in get_response.json()

    add_response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "drug_name": "Metformin",
            "dosage": "500mg",
            "quantity": 10,
            "source": "manual",
        },
    )
    assert add_response.status_code == 200
    item_id = add_response.json()["id"]
    assert add_response.json()["normalization_source"] in {"db", "candidate", "fallback"}
    assert 0.0 <= add_response.json()["normalization_confidence"] <= 1.0

    patch_response = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "drug_name": "Warfarin",
            "dosage": "3mg",
            "quantity": 14,
            "note": "uống buổi tối",
        },
    )
    assert patch_response.status_code == 200
    patched_item = patch_response.json()
    assert patched_item["drug_name"] == "Warfarin"
    assert patched_item["normalized_name"] == "warfarin"
    assert patched_item["dosage"] == "3mg"
    assert patched_item["quantity"] == 14
    assert patched_item["note"] == "uống buổi tối"
    assert patched_item["normalization_source"] in {"db", "candidate", "fallback"}
    assert 0.0 <= patched_item["normalization_confidence"] <= 1.0

    list_response = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert any(item["id"] == item_id for item in list_response.json()["items"])

    delete_response = client.delete(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True


def test_update_cabinet_item_put_alias_and_validation() -> None:
    token = _login("cabinet-update-user@example.com")
    add_response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "drug_name": "Metformin",
            "dosage": "500mg",
            "quantity": 10,
            "source": "manual",
        },
    )
    assert add_response.status_code == 200
    item_id = add_response.json()["id"]

    empty_update_response = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert empty_update_response.status_code == 400
    assert "Payload cập nhật rỗng" in empty_update_response.json()["detail"]

    put_response = client.put(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "quantity": 21,
            "source": "imported",
            "note": "đã chỉnh sửa qua endpoint PUT",
        },
    )
    assert put_response.status_code == 200
    body = put_response.json()
    assert body["id"] == item_id
    assert body["quantity"] == 21
    assert body["source"] == "imported"
    assert body["note"] == "đã chỉnh sửa qua endpoint PUT"


def test_update_cabinet_item_rejects_duplicate_drug_name() -> None:
    token = _login("cabinet-update-duplicate@example.com")
    add_warfarin = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_name": "Warfarin", "source": "manual"},
    )
    add_metformin = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_name": "Metformin", "source": "manual"},
    )
    assert add_warfarin.status_code == 200
    assert add_metformin.status_code == 200

    metformin_item_id = add_metformin.json()["id"]
    duplicate_response = client.patch(
        f"/api/v1/careguard/cabinet/items/{metformin_item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_name": "Warfarin"},
    )
    assert duplicate_response.status_code == 409
    assert "Thuốc đã tồn tại" in duplicate_response.json()["detail"]


def test_update_cabinet_item_isolated_by_user() -> None:
    owner_token = _login("cabinet-update-owner@example.com")
    outsider_token = _login("cabinet-update-outsider@example.com")

    add_response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"drug_name": "Aspirin", "source": "manual"},
    )
    assert add_response.status_code == 200
    item_id = add_response.json()["id"]

    outsider_update_response = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {outsider_token}"},
        json={"dosage": "100mg"},
    )
    assert outsider_update_response.status_code == 404
    assert "Không tìm thấy thuốc" in outsider_update_response.json()["detail"]


def test_scan_and_import_detection() -> None:
    token = _login("scan-user@example.com")
    scan_response = client.post(
        "/api/v1/careguard/cabinet/scan-text",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Toa thuoc: Panadol 500mg, ibuprofen 200mg"},
    )
    assert scan_response.status_code == 200
    detections = scan_response.json()["detections"]
    assert len(detections) >= 1
    assert all("requires_manual_confirm" in item for item in detections)
    assert all("confirmed" in item for item in detections)
    assert all("mapping_source" in item for item in detections)
    assert all("mapping_confidence" in item for item in detections)

    normalized_detections = []
    for detection in detections:
        updated = dict(detection)
        if updated["requires_manual_confirm"]:
            updated["confirmed"] = True
        normalized_detections.append(updated)

    import_response = client.post(
        "/api/v1/careguard/cabinet/import-detections",
        headers={"Authorization": f"Bearer {token}"},
        json={"detections": normalized_detections},
    )
    assert import_response.status_code == 200
    assert import_response.json()["inserted"] >= 1


def test_scan_text_applies_ocr_post_correction() -> None:
    token = _login("scan-ocr-correct-user@example.com")
    response = client.post(
        "/api/v1/careguard/cabinet/scan-text",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Toa thuoc: warfariin 3mg moi toi"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ocr_provider"] == "ocr-postprocess"
    assert payload["ocr_endpoint"] == "local-ocr-correction"
    assert "warfarin" in (payload.get("extracted_text") or "").lower()
    detections = payload["detections"]
    assert any(item["normalized_name"] == "warfarin" for item in detections)


def test_scan_text_keeps_manual_confirm_for_low_confidence_after_correction() -> None:
    token = _login("scan-ocr-low-confidence@example.com")
    response = client.post(
        "/api/v1/careguard/cabinet/scan-text",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Toa thuoc: panad0l 500mg sau an"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "panadol" in (payload.get("extracted_text") or "").lower()
    detections = payload["detections"]
    panadol_detection = next(
        (item for item in detections if item["normalized_name"] == "paracetamol"),
        None,
    )
    assert panadol_detection is not None
    assert panadol_detection["requires_manual_confirm"] is True
    assert panadol_detection["confirmed"] is False
    assert panadol_detection["confidence"] < 0.9

    # Correction is applied, but low-confidence detections still require explicit confirm at import.
    import_response = client.post(
        "/api/v1/careguard/cabinet/import-detections",
        headers={"Authorization": f"Bearer {token}"},
        json={"detections": detections},
    )
    assert import_response.status_code == 422
    detail = import_response.json()["detail"]
    assert detail["error"] == "manual_confirmation_required"


def test_import_detection_rejects_low_confidence_without_confirmation() -> None:
    token = _login("scan-reject-user@example.com")
    import_response = client.post(
        "/api/v1/careguard/cabinet/import-detections",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "detections": [
                {
                    "drug_name": "Panadol",
                    "normalized_name": "paracetamol",
                    "confidence": 0.82,
                    "evidence": "panadol",
                    "requires_manual_confirm": True,
                    "confirmed": False,
                }
            ]
        },
    )
    assert import_response.status_code == 422
    detail = import_response.json()["detail"]
    assert detail["error"] == "manual_confirmation_required"
    assert detail["blocked_detections"][0]["drug_name"] == "Panadol"


def test_scan_file_uses_tgc_ocr(monkeypatch) -> None:
    token = _login("scan-file-user@example.com")

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    captured: dict[str, object] = {}
    call_kinds: list[tuple[bool, bool]] = []

    def _fake_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        url = kwargs.get("url", args[0] if args else "")
        captured["url"] = url
        has_files = kwargs.get("files") is not None
        has_json = kwargs.get("json") is not None
        captured["has_files"] = has_files
        captured["has_json"] = has_json
        call_kinds.append((has_files, has_json))

        if has_files:
            return _FakeResponse(422, {"detail": "multipart not supported"})
        if has_json:
            return _FakeResponse(200, {"text": "Hoa don: Panadol 500mg, ibuprofen 200mg"})
        return _FakeResponse(500, {"detail": "unexpected request"})

    monkeypatch.setattr("clara_api.api.v1.endpoints.careguard.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/careguard/cabinet/scan-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("receipt.jpg", b"fake-image-data", "image/jpeg")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ocr_provider"] == "tgc-transhub"
    assert payload["ocr_endpoint"] == "/api/ocr"
    assert len(payload["detections"]) >= 1
    assert any(has_files for has_files, _ in call_kinds)
    assert any(has_json for _, has_json in call_kinds)


def test_vn_dictionary_requires_doctor_role() -> None:
    normal_token = _login("normal-mapping@example.com")
    response = client.get(
        "/api/v1/careguard/dictionary",
        headers={"Authorization": f"Bearer {normal_token}"},
    )
    assert response.status_code == 403
    assert "Không đủ quyền" in response.json()["detail"]


def test_vn_dictionary_crud_and_resolve() -> None:
    doctor_token = _login_doctor()

    create_response = client.post(
        "/api/v1/careguard/dictionary",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "brand_name": "Panadol Plus VN",
            "aliases": ["Panadol Plus VN", "Panadol-VN Plus"],
            "active_ingredients": "Paracetamol + Caffeine",
            "normalized_name": "paracetamol caffeine",
            "rx_cui": "999001",
            "mapping_source": "manual",
            "notes": "test mapping",
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    mapping_id = create_response.json()["id"]
    assert create_response.json()["normalized_name"] == "paracetamol caffeine"

    list_response = client.get(
        "/api/v1/careguard/dictionary?q=panadol",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1
    assert any(item["id"] == mapping_id for item in list_response.json()["items"])

    resolve_response = client.post(
        "/api/v1/careguard/dictionary/resolve",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"drug_name": "Panadol-VN Plus"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["mapping_source"] == "db"
    assert resolve_response.json()["mapping_confidence"] == 1.0
    assert resolve_response.json()["normalized_name"] == "paracetamol caffeine"
    assert resolve_response.json()["rx_cui"] == "999001"

    add_item_response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "drug_name": "Panadol-VN Plus",
            "dosage": "500mg",
            "quantity": 3,
            "source": "manual",
        },
    )
    assert add_item_response.status_code == 200
    assert add_item_response.json()["normalized_name"] == "paracetamol caffeine"
    assert add_item_response.json()["rx_cui"] == "999001"
    assert add_item_response.json()["normalization_source"] in {"db", "candidate", "fallback"}
    assert 0.0 <= add_item_response.json()["normalization_confidence"] <= 1.0

    update_response = client.patch(
        f"/api/v1/careguard/dictionary/{mapping_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"rx_cui": "999002"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["rx_cui"] == "999002"

    delete_response = client.delete(
        f"/api/v1/careguard/dictionary/{mapping_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    resolve_after_delete = client.post(
        "/api/v1/careguard/dictionary/resolve",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"drug_name": "Panadol-VN Plus"},
    )
    assert resolve_after_delete.status_code == 200
    assert resolve_after_delete.json()["mapping_source"] == "fallback"
    assert 0.0 <= resolve_after_delete.json()["mapping_confidence"] <= 1.0


def test_vn_dictionary_curation_requires_admin_role() -> None:
    doctor_token = _login_doctor()
    create_response = client.post(
        "/api/v1/careguard/dictionary",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "brand_name": "Curation Role Gate Drug",
            "aliases": ["Curation Role Gate Drug"],
            "active_ingredients": "Paracetamol",
            "normalized_name": "paracetamol",
            "rx_cui": "161",
            "mapping_source": "manual",
            "notes": "role gate",
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    mapping_id = create_response.json()["id"]

    doctor_curation_response = client.post(
        f"/api/v1/careguard/dictionary/{mapping_id}/curation",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"is_active": False, "reason": "doctor should be blocked"},
    )
    assert doctor_curation_response.status_code == 403
    assert "Không đủ quyền" in doctor_curation_response.json()["detail"]


def test_vn_dictionary_admin_curation_and_audit_trail() -> None:
    doctor_token = _login_doctor()
    admin_token = _login_admin()

    create_response = client.post(
        "/api/v1/careguard/dictionary",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "brand_name": "Audit Trail Drug",
            "aliases": ["Audit Trail Drug", "AuditTrail"],
            "active_ingredients": "Paracetamol + Caffeine",
            "normalized_name": "paracetamol caffeine",
            "rx_cui": "999111",
            "mapping_source": "manual",
            "notes": "needs curation",
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    mapping_id = create_response.json()["id"]

    approve_response = client.post(
        f"/api/v1/careguard/dictionary/{mapping_id}/curation",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "aliases": ["Audit Trail Drug", "AuditTrail", "Audit Drug VN"],
            "notes": "reviewed by admin",
            "rx_cui": "999222",
            "is_active": True,
            "reason": "reviewed",
        },
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["mapping_source"] == "curated"
    assert approve_response.json()["is_active"] is True
    assert approve_response.json()["rx_cui"] == "999222"
    assert "Audit Drug VN" in approve_response.json()["aliases"]

    reject_response = client.post(
        f"/api/v1/careguard/dictionary/{mapping_id}/curation",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False, "reason": "deactivate due to duplicate"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["is_active"] is False

    doctor_audit_response = client.get(
        f"/api/v1/careguard/dictionary/{mapping_id}/audit",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert doctor_audit_response.status_code == 403

    audit_response = client.get(
        f"/api/v1/careguard/dictionary/{mapping_id}/audit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert audit_payload["total"] >= 3
    actions = [item["action"] for item in audit_payload["items"]]
    assert "create" in actions
    assert actions.count("curate") >= 2
    latest = audit_payload["items"][0]
    assert latest["actor_email"] == get_settings().auth_bootstrap_admin_email
    assert latest["reason"] == "deactivate due to duplicate"
    assert isinstance(latest.get("before_json"), (dict, type(None)))
    assert isinstance(latest.get("after_json"), (dict, type(None)))
    assert isinstance(latest.get("metadata_json"), (dict, type(None)))

def test_dictionary_resolve_candidate_match() -> None:
    doctor_token = _login_doctor()
    create_response = client.post(
        "/api/v1/careguard/dictionary",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "brand_name": "Panadol Hybrid Candidate A",
            "aliases": ["Panadol Hybrid Candidate A"],
            "active_ingredients": "Paracetamol + Caffeine",
            "normalized_name": "paracetamol caffeine",
            "rx_cui": "900001",
            "mapping_source": "manual",
            "notes": "candidate match test",
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    mapping_id = create_response.json()["id"]

    resolve_response = client.post(
        "/api/v1/careguard/dictionary/resolve",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"drug_name": "Panadol Hybrd Candidate A"},
    )
    assert resolve_response.status_code == 200
    payload = resolve_response.json()
    assert payload["mapping_source"] == "candidate"
    assert payload["mapping_confidence"] >= 0.78
    assert payload["normalized_name"] == "paracetamol caffeine"
    assert payload["rx_cui"] == "900001"

    delete_response = client.delete(
        f"/api/v1/careguard/dictionary/{mapping_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert delete_response.status_code == 200


def test_add_cabinet_item_candidate_normalization() -> None:
    doctor_token = _login_doctor()
    create_response = client.post(
        "/api/v1/careguard/dictionary",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "brand_name": "Panadol Hybrid Candidate B",
            "aliases": ["Panadol Hybrid Candidate B"],
            "active_ingredients": "Paracetamol + Caffeine",
            "normalized_name": "paracetamol caffeine",
            "rx_cui": "900002",
            "mapping_source": "manual",
            "notes": "candidate add test",
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    mapping_id = create_response.json()["id"]

    add_response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"drug_name": "Panadol Hybrd Candidate B", "source": "manual"},
    )
    assert add_response.status_code == 200
    added = add_response.json()
    assert added["normalized_name"] == "paracetamol caffeine"
    assert added["rx_cui"] == "900002"
    assert added["normalization_source"] == "candidate"
    assert added["normalization_confidence"] >= 0.78

    duplicate_response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"drug_name": "Panadol Hybrid Candidate B", "source": "manual"},
    )
    assert duplicate_response.status_code == 409
    assert "Thuốc đã tồn tại" in duplicate_response.json()["detail"]

    delete_response = client.delete(
        f"/api/v1/careguard/dictionary/{mapping_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert delete_response.status_code == 200


def test_import_detections_candidate_normalization() -> None:
    doctor_token = _login_doctor()
    create_response = client.post(
        "/api/v1/careguard/dictionary",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "brand_name": "Panadol Hybrid Candidate C",
            "aliases": ["Panadol Hybrid Candidate C"],
            "active_ingredients": "Paracetamol + Caffeine",
            "normalized_name": "paracetamol caffeine",
            "rx_cui": "900003",
            "mapping_source": "manual",
            "notes": "candidate import test",
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    mapping_id = create_response.json()["id"]

    import_response = client.post(
        "/api/v1/careguard/cabinet/import-detections",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "detections": [
                {
                    "drug_name": "Panadol Hybrd Candidate C",
                    "normalized_name": "Panadol Hybrd Candidate C",
                    "confidence": 0.95,
                    "evidence": "ocr-line-candidate",
                    "requires_manual_confirm": False,
                    "confirmed": True,
                }
            ]
        },
    )
    assert import_response.status_code == 200
    assert import_response.json()["inserted"] == 1

    cabinet_response = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert cabinet_response.status_code == 200
    assert any(
        item["normalized_name"] == "paracetamol caffeine"
        and item["rx_cui"] == "900003"
        and item["normalization_source"] in {"db", "candidate", "fallback"}
        and 0.0 <= item["normalization_confidence"] <= 1.0
        for item in cabinet_response.json()["items"]
    )

    delete_response = client.delete(
        f"/api/v1/careguard/dictionary/{mapping_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert delete_response.status_code == 200


def test_auto_ddi_proxy_payload(monkeypatch) -> None:
    token = _login("ddi-user@example.com")
    client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_name": "Warfarin", "source": "manual"},
    )

    captured: dict[str, object] = {}

    def _fake_proxy(path: str, payload: dict[str, object]) -> dict[str, object]:
        captured["path"] = path
        captured["payload"] = payload
        return {
            "risk_tier": "high",
            "ddi_alerts": [{"title": "test"}],
            "recommendations": ["test"],
            "citations": [{"source": "RxNorm", "url": "https://rxnav.nlm.nih.gov/"}],
            "metadata": {
                "source_used": ["local_rules", "rxnav", "openfda"],
                "source_errors": {"openfda": ["timeout"]},
            },
        }

    monkeypatch.setattr("clara_api.api.v1.endpoints.careguard.proxy_ml_post", _fake_proxy)

    response = client.post(
        "/api/v1/careguard/cabinet/auto-ddi-check",
        headers={"Authorization": f"Bearer {token}"},
        json={"allergies": ["penicillin"], "symptoms": [], "labs": {}},
    )
    assert response.status_code == 200
    assert captured["path"] == "/v1/careguard/analyze"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "medications" in payload
    assert "medications_with_meta" in payload
    assert isinstance(payload["medications_with_meta"], list)
    assert len(payload["medications_with_meta"]) >= 1
    first_med = payload["medications_with_meta"][0]
    assert first_med["mapping_source"] in {"db", "candidate", "fallback"}
    assert 0.0 <= first_med["mapping_confidence"] <= 1.0
    assert payload["external_ddi_enabled"] is False
    body = response.json()
    assert "attribution" in body
    assert "attributions" in body
    assert body["attribution"]["channel"] == "careguard"
    assert body["attribution"]["mode"] == "external_plus_local"
    assert body["attribution"]["citation_count"] == 1
    assert body["attribution"]["source_used"] == ["local_rules", "rxnav", "openfda"]
    assert body["attribution"]["source_errors"] == {"openfda": ["timeout"]}
    assert body["attribution"]["source_count"] == 3
    assert isinstance(body["attributions"], list)
    assert body["attributions"][0]["channel"] == "careguard"
