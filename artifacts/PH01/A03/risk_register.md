# Risk Register: Phase PH01 — Agent A03 (Domain + GLHS Services)

**Phase:** PH01
**Agent:** A03
**Role:** Domain + GLHS services
**Worktree:** `/dev/shm/clara_worktrees/PH01_A03`
**Branch:** `phase/ph01-a03`
**Frozen HEAD SHA:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
**Task:** Lock ML dependencies and domain supply-chain; audit dependencies between services/api and services/ml; verify uv.lock integrity and hermetic package resolution across GLHS, lifemap, phr, compliance.
**Evaluation Date:** 2026-10-21

---

## 1. Supply-Chain & Domain Risk Overview

Phase PH01 focuses on toolchain re-establishment, dependency supply-chain locking, and hermetic reproducibility. For Agent A03 (Domain + GLHS services), the primary risk surfaces involve:
1. **Supply-Chain Integrity & Hermetic Resolution:** Deterministic lockfile resolution (`uv.lock`) across `services/api` and `services/ml` without network drift or undeclared transitive dependencies.
2. **Cross-Service Architectural Boundary Coupling:** Unintended direct Python imports between `clara_api` and `clara_ml`, bypassing the authenticated HTTP/gRPC boundary (`X-ML-Internal-Key`).
3. **Domain Dependency Containment:** Ensuring safety-critical subsystems (GLHS linearizable commit kernel, RFC 8785 canonical JSON, LifeMap CQRS, PHR migration guard, Compliance consent ledger) rely exclusively on locked, vetted, and minimal third-party libraries.
4. **Toolchain Version Drift:** Discrepancies in shared foundational dependencies (e.g., SQLAlchemy, Cryptography, Psycopg) between the API service and ML service runtimes.
5. **Runtime Test Environment Sensitivity:** Deprecation warnings and path-resolution dependencies that could affect automated CI gates.

---

## 2. Identified Risks and Gaps Matrix

