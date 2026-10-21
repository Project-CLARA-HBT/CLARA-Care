import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { OrganizationLinkBadge } from "./organization-link-badge";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

describe("OrganizationLinkBadge", () => {
  it("renders pill variant with organization name", () => {
    render(
      <OrganizationLinkBadge
        organizationName="Bệnh viện Bạch Mai"
        variant="pill"
      />,
    );

    expect(screen.getByTestId("org-link-badge-pill")).toBeInTheDocument();
    expect(screen.getByText("Bệnh viện Bạch Mai")).toBeInTheDocument();
  });

  it("renders compact variant with hospital tier badge and EMR indicator", () => {
    render(
      <OrganizationLinkBadge
        organizationName="Bệnh viện Chợ Rẫy"
        clinicTier="hospital"
        isEmrLinked={true}
        variant="compact"
      />,
    );

    expect(screen.getByTestId("org-link-badge-compact")).toBeInTheDocument();
    expect(screen.getByText("Bệnh viện Chợ Rẫy")).toBeInTheDocument();
    expect(screen.getByText("Bệnh viện")).toBeInTheDocument();
    expect(screen.getByText("EMR")).toBeInTheDocument();
  });

  it("renders full variant with department, clinician name, and CCHN code", () => {
    render(
      <OrganizationLinkBadge
        organizationName="Phòng khám Quốc tế"
        departmentName="Khoa Tim mạch"
        doctorName="BSCKII. Lê Hoàng Long"
        doctorCchn="Mã CCHN: 014829/HCM-CCHN"
        clinicTier="clinic"
        isTransfer={true}
        variant="full"
      />,
    );

    expect(screen.getByTestId("org-link-badge-full")).toBeInTheDocument();
    expect(screen.getByText("Phòng khám Quốc tế")).toBeInTheDocument();
    expect(screen.getByText("Khoa Tim mạch")).toBeInTheDocument();
    expect(screen.getByText(/BSCKII. Lê Hoàng Long/)).toBeInTheDocument();
    expect(screen.getByText("Mã CCHN: 014829/HCM-CCHN")).toBeInTheDocument();
    expect(screen.getByText("Phòng khám")).toBeInTheDocument();
    expect(screen.getByText("Chuyển viện")).toBeInTheDocument();
  });
});
