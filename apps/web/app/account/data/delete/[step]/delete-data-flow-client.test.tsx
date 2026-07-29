import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const push = vi.fn();
  const replace = vi.fn();
  return {
    push,
    replace,
    router: { push, replace },
    requestDsarDelete: vi.fn(),
    listDsarRequests: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/compliance", async () => {
  const actual = await vi.importActual<typeof import("@/lib/compliance")>(
    "@/lib/compliance",
  );
  return {
    ...actual,
    requestDsarDelete: mocks.requestDsarDelete,
    listDsarRequests: mocks.listDsarRequests,
  };
});

import DeleteDataFlowClient from "./delete-data-flow-client";

beforeEach(() => {
  vi.clearAllMocks();
  process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED = "true";
});

afterEach(() => {
  cleanup();
  delete process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED;
});

describe("DeleteDataFlowClient", () => {
  it("keeps deletion consequences on a separate focused review route", () => {
    render(<DeleteDataFlowClient step="review" />);

    expect(screen.getByRole("heading", { name: "Trước khi gửi yêu cầu xóa" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Điều gì sẽ xảy ra" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dữ liệu được giữ lại" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Gửi yêu cầu xóa" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));
    expect(mocks.push).toHaveBeenCalledWith("/account/data/delete/confirm");
  });

  it("requires an explicit acknowledgement before exercising deletion authority", async () => {
    mocks.requestDsarDelete.mockResolvedValue({ id: 27, kind: "delete", status: "received" });
    render(<DeleteDataFlowClient step="confirm" />);

    const confirm = screen.getByRole("button", { name: "Gửi yêu cầu xóa" });
    expect(confirm).toBeDisabled();
    expect(mocks.requestDsarDelete).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getByRole("switch", {
        name: "Tôi hiểu yêu cầu này có thể xóa hoặc ẩn danh hóa dữ liệu cá nhân và không thể hoàn tác.",
      }),
    );
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() => {
      expect(mocks.requestDsarDelete).toHaveBeenCalledOnce();
      expect(mocks.replace).toHaveBeenCalledWith("/account/data/delete/status?request=27");
    });
  });

  it("sanitizes a failing deletion command instead of exposing raw infrastructure details", async () => {
    mocks.requestDsarDelete.mockRejectedValue(
      new Error("postgres host=db.internal credential=super-secret"),
    );
    render(<DeleteDataFlowClient step="confirm" />);

    fireEvent.click(screen.getByRole("switch"));
    fireEvent.click(screen.getByRole("button", { name: "Gửi yêu cầu xóa" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Không thể gửi yêu cầu lúc này. Vui lòng thử lại.");
    expect(alert).not.toHaveTextContent("db.internal");
    expect(alert).not.toHaveTextContent("super-secret");
  });
});
