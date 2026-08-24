import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { LandingV6 } from "../landing-v6";
import { LANDING_COPY_V6 } from "../landing-copy-v6";

describe("LandingV6 — Immersive Spatial Editorial", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders the main landmark and top skip link", () => {
    render(<LandingV6 />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(
      screen.getByText(/Chuyển đến nội dung chính \/ Skip to main content/i)
    ).toBeInTheDocument();
  });

  it("renders all signature story sections", () => {
    render(<LandingV6 />);

    // 1. Hero
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();

    // 2. Trust
    expect(screen.getByText(LANDING_COPY_V6.vi.trust.title)).toBeInTheDocument();

    // 3. Manifesto
    expect(screen.getByText(/Một câu hỏi sức khỏe/i)).toBeInTheDocument();

    // 4. How CLARA Works
    expect(screen.getByText(LANDING_COPY_V6.vi.how.title)).toBeInTheDocument();

    // 5. Chat Signature Scene
    expect(screen.getByText(LANDING_COPY_V6.vi.chat.title)).toBeInTheDocument();

    // 6. LifeMap Signature Scene
    expect(screen.getByText(LANDING_COPY_V6.vi.lifemap.title)).toBeInTheDocument();

    // 7. Medicines
    expect(screen.getByText(LANDING_COPY_V6.vi.medicines.title)).toBeInTheDocument();

    // 8. PHR Sharing
    expect(screen.getByText(LANDING_COPY_V6.vi.phr.title)).toBeInTheDocument();

    // 9. Adaptive Modes Signature Scene
    expect(screen.getByText(LANDING_COPY_V6.vi.adaptive.title)).toBeInTheDocument();

    // 10. Clinical Transition
    expect(screen.getByText(LANDING_COPY_V6.vi.clinicalTransition.eyebrow)).toBeInTheDocument();

    // 11. Council Signature Scene
    expect(screen.getByText(LANDING_COPY_V6.vi.council.title)).toBeInTheDocument();

    // 12. Scribe
    expect(screen.getByText(LANDING_COPY_V6.vi.scribe.title)).toBeInTheDocument();

    // 13. Evidence
    expect(screen.getByText(LANDING_COPY_V6.vi.evidence.title)).toBeInTheDocument();

    // 14. Safety
    expect(screen.getByText(LANDING_COPY_V6.vi.safety.title)).toBeInTheDocument();

    // 15. Privacy
    expect(screen.getByText(LANDING_COPY_V6.vi.privacy.title)).toBeInTheDocument();

    // 16. Scenarios
    expect(screen.getByText(LANDING_COPY_V6.vi.scenarios.title)).toBeInTheDocument();

    // 17. Differentiation / Comparison
    expect(screen.getByText(LANDING_COPY_V6.vi.comparison.title)).toBeInTheDocument();

    // 18. FAQ
    expect(screen.getByText(LANDING_COPY_V6.vi.faq.title)).toBeInTheDocument();

    // 19. Final CTA
    expect(screen.getByText(LANDING_COPY_V6.vi.finalCta.title)).toBeInTheDocument();

    // 20. Footer
    expect(screen.getByText(LANDING_COPY_V6.vi.footer.tagline)).toBeInTheDocument();
  });

  it("toggles language between Vietnamese and English seamlessly", () => {
    render(<LandingV6 />);

    // Initially in Vietnamese
    expect(screen.getByText(LANDING_COPY_V6.vi.trust.title)).toBeInTheDocument();

    // Find and click language toggle for English in Nav
    const enButtons = screen.getAllByRole("button", { name: "EN" });
    fireEvent.click(enButtons[0]);

    // Check English copy rendered
    expect(screen.getByText(LANDING_COPY_V6.en.trust.title)).toBeInTheDocument();

    // Toggle back to Vietnamese
    const viButtons = screen.getAllByRole("button", { name: "VI" });
    fireEvent.click(viButtons[0]);
    expect(screen.getByText(LANDING_COPY_V6.vi.trust.title)).toBeInTheDocument();
  });

  it("allows switching adaptive modes and updates content", () => {
    render(<LandingV6 />);

    const clinicalTab = screen.getByRole("tab", { name: LANDING_COPY_V6.vi.adaptive.modes.clinical.label });
    fireEvent.click(clinicalTab);

    expect(
      screen.getByText(LANDING_COPY_V6.vi.adaptive.modes.clinical.headline)
    ).toBeInTheDocument();
  });

  it("expands and collapses FAQ items accessibly", () => {
    render(<LandingV6 />);

    const firstFaq = LANDING_COPY_V6.vi.faq.items[0];
    const faqButton = screen.getByRole("button", { name: firstFaq.question });

    expect(faqButton).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(faqButton);
    expect(faqButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(firstFaq.answer)).toBeInTheDocument();
  });
});
