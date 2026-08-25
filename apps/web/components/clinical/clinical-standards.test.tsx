import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ClinicalStandards from "./clinical-standards";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

describe("ClinicalStandards Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.scrollTo = vi.fn();
  });

  it("renders the Clinical Standards header, badges, and KPIs", () => {
    render(<ClinicalStandards />);

    expect(screen.getByText(/Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế CLARA/i)).toBeInTheDocument();
    expect(screen.getByText("ĐẶC TẢ TIÊU CHUẨN LÂM SÀNG")).toBeInTheDocument();
    expect(screen.getByText("Luật KBCB 15/2023/QH15")).toBeInTheDocument();
    expect(screen.getByText("FIDES Lite v1.2 Hard-Veto")).toBeInTheDocument();
    expect(screen.getByText("Zero-CoT Privacy")).toBeInTheDocument();
  });

  it("renders all 8 clinical standard sections", () => {
    render(<ClinicalStandards />);

    // Section 1: CDSS Overview
    expect(screen.getAllByText(/1\. Kiến trúc Hệ thống Hỗ trợ Quyết định Lâm sàng/i).length).toBeGreaterThanOrEqual(1);

    // Section 2: AI Council
    expect(screen.getAllByText(/2\. Điều phối Hội đồng Chuyên khoa AI/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Cardiology/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Neurology/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Nephrology/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Pharmacology/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Endocrinology/i).length).toBeGreaterThanOrEqual(1);

    // Section 3: Ambient Scribe & SOAP & E-Sign
    expect(screen.getAllByText(/3\. Trợ lý Ghi chép Ambient Scribe/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Subjective/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Objective/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Assessment/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Plan/i).length).toBeGreaterThanOrEqual(1);

    // Section 4: GLHS & Living Evidence
    expect(screen.getAllByText(/4\. Đồ thị Tri thức GLHS/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Phác đồ Bộ Y tế/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Dược thư Quốc gia VN/i).length).toBeGreaterThanOrEqual(1);

    // Section 5: DDI & Renal eGFR
    expect(screen.getAllByText(/5\. An toàn Tương tác thuốc \(DDI\)/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Critical \(Đỏ\)/i).length).toBeGreaterThanOrEqual(1);

    // Section 6: Legal Guardrails
    expect(screen.getAllByText(/6\. Ranh giới Pháp lý theo Luật Khám bệnh, chữa bệnh 2023/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Khóa cứng Kê đơn & Chẩn đoán Độc lập/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Luồng Cấp cứu Khẩn cấp Tức thời/i).length).toBeGreaterThanOrEqual(1);

    // Section 7: FIDES Hard-Veto
    expect(screen.getAllByText(/7\. Giao thức Xác thực Y khoa FIDES/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/QUY TẮC PHỦ QUYẾT TUYỆT ĐỐI \(HARD-VETO INVARIANT RULE\)/i).length).toBeGreaterThanOrEqual(1);

    // Section 8: Zero-CoT Privacy
    expect(screen.getAllByText(/8\. Bảo mật Dòng Suy luận Zero-CoT/i).length).toBeGreaterThanOrEqual(1);
  });

  it("switches language between Vietnamese and English", () => {
    render(<ClinicalStandards />);

    // Switch to English
    const enButton = screen.getByRole("button", { name: "English" });
    fireEvent.click(enButton);

    expect(screen.getByText(/CLARA Clinical Standards & Medical Safety Protocols/i)).toBeInTheDocument();
    expect(screen.getAllByText(/1\. Clinical Decision Support System \(CDSS\) Architecture/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/2\. Multi-Specialist AI Council Orchestration/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/7\. FIDES Medical Verification Protocols & Hard-Veto Rule/i).length).toBeGreaterThanOrEqual(1);

    // Switch back to Vietnamese
    const viButton = screen.getByRole("button", { name: "Tiếng Việt" });
    fireEvent.click(viButton);

    expect(screen.getByText(/Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế CLARA/i)).toBeInTheDocument();
  });

  it("navigates via table of contents section buttons", () => {
    render(<ClinicalStandards />);

    const fidesNavButton = screen.getByRole("button", { name: /7\. Giao thức Xác thực Y khoa FIDES/i });
    fireEvent.click(fidesNavButton);

    expect(fidesNavButton).toHaveClass("text-[var(--text-brand)]");
    expect(window.scrollTo).toHaveBeenCalled();
  });
});
