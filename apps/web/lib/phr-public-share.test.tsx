import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({
  default: { get: mocks.get },
}));

import SharedPhrClient from "@/app/phr/shared/[token]/shared-phr-client";
import { getPublicPhrShare } from "@/lib/phr";

afterEach(cleanup);

describe("public PHR share client", () => {
  it("encodes the opaque capability token in the public read-only request", async () => {
    mocks.get.mockResolvedValueOnce({ data: { scope: "full", record: {} } });

    await expect(getPublicPhrShare("opaque/token")).resolves.toEqual({
      scope: "full",
      record: {},
    });
    expect(mocks.get).toHaveBeenCalledWith("/api/v1/phr/shared/opaque%2Ftoken");
  });

  it("renders shared emergency card packet securely without leaking extra PII", async () => {
    mocks.get.mockResolvedValueOnce({
      data: {
        scope: "emergency_card",
        emergency_card: {
          blood_type: "AB+",
          emergency_contact: { name: "Nguyễn Văn H", phone: "0909123456" },
          allergies: [{ name: "Penicillin", severity: "severe", reaction: "Phù mạch" }],
          conditions: [{ name: "Hen suyễn", status: "active" }],
          current_medications: [{ name: "Ventolin", dose: "1 nhát xịt khi khó thở" }],
        },
      },
    });

    render(<SharedPhrClient token="safe-emergency-token" />);

    expect(screen.getByText("Đang mở nội dung được chia sẻ...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Thẻ khẩn cấp được chia sẻ")).toBeInTheDocument();
    });

    expect(screen.getByText("Penicillin (nặng • Phù mạch)")).toBeInTheDocument();
    expect(screen.getByText("Hen suyễn (đang theo dõi)")).toBeInTheDocument();
    expect(screen.getByText("Ventolin (1 nhát xịt khi khó thở)")).toBeInTheDocument();
    expect(screen.getByText("Nhóm máu: AB+")).toBeInTheDocument();
    expect(screen.getByText("Nguyễn Văn H • Số điện thoại khẩn cấp: 0909123456")).toBeInTheDocument();
  });

  it("renders shared full health record packet securely with observations", async () => {
    mocks.get.mockResolvedValueOnce({
      data: {
        scope: "full",
        record: {
          profile: {
            full_name: "Lê Thị Mai",
            date_of_birth: "1985-04-12",
            gender: "female",
            blood_type: "O",
          },
          allergies: [{ name: "Aspirin", severity: "mild", reaction: "Mày đay" }],
          conditions: [{ name: "Tăng huyết áp", status: "active" }],
          medications: [{ name: "Amlodipine 5mg", dose: "1 viên", frequency: "1 lần/ngày" }],
          observations: [
            { name: "Huyết áp & Nhịp tim", value: "120/80", unit: "mmHg", observed_on: "2026-08-20" },
          ],
        },
      },
    });

    render(<SharedPhrClient token="full-packet-token" />);

    await waitFor(() => {
      expect(screen.getByText("Hồ sơ sức khỏe được chia sẻ")).toBeInTheDocument();
    });

    expect(screen.getByText("Họ và tên: Lê Thị Mai")).toBeInTheDocument();
    expect(screen.getByText("Aspirin (nhẹ • Mày đay)")).toBeInTheDocument();
    expect(screen.getByText("Tăng huyết áp (đang theo dõi)")).toBeInTheDocument();
    expect(screen.getByText("Amlodipine 5mg (1 viên • 1 lần/ngày)")).toBeInTheDocument();
    expect(screen.getByText("Huyết áp & Nhịp tim (120/80 • mmHg • 2026-08-20)")).toBeInTheDocument();
  });

  it("renders graceful unavailable message when share link is revoked or invalid", async () => {
    mocks.get.mockRejectedValueOnce(new Error("404 Not Found"));

    render(<SharedPhrClient token="invalid-token" />);

    await waitFor(() => {
      expect(screen.getByText("Liên kết chia sẻ không hợp lệ, đã hết hạn hoặc đã bị thu hồi.")).toBeInTheDocument();
    });
  });
});
