import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

import HomePage, { metadata } from "./page";

describe("HomePage (/ - Spec v7 Spatial Art Landing & SEO)", () => {
  it("exports rich metadata targeting primary Vietnamese and English search keywords", () => {
    expect(metadata.title).toContain("The Clara Care");
    expect(metadata.title).toContain("Clinical AI Assistant");
    expect(metadata.description).toContain("FIDES");
    expect(metadata.description).toContain("Zero-CoT");
    expect(metadata.description).toContain("Dược thư Quốc gia");

    // Keywords in Vietnamese & English
    const keywords = metadata.keywords as string[];
    expect(keywords).toContain("trợ lý AI y tế");
    expect(keywords).toContain("AI y tế Việt Nam");
    expect(keywords).toContain("Clinical AI Assistant");
    expect(keywords).toContain("Drug-Drug Interaction Checker");
    expect(keywords).toContain("Vietnamese National Pharmacopoeia");
    expect(keywords).toContain("Zero-CoT Medical Privacy");

    // OpenGraph & Alternates
    expect(metadata.openGraph?.title).toContain("The Clara Care");
    expect(metadata.openGraph?.locale).toBe("vi_VN");
    expect(metadata.alternates?.canonical).toBe("/");
    expect(metadata.openGraph?.images).toEqual([
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "The Clara Care — Trợ lý AI Y tế Lâm sàng & Tham vấn Sức khỏe An toàn",
      },
    ]);
    expect(metadata.twitter?.images).toEqual(["/twitter-image"]);
    expect(metadata.verification).toBeDefined();

    // AI search engines other metadata
    expect(metadata.other).toEqual({
      "ai-agent": "https://theclaracare.com/.well-known/ai-plugin.json",
      "mcp-server": "https://theclaracare.com/.well-known/mcp.json",
      "llms-txt": "https://theclaracare.com/llms.txt",
      rating: "general",
      referrer: "origin-when-cross-origin",
      classification: "Medical Artificial Intelligence & Clinical Decision Support System",
    });
  });

  it("renders SeoJsonLd and LandingV7", () => {
    const { container } = render(<HomePage />);

    // SeoJsonLd script verification
    const jsonLdScript = container.querySelector('script[type="application/ld+json"]');
    expect(jsonLdScript).not.toBeNull();
    const jsonLdData = JSON.parse(jsonLdScript?.innerHTML || "{}");
    expect(jsonLdData["@context"]).toBe("https://schema.org");
    expect(jsonLdData["@graph"]).toBeDefined();
    expect(jsonLdData["@graph"].length).toBeGreaterThanOrEqual(3);

    // LandingV7 content verification
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(
      screen.getByText(/Chuyển đến nội dung chính \/ Skip to main content/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });
});
