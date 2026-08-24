import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PermissionGateDefault, {
  PermissionGate,
  type PermissionGateProps,
} from "./permission-gate";

describe("PermissionGate Artwork Component (Landing v7)", () => {
  it("exports both named and default PermissionGate", () => {
    expect(PermissionGate).toBeDefined();
    expect(PermissionGateDefault).toBeDefined();
    expect(PermissionGate).toBe(PermissionGateDefault);
  });

  it("renders with default props correctly", () => {
    render(<PermissionGate />);
    const root = screen.getByTestId("permission-gate");
    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute("data-artwork", "permission-gate");
    expect(root).toHaveAttribute("data-revoked", "false");
    expect(root).toHaveAttribute("data-allowed-count", "3");
    expect(root).toHaveAttribute("data-blocked-count", "2");

    expect(screen.getByText("Zero-CoT Permission Gate")).toBeInTheDocument();
    expect(screen.getByText("AES-256 GCM")).toBeInTheDocument();
    expect(screen.getByText("Thời hạn token: 24 giờ")).toBeInTheDocument();
    expect(screen.getByText(/3 Luồng Cấp phép đi qua/i)).toBeInTheDocument();
    expect(screen.getByText(/2 Trường Nhạy cảm Bị chặn/i)).toBeInTheDocument();
  });

  it("accepts custom props: isRevoked, allowedCount, blockedCount, expiryText, className", () => {
    const props: PermissionGateProps = {
      isRevoked: true,
      allowedCount: 5,
      blockedCount: 4,
      expiryText: "48 giờ",
      className: "custom-gate-class",
    };

    const { container } = render(<PermissionGate {...props} />);
    const root = screen.getByTestId("permission-gate");
    expect(root.className).toContain("custom-gate-class");
    expect(root).toHaveAttribute("data-revoked", "true");
    expect(root).toHaveAttribute("data-allowed-count", "5");
    expect(root).toHaveAttribute("data-blocked-count", "4");

    expect(screen.getByText("Đã ngắt quyền truy cập")).toBeInTheDocument();
    expect(screen.getByText(/5 Luồng Cấp phép đi qua/i)).toBeInTheDocument();
    expect(screen.getByText(/4 Trường Nhạy cảm Bị chặn/i)).toBeInTheDocument();

    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.querySelector("#dest-revoked-state")).toBeInTheDocument();
  });

  it("contains SVG flow paths for allowed green and blocked red streams", () => {
    const { container } = render(<PermissionGate isRevoked={false} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();

    expect(svg?.querySelector("#allowed-flow-streams")).toBeInTheDocument();
    expect(svg?.querySelector("#blocked-flow-streams")).toBeInTheDocument();
    expect(svg?.querySelector("#permission-boundary-gate")).toBeInTheDocument();
    expect(svg?.querySelector("#origin-vault-compartment")).toBeInTheDocument();
    expect(svg?.querySelector("#destination-enclave-compartment")).toBeInTheDocument();
  });
});
