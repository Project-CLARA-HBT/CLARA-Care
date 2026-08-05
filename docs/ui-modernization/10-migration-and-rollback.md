# Migration and rollback plan

## Principles

- No data deletion and no history rewrite.
- Presentation migrations are backward-compatible and independently revertible.
- Route access is never derived from menu visibility.
- Safety, consent, RBAC, profile isolation, audit, provenance, DrugBank, and FIDES behavior are unchanged.
- API/schema changes are optional and isolated from UI milestones.

## Milestone commits

1. `ui-foundation-tokens-primitives`
2. `ui-icon-and-phr`
3. `ui-route-access-workspaces`
4. `ui-shell-navigation`
5. `ui-personal-flows`
6. `ui-chat-research`
7. `ui-clinical-scribe`
8. `ui-quality-compatibility`

Actual hashes are recorded in `11-decisions-and-progress.md` as commits are created. Each commit is built/tested before the next starts; no force-push.

## Compatibility adapters

- `/selfmed*`, `/careguard`, `/research*`, admin aliases remain redirects.
- Existing `components/ui/*` exports remain stable while internals migrate.
- Existing `AppShell`, navigation helper, and legacy Chat imports receive adapters during extraction.
- `clara_sidebar_collapsed` remains readable; workspace storage is new, versioned, presentation-only.
- Public `/share/*` and `/phr/shared/*` remain shell-free and do not load authenticated analytics.

## Feature flags

The initial rollout uses milestone commits and revert, not an unimplemented shell kill switch. A `NEXT_PUBLIC_UI_SHELL_V2` flag may be introduced only in a later checkpoint if production observation proves it necessary; it is not an operational rollback mechanism until implemented, tested on both paths, documented in the flag inventory, and given an observation/retirement date. Chat V2 legacy flag remains until parity review. No flag can hide a required safety warning or authorize a route.

## Optional API migrations

The core UI work has no DB migration. If later work adds PHR section PATCH/ETag, recurring reminder entities, or server-resumable visit fields:

1. Add an Alembic migration with downgrade.
2. Keep old read/write contract backward-compatible.
3. Add round-trip and rollback tests.
4. Deploy API before enabling UI capability.
5. Disable feature flag and revert UI if migration or contract health fails.

## Rollback procedure

1. Stop rollout/disable the temporary UI flag if present.
2. Identify last stable milestone from the ExecPlan and git log.
3. Revert only the offending milestone commit (no `reset --hard`, no force-push).
4. Rebuild web from the previous lockfile/config and run route, safety, build, and E2E smoke.
5. Keep compatibility aliases and data; no destructive cleanup.
6. Record incident, evidence, and follow-up in `11-decisions-and-progress.md`.

## High-risk rollback notes

- Shell: old and new presentation must import the same access registry.
- Icon: keep old font CSS until SVG adoption covers active routes; SVG fallback is safe independently.
- Chat: toggle legacy Chat only through its existing reviewed flag, never by changing API safety behavior.
- Scribe: a UI rollback cannot turn a failed sign into signed; preserve server status.
- Medicines: UI rollback cannot merge or delete course/cabinet/PHR records.
- LifeMap: rollback cannot convert draft/review states into confirmed truth.

## Evidence required before release

- Full validation matrix and screenshot diff reviewed.
- No Critical/High review finding outstanding.
- Route and capability inventory complete.
- Working tree contains only intentional modernization changes plus pre-existing user-owned files.
- Deployment artifact checksum and rollback target recorded.
