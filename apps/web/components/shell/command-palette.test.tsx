import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CommandPalette } from "./command-palette";
import { ShellModeProvider } from "./shell-mode-provider";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, refresh: vi.fn() }),
  usePathname: () => "/home",
}));

describe("CommandPalette", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders when open and focuses input", () => {
    render(
      <ShellModeProvider>
        <CommandPalette open={true} role="normal" />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    const input = screen.getByRole("combobox");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("data-pii-safe", "true");
  });

  it("filters actions based on user input", () => {
    render(
      <ShellModeProvider>
        <CommandPalette open={true} role="normal" />
      </ShellModeProvider>,
    );

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "focus" } });

    expect(screen.getByText(/Chế độ Tập trung/)).toBeInTheDocument();
    expect(screen.queryByText(/Chế độ Toàn màn hình/)).not.toBeInTheDocument();
  });

  it("filters out role-restricted actions for normal role", () => {
    render(
      <ShellModeProvider>
        <CommandPalette open={true} role="normal" />
      </ShellModeProvider>,
    );

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "scribe" } });

    expect(screen.getByText("Không tìm thấy lệnh hoặc tính năng phù hợp")).toBeInTheDocument();
  });

  it("shows clinical actions for doctor role", () => {
    render(
      <ShellModeProvider>
        <CommandPalette open={true} role="doctor" />
      </ShellModeProvider>,
    );

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "scribe" } });

    expect(screen.getByText(/CLARA Scribe/)).toBeInTheDocument();
  });

  it("navigates on action selection", () => {
    const handleClose = vi.fn();
    render(
      <ShellModeProvider>
        <CommandPalette open={true} role="normal" onClose={handleClose} />
      </ShellModeProvider>,
    );

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "thuốc" } });

    const option = screen.getByText(/Tủ thuốc & An toàn/);
    fireEvent.click(option);

    expect(mocks.push).toHaveBeenCalledWith("/medicines");
    expect(handleClose).toHaveBeenCalled();
  });

  it("handles keyboard navigation ArrowDown and Enter", () => {
    render(
      <ShellModeProvider>
        <CommandPalette open={true} role="normal" />
      </ShellModeProvider>,
    );

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "explore" } });

    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
  });

  it("closes on Escape key", () => {
    const handleClose = vi.fn();
    render(
      <ShellModeProvider>
        <CommandPalette open={true} role="normal" onClose={handleClose} />
      </ShellModeProvider>,
    );

    const input = screen.getByRole("combobox");
    fireEvent.keyDown(input, { key: "Escape" });
    expect(handleClose).toHaveBeenCalled();
  });
});
