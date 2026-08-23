import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  FloatingComposer,
  StructuredAnswer,
  ConversationHistorySidebar,
  ChatWelcomeHero,
  ChatTurnBubble,
} from "@/components/chat";
import type { WorkspaceConversationItem } from "@/lib/workspace";
import type { ConversationItem, ResearchResult, Tier2Result } from "@/components/research/lib/research-page-types";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getTotalSize: () => count * 52,
    getVirtualItems: () =>
      Array.from({ length: count }, (_, index) => ({
        index,
        key: index,
        start: index * 52,
        size: 52,
      })),
    measureElement: () => undefined,
  }),
}));

describe("Modernized Chat Components", () => {
  describe("FloatingComposer with Medical Prompt Suggestions", () => {
    it("renders medical prompt suggestion chips and populates the prompt when clicked", () => {
      const onChangeQuery = vi.fn();
      render(
        <FloatingComposer
          query=""
          onChangeQuery={onChangeQuery}
          onSubmit={vi.fn()}
          isRunning={false}
          onCancel={vi.fn()}
          mode="fast"
          onChangeMode={vi.fn()}
          retrievalStackMode="auto"
          onChangeRetrievalStackMode={vi.fn()}
          personalMode={false}
          onTogglePersonalMode={vi.fn()}
          liveStatusNote=""
          uiLanguage="vi"
        />,
      );

      // Verify prompt suggestion chips exist in Vietnamese
      const drugInteractionBtn = screen.getByRole("button", { name: /Tương tác thuốc/i });
      const labResultBtn = screen.getByRole("button", { name: /Giải thích xét nghiệm/i });
      const protocolBtn = screen.getByRole("button", { name: /Phác đồ điều trị/i });

      expect(drugInteractionBtn).toBeInTheDocument();
      expect(labResultBtn).toBeInTheDocument();
      expect(protocolBtn).toBeInTheDocument();

      // Click on "Tương tác thuốc"
      fireEvent.click(drugInteractionBtn);
      expect(onChangeQuery).toHaveBeenCalledWith(
        expect.stringContaining("Rà soát tương tác thuốc"),
      );

      // Click on "Phác đồ điều trị"
      fireEvent.click(protocolBtn);
      expect(onChangeQuery).toHaveBeenCalledWith(
        expect.stringContaining("phác đồ điều trị"),
      );
    });

    it("renders English medical prompt suggestion chips when uiLanguage is en", () => {
      const onChangeQuery = vi.fn();
      render(
        <FloatingComposer
          query=""
          onChangeQuery={onChangeQuery}
          onSubmit={vi.fn()}
          isRunning={false}
          onCancel={vi.fn()}
          mode="fast"
          onChangeMode={vi.fn()}
          retrievalStackMode="auto"
          onChangeRetrievalStackMode={vi.fn()}
          personalMode={false}
          onTogglePersonalMode={vi.fn()}
          liveStatusNote=""
          uiLanguage="en"
        />,
      );

      expect(screen.getByRole("button", { name: /Drug interactions/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Explain lab results/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Treatment protocol/i })).toBeInTheDocument();
    });
  });

  describe("ConversationHistorySidebar with Search and Category Tags", () => {
    const mockConversations: WorkspaceConversationItem[] = [
      {
        conversation_id: 1,
        title: "Tương tác thuốc Warfarin và Amiodarone",
        preview: "Tương tác thuốc Warfarin",
        query_id: null,
        message_count: 2,
        created_at: new Date().toISOString(),
        last_message_at: new Date().toISOString(),
        folder_id: null,
        channel_id: null,
        is_favorite: false,
      },
      {
        conversation_id: 2,
        title: "Kết quả xét nghiệm men gan AST ALT cao",
        preview: "Kết quả xét nghiệm men gan",
        query_id: null,
        message_count: 4,
        created_at: new Date().toISOString(),
        last_message_at: new Date().toISOString(),
        folder_id: null,
        channel_id: null,
        is_favorite: false,
      },
      {
        conversation_id: 3,
        title: "Phác đồ điều trị tăng huyết áp theo AHA",
        preview: "Phác đồ điều trị tăng huyết áp",
        query_id: null,
        message_count: 1,
        created_at: new Date().toISOString(),
        last_message_at: new Date().toISOString(),
        folder_id: null,
        channel_id: null,
        is_favorite: true,
      },
    ];

    it("renders category tags (Tất cả, Thuốc, Xét nghiệm, Phác đồ, Đã lưu)", () => {
      render(
        <ConversationHistorySidebar
          conversations={mockConversations}
          activeId={1}
          isLoading={false}
          searchText=""
          onSearchChange={vi.fn()}
          onSelect={vi.fn()}
          onNewChat={vi.fn()}
          uiLanguage="vi"
        />,
      );

      expect(screen.getByRole("button", { name: /^Tất cả$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^Thuốc$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^Xét nghiệm$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^Phác đồ$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^Đã lưu$/i })).toBeInTheDocument();
    });

    it("filters conversation list by category tag", () => {
      render(
        <ConversationHistorySidebar
          conversations={mockConversations}
          activeId={null}
          isLoading={false}
          searchText=""
          onSearchChange={vi.fn()}
          onSelect={vi.fn()}
          onNewChat={vi.fn()}
          uiLanguage="vi"
        />,
      );

      // Initially all 3 conversations are present
      expect(screen.getByText("Tương tác thuốc Warfarin và Amiodarone")).toBeInTheDocument();
      expect(screen.getByText("Kết quả xét nghiệm men gan AST ALT cao")).toBeInTheDocument();
      expect(screen.getByText("Phác đồ điều trị tăng huyết áp theo AHA")).toBeInTheDocument();

      // Click "Thuốc" filter
      fireEvent.click(screen.getByRole("button", { name: /^Thuốc$/i }));
      expect(screen.getByText("Tương tác thuốc Warfarin và Amiodarone")).toBeInTheDocument();
      expect(screen.queryByText("Kết quả xét nghiệm men gan AST ALT cao")).not.toBeInTheDocument();

      // Click "Xét nghiệm" filter
      fireEvent.click(screen.getByRole("button", { name: /^Xét nghiệm$/i }));
      expect(screen.getByText("Kết quả xét nghiệm men gan AST ALT cao")).toBeInTheDocument();
      expect(screen.queryByText("Tương tác thuốc Warfarin và Amiodarone")).not.toBeInTheDocument();

      // Click "Đã lưu" filter (conversation #3 is favorite)
      fireEvent.click(screen.getByRole("button", { name: /^Đã lưu$/i }));
      expect(screen.getByText("Phác đồ điều trị tăng huyết áp theo AHA")).toBeInTheDocument();
      expect(screen.queryByText("Tương tác thuốc Warfarin và Amiodarone")).not.toBeInTheDocument();
    });
  });

  describe("StructuredAnswer: Answer-First (Warning -> Answer -> Next Action -> Citations -> Evidence)", () => {
    it("renders answer-first structure with warning, answer markdown, and citations", () => {
      const mockResult: Tier2Result = {
        tier: "tier2",
        answer: "Amiodarone ức chế mạnh **CYP2C9**, làm tăng nồng độ Warfarin trong máu.",
        citations: [
          {
            title: "Management of Amiodarone-Warfarin Interaction",
            url: "https://pubmed.ncbi.nlm.nih.gov/12345",
            source: "PubMed",
          },
          {
            title: "Drug Interaction: Amiodarone & Anticoagulants",
            url: "https://rxnorm.example/item",
            source: "RxNorm",
          },
        ] as unknown as Tier2Result["citations"],
        steps: [],
        flowStages: [],
        flowEvents: [],
        telemetry: {
          keywords: [],
          scores: [],
          docs: [],
          sourceReasoning: [],
          sourceAttempts: [],
          verificationMatrix: [],
          stageSpans: [],
          errors: [],
          traceMetadata: {},
        } as unknown as Tier2Result["telemetry"],
        visualAssets: [],
        chartSpecs: [],
        reasoningDigest: { items: [] } as unknown as Tier2Result["reasoningDigest"],
        tracedClaims: [],
        citationRegistry: [],
        debug: {
          stageCount: 0,
          flowEventCount: 0,
          telemetryKeywordCount: 0,
          telemetryDocCount: 0,
          telemetrySourceAttemptCount: 0,
          telemetryErrorCount: 0,
          crawlDomainCount: 0,
        },
      };

      render(<StructuredAnswer result={mockResult} uiLanguage="vi" />);

      // Answer content is rendered
      expect(screen.getByText("CYP2C9")).toBeInTheDocument();
      expect(screen.getByText(/Amiodarone ức chế mạnh/)).toBeInTheDocument();

      // References section is rendered
      expect(screen.getByText(/Nguồn tham khảo \(2\)/i)).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /Management of Amiodarone-Warfarin Interaction/i }),
      ).toHaveAttribute("href", "https://pubmed.ncbi.nlm.nih.gov/12345");
    });
  });

  describe("ChatTurnBubble", () => {
    it("renders user bubble and assistant turn with refined typography", () => {
      const mockTurn: ConversationItem = {
        id: "turn-1",
        query: "Bệnh nhân dùng Warfarin và Amiodarone có an toàn không?",
        result: {
          tier: "tier1",
          answer: "Cần theo dõi INR sát sao do tương tác làm tăng tác dụng chống đông.",
          debug: null,
        },
        createdAt: Date.now(),
      };

      render(<ChatTurnBubble turn={mockTurn} uiLanguage="vi" />);

      expect(
        screen.getByText("Bệnh nhân dùng Warfarin và Amiodarone có an toàn không?"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Cần theo dõi INR sát sao do tương tác làm tăng tác dụng chống đông."),
      ).toBeInTheDocument();
      expect(screen.getByText("CLARA")).toBeInTheDocument();
    });
  });
});
