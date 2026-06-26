/**
 * Feature-flag gate for the CLARA Chat redesign (CHAT_V2).
 *
 * The rebuilt, componentized chat (`app/chat/_v2`) is the DEFAULT experience as
 * of the production rollout (clara-chat-redesign task 8.3). The route serves the
 * v2 shell unless the flag is explicitly turned OFF, in which case it falls back
 * to the legacy implementation (`app/chat/_legacy/page-legacy.tsx`) byte-for-byte
 * unchanged (Requirement 8.1, 8.6; design Property P1 — flag isolation).
 *
 * The flag is read from the public, build-time-inlined env var
 * `NEXT_PUBLIC_CHAT_V2`:
 *   - unset / empty / unknown / opt-in (`"1"`, `"true"`, `"on"`) → ON  (v2, default)
 *   - explicit opt-out (`"0"`, `"false"`, `"off"`, case-insensitive)  → OFF (legacy)
 *
 * Defaulting ON keeps the rebuilt chat live everywhere while preserving an
 * instant, env-only rollback: set `NEXT_PUBLIC_CHAT_V2=false` (or `0`/`off`) in
 * any environment to restore the legacy page without a code change.
 */

const TRUTHY_FLAG_VALUES = new Set(["1", "true", "on"]);
const FALSY_FLAG_VALUES = new Set(["0", "false", "off"]);

/**
 * Normalizes an arbitrary flag value (env string or otherwise) into a boolean,
 * defaulting to ON. Only an explicit opt-out value disables the redesign.
 * Exported for direct unit testing without depending on `process.env`.
 */
export function parseChatV2Flag(value: string | null | undefined): boolean {
  if (typeof value !== "string") return true;
  const normalized = value.trim().toLowerCase();
  if (FALSY_FLAG_VALUES.has(normalized)) return false;
  if (TRUTHY_FLAG_VALUES.has(normalized)) return true;
  // Unset / empty / unrelated values resolve to ON (the default-on rollout).
  return true;
}

/**
 * Whether the CHAT_V2 redesign should be served. Defaults to ON (v2) unless
 * `NEXT_PUBLIC_CHAT_V2` is explicitly set to an opt-out value for rollback.
 */
export function isChatV2Enabled(): boolean {
  return parseChatV2Flag(process.env.NEXT_PUBLIC_CHAT_V2);
}
