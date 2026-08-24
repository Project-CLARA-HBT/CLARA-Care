import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";
import AdminIndexPage from "./page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("AdminIndexPage (/admin - Spec v5 Section 6.58)", () => {
  it("redirects immediately to /admin/overview", () => {
    AdminIndexPage();
    expect(redirect).toHaveBeenCalledWith("/admin/overview");
  });
});
