# Runbook: Credential rotation & managed-secret-store migration

Spec: `clara-platform-hardening` · Task 2.2 (author the credential-rotation
runbook).

This runbook is the documented procedure for rotating **every CLARA-Care
secret** and migrating each one out of plaintext compose/workflow defaults into a
**managed secret store**. It covers the JWT signing key (with the key-overlap
window that avoids a forced mass logout), the ML internal API key, the database
password, the bootstrap admin password, the object-store (MinIO) and graph-store
(Neo4j) credentials, the LLM/embedding provider keys, and the **deploy SSH
credential that was exposed in plaintext in an operator transcript** — including
its mandatory one-time rotation and the move to key-based SSH authentication
(Requirement 1.1–1.7; design §A).

This is **the procedure only**. Running it performs live rotation; nothing in
this document rotates a secret by itself. Treat every step as an operator action
to be executed during a maintenance window with the rollback notes in hand.

The model is always: **stage the new value in the secret store → inject it into
the target environment → redeploy → verify → invalidate the prior value →
record the rotation as completed.**

## Principles

- **No plaintext defaults.** No production secret is ever sourced from a
  `${VAR:-value}` shell default in a compose file or workflow, from a committed
  file, a build/CI log, or a container image layer (Requirement 1.1, 1.6;
  design Property P2). Production secrets are injected at deploy time from the
  managed secret store via the `:?required` pattern already used in
  `deploy/docker/docker-compose.deploy.yml`.
- **Fail fast, never fall back.** A required production secret left absent must
  cause a descriptive, **secret-value-free** startup failure rather than a start
  with an insecure default (Requirement 1.2; design Property P3). The startup
  guards in `services/api/src/clara_api/main.py` already reject `change-me` JWT
  keys and insecure bootstrap passwords in production.
- **Exposure ⇒ mandatory rotation.** Any secret identified as exposed must be
  rotated and the rotation recorded as completed (Requirement 1.4). The deploy
  SSH credential below is in this state today.
- **Invalidate the old value.** Rotation is not complete until the prior value
  is revoked/retired and confirmed unusable, except where a deliberate overlap
  window applies (the JWT signing key).

## Managed secret store

"Managed secret store" is the environment's external system of record for
secrets — a cloud secret manager, HashiCorp Vault, or GitHub Actions encrypted
secrets injected at deploy time. CLARA-Care's CD pipeline
(`.github/workflows/cd.yml`) already assembles the runtime `.env` for the
deploy stack from the `DEPLOY_ENV_FILE` GitHub encrypted secret and writes it on
the runner only at deploy time; the stack is then brought up with
`docker compose --env-file .env -f deploy/docker/docker-compose.deploy.yml`.

The secret store is the **only** place a secret's canonical value lives.
Operators read from and write to the store; they do not paste secret values into
chat, tickets, terminals that log to shared history, or committed files.

## Secret inventory

Every production secret, its store key, where it is consumed, and the rotation
class. Names match the deploy stack and `.env.example`.

| Secret | Env var(s) | Consumed by | Store location | Rotation class |
| --- | --- | --- | --- | --- |
| JWT signing key | `JWT_SECRET_KEY` (+ `JWT_SECRET_KEY_PREVIOUS` for overlap) | API auth (`core/security`) | secret store → `DEPLOY_ENV_FILE` | **Overlap window** |
| ML internal API key | `ML_INTERNAL_API_KEY` | API → ML calls; ML internal-key guard | secret store → `DEPLOY_ENV_FILE` | Coordinated (two services) |
| Database password | `POSTGRES_PASSWORD` (+ `DATABASE_URL`) | Postgres, API | secret store → `DEPLOY_ENV_FILE` | Datastore (alter role) |
| Bootstrap admin password | `AUTH_BOOTSTRAP_ADMIN_PASSWORD` | API bootstrap | secret store → `DEPLOY_ENV_FILE` | Account credential |
| Object-store credential | `MINIO_ROOT_PASSWORD` (+ `MINIO_ROOT_USER`) | MinIO, API uploads | secret store → `DEPLOY_ENV_FILE` | Datastore |
| Graph-store credential | `NEO4J_AUTH` / `NEO4J_PASSWORD` | Neo4j, API graph client | secret store → `DEPLOY_ENV_FILE` | Datastore |
| LLM provider key | `DEEPSEEK_API_KEY` (+ `YESCALE_API_KEY`) | ML → offshore LLM | secret store → `DEPLOY_ENV_FILE` | Provider-issued |
| Embedding provider key | `EMBEDDING_API_KEY` | ML → embedding endpoint | secret store → `DEPLOY_ENV_FILE` | Provider-issued |
| Deploy SSH credential | CI deploy key (private key) | CD deploy to host | CI encrypted secret only | **Exposed — rotate now; move to key-based** |

