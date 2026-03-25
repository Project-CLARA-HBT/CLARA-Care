from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import MedicineCabinet, MedicineItem, User
from clara_api.db.session import get_db
from clara_api.schemas import (
    CabinetAutoDdiRequest,
    CabinetImportRequest,
    CabinetScanDetection,
    CabinetScanTextRequest,
    CabinetScanTextResponse,
    MedicineCabinetItemCreate,
    MedicineCabinetItemResponse,
    MedicineCabinetResponse,
)

router = APIRouter()

DRUG_ALIAS_MAP: dict[str, list[str]] = {
    "paracetamol": ["paracetamol", "acetaminophen", "panadol", "hapacol", "efferalgan"],
    "ibuprofen": ["ibuprofen", "advil", "brufen"],
    "aspirin": ["aspirin"],
    "warfarin": ["warfarin", "coumadin"],
    "lisinopril": ["lisinopril"],
    "metformin": ["metformin", "glucophage"],
    "amoxicillin": ["amoxicillin", "augmentin"],
    "omeprazole": ["omeprazole"],
    "simvastatin": ["simvastatin"],
    "loratadine": ["loratadine", "claritin"],
    "cetirizine": ["cetirizine", "zyrtec"],
    "vitamin c": ["vitamin c", "ascorbic acid", "vitamin-c"],
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _to_title_case(value: str) -> str:
    return " ".join(token.capitalize() for token in value.split(" ") if token)


def _to_item_response(item: MedicineItem) -> MedicineCabinetItemResponse:
    return MedicineCabinetItemResponse(
        id=item.id,
        drug_name=item.drug_name,
        normalized_name=item.normalized_name,
        dosage=item.dosage,
        dosage_form=item.dosage_form,
        quantity=item.quantity,
        source=item.source,
        rx_cui=item.rx_cui,
        ocr_confidence=item.ocr_confidence,
        expires_on=item.expires_on,
        note=item.note,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _require_user(
    token: TokenPayload,
    db: Session,
) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Không tìm thấy người dùng")
    return user


def _get_or_create_cabinet(db: Session, user_id: int) -> MedicineCabinet:
    cabinet = db.execute(
        select(MedicineCabinet).where(MedicineCabinet.user_id == user_id)
    ).scalar_one_or_none()
    if cabinet:
        return cabinet

    cabinet = MedicineCabinet(user_id=user_id, label="Tủ thuốc cá nhân")
    db.add(cabinet)
    db.commit()
    db.refresh(cabinet)
    return cabinet


def _detect_drugs_from_text(text: str) -> list[CabinetScanDetection]:
    normalized_text = text.lower()
    detections: list[CabinetScanDetection] = []

    for canonical, aliases in DRUG_ALIAS_MAP.items():
        for alias in aliases:
            escaped_alias = re.escape(alias)
            pattern = rf"(^|[^a-z0-9]){escaped_alias}([^a-z0-9]|$)"
            if not re.search(pattern, normalized_text, flags=re.IGNORECASE):
                continue

            detections.append(
                CabinetScanDetection(
                    drug_name=_to_title_case(canonical),
                    normalized_name=_normalize_text(canonical),
                    confidence=0.94 if alias == canonical else 0.82,
                    evidence=alias,
                )
            )
            break

    detections.sort(key=lambda item: (-item.confidence, item.drug_name))
    return detections


def _parse_ocr_endpoints(raw: str) -> list[str]:
    entries = [entry.strip() for entry in raw.split(",")]
    return [entry if entry.startswith("/") else f"/{entry}" for entry in entries if entry]


def _collect_text_candidates(payload: Any) -> list[str]:
    candidates: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if len(text) >= 2:
                candidates.append(text)
            return

        if isinstance(value, list):
            for item in value:
                walk(item)
            return

        if not isinstance(value, dict):
            return

        for key, nested in value.items():
            lowered = key.lower()
            if lowered in {"text", "ocr_text", "full_text", "plain_text", "combined_ocr", "content"}:
                walk(nested)
                continue
            if lowered == "lines" and isinstance(nested, list):
                lines = [line.strip() for line in nested if isinstance(line, str) and line.strip()]
                if lines:
                    candidates.append("\n".join(lines))
                continue
            if lowered in {"chunks", "items", "elements", "fields"} and isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict):
                        for inner_key in ("text", "value"):
                            inner_value = item.get(inner_key)
                            if isinstance(inner_value, str) and inner_value.strip():
                                candidates.append(inner_value.strip())
                continue
            walk(nested)

    walk(payload)
    return candidates


def _extract_ocr_text(payload: Any) -> str:
    raw_candidates = _collect_text_candidates(payload)
    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        normalized = _normalize_text(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate.strip())

    if not unique_candidates:
        return ""

    unique_candidates.sort(key=lambda value: len(value), reverse=True)
    longest = unique_candidates[0]
    if len(longest) >= 120:
        return longest
    return "\n".join(unique_candidates[:20]).strip()


def _post_tgc_ocr_multipart(
    url: str,
    file_bytes: bytes,
    file_name: str,
    content_type: str,
    timeout_seconds: float,
    headers: dict[str, str],
) -> httpx.Response:
    files = {"file": (file_name, file_bytes, content_type)}
    return httpx.post(url, files=files, headers=headers, timeout=timeout_seconds)


def _post_tgc_ocr_json(
    url: str,
    file_bytes: bytes,
    timeout_seconds: float,
    headers: dict[str, str],
) -> httpx.Response:
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    payload = {"image": encoded, "lang": "vi"}
    return httpx.post(url, json=payload, headers=headers, timeout=timeout_seconds)


def _scan_with_tgc_ocr(file_bytes: bytes, file_name: str, content_type: str) -> tuple[str, str, str]:
    settings = get_settings()
    endpoints = _parse_ocr_endpoints(settings.tgc_ocr_endpoints)
    if not endpoints:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chưa cấu hình TGC_OCR_ENDPOINTS",
        )

    base_url = settings.tgc_ocr_base_url.rstrip("/")
    headers: dict[str, str] = {}
    if settings.tgc_ocr_api_key.strip():
        headers["x-api-key"] = settings.tgc_ocr_api_key.strip()

    last_error = "Không lấy được văn bản OCR từ TGC service"
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            response = _post_tgc_ocr_multipart(
                url=url,
                file_bytes=file_bytes,
                file_name=file_name,
                content_type=content_type,
                timeout_seconds=settings.tgc_ocr_timeout_seconds,
                headers=headers,
            )
        except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
            last_error = f"Không kết nối được OCR service: {exc.__class__.__name__}"
            continue
        except httpx.HTTPError as exc:
            last_error = f"OCR request lỗi: {exc}"
            continue

        # Some OCR services expose `/ocr` with JSON (base64 image), not multipart.
        if response.status_code in {400, 415, 422} and endpoint.endswith("/ocr"):
            try:
                response = _post_tgc_ocr_json(
                    url=url,
                    file_bytes=file_bytes,
                    timeout_seconds=settings.tgc_ocr_timeout_seconds,
                    headers=headers,
                )
            except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
                last_error = f"Không kết nối được OCR service: {exc.__class__.__name__}"
                continue
            except httpx.HTTPError as exc:
                last_error = f"OCR request lỗi: {exc}"
                continue

        if response.status_code >= 500:
            last_error = f"OCR upstream error: status={response.status_code}"
            continue
        if response.status_code >= 400:
            last_error = f"OCR endpoint từ chối request: status={response.status_code}"
            continue

        try:
            payload = response.json()
        except ValueError:
            last_error = "OCR endpoint trả về JSON không hợp lệ"
            continue

        extracted_text = _extract_ocr_text(payload)
        if not extracted_text:
            last_error = "OCR endpoint không trả về text hữu ích"
            continue

        return extracted_text, endpoint, "tgc-transhub"

    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=last_error)


