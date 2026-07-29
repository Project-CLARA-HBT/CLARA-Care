import type { ReactNode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const push = vi.fn();
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    getDraft: vi.fn(),
    updateDraft: vi.fn(),
    commitDraft: vi.fn(),
    push,
    replace,
    refresh,
    router: { push, replace, refresh },
  };
});

vi.mock("next/navigation", () => ({ useRouter: () => mocks.router }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/guided-flows", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/guided-flows")>();
  return {
    ...original,
    getGuidedFlowDraft: mocks.getDraft,
    updateLifeMapEpisodeDraft: mocks.updateDraft,
    commitLifeMapEpisodeDraft: mocks.commitDraft,
  };
});

import LifeMapEpisodeStepClient from "./step-client";

const draft = {
  id: "draft-opaque-1",
  flow_type: "lifemap_episode" as const,
  current_step: "title" as const,
  payload: {},
  status: "active" as const,
  revision: 1,
  expires_at: "2026-08-06T00:00:00Z",
  committed_resource: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getDraft.mockResolvedValue(draft);
  mocks.updateDraft.mockImplementation(
    async (_id: string, revision: number, currentStep: string, payload: object) => ({
      ...draft,
      current_step: currentStep,
      payload,
      revision: revision + 1,
    }),
  );
});

afterEach(cleanup);

async function renderStep(step: "title" | "goal" | "priority" | "review") {
  await act(async () => {
    render(<LifeMapEpisodeStepClient draftId={draft.id} step={step} />);
    await Promise.resolve();
    const request = mocks.getDraft.mock.results.at(-1)?.value;
    if (request instanceof Promise) await request;
    await Promise.resolve();
  });
}

describe("LifeMapEpisodeStepClient", () => {
  it("validates and focuses the journey title before sending health content", async () => {
    await renderStep("title");
    const title = await screen.findByLabelText("Bạn muốn gọi hành trình này là gì?");
    fireEvent.change(title, { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Nhập ít nhất 2 ký tự.");
    expect(title).toHaveFocus();
    expect(mocks.updateDraft).not.toHaveBeenCalled();
  });

  it("saves the complete allowlisted payload using the draft revision", async () => {
    await renderStep("title");
    const title = await screen.findByLabelText("Bạn muốn gọi hành trình này là gì?");
    fireEvent.change(title, { target: { value: "  Ngủ tốt hơn  " } });
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    await waitFor(() => {
      expect(mocks.updateDraft).toHaveBeenCalledWith(draft.id, 1, "goal", {
        title: "Ngủ tốt hơn",
        goal: "",
        priority: "routine",
      });
      expect(mocks.push).toHaveBeenCalledWith(`/lifemap/new/${draft.id}/goal`);
    });
  });

  it("does not expose raw API details when a revision save fails", async () => {
    mocks.updateDraft.mockRejectedValue(new Error("db.internal secret-token"));
    await renderStep("title");
    fireEvent.change(
      await screen.findByLabelText("Bạn muốn gọi hành trình này là gì?"),
      { target: { value: "Theo dõi giấc ngủ" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Không thể lưu vì bản nháp đã thay đổi");
    expect(alert).not.toHaveTextContent("db.internal");
    expect(alert).not.toHaveTextContent("secret-token");
  });

  it("commits only from review and returns to LifeMap", async () => {
    const reviewDraft = {
      ...draft,
      current_step: "review" as const,
      payload: { title: "Ngủ tốt hơn", goal: "Ngủ đủ", priority: "soon" as const },
      revision: 4,
    };
    mocks.getDraft.mockResolvedValue(reviewDraft);
    mocks.commitDraft.mockResolvedValue({
      ...reviewDraft,
      status: "committed",
      revision: 5,
      committed_resource: { type: "lifemap_episode", id: "episode-1" },
    });
    await renderStep("review");

    expect(await screen.findByText("Ngủ đủ")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tạo hành trình" }));

    await waitFor(() => {
      expect(mocks.commitDraft).toHaveBeenCalledWith(
        draft.id,
        4,
        expect.any(String),
      );
      expect(mocks.replace).toHaveBeenCalledWith("/lifemap");
      expect(mocks.refresh).toHaveBeenCalled();
    });
  });
});
