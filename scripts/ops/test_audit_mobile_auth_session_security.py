#!/usr/bin/env python3
"""Unit and regression tests for audit_mobile_auth_session_security.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from audit_mobile_auth_session_security import MobileAuthAuditor


@pytest.fixture
def repo_root() -> Path:
    """Returns the repository root path."""
    current = Path(__file__).resolve().parent.parent.parent
    return current


def test_auditor_runs_against_repo(repo_root: Path) -> None:
    auditor = MobileAuthAuditor(repo_root)
    findings = auditor.audit_all()
    assert isinstance(findings, list)
    rule_ids = {f.rule_id for f in findings}
    assert "MOB-AUTH-03" in rule_ids
    assert "MOB-STORAGE-01" in rule_ids
    assert "MOB-LOG-01" in rule_ids


def test_auditor_detects_clean_fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # 1. apps/mobile/lib/core/api_client.dart
        client_dir = root / "apps/mobile/lib/core"
        client_dir.mkdir(parents=True)
        (client_dir / "api_client.dart").write_text(
            """
            Future<String?> _attemptRefresh() {
              final existing = _refreshInFlight;
              if (existing != null) return existing;
              final future = _doRefresh();
              _refreshInFlight = future;
              return future;
            }
            Future<String?> _doRefresh() async {
              try {
                final res = await _httpClient.post(Uri.parse('/auth/refresh'));
                if (res.statusCode == 401) {
                  await hooks.onSessionCleared();
                }
              } catch (_) {
                // Keep session on network error
              }
              return null;
            }
            """,
            encoding="utf-8",
        )

        # 2. apps/mobile/lib/core/session_store.dart
        (client_dir / "session_store.dart").write_text(
            """
            class FlutterSecureSessionStorage implements SessionSecureStorage {
              FlutterSecureSessionStorage([FlutterSecureStorage? storage])
                  : _storage = storage ?? const FlutterSecureStorage(
                      aOptions: AndroidOptions(encryptedSharedPreferences: true, resetOnError: true),
                      iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device),
                    );
            }
            Future<void> hydrate() async {
              if (isExpired && isRefreshExpired) {
                await clear();
              }
            }
            Future<void> setSession({required String email}) async {
              if (_email != email) {
                await _purgeOfflineCaches();
              }
            }
            """,
            encoding="utf-8",
        )

        # 3. AndroidManifest.xml
        manifest_dir = root / "apps/mobile/android/app/src/main"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "AndroidManifest.xml").write_text(
            """<manifest><application android:allowBackup="false"></application></manifest>""",
            encoding="utf-8",
        )

        # 4. analytics.dart
        (client_dir / "analytics.dart").write_text(
            """
            const Set<String> _deniedExactKeys = <String>{'token', 'password', 'email'};
            const Set<String> _deniedSubstrings = <String>{'token', 'bearer', 'refreshtoken', 'accesstoken', 'secret', 'auth', 'authorization', 'password'};
            """,
            encoding="utf-8",
        )

        # 5. services/api/src/clara_api/api/v1/endpoints/auth.py
        srv_api_dir = root / "services/api/src/clara_api/api/v1/endpoints"
        srv_api_dir.mkdir(parents=True)
        (srv_api_dir / "auth.py").write_text(
            """
            if session_security.is_refresh_reused(candidate_jti):
                session_security.record_reuse(candidate_jti)
            rotated_refresh, _ = session_security.rotate_refresh(old_jti, email, role)
            """,
            encoding="utf-8",
        )

        # 6. services/api/src/clara_api/core/session_security.py
        srv_core_dir = root / "services/api/src/clara_api/core"
        srv_core_dir.mkdir(parents=True)
        (srv_core_dir / "session_security.py").write_text(
            """
            def revoke_token_family(self, family_id: str) -> None:
                pass
            """,
            encoding="utf-8",
        )

        auditor = MobileAuthAuditor(root)
        findings = auditor.audit_all()
        assert len(findings) == 0, f"Expected clean run, got findings: {findings}"


def test_auditor_detects_flawed_fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # Missing coalescing, missing allowBackup="false", missing token keys in analytics
        client_dir = root / "apps/mobile/lib/core"
        client_dir.mkdir(parents=True)
        (client_dir / "api_client.dart").write_text(
            """
            Future<String?> _doRefresh() async {
              try {
                // do post
              } catch (_) {
                await hooks.onSessionCleared();
              }
            }
            """,
            encoding="utf-8",
        )

        (client_dir / "session_store.dart").write_text(
            """
            class FlutterSecureSessionStorage {
              FlutterSecureSessionStorage();
            }
            Future<void> hydrate() async {
              if (isExpired) {
                await clear();
              }
            }
            Future<void> setSession() async {
              if (_email != null || _accessToken != null) {
                await _purgeOfflineCaches();
              }
            }
            """,
            encoding="utf-8",
        )

        manifest_dir = root / "apps/mobile/android/app/src/main"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "AndroidManifest.xml").write_text(
            """<manifest><application android:label="App"></application></manifest>""",
            encoding="utf-8",
        )

        (client_dir / "analytics.dart").write_text(
            """
            const Set<String> _deniedExactKeys = <String>{'email', 'password'};
            const Set<String> _deniedSubstrings = <String>{'email', 'password'};
            """,
            encoding="utf-8",
        )

        srv_api_dir = root / "services/api/src/clara_api/api/v1/endpoints"
        srv_api_dir.mkdir(parents=True)
        (srv_api_dir / "auth.py").write_text(
            """def refresh(): pass""",
            encoding="utf-8",
        )

        srv_core_dir = root / "services/api/src/clara_api/core"
        srv_core_dir.mkdir(parents=True)
        (srv_core_dir / "session_security.py").write_text(
            """class SessionSecurity: pass""",
            encoding="utf-8",
        )

        auditor = MobileAuthAuditor(root)
        findings = auditor.audit_all()
        rule_ids = {f.rule_id for f in findings}

        assert "MOB-AUTH-01" in rule_ids
        assert "MOB-AUTH-02" in rule_ids
        assert "MOB-AUTH-03" in rule_ids
        assert "MOB-AUTH-04" in rule_ids
        assert "MOB-STORAGE-01" in rule_ids
        assert "MOB-STORAGE-02" in rule_ids
        assert "MOB-LOG-01" in rule_ids
        assert "SRV-AUTH-01" in rule_ids
