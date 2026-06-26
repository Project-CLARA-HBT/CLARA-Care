import {
  DdiRiskLevel,
  DdiUserAlert,
  DdiUserSource,
  DdiUserView
} from "@/lib/careguard";

/**
 * CareGuard offline / degraded-mode client fallback (CLARA_Web).
 *
 * When `CAREGUARD_OFFLINE_FALLBACK_ENABLED` is on and a fresh DDI check cannot
 * reach the API, the client renders the last successfully retrieved
 * `DdiUserView`, clearly labeled "offline / không phải thời gian thực" so the
 * user knows the result is stale (Requirement 6.3).
 *
 * Safety boundaries baked into this module:
 *  - **Default OFF.** With the flag off, `cacheDdiUserView` and
 *    `readCachedDdiView` are no-ops/return `null`, so behavior is byte-for-byte
 *    unchanged (Requirement 12.1, 12.2).
 *  - **Projection only.** Only the End_User `DdiUserView` is cached, and even
 *    then it is re-projected to its four user-facing fields before persisting,
 *    so no runtime mode, fallback flag, connector identifier, or `source_errors`
 *    fragment can ever be written to client storage (Requirement 3.4, 6.2).
 *  - **No fabricated all-clear.** A cache miss returns `null`; the caller shows
 *    its normal error instead of inventing a "no interaction" result
 *    (Requirement 6.4).
 */

/** Vietnamese-first label shown on a stale, offline-served DDI result (Req 6.3). */
export const CAREGUARD_OFFLINE_LABEL = "offline / không phải thời gian thực";

const TRUTHY = new Set(["1", "true", "on"]);

/**
 * Whether the client offline/last-known DDI fallback is enabled. Reads the
 * client-readable `NEXT_PUBLIC_CAREGUARD_OFFLINE_FALLBACK_ENABLED` flag and
 * defaults to OFF (any non-truthy value preserves current behavior).
 */
export function isCareguardOfflineFallbackEnabled(): boolean {
  const value = process.env.NEXT_PUBLIC_CAREGUARD_OFFLINE_FALLBACK_ENABLED;
  if (typeof value !== "string") return false;
  return TRUTHY.has(value.trim().toLowerCase());
}

/** Storage key for the last-known DDI user view. */
export const CAREGUARD_OFFLINE_CACHE_KEY = "clara.careguard.ddi.last_known_view";

/** Schema version so an incompatible cache shape is ignored, not mis-rendered. */
const CACHE_VERSION = 1;

/** A persisted last-known DDI view plus the time it was captured. */
export type CachedDdiView = {
  version: number;
  cachedAt: string;
  view: DdiUserView;
};

/** Minimal Web Storage surface so callers/tests can inject their own store. */
export type CareguardCacheStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const VALID_RISK_LEVELS: ReadonlySet<DdiRiskLevel> = new Set([
  "low",
  "medium",
  "high",
  "critical",
  "unknown"
]);

function resolveStorage(explicit?: CareguardCacheStorage | null): CareguardCacheStorage | null {
  if (explicit) return explicit;
  try {
    const candidate = (globalThis as { localStorage?: CareguardCacheStorage }).localStorage;
    return candidate ?? null;
  } catch {
    // Accessing localStorage can throw in restricted/SSR contexts.
    return null;
  }
}

function projectAlertForCache(alert: DdiUserAlert): DdiUserAlert {
  const severity: DdiRiskLevel = VALID_RISK_LEVELS.has(alert.severity) ? alert.severity : "unknown";
  const projected: DdiUserAlert = { message: String(alert.message ?? ""), severity };
  if (typeof alert.details === "string" && alert.details.trim()) {
    projected.details = alert.details;
  }
  return projected;
}

function projectSourceForCache(source: DdiUserSource): DdiUserSource {
  const projected: DdiUserSource = { label: String(source.label ?? "") };
  if (typeof source.url === "string" && source.url.trim()) {
    projected.url = source.url;
  }
  return projected;
}

/**
 * Re-project an arbitrary `DdiUserView` down to exactly its four user-facing
 * fields, dropping anything else. This guarantees that only the End_User
 * projection — never an internal/diagnostic field — is persisted to the cache.
 */
