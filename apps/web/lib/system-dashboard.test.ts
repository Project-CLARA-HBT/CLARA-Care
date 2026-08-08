import { describe, expect, it } from "vitest";
import { normalizeSystemDashboard } from "@/lib/system";

describe("system dashboard normalization", () => {
  it("preserves alert severity, message, and safe destination", () => {
    const dashboard = normalizeSystemDashboard({
      alerts: [
        {
          id: "expired-medicine",
          severity: "critical",
          message: "Có thuốc cần xem lại.",
          href: "/medicines?tab=safety",
        },
      ],
    });

    expect(dashboard.alerts).toEqual([
      {
        id: "expired-medicine",
        severity: "critical",
        message: "Có thuốc cần xem lại.",
        href: "/medicines?tab=safety",
      },
    ]);
  });

  it("normalizes legacy string alerts without inventing a critical severity", () => {
    const dashboard = normalizeSystemDashboard({ alerts: ["Cần kiểm tra hệ thống."] });

    expect(dashboard.alerts).toEqual([
      {
        id: "alert-1",
        severity: "warning",
        message: "Cần kiểm tra hệ thống.",
        href: "/dashboard",
      },
    ]);
  });
});
