# Runbook: controlled VPS deployment

`cd.yml` deploys pre-built GHCR images on a controlled host. It does **not** run
Compose, migrations, or application smoke checks on a GitHub runner. The target
receives a small immutable release bundle, not a repository worktree.

## Bootstrap and protected inputs

On each target, install Docker Engine + Compose v2, then create the root:

```bash
install -d -m 700 /opt/clara-care/releases /opt/clara-care/backups
install -m 600 /dev/null /opt/clara-care/.env
```

Configure these independently in protected `staging` and `production` GitHub
environments (production requires review): variables `DEPLOY_SSH_HOST`,
`DEPLOY_SSH_PORT`, `DEPLOY_SSH_USER`, `DEPLOY_ROOT` (under `/opt/clara-care`),
`PUBLIC_BASE_URL`, `GHCR_PULL_USERNAME`; secrets `DEPLOY_SSH_PRIVATE_KEY`,
`DEPLOY_SSH_KNOWN_HOSTS`, `DEPLOY_ENV_FILE`, and `GHCR_PULL_TOKEN`.

Use a dedicated deploy key with a pinned host fingerprint. Password SSH and
`StrictHostKeyChecking=no` are prohibited. `DEPLOY_ENV_FILE` reaches the host
only through encrypted SSH stdin, is stored mode `600`, and is neither bundled
nor logged. It must contain the governed DeepSeek Pro/Flash configuration,
required API/ML credentials, and approved feature flags from `.env.example`.

## Sequence and evidence

Dispatch **Controlled deployment** with an existing immutable image tag. The
runner checks the four GHCR image manifests and migration downgrade declarations.
The host validates its environment, writes a checksum-verified pre-migration
Postgres backup, pulls images, runs Alembic, checks API/ML/ASR/web and both
anonymous share routes, then atomically advances `/opt/clara-care/current`.
The runner finally checks public HTTPS security headers and that the PHR viewer
does not redirect an anonymous request to login. Only sanitized Compose status
is uploaded as a CI artifact.

Before moving an existing legacy Nginx virtual host to this workflow, install
`deploy/nginx/clara.thiennn.icu.conf` (or copy its header stanza into the
domain's active virtual host), then use `nginx -t` and reload Nginx under the
host's approved change procedure. The stanza hides upstream framework headers
and emits the same browser policy on proxy-generated responses, so security
headers cannot disappear merely because a stale Next image or proxy error is
served. Do not claim this was applied until the workflow's external HTTPS
header smoke succeeds.

Each release stores protected `pre-migration-backup.path` and, when applicable,
`previous-release.path` receipts. The legacy source-tree deploy script remains
for an explicitly authorized operator only; CI uses the immutable bundle path.

## Rollback

Preserve the failed release, receipt, and protected logs first. For an
image-only rollback, dispatch the workflow with the prior immutable image tag.
For a schema-incompatible release, use the **new** API image to run the specific
`alembic downgrade <prior-revision>` before starting the old images. If data
recovery is necessary, restore the exact dump named by
`pre-migration-backup.path` using [backup-restore.md](backup-restore.md), then
deploy its matching old image set. Never delete retained releases or backups
during incident response, and never blindly downgrade a database.

If SSH, GHCR, environment validation, migration, smoke, public headers, or the
public share route fails, treat deployment as failed and correct that condition;
do not weaken host-key checks, package access, or logging controls.
