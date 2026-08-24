import {
  ALL_ADMIN_PREVIEW_PERSONAS,
  ALL_WORKSPACES,
  WORKSPACE_CHANGE_EVENT,
  WORKSPACE_COOKIE_NAME,
  WORKSPACE_STORAGE_KEY,
  type AdminPreviewPersona,
  type UserRole,
  type WorkspaceId,
} from "./workspace.contract";

export const ROLE_PERMITTED_WORKSPACES: Record<UserRole, WorkspaceId[]> = {
  normal: ["personal"],
  doctor: ["clinical", "personal"],
  researcher: ["research", "personal"],
  admin: ["admin", "clinical", "research", "personal"],
};

export const ROLE_DEFAULT_WORKSPACES: Record<UserRole, WorkspaceId> = {
  normal: "personal",
  doctor: "clinical",
  researcher: "research",
  admin: "admin",
};

export const WORKSPACE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30; // 30 days

/**
 * Pure role -> permitted workspaces derivation.
 */
export function getPermittedWorkspaces(role?: UserRole | null): WorkspaceId[] {
  if (!role || !ROLE_PERMITTED_WORKSPACES[role]) {
    return ["personal"];
  }
  return [...ROLE_PERMITTED_WORKSPACES[role]];
}

export const derivePermittedWorkspaces = getPermittedWorkspaces;

/**
 * Derives default workspace for a role.
 */
export function getDefaultWorkspace(role?: UserRole | null): WorkspaceId {
  if (!role || !ROLE_DEFAULT_WORKSPACES[role]) {
    return "personal";
  }
  return ROLE_DEFAULT_WORKSPACES[role];
}

export const getDefaultWorkspaceForRole = getDefaultWorkspace;

/**
 * Type guard for WorkspaceId.
 */
export function isValidWorkspace(value: unknown): value is WorkspaceId {
  return (
    typeof value === "string" && ALL_WORKSPACES.includes(value as WorkspaceId)
  );
}

/**
 * Type guard for AdminPreviewPersona.
 */
export function isValidAdminPreviewPersona(
  value: unknown,
): value is AdminPreviewPersona {
  return (
    typeof value === "string" &&
    ALL_ADMIN_PREVIEW_PERSONAS.includes(value as AdminPreviewPersona)
  );
}

/**
 * Determines canonical workspace from route pathname.
 */
export function getCanonicalWorkspaceForPath(
  pathname?: string | null,
): WorkspaceId | null {
  if (!pathname) return null;
  const clean = pathname.split("?")[0].split("#")[0].trim();
  if (!clean || clean === "/") return null;

  if (
    clean === "/dashboard/control-tower" ||
    clean === "/dashboard/ecosystem" ||
    clean.startsWith("/admin")
  ) {
    return "admin";
  }

  if (
    clean.startsWith("/council") ||
    clean.startsWith("/scribe") ||
    clean.startsWith("/clinical")
  ) {
    return "clinical";
  }

  if (
    clean.startsWith("/evidence") ||
    clean.startsWith("/research/source-hub")
  ) {
    return "research";
  }

  if (
    clean.startsWith("/today") ||
    clean.startsWith("/lifemap") ||
    clean.startsWith("/visits") ||
    clean.startsWith("/family") ||
    clean.startsWith("/medicines") ||
    clean.startsWith("/phr") ||
    clean.startsWith("/selfmed") ||
    clean.startsWith("/careguard") ||
    clean.startsWith("/you") ||
    clean.startsWith("/health") ||
    clean.startsWith("/care") ||
    clean === "/home" ||
    clean === "/ask" ||
    clean === "/community" ||
    clean === "/chat/shares" ||
    clean.startsWith("/account/")
  ) {
    return "personal";
  }

  return null;
}

/**
 * Checks if a route is neutral/shared across multiple workspaces.
 */
export function isNeutralRoute(pathname?: string | null): boolean {
  if (!pathname) return true;
  const clean = pathname.split("?")[0].split("#")[0].trim();
  return (
    clean === "" ||
    clean === "/" ||
    clean === "/dashboard" ||
    clean === "/chat" ||
    (clean.startsWith("/chat/") && clean !== "/chat/shares") ||
    clean === "/huong-dan" ||
    clean.startsWith("/welcome") ||
    clean.startsWith("/onboarding") ||
    clean === "/role-select"
  );
}

