import type { ReactNode } from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const push = vi.fn();
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    getOnboarding: vi.fn(),
    updateOnboarding: vi.fn(),
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
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: () => "normal",
}));

vi.mock("@/lib/phr-onboarding", () => ({
  getPhrOnboarding: mocks.getOnboarding,
  updatePhrOnboarding: mocks.updateOnboarding,
}));

import WelcomeStepClient from "./welcome-step-client";

const onboarding = {
  status: "pending",
  needs_onboarding: true,
  version: "2026-07-v1",
  completed_at: null,
  personalization_consent: false,
  optional_fields: [],
  record: {
    full_name: "Nguyễn An",
    date_of_birth: "1990-01-02",
    gender: "female",
    blood_type: "O",
    height_cm: 165,
    weight_kg: 55,
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getOnboarding.mockResolvedValue(onboarding);
  mocks.updateOnboarding.mockResolvedValue(onboarding);
});

afterEach(cleanup);

async function renderStep(
  step: Parameters<typeof WelcomeStepClient>[0]["step"],
) {
  await act(async () => {
    render(<WelcomeStepClient step={step} />);
    await Promise.resolve();
    const request = mocks.getOnboarding.mock.results.at(-1)?.value;
    if (request instanceof Promise) await request;
    await Promise.resolve();
  });
}

describe("WelcomeStepClient", () => {
  it("rejects an invalid measurement locally and focuses the first invalid field", async () => {
    await renderStep("body");

    const height = await screen.findByLabelText(/Chiều cao/);
    fireEvent.change(height, { target: { value: "không phải số" } });
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Chiều cao: Nhập một số từ 0 đến 300.",
    );
    expect(height).toHaveAttribute("aria-invalid", "true");
    expect(height).toHaveFocus();
    expect(mocks.updateOnboarding).not.toHaveBeenCalled();
  });

  it("saves edits before Back so route navigation does not discard the current step", async () => {
    const updated = {
      ...onboarding,
      record: { ...onboarding.record, full_name: "Nguyễn Bình" },
    };
    mocks.updateOnboarding.mockResolvedValue(updated);
    await renderStep("name");

    const name = await screen.findByLabelText(/Tên hiển thị/);
    fireEvent.change(name, { target: { value: "  Nguyễn Bình  " } });
    fireEvent.click(screen.getByRole("button", { name: "Quay lại" }));

    await waitFor(() => {
      expect(mocks.updateOnboarding).toHaveBeenCalledWith({
        action: "save",
        full_name: "Nguyễn Bình",
      });
      expect(mocks.push).toHaveBeenCalledWith("/welcome/start");
    });
  });

  it("sanitizes recoverable API failures instead of displaying raw internals", async () => {
    mocks.updateOnboarding.mockRejectedValue(
      new Error("postgres host=db.internal token=super-secret"),
    );
    await renderStep("name");

    await screen.findByLabelText(/Tên hiển thị/);
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Không thể lưu thay đổi lúc này. Vui lòng thử lại.",
    );
    expect(alert).not.toHaveTextContent("db.internal");
    expect(alert).not.toHaveTextContent("super-secret");
  });

  it("requires explicit self-declaration before sending completion authority", async () => {
    const completed = { ...onboarding, status: "completed", needs_onboarding: false };
    mocks.updateOnboarding.mockResolvedValue(completed);
    await renderStep("review");

    expect(await screen.findByText("Nữ")).toBeInTheDocument();
    const confirmation = screen.getByRole("checkbox", {
      name: "Tôi xác nhận các thông tin trên là do chính tôi tự khai báo.",
    });
    const finish = screen.getByRole("button", { name: "Hoàn tất thiết lập" });
    expect(confirmation).not.toBeChecked();
    expect(finish).toBeDisabled();
    expect(mocks.updateOnboarding).not.toHaveBeenCalled();

    fireEvent.click(confirmation);
    expect(finish).toBeEnabled();
    fireEvent.click(finish);

    await waitFor(() => {
      expect(mocks.updateOnboarding).toHaveBeenCalledWith({
        action: "complete",
        confirm_self_declared: true,
      });
      expect(mocks.replace).toHaveBeenCalledWith("/today");
      expect(mocks.refresh).toHaveBeenCalled();
    });
  });
});
