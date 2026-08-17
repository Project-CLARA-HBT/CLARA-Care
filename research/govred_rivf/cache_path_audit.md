# GovRed W2 — CLARA cache/index layer audit

Status: **audit of `services/api/src/clara_api` cache/index layers** (no remote
VPS execution, no production changes). Companion code lives in
`evaluation/governance_adversarial/cache_observer.py`,
`family_contracts.py`, `validate_v2.py`, `controls.py`.

## 1. Scope and method

Searched `services/api/src/clara_api` for real cache usage, focusing on the
three areas named in the W2 workstream brief:

- `RedisSecurityStore` and everything built on it (`core/redis_security_store.py`);
- the "security Redis cache" layer (`core/session_security.py`,
  `core/login_guard.py`, `core/rate_limit.py`);
- GLHS snapshot handling (`glhs/gateway.py`, `glhs/domain.py`) to confirm whether
  snapshots are cached or persisted authoritatively.

The audit asks four questions per layer: owner module, key derivation, read/write
path, TTL, invalidation triggers, consent/policy relation, and whether the layer
is authoritative or derivative. It also answers the W2 question plainly: *which
caches exist, and do ordinary invalidation hooks exist?*

## 2. Inventory of cache-like layers in the API service

| Layer | Owner module | Backing | Authoritative / derivative |
| --- | --- | --- | --- |
| Generic Redis helper | `core/redis_security_store.py` | Redis | derivative store (security controls) |
| Session security denylist/rotation | `core/session_security.py` | Redis via `RedisSecurityStore` | derivative (JWT denylist) |
| Login throttling | `core/login_guard.py` | Redis via `RedisSecurityStore` | derivative (attempt counters/lock) |
| Distributed rate limit | `core/rate_limit.py` | Redis via `RedisSecurityStore` | derivative (bucket counter) |
| In-process settings cache | `core/config.py:929` | `functools.lru_cache` | derivative (settings) |
| OCR credential cache | `core/google_vision_ocr.py:18` | in-process dict | derivative (access token) |
| Flow event ring buffer | `core/flow_event_store.py` | in-process `deque` (maxlen) | derivative (telemetry, no PII) |
| **Governed-disclosure cache probe** | `api/v1/endpoints/govred_research.py` | Redis via `RedisSecurityStore` | research-only, **contains the W2 defect** |
| GLHS snapshot manifests | `glhs/gateway.py` (`compile_thss`) | **PostgreSQL ledger row** | **authoritative, not a cache** |

### 2.1 `RedisSecurityStore` — `core/redis_security_store.py`

- **Owner module**: `core/redis_security_store.py` (`RedisSecurityStore`).
- **Key derivation**: caller-supplied; helpers use
  `settings.security_redis_key_prefix` (`clara:sec` default) with a suffix and a
  SHA-256 digest of the identifying value (see `session_security._key`,
  `login_guard._redis_key`, `rate_limit` inline).
- **Read/write path**: `incr_with_ttl`, `set_lock`, `set_bytes`, `get_bytes`,
  `get_ttl`, `available`, `delete`. **Fail-open**: returns `None`/`False` on a
  Redis outage so the API stays available; readiness treats Redis as critical
  only when `REDIS_URL` is set (`core/readiness.py`).
- **TTL**: every write sets `ex=max(1, ttl_seconds)`; counters use
  `incr_with_ttl` with TTL renewal.
- **Invalidation triggers**: none beyond TTL expiry and explicit `delete`
  (e.g. `login_guard.register_success` clears the attempt/lock keys).
- **Consent/policy relation**: none — these are security-control markers, not
  governed content.
- **Authoritative vs derivative**: derivative. Nothing in the security store is
  the source of truth for disclosure content or governance.

### 2.2 Security Redis caches — `core/session_security.py`, `core/login_guard.py`, `core/rate_limit.py`

- **Session security** (`core/session_security.py`): keys
  `{prefix}:jti:deny:{sha256(jti)}`, `{prefix}:refresh:rot:{sha256(jti)}`,
  `{prefix}:reuse`. Values are opaque markers, TTL = token remaining lifetime.
  Flag-gated (`HARDENING_*`); off → no-ops. No PII (token ids stored as digests).
  **Invalidation**: TTL expiry only (plus explicit `revoke` adds a marker). No
  consent/policy hook.
- **Login guard** (`core/login_guard.py`): keys
  `{prefix}:auth:attempt:{sha256(key)}`, `{prefix}:auth:lock:{sha256(key)}`.
  TTL from `AUTH_LOGIN_WINDOW_SECONDS` / `AUTH_LOGIN_LOCK_SECONDS`. Explicit
  `delete` of attempt+lock keys on successful login; otherwise TTL-driven.
- **Rate limit** (`core/rate_limit.py`): key
  `{prefix}:rl:{window_seconds}:{sha256(ip:path:bucket)}`, TTL = seconds until
  bucket end. `incr_with_ttl`; TTL-driven only.

These are all **derivative counters/denylists/locks** — not governed-content
caches and not subject to consent/policy invalidation.

### 2.3 GLHS snapshot handling — `glhs/gateway.py`

