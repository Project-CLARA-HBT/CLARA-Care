import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HeroObject } from "@/components/ui/hero-object";
import { ActionObject } from "@/components/ui/action-object";
import { EditorialSection } from "@/components/ui/editorial-section";

afterEach(cleanup);

describe("HeroObject Component", () => {
  it("renders title, description, contextTag, status, and supportingMeta", () => {
    render(
      <HeroObject
        title="Uống thuốc huyết áp buổi sáng"
        description="Amlodipine 5mg — 1 viên sau ăn sáng."
        contextTag="Nhiệm vụ tiếp theo"
        status="Đến giờ"
        supportingMeta="08:00 AM • Hôm nay"
      />
    );

    expect(
      screen.getByRole("heading", { name: /Uống thuốc huyết áp buổi sáng/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText("Amlodipine 5mg — 1 viên sau ăn sáng.")
    ).toBeInTheDocument();
    expect(screen.getByText("Nhiệm vụ tiếp theo")).toBeInTheDocument();
    expect(screen.getByText("Đến giờ")).toBeInTheDocument();
    expect(screen.getByText("08:00 AM • Hôm nay")).toBeInTheDocument();
  });

  it("supports badge alias for contextTag", () => {
    render(
      <HeroObject
        title="Khám phá hành trình mới"
        badge="LifeMap Journey"
      />
    );

    expect(screen.getByText("LifeMap Journey")).toBeInTheDocument();
  });

  it("renders all 4 semantic variants with data-variant attribute", () => {
    const { rerender, container } = render(
      <HeroObject title="Task Primary" variant="primary" />
    );
    expect(container.querySelector("[data-variant='primary']")).toBeTruthy();

    rerender(<HeroObject title="Journey Task" variant="journey" />);
    expect(container.querySelector("[data-variant='journey']")).toBeTruthy();

    rerender(<HeroObject title="Clinical Case" variant="clinical" />);
    expect(container.querySelector("[data-variant='clinical']")).toBeTruthy();

    rerender(<HeroObject title="Safety Warning" variant="alert" />);
    expect(container.querySelector("[data-variant='alert']")).toBeTruthy();
  });

  it("renders primary action as a link when href is supplied", () => {
    render(
      <HeroObject
        title="Hội đồng Chuyên khoa"
        primaryAction={{
          label: "Tiếp tục hội chẩn",
          href: "/council/case-123",
          icon: "progress",
        }}
      />
    );

    const link = screen.getByRole("link", { name: /Tiếp tục hội chẩn/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/council/case-123");
  });

  it("renders primary action as a button and fires onClick handler", () => {
    const handleClick = vi.fn();
    render(
      <HeroObject
        title="Đánh dấu đã uống"
        primaryAction={{
          label: "Xác nhận uống thuốc",
          onClick: handleClick,
          icon: "check",
        }}
      />
    );

    const button = screen.getByRole("button", { name: /Xác nhận uống thuốc/i });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("renders secondary action as an object or custom ReactNode", () => {
    const handleSecondary = vi.fn();
    const { rerender } = render(
      <HeroObject
        title="Đo huyết áp"
        primaryAction={{ label: "Ghi nhận ngay" }}
        secondaryAction={{
          label: "Nhắc lại sau",
          onClick: handleSecondary,
        }}
      />
    );

    const secondaryBtn = screen.getByRole("button", { name: /Nhắc lại sau/i });
    expect(secondaryBtn).toBeInTheDocument();
    fireEvent.click(secondaryBtn);
    expect(handleSecondary).toHaveBeenCalledTimes(1);

    rerender(
      <HeroObject
        title="Đo huyết áp"
        primaryAction={{ label: "Ghi nhận ngay" }}
        secondaryAction={<span data-testid="custom-secondary">Bỏ qua</span>}
      />
    );
    expect(screen.getByTestId("custom-secondary")).toHaveTextContent("Bỏ qua");
  });

  it("renders progress bar with numerical value and label", () => {
    render(
      <HeroObject
        title="Hành trình Tim mạch"
        progress={{ value: 3, max: 5, label: "Bước 3 / 5" }}
      />
    );

    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toBeInTheDocument();
    expect(progressbar).toHaveAttribute("aria-valuenow", "3");
    expect(progressbar).toHaveAttribute("aria-valuemax", "5");
    expect(screen.getByText("Bước 3 / 5")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
  });

  it("renders optional hero icon and extra children slot", () => {
    render(
      <HeroObject
        title="Đơn thuốc định kỳ"
        icon="medication"
      >
        <div data-testid="hero-child-content">Chi tiết toa thuốc #9821</div>
      </HeroObject>
    );

    expect(screen.getByTestId("hero-child-content")).toBeInTheDocument();
  });

  it("disables primary action when disabled prop is true", () => {
    render(
      <HeroObject
        title="Đang khóa"
        primaryAction={{
          label: "Chưa khả dụng",
          onClick: vi.fn(),
          disabled: true,
        }}
      />
    );

    const button = screen.getByRole("button", { name: /Chưa khả dụng/i });
    expect(button).toBeDisabled();
  });
});

describe("ActionObject Component", () => {
  it("renders title, description, badge, icon, and 3 highlights", () => {
    render(
      <ActionObject
        title="Hội đồng AI (Council)"
        description="Phân tích ca bệnh đa chuyên khoa với phản biện chéo."
        badge="AI Council"
        icon="progress"
        highlights={[
          "Triage đa chuyên khoa",
          "Phát hiện bất đồng thuận",
          "Xác thực FIDES",
        ]}
        href="/council"
      />
    );

    expect(screen.getByText("Hội đồng AI (Council)")).toBeInTheDocument();
    expect(
      screen.getByText("Phân tích ca bệnh đa chuyên khoa với phản biện chéo.")
    ).toBeInTheDocument();
    expect(screen.getByText("AI Council")).toBeInTheDocument();
    expect(screen.getByText("Triage đa chuyên khoa")).toBeInTheDocument();
    expect(screen.getByText("Phát hiện bất đồng thuận")).toBeInTheDocument();
    expect(screen.getByText("Xác thực FIDES")).toBeInTheDocument();
  });

  it("renders as a link when href is supplied", () => {
    render(
      <ActionObject
        title="Ghi chép khám (SOAP)"
        description="Chuyển âm hội thoại bác sĩ - bệnh nhân."
        href="/scribe"
      />
    );

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/scribe");
  });

  it("renders as a button and triggers onClick when no href is supplied", () => {
    const handleClick = vi.fn();
    render(
      <ActionObject
        title="Chuẩn bị thăm khám"
        description="Tạo bảng tóm tắt triệu chứng cho bác sĩ."
        onClick={handleClick}
      />
    );

    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("supports all 4 tones with data-tone attribute", () => {
    const { rerender, container } = render(
      <ActionObject title="Council" description="Desc" tone="brand" />
    );
    expect(container.querySelector("[data-tone='brand']")).toBeTruthy();

    rerender(<ActionObject title="Scribe" description="Desc" tone="mint" />);
    expect(container.querySelector("[data-tone='mint']")).toBeTruthy();

    rerender(<ActionObject title="Evidence" description="Desc" tone="iris" />);
    expect(container.querySelector("[data-tone='iris']")).toBeTruthy();

    rerender(<ActionObject title="Safety" description="Desc" tone="warning" />);
    expect(container.querySelector("[data-tone='warning']")).toBeTruthy();
  });

  it("supports custom actionLabel or defaults based on tone", () => {
    const { rerender } = render(
      <ActionObject
        title="Custom Label Test"
        description="Desc"
        actionLabel="Khám phá ngay"
      />
    );
    expect(screen.getByText("Khám phá ngay")).toBeInTheDocument();

    rerender(
      <ActionObject
        title="Warning Tone Test"
        description="Desc"
        tone="warning"
      />
    );
    expect(screen.getByText("Xem cảnh báo")).toBeInTheDocument();
  });

  it("renders disabled state with aria-disabled", () => {
    render(
      <ActionObject
        title="Tính năng thử nghiệm"
        description="Đang bảo trì nâng cấp."
        disabled
        href="/future"
      />
    );

    expect(screen.getByText("Tính năng thử nghiệm")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });
});

describe("EditorialSection Component", () => {
  it("renders header hierarchy with eyebrow, title, description, and trailing action", () => {
    render(
      <EditorialSection
        id="care-journey"
        eyebrow="TIẾP TỤC HÀNH TRÌNH"
        title="Chăm sóc Tim mạch & Huyết áp"
        description="Kế hoạch điều trị 30 ngày dưới sự hướng dẫn của bác sĩ chuyên khoa."
        action={<button type="button">Xem tất cả</button>}
      >
        <div data-testid="section-content">Nội dung bài viết</div>
      </EditorialSection>
    );

    expect(screen.getByText("TIẾP TỤC HÀNH TRÌNH")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Chăm sóc Tim mạch & Huyết áp" })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Kế hoạch điều trị 30 ngày dưới sự hướng dẫn của bác sĩ chuyên khoa."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xem tất cả" })).toBeInTheDocument();
    expect(screen.getByTestId("section-content")).toBeInTheDocument();
  });

  it("associates aria-labelledby with heading id", () => {
    const { container } = render(
      <EditorialSection
        id="clinical-tools"
        title="Công cụ Lâm sàng"
      >
        <p>Content</p>
      </EditorialSection>
    );

    const section = container.querySelector("section");
    expect(section).toHaveAttribute("aria-labelledby", "clinical-tools-heading");
  });

  it("renders as custom element with 'as' prop", () => {
    const { container } = render(
      <EditorialSection as="article" title="Article Title">
        <p>Article content</p>
      </EditorialSection>
    );

    expect(container.querySelector("article")).toBeTruthy();
  });

  it("applies maxWidth constraint classes", () => {
    const { container, rerender } = render(
      <EditorialSection title="Reading width" maxWidth="reading">
        <p>Text</p>
      </EditorialSection>
    );
    expect(container.firstChild).toHaveClass("max-w-[68ch]");

    rerender(
      <EditorialSection title="4XL width" maxWidth="4xl">
        <p>Text</p>
      </EditorialSection>
    );
    expect(container.firstChild).toHaveClass("max-w-4xl");
  });

  it("applies variant container classes (card, subtle, inset)", () => {
    const { container, rerender } = render(
      <EditorialSection title="Card variant" variant="card">
        <p>Text</p>
      </EditorialSection>
    );
    expect(container.firstChild).toHaveClass("bg-[var(--surface-panel)]");

    rerender(
      <EditorialSection title="Subtle variant" variant="subtle">
        <p>Text</p>
      </EditorialSection>
    );
    expect(container.firstChild).toHaveClass("bg-[var(--surface-muted)]/50");

    rerender(
      <EditorialSection title="Inset variant" variant="inset">
        <p>Text</p>
      </EditorialSection>
    );
    expect(container.firstChild).toHaveClass("bg-[var(--surface-lowest,#0b0e13)]");
  });

  it("renders only children when no header props are supplied", () => {
    const { container } = render(
      <EditorialSection>
        <div data-testid="pure-content">Chỉ có nội dung</div>
      </EditorialSection>
    );

    expect(container.querySelector("header")).toBeNull();
    expect(screen.getByTestId("pure-content")).toBeInTheDocument();
  });
});
