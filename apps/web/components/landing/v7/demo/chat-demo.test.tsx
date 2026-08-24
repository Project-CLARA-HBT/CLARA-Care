import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import ChatDemoDefault, { ChatDemo } from "./chat-demo";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { V7_DEMO_SOURCES } from "../landing-data-v7";

describe("ChatDemo (Landing v7 Interactive Demo)", () => {
  it("exports both named and default ChatDemo", () => {
    expect(ChatDemo).toBeDefined();
    expect(ChatDemoDefault).toBeDefined();
    expect(ChatDemo).toBe(ChatDemoDefault);
  });

  it("renders header chrome with FIDES Safe badge and Zero-CoT security", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <ChatDemo />
      </MotionProvider>
    );

    expect(screen.getByText("CLARA Clinical Assistant")).toBeInTheDocument();
    expect(screen.getByTestId("fides-safe-badge")).toBeInTheDocument();
    expect(screen.getByText("FIDES Safe")).toBeInTheDocument();
    expect(screen.getByTestId("zero-cot-badge")).toBeInTheDocument();
    expect(screen.getByText("Zero-CoT Security Active")).toBeInTheDocument();
  });

  it("renders user question turn with clinical context chips", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <ChatDemo />
      </MotionProvider>
    );

    expect(screen.getByText("Câu hỏi của bạn")).toBeInTheDocument();
    expect(
      screen.getByText(/Tôi mới bắt đầu uống Amlodipine 5mg được 3 ngày/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Amlodipine Besylate 5mg/i)).toBeInTheDocument();
  });

  it("renders Tier 1 Direct Answer with prominent takeaway", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <ChatDemo />
      </MotionProvider>
    );

    const tier1 = screen.getByTestId("tier-1-direct-answer");
    expect(tier1).toBeInTheDocument();
    expect(
      within(tier1).getByText(new RegExp(LANDING_COPY_V7.vi.chat.directAnswerTitle, "i"))
    ).toBeInTheDocument();
    expect(
      within(tier1).getByText(LANDING_COPY_V7.vi.chat.directAnswerBody)
    ).toBeInTheDocument();
  });

  it("renders Tier 2 Next Action checklist and toggles step completion", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <ChatDemo />
      </MotionProvider>
    );

    const tier2 = screen.getByTestId("tier-2-next-action");
    expect(tier2).toBeInTheDocument();
    expect(
      within(tier2).getByRole("heading", {
        name: new RegExp(LANDING_COPY_V7.vi.chat.nextActionTitle, "i"),
      })
    ).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThanOrEqual(3);

    // Initial state: not checked
    expect(checkboxes[0]).toHaveAttribute("aria-checked", "false");

    // Click first step to mark completed
    fireEvent.click(checkboxes[0]);
    expect(checkboxes[0]).toHaveAttribute("aria-checked", "true");

    // Click again to unmark
    fireEvent.click(checkboxes[0]);
    expect(checkboxes[0]).toHaveAttribute("aria-checked", "false");

    // Keyboard Enter to toggle
    fireEvent.keyDown(checkboxes[0], { key: "Enter" });
    expect(checkboxes[0]).toHaveAttribute("aria-checked", "true");
  });

  it("renders Tier 3 Uncertainty / Missing context yellow warning box", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <ChatDemo />
      </MotionProvider>
    );

    const tier3 = screen.getByTestId("tier-3-uncertainty");
    expect(tier3).toBeInTheDocument();
    expect(
      within(tier3).getByRole("heading", {
        name: new RegExp(LANDING_COPY_V7.vi.chat.uncertaintyTitle, "i"),
      })
    ).toBeInTheDocument();
    expect(
      within(tier3).getByText(LANDING_COPY_V7.vi.chat.uncertaintyBody)
    ).toBeInTheDocument();
  });

  it("renders Tier 4 Clinical Sources rail and interacts with Source Inspector", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <ChatDemo />
      </MotionProvider>
    );

    const tier4 = screen.getByTestId("tier-4-sources");
    expect(tier4).toBeInTheDocument();
    expect(
      within(tier4).getByRole("heading", {
        name: new RegExp(LANDING_COPY_V7.vi.chat.sourcesTitle, "i"),
      })
    ).toBeInTheDocument();

    // Default selected source is DAV
    const inspector = screen.getByTestId("source-inspector-panel");
    expect(inspector).toBeInTheDocument();
    expect(within(inspector).getByText("Dược thư Quốc gia Việt Nam (DAV)")).toBeInTheDocument();
    expect(within(inspector).getByText(V7_DEMO_SOURCES[0].relevanceVi)).toBeInTheDocument();

    // Click close button to dismiss inspector
    const closeBtn = screen.getByTestId("close-source-inspector");
    fireEvent.click(closeBtn);
    expect(screen.queryByTestId("source-inspector-panel")).not.toBeInTheDocument();

    // Click DrugBank source button to open DrugBank in inspector
    const drugbankBtn = screen.getByTestId("source-btn-drugbank-51");
    fireEvent.click(drugbankBtn);

    const updatedInspector = screen.getByTestId("source-inspector-panel");
    expect(updatedInspector).toBeInTheDocument();
    expect(within(updatedInspector).getByText("DrugBank 5.1 Comprehensive")).toBeInTheDocument();
    expect(within(updatedInspector).getByText(V7_DEMO_SOURCES[1].relevanceVi)).toBeInTheDocument();

    // Close via Escape key
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("source-inspector-panel")).not.toBeInTheDocument();
  });

  it("renders Tier 5 Advanced Pharmacological Detail and toggles mechanism view", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <ChatDemo />
      </MotionProvider>
    );

    const tier5 = screen.getByTestId("tier-5-advanced-pharmacology");
    expect(tier5).toBeInTheDocument();
    expect(
      within(tier5).getByRole("heading", {
        name: new RegExp(LANDING_COPY_V7.vi.chat.advancedDetailTitle, "i"),
      })
    ).toBeInTheDocument();

    // Initially collapsed
    expect(screen.queryByTestId("advanced-pharmacology-content")).not.toBeInTheDocument();

    const toggleBtn = screen.getByTestId("toggle-advanced-pharmacology");
    expect(toggleBtn).toHaveAttribute("aria-expanded", "false");

    // Click to expand
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("advanced-pharmacology-content")).toBeInTheDocument();
    expect(
      screen.getByText(LANDING_COPY_V7.vi.chat.advancedDetailBody)
    ).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("advanced-pharmacology-content")).not.toBeInTheDocument();
  });

  it("renders properly in English when language is 'en'", () => {
    render(
      <MotionProvider initialLanguage="en">
        <ChatDemo />
      </MotionProvider>
    );

    expect(screen.getByText("Your Question")).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(LANDING_COPY_V7.en.chat.directAnswerTitle, "i"))
    ).toBeInTheDocument();
    expect(
      screen.getByText(LANDING_COPY_V7.en.chat.directAnswerBody)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: new RegExp(LANDING_COPY_V7.en.chat.nextActionTitle, "i"),
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: new RegExp(LANDING_COPY_V7.en.chat.uncertaintyTitle, "i"),
      })
    ).toBeInTheDocument();
    expect(
      screen.getByText(LANDING_COPY_V7.en.chat.uncertaintyBody)
    ).toBeInTheDocument();
  });

  it("renders EvidenceRibbon visual connector in source rail", () => {
    const { container } = render(
      <MotionProvider initialLanguage="vi">
        <ChatDemo />
      </MotionProvider>
    );

    const ribbon = container.querySelector('[data-artwork="evidence-ribbon"]');
    expect(ribbon).toBeInTheDocument();
  });
});
