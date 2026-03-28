from typing import Any

import httpx
from fastapi import HTTPException, status

from clara_api.core.config import get_settings


def _build_fail_soft_response(fail_soft_payload: dict[str, Any], reason: str) -> dict[str, Any]:
    response = dict(fail_soft_payload)
    response.setdefault("metadata", {})
    response.setdefault("citations", [])
    response.setdefault("fallback", True)
    response.setdefault("fallback_reason", reason)
    return response


def proxy_ml_post(
    ml_path: str,
    payload: dict[str, Any],
    *,
    fail_soft_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/{ml_path.lstrip('/')}"
    response: httpx.Response | None = None

    for attempt in range(2):
        try:
            response = httpx.post(url, json=payload, timeout=settings.ml_service_timeout_seconds)
            break
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            if attempt < 1:
                continue
            if fail_soft_payload is not None:
                return _build_fail_soft_response(fail_soft_payload, exc.__class__.__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ML service unavailable: {exc.__class__.__name__}",
            ) from exc
        except httpx.NetworkError as exc:
            if fail_soft_payload is not None:
                return _build_fail_soft_response(fail_soft_payload, exc.__class__.__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ML service unavailable: {exc.__class__.__name__}",
            ) from exc
        except httpx.HTTPError as exc:
            if fail_soft_payload is not None:
                return _build_fail_soft_response(fail_soft_payload, exc.__class__.__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ML service unavailable: {exc}",
            ) from exc

    if response is None:
        if fail_soft_payload is not None:
            return _build_fail_soft_response(fail_soft_payload, "NoResponse")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ML service unavailable: no response",
        )

    if response.status_code >= 500:
        if fail_soft_payload is not None:
            return _build_fail_soft_response(fail_soft_payload, f"status_{response.status_code}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML service upstream error: status={response.status_code}",
        )
    if response.status_code >= 400:
        if fail_soft_payload is not None:
            return _build_fail_soft_response(fail_soft_payload, f"status_{response.status_code}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML service rejected request: status={response.status_code}",
        )

    try:
        data = response.json()
    except ValueError as exc:
        if fail_soft_payload is not None:
            return _build_fail_soft_response(fail_soft_payload, "InvalidJSON")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ML service returned invalid JSON",
        ) from exc

    if not isinstance(data, dict):
        if fail_soft_payload is not None:
            return _build_fail_soft_response(fail_soft_payload, "UnexpectedPayloadFormat")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ML service returned unexpected payload format",
        )

    return data
