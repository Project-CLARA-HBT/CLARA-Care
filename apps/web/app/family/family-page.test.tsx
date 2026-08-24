import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FamilyPage from "./page";
import * as visitFamilyModule from "@/lib/visit-family";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/family",
  useSearchParams: () => new URLSearchParams(),
}));

describe("Family Sharing Hub (/family) - Spec v5 Section 6.22", () => {
  const mockGrants: visitFamilyModule.FamilyGrant[] = [
    {
      id: "grant-1",
      supporter_label: "Nguyễn Thị B",
      object_type: "medications",
      object_id: "obj-1",
      allowed_actions: ["view", "add_observation"],
      purpose: "care_coordination",
      expires_at: new Date(Date.now() + 20 * 24 * 60 * 60 * 1000).toISOString(),
      status: "active",
    },
    {
      id: "grant-2",
      supporter_label: "Bác sĩ Lê Văn C",
      object_type: "visit",
      object_id: "obj-2",
      allowed_actions: ["view"],
      purpose: "visit_support",
      expires_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
      status: "expired",
    },
    {
      id: "grant-3",
      supporter_label: "Phạm Văn D",
      object_type: "episode",
      object_id: "obj-3",
      allowed_actions: ["view"],
      purpose: "care_coordination",
      expires_at: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
      status: "revoked",
      revoked_at: new Date().toISOString(),
    },
  ];

  const mockRelationships: visitFamilyModule.FamilyGrant[] = [
    {
      id: "rel-1",
      supporter_label: "Trần Văn E",
      object_type: "care_task",
      object_id: "obj-4",
      allowed_actions: ["view", "complete_task"],
      purpose: "care_coordination",
      expires_at: new Date(Date.now() + 15 * 24 * 60 * 60 * 1000).toISOString(),
      status: "active",
    },
  ];

  const mockNotifications: visitFamilyModule.FamilyNotification[] = [
    {
      id: "notif-1",
      kind: "delegated_care_task",
      profile_id: "prof-1",
      task_id: "task-101",
      purpose: "care_coordination",
      expires_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
      action: "complete_task",
      message: "Nhắc uống thuốc hạ huyết áp sau ăn sáng",
    },
  ];

  const mockLogs: visitFamilyModule.FamilyAccessLog[] = [
    {
      id: "log-1",
      actor_label: "Nguyễn Thị B",
      actor_code: "supporter",
      object_type: "medications",
      object_id: "obj-1",
      action: "view",
      action_code: "view",
      outcome: "success",
      outcome_code: "allowed",
      purpose: "care_coordination",
      created_at: new Date(Date.now() - 3600 * 1000).toISOString(),
    },
    {
      id: "log-2",
      actor_label: "Bác sĩ Lê Văn C",
      actor_code: "supporter",
      object_type: "visit",
      object_id: "obj-2",
      action: "view",
      action_code: "view",
      outcome: "denied",
      outcome_code: "denied",
      purpose: "visit_support",
      created_at: new Date(Date.now() - 7200 * 1000).toISOString(),
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(visitFamilyModule, "listFamilyGrants").mockResolvedValue(mockGrants);
    vi.spyOn(visitFamilyModule, "listFamilyRelationships").mockResolvedValue(mockRelationships);
    vi.spyOn(visitFamilyModule, "listFamilyNotifications").mockResolvedValue(mockNotifications);
    vi.spyOn(visitFamilyModule, "listFamilyAccessLog").mockResolvedValue(mockLogs);
    vi.spyOn(visitFamilyModule, "revokeFamilyGrant").mockResolvedValue(undefined);
    vi.spyOn(visitFamilyModule, "renewFamilyGrant").mockResolvedValue({
      id: "grant-1",
      token: "tok-renew-xyz-789",
      expires_at: new Date().toISOString(),
    });
    vi.spyOn(visitFamilyModule, "acknowledgeFamilyNotification").mockResolvedValue(undefined);
  });

  afterEach(cleanup);

  it("renders layout section 1: Header with Invite & Accept CTAs", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("family-sharing-hub")).toBeInTheDocument();
    });

    // Check title and subtitle
    expect(screen.getByText("Vòng tròn gia đình")).toBeInTheDocument();

    // Check Primary CTA linking to /family/invite
    const inviteLinks = screen.getAllByRole("link", { name: /Mời người chăm sóc \/ Bác sĩ/i });
    expect(inviteLinks.length).toBeGreaterThan(0);
    expect(inviteLinks[0]).toHaveAttribute("href", "/family/invite");

    // Check Secondary CTA linking to /family/accept
    const acceptLink = screen.getByRole("link", { name: /Xem mã mời/i });
    expect(acceptLink).toHaveAttribute("href", "/family/accept");
  });

  it("renders layout section 2: Explicit Scope Disclosure Banner", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("scope-disclosure-banner")).toBeInTheDocument();
    });

    expect(screen.getByText("Bảo vệ quyền riêng tư & Minh bạch phạm vi chia sẻ")).toBeInTheDocument();
    expect(screen.getByText("Phân quyền tường minh")).toBeInTheDocument();
    expect(screen.getByText("Bảo mật suy luận AI")).toBeInTheDocument();
    expect(screen.getByText("Thu hồi tức thì 1 chạm")).toBeInTheDocument();
    expect(screen.getByText("Nhật ký kiểm toán")).toBeInTheDocument();
  });

  it("renders layout section 3: Active sharing grants list rows with Who, Scope, Permission, Purpose, Expiry countdown, and Revoke button", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("grants-list")).toBeInTheDocument();
    });

    // Grant 1 details
    expect(screen.getByText("Nguyễn Thị B")).toBeInTheDocument();
    expect(screen.getByText("Đơn thuốc & Tủ thuốc")).toBeInTheDocument();
    expect(screen.getAllByText(/Phối hợp chăm sóc/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("xem").length).toBeGreaterThan(0);
    expect(screen.getByText("thêm ghi nhận")).toBeInTheDocument();
    expect(screen.getByTestId("revoke-grant-btn-grant-1")).toBeInTheDocument();
    expect(screen.getByTestId("renew-grant-btn-grant-1")).toBeInTheDocument();

    // Filter pills
    expect(screen.getByTestId("filter-all")).toBeInTheDocument();
    expect(screen.getByTestId("filter-active")).toBeInTheDocument();
    expect(screen.getByTestId("filter-expired")).toBeInTheDocument();
    expect(screen.getByTestId("filter-revoked")).toBeInTheDocument();

    // Filter to active only
    fireEvent.click(screen.getByTestId("filter-active"));
    expect(screen.getByText("Nguyễn Thị B")).toBeInTheDocument();
    expect(screen.queryByText("Bác sĩ Lê Văn C")).not.toBeInTheDocument();
  });

  it("handles immediate revocation flow via confirmation dialog", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("revoke-grant-btn-grant-1")).toBeInTheDocument();
    });

    // Click revoke button
    fireEvent.click(screen.getByTestId("revoke-grant-btn-grant-1"));

    // Check dialog opens
    expect(screen.getByTestId("revoke-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByText("Thu hồi quyền chia sẻ?")).toBeInTheDocument();
    expect(screen.getByText(/Bạn có chắc chắn muốn thu hồi quyền của Nguyễn Thị B/i)).toBeInTheDocument();

    // Confirm revoke
    fireEvent.click(screen.getByTestId("confirm-revoke-btn"));

    await waitFor(() => {
      expect(visitFamilyModule.revokeFamilyGrant).toHaveBeenCalledWith("grant-1");
    });
  });

  it("handles grant renewal and shows created token notice", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("renew-grant-btn-grant-1")).toBeInTheDocument();
    });

    // Click renew button
    fireEvent.click(screen.getByTestId("renew-grant-btn-grant-1"));

    await waitFor(() => {
      expect(visitFamilyModule.renewFamilyGrant).toHaveBeenCalledWith("grant-1", expect.any(String));
      expect(screen.getByTestId("grant-created-notice")).toBeInTheDocument();
      expect(screen.getByText("tok-renew-xyz-789")).toBeInTheDocument();
    });
  });

  it("renders layout section 4: Delegated tasks from family members in received tab", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("family-sharing-hub")).toBeInTheDocument();
    });

    // Switch to 'received' tab
    const receivedTabBtn = screen.getByRole("tab", { name: /Được chia sẻ với tôi/i });
    fireEvent.click(receivedTabBtn);

    expect(screen.getByTestId("delegated-tasks-section")).toBeInTheDocument();
    expect(screen.getByText("Nhắc uống thuốc hạ huyết áp sau ăn sáng")).toBeInTheDocument();
    expect(screen.getByTestId("acknowledge-task-btn-notif-1")).toBeInTheDocument();

    // Acknowledge task
    fireEvent.click(screen.getByTestId("acknowledge-task-btn-notif-1"));

    await waitFor(() => {
      expect(visitFamilyModule.acknowledgeFamilyNotification).toHaveBeenCalledWith(
        "notif-1",
        "task-101",
        "care_coordination",
      );
    });

    // Check received relationships section
    expect(screen.getByTestId("received-relationships-section")).toBeInTheDocument();
    expect(screen.getByText("Trần Văn E")).toBeInTheDocument();
  });

  it("renders layout section 5: Access audit log history in log tab", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("family-sharing-hub")).toBeInTheDocument();
    });

    // Switch to 'log' tab
    const logTabBtn = screen.getByRole("tab", { name: /Nhật ký truy cập/i });
    fireEvent.click(logTabBtn);

    expect(screen.getByTestId("access-history-section")).toBeInTheDocument();
    expect(screen.getByTestId("access-logs-table")).toBeInTheDocument();
    expect(screen.getByText("được cho phép")).toBeInTheDocument();
    expect(screen.getByText("bị từ chối")).toBeInTheDocument();
  });

  it("renders empty state when no grants are shared", async () => {
    vi.spyOn(visitFamilyModule, "listFamilyGrants").mockResolvedValue([]);
    vi.spyOn(visitFamilyModule, "listFamilyRelationships").mockResolvedValue([]);
    vi.spyOn(visitFamilyModule, "listFamilyNotifications").mockResolvedValue([]);
    vi.spyOn(visitFamilyModule, "listFamilyAccessLog").mockResolvedValue([]);

    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByText("Bạn chưa chia sẻ dữ liệu nào")).toBeInTheDocument();
    });
  });
});
