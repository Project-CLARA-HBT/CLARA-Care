import { afterEach, beforeEach, describe, expect, it } from "vitest";
import fc from "fast-check";

import type { DdiUserView } from "@/lib/careguard";
import {
  CAREGUARD_OFFLINE_CACHE_KEY,
  CAREGUARD_OFFLINE_LABEL,
  type CareguardCacheStorage,
  cacheDdiUserView,
  clearCachedDdiView,
  isCareguardOfflineFallbackEnabled,
  isLikelyOfflineError,
  projectDdiViewForCache,
  readCachedDdiView
} from "@/lib/careguard-offline";

/**
 * Feature: clara-selfmed-careguard-upgrade — Task 8.2 (Req 6.3).
 *
 * The client caches the last-known End_User DDI projection and renders it
 * labeled "offline / không phải thời gian thực" when the API is unreachable,
 * gated behind CAREGUARD_OFFLINE_FALLBACK_ENABLED (default OFF). Caching the
 * projection only — never internal diagnostic fields — and never fabricating an
 * all-clear are the load-bearing safety properties pinned here.
 */

const FLAG_KEY = "NEXT_PUBLIC_CAREGUARD_OFFLINE_FALLBACK_ENABLED";

function memoryStorage(): CareguardCacheStorage & { map: Map<string, string> } {
  const map = new Map<string, string>();
  return {
    map,
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
    removeItem: (key: string) => {
      map.delete(key);
    }
  };
}

const SAMPLE_VIEW: DdiUserView = {
  riskLevel: "high",
  alerts: [
    {
      message: "Phối hợp này có thể làm tăng nguy cơ chảy máu.",
      details: "Theo dõi dấu hiệu chảy máu.",
      severity: "high"
    }
  ],
  recommendations: ["Hỏi bác sĩ hoặc dược sĩ."],
  sources: [{ label: "Nguồn cục bộ" }]
};

let originalFlag: string | undefined;

beforeEach(() => {
  originalFlag = process.env[FLAG_KEY];
});

afterEach(() => {
  if (originalFlag === undefined) {
    delete process.env[FLAG_KEY];
  } else {
    process.env[FLAG_KEY] = originalFlag;
  }
});

describe("isCareguardOfflineFallbackEnabled (default OFF)", () => {
  it("is OFF when unset or non-truthy", () => {
    delete process.env[FLAG_KEY];
    expect(isCareguardOfflineFallbackEnabled()).toBe(false);
    for (const value of ["", "0", "false", "off", "no", "enabled"]) {
      process.env[FLAG_KEY] = value;
      expect(isCareguardOfflineFallbackEnabled()).toBe(false);
    }
  });

  it("is ON only for explicit truthy opt-in values", () => {
    for (const value of ["1", "true", "on", "TRUE", " On "]) {
      process.env[FLAG_KEY] = value;
      expect(isCareguardOfflineFallbackEnabled()).toBe(true);
    }
  });
});

describe("cache is inert when the flag is OFF (Req 12.1, 12.2)", () => {
  it("does not write when off and never reads back a value", () => {
    delete process.env[FLAG_KEY];
    const storage = memoryStorage();
    expect(cacheDdiUserView(SAMPLE_VIEW, { storage })).toBe(false);
    expect(storage.map.size).toBe(0);
    expect(readCachedDdiView({ storage })).toBeNull();
  });

  it("ignores a pre-existing cache entry while off (no leakage of stale data)", () => {
    process.env[FLAG_KEY] = "true";
    const storage = memoryStorage();
    cacheDdiUserView(SAMPLE_VIEW, { storage });
    delete process.env[FLAG_KEY];
    expect(readCachedDdiView({ storage })).toBeNull();
  });
});

describe("cache round-trip when the flag is ON (Req 6.3)", () => {
  beforeEach(() => {
    process.env[FLAG_KEY] = "true";
  });

  it("writes under the expected key and reads back the projection + timestamp", () => {
    const storage = memoryStorage();
    const now = new Date("2024-01-02T03:04:05.000Z");
    expect(cacheDdiUserView(SAMPLE_VIEW, { storage, now })).toBe(true);
    expect(storage.map.has(CAREGUARD_OFFLINE_CACHE_KEY)).toBe(true);

    const cached = readCachedDdiView({ storage });
    expect(cached).not.toBeNull();
    expect(cached?.cachedAt).toBe(now.toISOString());
    expect(cached?.view).toEqual(SAMPLE_VIEW);
  });

  it("returns null on a cache miss (never fabricates an all-clear, Req 6.4)", () => {
    const storage = memoryStorage();
    expect(readCachedDdiView({ storage })).toBeNull();
  });

  it("ignores a tampered/invalid cache payload", () => {
    const storage = memoryStorage();
    storage.map.set(CAREGUARD_OFFLINE_CACHE_KEY, "{not json");
    expect(readCachedDdiView({ storage })).toBeNull();
    storage.map.set(CAREGUARD_OFFLINE_CACHE_KEY, JSON.stringify({ version: 999, view: SAMPLE_VIEW }));
    expect(readCachedDdiView({ storage })).toBeNull();
  });

  it("clears the cached view", () => {
    const storage = memoryStorage();
    cacheDdiUserView(SAMPLE_VIEW, { storage });
    clearCachedDdiView({ storage });
    expect(readCachedDdiView({ storage })).toBeNull();
  });
});

