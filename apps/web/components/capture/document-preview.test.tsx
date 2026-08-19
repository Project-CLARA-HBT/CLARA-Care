import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentPreview } from "./document-preview";
import type { CaptureCandidateV2 } from "@/lib/api/v2-client";

afterEach(cleanup);

// Mock URL.createObjectURL and revokeObjectURL
if (typeof window !== "undefined") {
  window.URL.createObjectURL = vi.fn(() => "blob:mock-image-preview-url");
  window.URL.revokeObjectURL = vi.fn();
}

const mockCandidates: CaptureCandidateV2[] = [
  {
    id: "cand-med-1",
    category: "medication",
    field_name: "medication_name",
    value: "Panadol 500mg",
    status: "accepted",
    bounding_box: {
      x: 15,
      y: 25,
      width: 40,
      height: 12,
    },
  },
  {
    id: "cand-meas-1",
    category: "measurement",
    field_name: "blood_pressure",
    value: "120/80",
    status: "accepted",
    bounding_box: {
      x: 20,
      y: 55,
      width: 35,
      height: 10,
    },
  },
];

describe("DocumentPreview Component", () => {
  it("renders image preview and controls", () => {
    const fakeFile = new File(["dummy image"], "prescription.png", { type: "image/png" });

    render(
      <DocumentPreview
        file={fakeFile}
        candidates={mockCandidates}
        locale="vi"
      />,
    );

    expect(screen.getByTestId("document-preview")).toBeInTheDocument();
    expect(screen.getByText("prescription.png")).toBeInTheDocument();
    expect(screen.getByTestId("document-image-preview")).toBeInTheDocument();
    expect(screen.getByText("2 vùng khớp")).toBeInTheDocument();
  });

  it("handles zoom in, zoom out, rotate, and reset controls", () => {
    const fakeFile = new File(["dummy image"], "lab.jpg", { type: "image/jpeg" });

    render(
      <DocumentPreview
        file={fakeFile}
        locale="vi"
      />,
    );

    expect(screen.getByText("100%")).toBeInTheDocument();

    const zoomInBtn = screen.getByTestId("doc-zoom-in");
    fireEvent.click(zoomInBtn);
    expect(screen.getByText("125%")).toBeInTheDocument();

    const zoomOutBtn = screen.getByTestId("doc-zoom-out");
    fireEvent.click(zoomOutBtn);
    expect(screen.getByText("100%")).toBeInTheDocument();

    const rotateBtn = screen.getByTestId("doc-rotate");
    fireEvent.click(rotateBtn);

    const resetBtn = screen.getByTestId("doc-reset");
    fireEvent.click(resetBtn);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("renders interactive bounding region boxes and triggers onSelectCandidate", () => {
    const fakeFile = new File(["dummy image"], "prescription.png", { type: "image/png" });
    const onSelectCandidate = vi.fn();

    render(
      <DocumentPreview
        file={fakeFile}
        candidates={mockCandidates}
        selectedCandidateId="cand-med-1"
        onSelectCandidate={onSelectCandidate}
        locale="vi"
      />,
    );

    const box1 = screen.getByTestId("bounding-box-cand-med-1");
    const box2 = screen.getByTestId("bounding-box-cand-meas-1");

    expect(box1).toBeInTheDocument();
    expect(box2).toBeInTheDocument();

    fireEvent.click(box2);
    expect(onSelectCandidate).toHaveBeenCalledWith("cand-meas-1");
  });

  it("renders PDF document presentation card when PDF file is provided", () => {
    const pdfFile = new File(["%PDF-1.4..."], "medical_record.pdf", {
      type: "application/pdf",
    });

    render(
      <DocumentPreview
        file={pdfFile}
        candidates={mockCandidates}
        locale="vi"
      />,
    );

    expect(screen.getByTestId("document-pdf-preview")).toBeInTheDocument();
    expect(screen.getAllByText("medical_record.pdf").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Đã trích xuất")).toBeInTheDocument();
  });
});
