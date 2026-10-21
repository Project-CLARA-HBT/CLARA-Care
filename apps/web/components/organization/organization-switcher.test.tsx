import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { OrganizationSwitcher } from "./organization-switcher";
import { OrganizationProvider } from "./organization-provider";
import * as organizationContext from "@/lib/organization-context";
import * as organizationApi from "@/lib/organization-api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/clinical/patients",
  useRouter: () => ({
    refresh: vi.fn(),
    push: vi.fn(),
  }),
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/components/shell/session-boundary", () => ({
  useSession: () => ({
    isSessionChecked: true,
    isAuthenticated: true,
    role: "doctor",
  }),
}));

describe("OrganizationSwitcher", () => {
  const sampleOrgs: organizationContext.OrganizationItem[] = [
    {
      id: "org_bach_mai",
      name: "Bệnh viện Bạch Mai",
      slug: "bach-mai",
      tier: "hospital",
      status: "active",
      user_role: "clinician",
      workspace_count: 5,
    },
    {
      id: "org_pk_quocte",
      name: "Phòng khám Quốc tế",
      slug: "pk-quocte",
      tier: "professional",
      status: "active",
      user_role: "admin",
      workspace_count: 2,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders empty fallback when user belongs to no organizations", async () => {
    vi.spyOn(organizationApi, "listOrganizations").mockResolvedValue([]);

    await act(async () => {
      render(
        <OrganizationProvider initialOrganizations={[]} initialActiveOrgId={null}>
          <OrganizationSwitcher />
        </OrganizationProvider>,
      );
    });

    expect(screen.getByTestId("organization-switcher-empty")).toBeInTheDocument();
    expect(screen.getByText("Độc lập / Cá nhân")).toBeInTheDocument();
  });

  it("renders active organization name and tier badge", async () => {
    vi.spyOn(organizationApi, "listOrganizations").mockResolvedValue(sampleOrgs);

    await act(async () => {
      render(
        <OrganizationProvider
          initialOrganizations={sampleOrgs}
          initialActiveOrgId="org_bach_mai"
        >
          <OrganizationSwitcher />
        </OrganizationProvider>,
      );
    });

    expect(screen.getByTestId("organization-switcher")).toBeInTheDocument();
    expect(screen.getByText("Bệnh viện Bạch Mai")).toBeInTheDocument();
    expect(screen.getByText("Bệnh viện")).toBeInTheDocument();
  });

  it("opens menu and allows switching between organizations", async () => {
    vi.spyOn(organizationApi, "listOrganizations").mockResolvedValue(sampleOrgs);
    const changeHandler = vi.fn();

    await act(async () => {
      render(
        <OrganizationProvider
          initialOrganizations={sampleOrgs}
          initialActiveOrgId="org_bach_mai"
        >
          <OrganizationSwitcher onOrganizationChange={changeHandler} />
        </OrganizationProvider>,
      );
    });

    const trigger = screen.getByTestId("organization-switcher-trigger");
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    // Open dropdown
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("organization-switcher-menu")).toBeInTheDocument();

    // Verify list items
    const pkItem = screen.getByTestId("org-item-org_pk_quocte");
    expect(pkItem).toBeInTheDocument();
    expect(screen.getByText("Phòng khám Quốc tế")).toBeInTheDocument();

    // Select second organization
    await act(async () => {
      fireEvent.click(pkItem);
    });

    expect(changeHandler).toHaveBeenCalledWith("org_pk_quocte");
    expect(screen.queryByTestId("organization-switcher-menu")).not.toBeInTheDocument();
  });

  it("closes dropdown on Escape key", async () => {
    vi.spyOn(organizationApi, "listOrganizations").mockResolvedValue(sampleOrgs);

    await act(async () => {
      render(
        <OrganizationProvider
          initialOrganizations={sampleOrgs}
          initialActiveOrgId="org_bach_mai"
        >
          <OrganizationSwitcher />
        </OrganizationProvider>,
      );
    });

    const trigger = screen.getByTestId("organization-switcher-trigger");
    fireEvent.click(trigger);
    expect(screen.getByTestId("organization-switcher-menu")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("organization-switcher-menu")).not.toBeInTheDocument();
  });
});
