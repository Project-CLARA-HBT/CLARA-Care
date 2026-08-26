import type { ReactNode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const push = vi.fn();
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    getLifeMapToday: vi.fn(),
    getLifeMapDisputes: vi.fn(),
    getProfileContext: vi.fn(),
    getLifeMapV2Capabilities: vi.fn(),
    getLifeMapBaselines: vi.fn(),
    getActiveLifeMapCaptureSession: vi.fn(),
    startLifeMapTextCapture: vi.fn(),
    startLifeMapArtifactCapture: vi.fn(),
    uploadLifeMapCaptureArtifact: vi.fn(),
    getLifeMapCaptureJob: vi.fn(),
    getLifeMapCaptureSession: vi.fn(),
    reviewLifeMapCaptureCandidate: vi.fn(),
    getLifeMapCaptureNormalization: vi.fn(),
    createLifeMapTask: vi.fn(),
    acceptLifeMapTask: vi.fn(),
    getLifeMapReplay: vi.fn(),
    getLifeMapNextQuestion: vi.fn(),
    recordLifeMapQuestionInteraction: vi.fn(),
    startLifeMapGuidedAnswer: vi.fn(),
    correctLifeMapEvent: vi.fn(),
    getLifeMapRevisionComparison: vi.fn(),
    disputeLifeMapEvent: vi.fn(),
    resolveLifeMapEvent: vi.fn(),
    askLifeMap: vi.fn(),
    createLifeMapVisitPreparationDraft: vi.fn(),
    scanLifeMapReviewFindings: vi.fn(),
    actOnLifeMapReviewFinding: vi.fn(),
    getLifeMapSummary: vi.fn(),
    abandonLifeMapCaptureSession: vi.fn(),
    getLifeMapCaptureArtifact: vi.fn(),
    push,
    replace,
    refresh,
    router: { push, replace, refresh },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/profile-context-api", () => ({
  getProfileContext: mocks.getProfileContext,
}));

vi.mock("@/lib/lifemap", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/lifemap")>();
  return {
    ...original,
    getLifeMapToday: mocks.getLifeMapToday,
    getLifeMapDisputes: mocks.getLifeMapDisputes,
    getLifeMapV2Capabilities: mocks.getLifeMapV2Capabilities,
    getLifeMapBaselines: mocks.getLifeMapBaselines,
    getActiveLifeMapCaptureSession: mocks.getActiveLifeMapCaptureSession,
    startLifeMapTextCapture: mocks.startLifeMapTextCapture,
    startLifeMapArtifactCapture: mocks.startLifeMapArtifactCapture,
    uploadLifeMapCaptureArtifact: mocks.uploadLifeMapCaptureArtifact,
    getLifeMapCaptureJob: mocks.getLifeMapCaptureJob,
    getLifeMapCaptureSession: mocks.getLifeMapCaptureSession,
    reviewLifeMapCaptureCandidate: mocks.reviewLifeMapCaptureCandidate,
    getLifeMapCaptureNormalization: mocks.getLifeMapCaptureNormalization,
    createLifeMapTask: mocks.createLifeMapTask,
    acceptLifeMapTask: mocks.acceptLifeMapTask,
    getLifeMapReplay: mocks.getLifeMapReplay,
    getLifeMapNextQuestion: mocks.getLifeMapNextQuestion,
    recordLifeMapQuestionInteraction: mocks.recordLifeMapQuestionInteraction,
    startLifeMapGuidedAnswer: mocks.startLifeMapGuidedAnswer,
    correctLifeMapEvent: mocks.correctLifeMapEvent,
    getLifeMapRevisionComparison: mocks.getLifeMapRevisionComparison,
    disputeLifeMapEvent: mocks.disputeLifeMapEvent,
    resolveLifeMapEvent: mocks.resolveLifeMapEvent,
    askLifeMap: mocks.askLifeMap,
    createLifeMapVisitPreparationDraft: mocks.createLifeMapVisitPreparationDraft,
    scanLifeMapReviewFindings: mocks.scanLifeMapReviewFindings,
    actOnLifeMapReviewFinding: mocks.actOnLifeMapReviewFinding,
    getLifeMapSummary: mocks.getLifeMapSummary,
    abandonLifeMapCaptureSession: mocks.abandonLifeMapCaptureSession,
    getLifeMapCaptureArtifact: mocks.getLifeMapCaptureArtifact,
  };
});

