# Accepted / ignored dependency-vulnerability findings

Spec: `clara-platform-hardening` · Task 9.3 (record accepted/ignored findings).

This is the **register of record** for every dependency-vulnerability finding
that is *not* fixed by an upgrade or replacement — i.e. each finding that is
explicitly **accepted** (a compensating control is in place) or **ignored**
(suppressed in a scanner) — across `services/api`, `services/ml`, and
`apps/web`. It exists so the strengthened CI supply-chain gate
(`.github/workflows/ci.yml` → `security-audit` + `container-scan`) can block on
critical and high-severity findings while a small, documented, time-boxed set of
unfixable findings is carried deliberately rather than silently
(Requirement 8.4, 8.6). It also documents the Dependabot triage/merge cadence
that keeps the default branch from re-accumulating findings (Requirement 8.5).

This register backs the ongoing triage of the **~105 Dependabot findings** on
the default branch (1 critical, ~40 high at the time of writing). The default
disposition for every finding is **fix** (upgrade, replace, or remove the
dependency). Acceptance or suppression is the exception, is always justified and
time-boxed here, and is revisited on its review date.

> **No PII.** This file is version-controlled and contains no personal or health
> data and no secret values — only advisory ids, package names, severities, and
> human-authored justifications.

## How the gate uses this register

The supply-chain gate in `.github/workflows/ci.yml` runs:

- **`pip-audit`** over `services/api` + `services/ml` (Python),
- **`npm audit`** over `apps/web` (JavaScript), and
- **Trivy** image scans for the `api`, `ml`, and `web` containers
  (`--severity HIGH,CRITICAL --ignore-unfixed`).

