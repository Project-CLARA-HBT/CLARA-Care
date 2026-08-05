import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(__dirname, "../app/dashboard/page.tsx"), "utf8");

describe("dashboard data integrity presentation", () => {
  it("does not fabricate fallback activity, workflow tasks, or calibrated confidence", () => {
    expect(source).toContain("return [];");
    expect(source).toContain("Chưa có phiên hỗ trợ nào để hiển thị.");
    expect(source).toContain("Chưa có thước đo đã hiệu chuẩn");
    expect(source).not.toContain("So sánh DASH vs Địa Trung Hải");
    expect(source).not.toContain("confidenceFrom");
    expect(source).not.toContain("0.98");
  });

  it("renders an explicit unknown state when a backend count is unavailable", () => {
    expect(source).toContain('activeCases === null ? "chưa có dữ liệu"');
    expect(source).toContain('councilTotal === null ? "Chưa có dữ liệu"');
    expect(source).toContain("Chưa có dữ liệu thuốc để hiển thị.");
  });
});
