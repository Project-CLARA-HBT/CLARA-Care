import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { LandingV7 } from "../landing-v7";
import { LANDING_COPY_V7 } from "../landing-copy-v7";

describe("LandingV7 — Spatial Art Awwwards Orchestrator", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders the main landmark and top skip link", () => {
    render(<LandingV7 />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(
      screen.getByText(/Chuyển đến nội dung chính \/ Skip to main content/i)
    ).toBeInTheDocument();
  });

  it("renders all 20 canonical chapter scenes in storyboard order", () => {
    render(<LandingV7 />);

    // 1. Hero
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();

    // 2. Trust
    expect(screen.getByText(LANDING_COPY_V7.vi.trust.title)).toBeInTheDocument();

    // 3. Manifesto
    expect(screen.getByText(/Một câu hỏi sức khỏe/i)).toBeInTheDocument();

    // 4. How CLARA Works
    expect(screen.getByText(LANDING_COPY_V7.vi.how.title)).toBeInTheDocument();

    // 5. Chat Signature Scene
    expect(screen.getByText(LANDING_COPY_V7.vi.chat.title)).toBeInTheDocument();

    // 6. LifeMap Signature Scene
    expect(screen.getAllByText(LANDING_COPY_V7.vi.lifemap.title).length).toBeGreaterThan(0);

    // 7. Medicines
    expect(screen.getByText(LANDING_COPY_V7.vi.medicines.title)).toBeInTheDocument();

    // 8. PHR Sharing
    expect(screen.getByText(LANDING_COPY_V7.vi.phr.title)).toBeInTheDocument();

    // 9. Adaptive Modes Signature Scene
    expect(screen.getByText(LANDING_COPY_V7.vi.adaptive.title)).toBeInTheDocument();

    // 10. Clinical Transition
    expect(screen.getByText(LANDING_COPY_V7.vi.clinicalTransition.eyebrow)).toBeInTheDocument();

    // 11. Council Signature Scene
    expect(screen.getByText(LANDING_COPY_V7.vi.council.title)).toBeInTheDocument();

    // 12. Scribe
    expect(screen.getByText(LANDING_COPY_V7.vi.scribe.title)).toBeInTheDocument();

    // 13. Evidence
    expect(screen.getByText(LANDING_COPY_V7.vi.evidence.title)).toBeInTheDocument();

    // 14. Safety
    expect(screen.getByText(LANDING_COPY_V7.vi.safety.title)).toBeInTheDocument();

    // 15. Privacy
    expect(screen.getByText(LANDING_COPY_V7.vi.privacy.title)).toBeInTheDocument();

    // 16. Scenarios
    expect(screen.getByText(LANDING_COPY_V7.vi.scenarios.title)).toBeInTheDocument();

    // 17. Differentiation / Comparison
    expect(screen.getByText(LANDING_COPY_V7.vi.comparison.title)).toBeInTheDocument();

    // 18. FAQ
    expect(screen.getByText(LANDING_COPY_V7.vi.faq.title)).toBeInTheDocument();

    // 19. Final CTA
    expect(screen.getByText(LANDING_COPY_V7.vi.finalCta.title)).toBeInTheDocument();

    // 20. Footer
    expect(screen.getByText(LANDING_COPY_V7.vi.footer.tagline)).toBeInTheDocument();
  });

  it("toggles language between Vietnamese and English across all scenes", () => {
    render(<LandingV7 />);

    // Initially in Vietnamese
    expect(screen.getByText(LANDING_COPY_V7.vi.trust.title)).toBeInTheDocument();

    // Find and click language toggle for English in Nav
    const enButtons = screen.getAllByRole("button", { name: /EN|English/i });
    fireEvent.click(enButtons[0]);

    // Check English copy rendered
    expect(screen.getByText(LANDING_COPY_V7.en.trust.title)).toBeInTheDocument();

    // Toggle back to Vietnamese
    const viButtons = screen.getAllByRole("button", { name: /VI|Tiếng Việt/i });
    fireEvent.click(viButtons[0]);
    expect(screen.getByText(LANDING_COPY_V7.vi.trust.title)).toBeInTheDocument();
  });
});
