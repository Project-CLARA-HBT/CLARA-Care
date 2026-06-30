import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// `vi.mock` is hoisted; create the mock fns inside `vi.hoisted` so the factory
// can reference them safely.
const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/lib/http-client", () => ({ default: { get, post } }));

import {
  grantConsent,
  isDsarEnabled,
  isGranularConsentEnabled,
  isTransparencyNoticeEnabled,
  listAdminDsarQueue,
  listConsents,
  listDsarRequests,
  requestDsarDelete,
  requestDsarExport,
  submitDsarRequest,
  updateDsarStatus,
  withdrawConsent,
} from "@/lib/compliance";

/**
 * Feature: regulatory-compliance, Requirement 8.1, 8.2 (flag defaults preserve
 * current behavior).
 *
 * The web compliance surfaces activate ONLY when their `NEXT_PUBLIC_COMPLIANCE_*`
 * flag is explicitly enabled. These tests pin the default-OFF semantics so the
 * Consent Center / DSAR / transparency gate never alter behavior unless opted in.
 */

const ENV_KEYS = [
  "NEXT_PUBLIC_COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED",
  "NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED",
  "NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED",
] as const;

const originalEnv: Record<string, string | undefined> = {};

beforeEach(() => {
  for (const key of ENV_KEYS) {
    originalEnv[key] = process.env[key];
    delete process.env[key];
  }
});

afterEach(() => {
  for (const key of ENV_KEYS) {
    if (originalEnv[key] === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = originalEnv[key];
    }
  }
  vi.restoreAllMocks();
});

describe("compliance feature flags", () => {
  it("default to OFF when unset", () => {
    expect(isTransparencyNoticeEnabled()).toBe(false);
    expect(isGranularConsentEnabled()).toBe(false);
    expect(isDsarEnabled()).toBe(false);
  });

  it("only treats explicit opt-in values as enabled", () => {
    for (const value of ["1", "true", "on", "TRUE", " On "]) {
      process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED = value;
      expect(isDsarEnabled()).toBe(true);
    }
    for (const value of ["0", "false", "off", "", "yes", "enabled"]) {
      process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED = value;
      expect(isDsarEnabled()).toBe(false);
    }
  });

  it("reads each flag independently", () => {
    process.env.NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED = "true";
    expect(isGranularConsentEnabled()).toBe(true);
    expect(isTransparencyNoticeEnabled()).toBe(false);
    expect(isDsarEnabled()).toBe(false);
  });
});

/**
 * Consent Center transport (regulatory-compliance Requirement 2.6, Property
 * P10). Pins the client to the backend contract: singular `/compliance/consent`
 * routes, and a `{ purpose: granted }` projection normalized to records. CSRF is
 * attached by the shared `http-client` interceptor for these POST mutations.
 */
describe("consent transport", () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it("lists consents from GET /compliance/consent and normalizes the projection", async () => {
    get.mockResolvedValueOnce({
      data: {
        enabled: true,
        policy_version: "2026-03-v1",
        purposes: ["core_service", "personalization"],
        consents: { core_service: true, personalization: false },
      },
    });

    const result = await listConsents();

    expect(get).toHaveBeenCalledWith("/compliance/consent");
    expect(result.enabled).toBe(true);
    expect(result.policy_version).toBe("2026-03-v1");
    expect(result.consents).toEqual(
      expect.arrayContaining([
        { purpose: "core_service", granted: true },
        { purpose: "personalization", granted: false },
      ]),
    );
  });

  it("returns an empty record list when the feature is disabled", async () => {
    get.mockResolvedValueOnce({ data: { enabled: false } });

    const result = await listConsents();

    expect(result.enabled).toBe(false);
    expect(result.consents).toEqual([]);
  });

  it("grants consent via POST /compliance/consent/grant", async () => {
    post.mockResolvedValueOnce({ data: {} });

    await grantConsent("research");

    expect(post).toHaveBeenCalledWith("/compliance/consent/grant", {
      purpose: "research",
    });
  });

  it("includes the policy version when provided on grant", async () => {
    post.mockResolvedValueOnce({ data: {} });

    await grantConsent("research", "2026-03-v1");

    expect(post).toHaveBeenCalledWith("/compliance/consent/grant", {
      purpose: "research",
      policy_version: "2026-03-v1",
    });
  });

  it("withdraws consent via POST /compliance/consent/withdraw", async () => {
    post.mockResolvedValueOnce({ data: {} });

    await withdrawConsent("cross_border_processing");

    expect(post).toHaveBeenCalledWith("/compliance/consent/withdraw", {
      purpose: "cross_border_processing",
    });
  });
});

