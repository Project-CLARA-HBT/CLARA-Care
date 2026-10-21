import { describe, expect, it, vi } from "vitest";
import api from "./http-client";
import {
  createOrganization,
  createOrganizationWorkspace,
  deprovisionOrganization,
  getOrganization,
  inviteOrganizationMember,
  listOrganizationMembers,
  listOrganizations,
  listOrganizationWorkspaces,
  removeOrganizationMember,
  updateOrganization,
} from "./organization-api";

vi.mock("./http-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe("organization-api client", () => {
  it("listOrganizations fetches organization list", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: {
        items: [
          { id: "org_1", name: "Bệnh viện Bạch Mai", slug: "bach-mai", tier: "hospital", status: "active" },
        ],
        total: 1,
      },
    });

    const res = await listOrganizations();
    expect(mockApi.get).toHaveBeenCalledWith("/organizations");
    expect(res).toHaveLength(1);
    expect(res[0].name).toBe("Bệnh viện Bạch Mai");
  });

  it("getOrganization fetches single organization by ID", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { id: "org_1", name: "Bệnh viện Bạch Mai", tier: "hospital" },
    });

    const res = await getOrganization("org_1");
    expect(mockApi.get).toHaveBeenCalledWith("/organizations/org_1");
    expect(res.id).toBe("org_1");
  });

  it("createOrganization provisions a new organization", async () => {
    mockApi.post.mockResolvedValueOnce({
      data: { id: "org_2", name: "Phòng khám Quốc tế", slug: "pk-quocte", tier: "standard" },
    });

    const res = await createOrganization({
      name: "Phòng khám Quốc tế",
      tier: "standard",
    });
    expect(mockApi.post).toHaveBeenCalledWith("/organizations", {
      name: "Phòng khám Quốc tế",
      tier: "standard",
    });
    expect(res.id).toBe("org_2");
  });

  it("updateOrganization patches organization settings", async () => {
    mockApi.patch.mockResolvedValueOnce({
      data: { id: "org_1", name: "Bệnh viện Bạch Mai - Khu Mới" },
    });

    const res = await updateOrganization("org_1", { name: "Bệnh viện Bạch Mai - Khu Mới" });
    expect(mockApi.patch).toHaveBeenCalledWith("/organizations/org_1", {
      name: "Bệnh viện Bạch Mai - Khu Mới",
    });
    expect(res.name).toBe("Bệnh viện Bạch Mai - Khu Mới");
  });

  it("deprovisionOrganization deletes organization", async () => {
    mockApi.delete.mockResolvedValueOnce({ data: { status: "deprovisioned" } });
    await deprovisionOrganization("org_1");
    expect(mockApi.delete).toHaveBeenCalledWith("/organizations/org_1");
  });

  it("listOrganizationMembers fetches members", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: {
        items: [{ id: "mem_1", user_email: "doc@care.vn", role: "clinician", status: "active" }],
        total: 1,
      },
    });

    const res = await listOrganizationMembers("org_1");
    expect(mockApi.get).toHaveBeenCalledWith("/organizations/org_1/members");
    expect(res[0].user_email).toBe("doc@care.vn");
  });

  it("inviteOrganizationMember sends invite", async () => {
    mockApi.post.mockResolvedValueOnce({
      data: { id: "mem_2", user_email: "nurse@care.vn", role: "member", status: "pending" },
    });

    const res = await inviteOrganizationMember("org_1", {
      user_email: "nurse@care.vn",
      role: "member",
    });
    expect(mockApi.post).toHaveBeenCalledWith("/organizations/org_1/members", {
      user_email: "nurse@care.vn",
      role: "member",
    });
    expect(res.user_email).toBe("nurse@care.vn");
  });

  it("removeOrganizationMember removes member", async () => {
    mockApi.delete.mockResolvedValueOnce({ data: { status: "removed" } });
    await removeOrganizationMember("org_1", "doc@care.vn");
    expect(mockApi.delete).toHaveBeenCalledWith("/organizations/org_1/members/doc%40care.vn");
  });

  it("listOrganizationWorkspaces fetches collaborative workspaces", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: {
        items: [{ id: "ws_1", org_id: "org_1", name: "Khoa Tim mạch", slug: "cardiology" }],
        total: 1,
      },
    });

    const res = await listOrganizationWorkspaces("org_1");
    expect(mockApi.get).toHaveBeenCalledWith("/organizations/org_1/workspaces");
    expect(res[0].name).toBe("Khoa Tim mạch");
  });

  it("createOrganizationWorkspace creates a workspace", async () => {
    mockApi.post.mockResolvedValueOnce({
      data: { id: "ws_2", org_id: "org_1", name: "Khoa Cấp cứu", slug: "er" },
    });

    const res = await createOrganizationWorkspace("org_1", {
      name: "Khoa Cấp cứu",
      slug: "er",
    });
    expect(mockApi.post).toHaveBeenCalledWith("/organizations/org_1/workspaces", {
      name: "Khoa Cấp cứu",
      slug: "er",
    });
    expect(res.name).toBe("Khoa Cấp cứu");
  });
});