export interface ReconcileWorkspaceOptions {
  pathname?: string | null;
  serverRole?: UserRole | null;
  currentWorkspace?: WorkspaceId | null;
  permittedWorkspaces?: WorkspaceId[];
}

/**
 * Reconciles active workspace given pathname, role, and current workspace.
 */
export function reconcileWorkspaceWithRoute(
  options: ReconcileWorkspaceOptions,
): WorkspaceId {
  const role = options.serverRole ?? "normal";
  const permitted = options.permittedWorkspaces ?? getPermittedWorkspaces(role);
  const current = options.currentWorkspace;
  const pathname = options.pathname
    ? options.pathname.split("?")[0].split("#")[0].trim()
    : "";

  const isPermitted = (ws?: WorkspaceId | null): ws is WorkspaceId =>
    Boolean(ws && permitted.includes(ws));

  const routeCanonical = getCanonicalWorkspaceForPath(pathname);

  // If route has a canonical workspace and it's permitted for the user's role
  if (routeCanonical && isPermitted(routeCanonical)) {
    // If route is neutral, maintain user's current workspace if permitted
    if (isNeutralRoute(pathname)) {
      if (isPermitted(current)) {
        return current;
      }
      return routeCanonical;
    }
    return routeCanonical;
  }

  // If current workspace is valid and permitted, keep it
  if (isPermitted(current)) {
    return current;
  }

  // Fall back to default workspace for role if permitted
  const defaultWs = getDefaultWorkspace(role);
  if (isPermitted(defaultWs)) {
    return defaultWs;
  }

  return permitted[0] ?? "personal";
}

/**
 * Cookie reader for workspace persistence.
 */
export function getCookieWorkspace(): WorkspaceId | null {
  if (typeof document === "undefined") return null;
  try {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const chunk of cookies) {
      const [rawKey, ...rest] = chunk.trim().split("=");
      if (rawKey !== WORKSPACE_COOKIE_NAME) continue;
      const value = decodeURIComponent(rest.join("="));
      if (isValidWorkspace(value)) {
        return value;
      }
    }
  } catch {
    return null;
  }
  return null;
}

/**
 * Cookie writer for workspace persistence.
 */
export function saveCookieWorkspace(workspace: WorkspaceId): void {
  if (typeof document === "undefined") return;
  if (!isValidWorkspace(workspace)) return;
  const secure =
    typeof window !== "undefined" && window.location?.protocol === "https:"
      ? "; Secure"
      : "";
  document.cookie = `${WORKSPACE_COOKIE_NAME}=${encodeURIComponent(workspace)}; Path=/; Max-Age=${WORKSPACE_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax${secure}`;
}

/**
 * Cookie remover for workspace persistence.
 */
export function clearCookieWorkspace(): void {
  if (typeof document === "undefined") return;
  const secure =
    typeof window !== "undefined" && window.location?.protocol === "https:"
      ? "; Secure"
      : "";
  document.cookie = `${WORKSPACE_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
}

/**
 * Reads stored workspace from localStorage (falling back to cookie).
 */
export function getStoredWorkspace(): WorkspaceId | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (isValidWorkspace(stored)) {
      return stored;
    }
    return getCookieWorkspace();
  } catch {
    return getCookieWorkspace();
  }
}

/**
 * Saves stored workspace to localStorage and cookie.
 */
export function saveStoredWorkspace(workspace: WorkspaceId): void {
  if (typeof window === "undefined") return;
  if (!isValidWorkspace(workspace)) return;
  try {
    window.localStorage.setItem(WORKSPACE_STORAGE_KEY, workspace);
  } catch {
    // Ignore storage write failures (private mode / restricted webview)
  }
  saveCookieWorkspace(workspace);
  try {
    window.dispatchEvent(
      new CustomEvent<WorkspaceId>(WORKSPACE_CHANGE_EVENT, {
        detail: workspace,
      }),
    );
  } catch {
    // noop
  }
}

/**
 * Clears stored workspace from localStorage and cookie.
 */
export function clearStoredWorkspace(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
  } catch {
    // noop
  }
  clearCookieWorkspace();
}
