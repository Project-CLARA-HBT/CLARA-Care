import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PhrDemoDefault, { PhrDemo } from "./phr-demo";
import { MotionProvider } from "../runtime/motion-provider";

describe("PhrDemo (Landing v7 Interactive Demo)", () => {
  it("exports both named and default PhrDemo", () => {
    expect(PhrDemo).toBeDefined();
    expect(PhrDemoDefault).toBeDefined();
    expect(PhrDemo).toBe(PhrDemoDefault);
  });

  it("renders editorial anchor statement and default permitted & blocked columns", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <PhrDemo />
      </MotionProvider>
    );

    // Editorial anchor check
    expect(
      screen.getByText(/“Chia sẻ một phần không có nghĩa là chia sẻ toàn bộ hồ sơ.”/i)
    ).toBeInTheDocument();

    // Patient and Packet metadata
    expect(screen.getByText("Gói chia sẻ cho Bác sĩ Tim mạch")).toBeInTheDocument();
    expect(screen.getByText("Nguyễn Văn An")).toBeInTheDocument();
    expect(screen.getByText("MRN-8842-VN")).toBeInTheDocument();

    // Columns
    expect(screen.getByTestId("phr-permitted-column")).toBeInTheDocument();
    expect(screen.getByTestId("phr-blocked-column")).toBeInTheDocument();

    // Allowed Fields
    expect(screen.getByText("Tiền sử Dị ứng")).toBeInTheDocument();
    expect(screen.getByText("Danh mục Thuốc đang dùng")).toBeInTheDocument();
    expect(screen.getByText("Chỉ số Huyết áp & Đường huyết")).toBeInTheDocument();

    // Blocked Fields
    expect(screen.getByText("Ghi chú & Nhật ký Riêng tư")).toBeInTheDocument();
    expect(screen.getByText("Thông tin Bảo hiểm & Viện phí")).toBeInTheDocument();

    // Embedded PermissionGate artwork
    expect(screen.getByTestId("permission-gate")).toBeInTheDocument();
  });

  it("toggles revocation state on Revoke button click", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <PhrDemo />
      </MotionProvider>
    );

    const revokeBtn = screen.getByTestId("phr-revoke-btn");
    expect(revokeBtn).toHaveTextContent("Thu hồi quyền ngay lập tức");

    const gate = screen.getByTestId("permission-gate");
    expect(gate).toHaveAttribute("data-revoked", "false");

    // Click to revoke
    fireEvent.click(revokeBtn);

    expect(revokeBtn).toHaveTextContent("Khôi phục gói chia sẻ");
    expect(gate).toHaveAttribute("data-revoked", "true");
    expect(screen.getAllByText("Đã thu hồi quyền").length).toBeGreaterThan(0);

    // Click again to restore
    fireEvent.click(revokeBtn);
    expect(revokeBtn).toHaveTextContent("Thu hồi quyền ngay lập tức");
    expect(gate).toHaveAttribute("data-revoked", "false");
  });

  it("renders correctly in English when language is 'en'", () => {
    render(
      <MotionProvider initialLanguage="en">
        <PhrDemo />
      </MotionProvider>
    );

    expect(
      screen.getByText(/“Sharing a portion of your health data never means exposing your entire record.”/i)
    ).toBeInTheDocument();

    expect(screen.getByText("Cardiology Consultation Share Packet")).toBeInTheDocument();
    expect(screen.getByText("Nguyen Van An")).toBeInTheDocument();
    expect(screen.getByText("Allergy History")).toBeInTheDocument();
    expect(screen.getByText("Private Personal Notes")).toBeInTheDocument();

    const revokeBtn = screen.getByTestId("phr-revoke-btn");
    expect(revokeBtn).toHaveTextContent("Revoke Access Immediately");
  });
});
