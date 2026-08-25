import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import AnswerRenderer from "@/app/chat/_v2/components/AnswerRenderer";
import FlowTimeline from "@/app/chat/_v2/components/FlowTimeline";
import TurnView from "@/app/chat/_v2/components/TurnView";
import TelemetryPanel from "@/app/chat/_v2/components/TelemetryPanel";
import type {
  ConversationItem,
  ResearchResult,
  Tier2Result,
} from "@/components/research/lib/research-page-types";
import type { ResearchTier2Result } from "@/lib/research";

/**
 * Feature: clara-chat-redesign, Requirement 2.2 (typographic answer), 2.3/3.2
 * (inline flow timeline + degraded labeling, Property P5), 6.6 (admin-only
 * telemetry, Property P7), plus the per-turn error boundary (design "Error
 * Handling").
 */

function emptyTelemetry(): ResearchTier2Result["telemetry"] {
  return {
    keywords: [],
    scores: [],
    docs: [],
    sourceReasoning: [],
    sourceAttempts: [],
    verificationMatrix: [],
    stageSpans: [],
    errors: [],
    traceMetadata: {},
  } as unknown as ResearchTier2Result["telemetry"];
}

function makeTier2(overrides: Partial<ResearchTier2Result> = {}): Tier2Result {
  return {
    tier: "tier2",
    answer: "",
    citations: [],
    steps: [],
    flowStages: [],
    flowEvents: [],
    telemetry: emptyTelemetry(),
    visualAssets: [],
    chartSpecs: [],
    reasoningDigest: {
      items: [],
    } as unknown as ResearchTier2Result["reasoningDigest"],
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
    } as unknown as ResearchTier2Result["debug"],
    ...overrides,
  } as Tier2Result;
}

function makeTier1(answer: string): ResearchResult {
  return { tier: "tier1", answer, debug: null };
}

