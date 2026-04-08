import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { resolvePostLoginPath } from "@/lib/navigation.config";

const ACCESS_COOKIE_NAME = process.env.NEXT_PUBLIC_AUTH_ACCESS_COOKIE ?? "clara_access_token";
const REFRESH_COOKIE_NAME = process.env.NEXT_PUBLIC_AUTH_REFRESH_COOKIE ?? "clara_refresh_token";
const CLIENT_SESSION_COOKIE_NAME =
  process.env.NEXT_PUBLIC_AUTH_CLIENT_SESSION_COOKIE ?? "clara_client_session";

const PUBLIC_PATHS = new Set([
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
  "/huong-dan"
]);

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  if (pathname.startsWith("/share/")) return true;
  return pathname.startsWith("/_next") || pathname.startsWith("/api") || pathname.includes(".");
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = Boolean(
    request.cookies.get(ACCESS_COOKIE_NAME)?.value ||
      request.cookies.get(REFRESH_COOKIE_NAME)?.value ||
      request.cookies.get(CLIENT_SESSION_COOKIE_NAME)?.value
  );

  if (isPublicPath(pathname)) {
    if (hasSession && pathname === "/") {
      const target = resolvePostLoginPath({
        nextPath: request.nextUrl.searchParams.get("next")
      });
      return NextResponse.redirect(new URL(target, request.url));
    }
    if (hasSession && (pathname === "/login" || pathname === "/register")) {
      const target = resolvePostLoginPath({
        nextPath: request.nextUrl.searchParams.get("next")
      });
      return NextResponse.redirect(new URL(target, request.url));
    }
    return NextResponse.next();
  }

  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"]
};
