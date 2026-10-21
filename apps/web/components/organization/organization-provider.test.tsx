import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  OrganizationProvider,
  useOrganization,
} from "./organization-provider";
import * as organizationApi from "@/lib/organization-api";
import * as organizationContext from "@/lib/organization-context";

const mockRefresh = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/clinical/patients",
  useRouter: () => ({
    refresh: mockRefresh,
    push: vi.fn(),
  }),
}));

vi.mock("@/lib/navigation.config", () => ({
  isPublicRoute: () => false,
}));

vi.mock("@/components/shell/session-boundary", () => ({
  useSession: () => ({
    isSessionChecked: true,
    isAuthenticated: true,
    role: "doctor",
  }),
}));

function ConsumerComponent() {
  const {
    organizations,
    activeOrganization,
    activeOrganizationId,
    switchOrganization,
    isLoading,
  } = useOrganization();

  return (
    <div>
      <div data-testid="loading-state">{isLoading ? "loading" : "idle"}</div>
      <div data-testid="active-org-id">{activeOrganizationId ?? "none"}</div>
      <div data-testid="active-org-name">{activeOrganization?.name ?? "none"}</div>
      <div data-testid="org-count">{organizations.length}</div>
      {organizations.map((org) => (
        <button
          key={org.id}
          data-testid={`switch-${org.id}`}
          onClick={() => void switchOrganization(org.id)}
        >
          {org.name}
        </button>
      ))}
    </div>
  );
}

describe("OrganizationProvider", () => {
  const sampleOrgs: organizationContext.OrganizationItem[] = [
    {
      id: "org_bach_mai",
      name: "Bệnh viện Bạch Mai",
      slug: "bach-mai",
      tier: "hospital",
      status: "active",
    },
    {
      id: "org_pk_quocte",
      name: "Phòng khám Đa khoa Quốc tế",
      slug: "pk-quocte",
      tier: "standard",
      status: "active",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("throws error when useOrganization is used outside provider", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<ConsumerComponent />)).toThrow(
      "useOrganization must be used within an OrganizationProvider",
    );
    consoleError.mockRestore();
  });

  it("loads organizations and initializes first organization as active", async () => {
    vi.spyOn(organizationApi, "listOrganizations").mockResolvedValueOnce(sampleOrgs);

    render(
      <OrganizationProvider>
        <ConsumerComponent />
      </OrganizationProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("active-org-id").textContent).toBe("org_bach_mai");
      expect(screen.getByTestId("active-org-name").textContent).toBe("Bệnh viện Bạch Mai");
      expect(screen.getByTestId("org-count").textContent).toBe("2");
    });
  });

  it("switches active organization and triggers router refresh", async () => {
    vi.spyOn(organizationApi, "listOrganizations").mockResolvedValueOnce(sampleOrgs);
    const clearCacheSpy = vi.spyOn(organizationContext, "clearOrganizationScopedClientState");

    render(
      <OrganizationProvider>
        <ConsumerComponent />
      </OrganizationProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("active-org-id").textContent).toBe("org_bach_mai");
    });

    const switchBtn = screen.getByTestId("switch-org_pk_quocte");
    await act(async () => {
      fireEvent.click(switchBtn);
    });

    expect(clearCacheSpy).toHaveBeenCalled();
    expect(mockRefresh).toHaveBeenCalled();
    expect(screen.getByTestId("active-org-id").textContent).toBe("org_pk_quocte");
    expect(screen.getByTestId("active-org-name").textContent).toBe("Phòng khám Đa khoa Quốc tế");
  });
});
