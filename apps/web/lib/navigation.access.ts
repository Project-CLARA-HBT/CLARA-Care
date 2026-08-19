/**
 * Route access policy for the client shell.
 *
 * This module deliberately does not import the menu configuration. A route can
 * be authorized without being present in primary navigation, and hiding a menu
 * item must never become an authorization decision. The API remains the
 * authoritative RBAC boundary.
 */
export type UserRole = "normal" | "researcher" | "doctor" | "admin";

export const PUBLIC_ROUTES = new Set([
  "/",
  "/legal",
  "/legal/privacy",
  "/legal/terms",
  "/legal/consent",
  "/legal/cookies",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
]);

export const DEFAULT_POST_LOGIN_PATH = "/home";

const AUTH_ENTRY_ROUTES = new Set(["/login", "/register"]);
const AUTHENTICATED_UTILITY_ROUTES = new Set(["/welcome", "/role-select"]);
const AUTHENTICATED_UTILITY_PREFIXES = ["/welcome/"];

const ROLE_HOME_PATHS: Record<UserRole, string> = {
  normal: "/home",
  researcher: "/dashboard",
  doctor: "/dashboard",
  admin: "/dashboard",
};

const ALL_ROLES: UserRole[] = ["normal", "researcher", "doctor", "admin"];
const PROFESSIONAL_ROLES: UserRole[] = ["researcher", "doctor", "admin"];
const CLINICAL_ROLES: UserRole[] = ["doctor", "admin"];

const ROUTE_ACCESS: Array<{ prefix: string; roles: UserRole[] }> = [
  { prefix: "/home", roles: ALL_ROLES },
  { prefix: "/ask", roles: ALL_ROLES },
  { prefix: "/health", roles: ALL_ROLES },
  { prefix: "/care", roles: ALL_ROLES },
  { prefix: "/you", roles: ALL_ROLES },
  { prefix: "/today", roles: ALL_ROLES },
  { prefix: "/lifemap", roles: ALL_ROLES },
  { prefix: "/visits", roles: ALL_ROLES },
  { prefix: "/family", roles: ALL_ROLES },
  { prefix: "/phr", roles: ALL_ROLES },
  { prefix: "/medicines", roles: ALL_ROLES },
  { prefix: "/selfmed", roles: ALL_ROLES },
  { prefix: "/careguard", roles: ALL_ROLES },
  { prefix: "/chat", roles: ALL_ROLES },
  // Consumer research deep links remain compatible. Server policy and consent
  // still determine which research operations are available.
  { prefix: "/research", roles: ALL_ROLES },
  { prefix: "/evidence", roles: ALL_ROLES },
  { prefix: "/dashboard", roles: PROFESSIONAL_ROLES },
  { prefix: "/council", roles: CLINICAL_ROLES },
  { prefix: "/scribe", roles: CLINICAL_ROLES },
  { prefix: "/admin", roles: ["admin"] },
  { prefix: "/huong-dan", roles: ALL_ROLES },
];

const FLAG_TRUTHY = new Set(["1", "true", "on"]);

function isFlagOn(value: string | undefined): boolean {
  return typeof value === "string" && FLAG_TRUTHY.has(value.trim().toLowerCase());
}

function matchesPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

export function isPublicRoute(pathname: string): boolean {
  return (
    PUBLIC_ROUTES.has(pathname) ||
    pathname.startsWith("/share/") ||
    pathname.startsWith("/phr/shared/")
  );
}

export function isAuthenticatedUtilityRoute(pathname: string): boolean {
  return (
    AUTHENTICATED_UTILITY_ROUTES.has(pathname) ||
    AUTHENTICATED_UTILITY_PREFIXES.some((prefix) => pathname.startsWith(prefix))
  );
}

export function getRoleHomePath(role: UserRole = "normal"): string {
  return ROLE_HOME_PATHS[role] ?? DEFAULT_POST_LOGIN_PATH;
}

export function sanitizeNextPath(
  nextPath: string | null | undefined,
): string | null {
  if (!nextPath) return null;
  if (!nextPath.startsWith("/") || nextPath.startsWith("//")) return null;
  try {
    const parsed = new URL(nextPath, "http://localhost");
    if (AUTH_ENTRY_ROUTES.has(parsed.pathname)) return null;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return null;
  }
}

export function resolvePostLoginPath(options: {
  nextPath?: string | null;
  role?: UserRole;
}): string {
  return sanitizeNextPath(options.nextPath) ?? getRoleHomePath(options.role ?? "normal");
}

export function isRouteAllowedForRole(pathname: string, role: UserRole): boolean {
  if (pathname === "/community" || pathname.startsWith("/community/")) {
    return isFlagOn(process.env.NEXT_PUBLIC_SOCIAL_PLATFORM_ENABLED);
  }
  if (pathname === "/account/consent" || pathname.startsWith("/account/consent/")) {
    return isFlagOn(process.env.NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED);
  }
  if (pathname === "/account/data" || pathname.startsWith("/account/data/")) {
    return isFlagOn(process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED);
  }
  if (pathname === "/admin/dsar" || pathname.startsWith("/admin/dsar/")) {
    return role === "admin" && isFlagOn(process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED);
  }

  return ROUTE_ACCESS.some(
    (entry) => entry.roles.includes(role) && matchesPrefix(pathname, entry.prefix),
  );
}
