/**
 * Route access policy for the client shell.
 *
 * This module deliberately does not import the menu configuration or workspace
 * presentation layout. A route can be authorized without being present in
 * primary navigation, and hiding a menu item must never become an authorization
 * decision.
 *
 * SAFETY INVARIANT:
 * Server RBAC authorization is locked and authoritative. Presentation mode or
 * workspace switching (Personal, Clinical, Research, Administration) is
 * strictly a client presentation/view layout concern and never alters
 * role-based permissions or server authorization gates. The API remains the
 * authoritative RBAC boundary.
 */
export type UserRole = "normal" | "researcher" | "doctor" | "admin";

export const PUBLIC_ROUTES = new Set([
  "/",
  "/huong-dan",
  "/clinical",
  "/clinical/overview",
  "/legal",
  "/legal/privacy",
  "/legal/terms",
  "/legal/consent",
  "/legal/cookies",
  "/terms",
  "/privacy",
  "/consent",
  "/cookies",
  "/contact",
  "/safety",
  "/sources",
  "/clinical-standards",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/auth/callback",
]);

export const DEFAULT_POST_LOGIN_PATH = "/home";

const AUTH_ENTRY_ROUTES = new Set(["/login", "/register"]);
const AUTHENTICATED_UTILITY_ROUTES = new Set(["/welcome", "/role-select", "/onboarding"]);
const AUTHENTICATED_UTILITY_PREFIXES = ["/welcome/", "/onboarding/"];

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
  { prefix: "/clinical/patients", roles: CLINICAL_ROLES },
  { prefix: "/clinical", roles: ALL_ROLES },
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

function cleanPathname(pathname?: string | null): string {
  if (typeof pathname !== "string") return "/";
  const trimmed = pathname.trim();
  if (!trimmed) return "/";
  return trimmed.split("?")[0].split("#")[0].trim() || "/";
}

export function isPublicRoute(pathname?: string | null): boolean {
  const clean = cleanPathname(pathname);
  return (
    PUBLIC_ROUTES.has(clean) ||
    clean.startsWith("/share/") ||
    clean.startsWith("/chat/share/") ||
    clean.startsWith("/phr/shared/")
  );
}

export function isAuthenticatedUtilityRoute(pathname?: string | null): boolean {
  const clean = cleanPathname(pathname);
  return (
    AUTHENTICATED_UTILITY_ROUTES.has(clean) ||
    AUTHENTICATED_UTILITY_PREFIXES.some((prefix) => clean.startsWith(prefix))
  );
}

export function getRoleHomePath(role?: UserRole | null): string {
  if (!role) return DEFAULT_POST_LOGIN_PATH;
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

export function isRouteAllowedForRole(
  pathname?: string | null,
  role: UserRole = "normal",
): boolean {
  // Invariant: Admin role has full implicit access to all features across the platform in any workspace view
  if (role === "admin") {
    return true;
  }

  const clean = cleanPathname(pathname);
  if (!clean || clean === "/") {
    return false;
  }

  if (clean === "/community" || clean.startsWith("/community/")) {
    return isFlagOn(process.env.NEXT_PUBLIC_SOCIAL_PLATFORM_ENABLED);
  }
  if (clean === "/account/consent" || clean.startsWith("/account/consent/")) {
    return isFlagOn(process.env.NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED);
  }
  if (clean === "/account/data" || clean.startsWith("/account/data/")) {
    return isFlagOn(process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED);
  }
  if (clean === "/admin/dsar" || clean.startsWith("/admin/dsar/")) {
    return isFlagOn(process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED);
  }

  return ROUTE_ACCESS.some(
    (entry) => entry.roles.includes(role) && matchesPrefix(clean, entry.prefix),
  );
}
