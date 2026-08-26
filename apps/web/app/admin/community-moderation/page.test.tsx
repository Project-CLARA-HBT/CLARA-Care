import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mockListReports = vi.fn();
const mockActOnReport = vi.fn();

vi.mock("@/lib/social", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/social")>();
  return {
    ...actual,
    listReports: () => mockListReports(),
    actOnReport: (id: number, action: "dismiss" | "remove") =>
      mockActOnReport(id, action),
  };
});

vi.mock("@/lib/auth-store", () => ({
  getRole: () => "admin",
}));

import CommunityModerationPage from "@/app/admin/community-moderation/page";
import { SocialUnavailableError } from "@/lib/social";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("CommunityModerationPage (Spec v5 Section 6.65)", () => {
  it("renders AdminShell, summary KPIs, and dense reports table", async () => {
    mockListReports.mockResolvedValue([
      {
        id: 1,
        target_type: "post",
        target_id: 101,
        reason: "spam",
        status: "open",
        created_at: "2026-04-01T12:00:00Z",
      },
      {
        id: 2,
        target_type: "comment",
        target_id: 202,
        reason: "harassment",
        status: "open",
        created_at: "2026-04-02T14:30:00Z",
      },
    ]);

    render(<CommunityModerationPage />);

    await waitFor(() => {
      expect(screen.getByText("#1")).toBeInTheDocument();
    });

    expect(screen.getByText("Community Moderation")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
    expect(screen.getByText(/Post #101/i)).toBeInTheDocument();
    expect(screen.getByText(/Comment #202/i)).toBeInTheDocument();
  });

  it("opens content preview inspector when a report row is clicked", async () => {
    mockListReports.mockResolvedValue([
      {
        id: 1,
        target_type: "post",
        target_id: 101,
        reason: "spam",
        status: "open",
        created_at: "2026-04-01T12:00:00Z",
      },
    ]);

    render(<CommunityModerationPage />);

    await waitFor(() => {
      expect(screen.getByText("#1")).toBeInTheDocument();
    });

    const inspectBtn = screen.getByRole("button", { name: /inspect/i });
    fireEvent.click(inspectBtn);

    await waitFor(() => {
      expect(screen.getByText(/Reported Content Preview/i)).toBeInTheDocument();
      expect(screen.getByText(/Violation Reason/i)).toBeInTheDocument();
    });
  });

  it("opens confirmation modal before executing remove action", async () => {
    mockListReports.mockResolvedValue([
      {
        id: 1,
        target_type: "post",
        target_id: 101,
        reason: "harassment",
        status: "open",
        created_at: "2026-04-01T12:00:00Z",
      },
    ]);
    mockActOnReport.mockResolvedValue(undefined);

    render(<CommunityModerationPage />);

    await waitFor(() => {
      expect(screen.getByText("#1")).toBeInTheDocument();
    });

    const removeBtn = screen.getByRole("button", { name: /remove/i });
    fireEvent.click(removeBtn);

    // Modal opens
    await waitFor(() => {
      expect(screen.getByText(/Confirm Content Removal/i)).toBeInTheDocument();
    });

    // Action has not executed yet
    expect(mockActOnReport).not.toHaveBeenCalled();

    // Confirm in dialog
    const confirmBtn = screen.getByRole("button", { name: /confirm removal/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockActOnReport).toHaveBeenCalledWith(1, "remove");
    });
  });

  it("handles unavailable feature gracefully within AdminShell", async () => {
    mockListReports.mockRejectedValue(new SocialUnavailableError());

    render(<CommunityModerationPage />);

    await waitFor(() => {
      expect(screen.getByText(/Community platform is currently disabled/i)).toBeInTheDocument();
    });
  });
});
