# Branch Protection Policy (main)

Workflow: `.github/workflows/branch-protection-sync.yml`

## Mục tiêu

- Chặn merge vào `main` nếu thiếu check bắt buộc.
- Bắt buộc review PR và code owner review.
- Chặn force-push và xóa branch `main`.

## Policy ap dung

- Required status checks:
  - `required-ci-gates`
- Require pull request trước khi merge.
- Require toi thieu 2 approving reviews.
- Dismiss stale reviews khi có commit mới.
- Require code owner review.
- Require approval cho commit push cuoi cung (`require_last_push_approval=true`).
- Require conversation resolution.
- Enforce rule với cả admin.
- Disallow force pushes.
- Disallow deletions.

### CI gate policy (blocking vs advisory)

`required-ci-gates` gom 2 lop:

- Blocking core checks (luon bat buoc):
  - `quality`
  - `scripts-syntax`
  - `hackathon-artifacts-smoke`
  - `api-tests`
  - `ml-tests`
  - `web-lint-build`
- Hardening checks (`security-audit`, `docker-compose-smoke`, `container-scan`):
  - `push/workflow_dispatch`: blocking.
  - `pull_request`: advisory mac dinh.
  - `pull_request -> main`: co the nang thanh blocking bang repo variable `CI_STRICT_PR_HARDENING=true`.

## Cách chạy

1. Tạo secret repo: `BRANCH_PROTECTION_TOKEN`
   - Loại token: Fine-grained PAT hoặc GitHub App token.
   - Quyền tối thiểu: Repository administration (write).
2. Vào Actions -> `Branch Protection Sync`.
3. Run workflow với:
   - `branch`: `main`
   - `required_checks`: `required-ci-gates`
   - `required_approvals`: `2`
   - `require_code_owner_reviews`: `true`
   - `dry_run`: `true` để xem payload trước.
4. Chạy lại với `dry_run=false` để áp rule thật.

## Schedule tự động

- Workflow có cron mỗi thứ Hai 04:00 UTC để re-apply policy.
- Mục tiêu: tránh drift cấu hình do chỉnh tay trong Settings.
- Nếu thiếu secret `BRANCH_PROTECTION_TOKEN`, workflow sẽ tự `skip` và cảnh báo thay vì fail toàn job.

## Kết hợp với CODEOWNERS

- File `.github/CODEOWNERS` định nghĩa owner theo thư mục.
- Khi bật `require_code_owner_reviews`, PR sẽ cần owner approve trước merge.
