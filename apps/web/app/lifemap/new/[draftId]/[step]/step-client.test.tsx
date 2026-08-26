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

let currentWrapper: { unmount: () => void } | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  currentWrapper = null;
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

afterEach(() => {
  if (currentWrapper) {
    currentWrapper.unmount();
    currentWrapper = null;
  }
  cleanup();
});

async function renderStep(step: string, customDraft?: any) {
  if (currentWrapper) {
    currentWrapper.unmount();
    currentWrapper = null;
  }
  if (customDraft) {
    mocks.getDraft.mockResolvedValue(customDraft);
  }
  await act(async () => {
    currentWrapper = render(<LifeMapEpisodeStepClient draftId={draft.id} step={step} />);
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

  it("navigates smoothly through numbered steps (step-1 -> step-2 -> step-3 -> step-4 -> step-5)", async () => {
    // Step 1
    await renderStep("step-1");
    const titleInput = await screen.findByLabelText("Bạn muốn gọi hành trình này là gì?");
    fireEvent.change(titleInput, { target: { value: "Kiểm soát đường huyết" } });
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    await waitFor(() => {
      expect(mocks.updateDraft).toHaveBeenCalledWith(draft.id, 1, "goal", {
        title: "Kiểm soát đường huyết",
        goal: "",
        priority: "routine",
      });
      expect(mocks.push).toHaveBeenCalledWith(`/lifemap/new/${draft.id}/step-2`);
    });

    // Step 2
    const step2Draft = {
      ...draft,
      current_step: "goal" as const,
      payload: { title: "Kiểm soát đường huyết" },
      revision: 2,
    };
    await renderStep("step-2", step2Draft);
    const goalInput = await screen.findByLabelText(/Bạn muốn đạt được điều gì/);
    fireEvent.change(goalInput, { target: { value: "Đường huyết đói < 7.0 mmol/L" } });
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    await waitFor(() => {
      expect(mocks.updateDraft).toHaveBeenCalledWith(draft.id, 2, "priority", {
        title: "Kiểm soát đường huyết",
        goal: "Đường huyết đói < 7.0 mmol/L",
        priority: "routine",
      });
      expect(mocks.push).toHaveBeenCalledWith(`/lifemap/new/${draft.id}/step-3`);
    });

    // Step 3
    const step3Draft = {
      ...draft,
      current_step: "priority" as const,
      payload: { title: "Kiểm soát đường huyết", goal: "Đường huyết đói < 7.0 mmol/L" },
      revision: 3,
    };
    await renderStep("step-3", step3Draft);
    const prioritySelect = await screen.findByLabelText("Mức ưu tiên");
    fireEvent.change(prioritySelect, { target: { value: "urgent" } });
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    await waitFor(() => {
      expect(mocks.updateDraft).toHaveBeenCalledWith(draft.id, 3, "review", {
        title: "Kiểm soát đường huyết",
        goal: "Đường huyết đói < 7.0 mmol/L",
        priority: "urgent",
      });
      expect(mocks.push).toHaveBeenCalledWith(`/lifemap/new/${draft.id}/step-4`);
    });

    // Step 4 (Preview)
    const step4Draft = {
      ...draft,
      current_step: "review" as const,
      payload: {
        title: "Kiểm soát đường huyết",
        goal: "Đường huyết đói < 7.0 mmol/L",
        priority: "urgent" as const,
      },
      revision: 4,
    };
    await renderStep("step-4", step4Draft);
    expect(await screen.findByText("Sổ cái GLHS v2 • 6-Phase OCC Kernel")).toBeInTheDocument();
    expect(screen.getByText("Kiểm soát đường huyết")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    await waitFor(() => {
      expect(mocks.updateDraft).toHaveBeenCalledWith(draft.id, 4, "review", {
        title: "Kiểm soát đường huyết",
        goal: "Đường huyết đói < 7.0 mmol/L",
        priority: "urgent",
      });
      expect(mocks.push).toHaveBeenCalledWith(`/lifemap/new/${draft.id}/step-5`);
    });

    // Step 5 (Commit)
    const step5Draft = {
      ...draft,
      current_step: "review" as const,
      payload: {
        title: "Kiểm soát đường huyết",
        goal: "Đường huyết đói < 7.0 mmol/L",
        priority: "urgent" as const,
      },
      revision: 5,
    };
    mocks.commitDraft.mockResolvedValue({
      ...step5Draft,
      status: "committed",
      revision: 6,
      committed_resource: { type: "lifemap_episode", id: "ep-999" },
    });
    await renderStep("step-5", step5Draft);

    fireEvent.click(screen.getByRole("button", { name: "Tạo hành trình" }));

    await waitFor(() => {
      expect(mocks.commitDraft).toHaveBeenCalledWith(draft.id, 5, expect.any(String));
      expect(mocks.replace).toHaveBeenCalledWith("/lifemap");
      expect(mocks.refresh).toHaveBeenCalled();
    });
  });

  it("renders live accumulated preview cards across steps", async () => {
    // Step 1: title updates preview live
    await renderStep("step-1");
    const preview = screen.getByTestId("accumulated-config-preview");
    expect(preview).toBeInTheDocument();

    const titleInput = screen.getByLabelText("Bạn muốn gọi hành trình này là gì?");
    fireEvent.change(titleInput, { target: { value: "Chăm sóc sau phẫu thuật" } });

    expect(screen.getByText("Chăm sóc sau phẫu thuật")).toBeInTheDocument();

    // Step 2: preview shows accumulated title and lets user edit back to step-1
    const step2Draft = {
      ...draft,
      current_step: "goal" as const,
      payload: { title: "Chăm sóc sau phẫu thuật" },
      revision: 2,
    };
    await renderStep("step-2", step2Draft);

    expect(screen.getByText("Chăm sóc sau phẫu thuật")).toBeInTheDocument();
    const editButtons = screen.getAllByRole("button", { name: "Chỉnh sửa" });
    expect(editButtons.length).toBeGreaterThan(0);

    fireEvent.click(editButtons[0]);
    await waitFor(() => {
      expect(mocks.push).toHaveBeenCalledWith(`/lifemap/new/${draft.id}/step-1`);
    });
  });

  it("supports Back button navigation without losing entered draft data", async () => {
    const step3Draft = {
      ...draft,
      current_step: "priority" as const,
      payload: { title: "Tập vật lý trị liệu", goal: "Đi bộ 30 phút" },
      revision: 3,
    };
    await renderStep("step-3", step3Draft);

    const backButton = screen.getByRole("button", { name: "Quay lại" });
    fireEvent.click(backButton);

    await waitFor(() => {
      expect(mocks.updateDraft).toHaveBeenCalledWith(draft.id, 3, "goal", {
        title: "Tập vật lý trị liệu",
        goal: "Đi bộ 30 phút",
        priority: "routine",
      });
      expect(mocks.push).toHaveBeenCalledWith(`/lifemap/new/${draft.id}/step-2`);
    });
  });

  it("clears inline errors live as the user corrects the input", async () => {
    await renderStep("step-1");
    const titleInput = screen.getByLabelText("Bạn muốn gọi hành trình này là gì?");
    fireEvent.change(titleInput, { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    // Error is shown
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Nhập ít nhất 2 ký tự.")).toBeInTheDocument();

    // User types valid text -> error is cleared live
    fireEvent.change(titleInput, { target: { value: "Huyết áp ổn định" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("supports direct edit buttons on Step 4 preview card", async () => {
    const previewDraft = {
      ...draft,
      current_step: "review" as const,
      payload: {
        title: "Theo dõi nhịp tim",
        goal: "Duy trì 60-80 bpm",
        priority: "routine" as const,
      },
      revision: 4,
    };
    await renderStep("step-4", previewDraft);

    // Edit Title button
    const editTitleBtn = screen.getByRole("button", { name: "Tên hành trình" });
    fireEvent.click(editTitleBtn);
    await waitFor(() => {
      expect(mocks.push).toHaveBeenCalledWith(`/lifemap/new/${draft.id}/step-1`);
    });
  });

  it("redirects inactive draft to /lifemap on mount", async () => {
    const abandonedDraft = {
      ...draft,
      status: "abandoned" as const,
    };
    await renderStep("title", abandonedDraft);

    await waitFor(() => {
      expect(mocks.replace).toHaveBeenCalledWith("/lifemap");
    });
  });

  it("displays friendly error message when draft fetching fails", async () => {
    mocks.getDraft.mockRejectedValue(new Error("Network disconnect"));
    await renderStep("title");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Bản nháp không còn khả dụng hoặc đã thay đổi");
  });

  it("handles commit failure with error notification", async () => {
    const reviewDraft = {
      ...draft,
      current_step: "review" as const,
      payload: { title: "Kiểm tra định kỳ", goal: "Tái khám đúng hẹn", priority: "routine" as const },
      revision: 4,
    };
    mocks.commitDraft.mockRejectedValue(new Error("Commit internal server error"));
    await renderStep("review", reviewDraft);

    fireEvent.click(screen.getByRole("button", { name: "Tạo hành trình" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Chưa thể tạo hành trình");
  });
});