@router.get("/cabinet", response_model=MedicineCabinetResponse)
def get_cabinet(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> MedicineCabinetResponse:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)
    items = db.execute(
        select(MedicineItem)
        .where(MedicineItem.cabinet_id == cabinet.id)
        .order_by(MedicineItem.updated_at.desc(), MedicineItem.id.desc())
    ).scalars().all()
    return MedicineCabinetResponse(
        cabinet_id=cabinet.id,
        label=cabinet.label,
        items=[_to_item_response(item) for item in items],
    )


@router.post("/cabinet/items", response_model=MedicineCabinetItemResponse)
def add_cabinet_item(
    payload: MedicineCabinetItemCreate,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> MedicineCabinetItemResponse:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)

    normalized = _normalize_text(payload.drug_name)
    existing = db.execute(
        select(MedicineItem).where(
            MedicineItem.cabinet_id == cabinet.id,
            MedicineItem.normalized_name == normalized,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Thuốc đã tồn tại trong tủ thuốc")

    item = MedicineItem(
        cabinet_id=cabinet.id,
        drug_name=payload.drug_name.strip(),
        normalized_name=normalized,
        dosage=payload.dosage.strip(),
        dosage_form=payload.dosage_form.strip(),
        quantity=payload.quantity,
        source=payload.source,
        rx_cui=payload.rx_cui.strip(),
        ocr_confidence=payload.ocr_confidence,
        expires_on=payload.expires_on,
        note=payload.note.strip(),
        updated_at=datetime.now(tz=UTC),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_item_response(item)


@router.delete("/cabinet/items/{item_id}")
def delete_cabinet_item(
    item_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)
    item = db.execute(
        select(MedicineItem).where(
            MedicineItem.id == item_id,
            MedicineItem.cabinet_id == cabinet.id,
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thuốc")

    db.delete(item)
    db.commit()
    return {"deleted": True}


@router.post("/cabinet/scan-text", response_model=CabinetScanTextResponse)
def scan_cabinet_text(
    payload: CabinetScanTextRequest,
    _token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
) -> CabinetScanTextResponse:
    return CabinetScanTextResponse(detections=_detect_drugs_from_text(payload.text), extracted_text=payload.text)


@router.post("/cabinet/scan-file", response_model=CabinetScanTextResponse)
async def scan_cabinet_file(
    file: UploadFile = File(...),
    _token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
) -> CabinetScanTextResponse:
    file_name = file.filename or "uploaded-receipt"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File upload rỗng")
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File vượt quá 20MB",
        )

    extracted_text, used_endpoint, ocr_provider = _scan_with_tgc_ocr(
        file_bytes=file_bytes,
        file_name=file_name,
        content_type=content_type,
    )
    detections = _detect_drugs_from_text(extracted_text)
    return CabinetScanTextResponse(
        detections=detections,
        extracted_text=extracted_text[:4000],
        ocr_provider=ocr_provider,
        ocr_endpoint=used_endpoint,
    )


@router.post("/cabinet/import-detections")
def import_detections(
    payload: CabinetImportRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)

    existing_names = set(
        db.execute(
            select(MedicineItem.normalized_name).where(MedicineItem.cabinet_id == cabinet.id)
        ).scalars().all()
    )

    inserted = 0
    for detection in payload.detections:
        normalized = _normalize_text(detection.normalized_name or detection.drug_name)
        if not normalized or normalized in existing_names:
            continue
        item = MedicineItem(
            cabinet_id=cabinet.id,
            drug_name=detection.drug_name.strip(),
            normalized_name=normalized,
            source="ocr",
            ocr_confidence=detection.confidence,
            note=f"Phát hiện OCR: {detection.evidence}",
            updated_at=datetime.now(tz=UTC),
        )
        db.add(item)
        existing_names.add(normalized)
        inserted += 1

    db.commit()
    return {"inserted": inserted}


@router.post("/cabinet/auto-ddi-check")
def run_auto_ddi_check(
    payload: CabinetAutoDdiRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)
    medication_names = db.execute(
        select(MedicineItem.normalized_name).where(MedicineItem.cabinet_id == cabinet.id)
    ).scalars().all()

    request_payload: dict[str, Any] = {
        "symptoms": payload.symptoms,
        "labs": payload.labs,
        "medications": sorted(set(medication_names)),
        "allergies": payload.allergies,
    }
    return proxy_ml_post("/v1/careguard/analyze", request_payload)


@router.post("/analyze")
def careguard_analyze(
    payload: dict[str, Any],
    _token: TokenPayload = Depends(require_roles("normal", "doctor")),
) -> dict[str, Any]:
    return proxy_ml_post("/v1/careguard/analyze", payload)
