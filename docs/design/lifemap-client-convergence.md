# LifeMap client convergence and offline policy

The API endpoint `GET /api/v1/lifemap/v2/client-contract` is the authority for
the web and Flutter vocabulary. Contract version
`lifemap-client-contract-v1` defines exactly:

`draft`, `awaiting_review`, `confirmed`, `disputed`, `stale`, `unavailable`,
and `offline`.

Only `confirmed` carries truth authority. A client that receives an unknown
future state fails closed to `unavailable`; it does not relabel it as
confirmed. Every mutating capability declares `online_only`.

## Offline policy

- Health mutations are never queued. Network failure leaves the canonical
  state unchanged and the user input available for a later explicit retry.
- Flutter can cache the least-necessary Today read projection in
  `flutter_secure_storage` behind
  `LIFEMAP_OFFLINE_READ_CACHE_ENABLED` (default `false`).
- The cache contains only task id/title/due date, episode id/title/priority,
  pending-confirmation count, generation time, `cached_at`, and
  `valid_until`. It excludes profile identity, event payloads, provenance,
  documents, medication data, credentials, and safety status.
- Cached content is always labeled offline, even inside its 15-minute validity
  window. After `valid_until` it is additionally labeled stale. Completion and
  every other mutation on that projection are disabled.
- Logout and account switching erase the cached projection.
- The web client does not persist a LifeMap health projection offline because
  the current browser architecture has no approved encrypted-at-rest cache.
  A network failure therefore shows unavailable/offline state and retains no
  health payload in `localStorage` or `sessionStorage`.
- Cached safety status is never represented as current. CareGuard's separate
  last-known projection retains its own stronger warning and feature gate.

Enabling the mobile cache is an operational rollout decision:

```bash
flutter build apk \
  --dart-define=CLARA_API_BASE_URL=https://theclaracare.com \
  --dart-define=LIFEMAP_OFFLINE_READ_CACHE_ENABLED=true
```

This does not enable queued writes.
