import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const dashboardPageSource = readFileSync(
  resolve(__dirname, "../app/dashboard/page.tsx"),
  "utf8",
);
const clinicalLaunchpadSource = readFileSync(
  resolve(__dirname, "../components/clinical/clinical-overview-launchpad.tsx"),
  "utf8",
);
const researchLaunchpadSource = readFileSync(
  resolve(__dirname, "../components/research/research-overview-launchpad.tsx"),
  "utf8",
);
const combinedSource = `${dashboardPageSource}\n${clinicalLaunchpadSource}\n${researchLaunchpadSource}`;

describe("dashboard data integrity presentation", () => {
  it("implements Spec v5 Section 6.55 Role-Adaptive Home without monolithic card fallback", () => {
    expect(dashboardPageSource).toContain("ClinicalOverviewLaunchpad");
    expect(dashboardPageSource).toContain("ResearchOverviewLaunchpad");
    expect(dashboardPageSource).toContain('router.replace("/admin/overview")');
    expect(dashboardPageSource).toContain('router.replace("/today")');
    expect(dashboardPageSource).not.toContain("PRIMARY_CLINICAL_TOOLS");
    expect(dashboardPageSource).not.toContain("shortcutSets");
  });

  it("does not fabricate fallback activity, personal counts, or calibrated confidence", () => {
    expect(combinedSource).toContain("research.recentQueries");
    expect(combinedSource).toContain("dashboard?.cabinet.itemTotal");
    expect(combinedSource).toContain("Chưa có hoạt động gần đây để hiển thị.");
    expect(combinedSource).not.toContain("So sánh DASH vs Địa Trung Hải");
    expect(combinedSource).not.toContain("Metformin");
    expect(combinedSource).not.toContain("requestCount");
    expect(combinedSource).not.toContain("confidenceFrom");
    expect(combinedSource).not.toContain("0.98");
  });

  it("renders an explicit unknown state when a backend count is unavailable", () => {
    expect(combinedSource).toContain("cabinetCount === null");
    expect(combinedSource).toContain("Chưa có dữ liệu");
    expect(combinedSource).toContain("Chưa tải được tổng quan");
  });

  it("links each dashboard action to an implemented route", () => {
    expect(combinedSource).toContain('href: "/chat"');
    expect(combinedSource).toContain('href: "/evidence"');
    expect(combinedSource).toContain('href: "/council"');
    expect(combinedSource).toContain('href: "/research/source-hub"');
  });

  it("does not present a reassuring status while data is loading or unavailable", () => {
    expect(combinedSource).toContain("const ready = !loading && !error");
    expect(combinedSource).toContain('copy("Chưa xác định", "Unknown")');
    expect(combinedSource).not.toContain('copy("Ổn định", "Stable")');
  });

  it("preserves the first structured alert and its destination", () => {
    expect(combinedSource).toContain("topAlert.href");
    expect(combinedSource).toContain("topAlert.message");
    expect(combinedSource).toContain('topAlert.severity === "critical"');
  });

  it("uses the dark-theme-safe semantic text color for interactive labels", () => {
    expect(combinedSource).toContain("text-[var(--text-brand)]");
    expect(combinedSource).not.toContain("text-[var(--brand-700)]");
  });
});
