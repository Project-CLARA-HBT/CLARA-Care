import React from "react";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ClaraOrbDefault, {
  ClaraOrb,
  type ClaraOrbSize,
  type ClaraOrbTone,
} from "./clara-orb";

describe("ClaraOrb Component (Landing v7 Brand Artwork Anchor)", () => {
  it("exports both named ClaraOrb and default export", () => {
    expect(ClaraOrb).toBeDefined();
    expect(ClaraOrbDefault).toBeDefined();
    expect(ClaraOrb).toBe(ClaraOrbDefault);
  });

  it("renders with default props (size='md', tone='azure', pulse=true, interactive=false) and aria-hidden='true'", () => {
    const { container } = render(<ClaraOrb />);
    const orbEl = container.querySelector('[data-artwork="clara-orb"]');

    expect(orbEl).toBeInTheDocument();
    expect(orbEl).toHaveAttribute("aria-hidden", "true");
    expect(orbEl).toHaveAttribute("data-size", "md");
    expect(orbEl).toHaveAttribute("data-tone", "azure");
    expect(orbEl).toHaveAttribute("data-pulse", "true");

    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("focusable", "false");
  });

  it("renders all size variants ('sm', 'md', 'lg', 'xl') correctly", () => {
    const sizes: ClaraOrbSize[] = ["sm", "md", "lg", "xl"];

    sizes.forEach((size) => {
      const { container } = render(<ClaraOrb size={size} />);
      const orbEl = container.querySelector('[data-artwork="clara-orb"]');
      expect(orbEl).toHaveAttribute("data-size", size);
    });
  });

  it("renders all tone palettes ('azure', 'mint', 'iris', 'neutral') cleanly", () => {
    const tones: ClaraOrbTone[] = ["azure", "mint", "iris", "neutral"];

    tones.forEach((tone) => {
      const { container } = render(<ClaraOrb tone={tone} />);
      const orbEl = container.querySelector('[data-artwork="clara-orb"]');
      expect(orbEl).toHaveAttribute("data-tone", tone);
    });
  });

  it("toggles pulse animation layers when pulse is false vs true", () => {
    const { container: withPulse } = render(<ClaraOrb pulse={true} />);
    const { container: withoutPulse } = render(<ClaraOrb pulse={false} />);

    const orbWith = withPulse.querySelector('[data-artwork="clara-orb"]');
    const orbWithout = withoutPulse.querySelector('[data-artwork="clara-orb"]');

    expect(orbWith).toHaveAttribute("data-pulse", "true");
    expect(orbWithout).toHaveAttribute("data-pulse", "false");

    // With pulse should have multiple soft pulse halos, without pulse should omit them
    const halosWith = withPulse.querySelectorAll(".motion-safe\\:animate-\\[ping_3\\.6s_cubic-bezier\\(0\\,0\\,0\\.2\\,1\\)_infinite\\]");
    const halosWithout = withoutPulse.querySelectorAll(".motion-safe\\:animate-\\[ping_3\\.6s_cubic-bezier\\(0\\,0\\,0\\.2\\,1\\)_infinite\\]");

    expect(halosWith.length).toBeGreaterThan(0);
    expect(halosWithout.length).toBe(0);
  });

  it("supports interactive hover & active states when interactive=true", () => {
    const { container } = render(<ClaraOrb interactive={true} />);
    const orbEl = container.querySelector('[data-artwork="clara-orb"]');

    expect(orbEl?.className).toContain("cursor-pointer");
    expect(orbEl?.className).toContain("hover:scale-105");
  });

  it("supports Lite / Reduced Motion mode via motion-reduce CSS utilities", () => {
    const { container } = render(<ClaraOrb pulse={true} />);
    const reduceMotionElements = container.querySelectorAll(".motion-reduce\\:animate-none");
    expect(reduceMotionElements.length).toBeGreaterThan(0);

    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("class")).toContain("motion-reduce:transform-none");
  });

  it("ensures NO medical diagnosis or severity encoding is present", () => {
    const { container } = render(<ClaraOrb tone="azure" />);
    const html = container.innerHTML.toLowerCase();

    // Verify absence of clinical/severity/triage indicators
    expect(html).not.toContain("emergency");
    expect(html).not.toContain("triage");
    expect(html).not.toContain("critical");
    expect(html).not.toContain("warning");
    expect(html).not.toContain("diagnosis");
    expect(html).not.toContain("symptom");
  });

  it("accepts custom className and style props", () => {
    const { container } = render(
      <ClaraOrb className="custom-test-orb" style={{ zIndex: 42 }} />
    );
    const orbEl = container.querySelector('[data-artwork="clara-orb"]');

    expect(orbEl?.className).toContain("custom-test-orb");
    expect(orbEl).toHaveStyle({ zIndex: "42" });
  });
});