| Risk ID | Severity | Category | Component | Description & Forensic Evidence | Blast Radius & Potential Impact | Mitigation / Remediation Proposal |
|---|---|---|---|---|---|---|
| **RSK-PH01-A03-001** | High (P1) | Architecture / Coupling | `services/ml/lifemap/capture_evaluation.py` | `capture_evaluation.py:342` contains a direct import: `from clara_api.lifemap.capture_domain import emergency_fast_path`. | If `clara_ml` runs in an isolated container or virtualenv where `services/api/src` is not on `PYTHONPATH`, executing `python -m clara_ml.lifemap.capture_evaluation` triggers `ModuleNotFoundError: No module named 'clara_api'`. | Decouple evaluation script: extract `emergency_fast_path` into a shared contract module (`contracts/`), or pass the detector via dependency injection/HTTP endpoint. |
| **RSK-PH01-A03-002** | High (P1) | Architecture / Coupling | `services/api/api/v2/medications.py` | `medications.py:537` contains an in-process lazy import fallback: `from clara_ml.agents.careguard import run_careguard_analyze`. | If `clara_api` runs without `services/ml/src` on `PYTHONPATH` or without ML dependencies (e.g., `langchain`, `langgraph`), the fallback fails. Bypasses standard HTTP service-to-service communication. | Enforce that all medication DDI/Careguard analyses route strictly through the HTTP ML gateway client (`httpx` to ML port 8010/8110 with `X-ML-Internal-Key`), removing direct Python module coupling. |
| **RSK-PH01-A03-003** | Medium (P2) | Supply-Chain / Version Drift | `services/api/uv.lock` vs `services/ml/uv.lock` | Shared dependencies have minor version drift across the two lockfiles: `sqlalchemy` (API=2.0.48 vs ML=2.0.51), `cryptography` (API=46.0.7 vs ML=49.0.0), `psycopg` (API=3.3.3 vs ML=3.3.4), `greenlet` (API=3.3.2 vs ML=3.5.4), `tzdata` (API=2025.3 vs ML=2026.3). | Discrepancies in connection pooling, crypto cipher behavior, or async database operations could manifest in rare edge cases during multi-service integration. | Synchronize `uv.lock` versions in a unified workspace or pin exact shared versions in subsequent dependency synchronization phases. |
| **RSK-PH01-A03-004** | Low (P3) | Runtime / Deprecation | `services/api` SQLite Test Fixtures | Pytest execution on Python 3.12 triggers: `DeprecationWarning: The default datetime adapter is deprecated as of Python 3.12; see the sqlite3 documentation for suggested replacement recipes` in SQLAlchemy `default.py:952`. | Harmless in Python 3.12, but will become an exception in Python 3.13/3.14 if SQLite default datetime adapter is removed without explicit converter registration. | Register explicit `sqlite3` datetime adapters/converters in test suite conftest fixtures or ensure SQLAlchemy dialect options enable native datetime string parsing. |
| **RSK-PH01-A03-005** | Medium (P2) | Test Runner / Path Sensitivity | `services/api/tests/test_glhs_canonical_json.py` | `test_cross_process_determinism` executes a subprocess using `sys.path.insert(0, os.path.abspath('services/api/src'))`. | If pytest is invoked from within `services/api` directory (`cd services/api && pytest ...`), `abspath('services/api/src')` resolves to `services/api/services/api/src` which does not exist, causing `ModuleNotFoundError: No module named 'clara_api'`. | Update `test_cross_process_determinism` to dynamically discover repo root via `Path(__file__).resolve().parents[3]` so it succeeds regardless of invocation working directory. |
| **RSK-PH01-A03-006** | Low (P3) | Toolchain / Deprecation | FastAPI TestClient Fixtures | Test fixtures log: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead`. | Future Starlette minor/major upgrade may drop backward compatibility with current `TestClient` initialization pattern. | Track upstream Starlette/FastAPI roadmap and migrate test client harness when `httpx2` or new Starlette test client interface stabilizes. |
| **RSK-PH01-A03-007** | Medium (P2) | Migration / Integration | `test_glhs_dependency_vector_v2_migration.py` | `test_apply_transition_and_apply_commitment_transition_on_migrated_db` fails when run in isolation due to missing column `status` on `glhs_inference_context_bindings`. | Indicates that Alembic migrations applied during that specific test fixture did not reach the head containing the `status` column on `glhs_inference_context_bindings`. | Coordinate with Agent A02 (Data model + migration) to ensure all migration revisions in `alembic/versions` are monotonically linked and fully include `status`. |
| **RSK-PH01-A03-008** | Low (P3) | Test Assertion Drift | `test_glhs_inference_context_binding.py` | `test_consent_drift_rejected` asserts `match="commitment_proposal_consent_mismatch"`, but the hardened consent enforcement in `core.consent` returns `consent_revoked: stale_consent_version`. | Test fails due to regex mismatch while the underlying safety invariant (rejecting stale consent) is completely functional and actively fail-closed. | Update the regex matcher in `test_glhs_inference_context_binding.py:756` to accept either `"stale_consent_version"` or `"commitment_proposal_consent_mismatch"`. |

---

## 3. Defense-in-Depth & Supply-Chain Containment Safeguards

1. **Pure-Python Canonical JSON (Zero External Serialization Dependencies):**
   `clara_api.glhs.canonical_json` implements RFC 8785 (JCS) determinism using pure Python standard library (`json`, `math`, `re`, `hashlib`). It does not rely on third-party canonical JSON packages (e.g., `canonicaljson`), ensuring immunity to upstream serialization supply-chain attacks.

2. **Strict Cryptographic Attestation Isolation:**
   GLHS attestation receipts (`attestation_receipts.py`) rely strictly on the vetted `cryptography` package (Ed25519 digital signatures and SHA-256 digests) and standard library primitives. No unverified third-party cryptographic libraries are permitted.

3. **Schema-Derived Dependency Generation (LLM Hallucination Barrier):**
   `clara_api.glhs.dependency_contract` enforces that all dependency vectors for OCC state transitions are derived strictly from structured domain semantics (`_OPERATION_RULES`). Proposed dependencies from models/LLMs are validated against the schema-derived minimum; any omission or unpermitted excess triggers immediate `GlhsInvariantError` rejection.

4. **Hermetic Lockfile Enclosure:**
   Both `services/api/uv.lock` and `services/ml/uv.lock` are fully pinned with exact package versions, repository source hashes, and wheel artifacts. CI runs `uv sync --frozen`, prohibiting any network resolution of untracked dependencies.

5. **Fail-Closed Medical Consent & RBAC Invariants:**
   Every entry point in `compliance/api.py`, `lifemap/profile_scope.py`, and `core/consent.py` verifies actor role (`require_roles`), non-revoked session credentials (`has_valid_explicit_bearer_token`), and active versioned medical consent before disclosing health state or allowing mutations.
