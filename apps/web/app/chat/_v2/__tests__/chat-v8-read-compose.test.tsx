import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatWelcome from "@/app/chat/_v2/components/ChatWelcome";
import AnswerRenderer from "@/app/chat/_v2/components/AnswerRenderer";
import type { ResearchResult, Tier2Result } from "@/components/research/lib/research-page-types";

/**
 * Spec v8 §7.2 & §10 (READ_COMPOSE Workspace Canvas) Unit Tests:
 * 1. Centered reading column (760–900px)
 * 2. Dominant composer with embedded mode selector (Fast / Deep / Research)
 * 3. History is a collapsible 280–320px rail (ContextRail), default closed on <=1440px
 * 4. Welcome state with 3-4 starter chips and no 4 large shortcut tiles
 * 5. 5-part Answer hierarchy: Direct answer -> What matters -> Next action -> Uncertainty -> Sources
 * 6. Sources open InspectorDrawer on wide desktop
 */

const clearTurns = vi.fn();
const loadConversations = vi.fn().mockResolvedValue([]);
const loadNotes = vi.fn().mockResolvedValue(undefined);
const loadShares = vi.fn().mockResolvedValue(undefined);

vi.mock("@/app/chat/_v2/hooks/useConversations", () => ({
  useConversations: () => ({
    conversations: [
      {
        conversation_id: 101,
        title: "Tư vấn tương tác thuốc huyết áp",
        preview: "Metformin và Amlodipine có tương tác không?",
        query_id: null,
        message_count: 3,
        created_at: "2026-08-23T10:00:00.000Z",
        last_message_at: "2026-08-23T10:30:00.000Z",
        folder_id: null,
        channel_id: null,
        is_favorite: false,
      },
    ],
    merged: [
      {
        conversation_id: 101,
        title: "Tư vấn tương tác thuốc huyết áp",
        preview: "Metformin và Amlodipine có tương tác không?",
        query_id: null,
        message_count: 3,
        created_at: "2026-08-23T10:00:00.000Z",
        last_message_at: "2026-08-23T10:30:00.000Z",
        folder_id: null,
        channel_id: null,
        is_favorite: false,
      },
    ],
    localIds: new Set<number>(),
    activeId: null,
    isLoading: false,
    apiUnavailable: false,
    load: loadConversations,
    select: vi.fn(),
    create: vi.fn(),
    rename: vi.fn(),
    remove: vi.fn(),
    setFavorite: vi.fn(),
    setFolder: vi.fn(),
    upsertLocal: vi.fn(),
    removeLocal: vi.fn(),
    patch: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useChatTurns", () => ({
  useChatTurns: () => ({
    turns: [],
    cachedTurns: () => [],
    setActive: vi.fn(),
    load: vi.fn().mockResolvedValue(undefined),
    clear: clearTurns,
    appendTurn: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useChatStream", () => ({
  useChatStream: () => ({
    isRunning: false,
    statusNote: "",
    run: vi.fn(),
    cancel: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useWorkspace", () => ({
  useWorkspace: () => ({
    notes: [],
    shares: [],
    searchResults: null,
    loadNotes,
    loadShares,
    saveNote: vi.fn(),
    removeNote: vi.fn(),
    share: vi.fn(),
    revokeShare: vi.fn(),
    exportConversation: vi.fn(),
    search: vi.fn(),
    clearSearch: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useCommandPalette", () => ({
  useCommandPalette: () => ({
    isOpen: false,
    open: vi.fn(),
    close: vi.fn(),
    query: "",
    setQuery: vi.fn(),
    results: [],
    activeIndex: 0,
    setActiveIndex: vi.fn(),
    runActive: vi.fn(),
  }),
}));

// Lib modules
vi.mock("@/lib/auth-store", () => ({ getRole: () => "doctor" }));
vi.mock("@/lib/analytics/events", () => ({ trackChatMessageSent: vi.fn() }));
vi.mock("@/lib/user-facing-text", () => ({
  sanitizeUpstreamError: (m: string) => m,
  sanitizeAssistantAnswer: (m: string) => m,
  toModeLabel: (m: string) => m,
}));
vi.mock("@/lib/ui-language", () => ({
  getStoredUILanguage: () => "vi",
  onUILanguageChange: () => vi.fn(),
}));

function makeMockTier2Result(overrides: Partial<Tier2Result> = {}): ResearchResult {
  return {
    tier: "tier2",
    answer: "Metformin có thể phối hợp an toàn với Amlodipine theo phác đồ Bộ Y tế 2026.",
    citations: [
      {
        title: "Phác đồ điều trị ĐTĐ tuýp 2 Bộ Y tế 2026",
        url: "https://moh.gov.vn/phac-do-dtd",
        source: "Bộ Y tế Việt Nam",
      },
    ],
    citationRegistry: [
      {
        citationId: "cit-1",
        title: "Phác đồ điều trị ĐTĐ tuýp 2 Bộ Y tế 2026",
        url: "https://moh.gov.vn/phac-do-dtd",
        sourceType: "Hướng dẫn Bộ Y tế",
      },
    ],
    tracedClaims: [
      {
        claim: "Metformin an toàn khi phối hợp Amlodipine",
        confidence: 0.95,
        citationIds: ["cit-1"],
      },
    ],
    verificationStatus: {
      verdict: "ĐÃ KIỂM CHỨNG",
      note: "Xác thực FIDES thành công: Không có chống chỉ định tuyệt đối.",
    },
    policyAction: "allow",
    evidenceRelease: { passed: true, reasons: [] },
    debug: null,
    ...overrides,
  } as unknown as Tier2Result;
}

describe("Spec v8 §7.2 & §10 Chat READ_COMPOSE Rebuild", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
  });

  it("1. renders ChatShell with collapsible ContextRail and embedded Composer mode selector", async () => {
    const mod = await import("@/app/chat/_v2/ChatShell");
    const ChatShell = mod.default;
    render(<ChatShell />);

    await waitFor(() => expect(loadConversations).toHaveBeenCalled());

    // Navigation Rail Landmark exists
    const nav = screen.getByRole("navigation", { name: /Thanh điều hướng cục bộ/i });
    expect(nav).toBeInTheDocument();

    // Mode Selector (Fast / Deep / Research) is embedded inside Composer toolbar
    const modeGroup = screen.getByRole("group", { name: /Chế độ trả lời/i });
    expect(modeGroup).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nhanh/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Phân tích/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nghiên cứu/i })).toBeInTheDocument();

    // Toggle expand rail and verify item is displayed
    const toggleBtn = screen.getByRole("button", { name: /Mở rộng thanh điều hướng/i });
    expect(toggleBtn).toBeInTheDocument();
    fireEvent.click(toggleBtn);

    expect(screen.getByText("Tư vấn tương tác thuốc huyết áp")).toBeInTheDocument();
  });

  it("2. ChatWelcome renders calm clinical prompt and 3-4 compact starter chips (no 4 large shortcut tiles)", () => {
    const onChoosePrompt = vi.fn();
    render(
      <ChatWelcome
        role="doctor"
        uiLanguage="vi"
        onChoosePrompt={onChoosePrompt}
      />,
    );

    // Welcome title & calm subtitle
    expect(screen.getByText("Bạn đang cần làm rõ điều gì?")).toBeInTheDocument();
    expect(screen.getByText(/Nguồn khi có/i)).toBeInTheDocument();

    // 4 compact starter chips
    const chip = screen.getByRole("button", { name: /Tóm tắt ca bệnh/i });
    expect(chip).toBeInTheDocument();
    fireEvent.click(chip);
    expect(onChoosePrompt).toHaveBeenCalled();

    // Ensure no legacy monolithic tiles
    expect(screen.queryByText("4 công cụ lâm sàng cốt lõi")).not.toBeInTheDocument();
  });

  it("3. AnswerRenderer implements strict 5-layer hierarchy: Direct answer -> What matters -> Next action -> Uncertainty -> Sources", () => {
    const mockResult = makeMockTier2Result();
    const handleInspectSource = vi.fn();
    const handleInspectAllSources = vi.fn();

    render(
      <AnswerRenderer
        result={mockResult}
        uiLanguage="vi"
        role="doctor"
        onInspectSource={handleInspectSource}
        onInspectAllSources={handleInspectAllSources}
      />,
    );

    // 1. Direct answer
    expect(screen.getByText(/Metformin có thể phối hợp an toàn với Amlodipine/i)).toBeInTheDocument();

    // 2. What matters (FIDES Verification & Safety Badge)
    expect(screen.getByText(/Kiểm tra Dược lý & An toàn FIDES/i)).toBeInTheDocument();
    expect(screen.getByText("ĐÃ KIỂM CHỨNG")).toBeInTheDocument();
    expect(screen.getByText("ALLOW")).toBeInTheDocument();

    // 3. Next action
    expect(screen.getByRole("link", { name: /Đặt lịch hẹn/i })).toHaveAttribute("href", "/visits/new");

    // 4. Uncertainty & clinical boundaries
    expect(screen.getByText(/Độ chắc chắn & Giới hạn lâm sàng/i)).toBeInTheDocument();

    // 5. Sources & Inspector CTA
    expect(screen.getByText(/Bằng chứng \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText("Phác đồ điều trị ĐTĐ tuýp 2 Bộ Y tế 2026")).toBeInTheDocument();

    // Clicking Inspect opens InspectorDrawer
    const inspectBtn = screen.getByRole("button", { name: /Kiểm tra nguồn \(Inspector\)/i });
    expect(inspectBtn).toBeInTheDocument();
    fireEvent.click(inspectBtn);
    expect(handleInspectAllSources).toHaveBeenCalled();
  });

  it("4. clicking a specific citation row triggers InspectorDrawer on wide desktop", () => {
    const mockResult = makeMockTier2Result();
    const handleInspectSource = vi.fn();

    render(
      <AnswerRenderer
        result={mockResult}
        uiLanguage="vi"
        role="doctor"
        onInspectSource={handleInspectSource}
      />,
    );

    const inspectSpecificBtn = screen.getByRole("button", { name: /Chi tiết/i });
    expect(inspectSpecificBtn).toBeInTheDocument();
    fireEvent.click(inspectSpecificBtn);
    expect(handleInspectSource).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Phác đồ điều trị ĐTĐ tuýp 2 Bộ Y tế 2026",
        url: "https://moh.gov.vn/phac-do-dtd",
      }),
    );
  });
});