> Plaintext defaults to remove from `deploy/docker/docker-compose.app.yml` (Task
> 2.1, tracked separately): `JWT_SECRET_KEY:-change_me_super_secret`,
> `AUTH_BOOTSTRAP_ADMIN_PASSWORD:-Clara#Admin2026!`,
> `ML_INTERNAL_API_KEY:-clara_internal_key_default_2026`,
> `POSTGRES_PASSWORD:-clara_dev_password`, `MINIO_ROOT_PASSWORD:-minioadmin`,
> `NEO4J_AUTH:-neo4j/clara_dev_password`. This runbook assumes those defaults are
> being removed in favour of `:?required` injection.

## Rotation cadence

| Class | Routine cadence | On exposure |
| --- | --- | --- |
| JWT signing key | Every 90 days | Immediate (overlap window) |
| ML internal API key | Every 90 days | Immediate (coordinated) |
| Database / object-store / graph-store | Every 180 days | Immediate |
| Bootstrap admin password | Every 90 days | Immediate |
| LLM / embedding provider keys | Per provider policy, ≤ 180 days | Immediate (reissue) |
| Deploy SSH credential | Every 180 days | **Immediate — see one-time action below** |

On any suspected exposure, rotation is mandatory regardless of cadence
(Requirement 1.4).

---

## Immediate one-time action — exposed deploy SSH credential

**Status: exposed. Rotation is mandatory and must be completed before the next
deploy.** The deploy SSH **password** was disclosed in plaintext in an operator
transcript (Requirement 1.5; design §A). It must be rotated **and** SSH password
authentication must be replaced with key-based authentication whose private key
lives only in the managed secret store / CI encrypted secrets.

1. **Treat the exposed password as compromised.** Assume the disclosed value is
   known. Do not reuse it anywhere.
2. **Generate a deploy key pair** (ed25519) on a trusted machine:
   ```
   ssh-keygen -t ed25519 -C "clara-care-deploy" -f clara_deploy_key -N ""
   ```
   Keep `clara_deploy_key` (private) off disk longer than necessary; you will
   move it straight into the secret store.
3. **Install the public key** on the deploy host for the deploy user:
   append `clara_deploy_key.pub` to that user's `~/.ssh/authorized_keys`
   (mode `600`, `~/.ssh` mode `700`).
4. **Disable password authentication** on the deploy host's SSH daemon:
   set `PasswordAuthentication no` (and `ChallengeResponseAuthentication no`) in
   `sshd_config`, then reload `sshd`. Keep a separate console/break-glass path
   open until step 7 verifies key auth works.
5. **Store the private key in the managed secret store / CI encrypted secrets**
   (e.g. a `DEPLOY_SSH_PRIVATE_KEY` GitHub encrypted secret). The private key
   must exist **only** there — never in a committed file, workflow body, log, or
   image layer (Requirement 1.6).
6. **Rotate the host account password** anyway (to a strong store-held value),
   so the disclosed password is invalid even though password login is now
   disabled.
7. **Verify** a deploy-style SSH connection succeeds using the key and **fails**
   using any password:
   ```
   ssh -i clara_deploy_key -o PreferredAuthentications=publickey <deploy-user>@<host> "echo ok"
   ssh -o PreferredAuthentications=password <deploy-user>@<host> "echo nope"   # must be rejected
   ```
