import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(__dirname, "../app/dashboard/page.tsx"), "utf8");

describe("dashboard data integrity presentation", () => {
  it("does not fabricate fallback activity, personal counts, or calibrated confidence", () => {
    expect(source).toContain("dashboard.research.recentQueries");
    expect(source).toContain("dashboard.cabinet.itemTotal");
    expect(source).toContain("Chưa có hoạt động gần đây để hiển thị.");
    expect(source).not.toContain("So sánh DASH vs Địa Trung Hải");
    expect(source).not.toContain("Metformin");
    expect(source).not.toContain("requestCount");
    expect(source).not.toContain("confidenceFrom");
    expect(source).not.toContain("0.98");
  });

  it("renders an explicit unknown state when a backend count is unavailable", () => {
    expect(source).toContain('cabinetCount === null');
    expect(source).toContain("Chưa có dữ liệu thuốc");
    expect(source).toContain("Chưa tải được tổng quan");
    expect(source).toContain("Hôm nay chưa có việc cần xử lý");
  });

  it("links each dashboard action to an implemented route", () => {
    expect(source).toContain('href: "/chat"');
    expect(source).toContain('href: "/evidence"');
    expect(source).toContain('href: "/council"');
    expect(source).toContain('href: "/admin/analytics"');
  });

  it("does not present a reassuring status while data is loading or unavailable", () => {
    expect(source).toContain('const ready = !loading && !error');
    expect(source).toContain('copy("Chưa xác định", "Unknown")');
    expect(source).toContain('error ? null : nextTask');
    expect(source).not.toContain('copy("Ổn định", "Stable")');
  });

  it("preserves the first structured alert and its destination", () => {
    expect(source).toContain('topAlert.href');
    expect(source).toContain('topAlert.message');
    expect(source).toContain('topAlert.severity === "critical"');
  });

  it("uses the dark-theme-safe semantic text color for interactive labels", () => {
    expect(source).toContain('text-[var(--text-brand)]');
    expect(source).not.toContain('text-[var(--brand-700)]');
  });
});
