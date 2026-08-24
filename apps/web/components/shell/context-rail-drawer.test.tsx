import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  ContextRail,
  type ContextRailItem,
  type ContextRailGroup,
  InspectorDrawer,
  InspectorDrawerSection,
  InspectorDrawerField,
  SourceInspectorView,
  EvidenceBreakdownView,
  PatientDetailsView,
  TelemetryInspectorView,
  type SourceInspectionItem,
  type EvidenceClaimBreakdown,
  type PatientDetailsData,
  type TelemetryInspectionData,
} from "./index";

/* ========================================================================= */
/* Test Data Fixtures                                                        */
/* ========================================================================= */

const MOCK_RAIL_ITEMS: ContextRailItem[] = [
  {
    id: "item-chat",
    key: "chat",
    label: "Hội thoại lâm sàng",
    subtitle: "Phiên khám trực tuyến",
    icon: "chat",
    badge: 3,
    badgeVariant: "brand",
  },
  {
    id: "item-records",
    key: "records",
    label: "Hồ sơ bệnh án",
    icon: "folder",
    badge: "Mới",
    badgeVariant: "warning",
  },
  {
    id: "item-disabled",
    key: "disabled",
    label: "Tính năng khóa",
    icon: "warning",
    disabled: true,
  },
  {
    id: "item-settings",
    key: "settings",
    label: "Cấu hình phân hệ",
    icon: "settings",
  },
];

const MOCK_RAIL_GROUPS: ContextRailGroup[] = [
  {
    id: "grp-clinical",
    title: "Lâm sàng",
    items: [
      { id: "c-1", key: "c-1", label: "Khám tổng quát", icon: "clinical-notes" },
      { id: "c-2", key: "c-2", label: "Kê đơn FIDES", icon: "medication", badge: 1 },
    ],
  },
  {
    id: "grp-admin",
    title: "Quản trị",
    items: [
      { id: "a-1", key: "a-1", label: "Giám sát hệ thống", icon: "scan" },
    ],
  },
];

const MOCK_SOURCES: SourceInspectionItem[] = [
  {
    id: "src-1",
    title: "Dược thư Quốc gia Việt Nam 2024 - Chuyên luận Paracetamol",
    source: "Bộ Y tế Việt Nam",
    year: "2024",
    authors: "Hội đồng Dược thư Quốc gia",
    trustTier: "T1_OFFICIAL",
    trustTierLabel: "T1 Dược thư BYT",
    pmid: "VN-MOH-2024-PARA",
    url: "https://kcb.vn/duoc-thu",
    excerpt: "Liều tối đa 4g/ngày ở người lớn có chức năng gan bình thường.",
  },
  {
    id: "src-2",
    title: "Clinical safety of combined analgesic regimens",
    source: "The Lancet",
    year: "2025",
    authors: "Nguyen et al.",
    trustTier: "T2_PEER_REVIEWED",
    trustTierLabel: "T2 Peer-Reviewed",
    pmid: "38912345",
    url: "https://pubmed.ncbi.nlm.nih.gov/38912345",
    excerpt: "Synergistic effects observed without increased hepatotoxicity.",
  },
];

const MOCK_CLAIMS: EvidenceClaimBreakdown[] = [
  {
    id: "claim-1",
    claim: "Không có tương tác thuốc bất lợi (DDI) giữa Paracetamol và Vitamin C",
    status: "VERIFIED",
    statusLabel: "Đã xác minh FIDES",
    fidesTier: "HIGH",
    confidence: 0.98,
    rationale: "Đối chiếu Dược thư Quốc gia Việt Nam mục 4.2 và cơ sở dữ liệu FIDES.",
    citations: ["VN-MOH-2024-PARA", "PMC123456"],
  },
  {
    id: "claim-2",
    claim: "Cảnh báo quá liều khi dùng đồng thời hai chế phẩm chứa Paracetamol",
    status: "CRITICAL_BLOCKED",
    statusLabel: "Chặn an toàn",
    fidesTier: "CRITICAL",
    confidence: 0.99,
    rationale: "Phát hiện trùng lặp hoạt chất gây nguy cơ ngộ độc gan.",
    citations: ["FIDES-RULE-009"],
  },
];