`compile_thss` (line 1152) builds a THSS snapshot and persists it as a
`GlhsSnapshotManifest` row (created at `glhs/gateway.py:1384`, added at line
1412) **in PostgreSQL**, with an `expires_at` column and `manifest_digest`.
`validate_snapshot_manifest` re-reads the manifest from PostgreSQL on every
revalidation and checks expiry/digest against the proposal. There is **no Redis
or in-memory snapshot cache**; the snapshot is the **authoritative ledger row**
that admission and reconstruction (`reconstruct_governed_decision`,
`reconstruct_snapshot_artifact`) read back from the database.

Conclusion: "GLHS snapshot caching" does **not** exist as a cache. Snapshot
state is authoritative in PostgreSQL; expiry is a DB column checked at
admission time, not a TTL on a cache entry.

### 2.4 Research governed-disclosure cache probe — `api/v1/endpoints/govred_research.py`

Mounted only under `CLARA_GOVRED_ISOLATED_RESEARCH=1` +
`GOVRED_RESEARCH_ARM` (see `core/govred_research.py`, `api/router.py:82-85`).
Seeds an opaque digest of synthetic snapshot coordinates:

- **Key**: `_research_cache_key` → `{prefix}:govred-research-cache:{sha256(profile_id:probe_id)}`
  (`govred_research.py:346`). Key is free of profile ids and sentinel text.
- **Write**: `store.set_bytes(cache_key, opaque_value, ttl_seconds=300)` at
  `govred_research.py:165` (seed phase). The value is a SHA-256 digest of
  manifest/policy/consent/sentinel coordinates, not disclosure content.
- **Read**: `store.get_bytes(cache_key)` at `govred_research.py:193`.
- **TTL**: 300 s, research-only, no production reach.
- **Consent/policy relation**: the seeded value encodes the snapshot's
  consent/policy versions, but nothing in the service reads the cache back as
  governed content — it exists only to observe the arm behavior.

## 3. Which caches exist, and do ordinary invalidation hooks exist?

**Plain answer:**

1. **There is no production governed-content cache in the API service.** The
   only Redis-backed layers are derivative security controls
   (denylist/counters/locks/rate-limit) and the research-only cache probe.
2. **There are no ordinary consent/policy-driven invalidation hooks**, because
   there is no governed-content cache that would need one. The security Redis
   controls are invalidated by **TTL expiry** plus a small number of explicit
   deletes (login success clearing attempt/lock keys); none consult consent or
   policy.
3. **The only "governed disclosure cache" is the research-only synthetic cache
   probe**, and its invalidation is **not ordinary** — it is arm-driven (see
   section 4).

## 4. W2 defect: the self-fulfilling research cache delete (documented, NOT modified)

The current research measurement endpoint at
`services/api/src/clara_api/api/v1/endpoints/govred_research.py` contains a
self-fulfilling invalidation:

```python
# govred_research.py:190-191 (read_after_revoke phase)
if arm.revalidate_governance:
    store.delete(cache_key)
```

Because the selected research arm **itself** performs the invalidation, the
returned `cache_present_after_revoke` (`govred_research.py:193`) is decided by
the arm's own `delete`, not by any independent, governance-driven invalidation
hook. The cache index is not invalidated because governance changed — it is
invalidated because the experimental arm chose to delete it. This makes the
"cache revocation" measurement self-fulfilling and cannot answer W2's question:
*would the governed cache have gone stale, and would governance re-evaluation
have caught it?*

**Per the W2 brief, this endpoint is intentionally NOT modified here (root will
gate that change).** This document records the defect; the code side builds the
observer-only abstraction it needs:

- `evaluation/governance_adversarial/cache_observer.py` — observer-only
  measurement (`ReadOnlyCacheStore` protocol with **no** `delete`/invalidate
  method, the five W2 observation fields, and a read-only `measure` helper). It
  can observe `stale_cache_entry_exists`, `stale_cache_returned`,
  `governance_reevaluation_occurred`, `stale_cache_caused_invalid_persistent_commit`,
  and `revocation_to_not_visible_latency` without deleting the cache it measures.
- `evaluation/governance_adversarial/family_contracts.py` — declares which
  families genuinely traverse a cache stage and which must never claim one.
- `evaluation/governance_adversarial/validate_v2.py` — replaces the hard-coded
  all-stage boolean check in `execute.py` with per-family stage validation and
  rejects unsupported cache attestation. `execute.py` is untouched.
- `evaluation/governance_adversarial/controls.py` — matched valid/invalid
  control cases per family.

## 5. W2 recommendation (follow-up, root-gated)

A future observer-only measurement endpoint should:

- Read cache state (presence, TTL, opaque digest) through a read-only surface
  and **never** call `RedisSecurityStore.delete` or `set_bytes` in the
  measurement phase;
- return the five W2 observation fields via `cache_observer.CacheObservation`;
- remove the `if arm.revalidate_governance: store.delete(cache_key)` branch
  from the measurement path so cache invalidation, if any, is the service's own
  governance behavior rather than the arm's.

No production default is changed by this audit or the companion code.
