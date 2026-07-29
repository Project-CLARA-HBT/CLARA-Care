import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import {
  ErrorSummary,
  FeatureReadinessCard,
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  StepProgress,
} from "@/components/guided-flow";

const steps = [
  { id: "name", label: "Tên" },
  { id: "goal", label: "Mục tiêu" },
  { id: "review", label: "Kiểm tra" },
];

afterEach(cleanup);

describe("guided flow primitives", () => {
  it("announces the current step and exposes every step state without relying on color", () => {
    render(<StepProgress steps={steps} currentStep={1} label="Thiết lập LifeMap" />);

    const progress = screen.getByRole("navigation", { name: "Thiết lập LifeMap" });
    expect(progress).toHaveTextContent("Bước 2 / 3");
    expect(progress).toHaveTextContent("Tên: đã hoàn tất");
    expect(progress).toHaveTextContent("Mục tiêu: hiện tại");
    expect(progress).toHaveTextContent("Kiểm tra: chưa bắt đầu");
    expect(progress.querySelector('[aria-current="step"]')).toBeInTheDocument();
  });

  it("clamps an invalid step index so progress always has a valid current step", () => {
    render(<StepProgress steps={steps} currentStep={99} />);
    expect(screen.getByText(/Bước 3 \/ 3/)).toBeInTheDocument();
    expect(screen.getByText(/Kiểm tra: hiện tại/)).toBeInTheDocument();
  });

  it("associates the shell heading and reports saved draft state politely", () => {
    render(
      <GuidedFlowShell
        eyebrow="Tạo hành trình"
        title="Bạn muốn gọi hành trình này là gì?"
        description="Một câu ngắn là đủ."
        steps={steps}
        currentStep={0}
        saveState={{ kind: "saved" }}
        aside={<p>Bạn có thể quay lại sau.</p>}
      >
        <label>
          Tên hành trình
          <input />
        </label>
      </GuidedFlowShell>,
    );

    const region = screen.getByRole("region", {
      name: "Bạn muốn gọi hành trình này là gì?",
    });
    expect(region).toContainElement(screen.getByLabelText("Tên hành trình"));
    expect(screen.getByRole("status")).toHaveTextContent("Đã lưu bản nháp");
    expect(screen.getByText("Bạn có thể quay lại sau.").closest("aside")).not.toBeNull();
  });

  it("uses an assertive alert for a save failure and does not expose raw implementation detail", () => {
    render(
      <GuidedFlowShell
        title="Kiểm tra"
        steps={steps}
        currentStep={2}
        saveState={{ kind: "error", message: "Vui lòng thử lại." }}
      >
        <p>Nội dung</p>
      </GuidedFlowShell>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Chưa thể lưu thay đổi");
    expect(screen.getByRole("alert")).toHaveTextContent("Vui lòng thử lại.");
  });

  it("provides one primary next action plus optional back and skip actions", () => {
    const onNext = vi.fn();
    const onBack = vi.fn();
    render(
      <StepActions
        nextLabel="Lưu và tiếp tục"
        nextType="button"
        onNext={onNext}
        back={{ label: "Quay lại", onClick: onBack }}
        skip={{ label: "Bỏ qua", href: "/next" }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Lưu và tiếp tục" }));
    fireEvent.click(screen.getByRole("button", { name: "Quay lại" }));
    expect(onNext).toHaveBeenCalledOnce();
    expect(onBack).toHaveBeenCalledOnce();
    expect(screen.getByRole("link", { name: "Bỏ qua" })).toHaveAttribute("href", "/next");
  });

  it("disables navigation callbacks while saving", () => {
    const onBack = vi.fn();
    render(
      <StepActions
        saving
        nextLabel="Tiếp tục"
        back={{ label: "Quay lại", onClick: onBack }}
      />,
    );

    expect(screen.getByRole("button", { name: "Đang lưu…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Quay lại" })).toBeDisabled();
  });

  it("turns link navigation into disabled controls while saving", () => {
    render(
      <StepActions
        saving
        back={{ label: "Quay lại", href: "/previous" }}
        skip={{ label: "Bỏ qua", href: "/next" }}
      />,
    );

    expect(screen.queryByRole("link", { name: "Quay lại" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Bỏ qua" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quay lại" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Bỏ qua" })).toBeDisabled();
  });

  it("renders review data semantically and offers an edit destination", () => {
    render(
      <ReviewSection
        title="Thông tin cơ bản"
        description="Kiểm tra trước khi lưu."
        items={[
          { label: "Tên", value: "Nguyễn An" },
          { label: "Nhóm máu", value: "O+" },
        ]}
        edit={{ href: "/welcome/name" }}
      />,
    );

    expect(screen.getByRole("region", { name: "Thông tin cơ bản" })).toBeInTheDocument();
    expect(screen.getByText("Tên").tagName).toBe("DT");
    expect(screen.getByText("Nguyễn An").tagName).toBe("DD");
    expect(screen.getByRole("link", { name: "Chỉnh sửa" })).toHaveAttribute(
      "href",
      "/welcome/name",
    );
  });

  it("summarizes validation errors and links field errors to their controls", () => {
    render(
      <>
        <ErrorSummary
          errors={[
            {
              id: "name-required",
              fieldId: "journey-name",
              fieldLabel: "Tên hành trình",
              message: "Hãy nhập một tên ngắn.",
            },
            {
              id: "save-failed",
              message: "Thay đổi chưa được lưu. Vui lòng thử lại.",
            },
          ]}
        />
        <input id="journey-name" aria-label="Tên hành trình" />
      </>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveAccessibleName("Kiểm tra lại thông tin");
    expect(alert).toHaveAccessibleDescription(
      "Có một vài mục cần được sửa trước khi bạn tiếp tục.",
    );
    expect(
      screen.getByRole("link", {
        name: "Tên hành trình: Hãy nhập một tên ngắn.",
      }),
    ).toHaveAttribute("href", "#journey-name");
    expect(alert).toHaveTextContent("Thay đổi chưa được lưu");
  });

  it("does not render an empty error summary", () => {
    const { container } = render(<ErrorSummary errors={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows actionable readiness without exposing ignored internal configuration", () => {
    const readiness = {
      kind: "unavailable" as const,
      summary: "Kiểm tra tương tác hiện chưa thể chạy.",
      reason: "Nguồn xác minh cần thiết chưa sẵn sàng.",
      userAction: "Kiểm tra lại tên thuốc và thử lại sau.",
      administratorAction: "Xác minh nguồn dữ liệu trong Trung tâm thiết lập.",
      safeFallback: "Không hiển thị kết luận an toàn; hãy hỏi dược sĩ hoặc bác sĩ.",
      internalDetails: "DRUGBANK_PATH=/private/license.sqlite; token=secret",
      provider: "raw-upstream-provider",
    };

    render(
      <FeatureReadinessCard
        title="Kiểm tra tương tác thuốc"
        state={readiness}
        action={{ label: "Mở Trung tâm thiết lập", href: "/admin/setup" }}
      />,
    );

    const card = screen.getByRole("region", {
      name: "Kiểm tra tương tác thuốc",
    });
    expect(card).toHaveTextContent("Tạm thời chưa sẵn sàng");
    expect(card).toHaveTextContent("Bạn có thể làm gì");
    expect(card).toHaveTextContent("Quản trị viên cần làm gì");
    expect(card).toHaveTextContent("Cách tiếp tục an toàn");
    expect(card).not.toHaveTextContent("DRUGBANK_PATH");
    expect(card).not.toHaveTextContent("raw-upstream-provider");
    expect(
      screen.getByRole("link", { name: "Mở Trung tâm thiết lập" }),
    ).toHaveAttribute("href", "/admin/setup");
  });

  it("renders ready state concisely and supports an accessible callback action", () => {
    const onOpen = vi.fn();
    render(
      <FeatureReadinessCard
        title="Nhập tài liệu"
        state={{ kind: "ready", summary: "Bạn có thể tiếp tục." }}
        action={{ label: "Bắt đầu", onClick: onOpen }}
      />,
    );

    expect(screen.getByText("Sẵn sàng")).toBeInTheDocument();
    expect(screen.queryByText("Quản trị viên cần làm gì")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Bắt đầu" }));
    expect(onOpen).toHaveBeenCalledOnce();
  });
});
