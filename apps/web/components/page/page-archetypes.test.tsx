import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  PageFrame,
  PageHeader,
  HubLayout,
  ListDetailLayout,
  WorkflowLayout,
  ConversationLayout,
  CommandCenterLayout,
  SettingsLayout,
} from "./index";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

afterEach(cleanup);

describe("Page Archetype Primitives", () => {
  describe("1. PageFrame", () => {
    it("renders children, header, footer, and aside correctly", () => {
      render(
        <PageFrame
          header={<div data-testid="test-header">Header Content</div>}
          footer={<div data-testid="test-footer">Footer Content</div>}
          aside={<div data-testid="test-aside">Aside Rail</div>}
          archetype="custom-archetype"
        >
          <div data-testid="test-main">Main Content</div>
        </PageFrame>
      );

      expect(screen.getByTestId("test-header")).toBeInTheDocument();
      expect(screen.getByTestId("test-footer")).toBeInTheDocument();
      expect(screen.getByTestId("test-aside")).toBeInTheDocument();
      expect(screen.getByTestId("test-main")).toBeInTheDocument();
    });

    it("applies max-width presets and data-archetype attribute", () => {
      const { container, rerender } = render(
        <PageFrame maxWidth="narrow" archetype="hub">
          <div>Content</div>
        </PageFrame>
      );

      const frame = container.querySelector("[data-archetype='hub']");
      expect(frame).toBeTruthy();
      expect(container.querySelector(".max-w-3xl")).toBeTruthy();

      rerender(
        <PageFrame maxWidth="dense" archetype="command-center">
          <div>Content</div>
        </PageFrame>
      );
      expect(container.querySelector(".max-w-\\[1680px\\]")).toBeTruthy();

      rerender(
        <PageFrame maxWidth="full">
          <div>Content</div>
        </PageFrame>
      );
      expect(container.querySelector(".max-w-full")).toBeTruthy();
    });

    it("applies gutter and canvas background presets", () => {
      const { container, rerender } = render(
        <PageFrame gutter="none" bg="transparent">
          <div>Content</div>
        </PageFrame>
      );

      expect(container.querySelector(".p-0")).toBeTruthy();
      expect(container.querySelector(".bg-transparent")).toBeTruthy();

      rerender(
        <PageFrame gutter="spacious" bg="panel">
          <div>Content</div>
        </PageFrame>
      );
      expect(container.querySelector(".lg\\:px-12")).toBeTruthy();
      expect(container.querySelector(".bg-\\[var\\(--surface-panel\\)\\]")).toBeTruthy();
    });

    it("renders custom element tag via 'as' prop", () => {
      render(
        <PageFrame as="main" aria-label="Main Page Container">
          <div>Content</div>
        </PageFrame>
      );

      expect(screen.getByRole("main", { name: /Main Page Container/i })).toBeInTheDocument();
    });
  });

  describe("2. PageHeader", () => {
    it("renders title, eyebrow, subtitle, badges, and trailing actions", () => {
      render(
        <PageHeader
          eyebrow="Tủ thuốc gia đình"
          title="Thuốc đang sử dụng"
          subtitle="Quản lý phác đồ, nhắc uống thuốc và liều lượng."
          badges={<Badge tone="brand">3 Đang dùng</Badge>}
          actions={<Button variant="primary">Thêm thuốc</Button>}
        />
      );

      expect(screen.getByText("Tủ thuốc gia đình")).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { level: 1, name: /Thuốc đang sử dụng/i })
      ).toBeInTheDocument();
      expect(
        screen.getByText("Quản lý phác đồ, nhắc uống thuốc và liều lượng.")
      ).toBeInTheDocument();
      expect(screen.getByText("3 Đang dùng")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Thêm thuốc/i })
      ).toBeInTheDocument();
    });

    it("renders accessible breadcrumbs navigation", () => {
      const handleHomeClick = vi.fn();
      render(
        <PageHeader
          title="Chi tiết lần khám"
          breadcrumbs={[
            { label: "Trang chủ", href: "/" },
            { label: "Lịch sử khám", onClick: handleHomeClick },
            { label: "Lần khám #1042", active: true },
          ]}
        />
      );

      const nav = screen.getByRole("navigation", { name: /Breadcrumbs/i });
      expect(nav).toBeInTheDocument();

      const homeLink = screen.getByRole("link", { name: "Trang chủ" });
      expect(homeLink).toHaveAttribute("href", "/");

      const listButton = screen.getByRole("button", { name: "Lịch sử khám" });
      fireEvent.click(listButton);
      expect(handleHomeClick).toHaveBeenCalledTimes(1);

      expect(screen.getByText("Lần khám #1042")).toHaveAttribute("aria-current", "page");
    });

    it("renders back button with onClick or href", () => {
      const handleBack = vi.fn();
      const { rerender } = render(
        <PageHeader
          title="Tạo hành trình mới"
          backAction={{ label: "Quay lại LifeMap", onClick: handleBack }}
        />
      );

      const backBtn = screen.getByRole("button", { name: /Quay lại LifeMap/i });
      fireEvent.click(backBtn);
      expect(handleBack).toHaveBeenCalledTimes(1);

      rerender(
        <PageHeader
          title="Tạo hành trình mới"
          backAction={{ label: "Về danh sách", href: "/lifemap" }}
        />
      );

      const backLink = screen.getByRole("link", { name: /Về danh sách/i });
      expect(backLink).toHaveAttribute("href", "/lifemap");
    });

    it("supports sticky, border, and compact density", () => {
      const { container } = render(
        <PageHeader
          title="Bảng điều khiển"
          sticky
          border
          density="compact"
          titleAs="h2"
        />
      );

      const header = container.querySelector("header");
      expect(header).toHaveClass("sticky");
      expect(header).toHaveClass("border-b");
      expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    });
  });

  describe("3. HubLayout", () => {
    it("renders overview banner, quick action tiles, and domain sections", () => {
      const handleQuickAction = vi.fn();

      render(
        <HubLayout
          title="Trung tâm Sức khỏe Cá nhân"
          subtitle="Tổng quan hồ sơ y tế số, chỉ số sinh tồn và kết quả cận lâm sàng."
          overviewBanner={
            <div data-testid="overview-banner">Banner: Tất cả chỉ số ổn định</div>
          }
          quickActions={[
            {
              id: "action-vitals",
              title: "Đo huyết áp mới",
              description: "Ghi nhận chỉ số buổi sáng",
              icon: "body",
              onClick: handleQuickAction,
              badge: <Badge tone="ok">Đến giờ</Badge>,
            },
            {
              id: "action-meds",
              title: "Xem đơn thuốc",
              description: "3 loại thuốc cần uống hôm nay",
              icon: "medication",
              href: "/medicines",
            },
          ]}
          domainSections={[
            {
              id: "section-vitals",
              title: "Chỉ số sinh tồn",
              description: "Huyết áp, nhịp tim, đường huyết",
              icon: "body",
              children: <div data-testid="vitals-content">Dữ liệu sinh tồn gần nhất</div>,
            },
          ]}
        />
      );

      expect(
        screen.getByRole("heading", { level: 1, name: /Trung tâm Sức khỏe Cá nhân/i })
      ).toBeInTheDocument();
      expect(screen.getByTestId("overview-banner")).toBeInTheDocument();

      const actionButton = screen.getByRole("button", { name: /Đo huyết áp mới/i });
      fireEvent.click(actionButton);
      expect(handleQuickAction).toHaveBeenCalledTimes(1);

      const actionLink = screen.getByRole("link", { name: /Xem đơn thuốc/i });
      expect(actionLink).toHaveAttribute("href", "/medicines");

      expect(screen.getByText("Chỉ số sinh tồn")).toBeInTheDocument();
      expect(screen.getByTestId("vitals-content")).toBeInTheDocument();
    });
  });

  describe("4. ListDetailLayout", () => {
    it("renders list and detail inspector in split mode", () => {
      render(
        <ListDetailLayout
          title="Danh sách Bệnh nhân"
          toolbar={<input placeholder="Tìm kiếm bệnh nhân..." />}
          list={<div data-testid="patient-list">Danh sách 20 bệnh nhân</div>}
          detail={<div data-testid="patient-detail">Chi tiết bệnh nhân #001</div>}
          splitRatio="60/40"
        />
      );

      expect(screen.getByPlaceholderText("Tìm kiếm bệnh nhân...")).toBeInTheDocument();
      expect(screen.getByTestId("patient-list")).toBeInTheDocument();
      expect(screen.getByTestId("patient-detail")).toBeInTheDocument();
    });

    it("renders fallback empty state when no detail is selected in split mode", () => {
      render(
        <ListDetailLayout
          title="Nhật ký Hoạt động An toàn"
          list={<div data-testid="audit-list">Danh sách 50 bản ghi</div>}
        />
      );

      expect(screen.getByTestId("audit-list")).toBeInTheDocument();
      expect(screen.getByText("Chưa chọn mục nào")).toBeInTheDocument();
    });

    it("renders drawer mode with inspector controls", () => {
      const handleClose = vi.fn();
      render(
        <ListDetailLayout
          title="Hàng đợi Phản hồi Lâm sàng"
          inspectorMode="drawer"
          inspectorOpen={true}
          onInspectorClose={handleClose}
          list={<div data-testid="feedback-list">Danh sách phản hồi</div>}
          detail={<div data-testid="feedback-inspector">Inspector nội dung phản hồi</div>}
        />
      );

      expect(screen.getByTestId("feedback-list")).toBeInTheDocument();
      expect(screen.getByTestId("feedback-inspector")).toBeInTheDocument();
    });
  });

  describe("5. WorkflowLayout", () => {
    it("renders multi-step wizard, current step content, and default action buttons", () => {
      const handleBack = vi.fn();
      const handleNext = vi.fn();

      render(
        <WorkflowLayout
          title="Chuẩn bị Lần khám Mới"
          steps={[
            { id: "step-1", label: "Lý do khám" },
            { id: "step-2", label: "Triệu chứng" },
            { id: "step-3", label: "Thuốc mang theo" },
            { id: "step-4", label: "Xem lại & Lưu" },
          ]}
          currentStep={1}
          onBack={handleBack}
          onNext={handleNext}
        >
          <div data-testid="step-body">Nhập các triệu chứng hiện tại</div>
        </WorkflowLayout>
      );

      expect(screen.getByText("Chuẩn bị Lần khám Mới")).toBeInTheDocument();
      expect(screen.getByTestId("step-body")).toBeInTheDocument();

      const backBtn = screen.getByRole("button", { name: /Quay lại/i });
      fireEvent.click(backBtn);
      expect(handleBack).toHaveBeenCalledTimes(1);

      const nextBtn = screen.getByRole("button", { name: /Tiếp tục/i });
      fireEvent.click(nextBtn);
      expect(handleNext).toHaveBeenCalledTimes(1);
    });

    it("renders saving, saved, and error draft states correctly", () => {
      const { rerender } = render(
        <WorkflowLayout
          title="Hội chẩn Hội đồng Chuyên khoa"
          steps={[{ id: "s1", label: "Bước 1" }]}
          currentStep={0}
          saveState={{ kind: "saving", message: "Đang tự động lưu..." }}
        >
          <div>Nội dung</div>
        </WorkflowLayout>
      );

      expect(screen.getByText("Đang tự động lưu...")).toBeInTheDocument();

      rerender(
        <WorkflowLayout
          title="Hội chẩn Hội đồng Chuyên khoa"
          steps={[{ id: "s1", label: "Bước 1" }]}
          currentStep={0}
          saveState={{ kind: "error", message: "Mất kết nối máy chủ CLARA" }}
        >
          <div>Nội dung</div>
        </WorkflowLayout>
      );

      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText("Mất kết nối máy chủ CLARA")).toBeInTheDocument();
    });

    it("supports vertical step navigation and summary rail", () => {
      render(
        <WorkflowLayout
          title="Tạo Hành trình Sức khỏe"
          steps={[
            { id: "s1", label: "Mục tiêu sức khỏe" },
            { id: "s2", label: "Kế hoạch theo dõi" },
          ]}
          currentStep={0}
          orientation="vertical"
          summaryRail={<div data-testid="summary-rail">Tóm tắt hành trình</div>}
        >
          <div>Nội dung bước 1</div>
        </WorkflowLayout>
      );

      expect(screen.getByText("Mục tiêu sức khỏe")).toBeInTheDocument();
      expect(screen.getByTestId("summary-rail")).toBeInTheDocument();
    });
  });

  describe("6. ConversationLayout", () => {
    it("renders central chat feed, input composer, and safety disclaimer banner", () => {
      render(
        <ConversationLayout
          title="Tư vấn Sức khỏe cùng CLARA"
          subtitle="Phiên hội thoại an toàn, tuân thủ Luật Khám chữa bệnh 2023"
          disclaimerBanner={
            <div>CLARA là trợ lý y tế số hỗ trợ tra cứu, không thay thế bác sĩ.</div>
          }
          messages={<div data-testid="chat-messages">Lịch sử 5 tin nhắn</div>}
          composer={<input placeholder="Hỏi CLARA về triệu chứng hoặc đơn thuốc..." />}
        />
      );

      expect(screen.getByText("Tư vấn Sức khỏe cùng CLARA")).toBeInTheDocument();
      expect(
        screen.getByText(/CLARA là trợ lý y tế số hỗ trợ tra cứu/i)
      ).toBeInTheDocument();
      expect(screen.getByTestId("chat-messages")).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText("Hỏi CLARA về triệu chứng hoặc đơn thuốc...")
      ).toBeInTheDocument();
    });

    it("supports collapsible sidebar history and evidence inspector rail", () => {
      const handleToggleSidebar = vi.fn();
      const handleToggleInspector = vi.fn();

      render(
        <ConversationLayout
          title="Hội thoại Chuyên sâu"
          sidebar={<div data-testid="history-sidebar">Danh sách cuộc trò chuyện</div>}
          sidebarOpen={true}
          onToggleSidebar={handleToggleSidebar}
          inspector={<div data-testid="evidence-inspector">Nguồn tài liệu y khoa</div>}
          inspectorOpen={true}
          onToggleInspector={handleToggleInspector}
          messages={<div>Nội dung chat</div>}
        />
      );

      expect(screen.getByTestId("history-sidebar")).toBeInTheDocument();
      expect(screen.getByTestId("evidence-inspector")).toBeInTheDocument();

      const toggleSidebarBtn = screen.getByRole("button", {
        name: /Toggle conversation history/i,
      });
      fireEvent.click(toggleSidebarBtn);
      expect(handleToggleSidebar).toHaveBeenCalledTimes(1);

      const toggleInspectorBtn = screen.getByRole("button", {
        name: /Toggle context panel/i,
      });
      fireEvent.click(toggleInspectorBtn);
      expect(handleToggleInspector).toHaveBeenCalledTimes(1);
    });
  });

  describe("7. CommandCenterLayout", () => {
    it("renders KPI metrics, command strip, and operational stream layout", () => {
      const handleMetricClick = vi.fn();

      render(
        <CommandCenterLayout
          title="Bảng điều khiển Giám sát Hệ thống"
          commandStrip={
            <div data-testid="command-strip">Tabs: Tổng quan | Dịch vụ | An toàn | SLA</div>
          }
          metrics={[
            {
              id: "kpi-api",
              label: "Tổng truy vấn / phút",
              value: "1,240",
              change: "+12%",
              trend: "up",
              tone: "ok",
              onClick: handleMetricClick,
            },
            {
              id: "kpi-fides",
              label: "FIDES Can thiệp DDI",
              value: "38",
              tone: "warn",
            },
          ]}
          liveStream={<div data-testid="live-stream">Luồng sự kiện thời gian thực</div>}
          density="dense"
        >
          <div data-testid="dashboard-charts">Biểu đồ độ trễ và tỷ lệ lỗi</div>
        </CommandCenterLayout>
      );

      expect(
        screen.getByText("Bảng điều khiển Giám sát Hệ thống")
      ).toBeInTheDocument();
      expect(screen.getByTestId("command-strip")).toBeInTheDocument();
      expect(screen.getByText("Tổng truy vấn / phút")).toBeInTheDocument();
      expect(screen.getByText("1,240")).toBeInTheDocument();
      expect(screen.getByText("+12%")).toBeInTheDocument();
      expect(screen.getByText("FIDES Can thiệp DDI")).toBeInTheDocument();

      const metricCard = screen.getByText("Tổng truy vấn / phút").closest("section");
      if (metricCard) {
        fireEvent.click(metricCard);
        expect(handleMetricClick).toHaveBeenCalled();
      }

      expect(screen.getByTestId("dashboard-charts")).toBeInTheDocument();
      expect(screen.getByTestId("live-stream")).toBeInTheDocument();
    });
  });

  describe("8. SettingsLayout", () => {
    it("renders categorized navigation, profile banner, and handles category changes", () => {
      const handleCategoryChange = vi.fn();

      render(
        <SettingsLayout
          title="Cài đặt & Tùy chọn"
          profileBanner={<div data-testid="profile-banner">Tài khoản: Nguyễn Văn A</div>}
          categories={[
            { id: "account", label: "Tài khoản & Bảo mật", icon: "user-card" },
            { id: "privacy", label: "Quyền riêng tư & AI", icon: "warning" },
            { id: "notifications", label: "Thông báo & Lời nhắc", icon: "notifications" },
          ]}
          activeCategoryId="account"
          onCategoryChange={handleCategoryChange}
          aside={<div data-testid="privacy-guarantee">Cam kết Không lưu trữ CoT & Zero-PII</div>}
          saveBar={<button type="button">Lưu thay đổi</button>}
        >
          <div data-testid="settings-form">Form cài đặt tài khoản</div>
        </SettingsLayout>
      );

      expect(screen.getByText("Cài đặt & Tùy chọn")).toBeInTheDocument();
      expect(screen.getByTestId("profile-banner")).toBeInTheDocument();
      expect(screen.getByTestId("privacy-guarantee")).toBeInTheDocument();
      expect(screen.getByTestId("settings-form")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Lưu thay đổi" })).toBeInTheDocument();

      // Click on another category
      const privacyCategoryBtns = screen.getAllByRole("button", {
        name: /Quyền riêng tư & AI/i,
      });
      fireEvent.click(privacyCategoryBtns[0]);
      expect(handleCategoryChange).toHaveBeenCalledWith("privacy");
    });
  });
});
