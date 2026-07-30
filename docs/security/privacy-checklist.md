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
- [ ] CI/CD uploaded only status/readiness diagnostics and the artifact safety
      guard passed; raw container logs and runtime `.env` were not uploaded.
- [ ] Model/prompt/retrieval manifests are immutable and rollback choice is
      documented before enabling a risky model path.
- [ ] Upload type/size, retention and deletion propagation checks passed.
- [ ] Dependency, secret, SAST/container scans and restore drill have current
      evidence; otherwise release remains blocked.
- [ ] Release locked suite is measured, not merely structurally green.
