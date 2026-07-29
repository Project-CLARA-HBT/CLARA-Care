import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

/**
 * Feature: regulatory-compliance, Requirement 1.2 / Property P9 (no medical
 * content gating before acknowledgement when the flag is on) and 8.1/8.2 (flag
 * off ⇒ no gate, current behavior preserved).
 */

const mockGetNotice = vi.fn();
const mockAck = vi.fn();
const flagState = { enabled: false };
const pathState = { pathname: "/chat" };

vi.mock("@/lib/compliance", () => ({
  isTransparencyNoticeEnabled: () => flagState.enabled,
  getTransparencyNotice: () => mockGetNotice(),
  acknowledgeTransparencyNotice: (version: string) => mockAck(version),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => pathState.pathname,
}));

import TransparencyNoticeGate from "@/components/compliance/transparency-notice-gate";

beforeEach(() => {
  // Pin the UI language so button copy is deterministic (defaults to vi).
  window.localStorage.setItem("clara_ui_language", "en");
});

afterEach(() => {
  vi.clearAllMocks();
  flagState.enabled = false;
  pathState.pathname = "/chat";
  window.localStorage.clear();
});

describe("TransparencyNoticeGate", () => {
  it("renders nothing and makes no calls when the flag is OFF (Req 8.2)", async () => {
    flagState.enabled = false;
    const { container } = render(<TransparencyNoticeGate />);
    expect(container.firstChild).toBeNull();
    expect(mockGetNotice).not.toHaveBeenCalled();
  });

  it("renders nothing when off a medical surface", async () => {
    flagState.enabled = true;
    pathState.pathname = "/account/consent";
    const { container } = render(<TransparencyNoticeGate />);
    expect(container.firstChild).toBeNull();
    expect(mockGetNotice).not.toHaveBeenCalled();
  });

  it("presents the notice dialog when unacknowledged on a medical surface (Property P9)", async () => {
    flagState.enabled = true;
    mockGetNotice.mockResolvedValue({
      enabled: true,
      version: "2026-01-v1",
      acknowledged: false,
    });
    render(<TransparencyNoticeGate />);
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
  });

  it("records acknowledgement and dismisses the dialog", async () => {
    flagState.enabled = true;
    mockGetNotice.mockResolvedValue({
      enabled: true,
      version: "2026-01-v1",
      acknowledged: false,
    });
    mockAck.mockResolvedValue(undefined);
    render(<TransparencyNoticeGate />);
    const button = await screen.findByRole("button", {
      name: /understand and continue/i,
    });
    fireEvent.click(button);
    await waitFor(() => {
      expect(mockAck).toHaveBeenCalledWith("2026-01-v1");
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("does not gate when the notice is already acknowledged", async () => {
    flagState.enabled = true;
    mockGetNotice.mockResolvedValue({
      enabled: true,
      version: "2026-01-v1",
      acknowledged: true,
    });
    const { container } = render(<TransparencyNoticeGate />);
    await waitFor(() => {
      expect(mockGetNotice).toHaveBeenCalled();
    });
    expect(container.firstChild).toBeNull();
  });

  it("fails open (no gate) when the notice cannot be loaded", async () => {
    flagState.enabled = true;
    mockGetNotice.mockRejectedValue(new Error("network"));
    const { container } = render(<TransparencyNoticeGate />);
    await waitFor(() => {
      expect(mockGetNotice).toHaveBeenCalled();
    });
    expect(container.firstChild).toBeNull();
  });
});
