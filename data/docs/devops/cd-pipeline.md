# CD Pipeline: Staging -> Production Promote

Workflow: `.github/workflows/cd.yml`

## Muc tieu

- Deploy image da co san tren GHCR theo `image_tag`.
- Bat buoc smoke pass o `staging` truoc khi promote `production`.
- Co artifact de debug khi smoke fail.

## Trigger

- `workflow_dispatch` (manual run).

Inputs hien tai:

- `image_tag` (required): tag da ton tai tren GHCR, vi du `v1.3.0` hoac `sha-a1b2c3d`.
- `promote_to_production` (boolean, default `true`): co chay job production sau staging hay khong.
- `deployment_reason` (string, default `manual-release`): note cho run summary.

Luu y: workflow hien tai **khong** co `rollback_tag` va khong auto-sinh tag mac dinh.

## Co che approve

Workflow dung GitHub Environments:

- `deploy-staging` -> environment `staging`
- `promote-production` -> environment `production`

Neu can manual approval, cau hinh required reviewers tren tung environment.

## Secret va quyen can thiet

- Workflow permissions: `contents: read`, `packages: read`.
- Dang nhap GHCR bang `${{ github.actor }}` + `${{ secrets.GITHUB_TOKEN }}`.
- Khong dung SSH/rsync secrets trong workflow hien tai.

## Flow ky thuat

1. `preflight` resolve:
   - `image_tag`
   - `registry_repo=ghcr.io/<owner>/<repo>` (lowercase)
2. `preflight` verify ton tai 3 images:
   - `clara-api:<image_tag>`
   - `clara-ml:<image_tag>`
   - `clara-web:<image_tag>`
3. `deploy-staging`:
   - Tao `.env` tu `.env.example`, inject `API_IMAGE`, `ML_IMAGE`, `WEB_IMAGE`
   - Validate compose config.
   - `docker compose -f deploy/docker/docker-compose.deploy.yml pull` (co retry 3 lan)
   - `docker compose ... up -d` (co retry 3 lan)
   - Smoke localhost:
     - `http://127.0.0.1:${APP_API_PORT:-8100}/health`
     - `http://127.0.0.1:${APP_API_PORT:-8100}/api/v1/health`
     - `http://127.0.0.1:${APP_ML_PORT:-8110}/health`
     - `http://127.0.0.1:${APP_WEB_PORT:-3100}/`
4. Neu `promote_to_production=true`, `promote-production` lap lai quy trinh deploy + smoke.

## Artifacts khi run

- Staging smoke responses: `staging-smoke-<run_id>`
- Production smoke responses: `production-smoke-<run_id>` (neu co promote)
- Compose status snapshots:
  - `/tmp/cd-staging-ps.txt`
  - `/tmp/cd-production-ps.txt`
- Log failure:
  - `cd-staging-logs-<run_id>`
  - `cd-production-logs-<run_id>`

## Notes van hanh

- CD workflow khong build image moi.
- "Rollback" thuc te la rerun workflow voi mot `image_tag` cu con ton tai tren GHCR.