export function projectDdiViewForCache(view: DdiUserView): DdiUserView {
  return {
    riskLevel: VALID_RISK_LEVELS.has(view.riskLevel) ? view.riskLevel : "unknown",
    alerts: Array.isArray(view.alerts) ? view.alerts.map(projectAlertForCache) : [],
    recommendations: Array.isArray(view.recommendations)
      ? view.recommendations.filter((item): item is string => typeof item === "string")
      : [],
    sources: Array.isArray(view.sources) ? view.sources.map(projectSourceForCache) : []
  };
}

/**
 * Persist the last successfully retrieved DDI user view. No-op when the flag is
 * off or no storage is available. Returns `true` only when a value was written.
 */
export function cacheDdiUserView(
  view: DdiUserView,
  options?: { storage?: CareguardCacheStorage | null; now?: Date }
): boolean {
  if (!isCareguardOfflineFallbackEnabled()) return false;
  const storage = resolveStorage(options?.storage);
  if (!storage) return false;
  const payload: CachedDdiView = {
    version: CACHE_VERSION,
    cachedAt: (options?.now ?? new Date()).toISOString(),
    view: projectDdiViewForCache(view)
  };
  try {
    storage.setItem(CAREGUARD_OFFLINE_CACHE_KEY, JSON.stringify(payload));
    return true;
  } catch {
    return false;
  }
}

function isValidView(value: unknown): value is DdiUserView {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.riskLevel === "string" &&
    Array.isArray(record.alerts) &&
    Array.isArray(record.recommendations) &&
    Array.isArray(record.sources)
  );
}

/**
 * Read the last-known DDI user view, or `null` when the flag is off, no cache
 * exists, or the stored value is missing/invalid. Never fabricates a result.
 * The returned view is re-projected so a tampered cache cannot leak internals.
 */
export function readCachedDdiView(options?: {
  storage?: CareguardCacheStorage | null;
}): CachedDdiView | null {
  if (!isCareguardOfflineFallbackEnabled()) return null;
  const storage = resolveStorage(options?.storage);
  if (!storage) return null;
  let raw: string | null = null;
  try {
    raw = storage.getItem(CAREGUARD_OFFLINE_CACHE_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<CachedDdiView>;
    if (!parsed || parsed.version !== CACHE_VERSION) return null;
    if (typeof parsed.cachedAt !== "string" || !isValidView(parsed.view)) return null;
    return {
      version: CACHE_VERSION,
      cachedAt: parsed.cachedAt,
      view: projectDdiViewForCache(parsed.view)
    };
  } catch {
    return null;
  }
}

/** Remove any cached last-known DDI view. */
export function clearCachedDdiView(options?: { storage?: CareguardCacheStorage | null }): void {
  const storage = resolveStorage(options?.storage);
  if (!storage) return;
  try {
    storage.removeItem(CAREGUARD_OFFLINE_CACHE_KEY);
  } catch {
    // Ignore removal failures; a stale entry is re-validated on read.
  }
}

const OFFLINE_MESSAGE_MARKERS = [
  "network error",
  "failed to fetch",
  "load failed",
  "err_network",
  "err_internet_disconnected",
  "err_connection",
  "econnrefused",
  "econnaborted",
  "enotfound",
  "etimedout",
  "timeout",
  "quá thời gian chờ",
  "gateway",
  "502",
  "503",
  "504"
];

function resolveErrorMessage(cause: unknown): string {
  if (typeof cause === "string") return cause;
  if (cause instanceof Error) return cause.message;
  if (cause && typeof cause === "object") {
    const record = cause as Record<string, unknown>;
    if (typeof record.message === "string") return record.message;
    if (typeof record.code === "string") return record.code;
  }
  return "";
}

/**
 * Heuristic: did this failure look like the client could not reach the API
 * (offline / network / timeout / gateway), as opposed to a normal server-side
 * rejection? When the browser reports it is offline we treat any failure as
 * offline; otherwise we match well-known network/timeout/gateway markers.
 */
export function isLikelyOfflineError(cause: unknown): boolean {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return true;
  }
  const message = resolveErrorMessage(cause).toLowerCase();
  if (!message) return false;
  return OFFLINE_MESSAGE_MARKERS.some((marker) => message.includes(marker));
}
