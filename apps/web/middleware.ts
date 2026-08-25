import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const ACCESS_COOKIE_NAME =
  process.env.NEXT_PUBLIC_AUTH_ACCESS_COOKIE ?? "clara_access_token";
const REFRESH_COOKIE_NAME =
  process.env.NEXT_PUBLIC_AUTH_REFRESH_COOKIE ?? "clara_refresh_token";
const CLIENT_SESSION_COOKIE_NAME =
  process.env.NEXT_PUBLIC_AUTH_CLIENT_SESSION_COOKIE ?? "clara_client_session";
const AUTH_BYPASS_ENABLED =
  process.env.AUTH_BYPASS === "true" ||
  process.env.NEXT_PUBLIC_AUTH_BYPASS === "true";

const PUBLIC_PATHS = new Set([
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
  "/clinical/standards",
  "/login",
  "/register",
  "/logout",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/auth/callback",
]);

export const LEGACY_ROUTE_REDIRECTS: Record<string, string> = {
  "/ask": "/chat",
  "/health/medications": "/medicines",
  "/care/visits": "/visits",
  "/health/timeline": "/lifemap",
  "/health": "/phr",
  "/selfmed": "/medicines",
  "/careguard": "/medicines",
  "/admin/rag-sources": "/admin/knowledge-sources",
  "/admin/source-hub": "/admin/knowledge-sources",
  "/lifemap/visit-prep": "/care/prepare",
};

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  if (
    pathname.startsWith("/share/") ||
    pathname.startsWith("/chat/share/") ||
    pathname.startsWith("/phr/shared/")
  )
    return true;
  return (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  );
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (AUTH_BYPASS_ENABLED) {
    const legacyTarget = LEGACY_ROUTE_REDIRECTS[pathname];
    if (legacyTarget) {
      const redirectUrl = new URL(legacyTarget, request.url);
      redirectUrl.search = search;
      return NextResponse.redirect(redirectUrl);
    }
    return NextResponse.next();
  }

  const hasSession = Boolean(
    request.cookies.get(ACCESS_COOKIE_NAME)?.value ||
    request.cookies.get(REFRESH_COOKIE_NAME)?.value ||
    // This browser-written cookie is only a routing hint. It never grants API
    // access: AppShell immediately validates protected pages through /auth/me.
    // Keeping it here lets cookie-backed sessions recover through /auth/refresh
    // instead of being rejected by the edge before client hydration.
    request.cookies.get(CLIENT_SESSION_COOKIE_NAME)?.value,
  );

  if (isPublicPath(pathname)) {
    // The landing and authentication forms are always reachable. A stale
    // client-side session hint must never skip the login form; the API is the
    // authority and the form can safely re-authenticate or switch accounts.
    return NextResponse.next();
  }

  if (!hasSession) {
    const canonicalPath = LEGACY_ROUTE_REDIRECTS[pathname] ?? pathname;
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", `${canonicalPath}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  const legacyTarget = LEGACY_ROUTE_REDIRECTS[pathname];
  if (legacyTarget) {
    const redirectUrl = new URL(legacyTarget, request.url);
    redirectUrl.search = search;
    return NextResponse.redirect(redirectUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
