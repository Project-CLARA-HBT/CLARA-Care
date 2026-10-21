#!/usr/bin/env python3
"""Deterministic Red-Team Manifest Checker for Subagent Deliverables.

Audits subagent deliverables across phases for:
1. Simulated / fake test results (empty test suites, mocked success, mismatched exit codes).
2. Hardcoded credentials & secrets (API keys, bearer tokens, private keys, live JWTs).
3. PHI / PII leakage (patient identity numbers, Vietnamese phone numbers, personal emails).
4. Bypassed safety invariants (RBAC, CSRF, consent gate, emergency fast-path, FIDES critical drug check, legal hard-guards, no-PII telemetry).
5. Git commit integrity & signature verification (commit existence in object DB, valid formatting, signature status, SHA consistency).
6. Deliverable manifest integrity & path lane boundary conformance.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

# ==============================================================================
# Security & Red-Team Audit Patterns
# ==============================================================================

# Credential patterns
RE_SK_TOKEN = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
RE_API_KEY_ASSIGN = re.compile(
    r"(?i)\b(?:ROUTER|OPENAI|ANTHROPIC|CLARA|AWS|DEEPSEEK)_API_KEY\s*[:=]\s*"
    r"['\"]?(?!(?:\[REDACTED\]|<REDACTED>|<REDACTED_API_KEY>|\[REDACTED_API_KEY\]|\"\"|''|\$\{|\bNone\b|\bnull\b))[A-Za-z0-9_-]{16,}['\"]?"
)
RE_BEARER_TOKEN = re.compile(
    r"(?i)Authorization\s*:\s*Bearer\s+(?!(?:\[REDACTED\]|<REDACTED>|<REDACTED_API_KEY>|\[REDACTED_API_KEY\]|\$\{|\bNone\b|\bnull\b))[A-Za-z0-9_.-]{24,}"
)
RE_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
RE_LIVE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b")

# PHI / PII patterns
RE_VN_PHONE = re.compile(r"(?<!\d)(?:\+84|0)(?:3[2-9]|5[25689]|7[06-9]|8[1-9]|9[0-9])[0-9]{7}(?!\d)")
RE_PATIENT_NATIONAL_ID = re.compile(
    r"(?i)\b(?:patient[_-]?id|so[_-]?cccd|cmnd|cccd|benh[_-]?nhan|patient[_-]?ssn)\s*[:=]\s*(\d{9}|\d{12})\b"
)
RE_PERSONAL_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_UNREDACTED_PATIENT_RECORD = re.compile(
    r"(?i)\bpatient\s+(?:diagnosed\s+with|prescribed|admitted|tested\s+positive\s+for)\s+[A-Za-z0-9\s]{3,30}\b"
)

# Allowed email domains for tests and maintainers
ALLOWED_EMAIL_DOMAINS = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "claracare.vn",
        "claracare.internal",
    }
)

# Allowed mock keywords only when in explicit test assertion or doc context
SUSPICIOUS_TEST_FAKES = (
    re.compile(r"(?i)\bMOCK_ALL_TESTS\s*=\s*True\b"),
    re.compile(r"(?i)\bsimulate(?:d)?_pass\s*=\s*true\b"),
    re.compile(r"(?i)\bmocked_success\s*=\s*true\b"),
    re.compile(r"(?i)\bfake_receipt\s*=\s*true\b"),
    re.compile(r"(?i)\bpytest\s+--skip-all\b"),
    re.compile(r"(?i)\bassert\s+True\s*#\s*fake\b"),
    re.compile(r"(?i)\breturn\s+True\s*#\s*mock\b"),
    re.compile(r"(?i)\bdef\s+test_fake_\w+\(\):\s*pass\b"),
)

# Safety Invariant Bypass Patterns
SAFETY_BYPASS_PATTERNS = (
    ("RBAC", re.compile(r"(?i)\b(?:disable|bypass|skip)_rbac\b|\brbac_(?:disabled|bypassed|skipped)\b")),
    ("CSRF", re.compile(r"(?i)\b(?:disable|bypass|skip)_csrf\b|\bcsrf_(?:disabled|bypassed|skipped)\b")),
    ("CONSENT", re.compile(r"(?i)\b(?:disable|bypass|skip)_consent\b|\bconsent_(?:disabled|bypassed|skipped)\b")),
    (
        "EMERGENCY",
        re.compile(
            r"(?i)\b(?:disable|bypass|skip)_(?:emergency|fastpath)\b|\b(?:emergency|fastpath)_(?:disabled|bypassed|skipped)\b"
        ),
    ),
    (
        "FIDES",
        re.compile(
            r"(?i)\b(?:disable|bypass|skip)_fides\b|\bfides_(?:disabled|bypassed|skipped)\b|\ballow_critical_dosage\b"
        ),
    ),
    (
        "LEGAL_GUARD",
        re.compile(
            r"(?i)\b(?:disable|bypass|skip)_legal(?:_guard)?\b|\blegal(?:_guard)?_(?:disabled|bypassed|skipped)\b|\ballow_prescription_intent\b"
        ),
    ),
    (
        "NO_PII_TELEMETRY",
        re.compile(
            r"(?i)\bmetrics_allow_pii\b|\bdisable_pii_filter\b|\bskip_pii_redaction\b"
        ),
    ),
)


@dataclass
class AuditFinding:
    category: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"
    agent_id: str
    phase: str
    file_path: str
    rule: str
    message: str
    line_number: int | None = None
    snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RedTeamManifestChecker:
    """Deterministic red-team auditor for subagent deliverables."""

    def __init__(self, repo_root: Path | None = None, strict: bool = False) -> None:
        if repo_root is None:
            # Default to git root or 2 levels up from script
            repo_root = Path(__file__).resolve().parent.parent.parent
        self.repo_root = repo_root.resolve()
        self.strict = strict
        self.findings: list[AuditFinding] = []

    def _rel_path(self, path: Path) -> str:
        """Safely convert path to repo-relative string, falling back to absolute if outside."""
        try:
            return str(path.resolve().relative_to(self.repo_root))
        except ValueError:
            return str(path.resolve())

    def _add_finding(
        self,
        category: str,
        severity: str,
        agent_id: str,
        phase: str,
        file_path: str,
        rule: str,
        message: str,
        line_number: int | None = None,
        snippet: str | None = None,
    ) -> None:
        self.findings.append(
            AuditFinding(
                category=category,
                severity=severity,
                agent_id=agent_id,
                phase=phase,
                file_path=file_path,
                rule=rule,
                message=message,
                line_number=line_number,
                snippet=snippet,
            )
        )

    def verify_commit_integrity(
        self,
        manifest_data: dict[str, Any],
        manifest_path: Path,
        agent_id: str,
        phase: str,
    ) -> None:
        """Verify existence and cryptographic signatures of referenced git commits."""
        commit_keys = [
            "frozen_head_sha",
            "verified_head_sha",
            "base_sha",
            "commit",
            "commit_sha",
            "handoff_commit",
        ]
        shas: list[tuple[str, str]] = []
        for k in commit_keys:
            v = manifest_data.get(k)
            if v and isinstance(v, str):
                shas.append((k, v.strip()))

        # If integration agents list exists
        if "agents" in manifest_data and isinstance(manifest_data["agents"], list):
            for a in manifest_data["agents"]:
                if isinstance(a, dict) and "commit" in a and a["commit"]:
                    shas.append((f"agent_{a.get('agent_id')}_commit", str(a["commit"]).strip()))

        for key_name, sha in shas:
            # 1. Format check
            if not re.match(r"^[0-9a-fA-F]{7,40}$", sha):
                self._add_finding(
                    category="COMMIT_INTEGRITY",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=self._rel_path(manifest_path),
                    rule="invalid_commit_sha_format",
                    message=f"Commit SHA '{sha}' under '{key_name}' is not a valid 7-40 hex hash.",
                )
                continue

            # 2. Existence check in git object DB
            res = subprocess.run(
                ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                cwd=self.repo_root,
                capture_output=True,
            )
            if res.returncode != 0:
                self._add_finding(
                    category="COMMIT_INTEGRITY",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=self._rel_path(manifest_path),
                    rule="commit_not_found",
                    message=(
                        f"Commit '{sha}' under '{key_name}' does not exist in git object database "
                        f"(simulated or fabricated commit SHA)."
                    ),
                )
                continue

            # 3. Signature verification
            sig_res = subprocess.run(
                ["git", "log", "--format=%G? %GK %GS", "-1", sha],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
            sig_out = sig_res.stdout.strip().split()
            sig_status = sig_out[0] if sig_out else "N"

            if sig_status == "B":
                self._add_finding(
                    category="COMMIT_INTEGRITY",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=self._rel_path(manifest_path),
                    rule="tampered_commit_signature",
                    message=(
                        f"Commit '{sha}' has an INVALID / TAMPERED cryptographic signature (status 'B')."
                    ),
                )
            elif sig_status == "E":
                self._add_finding(
                    category="COMMIT_INTEGRITY",
                    severity="HIGH",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=self._rel_path(manifest_path),
                    rule="signature_eval_error",
                    message=f"Commit '{sha}' signature evaluation encountered error (status 'E').",
                )

        # 4. SHA consistency check
        frozen_sha = manifest_data.get("frozen_head_sha")
        verified_sha = manifest_data.get("verified_head_sha")
        if frozen_sha and verified_sha and str(frozen_sha).strip() != str(verified_sha).strip():
            self._add_finding(
                category="COMMIT_INTEGRITY",
                severity="HIGH",
                agent_id=agent_id,
                phase=phase,
                file_path=self._rel_path(manifest_path),
                rule="head_sha_mismatch",
                message=(
                    f"verified_head_sha '{verified_sha}' does not match frozen_head_sha '{frozen_sha}'."
                ),
            )

    def verify_deliverables_and_path_lane(
        self,
        manifest_data: dict[str, Any],
        manifest_path: Path,
        agent_id: str,
        phase: str,
    ) -> list[Path]:
        """Verify declared deliverables exist and adhere to assigned path lane."""
        file_paths: list[str] = []
        for key in ["deliverables", "files_created", "files_modified", "files_changed"]:
            val = manifest_data.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and "path" in item:
                        file_paths.append(item["path"])
                    elif isinstance(item, str):
                        file_paths.append(item)

        # Parse authorized path lane
        path_lane_raw = manifest_data.get("path_lane")
        path_lanes: list[str] = []
        if isinstance(path_lane_raw, str):
            path_lanes = [p.strip() for p in path_lane_raw.split(";") if p.strip()]
        elif isinstance(path_lane_raw, list):
            path_lanes = [str(p).strip() for p in path_lane_raw if str(p).strip()]

        existing_deliverable_paths: list[Path] = []
        for rel_path in file_paths:
            if "*" in rel_path:
                # Glob pattern, expand relative to repo_root
                expanded = list(self.repo_root.glob(rel_path))
                if not expanded:
                    self._add_finding(
                        category="DELIVERABLE_INTEGRITY",
                        severity="HIGH",
                        agent_id=agent_id,
                        phase=phase,
                        file_path=self._rel_path(manifest_path),
                        rule="empty_glob_deliverable",
                        message=f"Deliverable glob pattern '{rel_path}' matched no files on disk.",
                    )
                else:
                    existing_deliverable_paths.extend(expanded)
                continue

            full_path = self.repo_root / rel_path
            if not full_path.exists() and (manifest_path.parent / rel_path).exists():
                full_path = manifest_path.parent / rel_path

            if not full_path.exists():
                self._add_finding(
                    category="DELIVERABLE_INTEGRITY",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=self._rel_path(manifest_path),
                    rule="missing_deliverable_file",
                    message=f"Declared deliverable '{rel_path}' does not exist on disk.",
                )
            else:
                existing_deliverable_paths.append(full_path)

            # Path lane boundary check (excluding own agent artifact folder across phases)
            own_artifact_pattern = re.compile(rf"^artifacts/PH\d{{2}}/{agent_id}/")
            if path_lanes and not own_artifact_pattern.match(rel_path):
                in_lane = any(rel_path.startswith(lane.rstrip("*")) for lane in path_lanes)
                if not in_lane:
                    self._add_finding(
                        category="PATH_LANE_VIOLATION",
                        severity="HIGH",
                        agent_id=agent_id,
                        phase=phase,
                        file_path=self._rel_path(manifest_path),
                        rule="unauthorized_file_path",
                        message=(
                            f"File '{rel_path}' is outside authorized path lane "
                            f"{path_lanes}."
                        ),
                    )

        return existing_deliverable_paths

    def verify_test_results_and_evidence(
        self,
        manifest_data: dict[str, Any],
        manifest_path: Path,
        agent_dir: Path,
        agent_id: str,
        phase: str,
    ) -> None:
        """Verify test reports and audit for simulated / fake test results."""
        test_report_path = agent_dir / "test_report.md"

        # Check if test_report.md exists
        if not test_report_path.is_file():
            self._add_finding(
                category="FAKE_TEST_RESULT",
                severity="CRITICAL",
                agent_id=agent_id,
                phase=phase,
                file_path=self._rel_path(manifest_path),
                rule="missing_test_report",
                message=f"No 'test_report.md' found for subagent {agent_id} in {agent_dir}.",
            )
            return

        report_text = test_report_path.read_text(encoding="utf-8", errors="replace")
        if not report_text.strip():
            self._add_finding(
                category="FAKE_TEST_RESULT",
                severity="CRITICAL",
                agent_id=agent_id,
                phase=phase,
                file_path=self._rel_path(test_report_path),
                rule="empty_test_report",
                message="test_report.md is empty (zero bytes / no verification evidence).",
            )
            return

        # Check for suspicious mock/fake patterns in test_report.md
        for pat in SUSPICIOUS_TEST_FAKES:
            match = pat.search(report_text)
            if match:
                self._add_finding(
                    category="FAKE_TEST_RESULT",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=self._rel_path(test_report_path),
                    rule="fake_test_marker",
                    message=f"Matched suspicious fake test execution pattern: '{match.group(0)}'.",
                    snippet=match.group(0),
                )

        # Check status consistency if declared in manifest
        status = manifest_data.get("status")
        if status in {"COMPLETED", "PASSED"}:
            # If test results list exists, inspect exit codes
            for test_key in [
                "test_results",
                "verification_commands_summary",
                "test_commands_and_exit_codes",
            ]:
                records = manifest_data.get(test_key)
                if isinstance(records, list):
                    for idx, rec in enumerate(records):
                        if isinstance(rec, dict):
                            cmd = rec.get("command", "")
                            exit_code = rec.get("exit_code")
                            st = rec.get("status", "PASS")

                            # Trivial fake command check
                            if cmd in {"true", "echo pass", "echo ok", "exit 0"}:
                                self._add_finding(
                                    category="FAKE_TEST_RESULT",
                                    severity="CRITICAL",
                                    agent_id=agent_id,
                                    phase=phase,
                                    file_path=self._rel_path(manifest_path),
                                    rule="trivial_fake_command",
                                    message=(
                                        f"Trivial command '{cmd}' reported as test execution evidence."
                                    ),
                                )

                            # Non-zero exit code claiming PASS without expected-failure note
                            if exit_code is not None and exit_code != 0:
                                explicit_pass = st in {"PASS", "PASSED"}
                                # Check if documented as negative test or finding
                                desc = (
                                    rec.get("description", "")
                                    + " "
                                    + rec.get("rationale", "")
                                    + " "
                                    + str(manifest_data.get("key_findings", ""))
                                )
                                finding_explained = any(
                                    w in desc.lower() or w in report_text.lower()
                                    for w in [
                                        "finding",
                                        "fail-closed",
                                        "expected",
                                        "negative",
                                        "baseline",
                                        "sec-",
                                        "defect",
                                    ]
                                )
                                if explicit_pass and not finding_explained:
                                    self._add_finding(
                                        category="FAKE_TEST_RESULT",
                                        severity="HIGH",
                                        agent_id=agent_id,
                                        phase=phase,
                                        file_path=self._rel_path(manifest_path),
                                        rule="failing_exit_code_marked_pass",
                                        message=(
                                            f"Command '{cmd}' exited with code {exit_code} "
                                            f"but marked as status '{st}' without explanation."
                                        ),
                                    )

    def scan_file_for_secrets_phi_and_bypasses(
        self,
        file_path: Path,
        agent_id: str,
        phase: str,
    ) -> None:
        """Scan file content for credentials, PHI/PII, and safety bypasses."""
        # Test code modules (.py/.ts/.js/.dart) are unit tests exercising guardrails, not deliverables leaking data
        rel_to_repo = ""
        try:
            rel_to_repo = str(file_path.resolve().relative_to(self.repo_root))
        except ValueError:
            pass

        is_test_code = (
            file_path.suffix in (".py", ".ts", ".js", ".dart")
            and (
                file_path.name.startswith("test_")
                or file_path.name.endswith("_test.py")
                or "/tests/" in rel_to_repo
                or "\\tests\\" in rel_to_repo
            )
        )
        if is_test_code:
            return

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self._add_finding(
                category="DELIVERABLE_INTEGRITY",
                severity="HIGH",
                agent_id=agent_id,
                phase=phase,
                file_path=self._rel_path(file_path),
                rule="unreadable_file",
                message=f"Cannot read deliverable file: {exc}",
            )
            return

        rel_path = self._rel_path(file_path)
        lines = content.splitlines()

        # 1. Credentials Check
        for line_no, line in enumerate(lines, start=1):
            # Check sk- token
            sk_match = RE_SK_TOKEN.search(line)
            if sk_match:
                token = sk_match.group(0)
                # Ignore obvious dummy template tokens like sk-xxxx
                if not set(token[3:]).issubset({"x", "X", "."}):
                    self._add_finding(
                        category="CREDENTIAL_LEAK",
                        severity="CRITICAL",
                        agent_id=agent_id,
                        phase=phase,
                        file_path=rel_path,
                        line_number=line_no,
                        rule="hardcoded_sk_token",
                        message="Detected hardcoded live API key literal (sk-...).",
                        snippet=token[:8] + "...",
                    )

            # Check router API key assignment
            key_assign = RE_API_KEY_ASSIGN.search(line)
            if key_assign:
                self._add_finding(
                    category="CREDENTIAL_LEAK",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=rel_path,
                    line_number=line_no,
                    rule="hardcoded_api_key_assignment",
                    message="Detected hardcoded API key assignment without environment lookup.",
                    snippet=key_assign.group(0),
                )

            # Check Bearer auth header
            bearer_match = RE_BEARER_TOKEN.search(line)
            if bearer_match:
                self._add_finding(
                    category="CREDENTIAL_LEAK",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=rel_path,
                    line_number=line_no,
                    rule="hardcoded_bearer_token",
                    message="Detected unredacted Bearer authorization token header.",
                    snippet=bearer_match.group(0)[:30] + "...",
                )

            # Check Private Key
            if RE_PRIVATE_KEY.search(line):
                self._add_finding(
                    category="CREDENTIAL_LEAK",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=rel_path,
                    line_number=line_no,
                    rule="private_key_leak",
                    message="Detected unencrypted private key material.",
                )

            # Check Live JWT
            jwt_match = RE_LIVE_JWT.search(line)
            if jwt_match:
                jwt_val = jwt_match.group(0)
                # If not inside a test explaining JWT decode or mock
                if "REDACTED" not in line and "test" not in rel_path.lower():
                    self._add_finding(
                        category="CREDENTIAL_LEAK",
                        severity="HIGH",
                        agent_id=agent_id,
                        phase=phase,
                        file_path=rel_path,
                        line_number=line_no,
                        rule="unredacted_jwt",
                        message="Detected live unredacted JWT token string.",
                        snippet=jwt_val[:20] + "...",
                    )

        # 2. PHI / PII Check
        for line_no, line in enumerate(lines, start=1):
            # VN phone number in personal context
            phone_match = RE_VN_PHONE.search(line)
            if phone_match and "phone" in line.lower():
                self._add_finding(
                    category="PHI_LEAK",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=rel_path,
                    line_number=line_no,
                    rule="patient_phone_leak",
                    message="Detected plaintext Vietnamese phone number in patient/user context.",
                    snippet=phone_match.group(0),
                )

            # Patient national ID / CCCD / CMND
            id_match = RE_PATIENT_NATIONAL_ID.search(line)
            if id_match:
                self._add_finding(
                    category="PHI_LEAK",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=rel_path,
                    line_number=line_no,
                    rule="patient_national_id_leak",
                    message="Detected plaintext Citizen ID (CCCD/CMND) linked to patient identity.",
                    snippet=id_match.group(0),
                )

            # Email addresses
            emails = RE_PERSONAL_EMAIL.findall(line)
            for email in emails:
                domain = email.split("@", 1)[1].lower()
                if domain not in ALLOWED_EMAIL_DOMAINS and not domain.endswith(".example.com"):
                    self._add_finding(
                        category="PHI_LEAK",
                        severity="HIGH",
                        agent_id=agent_id,
                        phase=phase,
                        file_path=rel_path,
                        line_number=line_no,
                        rule="personal_email_leak",
                        message=f"Detected personal email address '{email}' outside authorized test domains.",
                        snippet=email,
                    )

            # Unredacted clinical record
            clin_match = RE_UNREDACTED_PATIENT_RECORD.search(line)
            if clin_match and "example" not in line.lower() and "mock" not in line.lower():
                self._add_finding(
                    category="PHI_LEAK",
                    severity="CRITICAL",
                    agent_id=agent_id,
                    phase=phase,
                    file_path=rel_path,
                    line_number=line_no,
                    rule="unredacted_clinical_record",
                    message="Detected unredacted clinical diagnosis / patient medical event in deliverable.",
                    snippet=clin_match.group(0),
                )

        # 3. Safety Invariants Bypass Check
        for line_no, line in enumerate(lines, start=1):
            # Skip lines that are simply documenting tests or comments asserting the invariant
            lower_line = line.lower()
            if any(
                w in lower_line
                for w in [
                    "never weaken",
                    "never bypass",
                    "prevent",
                    "reject",
                    "fails",
                    "invariant",
                    "check",
                    "assert",
                    "forbidden",
                    "remediated",
                ]
            ):
                continue

            for inv_name, pat in SAFETY_BYPASS_PATTERNS:
                m = pat.search(line)
                if m:
                    self._add_finding(
                        category="SAFETY_BYPASS",
                        severity="CRITICAL",
                        agent_id=agent_id,
                        phase=phase,
                        file_path=rel_path,
                        line_number=line_no,
                        rule=f"bypassed_{inv_name.lower()}",
                        message=f"Detected directive bypassing safety invariant '{inv_name}': '{m.group(0)}'.",
                        snippet=line.strip()[:100],
                    )

    def audit_agent_deliverables(self, manifest_path: Path) -> dict[str, Any]:
        """Audit single subagent deliverable directory given its change_manifest.json."""
        manifest_path = manifest_path.resolve()
        agent_dir = manifest_path.parent

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self._add_finding(
                category="DELIVERABLE_INTEGRITY",
                severity="CRITICAL",
                agent_id="UNKNOWN",
                phase="UNKNOWN",
                file_path=self._rel_path(manifest_path),
                rule="invalid_manifest_json",
                message=f"Failed to parse change_manifest.json as valid JSON: {exc}",
            )
            return {"status": "FAILED", "findings_count": len(self.findings)}

        agent_id = str(manifest_data.get("agent_id") or manifest_data.get("subagent_id") or "UNKNOWN")
        phase = str(manifest_data.get("phase") or manifest_data.get("phase_id") or "UNKNOWN")

        # 1. Commit integrity
        self.verify_commit_integrity(manifest_data, manifest_path, agent_id, phase)

        # 2. Deliverables and path lane check
        deliverable_paths = self.verify_deliverables_and_path_lane(
            manifest_data, manifest_path, agent_id, phase
        )

        # 3. Test results and evidence check
        self.verify_test_results_and_evidence(
            manifest_data, manifest_path, agent_dir, agent_id, phase
        )

        # 4. Deep content scan of manifest, test_report, risk_register, rollback, and deliverable files
        files_to_scan = set(deliverable_paths)
        files_to_scan.add(manifest_path)
        for standard_doc in ["test_report.md", "risk_register.md", "rollback.md"]:
            doc_path = agent_dir / standard_doc
            if doc_path.is_file():
                files_to_scan.add(doc_path)

        for file_to_scan in sorted(files_to_scan):
            if file_to_scan.is_file():
                self.scan_file_for_secrets_phi_and_bypasses(file_to_scan, agent_id, phase)

        agent_findings = [
            f for f in self.findings if f.agent_id == agent_id and f.phase == phase
        ]
        has_failure = any(
            f.severity in ("CRITICAL", "HIGH") or (self.strict and f.severity in ("MEDIUM", "LOW"))
            for f in agent_findings
        )

        return {
            "agent_id": agent_id,
            "phase": phase,
            "manifest": self._rel_path(manifest_path),
            "status": "FAILED" if has_failure else "PASSED",
            "findings_count": len(agent_findings),
            "findings": [f.to_dict() for f in agent_findings],
        }

    def audit_all(
        self,
        targets: list[Path] | None = None,
        phase_filter: str | None = None,
    ) -> dict[str, Any]:
        """Audit multiple targets (files or directories)."""
        manifest_files: list[Path] = []

        if not targets:
            # Default: scan artifacts directory
            artifacts_dir = self.repo_root / "artifacts"
            if artifacts_dir.is_dir():
                manifest_files.extend(artifacts_dir.glob("**/change_manifest.json"))
        else:
            for t in targets:
                p = (self.repo_root / t).resolve() if not t.is_absolute() else t.resolve()
                if p.is_file() and p.name == "change_manifest.json":
                    manifest_files.append(p)
                elif p.is_dir():
                    manifest_files.extend(p.glob("**/change_manifest.json"))

        manifest_files = sorted(set(manifest_files))

        if phase_filter:
            manifest_files = [
                m for m in manifest_files if f"/{phase_filter}/" in str(m)
            ]

        results = []
        for mf in manifest_files:
            results.append(self.audit_agent_deliverables(mf))

        total_critical = sum(1 for f in self.findings if f.severity == "CRITICAL")
        total_high = sum(1 for f in self.findings if f.severity == "HIGH")
        total_medium = sum(1 for f in self.findings if f.severity == "MEDIUM")
        total_low = sum(1 for f in self.findings if f.severity == "LOW")

        overall_passed = total_critical == 0 and total_high == 0
        if self.strict and (total_medium > 0 or total_low > 0):
            overall_passed = False

        return {
            "overall_status": "PASSED" if overall_passed else "FAILED",
            "manifests_audited": len(manifest_files),
            "total_findings": len(self.findings),
            "severity_counts": {
                "CRITICAL": total_critical,
                "HIGH": total_high,
                "MEDIUM": total_medium,
                "LOW": total_low,
            },
            "results": results,
            "findings": [f.to_dict() for f in self.findings],
        }


def format_cli_summary(report: dict[str, Any]) -> str:
    """Format audit results as readable CLI text."""
    lines = [
        "=" * 80,
        "DETERMINISTIC RED-TEAM MANIFEST CHECKER",
        f"Manifests Audited: {report['manifests_audited']}",
        f"Overall Status:    {report['overall_status']}",
        f"Findings Summary:  CRITICAL={report['severity_counts']['CRITICAL']}, "
        f"HIGH={report['severity_counts']['HIGH']}, "
        f"MEDIUM={report['severity_counts']['MEDIUM']}, "
        f"LOW={report['severity_counts']['LOW']}",
        "=" * 80,
    ]

    for res in report.get("results", []):
        st = res["status"]
        status_str = f"[{st}]"
        lines.append(f"{status_str:<8} Phase: {res['phase']:<6} Agent: {res['agent_id']:<6} -> {res['manifest']}")
        for f in res.get("findings", []):
            loc = f"{f['file_path']}"
            if f.get("line_number"):
                loc += f":{f['line_number']}"
            lines.append(f"         * [{f['severity']}] {f['category']} ({f['rule']}): {f['message']}")
            if f.get("snippet"):
                lines.append(f"           Snippet: {f['snippet']}")

    lines.append("=" * 80)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Specific change_manifest.json files or artifact directories to inspect",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Git repository root directory (default: current git root)",
    )
    parser.add_argument(
        "--phase",
        type=str,
        default=None,
        help="Filter audit to a specific phase (e.g. PH00, PH01, PH02)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail-closed on MEDIUM or LOW findings in addition to CRITICAL and HIGH",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON results",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Write structured audit report JSON to file",
    )

    args = parser.parse_args()
    checker = RedTeamManifestChecker(repo_root=args.repo_root, strict=args.strict)
    report = checker.audit_all(targets=args.paths, phase_filter=args.phase)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_cli_summary(report))

    return 0 if report["overall_status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