const MOCK_PATIENT: PatientDetailsData = {
  id: "pat-1001",
  name: "Trần Văn An",
  mrn: "MRN-882910",
  age: 45,
  gender: "Nam",
  dob: "15/08/1981",
  bloodType: "O+",
  insuranceNumber: "DN4791234567890",
  vitals: [
    { label: "Huyết áp", value: "120/80", unit: "mmHg", status: "normal" },
    { label: "Nhịp tim", value: "75", unit: "bpm", status: "normal" },
    { label: "SpO2", value: "98", unit: "%", status: "normal" },
    { label: "Nhiệt độ", value: "37.2", unit: "°C", status: "normal" },
  ],
  allergies: [
    { allergen: "Penicillin", severity: "Nặng", reaction: "Sốc phản vệ" },
    { allergen: "Aspirin", severity: "Vừa", reaction: "Phát ban da" },
  ],
  activeMedications: [
    { name: "Amlodipine", dosage: "5mg", frequency: "1 viên/ngày (sáng)" },
    { name: "Metformin", dosage: "500mg", frequency: "2 viên/ngày (sau ăn)" },
  ],
};

const MOCK_TELEMETRY: TelemetryInspectionData = {
  requestId: "req-fides-2026-9921",
  model: "deepseek-r1-distill-qwen-32b",
  timestamp: "2026-08-24 14:30:00",
  totalLatencyMs: 420,
  latencyBreakdown: {
    guardrailMs: 35,
    retrievalMs: 120,
    synthesisMs: 215,
    fidesVerificationMs: 50,
  },
  tokenUsage: {
    promptTokens: 512,
    completionTokens: 256,
    totalTokens: 768,
  },
  ragChunksRetrieved: 12,
  ragChunksUsed: 4,
  guardrailPassed: true,
  zeroPiiVerified: true,
};

/* ========================================================================= */
/* 1. ContextRail Unit Tests (Spec v8 Section 5.7)                            */
/* ========================================================================= */

