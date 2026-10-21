# Risk Register: PH01_A09 Developer Local Bootstrap Script & Toolchain Parity

## 1. Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant Enforced | Status |
|---|---|---|---|---|---|---|
| **RR-PH01-A09-01** | Non-Deterministic Toolchain Drift | Local developers using differing Python or Node.js versions leading to syntax, serialization, or library discrepancies. | High | Medium | `scripts/ops/bootstrap_dev.sh` strictly enforces Python `>=3.11` (target `3.12`) and Node 20 (`>=20 <21`), failing preflight check if versions drift. | Controlled |
| **RR-PH01-A09-02** | Destructive Environment Mutation | Bootstrap script accidentally overwriting developer `.env` files containing custom credentials or local ports. | Critical | Low | Non-destructive design: `action_setup_env` checks `test -f .env` and preserves existing configuration without modification. Verified in test case 6. | Controlled |
| **RR-PH01-A09-03** | Worktree Git Pollution | Executing research verification scripts during bootstrap creates dirty working tree states or updates timestamps. | High | Low | `bootstrap_dev.sh --verify-research` executes only sealed, read-only runners (`reproduce_e01.py`, `reproduce_e07.py`) which produce no untracked files or modifications. | Controlled |
| **RR-PH01-A09-04** | Unrestricted Network Egress | Bootstrap or research runners leaking test data, querying external APIs, or failing due to network downtime. | Critical | Low | Research runners activate `disable_network()` fail-closed mechanism, prohibiting all TCP/UDP socket creation and DNS resolution. | Controlled |
| **RR-PH01-A09-05** | Bypassed Pre-Commit Gates | Developers committing unformatted or un-typechecked code because git hooks are not installed. | Medium | High | `bootstrap_dev.sh --check` detects missing hooks and provides actionable guidance; `--install-hooks` automates `pre-commit install`. | Controlled |
| **RR-PH01-A09-06** | Package Manager Divergence | Developers using legacy pip or poetry rather than locked uv, breaking reproducible lockfile parity. | High | Low | Script enforces `uv` toolchain verification, checking PATH and providing direct installation instructions via Astral installer. | Controlled |
| **RR-PH01-A09-07** | Path Reference Invalidation | Introducing forbidden machine-specific absolute paths (`/home/`, `/Users/`, `/private/`) into documentation. | Medium | Low | Zero absolute machine paths used; validated against `scripts/docs/check-docs-links.sh` rules. | Controlled |

---

## 2. Invariant & Safety Guardrails Summary

1. **Non-Destructive Principle:** Operations performed by `bootstrap_dev.sh` are strictly non-destructive. No developer configurations, git stashes, or uncommitted work can be discarded.
2. **Fail-Closed Prerequisite Enforcement:** In `--check` mode, if core required toolchains (Python, Node, uv, git) are missing or invalid, the script exits with non-zero exit code `1` and prints precise remediation instructions.
3. **Hermetic Offline Reproduction:** Offline research suites (`reproduce_e01.py`, `reproduce_e07.py`) operate fail-closed with network disabled and reproduce bit-exact cryptographic seals.
4. **Path Lane Containment:** All created files reside strictly within `scripts/ops/`, `docs/implementation/`, and `artifacts/PH01/A09/`.
