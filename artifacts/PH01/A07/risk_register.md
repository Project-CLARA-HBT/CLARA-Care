# PH01 / A07 — Risk Register: Supply Chain & Dependency Security

**Phase:** PH01 (Toolchain tái lập và dependency supply-chain)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
**Date:** October 21, 2026
**Status:** COMPLETE

---

## 1. Overview

This risk register tracks security and supply-chain vulnerabilities, unpinned dependencies, lockfile voids, and CVE review expirations discovered during the PH01 A07 automated audit across Python, Node.js, and Flutter environments.

---

## 2. Risk Matrix & Findings

### RISK-SC01: Unpinned Dependency Installation in OCR Service Dockerfile
- **Category:** Supply Chain / Build Hermeticity
- **Severity:** HIGH (P1)
- **Affected Path:** `services/ocr/Dockerfile:4`
- **Description:**
  `services/ocr/Dockerfile` contains:
  ```dockerfile
  RUN pip install --no-cache-dir fastapi uvicorn httpx python-multipart
  ```
  These packages are unpinned and installed directly from PyPI at container build time without a lockfile or checksum verification. Any upstream release, compromised wheel, or breaking change in `fastapi`, `uvicorn`, `httpx`, or `python-multipart` will destabilize OCR container builds and introduce supply-chain injection vectors.
- **Root Cause:** OCR service was implemented as a thin sidecar without dependency management tooling (`uv` / `pyproject.toml`).
- **Remediation Plan (PH01 A04 / PH02):**
  Add a dedicated `pyproject.toml` and compile an exact `uv.lock` or `requirements.txt` with hashes, updating `Dockerfile` to `RUN pip install --no-cache-dir -r requirements.lock`.

---

### RISK-SC02: Missing Lockfile in ASR Sidecar Service
- **Category:** Supply Chain / Reproducibility
- **Severity:** MEDIUM (P2)
- **Affected Path:** `services/asr/pyproject.toml:6-11`
- **Description:**
  `services/asr/pyproject.toml` specifies exact equality pins (`fastapi==0.139.2`, `uvicorn==0.51.0`, `python-multipart==0.0.32`, `faster-whisper==1.2.1`), but does not have a checked-in `uv.lock`. Transitive dependencies (such as `ctranslate2`, `tokenizers`, `onnxruntime`, or `torch`) are resolved dynamically at install time without cryptographic hash locking.
- **Root Cause:** `uv lock` has not been generated or committed for `services/asr`.
- **Remediation Plan (PH01 A04):**
  Run `uv lock --directory services/asr` to generate a hermetic `uv.lock` with SHA-256 hashes for all direct and transitive wheels.

---

### RISK-SC03: Expired Review Date for Accepted Advisory GHSA-wj6h-64fc-37mp (CVE-2024-23342)
- **Category:** Vulnerability Management / CVE Triage
- **Severity:** MEDIUM (P2)
- **Affected Path:** `docs/security/accepted-findings.md:89`
- **Description:**
  Finding `GHSA-wj6h-64fc-37mp` (`ecdsa` 0.19.2 Minerva timing side-channel) was accepted on 2026-06-26 with a scheduled review date of `2026-09-24`. As of today's date (`2026-10-21`), this review date has expired.
- **Risk Assessment:**
  Low operational threat because CLARA Care uses HMAC (`HS256`/`HS512`) via the `cryptography` backend for JWT verification and does not invoke the pure-Python ECDSA verification path. However, policy requires review dates to remain strictly bounded within 90 days.
- **Remediation Plan (PH01 A08 / Security Lead):**
  Review whether `python-jose` has released a version removing the `ecdsa` dependency or if migrating to `PyJWT` / `cryptography` native token verification is viable. If remaining accepted, update the review date to `2026-12-24` with renewed architectural justification.

---

### RISK-SC04: 67 Unpinned Direct Dependencies in Manifests
- **Category:** Build Reproducibility / Version Drift
- **Severity:** LOW (P3)
- **Affected Paths:**
  - `services/api/pyproject.toml` (17 direct deps use `>=`)
  - `services/ml/pyproject.toml` (14 direct deps use `>=`)
  - `apps/web/package.json` (7 direct runtime deps use `^`)
  - `apps/mobile/pubspec.yaml` (4 direct deps use `^`)
- **Description:**
  Direct dependencies specify semver range operators rather than pinned versions. In the absence of a lockfile (or during developer installs with `pip install .`), newer minor/patch versions could be fetched automatically.
- **Compensating Control:**
  `services/api/uv.lock`, `services/ml/uv.lock`, `apps/web/package-lock.json`, and `apps/mobile/pubspec.lock` pin all resolved dependencies with cryptographic checksums. CI enforces `npm ci` and `uv sync --frozen`.
- **Remediation Plan:**
  Keep range constraints in development manifests to permit security patches, but enforce strict lockfile-only builds in CI and deployment pipelines (`scripts/ops/check_dependency_integrity.py`).

---

### RISK-SC05: 34 Pre-Existing Vulnerabilities in Web DevDependencies / Node Modules
- **Category:** Third-Party Vulnerability
- **Severity:** MEDIUM (P2)
- **Affected Path:** `apps/web/package-lock.json`
- **Description:**
  `npm audit --package-lock-only` in `apps/web` reports 34 vulnerabilities (3 critical, 23 high, 7 moderate, 1 low).
  - Critical findings affect `next` (cache poisoning / SSRF in specific configurations) and `tinypool` (prototype pollution in test worker).
  - High findings affect `axios`, `brace-expansion`, `braces`, `browserslist`, `dompurify`, `minimatch`, `nanoid`, `sharp`.
- **Compensating Control:**
  `ci.yml` runs `npm audit --omit=dev --audit-level=high`. Dev dependencies are isolated from production runtime images (`Dockerfile` uses multi-stage build running `next build` and exporting standalone output).
- **Remediation Plan (PH01 A04 / PH02):**
  Apply non-breaking patch updates via `npm audit fix` for `axios`, `dompurify`, `brace-expansion`, and verify Vitest / Playwright regression tests before upgrading major dependencies (`vitest`, `tailwindcss`).
