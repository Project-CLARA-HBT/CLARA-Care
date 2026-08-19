import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PersonalEvidenceDrawer } from "./personal-evidence-drawer";
import type {
  ConsumerPersonalEvidenceDto,
  ConsumerExternalSourceDto,
} from "@/lib/api/v2-client";

afterEach(cleanup);

describe("PersonalEvidenceDrawer", () => {
  const sampleEvidence: ConsumerPersonalEvidenceDto[] = [
    {
      id: "ev-1",
      title: "Metformin 850mg",
      resource_type: "medication",
      effective_at: "2026-08-10T08:00:00Z",
      source_name: "Bệnh viện Bạch Mai",
      state: "confirmed",
      snippet: "Ngày uống 2 lần, mỗi lần 1 viên sau ăn",
    },
  ];

  const sampleExternal: ConsumerExternalSourceDto[] = [
    {
      id: "src-1",
      title: "Hướng dẫn chẩn đoán và điều trị đái tháo đường",
      publisher: "Bộ Y tế",
      year: 2025,
      url: "https://moh.gov.vn",
      snippet: "Phác đồ điều trị bước đầu bằng Metformin",
    },
  ];

  it("renders nothing when isOpen is false", () => {
    const { container } = render(
      <PersonalEvidenceDrawer isOpen={false} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders evidence items, badges, and external sources when open", () => {
    const onClose = vi.fn();
    render(
      <PersonalEvidenceDrawer
        isOpen={true}
        onClose={onClose}
        evidence={sampleEvidence}
        externalSources={sampleExternal}
      />
    );

    const drawer = screen.getByTestId("personal-evidence-drawer");
    expect(drawer).toBeInTheDocument();
    expect(screen.getByText("Metformin 850mg")).toBeInTheDocument();
    expect(screen.getByText("Bác sĩ xác nhận")).toBeInTheDocument();
    expect(screen.getByText(/Ngày uống 2 lần/)).toBeInTheDocument();
    expect(
      screen.getByText("Hướng dẫn chẩn đoán và điều trị đái tháo đường")
    ).toBeInTheDocument();

    const closeBtn = screen.getByTestId("personal-evidence-drawer-close");
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape key press", () => {
    const onClose = vi.fn();
    render(
      <PersonalEvidenceDrawer
        isOpen={true}
        onClose={onClose}
        evidence={sampleEvidence}
      />
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
