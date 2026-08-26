import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LifeMapGuideModal } from "./lifemap-guide-modal";

afterEach(cleanup);

describe("LifeMapGuideModal", () => {
  it("renders modal with correct title, description, and accessibility attributes when open", () => {
    const onClose = vi.fn();
    render(<LifeMapGuideModal open onClose={onClose} />);

    const dialog = screen.getByRole("dialog", { name: "Hướng dẫn sử dụng LifeMap" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
    expect(dialog.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText("Bản đồ hành trình sức khỏe và hồ sơ y tế liên tục CLARA")).toBeInTheDocument();
  });

  it("does not render when open is false", () => {
    render(<LifeMapGuideModal open={false} onClose={vi.fn()} />);
    expect(screen.queryByTestId("lifemap-guide-modal")).not.toBeInTheDocument();
  });

  it("renders all 4 tutorial steps in the stepper navigation tabs", () => {
    render(<LifeMapGuideModal open onClose={vi.fn()} />);

    expect(screen.getByRole("tab", { name: /dòng thời gian/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /chuẩn bị đi khám/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /đối chiếu bitemporal/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /an toàn glhs/i })).toBeInTheDocument();
  });

  it("displays Step 1 content (Dòng thời gian liên tục) and interactive timeline nodes by default", () => {
    render(<LifeMapGuideModal open onClose={vi.fn()} />);

    expect(screen.getByText("Bước 1: Dòng thời gian liên tục")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Hiểu cách LifeMap kết nối toàn bộ đơn thuốc, xét nghiệm và lần khám thành một bức tranh toàn diện.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("step-1-diagram")).toBeInTheDocument();

    // Check nodes in step 1
    const medsNode = screen.getByText("1. Đơn thuốc");
    const testNode = screen.getByText("2. Xét nghiệm");
    const visitNode = screen.getByText("3. Tái khám lâm sàng");

    expect(medsNode).toBeInTheDocument();
    expect(testNode).toBeInTheDocument();
    expect(visitNode).toBeInTheDocument();

    // Click on Node 2 to inspect callout
    fireEvent.click(testNode);
    expect(
      screen.getByText("Mốc 2: Đối chiếu cận lâm sàng theo dõi tác dụng phụ"),
    ).toBeInTheDocument();

    // Click on Node 3
    fireEvent.click(visitNode);
    expect(
      screen.getByText("Mốc 3: Đánh giá hiệu quả lâm sàng toàn diện"),
    ).toBeInTheDocument();
  });

  it("navigates forward through steps using 'Tiếp tục' button", () => {
    render(<LifeMapGuideModal open onClose={vi.fn()} />);

    // Step 1
    expect(screen.getByText("Bước 1: Dòng thời gian liên tục")).toBeInTheDocument();

    // Click Tiếp tục -> Step 2
    fireEvent.click(screen.getByRole("button", { name: /tiếp tục sang bước tiếp theo/i }));
    expect(screen.getByText("Bước 2: Chuẩn bị đi khám bác sĩ")).toBeInTheDocument();
    expect(
      screen.getByText("Cách tạo bản tóm tắt 1 trang giúp bác sĩ nắm bắt bệnh sử trong 30 giây."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("step-2-diagram")).toBeInTheDocument();

    // Click Tiếp tục -> Step 3
    fireEvent.click(screen.getByRole("button", { name: /tiếp tục sang bước tiếp theo/i }));
    expect(
      screen.getByText("Bước 3: Đối chiếu 2 dòng thời gian (Bitemporal)"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Phân biệt thời gian triệu chứng bắt đầu và thời gian ghi vào hồ sơ để tránh sai sót y khoa.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("step-3-diagram")).toBeInTheDocument();

    // Click Tiếp tục -> Step 4
    fireEvent.click(screen.getByRole("button", { name: /tiếp tục sang bước tiếp theo/i }));
    expect(screen.getByText("Bước 4: Cam kết an toàn GLHS")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Mọi thay đổi dữ liệu y tế được bảo vệ bằng mã hóa, không bao giờ tự ý thay đổi hoặc xóa bỏ lịch sử khám.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("step-4-diagram")).toBeInTheDocument();
    expect(screen.getByTestId("start-experience-button")).toBeInTheDocument();
  });

  it("supports jumping directly to any step via tab clicks and navigating back with 'Quay lại'", () => {
    render(<LifeMapGuideModal open onClose={vi.fn()} />);

    // Jump to step 3
    fireEvent.click(screen.getByRole("tab", { name: /đối chiếu bitemporal/i }));
    expect(
      screen.getByText("Bước 3: Đối chiếu 2 dòng thời gian (Bitemporal)"),
    ).toBeInTheDocument();

    // Click Quay lại -> Step 2
    fireEvent.click(screen.getByRole("button", { name: /quay lại bước trước/i }));
    expect(screen.getByText("Bước 2: Chuẩn bị đi khám bác sĩ")).toBeInTheDocument();
  });

  it("interacts with Step 2 sheet tabs (Bệnh sử, Thuốc & Dị ứng, Câu hỏi cho Bác sĩ)", () => {
    render(<LifeMapGuideModal open initialStep={1} onClose={vi.fn()} />);

    expect(screen.getByText("Bước 2: Chuẩn bị đi khám bác sĩ")).toBeInTheDocument();
    expect(screen.getByText(/Lý do khám chính/i)).toBeInTheDocument();

    // Click Thuốc & Dị ứng
    fireEvent.click(screen.getByRole("button", { name: "Thuốc & Dị ứng" }));
    expect(screen.getByText(/Đơn thuốc đang dùng hàng ngày/i)).toBeInTheDocument();
    expect(screen.getByText(/Dị ứng Penicillin/i)).toBeInTheDocument();

    // Click Câu hỏi cho Bác sĩ
    fireEvent.click(screen.getByRole("button", { name: "Câu hỏi cho Bác sĩ" }));
    expect(screen.getByText(/3 câu hỏi gợi ý nên trao đổi với bác sĩ/i)).toBeInTheDocument();
  });

  it("interacts with Step 3 Bitemporal perspective toggle", () => {
    render(<LifeMapGuideModal open initialStep={2} onClose={vi.fn()} />);

    expect(
      screen.getByText("Bước 3: Đối chiếu 2 dòng thời gian (Bitemporal)"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Trục 1: Thời gian thực tế/i)).toBeInTheDocument();
    expect(screen.getByText(/Trục 2: Thời gian ghi nhận/i)).toBeInTheDocument();
    expect(screen.getByText(/Lợi ích Bitemporal của LifeMap/i)).toBeInTheDocument();

    // Toggle to traditional perspective
    fireEvent.click(screen.getByRole("button", { name: /Hồ sơ thường/i }));
    expect(screen.getByText(/Rủi ro ở hệ thống truyền thống/i)).toBeInTheDocument();
  });

  it("interacts with Step 4 GLHS integrity check", () => {
    vi.useFakeTimers();
    render(<LifeMapGuideModal open initialStep={3} onClose={vi.fn()} />);

    expect(screen.getByText("Bước 4: Cam kết an toàn GLHS")).toBeInTheDocument();
    expect(screen.getByText(/APPEND-ONLY LEDGER/i)).toBeInTheDocument();

    const verifyBtn = screen.getByRole("button", { name: /Kiểm tra tính toàn vẹn/i });
    expect(verifyBtn).toBeInTheDocument();

    fireEvent.click(verifyBtn);

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(screen.getByText(/Hồ sơ đạt 100% tính toàn vẹn mã hóa/i)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("triggers 1-click 'Bắt đầu trải nghiệm ngay' and invokes callbacks", () => {
    const onClose = vi.fn();
    const onStartExperience = vi.fn();

    render(
      <LifeMapGuideModal
        open
        initialStep={3}
        onClose={onClose}
        onStartExperience={onStartExperience}
      />,
    );

    const startBtn = screen.getByTestId("start-experience-button");
    expect(startBtn).toBeInTheDocument();
    expect(startBtn).toHaveTextContent("Bắt đầu trải nghiệm ngay");

    fireEvent.click(startBtn);
    expect(onStartExperience).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes modal on close button click", () => {
    const onClose = vi.fn();
    render(<LifeMapGuideModal open onClose={onClose} />);

    const closeBtn = screen.getByRole("button", { name: "Đóng hướng dẫn" });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes modal on Escape key press", () => {
    const onClose = vi.fn();
    render(<LifeMapGuideModal open onClose={onClose} />);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes modal on backdrop click", () => {
    const onClose = vi.fn();
    const { container } = render(<LifeMapGuideModal open onClose={onClose} />);

    const backdrop = container.querySelector(".bg-\\[rgba\\(16\\,20\\,25\\,0\\.8\\)\\]");
    expect(backdrop).toBeInTheDocument();
    if (backdrop) {
      fireEvent.click(backdrop);
      expect(onClose).toHaveBeenCalledTimes(1);
    }
  });
});