/**
 * DSAR transport (regulatory-compliance Requirement 3, Property P7). Pins the
 * client to the actual backend contract, which differs from the legacy shapes:
 * the submit route is singular (`/compliance/dsar/request`), export is a `GET`
 * returning a JSON bundle (not a POSTed Blob), deletion has its own route, and
 * the admin queue is RBAC-gated. These tests guard against route/method drift.
 */
describe("DSAR transport", () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it("submits a request via POST /compliance/dsar/request (singular)", async () => {
    post.mockResolvedValueOnce({
      data: {
        enabled: true,
        request_id: 42,
        kind: "correct",
        status: "received",
        created_at: "2026-04-15T00:00:00Z",
        due_at: "2026-05-15T00:00:00Z",
      },
    });

    const result = await submitDsarRequest("correct");

    expect(post).toHaveBeenCalledWith("/compliance/dsar/request", {
      kind: "correct",
    });
    expect(result).toMatchObject({ id: 42, kind: "correct", status: "received" });
  });

  it("exports via GET /compliance/dsar/export and returns the bundle", async () => {
    const bundle = { schema: "clara.dsar.export.v1", subject: { user_id: 1 } };
    get.mockResolvedValueOnce({ data: { enabled: true, export: bundle } });

    const result = await requestDsarExport();

    expect(get).toHaveBeenCalledWith("/compliance/dsar/export");
    expect(result).toEqual(bundle);
  });

  it("deletes via POST /compliance/dsar/delete", async () => {
    post.mockResolvedValueOnce({
      data: { enabled: true, request_id: 7, kind: "delete", status: "fulfilled" },
    });

    const result = await requestDsarDelete();

    expect(post).toHaveBeenCalledWith("/compliance/dsar/delete", {});
    expect(result).toMatchObject({ id: 7, kind: "delete", status: "fulfilled" });
  });

  it("lists own requests via GET /compliance/dsar/requests", async () => {
    get.mockResolvedValueOnce({
      data: {
        enabled: true,
        requests: [{ id: 1, kind: "export", status: "received" }],
      },
    });

    const result = await listDsarRequests();

    expect(get).toHaveBeenCalledWith("/compliance/dsar/requests");
    expect(result.enabled).toBe(true);
    expect(result.requests).toHaveLength(1);
  });

  it("lists the admin queue via GET /compliance/dsar/admin/queue", async () => {
    get.mockResolvedValueOnce({
      data: {
        enabled: true,
        requests: [{ id: 1, kind: "delete", status: "received", overdue: true }],
        overdue_count: 1,
      },
    });

    const result = await listAdminDsarQueue();

    expect(get).toHaveBeenCalledWith("/compliance/dsar/admin/queue");
    expect(result.overdue_count).toBe(1);
    expect(result.requests[0].overdue).toBe(true);
  });

  it("updates a status via POST /compliance/dsar/admin/status", async () => {
    post.mockResolvedValueOnce({
      data: { enabled: true, id: 3, kind: "correct", status: "fulfilled" },
    });

    const result = await updateDsarStatus(3, "fulfilled");

    expect(post).toHaveBeenCalledWith("/compliance/dsar/admin/status", {
      request_id: 3,
      status: "fulfilled",
    });
    expect(result).toMatchObject({ id: 3, status: "fulfilled" });
  });
});
