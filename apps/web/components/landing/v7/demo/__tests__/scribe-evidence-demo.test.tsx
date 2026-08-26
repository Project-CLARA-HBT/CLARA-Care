import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ScribeDemo } from "../scribe-demo";
import { EvidenceDemo } from "../evidence-demo";
import { MotionProvider } from "../../runtime/motion-provider";

describe("ScribeDemo Component (Landing v7)", () => {
  it("renders with default SOAP draft step (Step 4) and all 5 step indicators", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <ScribeDemo />
      </MotionProvider>
    );

    expect(screen.getByTestId("scribe-demo")).toBeInTheDocument();
    expect(screen.getByText("CLARA Ambient Clinical Scribe")).toBeInTheDocument();

    // Check all 5 step buttons exist
    const tabs = screen.getAllByRole("tab");
    expect(tabs.length).toBe(5);

    // Initial state is step 4 (SOAP draft)
    expect(screen.getByText("Bệnh án cấu trúc SOAP")).toBeInTheDocument();
    expect(screen.getByText(/S — Subjective/i)).toBeInTheDocument();
    expect(screen.getByText(/O — Objective/i)).toBeInTheDocument();
    expect(screen.getByText(/A — Assessment/i)).toBeInTheDocument();
    expect(screen.getByText(/P — Plan/i)).toBeInTheDocument();
  });

  it("transitions through all 5 steps when clicking stepper buttons", () => {
    const { container } = render(
      <MotionProvider initialLanguage="vi">
        <ScribeDemo />
      </MotionProvider>
    );

    // Step 1: Consent
    const tab1 = container.querySelector("#scribe-step-tab-1") as HTMLElement;
    fireEvent.click(tab1);
    expect(screen.getAllByText(/Bước 01/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Đồng thuận Ghi âm Bệnh nhân/i)).toBeInTheDocument();

    // Step 2: Recording (with CaptureWave)
    const tab2 = container.querySelector("#scribe-step-tab-2") as HTMLElement;
    fireEvent.click(tab2);
    expect(screen.getAllByText(/Bước 02/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId("capture-wave")).toBeInTheDocument();

    // Step 3: Transcript
    const tab3 = container.querySelector("#scribe-step-tab-3") as HTMLElement;
    fireEvent.click(tab3);
    expect(screen.getAllByText(/Bước 03/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Bác sĩ/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Bệnh nhân/i)).toBeInTheDocument();

    // Step 4: SOAP Draft
    const tab4 = container.querySelector("#scribe-step-tab-4") as HTMLElement;
    fireEvent.click(tab4);
    expect(screen.getAllByText(/Bước 04/i).length).toBeGreaterThan(0);

    // Step 5: Review & Sign-Off
    const tab5 = container.querySelector("#scribe-step-tab-5") as HTMLElement;
    fireEvent.click(tab5);
    expect(screen.getAllByText(/Bước 05/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Ký số & Đồng bộ EMR/i)).toBeInTheDocument();
  });

  it("handles physician verification sign-off seal interaction in Step 5", () => {
    const { container } = render(
      <MotionProvider initialLanguage="vi">
        <ScribeDemo />
      </MotionProvider>
    );

    // Navigate to Step 5
    const tab5 = container.querySelector("#scribe-step-tab-5") as HTMLElement;
    fireEvent.click(tab5);

    expect(screen.getByText("BS. CKI Nguyễn Minh Tuấn")).toBeInTheDocument();
    expect(screen.getByText("CA-MED-9948-VN")).toBeInTheDocument();

    const signBtn = screen.getByText(/Ký số & Đồng bộ EMR/i);
    fireEvent.click(signBtn);

    expect(screen.getAllByText(/ĐÃ KÝ DUYỆT & ĐỒNG BỘ EMR/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Đã ký duyệt thành công/i)).toBeInTheDocument();
  });

  it("renders correctly in English", () => {
    render(
      <MotionProvider initialLanguage="en">
        <ScribeDemo />
      </MotionProvider>
    );

    expect(screen.getByText(/Structured SOAP Protocol/i)).toBeInTheDocument();
  });
});

describe("EvidenceDemo Component (Landing v7)", () => {
  it("renders 5-tier evidence hierarchy rail and SourceLens inspector", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <EvidenceDemo />
      </MotionProvider>
    );

    expect(screen.getByTestId("evidence-demo")).toBeInTheDocument();
    expect(screen.getByText("Living Evidence Hub")).toBeInTheDocument();
    expect(screen.getByTestId("source-lens")).toBeInTheDocument();

    // Default selected source is DAV
    expect(screen.getAllByText("Dược thư Quốc gia Việt Nam (DAV)").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Tier I: Quốc gia/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Lý do phù hợp:/i)).toBeInTheDocument();
  });

  it("updates selected source when clicking different sources in the hierarchy list", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <EvidenceDemo />
      </MotionProvider>
    );

    // Click DrugBank
    const drugBankBtn = screen.getByText("DrugBank 5.1 Comprehensive");
    fireEvent.click(drugBankBtn);

    expect(screen.getAllByText(/Tier II: Quốc tế/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/OMx Technologies \/ University of Alberta/i).length).toBeGreaterThan(0);

    // Click FDA
    const fdaBtn = screen.getByText("FDA Drug Safety Communications");
    fireEvent.click(fdaBtn);

    expect(screen.getAllByText(/Tier III: Quản lý Dược/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/US Food and Drug Administration/i).length).toBeGreaterThan(0);
  });

  it("supports searching and opening FIDES verification coordinates", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <EvidenceDemo />
      </MotionProvider>
    );

    const fidesBtn = screen.getByText(/Tra cứu chứng chỉ xác thực FIDES/i);
    fireEvent.click(fidesBtn);

    expect(screen.getByText(/FIDES CRYPTO WITNESS COORDINATES/i)).toBeInTheDocument();
    expect(screen.getByText(/AUTH_HASH:/i)).toBeInTheDocument();
  });

  it("renders bilingual English copy correctly", () => {
    render(
      <MotionProvider initialLanguage="en">
        <EvidenceDemo />
      </MotionProvider>
    );

    expect(screen.getByText("Living Evidence Hub")).toBeInTheDocument();
    expect(screen.getByText(/5-Tier Evidence Hierarchy/i)).toBeInTheDocument();
    expect(screen.getByText(/Relevance Rationale:/i)).toBeInTheDocument();
  });
});
