import { describe, expect, it } from "vitest";
import { MixedConflictResolver } from "./mixed-conflict-resolver";

describe("MixedConflictResolver Conflict & Staleness Classifier", () => {
  it("classifies OCC version stale conflict with auto-retry permitted", () => {
    const res = MixedConflictResolver.classify(409, "glhs_stale_dependency_version");
    expect(res.category).toBe("OCC_VERSION_STALE");
    expect(res.autoRetryAllowed).toBe(true);
    expect(res.titleVi).toContain("cập nhật bởi người khác");
  });

  it("classifies lease expiration without auto-retry", () => {
    const res = MixedConflictResolver.classify(409, "lease_token_expired");
    expect(res.category).toBe("LEASE_EXPIRED");
    expect(res.autoRetryAllowed).toBe(false);
    expect(res.titleVi).toContain("hết hạn");
  });

  it("classifies consent revocation with hard-stop", () => {
    const res = MixedConflictResolver.classify(403, "consent_required", "patient revoked consent");
    expect(res.category).toBe("CONSENT_REVOKED");
    expect(res.autoRetryAllowed).toBe(false);
    expect(res.actionVi).toContain("Dừng thao tác dữ liệu");
  });

  it("classifies clinical policy drift", () => {
    const res = MixedConflictResolver.classify(409, "policy_version_drift");
    expect(res.category).toBe("POLICY_DRIFT");
    expect(res.autoRetryAllowed).toBe(false);
  });
});
