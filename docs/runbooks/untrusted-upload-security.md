# Runbook: Untrusted PHR OCR and Research uploads

PHR OCR and Research document uploads are an untrusted-input boundary. Before
OCR, parsing, persistence, retrieval, or model access, the API reads them in
bounded chunks and deterministically verifies the filename extension, browser
MIME and observed magic bytes. It accepts only UTF-8 text, PDF, and the common
image formats used by those surfaces. The stored MIME is the detected MIME, not
a browser-supplied claim.

This applies to:

- `POST /api/v1/phr/import/ocr/scan` (still review-only; it never writes PHR)
- `POST /api/v1/research/upload-file`
- `POST /api/v1/research/knowledge-sources/{source_id}/upload-file`

The PHR scan additionally requires the owner's current medical-disclaimer
consent before the file crosses the OCR boundary. A scan returns proposals only:
the API attaches reviewable corrected-text offsets and a short-lived,
owner-bound signed capability containing opaque candidate IDs (never OCR text).
`POST /api/v1/phr/import/ocr/confirm` accepts only explicitly confirmed rows
from that signed scan set; discarded rows remain unpersisted. Expired, malformed
or cross-user capabilities fail closed. This boundary does not change RBAC,
owner isolation or CSRF, does not inspect medical content, and never transmits
the upload to an LLM.

## Malware scanning rollout

Magic-byte validation is always active. ClamAV is separately controlled by the
following API environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `UPLOAD_MALWARE_SCAN_REQUIRED` | `false` | Require a `clean` ClamAV verdict before accepting an upload. |
| `UPLOAD_MALWARE_CLAMAV_HOST` | empty | Reachable ClamAV daemon hostname/IP. |
| `UPLOAD_MALWARE_CLAMAV_PORT` | `3310` | ClamAV INSTREAM port. |

Enable only after the daemon is reachable from the API container:

```bash
UPLOAD_MALWARE_SCAN_REQUIRED=true
UPLOAD_MALWARE_CLAMAV_HOST=clamav
UPLOAD_MALWARE_CLAMAV_PORT=3310
docker compose --env-file .env -f deploy/docker/docker-compose.deploy.yml up -d api
```

When the flag is true, an absent, unavailable, timed-out, malformed, or
infected scan has no fail-open path: the API returns a safe `503` for scanner
unavailability or rejects the upload as unsupported/unsafe. Do not enable the
flag until operational monitoring for ClamAV is available.

## Rollback

Set `UPLOAD_MALWARE_SCAN_REQUIRED=false` and restart only the API service. This
rolls back the scanner dependency while retaining mandatory size, filename,
MIME and magic-byte validation. No database migration or user data deletion is
involved.
