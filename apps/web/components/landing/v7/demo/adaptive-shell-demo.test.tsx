import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AdaptiveShellDemoDefault, { AdaptiveShellDemo } from "./adaptive-shell-demo";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";

describe("AdaptiveShellDemo (Landing v7 Interactive Demo)", () => {
  it("exports both named and default AdaptiveShellDemo", () => {
    expect(AdaptiveShellDemo).toBeDefined();
    expect(AdaptiveShellDemoDefault).toBeDefined();
    expect(AdaptiveShellDemo).toBe(AdaptiveShellDemoDefault);
  });

  it("renders segmented mode switcher and default Personal Mode", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <AdaptiveShellDemo />
      </MotionProvider>
    );

    // Segmented Mode Switcher
    const modeTabs = screen.getAllByRole("tab");
    expect(modeTabs).toHaveLength(3);
    expect(modeTabs[0]).toHaveTextContent(LANDING_COPY_V7.vi.adaptive.modes.personal.label);
    expect(modeTabs[1]).toHaveTextContent(LANDING_COPY_V7.vi.adaptive.modes.clinical.label);
    expect(modeTabs[2]).toHaveTextContent(LANDING_COPY_V7.vi.adaptive.modes.research.label);

    // Personal Mode Headlines & Action Items
    expect(
      screen.getByText(LANDING_COPY_V7.vi.adaptive.modes.personal.headline)
    ).toBeInTheDocument();
    expect(
      screen.getByText(LANDING_COPY_V7.vi.adaptive.modes.personal.actionItem)
    ).toBeInTheDocument();

    // Personal Mode Dock & Nav Items
    const personalItems = LANDING_COPY_V7.vi.adaptive.modes.personal.navItems;
    personalItems.forEach((item) => {
      expect(screen.getAllByText(item).length).toBeGreaterThan(0);
    });
  });

  it("morphs to Clinical Mode when Clinical tab is clicked", () => {
    const handleModeChange = vi.fn();
    render(
      <MotionProvider initialLanguage="vi">
        <AdaptiveShellDemo onModeChange={handleModeChange} />
      </MotionProvider>
    );

    const clinicalTab = screen.getByRole("tab", {
      name: new RegExp(LANDING_COPY_V7.vi.adaptive.modes.clinical.label, "i"),
    });
    fireEvent.click(clinicalTab);

    expect(handleModeChange).toHaveBeenCalledWith("clinical");

    // Clinical Mode Content
    expect(
      screen.getByText(LANDING_COPY_V7.vi.adaptive.modes.clinical.headline)
    ).toBeInTheDocument();
    expect(
      screen.getByText(LANDING_COPY_V7.vi.adaptive.modes.clinical.actionItem)
    ).toBeInTheDocument();

    // Clinical Nav Items: Tổng quan, Council, CLARA, Scribe, Thêm
    const clinicalItems = LANDING_COPY_V7.vi.adaptive.modes.clinical.navItems;
    clinicalItems.forEach((item) => {
      expect(screen.getAllByText(item).length).toBeGreaterThan(0);
    });
  });

  it("morphs to Research Mode when Research tab is clicked", () => {
    const handleModeChange = vi.fn();
    render(
      <MotionProvider initialLanguage="vi">
        <AdaptiveShellDemo onModeChange={handleModeChange} />
      </MotionProvider>
    );

    const researchTab = screen.getByRole("tab", {
      name: new RegExp(LANDING_COPY_V7.vi.adaptive.modes.research.label, "i"),
    });
    fireEvent.click(researchTab);

    expect(handleModeChange).toHaveBeenCalledWith("research");

    // Research Mode Content
    expect(
      screen.getByText(LANDING_COPY_V7.vi.adaptive.modes.research.headline)
    ).toBeInTheDocument();
    expect(
      screen.getByText(LANDING_COPY_V7.vi.adaptive.modes.research.actionItem)
    ).toBeInTheDocument();

    // Research Nav Items: Nghiên cứu, Evidence, CLARA, Nguồn, Thêm
    const researchItems = LANDING_COPY_V7.vi.adaptive.modes.research.navItems;
    researchItems.forEach((item) => {
      expect(screen.getAllByText(item).length).toBeGreaterThan(0);
    });
  });

  it("respects controlled currentMode prop", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <AdaptiveShellDemo currentMode="research" />
      </MotionProvider>
    );

    expect(
      screen.getByText(LANDING_COPY_V7.vi.adaptive.modes.research.headline)
    ).toBeInTheDocument();
    expect(
      screen.getByText(LANDING_COPY_V7.vi.adaptive.modes.research.actionItem)
    ).toBeInTheDocument();
  });

  it("renders correctly in English mode", () => {
    render(
      <MotionProvider initialLanguage="en">
        <AdaptiveShellDemo currentMode="clinical" />
      </MotionProvider>
    );

    expect(
      screen.getByText(LANDING_COPY_V7.en.adaptive.modes.clinical.headline)
    ).toBeInTheDocument();
    expect(
      screen.getByText(LANDING_COPY_V7.en.adaptive.modes.clinical.actionItem)
    ).toBeInTheDocument();

    const clinicalItemsEn = LANDING_COPY_V7.en.adaptive.modes.clinical.navItems;
    clinicalItemsEn.forEach((item) => {
      expect(screen.getAllByText(item).length).toBeGreaterThan(0);
    });
  });
});
