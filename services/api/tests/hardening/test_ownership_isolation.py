"""Cross-user owner-isolation coverage for client-supplied resource identifiers.

Feature: clara-platform-hardening — Epic 5 (Input validation & request limits),
task 5.3 ("Reaffirm ownership checks on client-supplied identifiers").

Requirement 4.4 requires that, where a request carries a client-controlled
resource identifier, the platform enforces that the authenticated subject owns
the referenced resource. This module is the focused, example-style reaffirmation
of that invariant for a representative set of owner-scoped surfaces that accept a
client-supplied id in the path:

* **Workspace folders** — ``/workspace/folders/{folder_id}`` (PATCH, DELETE)
* **Research knowledge sources** — ``/research/knowledge-sources/{source_id}``
  (PATCH, DELETE) and ``/research/knowledge-sources/{source_id}/documents`` (GET)
* **Council cases** — ``/council/cases/{case_id}`` (GET, PATCH)

For each surface the test provisions two **distinct users holding the same
role** (so the ``require_roles`` gate is satisfied for both and the *only*
difference is ownership), has user A create a resource, and asserts that user B
— presenting a genuine, sufficiently-privileged credential — cannot read or
mutate A's resource. The owner-isolation guard collapses a non-owned id to
"not found", so the expected rejection is **404** (or **403** for any surface
that chooses to distinguish forbidden from missing); both are accepted.

Each case also asserts the **positive control**: the owner (user A) *can* access
the same resource. That proves the cross-user rejection stems from the ownership
check rather than from the resource simply not existing, and that the check is
not over-broad (it does not lock the legitimate owner out).

The suite reuses the Epic-12 hardening harness (the in-process ``TestClient``,
the rate-limit relaxation and flags-off-baseline autouse fixtures, and the real
auto-provisioning login flow) so no new control path or fixture is introduced,
and it runs with every ``HARDENING_*`` flag off (Requirement 11.2). All requests
use bearer tokens, which are CSRF-exempt as today, so mutations need no CSRF
token.

**Validates: Requirements 4.4**
"""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from . import LOGIN_PASSWORD, bearer_headers, login_token

# Cross-user access to a resource the caller does not own must be denied. The
# owner-isolation guards filter by ``user_id``/``owner_user_id`` and raise
# 404 (not-found) for a non-owned id; a surface that instead distinguishes
# forbidden is equally acceptable, so both are treated as a correct denial.
_DENIED = frozenset({status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})

# Distinct same-role user pairs. Both addresses in a pair infer the same role
# (see ``auth._infer_role_from_email``) so the role gate passes for each and the
# only distinguishing factor is resource ownership.
_NORMAL_OWNER = "owner-a@patient.clara"  # -> normal
_NORMAL_OTHER = "owner-b@patient.clara"  # -> normal
_DOCTOR_OWNER = "owner-a@doctor.clara"  # -> doctor
_DOCTOR_OTHER = "owner-b@doctor.clara"  # -> doctor


def _token_for(client: TestClient, email: str) -> str:
    """Mint a genuine bearer token for ``email`` via the real login flow."""

    token, _role = login_token(client, email=email, password=LOGIN_PASSWORD)
    return token


def _assert_denied(response, *, surface: str) -> None:
    assert response.status_code in _DENIED, (
        f"{surface}: cross-user access must be denied with 403/404, "
        f"got {response.status_code} ({response.text})"
    )


# ---------------------------------------------------------------------------
# Workspace folders (any authenticated user; client-supplied folder_id)
# ---------------------------------------------------------------------------


