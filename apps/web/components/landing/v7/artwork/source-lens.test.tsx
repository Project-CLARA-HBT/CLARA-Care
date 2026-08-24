import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SourceLens, type AuthorityTier } from "./source-lens";

describe("SourceLens Artwork Component", () => {
  it("renders with default props and accessibility labels", () => {
    render(<SourceLens />);
    const lensElement = screen.getByTestId("source-lens");
    expect(lensElement).toBeInTheDocument();
    expect(lensElement).toHaveAttribute("data-active-tier", "National");
    expect(lensElement).toHaveAttribute("data-active", "true");
  });

  it("renders all 5 clinical authority sources in the lens field", () => {
    render(<SourceLens />);
    expect(screen.getAllByText("DAV").length).toBeGreaterThan(0);
    expect(screen.getAllByText("DrugBank").length).toBeGreaterThan(0);
    expect(screen.getAllByText("WHO").length).toBeGreaterThan(0);
    expect(screen.getAllByText("FDA").length).toBeGreaterThan(0);
    expect(screen.getAllByText("PubMed").length).toBeGreaterThan(0);
  });

  it("renders all 4 authority tier tabs and responds to selection", () => {
    const onSelectTier = vi.fn();
    render(<SourceLens tier="International" onSelectTier={onSelectTier} />);

    const intlTab = screen.getByRole("tab", { name: /International/i });
    expect(intlTab).toBeInTheDocument();
    expect(intlTab).toHaveAttribute("aria-selected", "true");

    const regTab = screen.getByRole("tab", { name: /Regulatory/i });
    fireEvent.click(regTab);
    expect(onSelectTier).toHaveBeenCalledWith("Regulatory");
  });

  it("supports all tier variants without runtime errors", () => {
    const tiers: AuthorityTier[] = ["National", "International", "Regulatory", "Peer-Reviewed"];
    tiers.forEach((t) => {
      const { unmount } = render(<SourceLens tier={t} active={true} />);
      expect(screen.getByTestId("source-lens")).toHaveAttribute("data-active-tier", t);
      unmount();
    });
  });

  it("applies custom className and custom ariaLabel correctly", () => {
    render(
      <SourceLens
        className="custom-lens-class"
        ariaLabel="Custom Lens Authority View"
      />
    );
    const element = screen.getByLabelText("Custom Lens Authority View");
    expect(element).toBeInTheDocument();
    expect(element).toHaveClass("custom-lens-class");
  });
});
