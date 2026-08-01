# Security and privacy implementation checklist

Use this operational checklist before a release; it is not a certification.

- [ ] RBAC/profile isolation and consent/CSRF contract tests passed.
- [ ] Emergency and legal hard-guard invariant tests passed.
- [ ] FIDES/claim verification and DrugBank required-source tests passed.
- [ ] Eval manifests/fixtures contain no PHI, secrets, prompts or provider keys.
- [ ] Any live-eval manifest is externally governed, de-identified, stored only
      as a deployment/Actions secret, materialized outside the repository, and
      removed after execution. `live-execution.json` contains no request or
      response body, raw case ID, credential or patient content.
- [ ] Any Encoder-SLM shadow endpoint is internal/approved, receives bounded
      redacted input only, has no user-facing confidence display, and has an
      exercised flag rollback (`ENCODER_SLM_SHADOW_ENABLED=false`).
- [ ] Logs, telemetry, workflow artifacts and judge report were reviewed for
      names, email, free-text clinical queries and drug lists.
- [ ] Preview email delivery logs only the action/mode. They must not contain a
      recipient, OTP, reset token, verification token, or signed action link.
- [ ] CI/CD uploaded only status/readiness diagnostics and the artifact safety
      guard passed; raw container logs, runtime `.env`, and mined hard-negative
      JSONL/free-text query data were not uploaded.
- [ ] A controlled deployment ran Compose, migration and service smoke checks
      on the pinned target host rather than a GitHub runner. SSH host trust was
      pinned, deploy/GHCR credentials were supplied only to their owning steps
      and over stdin where applicable, the target `.env` remained mode `600`,
      and the release/backup receipts are retained for rollback.
- [ ] Model/prompt/retrieval manifests are immutable and rollback choice is
      documented before enabling a risky model path.
- [ ] Untrusted PHR OCR and Research uploads passed bounded-read,
      filename/MIME/magic-byte regression checks. If
      `UPLOAD_MALWARE_SCAN_REQUIRED=true`, a reachable ClamAV INSTREAM service
      returned clean verdicts and an unavailable scanner was verified to fail
      closed (503), never fail open.
- [ ] Upload retention and deletion propagation checks passed.
- [ ] Dependency, secret, SAST/container scans and restore drill have current
      evidence; otherwise release remains blocked.
- [ ] Production `npm audit --omit=dev --audit-level=high` has no unreviewed
      result. A framework advisory with no compatible fixed release is a tracked
      release blocker, not a reason to lower the audit threshold or add a broad
      scanner suppression.
- [ ] Release locked suite is measured, not merely structurally green.
