import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  Alert,
  AlertTitle,
  AlertDescription,
  Timeline,
  TimelineItem,
  TimelineNode,
  TimelineContent,
  TimelineTitle,
  TimelineDescription,
  TimelineTimestamp,
  SourceDisclosure,
  SourceDisclosureBadge,
  SourceDisclosurePanel,
  SourceItemCard,
} from "@/components/ui";

afterEach(cleanup);

describe("Alert primitive", () => {
  it("renders multi-tone alert banners with appropriate default icons and roles", () => {
    const { container, rerender } = render(
      <Alert tone="info" title="Thông tin" description="Nội dung thông tin y tế." />,
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "info");
    expect(container.querySelector('[data-icon="clinical-notes"]')).toBeInTheDocument();
    expect(screen.getByText("Thông tin")).toBeInTheDocument();
    expect(screen.getByText("Nội dung thông tin y tế.")).toBeInTheDocument();

    // Warning tone
    rerender(<Alert tone="warning" title="Cảnh báo" description="Vui lòng kiểm tra liều lượng." />);
    expect(screen.getByRole("alert")).toHaveAttribute("data-tone", "warn");
    expect(container.querySelector('[data-icon="warning"]')).toBeInTheDocument();

    // Danger tone
    rerender(<Alert tone="danger" title="Nguy hiểm" description="Tương tác thuốc nghiêm trọng." />);
    expect(screen.getByRole("alert")).toHaveAttribute("data-tone", "danger");
    expect(container.querySelector('[data-icon="warning"]')).toBeInTheDocument();

    // Success tone
    rerender(<Alert tone="success" title="Thành công" description="Đã cập nhật hồ sơ." />);
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "success");
    expect(container.querySelector('[data-icon="check"]')).toBeInTheDocument();

    // Neutral tone
    rerender(<Alert tone="neutral" title="Ghi chú" description="Hệ thống đang hoạt động." />);
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "neutral");
    expect(container.querySelector('[data-icon="clinical-notes"]')).toBeInTheDocument();
  });

  it("supports custom icons, suppressing icon, and custom role", () => {
    const { container, rerender } = render(
      <Alert tone="info" icon="emergency" title="Cấp cứu" role="alert" />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(container.querySelector('[data-icon="emergency"]')).toBeInTheDocument();

    // Icon false
    rerender(<Alert tone="info" icon={false} title="Không có biểu tượng" />);
    expect(container.querySelector("svg")).not.toBeInTheDocument();

    // Custom ReactNode icon
    rerender(
      <Alert
        tone="info"
        icon={<span data-testid="custom-jsx-icon">★</span>}
        title="Custom JSX"
      />,
    );
    expect(screen.getByTestId("custom-jsx-icon")).toBeInTheDocument();
  });

  it("handles dismissible state and calls onDismiss callback", () => {
    const handleDismiss = vi.fn();
    render(
      <Alert
        tone="warn"
        title="Cảnh báo có thể đóng"
        dismissible
        onDismiss={handleDismiss}
      />,
    );

    const closeButton = screen.getByRole("button", { name: "Đóng thông báo" });
    expect(closeButton).toBeInTheDocument();

    fireEvent.click(closeButton);
    expect(handleDismiss).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Cảnh báo có thể đóng")).not.toBeInTheDocument();
  });

  it("renders action button and different variants", () => {
    const { rerender } = render(
      <Alert
        tone="danger"
        title="Lỗi tải"
        action={<button type="button">Thử lại</button>}
        variant="bordered"
      />,
    );

    expect(screen.getByRole("button", { name: "Thử lại" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveAttribute("data-variant", "bordered");

    rerender(<Alert tone="info" title="Banner" variant="banner" />);
    expect(screen.getByRole("status")).toHaveAttribute("data-variant", "banner");

    rerender(<Alert tone="info" title="Filled" variant="filled" />);
    expect(screen.getByRole("status")).toHaveAttribute("data-variant", "filled");
  });

  it("supports standalone subcomponents AlertTitle and AlertDescription", () => {
    render(
      <div>
        <AlertTitle>Tiêu đề độc lập</AlertTitle>
        <AlertDescription>Mô tả chi tiết độc lập.</AlertDescription>
      </div>,
    );

    expect(screen.getByText("Tiêu đề độc lập")).toBeInTheDocument();
    expect(screen.getByText("Mô tả chi tiết độc lập.")).toBeInTheDocument();
  });
});

describe("Timeline primitive", () => {
  it("renders data-driven event stream with all node states", () => {
    const items = [
      {
        id: "step-1",
        state: "completed" as const,
        title: "Khởi tạo hồ sơ",
        description: "Hồ sơ sức khỏe đã được tạo thành công.",
        timestamp: "10:00 01/01/2026",
      },
      {
        id: "step-2",
        state: "active" as const,
        title: "Đang xét nghiệm",
        description: "Đang tiến hành phân tích chỉ số máu.",
        timestamp: "10:30 01/01/2026",
      },
      {
        id: "step-3",
        state: "disputed" as const,
        title: "Cần xác thực thông tin",
        description: "Kết quả có mâu thuẫn cần bác sĩ đối chiếu.",
      },
      {
        id: "step-4",
        state: "error" as const,
        title: "Lỗi kết nối máy đo",
      },
      {
        id: "step-5",
        state: "pending" as const,
        title: "Tư vấn bác sĩ",
      },
    ];

    const { container } = render(<Timeline items={items} />);

    expect(screen.getByRole("list")).toHaveAttribute("data-orientation", "vertical");
    expect(screen.getByText("Khởi tạo hồ sơ")).toBeInTheDocument();
    expect(screen.getByText("10:00 01/01/2026")).toBeInTheDocument();
    expect(screen.getByText("Đang xét nghiệm")).toBeInTheDocument();
    expect(screen.getByText("Cần xác thực thông tin")).toBeInTheDocument();
    expect(screen.getByText("Lỗi kết nối máy đo")).toBeInTheDocument();
    expect(screen.getByText("Tư vấn bác sĩ")).toBeInTheDocument();

    const nodes = container.querySelectorAll("[data-state]");
    expect(nodes.length).toBeGreaterThanOrEqual(5);

    // Verify connectors exist between nodes
    const connectors = screen.getAllByTestId("timeline-connector-vertical");
    expect(connectors).toHaveLength(items.length - 1);
  });

  it("supports horizontal orientation and custom click handler", () => {
    const onClick = vi.fn();
    render(
      <Timeline
        orientation="horizontal"
        items={[
          { id: "h1", state: "completed", title: "Bước 1", onClick },
          { id: "h2", state: "active", title: "Bước 2" },
        ]}
      />,
    );

    expect(screen.getByRole("list")).toHaveAttribute("data-orientation", "horizontal");
    expect(screen.getByTestId("timeline-connector-horizontal")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Bước 1"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("supports composable JSX timeline structure", () => {
    render(
      <Timeline>
        <TimelineItem state="completed">
          <TimelineNode state="completed" icon="check" />
          <TimelineContent>
            <TimelineTitle>Bước thủ công 1</TimelineTitle>
            <TimelineTimestamp>08:00</TimelineTimestamp>
            <TimelineDescription>Mô tả chi tiết</TimelineDescription>
          </TimelineContent>
        </TimelineItem>
        <TimelineItem state="pending" isLast>
          <TimelineNode state="pending" />
          <TimelineContent>
            <TimelineTitle>Bước thủ công 2</TimelineTitle>
          </TimelineContent>
        </TimelineItem>
      </Timeline>,
    );

    expect(screen.getByText("Bước thủ công 1")).toBeInTheDocument();
    expect(screen.getByText("08:00")).toBeInTheDocument();
    expect(screen.getByText("Mô tả chi tiết")).toBeInTheDocument();
    expect(screen.getByText("Bước thủ công 2")).toBeInTheDocument();
  });
});

describe("SourceDisclosure primitive", () => {
  const sampleSources = [
    {
      id: "src-1",
      title: "Dược thư Quốc gia Việt Nam 2024",
      publication: "Bộ Y tế",
      year: 2024,
      snippet: "Paracetamol được chỉ định hạ sốt và giảm đau nhẹ đến vừa.",
      confidenceScore: 0.98,
      trustTier: "Tier 1",
      verificationState: "verified",
      url: "https://duocthu.gov.vn",
      tags: ["Dược thư", "Bộ Y tế"],
    },
    {
      id: "src-2",
      title: "Hồ sơ xét nghiệm máu 2025",
      snippet: "Chỉ số ALT/AST trong ngưỡng an toàn.",
      verificationState: "verified",
      tags: ["Hồ sơ cá nhân"],
    },
  ];

  it("renders trigger badge and toggles panel open/close in uncontrolled mode", () => {
    render(
      <SourceDisclosure
        sources={sampleSources}
        confidenceScore={98}
        verificationLabel="FIDES Verified"
      />,
    );

    const trigger = screen.getByRole("button", { name: /2 nguồn trích dẫn/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("98%")).toBeInTheDocument();
    expect(screen.getByText("FIDES Verified")).toBeInTheDocument();

    // Initially panel is not open
    expect(screen.queryByText("Dược thư Quốc gia Việt Nam 2024")).not.toBeInTheDocument();

    // Open panel
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region")).toBeInTheDocument();
    expect(screen.getByText("Dược thư Quốc gia Việt Nam 2024")).toBeInTheDocument();
    expect(screen.getAllByText(/Bộ Y tế/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Paracetamol được chỉ định/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Xem tài liệu gốc/i })).toHaveAttribute(
      "href",
      "https://duocthu.gov.vn",
    );

    // Close panel
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Dược thư Quốc gia Việt Nam 2024")).not.toBeInTheDocument();
  });

  it("supports controlled expansion mode and onToggle callback", () => {
    const handleToggle = vi.fn();
    const { rerender } = render(
      <SourceDisclosure
        sources={sampleSources}
        expanded={false}
        onToggle={handleToggle}
      />,
    );

    const trigger = screen.getByRole("button");
    fireEvent.click(trigger);
    expect(handleToggle).toHaveBeenCalledWith(true);

    // Rerender as expanded
    rerender(
      <SourceDisclosure
        sources={sampleSources}
        expanded={true}
        onToggle={handleToggle}
      />,
    );
    expect(screen.getByText("Dược thư Quốc gia Việt Nam 2024")).toBeInTheDocument();
  });

  it("renders category breakdown when provided", () => {
    render(
      <SourceDisclosure
        sources={sampleSources}
        defaultExpanded={true}
        breakdown={[
          { category: "guidelines", label: "Hướng dẫn y tế", count: 1 },
          { category: "phr", label: "Hồ sơ cá nhân", count: 1 },
        ]}
      />,
    );

    expect(screen.getByText("Hướng dẫn y tế:")).toBeInTheDocument();
    expect(screen.getByText("Hồ sơ cá nhân:")).toBeInTheDocument();
  });

  it("renders empty state in panel when no sources are passed", () => {
    render(<SourceDisclosure sources={[]} defaultExpanded={true} />);
    expect(screen.getByText("Chưa có nguồn trích dẫn chi tiết.")).toBeInTheDocument();
  });

  it("supports composable SourceDisclosureBadge and SourceDisclosurePanel subcomponents", () => {
    render(
      <div>
        <SourceDisclosureBadge count={1} expanded={true} label="1 nguồn" />
        <SourceDisclosurePanel>
          <SourceItemCard
            source={{
              title: "Tài liệu độc lập",
              verificationState: "disputed",
              confidenceScore: 0.65,
            }}
          />
        </SourceDisclosurePanel>
      </div>,
    );

    expect(screen.getByText("1 nguồn")).toBeInTheDocument();
    expect(screen.getByText("Tài liệu độc lập")).toBeInTheDocument();
    expect(screen.getByText("Tranh chấp")).toBeInTheDocument();
    expect(screen.getByText("65%")).toBeInTheDocument();
  });
});