import LifeMapPage from "./page";

describe("LifeMapPage (Spec v5 Section 6.16 - Journey Canvas)", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mocks.getProfileContext.mockResolvedValue({
      active_profile_id: "profile-user-1",
    });

    mocks.getLifeMapV2Capabilities.mockResolvedValue({
      lifemap_capture: true,
      lifemap_next_question_v2: true,
      lifemap_ask_ai: true,
      lifemap_vietnamese_drafts: true,
      lifemap_ai_review_findings: true,
      lifemap_ai_summaries: true,
      lifemap_baselines_v2: true,
    });

    mocks.getLifeMapToday.mockResolvedValue({
      generated_at: "2026-08-10T00:00:00Z",
      tasks: [
        {
          id: "task-1",
          episode_id: "ep-1",
          title: "Đo huyết áp sáng và tối",
          due_at: "2026-08-10T20:00:00Z",
          status: "accepted",
          version: 1,
        },
      ],
      episodes: [
        {
          id: "ep-1",
          title: "Kiểm soát huyết áp",
          goal: "Duy trì < 130/80 mmHg",
          priority: "soon",
          status: "active",
        },
      ],
      pending_confirmation_count: 0,
    });

    mocks.getLifeMapDisputes.mockResolvedValue([]);
    mocks.getLifeMapBaselines.mockResolvedValue([
      {
        id: "base-1",
        signal_key: "Huyết áp tâm thu (Systolic BP)",
        status: "ready",
        personal_median: 126,
        unit: "mmHg",
        sample_days: 14,
        rule_version: "v2.0",
      },
    ]);
    mocks.getActiveLifeMapCaptureSession.mockResolvedValue(null);
  });

  afterEach(cleanup);

  it("renders LifeMap header, episodes list, tasks list, and navigation buttons", async () => {
    await act(async () => {
      render(<LifeMapPage />);
    });

    expect(screen.getByRole("heading", { name: "LifeMap" })).toBeInTheDocument();
    expect(screen.getByText("Bạn đang theo dõi điều gì?")).toBeInTheDocument();
    expect(screen.getAllByText("Kiểm soát huyết áp")[0]).toBeInTheDocument();
    expect(screen.getByText("Việc đã được chấp nhận")).toBeInTheDocument();
    expect(screen.getByText("Đo huyết áp sáng và tối")).toBeInTheDocument();

    // Check link to timeline and new journey
    expect(screen.getByRole("link", { name: /dòng thời gian/i })).toHaveAttribute(
      "href",
      "/lifemap/timeline",
    );
    expect(screen.getAllByRole("link", { name: /Bắt đầu từng bước/ })[0]).toHaveAttribute(
      "href",
      "/lifemap/new",
    );
  });

  it("allows asking questions with AI and displays grounded citations", async () => {
    mocks.askLifeMap.mockResolvedValue({
      intent: "timeline_lookup",
      answer: "Trong 7 ngày qua, huyết áp trung bình của bạn là 126/81 mmHg, duy trì ổn định.",
      claims: [
        {
          claim_id: "claim-1",
          text: "Huyết áp trung bình đạt ngưỡng an toàn 126/81 mmHg.",
          citation_ids: ["ev-1"],
        },
      ],
      evidence: [
        {
          evidence_id: "ev-1",
          attribution: "Máy đo Omron HEM-7120",
          occurred_at: "2026-08-08T08:00:00Z",
          revision_id: "rev-abcdef123456",
        },
      ],
      disputed: [],
      conflicting: [],
      stale: [],
      unknown: [],
      disclosure: { mode: "grounded" },
    });

    await act(async () => {
      render(<LifeMapPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Hỏi LifeMap của tôi")).toBeInTheDocument();
    });

    const askInput = screen.getByLabelText("Bạn muốn tìm điều gì?");
    fireEvent.change(askInput, {
      target: { value: "Huyết áp tuần qua của tôi thế nào?" },
    });

    const submitBtn = screen.getByRole("button", { name: "Tra cứu" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mocks.askLifeMap).toHaveBeenCalledWith("Huyết áp tuần qua của tôi thế nào?", "ep-1");
      expect(
        screen.getByText("Trong 7 ngày qua, huyết áp trung bình của bạn là 126/81 mmHg, duy trì ổn định."),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Huyết áp trung bình đạt ngưỡng an toàn 126/81 mmHg."),
      ).toBeInTheDocument();
    });
  });

  it("creates and reviews visit preparation summary draft", async () => {
    mocks.createLifeMapVisitPreparationDraft.mockResolvedValue({
      title: "Bản tóm tắt chuẩn bị khám Tim mạch",
      status: "ready",
      plain_language_summary: {
        important_now: "Huyết áp ổn định nhưng có 1 lần chóng mặt nhẹ vào buổi chiều ngày 7/8.",
        based_on: [
          {
            text: "Ghi nhận nhật ký triệu chứng ngày 7/8.",
            occurred_at: "2026-08-07T15:30:00Z",
            citation_ids: ["rev-001"],
          },
        ],
        uncertainty: [],
        next_step: "Trao đổi với bác sĩ về thời điểm uống thuốc.",
        urgent_help: "Nếu huyết áp > 180/110 kèm đau thắt ngực, liên hệ cấp cứu 115.",
      },
      questions_to_consider: [
        {
          text: "Có cần bổ sung điện giải khi vận động ngoài trời không?",
          citation_ids: ["rev-001"],
        },
      ],
      source_revision_ids: ["rev-001"],
    });

    await act(async () => {
      render(<LifeMapPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Chuẩn bị buổi khám")).toBeInTheDocument();
    });

    const createDraftBtn = screen.getByRole("button", { name: "Tạo bản nháp" });
    fireEvent.click(createDraftBtn);

    await waitFor(() => {
      expect(mocks.createLifeMapVisitPreparationDraft).toHaveBeenCalled();
      expect(screen.getByText("Bản tóm tắt chuẩn bị khám Tim mạch")).toBeInTheDocument();
      expect(
        screen.getByText("Huyết áp ổn định nhưng có 1 lần chóng mặt nhẹ vào buổi chiều ngày 7/8."),
      ).toBeInTheDocument();
    });
  });

  it("scans AI review findings and resolves a finding", async () => {
    const finding = {
      id: "find-1",
      kind: "missing" as const,
      field_key: "blood_pressure_evening",
      rule_version: "v1.2",
      revision_ids: [],
      status: "pending" as const,
    };

    mocks.scanLifeMapReviewFindings.mockResolvedValue([finding]);
    mocks.actOnLifeMapReviewFinding.mockResolvedValue({
      ...finding,
      status: "resolved" as const,
    });

    await act(async () => {
      render(<LifeMapPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Thông tin cần bạn kiểm tra")).toBeInTheDocument();
    });

    const scanBtn = screen.getByRole("button", { name: "Kiểm tra" });
    fireEvent.click(scanBtn);

    await waitFor(() => {
      expect(mocks.scanLifeMapReviewFindings).toHaveBeenCalled();
      expect(screen.getByText("Cần bổ sung")).toBeInTheDocument();
    });

    const resolveBtn = screen.getByRole("button", { name: "Tôi đã kiểm tra" });
    fireEvent.click(resolveBtn);

    await waitFor(() => {
      expect(mocks.actOnLifeMapReviewFinding).toHaveBeenCalledWith(
        "find-1",
        "resolved",
        expect.any(String),
      );
      expect(screen.getByText("Đã ghi nhận lựa chọn của bạn.")).toBeInTheDocument();
    });
  });

  it("opens Episode Replay and views bitemporal revision comparisons", async () => {
    mocks.getLifeMapReplay.mockResolvedValue({
      episode: {
        id: "ep-1",
        title: "Kiểm soát huyết áp",
      },
      events: [
        {
          id: "evt-replay-1",
          revision: 1,
          revision_id: "rev-1",
          type: "vitals",
          truth_state: "confirmed",
          policy_version: "vitals.v1",
          provenance: {
            assertion: "Đo huyết áp: 126/81 mmHg",
          },
          why: {
            text: "Đo huyết áp sáng định kỳ.",
          },
        },
      ],
      decisions: [],
    });

    mocks.getLifeMapRevisionComparison.mockResolvedValue({
      event_id: "evt-replay-1",
      summary: "Cập nhật chỉ số huyết áp sau hiệu chỉnh.",
      changes: [
        {
          field: "BP",
          before: "128/84",
          after: "126/81",
        },
      ],
      source_spans: {
        before: { source_span: { start: 0, end: 10 } },
        after: { source_span: { start: 0, end: 10 } },
      },
    });

    await act(async () => {
      render(<LifeMapPage />);
    });

    const replayBtn = screen.getByRole("button", { name: "Xem lại" });
    fireEvent.click(replayBtn);

    await waitFor(() => {
      expect(mocks.getLifeMapReplay).toHaveBeenCalledWith("ep-1");
      expect(screen.getByText("Đo huyết áp: 126/81 mmHg")).toBeInTheDocument();
    });

    const compareBtn = screen.getByRole("button", { name: "Xem thay đổi giữa các phiên bản" });
    fireEvent.click(compareBtn);

    await waitFor(() => {
      expect(mocks.getLifeMapRevisionComparison).toHaveBeenCalled();
      expect(screen.getByText("Cập nhật chỉ số huyết áp sau hiệu chỉnh.")).toBeInTheDocument();
    });
  });

  it("creates a text capture session via the Sidecar", async () => {
    mocks.startLifeMapTextCapture.mockResolvedValue({
      id: "cap-1",
      persisted: true,
      status: "draft",
      candidates: [
        {
          id: "cand-1",
          type: "symptom",
          status: "draft",
          value: { text: "Hôm nay cảm thấy rất khỏe", category: "care_note" },
          missing_critical_fields: [],
          security_findings: [],
          field_confidence: { text: 0.95 },
        },
      ],
    });

    mocks.reviewLifeMapCaptureCandidate.mockResolvedValue({
      candidate: {
        id: "cand-1",
        type: "symptom",
        status: "confirmed",
        value: { text: "Hôm nay cảm thấy rất khỏe", category: "care_note" },
      },
    });

    await act(async () => {
      render(<LifeMapPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Ghi nhận nhanh")).toBeInTheDocument();
    });

    const textInput = screen.getByLabelText("Điều bạn muốn ghi lại");
    fireEvent.change(textInput, {
      target: { value: "Hôm nay cảm thấy rất khỏe" },
    });

    const createTextBtn = screen.getByRole("button", { name: "Tạo bản nháp văn bản" });
    fireEvent.click(createTextBtn);

    await waitFor(() => {
      expect(mocks.startLifeMapTextCapture).toHaveBeenCalledWith("Hôm nay cảm thấy rất khỏe");
      expect(screen.getByText("Bản nháp cần xem lại")).toBeInTheDocument();
    });

    const confirmBtn = screen.getByRole("button", { name: "Xác nhận sau khi đối chiếu" });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mocks.reviewLifeMapCaptureCandidate).toHaveBeenCalledWith(
        "cand-1",
        "confirm",
        expect.any(Object),
      );
    });
  });
});
