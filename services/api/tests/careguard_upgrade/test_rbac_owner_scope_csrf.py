"""RBAC / owner-scope and CSRF preservation on the CareGuard surfaces.

Feature: clara-selfmed-careguard-upgrade (task 11.2)

Pins Requirements 12.4 (RBAC/owner-scoping on the cabinet, dictionary-admin, and
metrics surfaces) and 12.5 (CSRF protection on cookie-authenticated mutating
endpoints). These guardrails are unconditional — they do not depend on any new
``SELFMED_*`` / ``CAREGUARD_*`` flag (except the observability metrics surface,
which is flag-gated as designed) — so previously-valid authenticated requests
remain accepted and the flags-off baseline is preserved.

What is pinned, mapped to the CURRENT route definitions in
``endpoints/careguard.py`` (and the global CSRF middleware in ``main.py``):

* Cabinet (``/careguard/cabinet*``): authenticated, owner-scoped. A request
  with no credentials is rejected (401); a second user never sees or mutates the
  first user's items (owner isolation — Req 1.6, 11.5).
* Dictionary CRUD (``GET/POST/PATCH/DELETE /careguard/dictionary*``,
  ``/dictionary/resolve``): ``require_roles("doctor")`` (admin always allowed).
  A ``normal`` / ``researcher`` caller is rejected (403); a ``doctor`` is
  admitted.
* Dictionary curation + audit (``/dictionary/{id}/curation``,
  ``/dictionary/{id}/audit``): ``require_roles("admin")``. A ``doctor`` (and any
  non-admin) is rejected (403); an ``admin`` is admitted.
* Observability metrics (``GET /careguard/metrics``): ``require_roles("admin")``
  and gated by ``CAREGUARD_OBSERVABILITY_ENABLED``. Non-admin → 403; admin with
  the flag off → 404 (ships dark); admin with the flag on → 200.
* CSRF: a cookie-authenticated mutation without a valid CSRF token is rejected
  (403); a Bearer-authenticated mutation and a cookie request carrying a
  matching CSRF cookie+header are admitted.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.core.security import create_access_token
from clara_api.main import app

client = TestClient(app)

# Bootstrap admin credentials provisioned by the repository-root test conftest.
_BOOTSTRAP_ADMIN_EMAIL = "admin@example.com"
_BOOTSTRAP_ADMIN_PASSWORD = "test-admin-pass-123"


def _unique_email(prefix: str, domain: str = "example.com") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@{domain}"


def _login_with_consent(email: str, password: str = "secret123") -> str:
    """Full login + medical-disclaimer consent, returning a Bearer token.

    Mirrors the helper in ``test_cabinet_validation_guards``. New ``normal`` /
    ``doctor`` / ``researcher`` users are auto-provisioned by the (non-prod)
    login path from the email domain; the pre-existing bootstrap admin is found
    as-is. Accepting consent satisfies the ``_require_user`` gate so authorized
    callers reach the endpoint body rather than being stopped at the 428 consent
    precondition.
    """

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    status_response = client.get("/api/v1/auth/consent-status", headers=headers)
    assert status_response.status_code == 200, status_response.text
    required_version = status_response.json()["required_version"]
    accept = client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={"consent_version": required_version, "accepted": True},
    )
    assert accept.status_code == 200, accept.text
    return token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _minted(role: str) -> dict[str, str]:
    """Authorization header for a freshly-minted token of ``role``.

    RBAC is enforced by the ``require_roles`` dependency, which inspects only the
    decoded JWT role and runs BEFORE the endpoint body (and before any DB user
    lookup / consent gate). A minted token is therefore sufficient to pin a 403
    rejection without provisioning a user. Sending it via the ``Authorization``
    header also makes the request Bearer-authenticated, so the CSRF middleware
    does not apply (it targets cookie sessions only).
    """

    return _bearer(create_access_token(subject=_unique_email(role), role=role))


# ===========================================================================
# Req 12.4 — Cabinet: authentication + owner isolation
# ===========================================================================


def test_cabinet_requires_authentication() -> None:
    client.cookies.clear()
    response = client.get("/api/v1/careguard/cabinet")
    assert response.status_code == 401


def test_cabinet_mutation_requires_authentication() -> None:
    client.cookies.clear()
    response = client.post(
        "/api/v1/careguard/cabinet/items",
        json={"source": "manual", "drug_name": "Paracetamol"},
    )
    assert response.status_code == 401


def test_cabinet_read_is_owner_scoped() -> None:
    owner = _login_with_consent(_unique_email("scope-owner"))
    outsider = _login_with_consent(_unique_email("scope-outsider"))

    created = client.post(
        "/api/v1/careguard/cabinet/items",
        headers=_bearer(owner),
        json={"source": "manual", "drug_name": "Warfarin"},
    )
    assert created.status_code == 200, created.text
    owner_item_id = created.json()["id"]

    # The outsider's cabinet is a distinct, empty cabinet — the owner's row is
    # never visible across the account boundary.
    outsider_cabinet = client.get(
        "/api/v1/careguard/cabinet", headers=_bearer(outsider)
    )
    assert outsider_cabinet.status_code == 200, outsider_cabinet.text
    assert all(item["id"] != owner_item_id for item in outsider_cabinet.json()["items"])


def test_cabinet_item_not_readable_or_mutable_by_non_owner() -> None:
    owner = _login_with_consent(_unique_email("scope2-owner"))
    outsider = _login_with_consent(_unique_email("scope2-outsider"))

    created = client.post(
        "/api/v1/careguard/cabinet/items",
        headers=_bearer(owner),
        json={"source": "manual", "drug_name": "Aspirin"},
    )
    assert created.status_code == 200, created.text
    item_id = created.json()["id"]

    # A non-owner cannot mutate the targeted row (owner-scope, Req 1.6).
    patched = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers=_bearer(outsider),
        json={"dosage": "100mg"},
    )
    assert patched.status_code == 404

    deleted = client.delete(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers=_bearer(outsider),
    )
    assert deleted.status_code == 404

    # The owner's row survives untouched (Req 11.5).
    owner_cabinet = client.get("/api/v1/careguard/cabinet", headers=_bearer(owner))
    assert any(item["id"] == item_id for item in owner_cabinet.json()["items"])


# ===========================================================================
# Req 12.4 — Dictionary CRUD: doctor (or admin) only
# ===========================================================================


def test_dictionary_list_rejects_normal_role() -> None:
    response = client.get("/api/v1/careguard/dictionary", headers=_minted("normal"))
    assert response.status_code == 403
    assert response.json()["detail"] == "Không đủ quyền truy cập"


def test_dictionary_list_rejects_researcher_role() -> None:
    response = client.get("/api/v1/careguard/dictionary", headers=_minted("researcher"))
    assert response.status_code == 403


def test_dictionary_create_rejects_normal_role() -> None:
    response = client.post(
        "/api/v1/careguard/dictionary",
        headers=_minted("normal"),
        json={
            "brand_name": "Panadol",
            "active_ingredients": "paracetamol",
            "normalized_name": "paracetamol",
            "aliases": [],
        },
    )
    assert response.status_code == 403


def test_dictionary_update_rejects_researcher_role() -> None:
    response = client.patch(
        "/api/v1/careguard/dictionary/1",
        headers=_minted("researcher"),
        json={"notes": "x"},
    )
    assert response.status_code == 403


def test_dictionary_delete_rejects_normal_role() -> None:
    response = client.delete(
        "/api/v1/careguard/dictionary/1", headers=_minted("normal")
    )
    assert response.status_code == 403


def test_dictionary_resolve_rejects_normal_role() -> None:
    response = client.post(
        "/api/v1/careguard/dictionary/resolve",
        headers=_minted("normal"),
        json={"drug_name": "Panadol"},
    )
    assert response.status_code == 403


def test_dictionary_list_admitted_for_doctor() -> None:
    doctor = _login_with_consent(_unique_email("dict-doctor", "doctor.clara"))
    response = client.get("/api/v1/careguard/dictionary", headers=_bearer(doctor))
    assert response.status_code == 200, response.text
    body = response.json()
    assert "items" in body and "total" in body


# ===========================================================================
# Req 12.4 — Dictionary curation + audit: admin only
# ===========================================================================


def test_dictionary_curation_rejects_doctor_role() -> None:
    # A doctor may run CRUD but NOT curation — that is admin-only.
    response = client.post(
        "/api/v1/careguard/dictionary/1/curation",
        headers=_minted("doctor"),
        json={"reason": "review", "notes": "x"},
    )
    assert response.status_code == 403


def test_dictionary_curation_rejects_normal_role() -> None:
    response = client.post(
        "/api/v1/careguard/dictionary/1/curation",
        headers=_minted("normal"),
        json={"reason": "review", "notes": "x"},
    )
    assert response.status_code == 403


def test_dictionary_audit_rejects_doctor_role() -> None:
    response = client.get(
        "/api/v1/careguard/dictionary/1/audit", headers=_minted("doctor")
    )
    assert response.status_code == 403


def test_dictionary_curation_admitted_for_admin() -> None:
    # The admin clears RBAC + the admin-user gate and reaches the body; a
    # non-existent mapping then yields 404 (not 403/401), proving authorization.
    admin = _login_with_consent(_BOOTSTRAP_ADMIN_EMAIL, _BOOTSTRAP_ADMIN_PASSWORD)
    response = client.post(
        "/api/v1/careguard/dictionary/999999/curation",
        headers=_bearer(admin),
        json={"reason": "review", "notes": "x"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Không tìm thấy mapping"


def test_dictionary_audit_admitted_for_admin() -> None:
    admin = _login_with_consent(_BOOTSTRAP_ADMIN_EMAIL, _BOOTSTRAP_ADMIN_PASSWORD)
    response = client.get(
        "/api/v1/careguard/dictionary/999999/audit", headers=_bearer(admin)
    )
    assert response.status_code == 404


# ===========================================================================
# Req 12.4 — Observability metrics: admin only + flag-gated (Req 9.5)
# ===========================================================================


def test_metrics_rejects_doctor_role(set_flags) -> None:
    set_flags(careguard_observability_enabled=True)
    response = client.get("/api/v1/careguard/metrics", headers=_minted("doctor"))
    assert response.status_code == 403


def test_metrics_rejects_normal_role(set_flags) -> None:
    set_flags(careguard_observability_enabled=True)
    response = client.get("/api/v1/careguard/metrics", headers=_minted("normal"))
    assert response.status_code == 403


def test_metrics_admin_404_when_flag_off() -> None:
    # Flag defaults off: the surface ships dark even for an admin.
    assert get_settings().careguard_observability_enabled is False
    response = client.get("/api/v1/careguard/metrics", headers=_minted("admin"))
    assert response.status_code == 404


def test_metrics_admin_admitted_when_flag_on(set_flags) -> None:
    set_flags(careguard_observability_enabled=True)
    response = client.get("/api/v1/careguard/metrics", headers=_minted("admin"))
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), dict)


# ===========================================================================
# Req 12.5 — CSRF on cookie-authenticated mutations
# ===========================================================================


def test_csrf_rejects_cookie_auth_mutation_without_token() -> None:
    """A cookie-authenticated mutation without a CSRF token is rejected (403).

    The global ``enforce_csrf_for_cookie_session`` middleware only checks for the
    presence of a session cookie (not its validity) before requiring a matching
    CSRF cookie+header, so a placeholder access cookie is enough to exercise the
    guard deterministically (mirrors the established compliance CSRF test).
    """

    settings = get_settings()
    if not settings.auth_csrf_enabled:
        # CSRF disabled in this environment — nothing to assert.
        return
    client.cookies.clear()
    client.cookies.set(settings.auth_cookie_access_name, "placeholder-session-cookie")
    try:
        response = client.post(
            "/api/v1/careguard/cabinet/items",
            json={"source": "manual", "drug_name": "Paracetamol"},
        )
    finally:
        client.cookies.clear()
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_csrf_rejects_cookie_auth_with_invalid_lowercase_bearer_header() -> None:
    """A junk Bearer header cannot disable cookie-session CSRF protection."""

    settings = get_settings()
    if not settings.auth_csrf_enabled:
        return
    client.cookies.clear()
    client.cookies.set(settings.auth_cookie_access_name, "placeholder-session-cookie")
    try:
        response = client.post(
            "/api/v1/careguard/cabinet/items",
            headers={"Authorization": "bearer junk"},
            json={"source": "manual", "drug_name": "Paracetamol"},
        )
    finally:
        client.cookies.clear()
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_csrf_rejects_cookie_auth_mutation_with_mismatched_token() -> None:
    settings = get_settings()
    if not settings.auth_csrf_enabled:
        return
    client.cookies.clear()
    client.cookies.set(settings.auth_cookie_access_name, "placeholder-session-cookie")
    client.cookies.set(settings.auth_csrf_cookie_name, "cookie-value")
    try:
        response = client.post(
            "/api/v1/careguard/cabinet/items",
            headers={settings.auth_csrf_header_name: "header-value-does-not-match"},
            json={"source": "manual", "drug_name": "Paracetamol"},
        )
    finally:
        client.cookies.clear()
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_csrf_allows_bearer_auth_mutation() -> None:
    """A Bearer-authenticated mutation bypasses CSRF (no browser cookie vector)."""

    token = _login_with_consent(_unique_email("csrf-bearer"))
    client.cookies.clear()  # ensure no session cookie influences the decision
    response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers=_bearer(token),
        json={"source": "manual", "drug_name": "Ibuprofen"},
    )
    assert response.status_code == 200, response.text
    # The created item is returned (proving the request was not CSRF-rejected).
    assert response.json()["normalized_name"] == "ibuprofen"


def test_csrf_allows_valid_lowercase_bearer_auth_mutation() -> None:
    """A valid lowercase Bearer scheme authenticates without cookie fallback."""

    token = _login_with_consent(_unique_email("csrf-lowercase-bearer"))
    client.cookies.clear()
    response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"bearer {token}"},
        json={"source": "manual", "drug_name": "Cetirizine"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["normalized_name"] == "cetirizine"


def test_csrf_allows_cookie_auth_mutation_with_matching_token() -> None:
    """A cookie session carrying a matching CSRF cookie+header is admitted."""

    settings = get_settings()
    client.cookies.clear()
    # Login populates the cookie jar with the access cookie AND (when CSRF is on)
    # the readable CSRF cookie.
    _login_with_consent(_unique_email("csrf-cookie"))
    request_headers: dict[str, str] = {}
    if settings.auth_csrf_enabled:
        csrf_value = client.cookies.get(settings.auth_csrf_cookie_name)
        assert csrf_value, "login should set a CSRF cookie when CSRF is enabled"
        request_headers[settings.auth_csrf_header_name] = csrf_value
    try:
        # No Authorization header => the request is authenticated by the session
        # cookie, so the CSRF guard applies and must pass with the matching token.
        response = client.post(
            "/api/v1/careguard/cabinet/items",
            headers=request_headers,
            json={"source": "manual", "drug_name": "Loratadine"},
        )
    finally:
        client.cookies.clear()
    assert response.status_code == 200, response.text
    assert response.json()["normalized_name"] == "loratadine"
