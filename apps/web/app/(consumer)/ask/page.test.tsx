import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ConsumerAskPage from "./page";
import { v2Client, type ConsumerAnswerEnvelope } from "@/lib/api/v2-client";

let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
}));

vi.mock("@/components/shell/preference-provider", () => ({
  usePreferences: () => ({
    uiLanguage: "vi",
    themePreference: "light",
  }),
}));

vi.mock("@/components/shell/profile-boundary", () => ({
  useProfileContext: () => ({
    activeProfileId: "profile-1",
    activeProfile: { id: "profile-1", display_name: "Tôi" },
  }),
}));

afterEach(cleanup);

beforeEach(() => {
  mockSearchParams = new URLSearchParams();
  vi.restoreAllMocks();
});

describe("ConsumerAskPage", () => {
  it("renders empty state with prompt suggestions when no active question", () => {
    render(<ConsumerAskPage />);

    expect(screen.getByRole("heading", { name: "Hỏi CLARA" })).toBeInTheDocument();
    expect(screen.getByTestId("ask-empty-state")).toBeInTheDocument();
    expect(
      screen.getByText("Bạn đang băn khoăn điều gì về sức khỏe?")
    ).toBeInTheDocument();
    expect(screen.getByTestId("suggestion-chip-0")).toBeInTheDocument();
    expect(screen.getByTestId("ask-composer")).toBeInTheDocument();
  });

  it("submits question via streamAsk and displays envelope response", async () => {
    const mockEnvelope: ConsumerAnswerEnvelope = {
      answer: {
        main_message: "Thuốc nên uống sau bữa ăn sáng 30 phút.",
        actions: [],
        sections: [],
      },
      personal_evidence: [],
      safety: { urgency: "routine" },
    };

    vi.spyOn(v2Client, "streamAsk").mockImplementation(
      async (_req, handlers) => {
        handlers.onStart?.();
        handlers.onToken?.("Thuốc nên uống ");
        handlers.onToken?.("sau bữa ăn sáng 30 phút.");
        handlers.onDone?.(mockEnvelope);
      }
    );

    render(<ConsumerAskPage />);

    const textarea = screen.getByTestId("ask-composer-textarea");
    fireEvent.change(textarea, { target: { value: "Uống thuốc khi nào?" } });

    const sendBtn = screen.getByTestId("ask-composer-send-button");
    fireEvent.click(sendBtn);

    expect(await screen.findByTestId("ask-active-exchange")).toBeInTheDocument();
    expect(screen.getByTestId("ask-user-message-text")).toHaveTextContent(
      "Uống thuốc khi nào?"
    );

    await waitFor(() => {
      expect(
        screen.getByText("Thuốc nên uống sau bữa ăn sáng 30 phút.")
      ).toBeInTheDocument();
    });
  });

  it("supports cancellation via Stop button and preserves user draft", async () => {
    let capturedSignal: AbortSignal | undefined;

    vi.spyOn(v2Client, "streamAsk").mockImplementation(
      async (_req, handlers, options) => {
        capturedSignal = options?.signal;
        handlers.onStart?.();
        handlers.onToken?.("Đang suy nghĩ...");
        // Return a promise that waits or checks aborted
        return new Promise<void>((resolve, reject) => {
          options?.signal?.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        });
      }
    );

    render(<ConsumerAskPage />);

    const textarea = screen.getByTestId("ask-composer-textarea");
    fireEvent.change(textarea, { target: { value: "Câu hỏi cần dừng" } });

    const sendBtn = screen.getByTestId("ask-composer-send-button");
    fireEvent.click(sendBtn);

    // Stop button appears
    const stopBtn = await screen.findByTestId("ask-composer-stop-button");
    fireEvent.click(stopBtn);

    expect(capturedSignal?.aborted).toBe(true);

    // Draft is preserved in composer textarea
    await waitFor(() => {
      expect(screen.getByText("Đã dừng câu trả lời")).toBeInTheDocument();
    });
    expect(screen.getByTestId("ask-composer-textarea")).toHaveValue("Câu hỏi cần dừng");
  });

  it("renders scoped context banner when URL contains context parameters", () => {
    mockSearchParams = new URLSearchParams({
      context_kind: "result",
      context_id: "res-10",
      context_label: "Xét nghiệm đường huyết",
    });

    render(<ConsumerAskPage />);

    expect(screen.getByTestId("entry-context-banner")).toBeInTheDocument();
    expect(screen.getByText("Xét nghiệm đường huyết")).toBeInTheDocument();
  });
});
