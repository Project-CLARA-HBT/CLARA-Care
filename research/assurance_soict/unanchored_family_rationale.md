# GovMut unanchored family rationale

Status: **protocol finding; no mutant result**.

The catalog deliberately leaves three fault families unanchored. They are not
missing zeroes and must not be padded with cosmetic overlays merely to reach a
target count.

| Family | Why no one-line overlay is currently defensible | Required executable test-only mechanism |
| --- | --- | --- |
| M10 — state/audit transaction atomicity | The contract spans transition, transition-item, state-version, and audit persistence. Removing a single gateway condition is not a transaction-atomicity mutation and would mislabel a different fault. | A fresh PostgreSQL-only fault injector at a defined write/audit boundary, with an explicit rollback oracle that observes all affected tables. |
| M12 — stale derived snapshot/cache reuse | Current GLHS source compiles persisted manifests but has no test-only cache adapter that exposes a derived-cache read/invalidation boundary. Mutating a Python variable or a Redis-like fixture would not exercise the production enforcement site. | An isolated cache/index adapter with a provenance-bearing cache key, deterministic invalidation hook, and replay oracle after state/consent/policy change. |
| M15 — retry after governance rejection without reauthorization | The current gateway returns a rejection; it does not contain an automatic retry workflow that can be mutated independently of the existing consent/policy checks. Reusing M03 would duplicate the consent fault rather than test retry semantics. | A test-only retry driver that records initial rejection, reauthorization attempt, and later commit; its mutant must skip the reauthorization step while preserving the same logical request. |

Each future implementation must produce an anchored one-change overlay, a
dedicated non-equivalence test, and an isolation record before it joins the
mutation-score denominator.
