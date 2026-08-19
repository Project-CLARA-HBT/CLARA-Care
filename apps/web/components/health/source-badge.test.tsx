import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  SourceBadge,
  SourceDetail,
  SOURCE_KIND_MAP,
  VERIFICATION_STATE_MAP,
  type SourceKind,
  type SourceVerificationState,
} from "./source-badge";

afterEach(cleanup);

describe("SourceBadge", () => {
  const KINDS: SourceKind[] = [
    "clinician",
    "doctor",
    "hospital",
    "clinic",
    "device",
    "patient",
    "self",
    "imported",
    "prescription",
    "lab",
  ];

  it.each(KINDS)("renders source kind %s in Vietnamese", (kind) => {
    render(<SourceBadge sourceKind={kind} locale="vi" />);
    const meta = SOURCE_KIND_MAP[kind];
    expect(screen.getByText(meta.labelVi)).toBeInTheDocument();
  });

  it.each(KINDS)("renders source kind %s in English", (kind) => {
    render(<SourceBadge sourceKind={kind} locale="en" />);
    const meta = SOURCE_KIND_MAP[kind];
    expect(screen.getByText(meta.labelEn)).toBeInTheDocument();
  });

  const VERIFICATIONS: SourceVerificationState[] = [
    "verified",
    "self-reported",
    "imported",
    "device",
    "pending",
    "unverified",
  ];

  it.each(VERIFICATIONS)("renders verification state badge %s", (state) => {
    render(<SourceBadge verificationState={state} locale="vi" />);
    const meta = VERIFICATION_STATE_MAP[state];
    expect(screen.getByText(meta.labelVi)).toBeInTheDocument();
  });
});

describe("SourceDetail", () => {
  it("renders source detail with metadata fields", () => {
    render(
      <SourceDetail
        sourceKind="hospital"
        sourceName="Bệnh viện Bạch Mai"
        recorder="BS. Nguyễn Văn A"
        recordedAt="15/08/2026"
        verificationState="verified"
        notes="Ghi nhận tại khoa Tim Mạch"
        referenceUrl="https://example.com/record.pdf"
        locale="vi"
      />,
    );

    expect(screen.getByText("Bệnh viện Bạch Mai")).toBeInTheDocument();
    expect(screen.getByText("BS. Nguyễn Văn A")).toBeInTheDocument();
    expect(screen.getByText("15/08/2026")).toBeInTheDocument();
    expect(screen.getByText("Ghi nhận tại khoa Tim Mạch")).toBeInTheDocument();
    expect(screen.getByText("Tài liệu đính kèm")).toBeInTheDocument();
  });

  it("renders source detail in English when locale is en", () => {
    render(
      <SourceDetail
        sourceKind="device"
        sourceName="Omron Blood Pressure Monitor"
        recorder="Bluetooth Sync"
        recordedAt="2026-08-15"
        verificationState="device"
        locale="en"
      />,
    );

    expect(screen.getByText("Omron Blood Pressure Monitor")).toBeInTheDocument();
    expect(screen.getByText("Recorded by:")).toBeInTheDocument();
    expect(screen.getByText("Bluetooth Sync")).toBeInTheDocument();
  });
});
