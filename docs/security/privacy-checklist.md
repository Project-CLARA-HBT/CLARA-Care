# Security and privacy implementation checklist

Use this operational checklist before a release; it is not a certification.

- [ ] RBAC/profile isolation and consent/CSRF contract tests passed.
- [ ] Emergency and legal hard-guard invariant tests passed.
- [ ] FIDES/claim verification and DrugBank required-source tests passed.
- [ ] Eval manifests/fixtures contain no PHI, secrets, prompts or provider keys.
- [ ] Logs, telemetry, workflow artifacts and judge report were reviewed for
      names, email, free-text clinical queries and drug lists.
- [ ] Model/prompt/retrieval manifests are immutable and rollback choice is
      documented before enabling a risky model path.
- [ ] Upload type/size, retention and deletion propagation checks passed.
- [ ] Dependency, secret, SAST/container scans and restore drill have current
      evidence; otherwise release remains blocked.
- [ ] Release locked suite is measured, not merely structurally green.
