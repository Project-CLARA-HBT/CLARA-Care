/**
 * Client-side multi-tenant organization and workspace context boundary.
 *
 * Provides safe tenant context isolation, local storage persistence for the
 * active organization ID, and explicit client-side cache purging upon organization
 * switches to eliminate cross-tenant data contamination.
 *
 * Invariant: The active organization ID is only a client presentation hint;
 * the backend API Gateway independently enforces organization membership and
 * RBAC authorization on every protected route.
 */

export type OrganizationRole =
  | "owner"
  | "admin"
  | "clinician"
  | "member"
  | "viewer";

export type OrganizationTier =
  | "starter"
  | "standard"
  | "professional"
  | "enterprise"
  | "hospital";

export type OrganizationStatus =
  | "active"
  | "suspended"
  | "pending"
  | "deprovisioned";

export type TenantWorkspaceRole = "admin" | "contributor" | "viewer";

export interface TenantWorkspaceItem {
  id: string;
  org_id: string;
  name: string;
  slug: string;
  description?: string | null;
  is_restricted?: boolean;
  is_archived?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface OrganizationMemberItem {
  id: string;
  org_id: string;
  user_id?: number | null;
  user_email: string;
  role: OrganizationRole;
  status: string;
  joined_at?: string | null;
  created_at?: string;
}

export interface OrganizationItem {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  tier: OrganizationTier | string;
  status: OrganizationStatus | string;
  contact_email?: string | null;
  member_count?: number;
  workspace_count?: number;
  user_role?: OrganizationRole | string;
  created_at?: string;
  updated_at?: string;
}

export interface OrganizationContextState {
  organizations: OrganizationItem[];
  active_organization_id: string | null;
  active_organization: OrganizationItem | null;
  cache_scope: string | null;
  reset_required: boolean;
}

export const ACTIVE_ORGANIZATION_STORAGE_KEY = "clara_active_org_id";
export const ORGANIZATION_CACHE_PREFIX = "clara_org_cache:";
export const TENANT_CACHE_PREFIX = "clara_tenant_cache:";
export const ORGANIZATION_CONTEXT_CHANGE_EVENT = "clara:organization-context-changed";

function browserStorage(): Storage[] {
  if (typeof window === "undefined") return [];
  return [window.sessionStorage, window.localStorage];
}

/**
 * Retrieve the active organization ID from browser localStorage.
 */
export function getActiveOrganizationId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(ACTIVE_ORGANIZATION_STORAGE_KEY)?.trim();
    return value || null;
  } catch {
    return null;
  }
}

/**
 * Purge tenant/organization-scoped client state from all storage levels.
 * Non-tenant session and global preferences (theme, language) are preserved.
 */
export function clearOrganizationScopedClientState(): void {
  for (const storage of browserStorage()) {
    try {
      const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index));
      for (const key of keys) {
        if (
          key?.startsWith(ORGANIZATION_CACHE_PREFIX) ||
          key?.startsWith(TENANT_CACHE_PREFIX)
        ) {
          storage.removeItem(key);
        }
      }
    } catch {
      // Storage might be unavailable in restricted environments
    }
  }
}

/**
 * Switch the active organization context.
 * Purges organization-scoped caches and dispatches a cross-component change event.
 */
export function setActiveOrganizationId(orgId: string | null): void {
  if (typeof window === "undefined") return;
  const next = orgId?.trim() || null;
  const previous = getActiveOrganizationId();
  if (previous === next) return;

  // Enforce zero cross-tenant contamination
  clearOrganizationScopedClientState();

  try {
    if (next) {
      window.localStorage.setItem(ACTIVE_ORGANIZATION_STORAGE_KEY, next);
    } else {
      window.localStorage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
    }
  } catch {
    // Current page still dispatches context event
  }

  window.dispatchEvent(
    new CustomEvent(ORGANIZATION_CONTEXT_CHANGE_EVENT, {
      detail: { previous, next },
    }),
  );
}

/**
 * Clear the active organization context and remove all tenant caches.
 */
export function clearActiveOrganizationContext(): void {
  clearOrganizationScopedClientState();
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
  } catch {
    // noop
  }
}
