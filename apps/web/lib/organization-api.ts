import api from "@/lib/http-client";
import type {
  OrganizationItem,
  OrganizationMemberItem,
  TenantWorkspaceItem,
} from "./organization-context";

export interface OrganizationListResponse {
  items: OrganizationItem[];
  total: number;
}

export interface OrganizationMemberListResponse {
  items: OrganizationMemberItem[];
  total: number;
}

export interface TenantWorkspaceListResponse {
  items: TenantWorkspaceItem[];
  total: number;
}

export interface OrganizationCreatePayload {
  name: string;
  slug?: string;
  description?: string;
  tier?: string;
  contact_email?: string;
  settings?: Record<string, unknown>;
}

export interface OrganizationUpdatePayload {
  name?: string;
  description?: string;
  tier?: string;
  status?: string;
  contact_email?: string;
  settings?: Record<string, unknown>;
}

export interface OrganizationMemberInvitePayload {
  user_email: string;
  role: string;
}

export interface TenantWorkspaceCreatePayload {
  name: string;
  slug?: string;
  description?: string;
  is_restricted?: boolean;
}

/**
 * Fetch all organizations accessible to the current authenticated actor.
 */
export async function listOrganizations(): Promise<OrganizationItem[]> {
  const res = await api.get<OrganizationListResponse>("/organizations");
  return res.data?.items ?? [];
}

/**
 * Get organization metadata by ID.
 */
export async function getOrganization(orgId: string): Promise<OrganizationItem> {
  const res = await api.get<OrganizationItem>(`/organizations/${encodeURIComponent(orgId)}`);
  return res.data;
}

/**
 * Provision a new organization.
 */
export async function createOrganization(
  payload: OrganizationCreatePayload,
): Promise<OrganizationItem> {
  const res = await api.post<OrganizationItem>("/organizations", payload);
  return res.data;
}

/**
 * Update organization settings or profile.
 */
export async function updateOrganization(
  orgId: string,
  payload: OrganizationUpdatePayload,
): Promise<OrganizationItem> {
  const res = await api.patch<OrganizationItem>(
    `/organizations/${encodeURIComponent(orgId)}`,
    payload,
  );
  return res.data;
}

/**
 * Deprovision an organization.
 */
export async function deprovisionOrganization(orgId: string): Promise<void> {
  await api.delete(`/organizations/${encodeURIComponent(orgId)}`);
}

/**
 * List active members for an organization.
 */
export async function listOrganizationMembers(
  orgId: string,
): Promise<OrganizationMemberItem[]> {
  const res = await api.get<OrganizationMemberListResponse>(
    `/organizations/${encodeURIComponent(orgId)}/members`,
  );
  return res.data?.items ?? [];
}

/**
 * Invite a new member to an organization.
 */
export async function inviteOrganizationMember(
  orgId: string,
  payload: OrganizationMemberInvitePayload,
): Promise<OrganizationMemberItem> {
  const res = await api.post<OrganizationMemberItem>(
    `/organizations/${encodeURIComponent(orgId)}/members`,
    payload,
  );
  return res.data;
}

/**
 * Remove a member from an organization.
 */
export async function removeOrganizationMember(
  orgId: string,
  userEmail: string,
): Promise<void> {
  await api.delete(
    `/organizations/${encodeURIComponent(orgId)}/members/${encodeURIComponent(userEmail)}`,
  );
}

/**
 * List collaborative workspaces within an organization.
 */
export async function listOrganizationWorkspaces(
  orgId: string,
): Promise<TenantWorkspaceItem[]> {
  const res = await api.get<TenantWorkspaceListResponse>(
    `/organizations/${encodeURIComponent(orgId)}/workspaces`,
  );
  return res.data?.items ?? [];
}

/**
 * Create a new collaborative workspace inside an organization.
 */
export async function createOrganizationWorkspace(
  orgId: string,
  payload: TenantWorkspaceCreatePayload,
): Promise<TenantWorkspaceItem> {
  const res = await api.post<TenantWorkspaceItem>(
    `/organizations/${encodeURIComponent(orgId)}/workspaces`,
    payload,
  );
  return res.data;
}
