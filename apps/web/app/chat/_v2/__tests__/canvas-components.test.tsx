import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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