def test_workspace_folder_owner_isolation(client: TestClient) -> None:
    owner = bearer_headers(_token_for(client, _NORMAL_OWNER))
    other = bearer_headers(_token_for(client, _NORMAL_OTHER))

    created = client.post(
        "/api/v1/workspace/folders",
        headers=owner,
        json={"name": "Owner Folder", "description": "private"},
    )
    assert created.status_code == status.HTTP_200_OK, created.text
    folder_id = created.json()["id"]

    # User B cannot mutate or delete user A's folder.
    _assert_denied(
        client.patch(
            f"/api/v1/workspace/folders/{folder_id}",
            headers=other,
            json={"name": "Hijacked"},
        ),
        surface="PATCH /workspace/folders/{id}",
    )
    _assert_denied(
        client.delete(f"/api/v1/workspace/folders/{folder_id}", headers=other),
        surface="DELETE /workspace/folders/{id}",
    )

    # Positive control: the owner can still update its own folder.
    owner_update = client.patch(
        f"/api/v1/workspace/folders/{folder_id}",
        headers=owner,
        json={"name": "Renamed By Owner"},
    )
    assert owner_update.status_code == status.HTTP_200_OK, owner_update.text


# ---------------------------------------------------------------------------
# Research knowledge sources (normal+; client-supplied source_id)
# ---------------------------------------------------------------------------


def test_knowledge_source_owner_isolation(client: TestClient) -> None:
    owner = bearer_headers(_token_for(client, _NORMAL_OWNER))
    other = bearer_headers(_token_for(client, _NORMAL_OTHER))

    created = client.post(
        "/api/v1/research/knowledge-sources",
        headers=owner,
        json={"name": "Owner Source", "description": "private"},
    )
    assert created.status_code == status.HTTP_200_OK, created.text
    source_id = created.json()["id"]

    # User B cannot read documents under, mutate, or delete user A's source.
    _assert_denied(
        client.get(
            f"/api/v1/research/knowledge-sources/{source_id}/documents",
            headers=other,
        ),
        surface="GET /research/knowledge-sources/{id}/documents",
    )
    _assert_denied(
        client.patch(
            f"/api/v1/research/knowledge-sources/{source_id}",
            headers=other,
            json={"name": "Hijacked"},
        ),
        surface="PATCH /research/knowledge-sources/{id}",
    )
    _assert_denied(
        client.delete(
            f"/api/v1/research/knowledge-sources/{source_id}", headers=other
        ),
        surface="DELETE /research/knowledge-sources/{id}",
    )

    # Positive control: the owner can list its own source's documents.
    owner_docs = client.get(
        f"/api/v1/research/knowledge-sources/{source_id}/documents",
        headers=owner,
    )
    assert owner_docs.status_code == status.HTTP_200_OK, owner_docs.text


# ---------------------------------------------------------------------------
# Council cases (doctor+; client-supplied case_id)
# ---------------------------------------------------------------------------


def test_council_case_owner_isolation(client: TestClient) -> None:
    owner = bearer_headers(_token_for(client, _DOCTOR_OWNER))
    other = bearer_headers(_token_for(client, _DOCTOR_OTHER))

    created = client.post(
        "/api/v1/council/cases",
        headers=owner,
        json={"title": "Owner Case"},
    )
    assert created.status_code == status.HTTP_200_OK, created.text
    case_id = created.json()["id"]

    # A second doctor (role gate passes) still cannot read or mutate A's case.
    _assert_denied(
        client.get(f"/api/v1/council/cases/{case_id}", headers=other),
        surface="GET /council/cases/{id}",
    )
    _assert_denied(
        client.patch(
            f"/api/v1/council/cases/{case_id}",
            headers=other,
            json={"title": "Hijacked"},
        ),
        surface="PATCH /council/cases/{id}",
    )

    # Positive control: the owner can read its own case.
    owner_read = client.get(f"/api/v1/council/cases/{case_id}", headers=owner)
    assert owner_read.status_code == status.HTTP_200_OK, owner_read.text


# ---------------------------------------------------------------------------
# Sanity: the two users in each pair are genuinely distinct subjects
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email_a,email_b",
    [
        (_NORMAL_OWNER, _NORMAL_OTHER),
        (_DOCTOR_OWNER, _DOCTOR_OTHER),
    ],
)
def test_user_pairs_are_distinct(
    client: TestClient, email_a: str, email_b: str
) -> None:
    token_a = _token_for(client, email_a)
    token_b = _token_for(client, email_b)
    assert token_a != token_b, "expected two distinct subjects' tokens to differ"
