# PH01 / A07 — Test Report: SBOM Generator and Dependency Security Audit

**Phase:** PH01 (Toolchain tái lập và dependency supply-chain)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
**Branch:** `phase/ph01-a07`
**Date:** October 21, 2026
**Status:** COMPLETE

---

## 1. Scope & Objective

Deliver an automated, hermetic Software Bill of Materials (SBOM) generator and dependency security integrity audit tool suite for CLARA Care across Python (`services/api`, `services/ml`, `services/asr`, `services/ocr`), Node (`apps/web`), and Flutter (`apps/mobile`).

The work encompasses:
1. Automated generation of CycloneDX 1.5 JSON SBOM and CLARA Supply Chain Manifest.
2. Complete audit of package dependencies across Python, Node, Flutter, detecting unpinned direct dependencies and lockfile absence.
3. Cryptographic hash coverage evaluation across resolved package locks.
4. Validation of CVE triage register in `docs/security/accepted-findings.md` against required schemas, expiration dates, and suppression mechanisms.
5. Integration of SBOM generation and dependency integrity verification steps into `.github/workflows/ci.yml`.
6. Full automated test suite in `services/api/tests/test_sbom_and_dependency_integrity.py`.

---

## 2. Test Execution & Evidence

### 2.1 Automated Test Suite (`services/api/tests/test_sbom_and_dependency_integrity.py`)

- **Runner:** `pytest-9.1.1` (Python 3.12.3)
- **Execution Command:**
  ```bash
  (cd services/api && pytest tests/test_sbom_and_dependency_integrity.py)
  ```
- **Exit Code:** `0`
- **Output Excerpt:**
  ```
  ============================= test session starts ==============================
  platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
  rootdir: /dev/shm/clara_worktrees/PH01_A07/services/api
  configfile: pyproject.toml
  plugins: anyio-4.14.2, asyncio-1.4.0, hypothesis-6.167.1
  asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collected 10 items

  tests/test_sbom_and_dependency_integrity.py ..........                   [100%]

  ============================= 10 passed in 26.75s ==============================
  ```

### 2.2 Test Case Matrix

| Test Function | Target Verified | Result |
|---|---|---|
| `test_make_purl_ecosystems` | Package URL (PURL) RFC spec generation for pypi, npm, pub, generic | **PASS** |
| `test_is_constraint_pinned` | Accurate parsing of exact pin (`==`, exact semver) vs ranges (`^`, `~`, `>=`) | **PASS** |
| `test_sbom_builder_scan_and_cyclonedx` | CycloneDX 1.5 schema validation, multi-ecosystem component discovery | **PASS** |
| `test_sbom_builder_manifest` | CLARA supply chain manifest schema, lockfile SHA-256 integrity calculation | **PASS** |
| `test_parse_accepted_findings_from_repo` | Extraction of active CVE table from `docs/security/accepted-findings.md` | **PASS** |
| `test_parse_accepted_findings_malformed` | Fail-closed validation on missing justifications, controls, or review dates | **PASS** |
| `test_run_dependency_integrity_audit` | Full repo dependency audit, hash coverage, unpinned tracking | **PASS** |
| `test_run_dependency_integrity_audit_fail_strict` | Strict enforcement gating on unpinned dependencies | **PASS** |
| `test_cli_generate_sbom_invocation` | CLI invocation of `generate_sbom.py` with argument parsing and artifact writing | **PASS** |
| `test_cli_check_dependency_integrity_invocation` | CLI invocation of `check_dependency_integrity.py` with JSON report output | **PASS** |

### 2.3 CLI Tool Verification

#### Command: `python3 scripts/ops/generate_sbom.py --output-dir artifacts/PH01/A07 --summary`
- **Exit Code:** `0`
- **Output:**
  ```
  [SBOM] Wrote CycloneDX SBOM to artifacts/PH01/A07/sbom.cyclonedx.json
  [SBOM] Wrote CLARA Supply Chain Manifest to artifacts/PH01/A07/sbom_manifest.json
  ======================================================================
  CLARA SUPPLY-CHAIN SBOM SUMMARY
  ======================================================================
  Total Components Identified: 1048
    • Python (pypi):           143
    • Node.js (npm):           826
    • Flutter / Dart (pub):    79
  ----------------------------------------------------------------------
  Direct Dependencies:         85
    • Pinned exact:            18
    • Unpinned / range:        67
  ----------------------------------------------------------------------
  [WARN] Surfaces lacking hermetic lockfiles:
    - services/asr/uv.lock
    - services/ocr/Dockerfile (direct unpinned pip install)
  ======================================================================
  ```

#### Command: `python3 scripts/ops/check_dependency_integrity.py --report-file artifacts/PH01/A07/dependency_audit_report.json`
- **Exit Code:** `0`
- **Output:**
  ```
  ======================================================================
  CLARA DEPENDENCY INTEGRITY & CVE TRIAGE AUDIT
  ======================================================================
  Components checked:          1048
  Direct dependencies:         85
  Unpinned direct:             67
  Lockfile hash coverage:      98.57%
  Active accepted findings:    1
  Expired accepted findings:   1
  ----------------------------------------------------------------------
  [WARNINGS]
    [WARN] Surface lacks hermetic lockfile: services/asr/uv.lock
    [WARN] Surface lacks hermetic lockfile: services/ocr/Dockerfile (direct unpinned pip install)
    [WARN] Accepted finding GHSA-wj6h-64fc-37mp (CVE-2024-23342) (ecdsa (0.19.2, pip)) review date expired on 2026-09-24
  ----------------------------------------------------------------------
  OVERALL INTEGRITY STATUS: PASS
  ======================================================================
  ```

### 2.4 Code Quality & Linting (`ruff check`)

- **Command:** `ruff check scripts/ops/generate_sbom.py scripts/ops/check_dependency_integrity.py services/api/tests/test_sbom_and_dependency_integrity.py`
- **Exit Code:** `0`
- **Output:** `All checks passed!`

---

## 3. Inventory & Audit Findings

1. **Lockfile Completeness:**
   - `services/api/uv.lock`: Present (66 packages, 100% SHA-256 hashed).
   - `services/ml/uv.lock`: Present (69 packages, 100% SHA-256 hashed).
   - `apps/web/package-lock.json`: Present (826 packages, 100% SHA-512 hashed).
   - `apps/mobile/pubspec.lock`: Present (79 packages, 97.5% SHA-256 hashed; SDK packages flutter/flutter_localizations do not carry external hashes).
   - `services/asr`: `pyproject.toml` pins dependencies strictly (`==`), but lacks `uv.lock`.
   - `services/ocr`: `Dockerfile` executes unpinned `RUN pip install fastapi uvicorn httpx python-multipart`.

2. **Unpinned Direct Dependencies:**
   - Python (`services/api`, `services/ml`): Direct requirements in `pyproject.toml` use minimum bounds (`>=`), while resolved versions are locked in `uv.lock`.
   - Node (`apps/web`): 7 direct production dependencies and devDependencies use caret ranges (`^`).
   - Flutter (`apps/mobile`): 4 direct dependencies use caret ranges (`^1.2.2`, etc.).

3. **CVE Triage Governance (`docs/security/accepted-findings.md`):**
   - Active finding `GHSA-wj6h-64fc-37mp` (CVE-2024-23342) on `ecdsa` carries all mandatory schema fields (justification, compensating control, owner, revisit condition).
   - Review date `2026-09-24` is past today's date (`2026-10-21`), requiring a formal triage review by the security lead (flagged in risk register).
