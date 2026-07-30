# Runbook: CI/CD diagnostic artifact safety

CI/CD artifacts are not a substitute for a controlled production log store.
They can be downloaded by people with repository actions access, so a failed
deployment must never upload raw container logs, request bodies, transcripts,
or a rendered runtime `.env` file.

## Guardrail in this repository

`scripts/security/check_ci_artifact_safety.py` is the fail-closed guard for the
small diagnostic files that CI/CD may upload: readiness responses and Docker
Compose status. It rejects basic identifiers and credentials (email, Vietnamese
phone pattern, bearer/JWT tokens, private-key headers, and common credential
assignments). It intentionally does **not** claim that arbitrary text can be
made safe through regex redaction.

The CI and CD workflows consequently upload only:

- API/ML/ASR/web health and route-readiness responses;
- Docker Compose service status; and
- evaluator outputs generated from the sanitized fixture set.

They do not upload `docker compose logs`. A guard failure means no artifact is
uploaded, and the workflow must be investigated rather than bypassed.

## Incident diagnostics

1. Record the GitHub run ID and the non-sensitive service/status information.
2. Use the production incident-access process to inspect raw logs on the
   controlled host. Do not copy request/response bodies, prompts, transcripts,
   patient names, medication lists, `.env`, or tokens into an issue or artifact.
3. If a credential marker is found, stop the deployment, rotate the affected
   secret under [credential rotation](credential-rotation.md), then document
   only the secret *name* and rotation timestamp.
4. If a PII marker is found, follow the privacy incident process; retain only
   the minimum access-controlled evidence required by policy.

## Local operator check

Use this only for the small, generated files above:

```bash
python3 scripts/security/check_ci_artifact_safety.py \
  /tmp/cd-production-ps.txt /tmp/prod-api-root-health.json
```

The command exits non-zero for a missing file or a detected marker. Do not add
an allowlist for a real secret or patient datum; replace the artifact with a
counts/status-only projection instead.