8. **Securely destroy** the local copy of the private key once it is confirmed in
   the secret store and working (`shred`/secure-delete `clara_deploy_key`).
9. **Record completion** in the rotation log below: the exposed SSH password is
   rotated, password auth is disabled, and the deploy now uses a key held only in
   the managed secret store / CI encrypted secrets (Requirement 1.4, 1.5).

---

## JWT signing key — rotation with key-overlap window

The JWT signing key is rotated **without forcing a mass logout** by accepting the
prior key for verification until tokens signed with it expire naturally
(Requirement 1.7; design §A). Access tokens are short-lived
(`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30); refresh tokens live up to
`REFRESH_TOKEN_EXPIRE_MINUTES` (default 43200 min ≈ 30 days). The overlap window
must be **at least the longest-lived token's remaining lifetime** so no valid
token is rejected mid-window.

1. **Generate** a new high-entropy signing key in the secret store as the new
   `JWT_SECRET_KEY`.
2. **Move the current key to the previous slot.** Set `JWT_SECRET_KEY_PREVIOUS`
   to the value currently in `JWT_SECRET_KEY`. New tokens are signed with the new
   key; verification accepts **both** the new key and the previous key during the
   window.
3. **Inject and redeploy** the API with both values present. New issuance uses
   the new key immediately; tokens signed with the prior key keep verifying.
4. **Hold the overlap window** for at least the refresh-token lifetime (≈ 30 days
   with defaults, or your configured value). Do not shorten this below the
   longest-lived issued token, or holders of still-valid tokens are logged out.
5. **Close the window:** once no token signed with the prior key can still be
   valid, remove `JWT_SECRET_KEY_PREVIOUS` from the store and redeploy. The prior
   key is now fully invalidated (Requirement 1.3).
6. **Verify** that a token minted before rotation no longer verifies after the
   window closes, and that current sessions are unaffected throughout.
7. **Record completion** in the rotation log.

> Emergency variant (key believed compromised, no graceful window acceptable):
> rotate `JWT_SECRET_KEY` **without** populating `JWT_SECRET_KEY_PREVIOUS`. This
> invalidates every existing token immediately and forces re-authentication.
> Use only when the exposure outweighs the mass-logout cost.

## ML internal API key — coordinated two-service rotation

`ML_INTERNAL_API_KEY` is shared: the API sends it and the ML internal-key guard
validates it on protected prefixes (Requirement 3.5). Rotate it as a coordinated
pair so calls are never rejected mid-rotation.

1. **Generate** the new key in the secret store.
2. **Inject the new value into both** the API and ML environments in the same
   change set (`docker-compose.deploy.yml` sources both from `DEPLOY_ENV_FILE`).
3. **Redeploy ML first, then the API** (or both together) so the validator
   accepts the new key before the caller starts sending it.
4. **Verify** an authenticated API→ML internal call succeeds and that a call
   bearing the old key is rejected.
5. **Invalidate** the old value by removing it from the store; confirm no
   environment still references it.
6. **Record completion** in the rotation log.

## Database password — `POSTGRES_PASSWORD`

1. **Generate** the new password in the secret store.
2. **Change the role password** in Postgres:
   ```
   ALTER ROLE clara WITH PASSWORD '<new-value-from-store>';
   ```
3. **Update** `POSTGRES_PASSWORD` and the embedded credential in `DATABASE_URL`
   in the secret store / `DEPLOY_ENV_FILE` to the new value.
4. **Redeploy** the API so it reconnects with the new credential
   (`pool_pre_ping` revalidates pooled connections).
5. **Verify** the readiness probe / a `SELECT 1` succeeds and the old password no
   longer authenticates.
6. **Record completion** in the rotation log.

> Same pattern for the **object-store** (`MINIO_ROOT_PASSWORD`) and
> **graph-store** (`NEO4J_AUTH` / `NEO4J_PASSWORD`): set the new value on the
> datastore, update the store-held env var, redeploy the consumer, verify
> connectivity, invalidate the old value, record completion.

## Bootstrap admin password — `AUTH_BOOTSTRAP_ADMIN_PASSWORD`

1. **Generate** the new password in the secret store.
2. **Update** `AUTH_BOOTSTRAP_ADMIN_PASSWORD` in the store / `DEPLOY_ENV_FILE`.
3. **Redeploy** the API. With `AUTH_BOOTSTRAP_ADMIN_FORCE_RESET_PASSWORD=true`
   the bootstrap admin password is reset to the new value on start.
4. **Verify** login with the new credential succeeds and the old one fails.
5. **Record completion** in the rotation log.

## LLM / embedding provider keys — `DEEPSEEK_API_KEY`, `EMBEDDING_API_KEY`

Provider keys are reissued at the provider, then swapped in.

1. **Issue** a new key in the provider console (YEScale / DeepSeek / embedding
   provider). If the provider supports overlapping keys, keep the old key active
   until step 4.
2. **Update** `DEEPSEEK_API_KEY` / `EMBEDDING_API_KEY` (and `YESCALE_API_KEY`
   where used) in the secret store / `DEPLOY_ENV_FILE`.
3. **Redeploy** the ML service so outbound LLM/embedding calls use the new key.
4. **Verify** a synthesis call and an embedding call succeed, then **revoke** the
   old key at the provider.
5. **Record completion** in the rotation log.

---

## Post-rotation verification (every rotation)

After any rotation, before recording it complete:

- The target service starts cleanly with the new value injected from the store;
  no startup guard fires and no plaintext default is in effect
  (Requirement 1.2).
- The dependent path works end-to-end (login for JWT/bootstrap, API→ML for the
  internal key, `SELECT 1`/readiness for the DB, an upload for MinIO, a graph
  query for Neo4j, a synthesis/embedding call for provider keys).
- The **old value is confirmed unusable** (except the JWT key during its
  deliberate overlap window).
- No secret value appears in any committed file, build/CI log, container image
  layer, ticket, or chat (Requirement 1.6; design Property P2). Scan the deploy
  stack and workflows to confirm no usable plaintext default remains.

## Rollback

Rotation changes are config-only at the platform layer (new value injected from
the store + redeploy); the rollback for a botched rotation is to **re-inject the
prior value and redeploy**, except:

- **JWT key:** if a new key misbehaves, restore the prior `JWT_SECRET_KEY` from
  the store and redeploy; the overlap design means previously-issued tokens stay
  valid. Never roll back by widening the overlap window beyond a token lifetime.
- **Datastore passwords:** rollback requires re-applying the prior password on
  the datastore itself (`ALTER ROLE ...`) **and** in the store, since the live
  value was changed on the server. Keep the prior value retrievable in the store
  until post-rotation verification passes, then invalidate it.
- **Deploy SSH credential:** do **not** roll back to password auth. If the new
  key fails, generate and install another key via the break-glass console path;
  password authentication stays disabled.

## Rotation log

Record each rotation here (or in the environment's secret-store audit). No secret
values — store metadata only: secret name, environment, date, operator, and
whether the prior value was invalidated. This is the record that satisfies
"rotation recorded as completed" (Requirement 1.4).

| Date | Secret | Environment | Operator | Prior value invalidated? | Notes |
| --- | --- | --- | --- | --- | --- |
| _pending_ | Deploy SSH credential | production | _ops_ | _yes — password auth disabled, moved to key-based; private key in CI encrypted secrets_ | Exposed in operator transcript (Requirement 1.5). Complete before next deploy. |

## Notes

- This runbook documents the procedure; it does not perform live rotation. Run
  each section deliberately, during a maintenance window where a redeploy is
  acceptable, with the rollback notes to hand.
- Removing the plaintext compose defaults (Task 2.1) and extending the startup
  secret guards / JWT dual-key validation (Task 2.4) are companion tasks; this
  runbook assumes secrets are injected via the `:?required` pattern and that the
  production guards fail fast on an absent or insecure secret.
- The only rotation with a deliberate "old value still valid" window is the JWT
  signing key (key-overlap, Requirement 1.7). Every other rotation ends with the
  prior value invalidated.
