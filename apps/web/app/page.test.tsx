import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

import HomePage, { metadata } from "./page";

describe("HomePage (/ - Spec v5 Section 6.1 Marketing Landing)", () => {
  it("exports metadata matching CLARA clinical assistant positioning", () => {
    expect(metadata.title).toContain("The Clara Care");
    expect(metadata.description).toContain("FIDES");
    expect(metadata.description).toContain("Zero-CoT");
  });

  it("renders the Public Marketing Landing page", () => {
    const { container } = render(<HomePage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_MARKETING");
    expect(root).toHaveAttribute("data-layout-archetype", "Marketing Landing");

    // Header & Hero
    const loginLinks = screen.getAllByRole("link", { name: /đăng nhập/i });
    expect(loginLinks.length).toBeGreaterThan(0);
    expect(loginLinks[0]).toHaveAttribute("href", "/login");

    const registerLinks = screen.getAllByRole("link", { name: /đăng ký/i });
    expect(registerLinks.length).toBeGreaterThan(0);
    expect(registerLinks[0]).toHaveAttribute("href", "/register");

    expect(screen.getAllByText("FIDES Guardrail Verified").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Zero-CoT Privacy Safe").length).toBeGreaterThan(0);

    // Footer links
    expect(screen.getByRole("link", { name: /trung tâm pháp lý \(\/legal\)/i })).toHaveAttribute(
      "href",
      "/legal",
    );
    expect(screen.getByRole("link", { name: /trung tâm hướng dẫn \(\/huong-dan\)/i })).toHaveAttribute(
      "href",
      "/huong-dan",
    );
  });
});