describe("AnswerRenderer", () => {
  it("renders markdown answer content", () => {
    render(
      <AnswerRenderer
        result={makeTier1("Take **metformin** with food.")}
        uiLanguage="en"
      />,
    );
    expect(screen.getByText("metformin")).toBeInTheDocument();
  });

  it("labels a degraded local-fallback answer (Property P5)", () => {
    const degraded = makeTier2({
      answer: "Fallback answer",
      fallbackUsed: true,
    });
    render(<AnswerRenderer result={degraded} uiLanguage="en" />);
    expect(screen.getByText(/Degraded/i)).toBeInTheDocument();
  });

  it("does not label a normal answer as degraded", () => {
    render(<AnswerRenderer result={makeTier1("All good")} uiLanguage="en" />);
    expect(screen.queryByText(/Degraded/i)).not.toBeInTheDocument();
  });

  it("uses a calm evidence boundary and an existing visit-preparation route when release is blocked", () => {
    render(
      <AnswerRenderer
        result={makeTier2({
          answer: "",
          evidenceRelease: {
            passed: false,
            reasons: ["no_retrieved_evidence"],
          },
        })}
        uiLanguage="en"
      />,
    );
    expect(screen.getByText(/not enough evidence/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /prepare for a visit/i })).toHaveAttribute(
      "href",
      "/visits/new",
    );
  });

  it("renders citations for a tier2 answer", () => {
    const result = makeTier2({
      answer: "Answer",
      citations: [
        {
          title: "PubMed study",
          url: "https://pubmed.example/1",
          source: "PubMed",
        },
      ] as unknown as ResearchTier2Result["citations"],
    });
    render(<AnswerRenderer result={result} uiLanguage="en" />);
    expect(screen.getByText(/References \(1\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /PubMed study/ })).toHaveAttribute(
      "href",
      "https://pubmed.example/1",
    );
  });

  it("surfaces research integrity metrics for deep results", () => {
    render(
      <AnswerRenderer
        result={makeTier2({
          answer: "Evidence synthesis",
          deepPassCount: 2,
          verificationStatus: { verdict: "supported" },
        })}
        uiLanguage="en"
        role="researcher"
      />,
    );
    expect(
      screen.getByRole("region", { name: /research integrity/i }),
    ).toHaveTextContent("supported");
    expect(screen.getByText("Deep passes")).toBeInTheDocument();
  });

  it("does not expose research diagnostics to a general user", () => {
    render(
      <AnswerRenderer
        result={makeTier2({
          answer: "Patient-friendly answer",
          deepPassCount: 3,
          verificationStatus: { verdict: "supported" },
        })}
        uiLanguage="en"
        role="normal"
      />,
    );
    expect(screen.queryByRole("region", { name: /research integrity/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Deep passes")).not.toBeInTheDocument();
  });

  it("removes hidden reasoning and raw confidence lines from answer text", () => {
    render(
      <AnswerRenderer
        result={makeTier1([
          "Useful patient-facing guidance.",
          "chain-of-thought: private scratchpad",
          "internal reasoning: hidden",
          "provider/model id: secret-provider",
          "confidence: 0.93",
        ].join("\n"))}
        uiLanguage="en"
      />,
    );
    expect(screen.getByText("Useful patient-facing guidance.")).toBeInTheDocument();
    expect(screen.queryByText(/private scratchpad|secret-provider|confidence: 0\.93/i)).not.toBeInTheDocument();
  });
});

describe("FlowTimeline", () => {
  it("renders nothing when there are no visible nodes and not running", () => {
    const { container } = render(
      <FlowTimeline result={makeTier2()} uiLanguage="en" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the reasoning flow heading when a stage has progressed", () => {
    const result = makeTier2({
      answer: "Synthesized answer",
      flowStages: [
        { id: "synthesis", status: "completed", detail: "done" },
      ] as unknown as ResearchTier2Result["flowStages"],
    });
    render(<FlowTimeline result={result} uiLanguage="en" />);
    expect(
      screen.getByRole("region", { name: /Reasoning flow/i }),
    ).toBeInTheDocument();
  });

  it("strips internal telemetry labels from stage detail (Req 4.1)", () => {
    const result = makeTier2({
      answer: "Synthesized answer",
      flowStages: [
        {
          id: "hybrid_retrieval",
          status: "completed",
          detail: "RAG mode retrieval done",
        },
      ] as unknown as ResearchTier2Result["flowStages"],
    });
    // Vietnamese UI: the localized stage label ("Truy xuất bằng chứng") carries
    // no blocklisted token, so this isolates the detail-string sanitization.
    render(<FlowTimeline result={result} uiLanguage="vi" />);
    const region = screen.getByRole("region", { name: /Luồng suy luận/i });
    // The raw internal telemetry labels must not reach the End_User view.
    expect(region).not.toHaveTextContent(/RAG mode/i);
    expect(region).not.toHaveTextContent(/retrieval/i);
    // The non-telemetry remainder of the detail survives.
    expect(region).toHaveTextContent(/done/i);
  });
});

describe("TurnView", () => {
  it("renders the user query and the answer", () => {
    const turn: ConversationItem = {
      id: "t1",
      query: "What is metformin?",
      result: makeTier1("It is a diabetes medicine."),
      createdAt: Date.now(),
    };
    render(<TurnView turn={turn} uiLanguage="en" />);
    expect(screen.getByText("What is metformin?")).toBeInTheDocument();
    expect(screen.getByText("It is a diabetes medicine.")).toBeInTheDocument();
  });

  it("places the answer before collapsed explainability details", () => {
    const turn: ConversationItem = {
      id: "t-answer-first",
      query: "What should I know?",
      result: makeTier2({ answer: "The important answer comes first." }),
      createdAt: Date.now(),
    };
    const { container } = render(<TurnView turn={turn} uiLanguage="en" />);
    const answer = screen.getByText("The important answer comes first.");
    const disclosure = screen.getByText("Why did CLARA give this answer?");
    expect(answer.compareDocumentPosition(disclosure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container.querySelector("details")?.hasAttribute("open")).toBe(false);
  });

  it("lets a user escalate an answer into the existing research workflow", () => {
    const onLaunchResearch = vi.fn();
    const turn: ConversationItem = {
      id: "t-research",
      query: "Does metformin reduce cardiovascular risk?",
      result: makeTier1("It depends on the population."),
      createdAt: Date.now(),
    };
    render(
      <TurnView
        turn={turn}
        uiLanguage="en"
        onLaunchResearch={onLaunchResearch}
      />,
    );
    screen
      .getByRole("button", { name: /Investigate with Medical Research/i })
      .click();
    expect(onLaunchResearch).toHaveBeenCalledWith(turn.query);
  });

  it("isolates a render failure to a per-turn error boundary", () => {
    // A tier2 result whose `citations` is null makes the inner renderer throw;
    // the per-turn boundary catches it instead of crashing the log.
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const turn = {
      id: "bad",
      query: "boom",
      result: makeTier2({
        answer: "x",
        citations: null as unknown as ResearchTier2Result["citations"],
      }),
      createdAt: Date.now(),
    } as unknown as ConversationItem;
    render(<TurnView turn={turn} uiLanguage="en" />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      /could not be displayed/i,
    );
    errorSpy.mockRestore();
  });

  it("renders 1-click action buttons: Copy, Save to Notebook, Voice Read-Aloud, and Related Questions", async () => {
    const onSaveNote = vi.fn();
    const onAskFollowUp = vi.fn();
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: writeTextMock },
    });

    const speakMock = vi.fn();
    const cancelMock = vi.fn();
    (window as any).speechSynthesis = {
      speak: speakMock,
      cancel: cancelMock,
    };
    (window as any).SpeechSynthesisUtterance = class {
      text: string;
      lang = "";
      constructor(text: string) {
        this.text = text;
      }
    };

    const turn: ConversationItem = {
      id: "t-actions",
      query: "Uống Metformin khi nào?",
      result: makeTier1("Uống Metformin cùng hoặc ngay sau bữa ăn để giảm tác dụng phụ đường tiêu hóa."),
      createdAt: Date.now(),
    };

    render(
      <TurnView
        turn={turn}
        uiLanguage="vi"
        onSaveNote={onSaveNote}
        onAskFollowUp={onAskFollowUp}
      />,
    );

    // 1. Copy answer button
    const copyBtn = screen.getByRole("button", { name: /Sao chép câu trả lời/i });
    expect(copyBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(copyBtn);
    });
    expect(writeTextMock).toHaveBeenCalledWith("Uống Metformin cùng hoặc ngay sau bữa ăn để giảm tác dụng phụ đường tiêu hóa.");

    // 2. Save to notebook button
    const saveBtn = screen.getByRole("button", { name: /Lưu vào Sổ tay/i });
    expect(saveBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(saveBtn);
    });
    expect(onSaveNote).toHaveBeenCalledWith("Uống Metformin cùng hoặc ngay sau bữa ăn để giảm tác dụng phụ đường tiêu hóa.");

    // 3. Voice read-aloud button
    const voiceBtn = screen.getByRole("button", { name: /Đọc to \(Voice\)/i });
    expect(voiceBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(voiceBtn);
    });
    expect(speakMock).toHaveBeenCalled();

    // 4. Related questions button
    const relatedBtn = screen.getByRole("button", { name: /Hỏi thêm câu liên quan/i });
    expect(relatedBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(relatedBtn);
    });
    expect(screen.getByText(/Gợi ý câu hỏi đào sâu tiếp theo:/i)).toBeInTheDocument();

    const followUpChoice = screen.getByRole("button", { name: /Tác dụng phụ thường gặp nhất/i });
    expect(followUpChoice).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(followUpChoice);
    });
    expect(onAskFollowUp).toHaveBeenCalledWith(expect.stringContaining("Tác dụng phụ"));
  });
});

describe("TelemetryPanel (admin-only detail, Property P7)", () => {
  it("renders detailed telemetry for an admin", () => {
    render(
      <TelemetryPanel
        role="admin"
        result={makeTier2({ answer: "x" })}
        uiLanguage="en"
      />,
    );
    expect(
      screen.getByRole("complementary", { name: /telemetry/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^confidence$/i)).not.toBeInTheDocument();
  });

  it("renders nothing for a non-admin role", () => {
    const { container } = render(
      <TelemetryPanel
        role="normal"
        result={makeTier2({ answer: "x" })}
        uiLanguage="en"
      />,
    );
    expect(container.querySelector("[aria-label]")).toBeNull();
  });
});
