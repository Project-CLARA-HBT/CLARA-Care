# Runbook: CLARA Chat redesign (`CHAT_V2`) staged rollout

Spec: `clara-chat-redesign` · Task 8.3 (rollout).

This runbook covers the staged enablement of the rebuilt, componentized chat
(`apps/web/app/chat/_v2`) behind the `CHAT_V2` flag, parity verification, the
production default flip, rollback, and the follow-up legacy-removal cleanup.

## Summary

The redesign ships behind a single build-time feature flag,
`NEXT_PUBLIC_CHAT_V2`, read in `apps/web/app/chat/_v2/flag.ts`:

| `NEXT_PUBLIC_CHAT_V2` value           | Served experience            |
| ------------------------------------- | ---------------------------- |
| unset / empty / `1` / `true` / `on`   | **v2 redesign (default ON)** |
| `0` / `false` / `off` (case-insens.)  | legacy chat (rollback)       |

Because the flag is `NEXT_PUBLIC_*` it is inlined at **build time** for the web
app. "Flipping" the flag in an environment means setting the env var for that
environment's build/deploy and shipping a new build — there is no runtime
toggle. The default is ON, so the redesign rolls out wherever the var is left
unset; rollback is an explicit per-environment opt-out (`=false`) plus redeploy.

The legacy page is preserved verbatim at `apps/web/app/chat/_legacy/page-legacy.tsx`
and is only loaded when the flag is OFF, so rollback is byte-for-byte
(design Property P1 — flag isolation; Requirement 8.1, 8.2, 8.6).

## Prerequisites

- Parity verification tasks complete: 8.1 (parity matrix) and 8.2 (no-PII
  analytics, consent/disclaimer/RBAC preserved).
- Parity matrix test green:
  `apps/web/app/chat/_v2/__tests__/parity-matrix.test.tsx` (design Property P3,
  Requirement 6.1–6.6).
- Flag isolation tests green: `apps/web/app/chat/_v2/__tests__/flag.test.ts` and
  `apps/web/app/chat/_v2/__tests__/route-gate.test.tsx`.

## Stage 1 — Enable in staging

1. In the **staging** environment config, leave `NEXT_PUBLIC_CHAT_V2` **unset**
   (default ON) or set it explicitly to `on` to make intent obvious.
2. Build and deploy the web app to staging.
3. Confirm the route renders the v2 shell (`ChatShell`), not the legacy page.

## Stage 2 — Verify parity in staging

Confirm the redesign supports every user-facing capability the legacy page did
(Requirement 6) before touching production.

1. Run the parity matrix test (the single source of truth for "are we at
   parity?"):
   ```
   npm run test -- app/chat/_v2/__tests__/parity-matrix.test.tsx
   ```
   (run from `apps/web`). A failure here means a Requirement 6 capability lost
   its v2 implementation or covering test — **do not proceed** until green.
2. Smoke-test the staged build against the parity checklist:
   - conversation create / select / rename / delete, favorites, folders (6.1)
   - notes, sharing (expiry / rotation / revoke), export markdown + docx (6.2)
   - command palette + actions (6.3)
   - search across conversations (6.4)
   - local-fallback workspace when the workspace API is unavailable (6.5)
   - telemetry / flow panels with admin-only detail visibility (6.6)
   - consent gate, medical disclaimer, RBAC nav still enforced (8.4)
3. Verify fast streaming, deep / deep_beta job runs, streaming fallback, and
   cancel behave as before with no turn loss (Requirement 3).

## Stage 3 — Flip default in production

Only after staging parity is confirmed.

1. In the **production** environment config, leave `NEXT_PUBLIC_CHAT_V2` unset
   (default ON) — or set it to `on` for explicit intent.
2. Build and deploy. The production route now serves the v2 shell.
3. Monitor error rates, chat-stream success, and latency. Watch for regressions
   in deep / deep_beta runs and export/share flows.

## Rollback (any environment)

Rollback is env-only — no code change required.

1. Set `NEXT_PUBLIC_CHAT_V2=false` (or `0` / `off`) in the affected
   environment's config.
2. Rebuild and redeploy the web app.
3. The route falls back to the preserved legacy page
   (`_legacy/page-legacy.tsx`), unchanged.

Keep the legacy page in the tree until the cleanup below — it is the rollback
target.

## Follow-up — schedule legacy removal (later cleanup task)

Once the redesign has been the production default and stable for an agreed bake
period (and no rollback is anticipated), schedule a **separate cleanup task** to
remove the legacy implementation. That task — out of scope for 8.3 — should:

1. Delete `apps/web/app/chat/_legacy/page-legacy.tsx`.
2. Simplify the route gate `apps/web/app/chat/page.tsx` to render the v2 shell
   directly, and remove the `CHAT_V2` flag, `flag.ts`, and the flag/route-gate
   tests that exist only to guard the legacy fallback.
3. Remove the `NEXT_PUBLIC_CHAT_V2` entry from `.env.example` and environment
   configs.
4. Update the parity matrix test as needed once parity is permanent.

> Do not perform this removal as part of task 8.3. It is intentionally deferred
> so rollback stays available throughout the rollout (Requirement 8.6).
