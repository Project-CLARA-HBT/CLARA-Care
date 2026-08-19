import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConflictResolverModal } from "./conflict-resolver-modal";

afterEach(cleanup);

describe("ConflictResolverModal", () => {
  const clientDraft = {
    substance: "Penicillin",
    reaction: "Severe Rash",
    severity: "severe",
  };

  const serverState = {
    substance: "Penicillin VK",
    reaction: "Mild itching",
    severity: "mild",
  };

  it("renders side-by-side diff comparing server state and client draft", () => {
    render(
      <ConflictResolverModal
        open={true}
        onClose={vi.fn()}
        resourceName="Dị ứng"
        clientDraft={clientDraft}
        serverState={serverState}
        onKeepClient={vi.fn()}
        onAcceptServer={vi.fn()}
      />,
    );

    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByText(/Xung đột dữ liệu: Dị ứng/i)).toBeInTheDocument();
    expect(screen.getByText("Severe Rash")).toBeInTheDocument();
    expect(screen.getByText("Mild itching")).toBeInTheDocument();
    expect(screen.getByText("Bản ghi trên máy chủ (Mới nhất)")).toBeInTheDocument();
    expect(screen.getByText("Thay đổi của bạn (Bản nháp)")).toBeInTheDocument();
  });

  it("calls onKeepClient when user chooses to keep their draft", () => {
    const keepSpy = vi.fn();
    render(
      <ConflictResolverModal
        open={true}
        onClose={vi.fn()}
        clientDraft={clientDraft}
        serverState={serverState}
        onKeepClient={keepSpy}
        onAcceptServer={vi.fn()}
      />,
    );

    const keepBtn = screen.getByRole("button", { name: "Giữ thay đổi của tôi" });
    fireEvent.click(keepBtn);
    expect(keepSpy).toHaveBeenCalledTimes(1);
  });

  it("calls onAcceptServer when user chooses server version", () => {
    const serverSpy = vi.fn();
    render(
      <ConflictResolverModal
        open={true}
        onClose={vi.fn()}
        clientDraft={clientDraft}
        serverState={serverState}
        onKeepClient={vi.fn()}
        onAcceptServer={serverSpy}
      />,
    );

    const acceptBtn = screen.getByRole("button", { name: "Chấp nhận bản máy chủ" });
    fireEvent.click(acceptBtn);
    expect(serverSpy).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when cancel is clicked", () => {
    const closeSpy = vi.fn();
    render(
      <ConflictResolverModal
        open={true}
        onClose={closeSpy}
        clientDraft={clientDraft}
        serverState={serverState}
        onKeepClient={vi.fn()}
        onAcceptServer={vi.fn()}
      />,
    );

    const cancelBtn = screen.getByRole("button", { name: "Hủy & Xem lại" });
    fireEvent.click(cancelBtn);
    expect(closeSpy).toHaveBeenCalledTimes(1);
  });
});
