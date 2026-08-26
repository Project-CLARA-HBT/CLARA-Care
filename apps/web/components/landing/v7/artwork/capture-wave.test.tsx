import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CaptureWaveDefault, {
  CaptureWave,
  type CaptureWaveProps,
  type ScribeState,
} from "./capture-wave";

describe("CaptureWave Artwork Component (Landing v7 Scribe Transformation)", () => {
  it("exports both named and default CaptureWave", () => {
    expect(CaptureWave).toBeDefined();
    expect(CaptureWaveDefault).toBeDefined();
    expect(CaptureWave).toBe(CaptureWaveDefault);
  });

  it("renders with default props (state='recording', isRecording=true) without errors", () => {
    const { container } = render(<CaptureWave />);
    const root = screen.getByTestId("capture-wave");

    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute("data-artwork", "capture-wave");
    expect(root).toHaveAttribute("data-state", "recording");
    expect(root).toHaveAttribute("data-recording", "true");

    expect(screen.getByText(/Ghi âm hội thoại/i)).toBeInTheDocument();
    expect(screen.getByText(/02:45 • Đang thu âm đa kênh/i)).toBeInTheDocument();

    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.querySelector("#ambient-acoustic-waveform-system")).toBeInTheDocument();
    expect(svg?.querySelector("#document-fold-transformation-guide")).toBeInTheDocument();
  });

  it("accepts and applies custom className and style props", () => {
    const { container } = render(
      <CaptureWave className="custom-wave-class" style={{ opacity: 0.95 }} />
    );
    const root = screen.getByTestId("capture-wave");
    expect(root.className).toContain("custom-wave-class");
    expect(container.firstElementChild).toHaveStyle({ opacity: "0.95" });
  });

  it("renders 12-bar acoustic soundwave visualizer with glowing mic aura during recording", () => {
    const { container } = render(<CaptureWave state="recording" isRecording={true} />);
    const spectrumBars = container.querySelector("#acoustic-spectrum-bars");
    expect(spectrumBars).toBeInTheDocument();

    // Verify 12 spectrum bars in SVG
    const barNodes = spectrumBars?.querySelectorAll('g[id^="bar-"]');
    expect(barNodes?.length).toBe(12);

    // Verify frequency labels
    expect(screen.getByText("64Hz")).toBeInTheDocument();
    expect(screen.getByText("125Hz")).toBeInTheDocument();
    expect(screen.getByText("1kHz")).toBeInTheDocument();
    expect(screen.getByText("8kHz")).toBeInTheDocument();
    expect(screen.getByText("20kHz")).toBeInTheDocument();
    expect(screen.getByText("24kHz")).toBeInTheDocument();

    // Verify bottom equalizer micro-bars
    const bottomBarContainer = container.querySelector('div[aria-hidden="true"]');
    const bottomBars = bottomBarContainer?.querySelectorAll("span");
    expect(bottomBars?.length).toBe(12);
  });

  it("renders document transformation fold guide during SOAP drafting", () => {
    const { container } = render(<CaptureWave state="soap" isRecording={false} />);
    const root = screen.getByTestId("capture-wave");
    expect(root).toHaveAttribute("data-state", "soap");

    // Check for 4 SOAP quadrants
    expect(container.querySelector("#soap-quadrant-s")).toBeInTheDocument();
    expect(container.querySelector("#soap-quadrant-o")).toBeInTheDocument();
    expect(container.querySelector("#soap-quadrant-a")).toBeInTheDocument();
    expect(container.querySelector("#soap-quadrant-p")).toBeInTheDocument();

    // Check for fold creases & corner origami fold guide
    expect(container.querySelector("#document-fold-creases")).toBeInTheDocument();
    expect(container.querySelector("#fold-crease-horizontal")).toBeInTheDocument();
    expect(container.querySelector("#fold-crease-vertical")).toBeInTheDocument();
    expect(container.querySelector("#document-corner-fold")).toBeInTheDocument();
    expect(container.querySelector("#fold-guide-callout")).toBeInTheDocument();
  });

  it.each(["consent", "recording", "transcript", "soap", "review"] as ScribeState[])(
    "renders correctly for state '%s'",
    (state) => {
      render(<CaptureWave state={state} />);
      const root = screen.getByTestId("capture-wave");
      expect(root).toHaveAttribute("data-state", state);
    }
  );

  it("toggles isRecording prop independently from state", () => {
    const { rerender } = render(<CaptureWave state="soap" isRecording={true} />);
    let root = screen.getByTestId("capture-wave");
    expect(root).toHaveAttribute("data-recording", "true");

    rerender(<CaptureWave state="recording" isRecording={false} />);
    root = screen.getByTestId("capture-wave");
    expect(root).toHaveAttribute("data-recording", "false");
  });

  it("invokes onStateChange callback when stepper tabs are clicked", () => {
    const onStateChange = vi.fn();
    render(<CaptureWave state="consent" onStateChange={onStateChange} />);

    // Click step 4 (SOAP)
    const soapBtn = screen.getByRole("tab", { name: /04/i });
    fireEvent.click(soapBtn);
    expect(onStateChange).toHaveBeenCalledWith("soap");

    // Click step 2 (Recording)
    const recordingBtn = screen.getByRole("tab", { name: /02/i });
    fireEvent.click(recordingBtn);
    expect(onStateChange).toHaveBeenCalledWith("recording");

    // Click step 5 (Review)
    const reviewBtn = screen.getByRole("tab", { name: /05/i });
    fireEvent.click(reviewBtn);
    expect(onStateChange).toHaveBeenCalledWith("review");
  });

  it("renders physician verification seal only during 'review' state", () => {
    const { container, rerender } = render(<CaptureWave state="recording" />);
    expect(container.querySelector("#physician-review-seal")).not.toBeInTheDocument();

    rerender(<CaptureWave state="review" />);
    expect(container.querySelector("#physician-review-seal")).toBeInTheDocument();
    expect(screen.getByText("BÁC SĨ ĐÃ DUYỆT")).toBeInTheDocument();
  });

  it("ensures accessible labels and role='img' are properly formatted", () => {
    render(<CaptureWave ariaLabel="Custom Scribe Acoustic Wave" />);
    const svg = screen.getByRole("img", { name: /Custom Scribe Acoustic Wave/i });
    expect(svg).toBeInTheDocument();
  });
});
