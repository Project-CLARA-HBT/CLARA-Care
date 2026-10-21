#!/usr/bin/env python3
"""Mobile Authentication, Refresh Rotation & Session Persistence Security Auditor.

Audit tool for CLARA Mobile and API auth contracts:
  - Token refresh rotation and reuse prevention (RFC 6749 §10.4, OWASP MASVS-AUTH-1)
  - Secure storage architecture and backup exposure (OWASP MASVS-STORAGE-1/2)
  - Token leak risks in logging, analytics, and telemetry (OWASP MASVS-CODE-2)
  - Server-side rotation verification and session lifecycle contracts

Usage:
  python3 scripts/ops/audit_mobile_auth_session_security.py [--repo-root .] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    rule_id: str
    title: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: str  # REFRESH_ROTATION, SECURE_STORAGE, LOGGING_LEAK, SERVER_CONTRACT
    file_path: str
    line_number: int | None
    code_anchor: str
    description: str
    impact: str
    remediation: str


class MobileAuthAuditor:
    """Static and architectural security auditor for CLARA Mobile auth subsystems."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.findings: list[Finding] = []

    def audit_all(self) -> list[Finding]:
        self.findings.clear()
        self._audit_refresh_rotation()
        self._audit_session_hydration()
        self._audit_cache_purge_behavior()
        self._audit_android_backup_config()
        self._audit_secure_storage_options()
        self._audit_analytics_pii_denylist()
        self._audit_logging_hygiene()
        self._audit_public_share_links()
        self._audit_server_session_security()
        return self.findings

    def _audit_refresh_rotation(self) -> None:
        client_file = self.repo_root / "apps/mobile/lib/core/api_client.dart"
        if not client_file.exists():
            return

        content = client_file.read_text(encoding="utf-8")

        # 1. Check refresh coalescing
        if "_refreshInFlight" not in content or "_attemptRefresh" not in content:
            self.findings.append(
                Finding(
                    rule_id="MOB-AUTH-01",
                    title="Missing Concurrent Token Refresh Coalescing",
                    severity="HIGH",
                    category="REFRESH_ROTATION",
                    file_path="apps/mobile/lib/core/api_client.dart",
                    line_number=None,
                    code_anchor="_attemptRefresh",
                    description="Concurrent authenticated requests may race and execute parallel refresh calls.",
                    impact="Race condition triggering server reuse detection and session revocation.",
                    remediation="Maintain single in-flight refresh Future for coalesced execution.",
                )
            )

        # 2. Check transient error handling in _doRefresh
        if "_doRefresh" in content and re.search(r"catch\s*\([^)]*\)\s*\{[^}]*onSessionCleared", content, re.DOTALL):
            do_refresh_pos = content.find("_doRefresh")
            line_no = content[:do_refresh_pos].count("\n") + 1 if do_refresh_pos != -1 else None
            self.findings.append(
                Finding(
                    rule_id="MOB-AUTH-02",
                    title="Session Wiped on Transient Network Failure During Refresh",
                    severity="MEDIUM",
                    category="REFRESH_ROTATION",
                    file_path="apps/mobile/lib/core/api_client.dart",
                    line_number=line_no,
                    code_anchor="_doRefresh() catch block",
                    description="Transient socket timeout or offline disconnect during refresh immediately clears user credentials.",
                    impact="Poor user resilience: user forced to re-login on flaky network connections.",
                    remediation="Distinguish network/transport exceptions from 401/403 responses. Only clear session on terminal auth rejections.",
                )
            )

    def _audit_session_hydration(self) -> None:
        store_file = self.repo_root / "apps/mobile/lib/core/session_store.dart"
        if not store_file.exists():
            return

        content = store_file.read_text(encoding="utf-8")

        # Check hydrate method logic
        if re.search(r"hydrate\s*\([^)]*\)\s*async\s*\{.*?if\s*\(\s*isExpired\s*\).*?clear\(\)", content, re.DOTALL):
            hydrate_pos = content.find("hydrate()")
            line_no = content[:hydrate_pos].count("\n") + 1 if hydrate_pos != -1 else None
            self.findings.append(
                Finding(
                    rule_id="MOB-AUTH-03",
                    title="Premature Session Eviction on Launch Without Refresh Attempt",
                    severity="HIGH",
                    category="REFRESH_ROTATION",
                    file_path="apps/mobile/lib/core/session_store.dart",
                    line_number=line_no,
                    code_anchor="hydrate() -> if (isExpired) await clear();",
                    description="On cold start, if the access token has expired, hydrate() clears all stored credentials, discarding the valid refresh token without attempting an exchange.",
                    impact="User session does not survive beyond access token lifetime (15-30m) across app restarts, undermining mobile session persistence.",
                    remediation="Preserve valid refresh tokens during hydrate, or trigger background refresh before evicting the session.",
                )
            )

    def _audit_cache_purge_behavior(self) -> None:
        store_file = self.repo_root / "apps/mobile/lib/core/session_store.dart"
        if not store_file.exists():
            return

        content = store_file.read_text(encoding="utf-8")
        if re.search(r"setSession\s*\(.*?_purgeOfflineCaches", content, re.DOTALL):
            if re.search(r"if\s*\(\s*_email\s*!=\s*null\s*\|\|\s*_accessToken\s*!=\s*null\s*\)\s*\{?\s*(?:await\s+)?_purgeOfflineCaches", content, re.DOTALL):
                set_session_pos = content.find("setSession")
                line_no = content[:set_session_pos].count("\n") + 1 if set_session_pos != -1 else None
                self.findings.append(
                    Finding(
                        rule_id="MOB-AUTH-04",
                        title="Offline Cache Evicted on In-Session Token Refresh",
                        severity="MEDIUM",
                        category="REFRESH_ROTATION",
                        file_path="apps/mobile/lib/core/session_store.dart",
                        line_number=line_no,
                        code_anchor="setSession() -> _purgeOfflineCaches",
                        description="setSession() calls _purgeOfflineCaches() whenever _email or _accessToken is non-null, erasing cached medical projections during routine token rotations for the same user.",
                        impact="Loss of offline CareGuard and LifeMap data whenever access token is rotated in-flight.",
                        remediation="Only purge caches if the new email or tokenSubject differs from the previous user identity.",
                    )
                )

    def _audit_android_backup_config(self) -> None:
        manifest_file = self.repo_root / "apps/mobile/android/app/src/main/AndroidManifest.xml"
        if not manifest_file.exists():
            return

        content = manifest_file.read_text(encoding="utf-8")
        app_match = re.search(r"<application\b([^>]*)>", content, re.DOTALL)
        if app_match:
            attrs = app_match.group(1)
            line_no = content[: app_match.start()].count("\n") + 1
            if 'android:allowBackup="false"' not in attrs:
                self.findings.append(
                    Finding(
                        rule_id="MOB-STORAGE-01",
                        title="Android Auto-Backup Exposure for Sensitive App Data",
                        severity="HIGH",
                        category="SECURE_STORAGE",
                        file_path="apps/mobile/android/app/src/main/AndroidManifest.xml",
                        line_number=line_no,
                        code_anchor="<application ...>",
                        description="AndroidManifest.xml omits android:allowBackup=\"false\", defaulting to true. This permits extraction of app data via adb backup and Google Cloud Backup.",
                        impact="Potential extraction of cached medical information and shared preferences on unencrypted backups.",
                        remediation="Explicitly set android:allowBackup=\"false\" in AndroidManifest.xml and configure dataExtractionRules.",
                    )
                )

    def _audit_secure_storage_options(self) -> None:
        store_file = self.repo_root / "apps/mobile/lib/core/session_store.dart"
        if not store_file.exists():
            return

        content = store_file.read_text(encoding="utf-8")
        if "FlutterSecureSessionStorage" in content:
            if "AndroidOptions" not in content or "encryptedSharedPreferences" not in content:
                pos = content.find("class FlutterSecureSessionStorage")
                line_no = content[:pos].count("\n") + 1 if pos != -1 else None
                self.findings.append(
                    Finding(
                        rule_id="MOB-STORAGE-02",
                        title="FlutterSecureStorage Omits Hardened Android/iOS Options",
                        severity="MEDIUM",
                        category="SECURE_STORAGE",
                        file_path="apps/mobile/lib/core/session_store.dart",
                        line_number=line_no,
                        code_anchor="FlutterSecureSessionStorage constructor",
                        description="FlutterSecureStorage is instantiated with default options, lacking AndroidOptions(encryptedSharedPreferences: true, resetOnError: true) and iOS KeychainAccessibility controls.",
                        impact="Risk of unhandled KeyStore corruption crashes on Android OEM updates, and suboptimal keychain accessibility boundaries on iOS.",
                        remediation="Configure AndroidOptions(encryptedSharedPreferences: true, resetOnError: true) and IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device).",
                    )
                )

    def _audit_analytics_pii_denylist(self) -> None:
        analytics_file = self.repo_root / "apps/mobile/lib/core/analytics.dart"
        if not analytics_file.exists():
            return

        content = analytics_file.read_text(encoding="utf-8")
        line_no = 286

        # Check for token denylist in _deniedExactKeys and _deniedSubstrings
        keys_match = re.search(r"const Set<String>\s+_deniedExactKeys\s*=\s*<String>\{(.*?)\};", content, re.DOTALL)
        subs_match = re.search(r"const Set<String>\s+_deniedSubstrings\s*=\s*<String>\{(.*?)\};", content, re.DOTALL)

        keys_text = keys_match.group(1) if keys_match else ""
        subs_text = subs_match.group(1) if subs_match else ""

        token_terms = {"token", "refreshtoken", "accesstoken", "bearer", "secret", "authorization"}
        missing_terms = [t for t in token_terms if f"'{t}'" not in keys_text and f"'{t}'" not in subs_text]

        if missing_terms:
            self.findings.append(
                Finding(
                    rule_id="MOB-LOG-01",
                    title="Analytics PII Denylist Missing Bearer Token Key Filters",
                    severity="HIGH",
                    category="LOGGING_LEAK",
                    file_path="apps/mobile/lib/core/analytics.dart",
                    line_number=line_no,
                    code_anchor="_deniedExactKeys / _deniedSubstrings",
                    description=f"Analytics property sanitization lacks token-specific redaction keywords: {', '.join(missing_terms)}.",
                    impact="Accidental inclusion of token attributes in custom event payloads would be transmitted to external analytics providers.",
                    remediation="Add 'token', 'accesstoken', 'refreshtoken', 'bearer', 'secret', and 'auth' to _deniedSubstrings and _deniedExactKeys.",
                )
            )

    def _audit_logging_hygiene(self) -> None:
        mobile_lib = self.repo_root / "apps/mobile/lib"
        if not mobile_lib.exists():
            return

        # Scan for raw prints in mobile production code
        print_regex = re.compile(r"\bprint\s*\([^)]*\)", re.MULTILINE)
        debug_print_regex = re.compile(r"\bdebugPrint\s*\([^)]*\)", re.MULTILINE)

        found_prints: list[str] = []
        for dart_file in mobile_lib.rglob("*.dart"):
            text = dart_file.read_text(encoding="utf-8")
            if print_regex.search(text) or debug_print_regex.search(text):
                found_prints.append(str(dart_file.relative_to(self.repo_root)))

        if found_prints:
            self.findings.append(
                Finding(
                    rule_id="MOB-LOG-02",
                    title="Unstructured Console Logging Detected in Mobile Library",
                    severity="LOW",
                    category="LOGGING_LEAK",
                    file_path=found_prints[0],
                    line_number=None,
                    code_anchor="print / debugPrint",
                    description=f"Direct print or debugPrint statements detected in: {', '.join(found_prints)}.",
                    impact="Console logs on Android Logcat and iOS syslog may expose internal application state.",
                    remediation="Use structured, PII-sanitized logger or remove raw print statements.",
                )
            )

    def _audit_public_share_links(self) -> None:
        share_file = self.repo_root / "apps/mobile/lib/core/public_share_link.dart"
        if not share_file.exists():
            return

        content = share_file.read_text(encoding="utf-8")
        # Ensure deep link tokens are bounded and memory-only
        if "phrShareTokenFromLink" in content:
            if "length > 512" not in content or "https" not in content.lower():
                self.findings.append(
                    Finding(
                        rule_id="MOB-LOG-03",
                        title="Unbounded or Insecure Public Share Link Parsing",
                        severity="MEDIUM",
                        category="LOGGING_LEAK",
                        file_path="apps/mobile/lib/core/public_share_link.dart",
                        line_number=45,
                        code_anchor="phrShareTokenFromLink",
                        description="Public share token parser does not enforce strict HTTPS scheme or token length bounding.",
                        impact="Malformed intents may cause unhandled exceptions or URL injection.",
                        remediation="Ensure strict HTTPS, domain whitelist, and length <= 512 characters.",
                    )
                )

    def _audit_server_session_security(self) -> None:
        auth_file = self.repo_root / "services/api/src/clara_api/api/v1/endpoints/auth.py"
        session_sec_file = self.repo_root / "services/api/src/clara_api/core/session_security.py"

        if not auth_file.exists() or not session_sec_file.exists():
            return

        auth_content = auth_file.read_text(encoding="utf-8")
        sec_content = session_sec_file.read_text(encoding="utf-8")

        # Check server reuse detection and rotation
        if "is_refresh_reused" not in auth_content or "rotate_refresh" not in auth_content:
            self.findings.append(
                Finding(
                    rule_id="SRV-AUTH-01",
                    title="Server Lacks Refresh Rotation or Reuse Detection Wiring",
                    severity="CRITICAL",
                    category="SERVER_CONTRACT",
                    file_path="services/api/src/clara_api/api/v1/endpoints/auth.py",
                    line_number=765,
                    code_anchor="refresh_token endpoint",
                    description="Server auth endpoint does not invoke session_security.is_refresh_reused or rotate_refresh.",
                    impact="Refresh tokens can be replayed indefinitely without detection.",
                    remediation="Integrate session_security.is_refresh_reused and rotate_refresh in POST /refresh.",
                )
            )

        # Check family revocation RFC 6749 §10.4
        if "record_reuse" in auth_content and "revoke_token_family" not in sec_content:
            self.findings.append(
                Finding(
                    rule_id="SRV-AUTH-02",
                    title="Incomplete Token Family Revocation on Replay Detection",
                    severity="MEDIUM",
                    category="SERVER_CONTRACT",
                    file_path="services/api/src/clara_api/core/session_security.py",
                    line_number=161,
                    code_anchor="record_reuse()",
                    description="When a replayed refresh token is detected, the server rejects the request and increments a counter, but does not invalidate the legitimate descendant token issued during the initial rotation.",
                    impact="Breach of RFC 6749 §10.4 token family revocation recommendation: compromised session remains active for the holder of the rotated token.",
                    remediation="Implement family-wide token revocation tying rotated descendants to parent lineage marker.",
                )
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit CLARA Mobile Auth & Session Persistence Security.")
    parser.add_argument("--repo-root", default=".", help="Repository root path (default: .)")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    parser.add_argument("--severity-threshold", default="LOW", choices=["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"])
    parser.add_argument("--fail-on-findings", action="store_true", help="Exit with code 1 if findings exceed threshold")

    args = parser.parse_args()
    repo_root = Path(args.repo_root)

    auditor = MobileAuthAuditor(repo_root)
    findings = auditor.audit_all()

    severity_order = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    threshold = severity_order[args.severity_threshold]

    filtered_findings = [f for f in findings if severity_order[f.severity] >= threshold]

    if args.json:
        output = {
            "auditor": "MobileAuthAuditor",
            "repo_root": str(repo_root.resolve()),
            "total_findings": len(findings),
            "filtered_findings_count": len(filtered_findings),
            "findings": [asdict(f) for f in filtered_findings],
        }
        print(json.dumps(output, indent=2))
    else:
        print("=" * 80)
        print("CLARA MOBILE AUTH, REFRESH ROTATION & SESSION PERSISTENCE SECURITY AUDIT")
        print("=" * 80)
        print(f"Repository Root: {repo_root.resolve()}")
        print(f"Total Findings Detected: {len(findings)} (Filtered by >={args.severity_threshold}: {len(filtered_findings)})")
        print("=" * 80)

        for idx, f in enumerate(filtered_findings, 1):
            print(f"[{idx}] {f.rule_id}: {f.title} ({f.severity})")
            print(f"    Category:     {f.category}")
            print(f"    Location:     {f.file_path}:{f.line_number or 'N/A'}")
            print(f"    Code Anchor:  {f.code_anchor}")
            print(f"    Description:  {f.description}")
            print(f"    Impact:       {f.impact}")
            print(f"    Remediation:  {f.remediation}")
            print("-" * 80)

    if args.fail_on_findings and any(severity_order[f.severity] >= severity_order["HIGH"] for f in filtered_findings):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