For a finding to be carried past the gate it MUST have a corresponding **Active**
entry in the register below **and** a matching suppression in the relevant
scanner ignore mechanism (see [Suppression mechanisms](#suppression-mechanisms)).
A suppression without a register entry, or a register entry missing a required
field, is a process failure: the accepted-findings completeness check
(Task 9.5, design Property 22) fails the build when any **Active** entry lacks a
justification, a compensating control, or a review date.

## Required fields per entry

Every entry MUST carry all of the following. Entries missing any field are
invalid and will fail the completeness check.

| Field | Meaning |
| --- | --- |
| **Advisory ID** | The canonical id: GHSA, CVE, PYSEC, or npm advisory number. Include all that apply. |
| **Package / ecosystem** | Affected package and ecosystem (pip / npm / docker), with the affected version or range. |
| **Surface** | Which component(s) ship it: `services/api`, `services/ml`, `apps/web`, or a container image. |
| **Severity** | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` as reported by the scanner / advisory. |
| **Disposition** | `accepted` (no fix available, compensating control in place) or `ignored` (not exploitable in our usage / false positive). |
| **Justification** | Why this is safe to carry now: no fix released, transitive-only, dev-only, code path not reached, etc. Be specific. |
| **Compensating control** | The concrete control that bounds the risk (network isolation, input validation, internal-key guard, not-in-runtime-path, etc.). Required for `accepted`; for `ignored` state why it is not reachable/applicable. |
| **Owner** | The accountable person/role (GitHub handle or team) who owns re-evaluation. |
| **Accepted on** | Date the acceptance was recorded (ISO `YYYY-MM-DD`). |
| **Review date** | Date by which the acceptance MUST be revisited (ISO `YYYY-MM-DD`). |
| **Revisit condition** | The trigger that ends the acceptance early — typically "a fixed version is released", but may be a usage change or a published exploit. |
| **Suppression ref** | Where the matching scanner suppression lives (e.g. `pip-audit --ignore-vuln`, `.trivyignore`, npm advisory id) so the gate and the register stay in sync. |

### Conventions

- **Default disposition is fix.** Only record an entry here when an upgrade,
  replacement, or removal is genuinely unavailable or unsafe to apply now.
- **Review dates are mandatory and bounded.** Use a review window no longer than
  **90 days** for `HIGH`/`CRITICAL` and **180 days** for `MEDIUM`/`LOW`. An entry
  past its review date is treated as **expired** and must be re-justified or
  removed; expired entries should fail review.
- **One advisory per row.** If a single package upgrade clears several
  advisories, keep them as separate rows so each can expire independently.
- **Move, don't delete.** When a finding is fixed (a fixed version ships) or an
  acceptance expires and is retired, move the row to
  [Resolved / retired](#resolved--retired-history) with the resolution date and
  the fixing change — keep the audit trail.

## Active accepted / ignored findings

> One finding is carried below: `ecdsa` GHSA-wj6h-64fc-37mp (CVE-2024-23342),
> which has no upstream fix. Every other Dependabot finding is in the **fix**
> track (Task 9.1) — remediated by raising the affected direct-dependency floors
> (`python-jose>=3.4.0`, `python-multipart>=0.0.18`) so the resolved lockfiles
> stay on patched versions — until proven unfixable, at which point it is
> recorded here with all required fields before the gate is allowed to pass.

| Advisory ID | Package / ecosystem (version) | Surface | Severity | Disposition | Justification | Compensating control | Owner | Accepted on | Review date | Revisit condition | Suppression ref |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GHSA-wj6h-64fc-37mp (CVE-2024-23342) | ecdsa (0.19.2, pip) | services/api | HIGH | accepted | No fix is available: the `ecdsa` maintainers have stated the Minerva timing side-channel is not fixable in pure Python and will not be patched, so no upgrade clears it. It is pulled in only transitively by `python-jose[cryptography]` (which is itself on the patched `>=3.4.0` floor); CLARA signs/verifies JWTs with the HMAC (`HS*`) algorithms via the `cryptography` backend, not the ECDSA (`ES*`) code path that the advisory affects. | The vulnerable ECDSA signing/verification path is not exercised: JWT issuance/validation uses HMAC keys, and token signing happens server-side over a managed secret (not attacker-timed across a network boundary). The internal-key guard and TLS-terminated ingress further bound any timing-oracle exposure. Tracked for removal if `python-jose` drops the `ecdsa` dependency. | @TBD | 2026-06-26 | 2026-09-24 | fixed version verified (ecdsa publishes a constant-time fix, or python-jose removes the ecdsa dependency) | pip-audit --ignore-vuln GHSA-wj6h-64fc-37mp |
| _none yet_ | — | — | — | — | — | — | — | — | — | — | — |

### Entry template (copy a row when accepting a finding)

```
| GHSA-xxxx-xxxx-xxxx (CVE-YYYY-NNNNN) | <package> (<affected version/range>, <pip|npm|docker>) | services/api | HIGH | accepted | <why no fix can be applied now> | <concrete control bounding the risk> | @<owner> | YYYY-MM-DD | YYYY-MM-DD | fixed version released | <.trivyignore | pip-audit --ignore-vuln | npm advisory> |
```

## Suppression mechanisms

Keep each register entry in sync with the scanner suppression that lets the gate
pass. Do **not** suppress a finding without a matching **Active** entry above.

- **pip-audit (`services/api`, `services/ml`)** — suppress a specific advisory
  with `--ignore-vuln <ID>` in the `Run pip-audit` step of
  `.github/workflows/ci.yml`. Annotate the workflow with a comment pointing at
  the register entry. Prefer fixing via the lockfile over suppressing.
- **npm audit (`apps/web`)** — the gate runs `npm audit --omit=dev
  --audit-level=critical`. Where a dev-only or unreachable advisory must be
  carried, record it here and, if needed, scope it with the project's npm
  override/resolution mechanism; do not broaden the audit level to hide it.
- **Trivy container scan (`api`, `ml`, `web` images)** — add the advisory id to
  a repo-root `.trivyignore` (the scan already runs with `--ignore-unfixed`, so
  no-fix-available OS findings are skipped automatically). Each manual entry in
  `.trivyignore` MUST correspond to an **Active** row here.

## Dependabot triage and merge cadence

Dependabot configuration (`.github/dependabot.yml`) is preserved
(Requirement 8.5). It opens **weekly** update PRs (Monday, `Asia/Ho_Chi_Minh`)
across these ecosystems, each limited to 10 open PRs and labeled `dependencies`:

| Ecosystem | Directory | Label |
| --- | --- | --- |
| github-actions | `/` | `github-actions` |
| pip | `/services/api` | `python` |
| pip | `/services/ml` | `python` |
| npm | `/apps/web` | `javascript` |
| docker | `/`, `/services/api`, `/services/ml`, `/apps/web` | `docker` |

**Triage cadence**

- **Weekly triage (within 2 business days of the Monday batch).** Review every
  open Dependabot PR. The reviewer is the surface owner per `.github/CODEOWNERS`.
- **Security-only updates are expedited.** A PR addressing a `CRITICAL` or `HIGH`
  advisory is triaged within **1 business day** and prioritized for merge ahead
  of routine version bumps.
- **Merge when green.** A Dependabot PR merges once CI is green — including the
  `security-audit` and `container-scan` gates — and any required review approval
  is in place. Patch and minor security updates are the default merge path.
- **Hold and record, don't ignore silently.** If an update cannot be merged
  (breaking change, no compatible version, regression), either pin to the last
  safe version with a tracking issue, or — if the underlying advisory is
  unfixable — add an **Active** entry to this register with all required fields.
- **Stale PR hygiene.** Dependabot PRs open longer than **two cycles** (≈2 weeks)
  are escalated to the surface owner during weekly triage; superseded PRs are
  rebased or closed so the queue reflects current findings.

## Review workflow

1. **On every weekly triage**, scan the **Active** table for any entry whose
   **review date** is reached or passed. Each such entry is re-justified
   (extend with a new, bounded review date and a fresh rationale) or retired.
2. **When a fix becomes available** (a fixed version ships, or the revisit
   condition fires), apply the upgrade/replacement, remove the matching scanner
   suppression, and move the row to
   [Resolved / retired](#resolved--retired-history).
3. **The completeness check** (Task 9.5, design Property 22) runs in CI and
   fails if any **Active** entry is missing a justification, a compensating
   control, or a review date — keeping the register honest.

## Resolved / retired history

Findings that were fixed (a fixed version shipped) or whose acceptance expired
and was retired. Keep the audit trail; do not delete rows from the Active table.

| Advisory ID | Package / ecosystem | Surface | Resolution date | Resolution (fix / retirement) |
| --- | --- | --- | --- | --- |
| _none yet_ | — | — | — | — |

## References

- Requirement 8.4 — keep the container image scan; record an inventory of
  accepted/ignored findings with justification and review date.
- Requirement 8.5 — preserve the Dependabot configuration; document the triage
  and merge cadence.
- Requirement 8.6 — where a vulnerability has no fix, document the compensating
  control and the conditions under which the acceptance is revisited.
- Design Property 22 — accepted-findings completeness (every ignored/unfixable
  finding has a justification, a compensating control, and a review date).
- Related: `.github/workflows/ci.yml` (`security-audit`, `container-scan`),
  `.github/dependabot.yml`, `.github/requirements-security-audit.txt`,
  `docs/security/security-remediation-2026-04-03.md`,
  `docs/runbooks/platform-hardening-rollout.md`.