describe("ContextRail Component (Spec v8 Section 5.7)", () => {
  it("renders desktop navigation rail landmark with title, subtitle, items, and badges", () => {
    render(
      <ContextRail
        title="Phân hệ Khám bệnh"
        subtitle="Khoa Nội tổng quát"
        items={MOCK_RAIL_ITEMS}
        activeKey="chat"
      />,
    );

    const nav = screen.getByRole("navigation", { name: "Thanh điều hướng cục bộ" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByText("Phân hệ Khám bệnh")).toBeInTheDocument();
    expect(screen.getByText("Khoa Nội tổng quát")).toBeInTheDocument();

    expect(screen.getByText("Hội thoại lâm sàng")).toBeInTheDocument();
    expect(screen.getByText("Phiên khám trực tuyến")).toBeInTheDocument();
    expect(screen.getByText("Hồ sơ bệnh án")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Mới")).toBeInTheDocument();
  });

  it("supports grouped items and category headers", () => {
    render(
      <ContextRail
        groups={MOCK_RAIL_GROUPS}
        activeKey="c-1"
      />,
    );

    expect(screen.getByText("Lâm sàng")).toBeInTheDocument();
    expect(screen.getByText("Quản trị")).toBeInTheDocument();
    expect(screen.getByText("Khám tổng quát")).toBeInTheDocument();
    expect(screen.getByText("Kê đơn FIDES")).toBeInTheDocument();
    expect(screen.getByText("Giám sát hệ thống")).toBeInTheDocument();
  });

  it("supports collapsible desktop toggle and callbacks", () => {
    const handleToggle = vi.fn();
    const handleCollapseChange = vi.fn();

    const { rerender } = render(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        collapsed={false}
        onToggleCollapse={handleToggle}
        onCollapseChange={handleCollapseChange}
      />,
    );

    const collapseBtn = screen.getByRole("button", { name: "Thu gọn thanh điều hướng" });
    expect(collapseBtn).toBeInTheDocument();
    fireEvent.click(collapseBtn);

    expect(handleToggle).toHaveBeenCalledTimes(1);
    expect(handleCollapseChange).toHaveBeenCalledWith(true);

    // Rerender collapsed state
    rerender(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        collapsed={true}
        onToggleCollapse={handleToggle}
        onCollapseChange={handleCollapseChange}
      />,
    );

    const expandBtn = screen.getByRole("button", { name: "Mở rộng thanh điều hướng" });
    expect(expandBtn).toBeInTheDocument();
  });

  it("handles item selection and ignores disabled items", () => {
    const handleSelect = vi.fn();
    const handleChange = vi.fn();

    render(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        activeKey="chat"
        onSelect={handleSelect}
        onChange={handleChange}
      />,
    );

    const recordsBtn = screen.getByRole("button", { name: "Hồ sơ bệnh án" });
    fireEvent.click(recordsBtn);

    expect(handleSelect).toHaveBeenCalledWith("records", expect.objectContaining({ key: "records" }));
    expect(handleChange).toHaveBeenCalledWith("records", expect.objectContaining({ key: "records" }));

    const disabledBtn = screen.getByRole("button", { name: "Tính năng khóa" });
    expect(disabledBtn).toBeDisabled();
    fireEvent.click(disabledBtn);

    expect(handleSelect).toHaveBeenCalledTimes(1);
  });

  it("supports roving tabindex and keyboard navigation (ArrowDown, ArrowUp, Home, End)", () => {
    const handleSelect = vi.fn();

    render(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        activeKey="chat"
        onSelect={handleSelect}
      />,
    );

    const chatBtn = screen.getByRole("button", { name: "Hội thoại lâm sàng" });
    const recordsBtn = screen.getByRole("button", { name: "Hồ sơ bệnh án" });
    const settingsBtn = screen.getByRole("button", { name: "Cấu hình phân hệ" });

    // Active item has tabIndex=0, other items have tabIndex=-1
    expect(chatBtn).toHaveAttribute("tabIndex", "0");
    expect(recordsBtn).toHaveAttribute("tabIndex", "-1");
    expect(settingsBtn).toHaveAttribute("tabIndex", "-1");

    chatBtn.focus();

    // ArrowDown should skip disabled item and navigate to 'records'
    fireEvent.keyDown(chatBtn, { key: "ArrowDown" });
    expect(handleSelect).toHaveBeenCalledWith("records", expect.objectContaining({ key: "records" }));

    // ArrowDown again should skip 'disabled' and land on 'settings'
    fireEvent.keyDown(recordsBtn, { key: "ArrowDown" });
    expect(handleSelect).toHaveBeenCalledWith("settings", expect.objectContaining({ key: "settings" }));

    // Home goes to first enabled item ('chat')
    fireEvent.keyDown(settingsBtn, { key: "Home" });
    expect(handleSelect).toHaveBeenCalledWith("chat", expect.objectContaining({ key: "chat" }));

    // End goes to last enabled item ('settings')
    fireEvent.keyDown(chatBtn, { key: "End" });
    expect(handleSelect).toHaveBeenCalledWith("settings", expect.objectContaining({ key: "settings" }));

    // ArrowUp from settings should go to 'records' (skipping disabled)
    fireEvent.keyDown(settingsBtn, { key: "ArrowUp" });
    expect(handleSelect).toHaveBeenCalledWith("records", expect.objectContaining({ key: "records" }));
  });

  it("renders mobile drawer sheet overlay with role='dialog', aria-modal='true', and focus trap", () => {
    const handleClose = vi.fn();

    render(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        isMobile={true}
        mobileOpen={true}
        onMobileClose={handleClose}
        title="Thanh điều hướng di động"
      />,
    );

    const dialog = screen.getByRole("dialog", { name: "Thanh điều hướng cục bộ" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");

    // Close button
    const closeBtn = screen.getByRole("button", { name: "Đóng thanh điều hướng" });
    expect(closeBtn).toBeInTheDocument();
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("closes mobile drawer on Escape key press", () => {
    const handleClose = vi.fn();

    render(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        open={true}
        isMobile={true}
        onClose={handleClose}
      />,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("supports link items with href and aria-current='page'", () => {
    const handleSelect = vi.fn();
    const LINK_ITEMS: ContextRailItem[] = [
      { key: "chat", label: "Hội thoại", href: "/chat" },
      { key: "council", label: "Hội chẩn", href: "/council" },
    ];

    render(
      <ContextRail
        items={LINK_ITEMS}
        activeKey="chat"
        onSelect={handleSelect}
      />,
    );

    const chatLink = screen.getByRole("link", { name: "Hội thoại" });
    expect(chatLink).toHaveAttribute("href", "/chat");
    expect(chatLink).toHaveAttribute("aria-current", "page");
    expect(chatLink).toHaveAttribute("tabIndex", "0");

    const councilLink = screen.getByRole("link", { name: "Hội chẩn" });
    expect(councilLink).toHaveAttribute("href", "/council");
    expect(councilLink).not.toHaveAttribute("aria-current");
    expect(councilLink).toHaveAttribute("tabIndex", "-1");

    fireEvent.click(councilLink);
    expect(handleSelect).toHaveBeenCalledWith("council", expect.objectContaining({ key: "council" }));
  });

  it("supports Enter and Space key to activate non-link items", () => {
    const handleSelect = vi.fn();

    render(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        activeKey="chat"
        onSelect={handleSelect}
      />,
    );

    const recordsBtn = screen.getByRole("button", { name: "Hồ sơ bệnh án" });
    fireEvent.keyDown(recordsBtn, { key: "Enter" });
    expect(handleSelect).toHaveBeenCalledWith("records", expect.objectContaining({ key: "records" }));

    fireEvent.keyDown(recordsBtn, { key: " " });
    expect(handleSelect).toHaveBeenCalledWith("records", expect.objectContaining({ key: "records" }));
  });

  it("supports custom width presets and number widths (240px, 280px, 270)", () => {
    const { container, rerender } = render(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        width="280px"
      />,
    );

    const nav = container.querySelector("nav");
    expect(nav).toHaveClass("w-[280px]");

    rerender(
      <ContextRail
        items={MOCK_RAIL_ITEMS}
        width={270}
      />,
    );
    expect(nav?.style.width).toBe("270px");
  });
});

/* ========================================================================= */
/* 2. InspectorDrawer Unit Tests (Spec v8 Section 5.8)                        */
/* ========================================================================= */

describe("InspectorDrawer Component (Spec v8 Section 5.8)", () => {
  it("renders slide-over sheet (300-380px) with WAI-ARIA role='dialog', title, badges and actions", () => {
    const handleClose = vi.fn();

    render(
      <InspectorDrawer
        open={true}
        onClose={handleClose}
        title="Kiểm tra chi tiết ca bệnh"
        subtitle="Mã ca: #CA-2026-881"
        badge={<span data-testid="badge-fides">FIDES T1</span>}
        actions={<button type="button">Chia sẻ</button>}
        footer={<button type="button">Xác nhận đánh giá</button>}
      >
        <div>Nội dung kiểm tra chi tiết</div>
      </InspectorDrawer>,
    );

    const dialog = screen.getByRole("dialog", { name: "Kiểm tra chi tiết ca bệnh" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");

    expect(screen.getByText("Mã ca: #CA-2026-881")).toBeInTheDocument();
    expect(screen.getByTestId("badge-fides")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Chia sẻ" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xác nhận đánh giá" })).toBeInTheDocument();
    expect(screen.getByText("Nội dung kiểm tra chi tiết")).toBeInTheDocument();
  });

  it("closes on close button click and Escape key dismissal", () => {
    const handleClose = vi.fn();

    render(
      <InspectorDrawer
        open={true}
        onClose={handleClose}
        title="Bảng kiểm tra chứng cứ"
        closeLabel="Đóng thanh kiểm tra"
      >
        <p>Chi tiết</p>
      </InspectorDrawer>,
    );

    // Escape key
    fireEvent.keyDown(document, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);

    // Close button
    const closeBtn = screen.getByRole("button", { name: "Đóng thanh kiểm tra" });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(2);
  });

  it("ignores Escape when dismissible={false}", () => {
    const handleClose = vi.fn();

    render(
      <InspectorDrawer
        open={true}
        onClose={handleClose}
        dismissible={false}
        title="Khóa kiểm tra an toàn"
      >
        <p>Bắt buộc hoàn thành</p>
      </InspectorDrawer>,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(handleClose).not.toHaveBeenCalled();
  });

  it("traps focus inside the slide-over drawer on Tab and Shift+Tab", () => {
    render(
      <InspectorDrawer
        open={true}
        onClose={vi.fn()}
        title="Bẫy tiêu điểm"
      >
        <button type="button">Nút A</button>
        <button type="button">Nút B</button>
      </InspectorDrawer>,
    );

    const closeBtn = screen.getByRole("button", { name: "Đóng bộ kiểm tra" });
    const btnA = screen.getByRole("button", { name: "Nút A" });
    const btnB = screen.getByRole("button", { name: "Nút B" });

    // Focus close button (first element), Shift+Tab wraps to last element (btnB)
    closeBtn.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(btnB);

    // Focus last element (btnB), Tab wraps to first element (closeBtn)
    btnB.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: false });
    expect(document.activeElement).toBe(closeBtn);
  });

  it("renders inline mode panel with role='region' landmark", () => {
    render(
      <InspectorDrawer
        mode="inline"
        title="Bảng điều khiển trích dẫn"
        subtitle="Hiển thị song song"
      >
        <div>Nội dung trích dẫn tài liệu</div>
      </InspectorDrawer>,
    );

    const region = screen.getByRole("region", { name: "Bảng điều khiển trích dẫn" });
    expect(region).toBeInTheDocument();
    expect(screen.getByText("Nội dung trích dẫn tài liệu")).toBeInTheDocument();
  });

  it("supports collapsible InspectorDrawerSection with keyboard toggle", () => {
    render(
      <InspectorDrawerSection
        title="Dược động học & Tương tác"
        collapsible={true}
        defaultExpanded={true}
      >
        <div>Thời gian bán thải T1/2: 2-3 giờ</div>
      </InspectorDrawerSection>,
    );

    expect(screen.getByText("Thời gian bán thải T1/2: 2-3 giờ")).toBeInTheDocument();

    const toggleHeader = screen.getByRole("button", { name: /Dược động học & Tương tác/i });
    fireEvent.click(toggleHeader);
    expect(screen.queryByText("Thời gian bán thải T1/2: 2-3 giờ")).not.toBeInTheDocument();

    // Toggle back with Enter key
    fireEvent.keyDown(toggleHeader, { key: "Enter" });
    expect(screen.getByText("Thời gian bán thải T1/2: 2-3 giờ")).toBeInTheDocument();
  });

  it("supports InspectorDrawerField with copy functionality", async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    render(
      <InspectorDrawerField
        label="Mã định danh DOI"
        value="10.1016/j.clin.2026.01.002"
        copyable={true}
        hint="Nhấp để sao chép mã DOI"
      />,
    );

    expect(screen.getByText("Mã định danh DOI")).toBeInTheDocument();
    expect(screen.getByText("10.1016/j.clin.2026.01.002")).toBeInTheDocument();
    expect(screen.getByText("Nhấp để sao chép mã DOI")).toBeInTheDocument();

    const copyBtn = screen.getByRole("button", { name: "Sao chép giá trị" });
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(writeTextMock).toHaveBeenCalledWith("10.1016/j.clin.2026.01.002");
    expect(screen.getByRole("button", { name: "Đã sao chép" })).toBeInTheDocument();
  });

  it("supports alertdialog role and custom width presets", () => {
    render(
      <InspectorDrawer
        open={true}
        onClose={vi.fn()}
        role="alertdialog"
        width="380px"
        title="Cảnh báo can thiệp an toàn"
        description="FIDES phát hiện chống chỉ định tuyệt đối"
      >
        <p>Chi tiết cảnh báo</p>
      </InspectorDrawer>,
    );

    const alertdialog = screen.getByRole("alertdialog", { name: "Cảnh báo can thiệp an toàn" });
    expect(alertdialog).toBeInTheDocument();
    expect(alertdialog).toHaveClass("w-[380px]");
    expect(screen.getByText("FIDES phát hiện chống chỉ định tuyệt đối")).toBeInTheDocument();
  });
});

/* ========================================================================= */
/* 3. Specialized Inspector Views Unit Tests                                 */
/* ========================================================================= */

describe("Specialized Inspector Views (Sources, Evidence, Patient, Telemetry)", () => {
  it("renders SourceInspectorView with citations, trust tier badges, PMID, and external links", () => {
    const handleSelectSource = vi.fn();

    render(
      <SourceInspectorView
        sources={MOCK_SOURCES}
        onSelectSource={handleSelectSource}
      />,
    );

    expect(screen.getByText("Nguồn & Bằng chứng tham chiếu")).toBeInTheDocument();
    expect(screen.getByText("Dược thư Quốc gia Việt Nam 2024 - Chuyên luận Paracetamol")).toBeInTheDocument();
    expect(screen.getByText("T1 Dược thư BYT")).toBeInTheDocument();
    expect(screen.getByText("Clinical safety of combined analgesic regimens")).toBeInTheDocument();
    expect(screen.getByText("T2 Peer-Reviewed")).toBeInTheDocument();

    const firstSourceCard = screen.getByText("Dược thư Quốc gia Việt Nam 2024 - Chuyên luận Paracetamol");
    fireEvent.click(firstSourceCard);
    expect(handleSelectSource).toHaveBeenCalledWith(MOCK_SOURCES[0]);
  });

  it("renders SourceInspectorView empty state when no sources provided", () => {
    render(
      <SourceInspectorView
        sources={[]}
        emptyMessage="Không có nguồn trích dẫn nào cho câu hỏi này."
      />,
    );

    expect(screen.getByText("Không có nguồn trích dẫn nào cho câu hỏi này.")).toBeInTheDocument();
  });

  it("renders EvidenceBreakdownView with verification status, confidence score, and rationale", () => {
    render(
      <EvidenceBreakdownView
        claims={MOCK_CLAIMS}
        summary="Tổng hợp 2 khẳng định lâm sàng"
      />,
    );

    expect(screen.getByText("Chi tiết kiểm chứng FIDES & Bằng chứng")).toBeInTheDocument();
    expect(screen.getByText("FIDES Verified")).toBeInTheDocument();
    expect(screen.getByText("Tổng hợp 2 khẳng định lâm sàng")).toBeInTheDocument();

    expect(screen.getByText("Không có tương tác thuốc bất lợi (DDI) giữa Paracetamol và Vitamin C")).toBeInTheDocument();
    expect(screen.getByText("Đã xác minh FIDES")).toBeInTheDocument();
    expect(screen.getByText("98%")).toBeInTheDocument();

    expect(screen.getByText("Cảnh báo quá liều khi dùng đồng thời hai chế phẩm chứa Paracetamol")).toBeInTheDocument();
    expect(screen.getByText("Chặn an toàn")).toBeInTheDocument();
  });

  it("renders PatientDetailsView with demographics, vital signs, and allergy badges", () => {
    render(
      <PatientDetailsView patient={MOCK_PATIENT} />,
    );

    const nameElements = screen.getAllByText("Trần Văn An");
    expect(nameElements.length).toBeGreaterThanOrEqual(1);
    expect(nameElements[0]).toBeInTheDocument();
    expect(screen.getByText(/MRN: MRN-882910/i)).toBeInTheDocument();
    expect(screen.getByText("DN4791234567890")).toBeInTheDocument();

    // Vitals
    expect(screen.getByText("Huyết áp")).toBeInTheDocument();
    expect(screen.getByText("120/80")).toBeInTheDocument();

    // Allergies
    expect(screen.getByText("Penicillin")).toBeInTheDocument();
    expect(screen.getByText("Sốc phản vệ")).toBeInTheDocument();
  });

  it("renders TelemetryInspectorView with Zero-PII guarantee, latency breakdown, and token usage", () => {
    render(
      <TelemetryInspectorView telemetry={MOCK_TELEMETRY} />,
    );

    expect(screen.getByText(/Bảo mật Zero-PII/i)).toBeInTheDocument();
    expect(screen.getByText("req-fides-2026-9921")).toBeInTheDocument();
    expect(screen.getByText("deepseek-r1-distill-qwen-32b")).toBeInTheDocument();
    expect(screen.getByText("420 ms")).toBeInTheDocument();

    // Latency breakdown
    expect(screen.getByText("35 ms")).toBeInTheDocument();
    expect(screen.getByText("120 ms")).toBeInTheDocument();
    expect(screen.getByText("215 ms")).toBeInTheDocument();
    expect(screen.getByText("50 ms")).toBeInTheDocument();

    // Tokens
    expect(screen.getByText("512")).toBeInTheDocument();
    expect(screen.getByText("256")).toBeInTheDocument();
    expect(screen.getByText("768")).toBeInTheDocument();
  });
});