describe("projectDdiViewForCache drops non-projection fields (Req 3.4, 6.2)", () => {
  it("keeps only the four user-facing fields, stripping injected internals", () => {
    const polluted = {
      ...SAMPLE_VIEW,
      mode: "external_plus_local",
      fallback_used: true,
      source_errors: { openfda: ["openfda http_400"] },
      alerts: [
        {
          message: "Phối hợp này có thể làm tăng nguy cơ chảy máu.",
          severity: "high",
          // Internal/diagnostic fields that must not be persisted.
          sources: ["openfda", "rxnav"],
          rawSeverity: "critical"
        }
      ]
    } as unknown as DdiUserView;

    const projected = projectDdiViewForCache(polluted);
    expect(Object.keys(projected).sort()).toEqual(
      ["alerts", "recommendations", "riskLevel", "sources"].sort()
    );
    expect(Object.keys(projected.alerts[0]).sort()).toEqual(["message", "severity"].sort());
    const json = JSON.stringify(projected).toLowerCase();
    for (const leak of ["mode", "fallback", "source_errors", "openfda", "rxnav", "rawseverity"]) {
      expect(json.includes(leak)).toBe(false);
    }
  });

  it("Property: cached payload never contains internal markers for any view", () => {
    process.env[FLAG_KEY] = "true";
    const internalMarker = "openfda";
    const alertArb = fc.record(
      {
        message: fc.constantFrom(
          "Phối hợp này có thể làm tăng nguy cơ chảy máu.",
          "Phối hợp này có thể làm tăng kali máu."
        ),
        severity: fc.constantFrom("low", "medium", "high", "critical", "unknown"),
        // Adversarial internal fields a caller might smuggle in.
        details: fc.option(fc.constantFrom("Theo dõi triệu chứng.", "openfda http_400"), { nil: undefined }),
        source_errors: fc.constant({ openfda: ["openfda http_400"] }),
        mode: fc.constantFrom("local_only", "external_plus_local")
      },
      { requiredKeys: ["message", "severity"] }
    );
    const viewArb = fc.record({
      riskLevel: fc.constantFrom("low", "medium", "high", "critical", "unknown"),
      alerts: fc.array(alertArb, { maxLength: 4 }),
      recommendations: fc.array(fc.constantFrom("Hỏi bác sĩ.", "Theo dõi triệu chứng."), { maxLength: 3 }),
      sources: fc.array(fc.record({ label: fc.constantFrom("Nguồn cục bộ", "OpenFDA") }), { maxLength: 3 })
    });

    fc.assert(
      fc.property(viewArb, (view) => {
        const storage = memoryStorage();
        cacheDdiUserView(view as unknown as DdiUserView, { storage });
        const stored = storage.map.get(CAREGUARD_OFFLINE_CACHE_KEY) ?? "";
        // The `details`/`label` copy may legitimately contain text, but the
        // structural internal keys must never be persisted.
        const parsed = JSON.parse(stored) as { view: Record<string, unknown> };
        const alertKeys = (parsed.view.alerts as Record<string, unknown>[]).flatMap((a) => Object.keys(a));
        return (
          !alertKeys.includes("source_errors") &&
          !alertKeys.includes("mode") &&
          !Object.keys(parsed.view).includes("source_errors") &&
          !Object.keys(parsed.view).includes(internalMarker)
        );
      }),
      { numRuns: 200 }
    );
  });
});

describe("isLikelyOfflineError", () => {
  it("matches network/timeout/gateway failures", () => {
    expect(isLikelyOfflineError(new Error("Network Error"))).toBe(true);
    expect(isLikelyOfflineError(new Error("Yêu cầu xử lý quá thời gian chờ. Vui lòng thử lại."))).toBe(true);
    expect(isLikelyOfflineError("Failed to fetch")).toBe(true);
    expect(isLikelyOfflineError({ code: "ERR_NETWORK" })).toBe(true);
    expect(isLikelyOfflineError(new Error("Dich vu tam thoi gian doan (502)."))).toBe(true);
  });

  it("does not treat a normal server rejection as offline", () => {
    expect(isLikelyOfflineError(new Error("Bạn cần chấp nhận điều khoản trước khi sử dụng."))).toBe(false);
    expect(isLikelyOfflineError(new Error("Cần ít nhất 2 thuốc để kiểm tra tương tác."))).toBe(false);
    expect(isLikelyOfflineError("")).toBe(false);
  });
});

describe("CAREGUARD_OFFLINE_LABEL", () => {
  it("is the Vietnamese-first stale-result label", () => {
    expect(CAREGUARD_OFFLINE_LABEL).toBe("offline / không phải thời gian thực");
  });
});
